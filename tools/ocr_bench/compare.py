"""A4–A8: porównanie OCR z referencją (zestaw S i jego degradacje D).

Wyniki (reports/ocr/):
  per_page.csv       — CER / CER natywny / CER łagodny / WER per konfiguracja × strona
  errors.csv         — każda operacja błędu: gdzie (strona, x, y, pole GT), co (ref→ocr), kategorie
  char_confusion.csv — pary znaków ref→ocr
  conf_bins.csv      — odsetek błędnych tokenów w przedziałach confidence
  heatmap.csv        — błędy na siatce 10×10 strony
"""

from __future__ import annotations

import json
import re
import time
from collections import Counter, defaultdict

from rapidfuzz.distance import Levenshtein

from .common import OUT, flatten, field_key, lenient, load_manifest, select_docs, strip_diacritics, write_csv
from .fields import field_class, find_spans, forms
from .layout import native_text, row_tokens
from .pdfio import extract_reference
from .run_ocr import list_configs, parse_config_id, tsv_path
from .tess import parse_tsv

PUNCT = re.compile(r"[.,:;\-/()\"'!?\[\]]")
SPECIAL = set("@§_#%&*+=<>|\\~^$")
DIGIT_LETTER = {
    frozenset(p)
    for p in [("0", "O"), ("0", "o"), ("0", "D"), ("1", "l"), ("1", "I"), ("1", "i"), ("1", "|"), ("1", "!"),
              ("5", "S"), ("5", "s"), ("8", "B"), ("2", "Z"), ("2", "z"), ("6", "G"), ("6", "b"), ("9", "g"), ("4", "A"), ("7", "T")]
}
DIACRITIC_CHARS = set("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ")
CONF_BINS = [(0, 50), (50, 70), (70, 85), (85, 95), (95, 101)]
NAME_CLASSES = {"osoba", "nazwa_podmiotu", "miejscowosc"}


# ----------------------------------------------------------------------------- wyrównanie


MAX_SPLIT = 6
MAX_BLOCK_CELLS = 4000


def align_block(R: list[str], O: list[str]) -> list[tuple[str, list[int], list[int]]]:
    """Wyrównanie bloku niezgodności: sub (1-1), split (1-k), merge (k-1), del (1-0), ins (0-1)."""
    n, m = len(R), len(O)
    if n * m > MAX_BLOCK_CELLS:  # duży, zaszumiony blok — bez dokładnego wyrównania
        k = min(n, m)
        return [("sub", [i], [i]) for i in range(k)] + [("del", [i], []) for i in range(k, n)] + [("ins", [], [j]) for j in range(k, m)]
    nd = Levenshtein.normalized_distance
    INF = float("inf")
    cost = [[INF] * (m + 1) for _ in range(n + 1)]
    back: list[list[tuple | None]] = [[None] * (m + 1) for _ in range(n + 1)]
    cost[0][0] = 0.0
    for i in range(n + 1):
        for j in range(m + 1):
            c = cost[i][j]
            if c == INF:
                continue
            moves = []
            if i < n and j < m:
                moves.append(("sub", 1, 1, nd(R[i], O[j])))
            if i < n:
                moves.append(("del", 1, 0, 1.0))
            if j < m:
                moves.append(("ins", 0, 1, 1.0))
            for k in range(2, MAX_SPLIT + 1):
                if i < n and j + k <= m:
                    moves.append(("split", 1, k, nd(R[i], "".join(O[j : j + k])) + 0.1 * (k - 1)))
                if i + k <= n and j < m:
                    moves.append(("merge", k, 1, nd("".join(R[i : i + k]), O[j]) + 0.1 * (k - 1)))
            for kind, di, dj, mc in moves:
                if c + mc < cost[i + di][j + dj]:
                    cost[i + di][j + dj] = c + mc
                    back[i + di][j + dj] = (kind, di, dj)
    out = []
    i, j = n, m
    while i or j:
        kind, di, dj = back[i][j]
        out.append((kind, list(range(i - di, i)), list(range(j - dj, j))))
        i, j = i - di, j - dj
    return out[::-1]


