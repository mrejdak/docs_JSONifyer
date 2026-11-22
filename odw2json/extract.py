"""Ekstrakcja pól (docs/04_ekstrakcja_i_walidacja.md): LLM wyciąga wartości, kod normalizuje i weryfikuje.

1. Wywołania LLM z `llm_calls` w type.yaml (równolegle). Prompt = wspólny szablon config/prompts/ekstrakcja.md
   + instrukcja wywołania (config/types/<typ>/prompts/<plik>) + wymagania pól i format JSON generowane ze
   schema.json (pola z x-llm-call = nazwa wywołania). Kontekst: pierwsze strony dokumentu (bez sekcji
   wycinanych regexem).
2. Złożenie wyniku wg schematu (kolejność kluczy, listy: x-max-items / minItems).
3. Każdy liść: normalizacja → weryfikacja w tekście, który widział LLM, i z kandydatami regex (verify.py).
4. Pola pochodne (x-derived-from + słownik) i reguły spójności (`consistency` w type.yaml).
Bez LLM (brak klucza / błąd wywołania): pola wywołania z pierwszego kandydata regex w sekcji `x-section`
(sekcje z type.yaml) — tryb awaryjny o świadomie niższej jakości.
"""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor

from . import llm
from .candidates import find_candidates
from .classify import _template, excerpt
from .config import DocType, dictionary, settings
from .patterns import compile_pattern
from .schema import is_leaf, validate
from .verify import TextIndex, is_null, reconcile


# ------------------------------------------------------------------------------------------- schemat
def _is_array(s: dict) -> bool:
    t = s.get("type")
    return t == "array" or (isinstance(t, list) and "array" in t)


def subschema(schema: dict, call: str) -> dict | None:
    """Schemat obcięty do pól danego wywołania (struktura zachowana)."""
    if is_leaf(schema):
        return schema if schema.get("x-llm-call") == call else None
    if _is_array(schema):
        items = subschema(schema.get("items", {}), call)
        return {**schema, "items": items} if items else None
    props = {k: s for k, v in schema.get("properties", {}).items() if (s := subschema(v, call))}
    return {**schema, "properties": props} if props else None


def _hint(s: dict) -> str:
    enum = [e for e in s.get("enum") or [] if e is not None]
    if enum:
        if len(enum) <= 4:
            return "|".join(map(str, enum)) + "|null"
        return f"liczba {min(enum)}–{max(enum)} ze słownika albo null"
    if s.get("format") == "date":
        return "RRRR-MM-DD albo null"
    ts = set(s.get("type") if isinstance(s.get("type"), list) else [s.get("type")])
    if "number" in ts:
        return "liczba albo null"
    if "integer" in ts:
        return "liczba całkowita albo null"
    return "tekst albo null"


def example(s: dict):
    if is_leaf(s):
        return _hint(s)
    if _is_array(s):
        return [example(s.get("items", {}))]
    return {k: example(v) for k, v in s.get("properties", {}).items()}


def _leaves(s: dict, prefix: str = ""):
    if is_leaf(s):
        yield prefix, s
    elif _is_array(s):
        yield from _leaves(s.get("items", {}), prefix + "[]")
    else:
        for k, v in s.get("properties", {}).items():
            yield from _leaves(v, f"{prefix}.{k}" if prefix else k)


def field_requirements(sub: dict, extra: dict) -> str:
    out = [f"- {k}: {v}" for k, v in extra.items()]
    for path, s in _leaves(sub):
        out.append(f"- {path}: {' '.join(s.get('description', '').split())}")
    return "\n".join(out)


def dictionaries_text(sub: dict) -> str:
    out = []
    for path, s in _leaves(sub):
        name = s.get("x-dictionary")
        if not name or s.get("x-source") != "inferred":
            continue
        d = dictionary(name)
        out.append(f"\nSłownik dla pola {path} (wartość = numer; po myślniku przykładowe sformułowania):")
        for k, e in d.get("entries", {}).items():
            hints = "; ".join(e.get("hints", []))
            out.append(f"  {k} = {e['opis']}" + (f" — {hints}" if hints else ""))
    return "\n".join(out) + ("\n" if out else "")


def _reorder(obj: dict, order: list[str]) -> dict:
    """Kolejność pól w formacie dla LLM (llm_calls.<n>.field_order): wskazane ścieżki na początek swojego
    obiektu. Wynik i tak jest składany w kolejności schematu."""
    for path in order:
        parts = path.split(".")
        node = obj
        for p in parts[:-1]:
            node = node.get(p) if isinstance(node, dict) else None
            if isinstance(node, list):
                node = node[0] if node else None
        if isinstance(node, dict) and parts[-1] in node:
            items = list(node.items())
            node.clear()
            node[parts[-1]] = dict(items)[parts[-1]]
            node.update((k, v) for k, v in items if k != parts[-1])
    return obj


