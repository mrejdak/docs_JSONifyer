"""Ewaluacja klasyfikacji (docs/02_klasyfikacja.md §8).

Etykiety referencyjne z nazw plików/katalogów (TYLKO tutaj — aplikacja nazw nie używa).
Tryby tekstu:  auto = warstwa tekstowa, OCR tylko stron bez tekstu;  ocr = wymuszony OCR (odporność).

  .venv\\Scripts\\python -m tools.eval_classification --text auto
  .venv\\Scripts\\python -m tools.eval_classification --text ocr --workers 14
  .venv\\Scripts\\python -m tools.eval_classification --llm off      # sam regex (tryb awaryjny)
LLM: auto = wg .env (domyślnie), off = wyłączony. Raport porównuje decyzję końcową, sam regex i sam LLM.
Wyniki: reports/classification/results_<tag>.csv, summary_<tag>.md
"""

from __future__ import annotations

import argparse
import sys
import time
import warnings
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed

warnings.filterwarnings("ignore", category=FutureWarning)

from odw2json.config import APP_ROOT, doc_types  # noqa: E402
from tools.ocr_bench.common import load_manifest, write_csv  # noqa: E402

OUT = APP_ROOT / "reports" / "classification"
NONE = "brak"


def _one(pdf: str, force_ocr: bool) -> dict:
    from odw2json.classify import classify
    from odw2json.text import DocumentText

    t0 = time.perf_counter()
    doc = DocumentText(pdf, force_ocr=force_ocr)
    c = classify(doc)
    s = doc.summary()
    v = c.llm or {}
    return {"pred": c.type or NONE, "path": c.path, "reason": c.reason, "scores": c.scores,
            "regex_pred": c.regex_type or NONE,
            "llm_pred": "" if (not v or v.get("error")) else (NONE if v.get("typ") == "inny" else v.get("typ", "")),
            "llm_conf": v.get("pewnosc", ""), "llm_grounding": v.get("grounding", ""), "llm_error": v.get("error", ""),
            "llm_cached": v.get("cached", ""),
            "ocr_pages": len(s["ocr_pages"]), "mean_conf": s["mean_conf"], "seconds": round(time.perf_counter() - t0, 2)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", choices=["auto", "ocr"], default="auto")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--llm", choices=["auto", "off"], default="auto")
    ap.add_argument("--without", default="", help="wyłącz typ(y) z configu (test: nieznany typ → brak), np. przelew")
    a = ap.parse_args(argv)
    if a.without:
        import os

        os.environ["ODW_EXCLUDE_TYPES"] = a.without  # dziedziczone przez procesy robocze
        doc_types.cache_clear()
    if a.llm == "off":
        import os

        os.environ["ODW_LLM"] = "off"  # dziedziczone przez procesy robocze
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    from odw2json import llm

    llm_name = llm.model_name() if llm.available() else "wyłączony"
    print(f"[eval] LLM: {llm_name}", flush=True)

    docs = load_manifest()
    types = list(doc_types())
    excluded = set(a.without.split(",")) if a.without else set()
    for d in docs:  # dokumenty wyłączonego typu powinny trafić do „brak”
        if d.label in excluded:
            d.label = NONE
    rows = []
    t0 = time.perf_counter()
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(_one, d.pdf, a.text == "ocr"): d for d in docs}
        for i, f in enumerate(as_completed(futs), 1):
            d = futs[f]
            r = f.result()
            row = {"doc_id": d.doc_id, "set": d.set, "true": d.label, "pred": r["pred"], "ok": d.label == r["pred"],
                   "path": r["path"], "reason": r["reason"], "ocr_pages": r["ocr_pages"], "mean_conf": r["mean_conf"],
                   "seconds": r["seconds"], "regex_pred": r["regex_pred"], "llm_pred": r["llm_pred"],
                   "llm_conf": r["llm_conf"], "llm_grounding": r["llm_grounding"], "llm_error": r["llm_error"],
                   "llm_cached": r["llm_cached"]}
            for t in types:
                sc = r["scores"].get(t, {})
                row[f"score_{t}"] = sc.get("score", "")
                row[f"hits_{t}"] = "+".join(sc.get("hits", [])) + ("" if not sc.get("neg_hits") else " -" + "-".join(sc["neg_hits"]))
            rows.append(row)
            if i % 25 == 0:
                print(f"[eval] {i}/{len(docs)} {time.perf_counter() - t0:.0f}s", flush=True)
    rows.sort(key=lambda r: r["doc_id"])
    tag = a.text + ("_regex" if llm_name == "wyłączony" else "") + (f"_bez_{a.without.replace(',', '_')}" if a.without else "")
    write_csv(OUT / f"results_{tag}.csv", rows)

    labels = types + [NONE]
    cm = Counter((r["true"], r["pred"]) for r in rows)
    acc = sum(r["ok"] for r in rows) / len(rows)
    md = [f"# Klasyfikacja — tryb tekstu `{a.text}`, LLM: `{llm_name}`\n",
          f"Dokumentów: {len(rows)}, poprawnie: {sum(r['ok'] for r in rows)} (**{100 * acc:.2f}%**). "
          f"Czas: {time.perf_counter() - t0:.0f} s.\n",
          "## Macierz pomyłek (wiersz = prawda, kolumna = predykcja)\n",
          "| prawda \\ predykcja | " + " | ".join(labels) + " |", "|---|" + "---|" * len(labels)]
    for t in labels:
        md.append(f"| {t} | " + " | ".join(str(cm[(t, p)]) for p in labels) + " |")
    md.append("\n## Precision / recall\n\n| klasa | precision | recall | n |\n|---|---|---|---|")
    for t in labels:
        tp = cm[(t, t)]
        pp = sum(cm[(x, t)] for x in labels)
        n = sum(cm[(t, x)] for x in labels)
        md.append(f"| {t} | {tp / pp if pp else 0:.3f} | {tp / n if n else 0:.3f} | {n} |")
    md.append("\n## Decyzja końcowa vs sam regex vs sam LLM\n")
    md.append("| wariant | poprawnie | dokumentów | dokładność |\n|---|---|---|---|")
    md.append(f"| końcowa | {sum(r['ok'] for r in rows)} | {len(rows)} | {100 * acc:.2f}% |")
    rx_ok = sum(r["regex_pred"] == r["true"] for r in rows)
    md.append(f"| sam regex | {rx_ok} | {len(rows)} | {100 * rx_ok / len(rows):.2f}% |")
    lr = [r for r in rows if r["llm_pred"]]
    if lr:
        l_ok = sum(r["llm_pred"] == r["true"] for r in lr)
        md.append(f"| sam LLM | {l_ok} | {len(lr)} | {100 * l_ok / len(lr):.2f}% |")
        md.append(f"\nBłędy wywołań LLM: {sum(bool(r['llm_error']) for r in rows)}. "
                  f"Niezgodność regex vs LLM: {sum(r['regex_pred'] != r['llm_pred'] for r in lr)} dokumentów.")
    md.append("\n## Ścieżka decyzji\n")
    md.append("| ścieżka | dokumenty |\n|---|---|")
    for k, v in Counter(r["path"] for r in rows).most_common():
        md.append(f"| {k} | {v} |")
    md.append("\n## Zapas progów (dla każdej klasy prawdziwej: wynik własnego typu i najwyższy wynik innego typu)\n")
    md.append("| prawda | zestaw | n | min wynik własny | mediana własny | max wynik obcy | min (własny − obcy) |\n|---|---|---|---|---|---|---|")
    g = defaultdict(list)
    for r in rows:
        g[(r["true"], r["set"])].append(r)
    for (t, s), rs in sorted(g.items()):
        own = [r[f"score_{t}"] for r in rs] if t in types else [0] * len(rs)
        other = [max(r[f"score_{x}"] for x in types if x != t) for r in rs]
        diff = [o - x for o, x in zip(own, other)]
        own_s = sorted(own)
        md.append(f"| {t} | {s} | {len(rs)} | {min(own)} | {own_s[len(own_s) // 2]} | {max(other)} | {min(diff)} |")
    errs = [r for r in rows if not r["ok"]]
    md.append(f"\n## Błędy ({len(errs)})\n")
    if errs:
        md.append("| dokument | prawda | predykcja | ścieżka | uzasadnienie | LLM | " + " | ".join(types) + " |")
        md.append("|---|---|---|---|---|---|" + "---|" * len(types))
        for r in errs:
            md.append(f"| {r['doc_id']} | {r['true']} | {r['pred']} | {r['path']} | {r['reason']} | "
                      f"{r['llm_pred']} {r['llm_conf']} {str(r['llm_error'])[:60]} | "
                      + " | ".join(f"{r[f'score_{t}']} ({r[f'hits_{t}']})" for t in types) + " |")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"summary_{tag}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md[:20]))
    print(f"... zapisano {OUT / f'summary_{tag}.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
