"""Ewaluacja ekstrakcji — F1 na poziomie liści (docs/04 §9.1).

Liść: TP gdy pred = GT (także null/null — poprawnie rozpoznany brak informacji, FAQ pkt 6);
FP gdy pred ≠ null i różne od GT; FN gdy GT ≠ null i pred różne od GT (błędna wartość = FP + FN).
Listy (Zamawiajacy, mocodawca, podpisujacy, pelnomocnicy…) parowane optymalnie (maks. liczba zgodnych liści).
Dokument negatywny (tylko --classify): GT {} → pred {} = 1 TP, inaczej niepuste liście pred = FP.

Porównanie wartości: stringi po zwinięciu spacji; liczby numerycznie; pesel jako tekst; numer_bzp bez spacji;
rachunki BEZ prefiksu kraju (GT treningowe gubi „PL”, który aplikacja celowo zachowuje — patrz PROGRESS).
Etykiety typu z nazw plików (TYLKO tutaj). Domyślnie typ z etykiety (ocena samej ekstrakcji);
--classify = pełny potok (klasyfikacja + ekstrakcja, z negatywami).

  .venv\\Scripts\\python -m tools.eval_extraction                     # S + K, tekst auto
  .venv\\Scripts\\python -m tools.eval_extraction --set K --workers 4
  .venv\\Scripts\\python -m tools.eval_extraction --llm off          # tryb awaryjny regex
  .venv\\Scripts\\python -m tools.eval_extraction --classify         # end-to-end
Wyniki: reports/extraction/summary_<tag>.md, per_field_<tag>.csv, errors_<tag>.csv
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import re
import sys
import time
import warnings
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed

warnings.filterwarnings("ignore", category=FutureWarning)

from odw2json.config import APP_ROOT, doc_types  # noqa: E402
from tools.ocr_bench.common import load_manifest, write_csv  # noqa: E402

OUT = APP_ROOT / "reports" / "extraction"
NONE = "brak"
ACCOUNT_KEYS = ("z_rachunku", "na_rachunek")


# ------------------------------------------------------------------------------------------ porównanie
def norm_value(key: str, v):
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)) and key.split(".")[-1] not in ("pesel",):
        return float(v)
    s = re.sub(r"\s+", " ", str(v)).strip()
    last = key.split(".")[-1]
    if last in ACCOUNT_KEYS:
        s = re.sub(r"^[A-Z]{2}(?=\d)", "", s.replace(" ", ""))
    if last == "numer_bzp":
        s = s.replace(" ", "")
    return s or None


def pairs(g, p, path: str = ""):
    """(ścieżka, gt, pred) dla liści; listy parowane optymalnie."""
    if isinstance(g, dict) or isinstance(p, dict):
        gd, pd = g if isinstance(g, dict) else {}, p if isinstance(p, dict) else {}
        for k in list(gd) + [k for k in pd if k not in gd]:
            yield from pairs(gd.get(k), pd.get(k), f"{path}.{k}" if path else k)
        return
    if isinstance(g, list) or isinstance(p, list):
        gl, pl = g if isinstance(g, list) else [], p if isinstance(p, list) else []

        def score(a, b):
            return sum(1 for _, x, y in pairs(a, b) if x == y and x is not None)

        n, m = len(gl), len(pl)
        sc = [[score(gl[i], pl[j]) for j in range(m)] for i in range(n)]
        best, best_map = -1, {}
        if n and m and max(n, m) <= 7:
            for perm in itertools.permutations(range(m), min(n, m)) if n <= m else ():
                s = sum(sc[i][perm[i]] for i in range(n))
                if s > best:
                    best, best_map = s, {i: perm[i] for i in range(n)}
            if n > m:
                for perm in itertools.permutations(range(n), m):
                    s = sum(sc[perm[j]][j] for j in range(m))
                    if s > best:
                        best, best_map = s, {perm[j]: j for j in range(m)}
        else:  # zachłannie
            used = set()
            for i in range(n):
                cand = [(sc[i][j], j) for j in range(m) if j not in used]
                if cand:
                    s, j = max(cand)
                    best_map[i] = j
                    used.add(j)
        matched_p = set(best_map.values())
        for i in range(n):
            j = best_map.get(i)
            yield from pairs(gl[i], pl[j] if j is not None else None, f"{path}[{i}]" if j is not None else f"{path}[-{i}]")
        for j in range(m):
            if j not in matched_p:
                yield from pairs(None, pl[j], f"{path}[+{j}]")
        return
    yield path, norm_value(path, g), norm_value(path, p)


def score_doc(gt: dict, pred: dict) -> list[dict]:
    if gt == {}:
        if not pred or all(pv is None for _, _, pv in pairs({}, pred)):
            return [{"key": "(dokument negatywny)", "path": "", "gt": "{}", "pred": "{}", "tp": 1, "fp": 0, "fn": 0}]
        return [{"key": re.sub(r"\[[+-]?\d+\]", "", path), "path": path, "gt": None, "pred": pv, "tp": 0, "fp": 1, "fn": 0}
                for path, _, pv in pairs({}, pred) if pv is not None]
    out = []
    for path, gv, pv in pairs(gt, pred):
        if gv is None and pv is None and re.search(r"\[[+-]\d+\]", path):
            continue  # element listy bez pary: puste liście nie są trafieniem null/null
        tp = int(gv == pv)
        fp = int(not tp and pv is not None)
        fn = int(not tp and gv is not None)
        out.append({"key": re.sub(r"\[[+-]?\d+\]", "", path), "path": path, "gt": gv, "pred": pv, "tp": tp, "fp": fp, "fn": fn})
    return out


def prf(rows) -> tuple[float, float, float, int, int, int]:
    tp, fp, fn = sum(r["tp"] for r in rows), sum(r["fp"] for r in rows), sum(r["fn"] for r in rows)
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f, tp, fp, fn


# ---------------------------------------------------------------------------------------------- przebieg
def _one(pdf: str, label: str, force_ocr: bool, do_classify: bool) -> dict:
    from odw2json.classify import classify
    from odw2json.config import doc_types as dts
    from odw2json.extract import extract
    from odw2json.text import DocumentText

    t0 = time.perf_counter()
    doc = DocumentText(pdf, force_ocr=force_ocr)
    typ = label
    cls = None
    if do_classify:
        c = classify(doc)
        typ, cls = c.type or NONE, c.path
    if typ == NONE or typ not in dts():
        return {"pred": {}, "type": typ, "cls": cls, "fields": {}, "calls": {}, "seconds": round(time.perf_counter() - t0, 2)}
    res, tr = extract(doc, dts()[typ])
    calls = {n: c.get("error", "ok") for n, c in tr["calls"].items()}
    return {"pred": res, "type": typ, "cls": cls, "fields": tr["fields"], "calls": calls, "extras": tr.get("extras"),
            "seconds": round(time.perf_counter() - t0, 2)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", choices=["auto", "ocr"], default="auto")
    ap.add_argument("--set", default="all", help="S | K | all")
    ap.add_argument("--subset", default="", help="regex na doc_id")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--llm", choices=["auto", "off"], default="auto")
    ap.add_argument("--classify", action="store_true", help="pełny potok z klasyfikacją (i negatywami)")
    ap.add_argument("--tag", default="")
    a = ap.parse_args(argv)
    if a.llm == "off":
        os.environ["ODW_LLM"] = "off"
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    from odw2json import llm

    llm_name = llm.model_name() if llm.available() else "wyłączony"
    types = list(doc_types())
    docs = [d for d in load_manifest() if (a.set == "all" or d.set == a.set)
            and (d.label in types and d.gt or (a.classify and d.label == NONE))]
    if a.subset:
        docs = [d for d in docs if re.search(a.subset, d.doc_id)]
    print(f"[eval] {len(docs)} dokumentów, LLM: {llm_name}, tekst: {a.text}, klasyfikacja: {a.classify}", flush=True)

    rows, docrows = [], []
    t0 = time.perf_counter()
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(_one, d.pdf, d.label, a.text == "ocr", a.classify): d for d in docs}
        for i, f in enumerate(as_completed(futs), 1):
            d = futs[f]
            try:
                r = f.result()
            except Exception as e:  # noqa: BLE001
                print(f"[eval] BŁĄD {d.doc_id}: {type(e).__name__}: {e}", flush=True)
                r = {"pred": {}, "type": "błąd", "cls": None, "fields": {}, "calls": {}, "seconds": 0}
            gt = d.load_gt() if d.label != NONE else {}
            gt = gt or {}
            sc = score_doc(gt, r["pred"])
            for x in sc:
                fi = r["fields"].get(re.sub(r"\[[+-]", "[", x["path"]), {})
                rows.append({"doc_id": d.doc_id, "set": d.set, "label": d.label, **x,
                             "decision": fi.get("decision", ""), "llm": json.dumps(fi.get("llm"), ensure_ascii=False)})
            p, rr, f1, *_ = prf(sc)
            docrows.append({"doc_id": d.doc_id, "set": d.set, "label": d.label, "pred_type": r["type"], "cls_path": r["cls"],
                            "f1": round(f1, 4), "calls": json.dumps(r["calls"], ensure_ascii=False), "seconds": r["seconds"]})
            if i % 20 == 0:
                print(f"[eval] {i}/{len(docs)} {time.perf_counter() - t0:.0f}s", flush=True)

    tag = a.tag or ("_".join(x for x in [a.text, a.set if a.set != "all" else "", "regex" if llm_name == "wyłączony" else "",
                                          "e2e" if a.classify else ""] if x))
    OUT.mkdir(parents=True, exist_ok=True)
    write_csv(OUT / f"docs_{tag}.csv", sorted(docrows, key=lambda r: r["doc_id"]))
    errs = [r for r in rows if not r["tp"]]
    write_csv(OUT / f"errors_{tag}.csv", sorted(errs, key=lambda r: (r["key"], r["doc_id"])))

    md = [f"# Ekstrakcja — F1 (tekst `{a.text}`, LLM `{llm_name}`, zestaw `{a.set}`, klasyfikacja {'tak' if a.classify else 'z etykiety'})\n",
          f"Dokumentów: {len(docs)}, czas: {time.perf_counter() - t0:.0f} s. Błędy wywołań LLM: "
          f"{sum('ok' not in v for d in docrows for v in json.loads(d['calls']).values())}.\n"]
    p, r_, f, tp, fp, fn = prf(rows)
    nn = [x for x in rows if not (x["gt"] is None and x["pred"] is None)]
    p2, r2, f2, *_ = prf(nn)
    md += ["| miara | precision | recall | F1 | TP | FP | FN |", "|---|---|---|---|---|---|---|",
           f"| **micro (null/null = TP)** | {p:.4f} | {r_:.4f} | **{f:.4f}** | {tp} | {fp} | {fn} |",
           f"| tylko wartości niepuste | {p2:.4f} | {r2:.4f} | {f2:.4f} | | | |", ""]
    md.append("## Per typ i zestaw\n\n| typ | zestaw | dok. | P | R | F1 |\n|---|---|---|---|---|---|")
    g = defaultdict(list)
    for x in rows:
        g[(x["label"], x["set"])].append(x)
    for (t, s), rs in sorted(g.items()):
        p_, r__, f_, *_ = prf(rs)
        n = len({x["doc_id"] for x in rs})
        md.append(f"| {t} | {s} | {n} | {p_:.3f} | {r__:.3f} | {f_:.3f} |")
    md.append("\n## Per pole\n\n| pole | n | TP | FP | FN | F1 | błędy: decyzje |\n|---|---|---|---|---|---|---|")
    fieldrows = []
    g = defaultdict(list)
    for x in rows:
        g[x["key"]].append(x)
    for k, rs in sorted(g.items()):
        p_, r__, f_, tp_, fp_, fn_ = prf(rs)
        dec = defaultdict(int)
        for x in rs:
            if not x["tp"]:
                dec[x["decision"] or "?"] += 1
        decs = ", ".join(f"{k2} {v}" for k2, v in sorted(dec.items(), key=lambda kv: -kv[1]))
        fieldrows.append({"key": k, "n": len(rs), "tp": tp_, "fp": fp_, "fn": fn_, "f1": round(f_, 4), "decisions": decs})
        md.append(f"| {k} | {len(rs)} | {tp_} | {fp_} | {fn_} | {f_:.3f} | {decs} |")
    write_csv(OUT / f"per_field_{tag}.csv", fieldrows)
    worst = sorted(docrows, key=lambda r: r["f1"])[:10]
    md.append("\n## Najsłabsze dokumenty\n\n| dokument | typ | F1 | wywołania |\n|---|---|---|---|")
    for r in worst:
        md.append(f"| {r['doc_id']} | {r['label']}→{r['pred_type']} | {r['f1']} | {r['calls']} |")
    (OUT / f"summary_{tag}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md[:8]))
    print(f"... zapisano {OUT / f'summary_{tag}.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
