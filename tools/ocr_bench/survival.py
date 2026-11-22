"""A7/B1: przeżywalność wartości pól GT w tekście OCR.

Zestaw S (i D = S z degradacją): mianownik = pola, których zapis występuje w tekście referencyjnym
(na stronach objętych OCR); szukamy dokładnie tego zapisu. Zestaw K (skany): brak referencji —
szukamy wszystkich typowych zapisów wartości.

Wyniki: survival_<S|K>.csv (per pole), survival_summary_<S|K>.csv (agregaty), fields_not_in_ref.csv.
"""

from __future__ import annotations

import re
import time
from collections import defaultdict

from .common import OUT, field_key, flatten, load_manifest, select_docs, write_csv
from .fields import find_spans, forms, survival_level
from .layout import native_text, rows_text
from .pdfio import extract_reference
from .run_ocr import list_configs, parse_config_id, tsv_path
from .tess import parse_tsv

LEVELS = ["L0", "L1", "L2", "L3"]
LAYOUTS = {"rows": rows_text, "native": native_text}


def _ocr_texts(cid: str, doc) -> tuple[dict[str, str], list[int]]:
    """Tekst OCR dokumentu w obu linearyzacjach: wiersze wizualne i natywna kolejność Tesseracta."""
    texts: dict[str, list[str]] = {k: [] for k in LAYOUTS}
    pages = []
    for page in range(1, doc.pages + 1):
        tp = tsv_path(cid, doc.doc_id, page)
        if tp.exists():
            pg = parse_tsv(tp.read_text(encoding="utf-8"))
            for k, fn in LAYOUTS.items():
                texts[k].append(fn(pg))
            pages.append(page)
    return {k: "\n".join(v) for k, v in texts.items()}, pages


def run_survival(set_: str, config_filter: str = "") -> None:
    t0 = time.perf_counter()
    docs = [d for d in select_docs(load_manifest(), set_) if d.gt]
    rx = re.compile(config_filter) if config_filter else None
    configs = [c for c in list_configs() if not rx or rx.search(c)]
    rows, not_in_ref = [], {}
    for cid in configs:
        cfg = parse_config_id(cid)
        subset = "D" if (set_ == "S" and cfg["degrade"] != "none") else set_
        n_docs = 0
        for d in docs:
            ocr_texts, pages = _ocr_texts(cid, d)
            if not pages:
                continue
            n_docs += 1
            ref_text = None
            if set_ == "S":
                ref = extract_reference(d)
                ref_text = "\n".join(rows_text(ref["pages"][p - 1]) for p in pages)
            for path, val in flatten(d.load_gt()):
                fm = forms(path, val)
                if not fm:
                    continue
                base = {"set": subset, **cfg, "doc_id": d.doc_id, "label": d.label, "path": path,
                        "field_key": field_key(path), "field_class": fm.cls, "value": val}
                ref_form = None
                if ref_text is not None:
                    spans = find_spans(fm, ref_text)
                    if not spans:
                        not_in_ref[(d.doc_id, path)] = {"doc_id": d.doc_id, "label": d.label, "path": path,
                                                        "field_class": fm.cls, "value": val, "pages": len(pages)}
                        continue
                    s, e = spans[0]
                    ref_form = ref_text[s:e]
                for layout, text in ocr_texts.items():
                    res = survival_level(fm, text, ref_form)
                    rows.append({**base, "layout": layout, **res, "ref_form": ref_form or ""})
        print(f"[survival] {cid}: {n_docs} dokumentów", flush=True)

    fields = ["set", "config", "layout", "dpi", "degrade", "preproc", "psm", "model", "doc_id", "label", "path", "field_key",
              "field_class", "value", "level", "distance", "ref_form", "window"]
    write_csv(OUT / f"survival_{set_}.csv", rows, fields)
    if set_ == "S":
        write_csv(OUT / "fields_not_in_ref.csv", list(not_in_ref.values()),
                  ["doc_id", "label", "path", "field_class", "value", "pages"])

    agg: dict = defaultdict(lambda: defaultdict(int))
    for r in rows:
        for cls in (r["field_class"], "WSZYSTKIE"):
            k = (r["set"], r["config"], r["layout"], cls)
            agg[k][r["level"]] += 1
            agg[k]["n"] += 1
    summary = []
    for (s, c, lay, cls), cnt in sorted(agg.items()):
        n = cnt["n"]
        summary.append({"set": s, "config": c, "layout": lay, "field_class": cls, "n": n,
                        **{lv: round(cnt[lv] / n, 4) for lv in LEVELS},
                        "L0+L1": round((cnt["L0"] + cnt["L1"]) / n, 4),
                        "L0+L1+L2": round((cnt["L0"] + cnt["L1"] + cnt["L2"]) / n, 4)})
    write_csv(OUT / f"survival_summary_{set_}.csv", summary)
    print(f"[survival] {len(configs)} konfiguracji, {len(rows)} pól, poza referencją: {len(not_in_ref)}, {time.perf_counter() - t0:.0f}s")