def char_ops(r: str, o: str) -> list[tuple[str, str]]:
    ops = []
    for tag, s, d in Levenshtein.editops(r, o):
        if tag == "replace":
            ops.append((r[s], o[d]))
        elif tag == "delete":
            ops.append((r[s], ""))
        else:
            ops.append(("", o[d]))
    return ops


def error_types(kind: str, r: str, o: str, ops: list[tuple[str, str]]) -> list[str]:
    t: set[str] = set()
    if kind in ("split", "merge"):
        t.add("podzial_slow")
    if kind == "del":
        return ["pominiete"]
    if kind == "ins":
        return ["nadmiarowe"]
    if r == o:
        return sorted(t) or ["inne"]
    if strip_diacritics(r) == strip_diacritics(o):
        t.add("diakrytyki")
    elif r.casefold() == o.casefold():
        t.add("wielkosc_liter")
    elif PUNCT.sub("", r) == PUNCT.sub("", o):
        t.add("interpunkcja")
    else:
        for a, b in ops:
            if frozenset((a, b)) in DIGIT_LETTER:
                t.add("cyfra_litera")
            if (a in DIACRITIC_CHARS and strip_diacritics(a) in (b, "")) or (b in DIACRITIC_CHARS and strip_diacritics(b) == a):
                t.add("diakrytyki")
            if a in SPECIAL or b in SPECIAL:
                t.add("znaki_specjalne")
            if (a and PUNCT.fullmatch(a)) or (b and PUNCT.fullmatch(b)):
                t.add("interpunkcja")
    return sorted(t) or ["inne"]


def _vocab_key(tok: str) -> str:
    return PUNCT.sub("", lenient(tok))


def token_type(tok: str, in_field: str, common: set[str]) -> str:
    if not tok:
        return "-"
    if len(re.findall(r"\d", tok)) >= 4:
        return "identyfikator"
    core = PUNCT.sub("", tok)
    if (len(tok) <= 6 and tok.endswith(".") and core.isalpha()) or (2 <= len(core) <= 6 and core.isalpha() and core.isupper()):
        return "skrot"
    if in_field and field_class(in_field) in NAME_CLASSES:
        return "nazwa_wlasna"
    if core[:1].isupper() and _vocab_key(tok) not in common:
        return "nazwa_wlasna"
    if any(ch.isdigit() for ch in tok):
        return "liczba"
    return "zwykle"


# ----------------------------------------------------------------------------- dane pomocnicze


def build_common_vocab(docs, min_df: int = 15) -> set[str]:
    df: Counter = Counter()
    for d in docs:
        ref = extract_reference(d)
        seen = {_vocab_key(t["t"]) for pg in ref["pages"] for ln in pg["lines"] for t in ln["tokens"]}
        df.update(seen)
    return {w for w, c in df.items() if c >= min_df}


def gt_forms(doc) -> list[tuple[str, object]]:
    gt = doc.load_gt()
    if not gt:
        return []
    out = []
    for path, val in flatten(gt):
        fm = forms(path, val)
        if fm:
            out.append((field_key(path), fm))
    return out


def token_fields(tokens: list[str], text: str, fms) -> list[str]:
    """Dla każdego tokenu: ścieżka pola GT, do którego wartości należy (lub '')."""
    offs, pos = [], 0
    for t in tokens:
        offs.append((pos, pos + len(t)))
        pos += len(t) + 1
    res = [""] * len(tokens)
    for key, fm in fms:
        for s, e in find_spans(fm, text):
            for i, (a, b) in enumerate(offs):
                if a < e and b > s and not res[i]:
                    res[i] = key
    return res


# ----------------------------------------------------------------------------- główna pętla


LEADER = re.compile(r"^[._\-…·:]{3,}$")  # kropki/kreski do podpisu — bez treści


def _is_spaced_letter(t: dict) -> bool:
    return len(t["t"]) == 1 and t["t"].isalpha() and t["t"].isupper()


