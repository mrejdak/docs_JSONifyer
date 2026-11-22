"""Klasyfikacja typu dokumentu (docs/02_klasyfikacja.md).

Decyduje LLM, regex jest wstępną oceną, zabezpieczeniem i trybem awaryjnym:
1. Regex (type.yaml: signals / negative_signals) liczy dla każdego typu wynik i „dowody leksykalne”
   (suma wag trafionych sygnałów pozytywnych). Daje to wstępną klasyfikację bez LLM.
2. LLM dostaje opisy WSZYSTKICH typów z configu z listą wymagań (konieczne / pomocnicze) + opcję „inny”
   i początek dokumentu (bez podpowiedzi regexu — żeby nie kotwiczyć odpowiedzi). Ocenia dokument jako
   całość: nazywa jego rodzaj, odpowiada „tak/nie” na każde wymaganie, wybiera typ, podaje stopień
   pewności (wysoka / średnia / niska — bez liczb, których modele nie kalibrują) i dosłowne cytaty.
3. Polityka (settings.classification.llm):
   - pewność poniżej min_level / LLM niedostępny / błąd → decyzja samego regexu (tryb awaryjny);
   - odpowiedź niespójna (typ bez spełnionych wymagań koniecznych albo „inny” mimo spełnionych)
                                            → pewny regex, inaczej brak typu;
   - LLM „inny”                            → brak typu ({}), nawet gdy regex wskazywał typ (weto);
   - LLM typ T i są dowody leksykalne T    → T (także wbrew regexowi — korekta);
   - LLM typ T bez dowodów leksykalnych    → T tylko przy pewności „wysoka” i cytatach znalezionych w tekście.
Nazwa pliku NIE jest używana.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import asdict, dataclass, field

from rapidfuzz import fuzz

from . import llm
from .config import CONFIG_DIR, DocType, doc_types, settings
from .patterns import compile_pattern

OTHER = "inny"


@dataclass
class Classification:
    type: str | None
    path: str     # llm+regex | llm | llm_bez_dowodow | llm_inny | llm_odrzucony | llm_niespojny | regex | regex_pewny | regex_awaryjny | brak
    reason: str = ""
    regex_type: str | None = None              # decyzja samego regexu (wstępna klasyfikacja)
    scores: dict = field(default_factory=dict)
    llm: dict | None = None                    # werdykt LLM albo błąd

    def to_dict(self) -> dict:
        return asdict(self)


# ----------------------------------------------------------------------------------------------- regex
class _Texts:
    """Cache tekstu dokumentu dla zakresów sygnałów."""

    def __init__(self, doc):
        self.doc = doc
        self._by_pages: dict[int, str] = {}

    def get(self, scope: dict) -> str:
        pages = int(scope.get("pages", settings()["classification"]["pages"]))
        if pages not in self._by_pages:
            self._by_pages[pages] = self.doc.text(pages)
        txt = self._by_pages[pages]
        chars = scope.get("chars")
        return txt[: int(chars)] if chars else txt


def score_type(dt: DocType, texts: _Texts) -> dict:
    cl = dt.classification
    tolerant = cl.get("ocr_tolerant", True)
    base_scope = cl.get("scope", {})
    pos, negw, hits, neg, missing_required = 0, 0, [], [], []
    for s in cl.get("signals", []):
        rx = compile_pattern(s["pattern"], s.get("ocr_tolerant", tolerant))
        if rx.search(texts.get({**base_scope, **s.get("scope", {})})):
            pos += s.get("weight", 1)
            hits.append(s["id"])
        elif s.get("required"):
            missing_required.append(s["id"])
    for s in cl.get("negative_signals", []):
        rx = compile_pattern(s["pattern"], s.get("ocr_tolerant", tolerant))
        if rx.search(texts.get({**base_scope, **s.get("scope", {})})):
            negw += s.get("weight", 1)
            neg.append(s["id"])
    mp = cl.get("max_pages")
    if mp and texts.doc.page_count > int(mp.get("limit", 999)):
        negw += int(mp.get("penalty", 3))
        neg.append(f"max_pages>{mp.get('limit')}")
    score = pos - negw
    if missing_required:
        neg.append("brak wymaganych: " + ",".join(missing_required))
        score = -999
    return {"score": score, "evidence": pos, "negative": negw, "hits": hits, "neg_hits": neg,
            "accept": cl.get("accept", 8), "reject": cl.get("reject", 3), "margin": cl.get("margin", 3)}


def regex_decision(scores: dict) -> tuple[str | None, bool, str]:
    """Decyzja samego regexu: (typ, pewna?, uzasadnienie). Pewna = wynik ≥ accept z marginesem."""
    ranked = sorted(scores.items(), key=lambda kv: kv[1]["score"], reverse=True)
    if not ranked:
        return None, False, "brak typów regex"
    name, best = ranked[0]
    second = ranked[1][1]["score"] if len(ranked) > 1 else -999
    if best["score"] >= best["accept"] and best["score"] - second >= best["margin"]:
        return name, True, f"regex: {name} {best['score']} ≥ {best['accept']}, margines {best['score'] - second}"
    if best["score"] >= (best["reject"] + best["accept"]) / 2 and best["score"] > second:
        return name, False, f"regex: {name} {best['score']} (strefa niepewna)"
    # „brak” z regexu nigdy nie jest pewny: dokument o nietypowej budowie może nie trafić w żaden sygnał
    return None, False, f"regex: najwyższy {name} {best['score']} — brak typu"


# ------------------------------------------------------------------------------------------------- LLM
def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).replace("ł", "l")
    return re.sub(r"\s+", " ", re.sub(r"[|]", " ", s)).strip()


def grounding(quotes: list, text: str, min_ratio: float = 85) -> float | None:
    """Odsetek cytatów-dowodów LLM znalezionych w tekście (rozmycie: błędy OCR, różnice spacji)."""
    qs = [q for q in quotes or [] if isinstance(q, str) and len(q.strip()) >= 3]
    if not qs:
        return None
    t = _norm(text)
    return sum(fuzz.partial_ratio(_norm(q), t) >= min_ratio for q in qs) / len(qs)


def excerpt(doc, cfg: dict) -> str:
    """Początek dokumentu (+ fragment ostatniej strony, gdy dokument jest dłuższy)."""
    pages = int(cfg.get("pages", 2))
    head = doc.text(pages)[: int(cfg.get("head_chars", 5000))]
    tail_chars = int(cfg.get("tail_chars", 0))
    if tail_chars and doc.page_count > pages:
        last = doc.page(doc.page_count).text.strip()
        head += f"\n[… pominięto strony {pages + 1}–{doc.page_count - 1} …]\n" if doc.page_count > pages + 1 else "\n"
        head += f"[ostatnia strona ({doc.page_count}), fragment:]\n" + last[-tail_chars:]
    return head


def _template(name: str) -> tuple[str, str]:
    raw = (CONFIG_DIR / "prompts" / name).read_text(encoding="utf-8")
    raw = re.sub(r"<!--.*?-->", "", raw, flags=re.S)
    system = raw.split("=== SYSTEM ===", 1)[1].split("=== USER ===", 1)[0].strip()
    user = raw.split("=== USER ===", 1)[1].strip()
    return system, user


def _requirements(dt: DocType) -> list[dict]:
    reqs = (dt.classification.get("semantic") or {}).get("requirements") or []
    return [{"id": r["id"], "text": r["text"], "essential": bool(r.get("essential", True))} for r in reqs]


def type_descriptions(types: dict[str, DocType]) -> str:
    out = []
    for dt in types.values():
        sem = dt.classification.get("semantic", {}) or {}
        out.append(f"- {dt.name}: {dt.title}. {' '.join(dt.description.split())}")
        for r in _requirements(dt):
            out.append(f"    • wymaganie {r['id']} ({'konieczne' if r['essential'] else 'pomocnicze'}): {r['text']}")
        for k in sem.get("not_to_confuse_with", []):
            out.append(f"    • nie mylić z: {k}")
    return "\n".join(out)


def response_format(types: dict[str, DocType]) -> dict:
    """Format odpowiedzi: rozpoznanie dokumentu i wymagania → decyzja → cytaty i uzasadnienie.
    Kolejność = tok rozumowania; długie pola na końcu, żeby ucięcie odpowiedzi nie zgubiło decyzji."""
    return {
        "rodzaj_dokumentu": "<czym jest ten dokument jako całość, kilka słów>",
        "wymagania": {dt.name: {r["id"]: "tak|nie" for r in _requirements(dt)} for dt in types.values() if _requirements(dt)},
        "typ": "<nazwa typu albo inny>",
        "pewnosc": "wysoka|srednia|niska",
        "dowody": ["<krótki dosłowny urywek, max 12 słów>", "..."],
        "uzasadnienie": "<jedno krótkie zdanie>",
    }


def build_prompt(types: dict[str, DocType], text: str, prompt_file: str = "klasyfikacja.md") -> list[dict]:
    system, user = _template(prompt_file)
    names = ", ".join(f'"{n}"' for n in [*types, OTHER])
    user = (user.replace("{{typy}}", type_descriptions(types)).replace("{{nazwy}}", names)
            .replace("{{format_json}}", json.dumps(response_format(types), ensure_ascii=False))
            .replace("{{tekst}}", text))
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


LEVELS = {"niska": 1, "srednia": 2, "wysoka": 3}


def _level(v) -> int:
    """Stopień pewności → 1..3 (słowa; liczby tylko awaryjnie, gdy model jednak zwróci liczbę)."""
    if isinstance(v, (int, float)):
        return 3 if v >= 0.85 else 2 if v >= 0.6 else 1
    s = _norm(str(v))
    for word, lvl in LEVELS.items():
        if s.startswith(word[:4]):
            return lvl
    return 0


def _yes(v) -> bool | None:
    s = _norm(str(v))
    if s in ("tak", "true", "yes", "1"):
        return True
    if s in ("nie", "false", "no", "0"):
        return False
    return None  # „częściowo”, brak odpowiedzi itp.


def requirements_met(types: dict[str, DocType], answers: dict) -> dict[str, bool | None]:
    """Dla każdego typu: czy LLM uznał wszystkie wymagania konieczne za spełnione (None = brak odpowiedzi)."""
    out = {}
    for name, dt in types.items():
        ess = [r["id"] for r in _requirements(dt) if r["essential"]]
        got = answers.get(name) if isinstance(answers, dict) else None
        if not ess or not isinstance(got, dict) or not any(k in got for k in ess):
            out[name] = None
            continue
        out[name] = all(_yes(got.get(k)) is True for k in ess)
    return out


def llm_verdict(doc, types: dict[str, DocType], cfg: dict) -> dict:
    """Werdykt LLM: {rodzaj_dokumentu, typ, pewnosc, poziom, wymagania, spelnia, spojny, dowody, grounding, …}
    albo {error}."""
    text = excerpt(doc, cfg)
    try:
        ans, meta = llm.chat_json(build_prompt(types, text, cfg.get("prompt", "klasyfikacja.md")))
    except (llm.LLMUnavailable, ValueError, json.JSONDecodeError) as e:
        return {"error": str(e)}
    typ = _norm(str(ans.get("typ", "")))
    quotes = ans.get("dowody") or []
    if isinstance(quotes, str):
        quotes = [quotes]
    met = requirements_met(types, ans.get("wymagania") or {})
    # spójność: wybrany typ ma spełnione wymagania konieczne; „inny” — żaden typ ich nie spełnia
    if typ == OTHER:
        consistent = not any(v is True for v in met.values())
    else:
        consistent = met.get(typ) is not False
    v = {"rodzaj_dokumentu": ans.get("rodzaj_dokumentu", ""), "typ": typ, "pewnosc": ans.get("pewnosc"),
         "poziom": _level(ans.get("pewnosc")), "wymagania": ans.get("wymagania"), "spelnia": met,
         "spojny": consistent, "dowody": quotes, "uzasadnienie": ans.get("uzasadnienie", ""),
         "grounding": grounding(quotes, text), "model": meta["model"], "provider": meta.get("provider"), "cached": meta["cached"],
         "naprawiony": bool(ans.get("_naprawiony"))}
    if typ not in types and typ != OTHER:
        v["error"] = f"nieznany typ w odpowiedzi: {typ!r}"
    return v


# -------------------------------------------------------------------------------------------- decyzja
def decide(scores: dict, verdict: dict | None, cfg: dict) -> tuple[str | None, str, str]:
    """Polityka łączenia regex + LLM → (typ, ścieżka, uzasadnienie). Czysta funkcja (testowana bez LLM)."""
    rtype, rsure, rreason = regex_decision(scores)
    if verdict is None:
        return rtype, "regex", rreason + " (LLM wyłączony)"
    if verdict.get("error"):
        return rtype, "regex_awaryjny", rreason + f" (LLM: {verdict['error'][:120]})"
    typ, lvl = verdict["typ"], int(verdict.get("poziom", 0))
    tag = f"LLM: {typ} ({verdict.get('pewnosc')}; {verdict.get('rodzaj_dokumentu', '')})"
    if lvl < LEVELS.get(cfg.get("min_level", "srednia"), 2):
        return rtype, "regex_awaryjny", rreason + f" ({tag} — za mała pewność)"
    if not verdict.get("spojny", True):
        # typ wybrany wbrew własnej ocenie wymagań (albo „inny”, choć wymagania typu spełnione):
        # rozstrzyga tylko pewny regex, inaczej brak typu
        return (rtype if rsure else None), "llm_niespojny", f"{tag} niespójne z wymaganiami {verdict.get('spelnia')}; " + rreason
    if typ == OTHER:
        return None, "llm_inny", tag + (f"; regex wskazywał {rtype}" if rtype else "")
    ev = scores.get(typ, {})
    if ev.get("evidence", 0) >= ev.get("reject", 3):
        path = "llm+regex" if typ == rtype else "llm"
        return typ, path, f"{tag}, dowody regex {ev['evidence']}" + ("" if typ == rtype else f"; regex: {rtype or 'brak'}")
    g = verdict.get("grounding")
    if lvl >= LEVELS.get(cfg.get("no_evidence_level", "wysoka"), 3) and (g or 0) >= float(cfg.get("grounding_min", 0.5)):
        return typ, "llm_bez_dowodow", f"{tag}, cytaty w tekście {g:.0%}, brak dowodów regex"
    return None, "llm_odrzucony", f"{tag} bez dowodów regex i potwierdzonych cytatów ({g}) → brak typu"


def classify(doc) -> Classification:
    types = doc_types()
    cfg = settings()["classification"]
    lcfg = {"pages": cfg.get("pages", 2), **(cfg.get("llm") or {})}
    texts = _Texts(doc)
    scores = {n: score_type(dt, texts) for n, dt in types.items()}
    rtype, rsure, rreason = regex_decision(scores)

    mode = cfg.get("mode", "llm_verify")
    if mode == "regex_only" or not llm.available():
        t, path, reason = decide(scores, None, lcfg)
        return Classification(t, path, reason, rtype, scores, None)
    if lcfg.get("call", "always") == "uncertain" and rsure:
        # tryb oszczędny: LLM tylko gdy regex niepewny
        return Classification(rtype, "regex_pewny", rreason, rtype, scores, None)
    verdict = llm_verdict(doc, types, lcfg)
    t, path, reason = decide(scores, verdict, lcfg)
    return Classification(t, path, reason, rtype, scores, verdict)
