"""Weryfikacja wartości pól (docs/04 E5–E6): LLM wyciąga, kod sprawdza.

Dla każdego liścia: wartość z LLM → normalizatory (x-normalize) → uzgodnienie z tekstem i kandydatami regex
→ walidacja (x-validate, enum, data). Rodzaj porównania (x-match.kind, domyślnie z normalizatorów):
  digits — identyfikatory i rachunki: cyfry porównywane po mapie pomyłek OCR; zgodny lub bliski (≤ max_edits)
           kandydat regex ma pierwszeństwo (zapis jak w dokumencie, np. prefiks PL rachunku);
  exact  — daty i kwoty: wartość musi wystąpić w tekście (po normalizacji wszystkich dat/kwot z tekstu);
  fuzzy  — nazwy, tytuły, e-maile, imiona: podobieństwo do tekstu (bez ogonków, wielkości liter, spacji);
           imiona i nazwiska także po rdzeniach (odmiana: „Annę Kowalską” → „Anna Kowalska”);
  none   — pola wnioskowane: tylko enum.
Wartość, której nie da się odnaleźć w tekście, jest odrzucana (null) — ochrona przed halucynacją.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date

from rapidfuzz import fuzz
from rapidfuzz.distance import Levenshtein

from . import normalize
from .config import patterns
from .normalize import OCR_DIGIT_MAP

DIGIT_NORMALIZERS = {"digits", "account", "bzp", "ted"}
EXACT_NORMALIZERS = {"date_iso", "amount"}
DEFAULTS = {"digits": {"max_edits": 1, "prefer": "candidate"},
            "fuzzy": {"accept": 0.97, "snap": 0.85, "prefer": "llm"},
            "exact": {}, "none": {}}
NULL_WORDS = {"", "null", "none", "brak", "nie dotyczy", "n/a", "-", "—"}


def fold(s: str) -> str:
    """Postać do porównań: małe litery, bez ogonków, ujednolicone cudzysłowy/myślniki, bez separatora kolumn."""
    s = unicodedata.normalize("NFKD", str(s).lower())
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).replace("ł", "l")
    s = re.sub(r"[\"'„”“«»‚’‘`]", "", s)
    s = re.sub(r"[–—‐‑−]", "-", s)
    s = s.replace(" | ", " ")
    return re.sub(r"\s+", " ", s).strip()


def _digitize(text: str) -> str:
    """Tokeny „prawie cyfrowe” (≤ 2 litery) → cyfry wg mapy pomyłek OCR; słowa bez zmian."""
    def fix(m: re.Match) -> str:
        tok = m.group(0)
        nd = sum(c.isdigit() for c in tok)
        return tok.translate(OCR_DIGIT_MAP) if nd >= 2 and nd >= len(tok) - 2 else tok
    return re.sub(r"[0-9A-Za-z|!]+", fix, text)


def only_digits(v) -> str:
    return re.sub(r"\D", "", str(v or ""))


class TextIndex:
    """Indeks tekstu dokumentu (tego, który widział LLM) do weryfikacji wartości."""

    def __init__(self, text: str):
        self.text = text
        self.folded = fold(text)
        dig = _digitize(text)
        self.runs = [only_digits(m.group(0)) for m in re.finditer(r"\d(?:[ \-./]?\d)*", dig)]
        self.dates = {d for m in re.finditer(patterns()["date"], dig, re.I) if (d := normalize.date_iso(m.group(0)))}
        amt = set()
        for rx in (patterns()["amount"], r"(?<![\d.,])\d+(?:[.,]\d{2})?(?![\d.,])"):
            for m in re.finditer(rx, dig):
                a = normalize.amount(m.group(0))
                if a is not None:
                    amt.add(round(a, 2))
        self.amounts = amt
        self.prefixes = {w[:4] for w in re.findall(r"\w+", self.folded) if len(w) >= 3}

    def digits_distance(self, d: str, max_edits: int) -> int | None:
        if not d:
            return None
        best = None
        for run in self.runs:
            if d in run:
                return 0
            if len(run) < len(d) - max_edits:
                continue
            if len(run) <= len(d) + max_edits:
                dist = Levenshtein.distance(run, d)
            else:
                dist = min(Levenshtein.distance(run[i : i + len(d)], d) for i in range(len(run) - len(d) + 1))
            if dist <= max_edits and (best is None or dist < best):
                best = dist
        return best

    def similarity(self, v: str) -> float:
        f = fold(v)
        if not f:
            return 0.0
        if f in self.folded:
            return 1.0
        return fuzz.partial_ratio(f, self.folded) / 100

    def document_form(self, v: str) -> str | None:
        """Zapis wartości tak jak w dokumencie, gdy różni się tylko spacjami, myślnikami lub cudzysłowami
        (np. LLM zamienił „2026–2027” na „2026-2027”)."""
        words = re.findall(r"\S+", v)
        if not words:
            return None
        def w(x: str) -> str:
            x = re.sub(r"[\"'„”“«»‚’‘`]", "", x)
            parts = [re.escape(c) if c not in "-–—" else "[-–—]" for c in x]
            return "[\"'„”“«»‚’‘`]?" + "".join(parts) + "[\"'„”“«»‚’‘`]?"
        rx = r"(?<!\w)" + r"\s+".join(w(x) for x in words) + r"(?!\w)"
        m = re.search(rx, self.text)  # wielkość liter z LLM (druk wersalikami to cecha wydruku, nie wartości)
        return normalize.unquote(re.sub(r"\s+", " ", m.group(0))) if m else None

    def person_match(self, v: str) -> bool:
        """Każdy człon imienia/nazwiska ma w tekście słowo o tym samym początku (odmiana przez przypadki)."""
        toks = [t for t in re.findall(r"\w+", fold(v)) if len(t) >= 3]
        return bool(toks) and all(t[:4] in self.prefixes for t in toks)


def kind_of(spec: dict) -> str:
    m = spec.get("x-match") or {}
    if m.get("kind"):
        return m["kind"]
    norm = set(spec.get("x-normalize") or [])
    if spec.get("x-source") in ("inferred", "derived") or spec.get("enum"):
        return "none"
    if norm & DIGIT_NORMALIZERS:
        return "digits"
    if norm & EXACT_NORMALIZERS:
        return "exact"
    return "fuzzy"


def _valid(spec: dict, v) -> str | None:
    """Błąd walidacji wartości końcowej albo None."""
    if v is None:
        return None
    enum = spec.get("enum")
    if enum is not None and v not in enum:
        return f"spoza enum {enum}"
    if isinstance(v, str):
        if spec.get("x-validate") and not re.search(spec["x-validate"], v):
            return f"nie spełnia {spec['x-validate']}"
        if spec.get("format") == "date":
            try:
                date.fromisoformat(v)
            except ValueError:
                return "nie jest datą"
    return None


def _cast(spec: dict, v):
    t = spec.get("type")
    ts = set(t if isinstance(t, list) else [t])
    if v is None:
        return None
    if "integer" in ts and not isinstance(v, bool):
        try:
            return int(str(v).strip())
        except ValueError:
            return v
    if "number" in ts and not isinstance(v, bool):
        try:
            return float(v)
        except (TypeError, ValueError):
            return normalize.amount(v)
    if "string" in ts and not isinstance(v, str):
        return str(v)
    return v


def strip_layout(s: str) -> str:
    """Usuwa artefakty linearyzacji z wartości: fragmenty oddzielone ' | ' bez treści (np. '… | *', '| :')."""
    if " | " not in s and not s.strip().startswith("|") and not s.strip().endswith("|"):
        return s
    parts = [x.strip() for x in s.split("|")]
    keep = [x for x in parts if len(re.findall(r"\w", x)) >= 2]
    return " ".join(keep) if keep else s


def is_null(raw) -> bool:
    return raw is None or (isinstance(raw, str) and raw.strip().lower() in NULL_WORDS) or raw == []


def reconcile(spec: dict, raw, cands: list, idx: TextIndex, fallback: bool = False,
              foreign: set[str] | None = None) -> tuple[object, dict]:
    """Wartość końcowa liścia + ślad decyzji. `fallback` = brak odpowiedzi LLM → pierwszy kandydat regex.
    `foreign` = cyfry kandydatów INNYCH pól (np. NIP-y z etykiet „NIP:” dla pola KRS)."""
    kind = kind_of(spec)
    opts = {**DEFAULTS.get(kind, {}), **(spec.get("x-match") or {})}
    norm = spec.get("x-normalize") or []
    info: dict = {"llm": raw, "kind": kind}
    if cands:
        info["candidates"] = [c.value for c in cands[:3]]

    def done(v, decision, **kw):
        v = _cast(spec, v)
        err = _valid(spec, v)
        if err:
            info.update(decision="invalid", rejected=v, error=err, **kw)
            return None, info
        info.update(decision=decision, **kw)
        return v, info

    if is_null(raw):
        if fallback and cands:
            return done(cands[0].value, "regex_fallback", raw=cands[0].raw)
        info["decision"] = "absent"
        return None, info
    if isinstance(raw, (dict, list)):
        info["decision"] = "bad_type"
        return None, info

    if isinstance(raw, str):
        raw = strip_layout(raw)
    val = normalize.apply(raw, norm) if norm else raw
    if val is None:
        info["decision"] = "unparsable"
        return None, info

    if kind == "none":
        return done(val, "inferred")

    if kind == "digits":
        d = only_digits(val)
        for c in cands:
            if only_digits(c.value) == d:
                return done(c.value, "agree")
        if foreign and d in foreign:
            # numer stoi w dokumencie przy etykiecie innego pola (np. NIP wpisany jako KRS)
            info.update(decision="other_field_value", rejected=val)
            return None, info
        maxe = int(opts.get("max_edits", 1))
        if idx.digits_distance(d, 0) == 0:
            return done(val, "in_text", distance=0)
        if cands and opts.get("prefer") == "candidate":
            dist, c = min(((Levenshtein.distance(only_digits(c.value), d), c) for c in cands), key=lambda x: x[0])
            if dist <= maxe and not _valid(spec, _cast(spec, c.value)):
                return done(c.value, "near_candidate", distance=dist)
        dist = idx.digits_distance(d, maxe)
        if dist is not None:
            return done(val, "in_text", distance=dist)
        info.update(decision="rejected_not_in_text", rejected=val)
        return None, info

    if kind == "exact":
        if "date_iso" in norm or spec.get("format") == "date":
            ok = val in idx.dates
        elif "amount" in norm:
            ok = round(float(val), 2) in idx.amounts
        else:
            ok = any(c.value == val for c in cands) or idx.similarity(str(val)) >= 1.0
        if ok:
            return done(val, "in_text")
        info.update(decision="rejected_not_in_text", rejected=val)
        return None, info

    # fuzzy
    snap = float(opts.get("snap", 0.85))
    sim = idx.similarity(str(val))
    person = "person_nominative" in norm and idx.person_match(str(val))
    info["similarity"] = round(sim, 3)
    if spec.get("x-source") == "verbatim" and sim >= 1.0:
        doc_form = idx.document_form(str(val))
        if doc_form and normalize.apply(doc_form, norm) is not None:
            v2 = normalize.apply(doc_form, norm)
            return done(v2, "in_text" if v2 == val else "document_form")
    if cands and opts.get("prefer") == "candidate" and sim < 1.0:
        best = max(cands, key=lambda c: fuzz.ratio(fold(str(c.value)), fold(str(val))))
        r = fuzz.ratio(fold(str(best.value)), fold(str(val))) / 100
        if r >= snap and not _valid(spec, best.value):
            return done(best.value, "agree" if r >= 1.0 else "near_candidate", ratio=round(r, 3))
    if sim >= snap or person:
        return done(val, "in_text" if sim >= snap else "in_text_inflected")
    info.update(decision="rejected_not_in_text", rejected=val)
    return None, info