def _content(tokens: list[dict]) -> list[dict]:
    """Bez kropek do podpisu; rozstrzelone nagłówki (P E Ł N O …, ≥3 litery) scalone w jedno słowo."""
    tokens = [t for t in tokens if not LEADER.match(t["t"])]
    out, i = [], 0
    while i < len(tokens):
        j = i
        while j < len(tokens) and _is_spaced_letter(tokens[j]):
            j += 1
        if j - i >= 3:
            run = tokens[i:j]
            bb = [min(t["bbox"][0] for t in run), min(t["bbox"][1] for t in run),
                  max(t["bbox"][2] for t in run), max(t["bbox"][3] for t in run)]
            out.append({"t": "".join(t["t"] for t in run), "bbox": bb, "conf": run[0]["conf"]})
            i = j
        else:
            out.append(tokens[i])
            i += 1
    return out


def _blocks(opcodes):
    """Łączy sąsiednie operacje niezgodności w bloki (insert+replace itp. → jeden blok)."""
    cur = None
    for op in opcodes:
        if op.tag == "equal":
            if cur:
                yield cur
                cur = None
            continue
        if cur is None:
            cur = [op.src_start, op.src_end, op.dest_start, op.dest_end]
        else:
            cur[1], cur[3] = op.src_end, op.dest_end
    if cur:
        yield cur


def compare_page(ref_page: dict, ocr_page: dict, fms, common: set[str]):
    rt = _content(row_tokens(ref_page))
    ot = _content(row_tokens(ocr_page))
    R = [t["t"] for t in rt]
    O = [t["t"] for t in ot]
    ref_str, ocr_str = " ".join(R), " ".join(O)
    nat_str = " ".join(t for t in native_text(ocr_page).split() if not LEADER.match(t))
    n = max(1, len(ref_str))
    char_err = Levenshtein.distance(ref_str, ocr_str)
    stats = {
        "ref_chars": len(ref_str),
        "ref_tokens": len(R),
        "char_errors": char_err,
        "cer": char_err / n,
        "cer_native": Levenshtein.distance(ref_str, nat_str) / n,
        "cer_lenient": Levenshtein.distance(lenient(ref_str), lenient(ocr_str)) / n,
        "wer": Levenshtein.distance(R, O) / max(1, len(R)),
    }
    infield = token_fields(R, ref_str, fms)
    errors = []
    ref_wrong = [False] * len(R)
    ocr_wrong = [False] * len(O)
    for s0, s1, d0, d1 in _blocks(Levenshtein.opcodes(R, O)):
        rs, os_ = list(range(s0, s1)), list(range(d0, d1))
        items = [(k, [rs[i] for i in ri], [os_[j] for j in oj]) for k, ri, oj in align_block([R[i] for i in rs], [O[j] for j in os_])]
        for kind, ri, oj in items:
            r = "".join(R[i] for i in ri)
            o = "".join(O[j] for j in oj)
            if kind == "sub" and r == o:
                continue
            for i in ri:
                ref_wrong[i] = True
            for j in oj:
                ocr_wrong[j] = True
            ops = char_ops(r, o)
            anchor = rt[ri[0]] if ri else ot[oj[0]]
            bb = anchor["bbox"]
            fld = infield[ri[0]] if ri else ""
            ctx_i = ri[0] if ri else s0
            errors.append(
                {
                    "kind": kind,
                    "ref": " ".join(R[i] for i in ri),
                    "ocr": " ".join(O[j] for j in oj),
                    "char_ops": " ".join(f"{a or '∅'}→{b or '∅'}" for a, b in ops),
                    "error_type": "|".join(error_types(kind, r, o, ops)),
                    "token_type": token_type(R[ri[0]] if ri else "", fld, common),
                    "in_field": fld,
                    "conf": min((ot[j]["conf"] for j in oj), default=""),
                    "x": round((bb[0] + bb[2]) / 2, 3),
                    "y": round((bb[1] + bb[3]) / 2, 3),
                    "context": " ".join(R[max(0, ctx_i - 5) : ctx_i + 6]),
                    "_ops": ops,
                }
            )
    return stats, errors, rt, ref_wrong, ot, ocr_wrong