def build_prompt(dt: DocType, call_name: str, call: dict, text: str) -> list[dict]:
    sub = subschema(dt.schema, call_name) or {}
    extra = call.get("extra") or {}
    fmt = {**{k: v for k, v in extra.items()}, **_reorder(example(sub), list(call.get("field_order") or []))}
    system, user = _template(call.get("template", "ekstrakcja.md"))
    instr = (dt.dir / "prompts" / call["prompt"]).read_text(encoding="utf-8").strip() if call.get("prompt") else ""
    user = (user.replace("{{typ_opis}}", f"{dt.title}. {' '.join(dt.description.split())}")
            .replace("{{instrukcja}}", instr)
            .replace("{{pola}}", field_requirements(sub, extra))
            .replace("{{slowniki}}", dictionaries_text(sub))
            .replace("{{format_json}}", json.dumps(fmt, ensure_ascii=False))
            .replace("{{tekst}}", text))
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def call_context(doc, call: dict) -> str:
    ctx = call.get("context") or {}
    return excerpt(doc, {"pages": ctx.get("pages", 2), "head_chars": ctx.get("max_chars", 6000),
                         "tail_chars": ctx.get("tail_chars", 0)})


# --------------------------------------------------------------------------------------------- ścieżki
def _tok(path: str) -> list:
    out = []
    for part in path.split("."):
        m = re.match(r"^([^\[]+)((?:\[(?:\*|\d+)\])*)$", part)
        out.append(m.group(1))
        for ix in re.findall(r"\[(\*|\d+)\]", m.group(2)):
            out.append("*" if ix == "*" else int(ix))
    return out


def _expand(obj, toks: list, acc: list | None = None) -> list[list]:
    """Konkretne ścieżki (listy kluczy/indeksów) pasujące do ścieżki z [*]."""
    acc = acc or []
    if not toks:
        return [acc]
    t, rest = toks[0], toks[1:]
    if t == "*":
        if not isinstance(obj, list):
            return []
        return [p for i, it in enumerate(obj) for p in _expand(it, rest, acc + [i])]
    if isinstance(t, int):
        return _expand(obj[t], rest, acc + [t]) if isinstance(obj, list) and t < len(obj) else []
    if isinstance(obj, dict) and t in obj:
        return _expand(obj[t], rest, acc + [t])
    return []


def _get(obj, path: list):
    for t in path:
        obj = obj[t]
    return obj


def _set(obj, path: list, v):
    for t in path[:-1]:
        obj = obj[t]
    obj[path[-1]] = v


def apply_derived(dt: DocType, result: dict, trace: dict) -> None:
    for path, s in _leaves(dt.schema):
        src = s.get("x-derived-from")
        if not src:
            continue
        d = dictionary(s["x-dictionary"]).get("entries", {}) if s.get("x-dictionary") else {}
        for p in _expand(result, _tok(path.replace("[]", "[*]"))):
            sp = _tok(src)
            try:
                key = _get(result, sp)
            except (KeyError, IndexError, TypeError):
                key = None
            val = d.get(str(key), {}).get("opis") if key is not None else None
            _set(result, p, val)
            trace[path] = {"decision": "derived", "from": src, "value": val}


def apply_consistency(dt: DocType, result: dict) -> list[str]:
    """Reguły spójności z type.yaml. [*] w warunku wiąże ten sam indeks w akcjach z tym samym prefiksem listy."""
    log = []
    for ri, rule in enumerate(dt.raw.get("consistency") or []):
        cond, then = rule.get("if", {}), rule.get("then", {})
        targets = list(then.get("set_null", [])) + list((then.get("set") or {}).keys())
        if "count" in cond:
            try:
                n = len(_get(result, _tok(cond["count"])) or [])
            except (KeyError, IndexError, TypeError):
                n = 0
            bindings = [None] if n == cond.get("eq") else []
            prefix = None
        else:
            cp = cond["path"]
            prefix = cp.split("[*]")[0] if "[*]" in cp else None
            n = len(_get(result, _tok(prefix)) or []) if prefix else 0
            bindings = list(range(n)) if prefix else [None]
        for b in bindings:
            def bind(p: str) -> str:
                return p.replace(f"{prefix}[*]", f"{prefix}[{b}]", 1) if prefix and b is not None else p
            if "count" not in cond:
                paths = _expand(result, _tok(bind(cond["path"])))
                if not paths:
                    continue
                v = _get(result, paths[0])
                if "eq" in cond and v != cond["eq"]:
                    continue
                if cond.get("not_null") and v is None:
                    continue
            for t in targets:
                newv = None if t in then.get("set_null", []) else then["set"][t]
                for p in _expand(result, _tok(bind(t))):
                    if _get(result, p) != newv:
                        _set(result, p, newv)
                        log.append(f"reguła {ri}: {'.'.join(map(str, p))} → {newv}")
    return log