def run_compare(config_filter: str = "") -> None:
    t0 = time.perf_counter()
    docs = select_docs(load_manifest(), "S")
    common = build_common_vocab(docs)
    fms_cache = {d.doc_id: gt_forms(d) for d in docs}
    rx = re.compile(config_filter) if config_filter else None
    configs = [c for c in list_configs() if not rx or rx.search(c)]

    per_page, all_errors = [], []
    confusion: Counter = Counter()
    conf_bins: dict = defaultdict(lambda: [0, 0])
    heat: dict = defaultdict(lambda: [0, 0])
    for cid in configs:
        cfg = parse_config_id(cid)
        for d in docs:
            ref = None
            for page in range(1, d.pages + 1):
                tp = tsv_path(cid, d.doc_id, page)
                if not tp.exists():
                    continue
                ref = ref or extract_reference(d)
                ocr_page = parse_tsv(tp.read_text(encoding="utf-8"))
                meta_p = tp.with_suffix(".json")
                meta = json.loads(meta_p.read_text()) if meta_p.exists() else {}
                stats, errors, rt, ref_wrong, ot, ocr_wrong = compare_page(ref["pages"][page - 1], ocr_page, fms_cache[d.doc_id], common)
                base = {**cfg, "doc_id": d.doc_id, "label": d.label, "page": page}
                per_page.append({**base, **{k: round(v, 5) if isinstance(v, float) else v for k, v in stats.items()},
                                 "n_error_ops": len(errors), "ocr_seconds": meta.get("ocr_seconds", "")})
                for e in errors:
                    for a, b in e.pop("_ops"):
                        confusion[(cid, a, b)] += 1
                    all_errors.append({"config": cid, "doc_id": d.doc_id, "label": d.label, "page": page, **e})
                for t, wrong in zip(ot, ocr_wrong):
                    c = t["conf"] if t["conf"] is not None else -1
                    cls = "identyfikator" if len(re.findall(r"\d", t["t"])) >= 4 else "inne"
                    for lo, hi in CONF_BINS:
                        if lo <= c < hi:
                            for k in (cls, "wszystkie"):
                                conf_bins[(cid, k, f"{lo}-{min(hi, 100)}")][0] += 1
                                conf_bins[(cid, k, f"{lo}-{min(hi, 100)}")][1] += wrong
                for t, wrong in zip(rt, ref_wrong):
                    bb = t["bbox"]
                    gx = min(9, max(0, int((bb[0] + bb[2]) / 2 * 10)))
                    gy = min(9, max(0, int((bb[1] + bb[3]) / 2 * 10)))
                    heat[(cid, gx, gy)][0] += 1
                    heat[(cid, gx, gy)][1] += wrong
        print(f"[compare] {cid}: {sum(1 for r in per_page if r['config'] == cid)} stron", flush=True)

    write_csv(OUT / "per_page.csv", per_page)
    write_csv(OUT / "errors.csv", all_errors,
              ["config", "doc_id", "label", "page", "kind", "ref", "ocr", "char_ops", "error_type", "token_type", "in_field", "conf", "x", "y", "context"])
    write_csv(OUT / "char_confusion.csv",
              [{"config": c, "ref": a or "∅", "ocr": b or "∅", "count": n} for (c, a, b), n in confusion.most_common()])
    write_csv(OUT / "conf_bins.csv",
              [{"config": c, "token_class": k, "bin": b, "n_tokens": v[0], "n_wrong": v[1], "error_rate": round(v[1] / v[0], 4) if v[0] else ""}
               for (c, k, b), v in sorted(conf_bins.items())])
    write_csv(OUT / "heatmap.csv",
              [{"config": c, "gx": gx, "gy": gy, "n_tokens": v[0], "n_err": v[1]} for (c, gx, gy), v in sorted(heat.items())])
    print(f"[compare] {len(configs)} konfiguracji, {len(per_page)} stron, {len(all_errors)} błędów, {time.perf_counter() - t0:.0f}s")