# ------------------------------------------------------------------------------------------- sekcje
def section_texts(dt: DocType, text: str) -> dict[str, str]:
    """Sekcje z type.yaml (tylko tryb awaryjny bez LLM): od dopasowania `start` do `end` / początku innej sekcji."""
    secs = dt.raw.get("sections") or {}
    starts = {}
    for name, s in secs.items():
        m = compile_pattern(s["start"]).search(text)
        if m:
            starts[name] = m.start()
    out = {}
    for name, s in secs.items():
        if name in starts:
            st = starts[name]
            ends = [p for n, p in starts.items() if n != name and p > st]
            if s.get("end"):
                m = compile_pattern(s["end"]).search(text, st + 1)
                if m:
                    ends.append(m.start())
            out[name] = text[st : min(ends) if ends else len(text)]
        elif (s.get("fallback") or {}).get("chars"):
            out[name] = text[: int(s["fallback"]["chars"])]
        elif s.get("fallback"):
            out[name] = text
    return out


# ------------------------------------------------------------------------------------------ złożenie
def _key(obj: dict, k: str):
    if k in obj:
        return obj[k]
    nk = re.sub(r"[\W_]", "", k.lower())
    for kk, v in obj.items():
        if re.sub(r"[\W_]", "", str(kk).lower()) == nk:
            return v
    return None


class _Ctx:
    def __init__(self, dt: DocType, idx: TextIndex, failed: set[str], sections: dict[str, str], extras: dict):
        self.dt, self.idx, self.failed, self.sections = dt, idx, failed, sections
        self.extras = extras  # pola pomocnicze z odpowiedzi LLM (klucze „_…”), np. cytat nagłówka
        self.trace: dict = {}
        self._cands: dict = {}
        self._ev: dict = {}

    def evidence(self, name: str) -> TextIndex | None:
        """Indeks cytatu-dowodu (x-evidence) — None, gdy cytatu brak albo nie występuje w tekście."""
        if name not in self._ev:
            q = self.extras.get(name)
            ok = isinstance(q, str) and not is_null(q) and self.idx.similarity(q) >= 0.85
            self._ev[name] = TextIndex(q) if ok else None
        return self._ev[name]

    def cands(self, spec: dict, path: str, fallback: bool):
        key = (id(spec), fallback)  # kandydaci liczeni raz na pole (wszystkie elementy listy)
        if key not in self._cands:
            if not spec.get("x-candidates"):
                self._cands[key] = []
            else:
                text = self.idx.text
                if fallback and spec.get("x-section"):
                    text = self.sections.get(spec["x-section"], "")
                self._cands[key] = find_candidates(spec, text)
        return self._cands[key]

    def leaf(self, spec: dict, raw, path: str):
        fallback = spec.get("x-llm-call") in self.failed and spec.get("x-source") != "derived"
        if fallback and re.search(r"\[[1-9]\d*\]", path):
            fallback = False  # tryb awaryjny wypełnia tylko pierwszy element listy
        ev = spec.get("x-evidence")
        if ev and not fallback:
            # wartość musi pochodzić z cytatu-dowodu (np. linii nagłówka), który sam występuje w tekście
            eidx = self.evidence(ev)
            if eidx is None:
                self.trace[path] = {"llm": raw, "decision": "no_evidence", "evidence": ev, "quote": self.extras.get(ev)}
                return None
            v, info = reconcile(spec, raw, find_candidates(spec, eidx.text), eidx)
            info["evidence"] = ev
        else:
            v, info = reconcile(spec, raw, self.cands(spec, path, fallback), self.idx, fallback,
                                self.foreign(spec, path))
        self.trace[path] = info
        return v

    def foreign(self, spec: dict, path: str) -> set[str]:
        """Cyfry kandydatów regex pól o INNEJ nazwie (krs ↔ nip ↔ regon ↔ pesel …) — wartość, która w
        dokumencie stoi przy etykiecie innego pola, nie może trafić do tego pola."""
        if not hasattr(self, "_digit_fields"):
            from .verify import kind_of, only_digits
            self._digit_fields = {}
            for p, s in _leaves(self.dt.schema):
                if s.get("x-candidates") and kind_of(s) == "digits":
                    name = p.split(".")[-1]
                    self._digit_fields.setdefault(name, set()).update(
                        only_digits(c.value) for c in self.cands(s, p, False))
        name = path.split(".")[-1]
        return set().union(*(v for k, v in self._digit_fields.items() if k != name)) if self._digit_fields else set()


def _all_null(o) -> bool:
    if isinstance(o, dict):
        return all(_all_null(v) for v in o.values())
    if isinstance(o, list):
        return all(_all_null(v) for v in o)
    return o is None


def assemble(schema: dict, ans, path: str, ctx: _Ctx):
    if is_leaf(schema):
        return ctx.leaf(schema, ans, path)
    if _is_array(schema):
        items = ans if isinstance(ans, list) else ([ans] if isinstance(ans, dict) else [])
        mx = schema.get("x-max-items")
        items = items[: int(mx)] if mx else items
        out = [assemble(schema.get("items", {}), it, f"{path}[{i}]", ctx) for i, it in enumerate(items)]
        out = [o for o in out if not _all_null(o)]
        while len(out) < int(schema.get("minItems", 0)):
            out.append(assemble(schema.get("items", {}), None, f"{path}[{len(out)}]", ctx))
        return out
    obj = ans if isinstance(ans, dict) else {}
    return {k: assemble(v, _key(obj, k), f"{path}.{k}" if path else k, ctx)
            for k, v in schema.get("properties", {}).items()}


def _merge(a, b):
    if isinstance(a, dict) and isinstance(b, dict):
        out = dict(a)
        for k, v in b.items():
            out[k] = _merge(out[k], v) if k in out else v
        return out
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        return [_merge(x, y) for x, y in zip(a, b)]
    return b if a is None else a


# --------------------------------------------------------------------------------------------- wejście
def _run_call(doc, dt: DocType, name: str, call: dict) -> dict:
    text = call_context(doc, call)
    try:
        ans, meta = llm.chat_json(build_prompt(dt, name, call, text))
    except (llm.LLMUnavailable, ValueError, json.JSONDecodeError) as e:
        return {"text": text, "error": str(e)}
    return {"text": text, "answer": ans, "model": meta["model"], "provider": meta.get("provider"), "cached": meta["cached"],
            "repaired": bool(ans.pop("_naprawiony", False)) if isinstance(ans, dict) else False}


def extract(doc, dt: DocType) -> tuple[dict, dict]:
    cfg = settings().get("extraction") or {}
    calls = dt.raw.get("llm_calls") or {}
    use_llm = cfg.get("mode", "llm") != "regex_only" and llm.available()
    runs: dict[str, dict] = {}
    if use_llm and calls:
        with ThreadPoolExecutor(max_workers=max(1, min(len(calls), int(cfg.get("parallel_calls", 3))))) as ex:
            futs = {n: ex.submit(_run_call, doc, dt, n, c) for n, c in calls.items()}
            runs = {n: f.result() for n, f in futs.items()}
    else:
        for n, c in calls.items():
            runs[n] = {"text": call_context(doc, c), "error": "LLM wyłączony / niedostępny"}

    failed = {n for n, r in runs.items() if r.get("error")}
    merged: dict = {}
    for n, r in runs.items():
        if isinstance(r.get("answer"), dict):
            merged = _merge(merged, r["answer"])
    # tekst do weryfikacji = to, co widział LLM (suma kontekstów wywołań)
    seen = []
    for r in runs.values():
        if r["text"] not in seen:
            seen.append(r["text"])
    full = "\n".join(seen)
    idx = TextIndex(full)
    extras = {k: v for k, v in merged.items() if str(k).startswith("_")}
    ctx = _Ctx(dt, idx, failed, section_texts(dt, full) if failed else {}, extras)
    result = assemble(dt.schema, merged, "", ctx)
    apply_derived(dt, result, ctx.trace)
    rules = apply_consistency(dt, result)
    errors = validate(result, dt.schema)
    trace = {
        "mode": "llm" if use_llm else "regex_only",
        "calls": {n: {k: v for k, v in r.items() if k != "text"} | {"context_chars": len(r["text"])} for n, r in runs.items()},
        "extras": extras, "fields": ctx.trace, "consistency": rules, "schema_errors": errors,
    }
    return result, trace
