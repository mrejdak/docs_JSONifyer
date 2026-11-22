"""Q7: czysty pomiar czasu OCR na stronę (sekwencyjnie, bez cache, bez równoległego obciążenia).

Mierzy render + OCR dla kilku stron każdego typu, dwa tryby wątków Tesseracta:
  omp1 — OMP_THREAD_LIMIT=1 (tryb wsadowy: wiele stron równolegle w procesach)
  ompN — domyślna liczba wątków (tryb pojedynczego dokumentu)
Wynik: reports/ocr/timing.csv
"""

from __future__ import annotations

import os
import statistics as st
import time

from .common import OUT, load_manifest, select_docs, write_csv
from .pdfio import encode_png, render_gray
from . import tess


def run_timing(configs: list[str], n_per_label: int = 3) -> None:
    from .run_ocr import parse_config_id

    docs = select_docs(load_manifest(), "S", "strat10")
    sample = []
    for lab in ("odwolanie", "pelnomocnictwo", "przelew"):
        sample += [(d, 1) for d in docs if d.label == lab][:n_per_label]
    k = select_docs(load_manifest(), "K")
    for lab in ("odwolanie", "pelnomocnictwo", "przelew"):
        sample += [(d, 1) for d in k if d.label == lab][:n_per_label]
    rows = []
    for cid in configs:
        cfg = parse_config_id(cid)
        if cfg["degrade"] != "none" or cfg["preproc"] != "none":
            print(f"[timing] pomijam {cid} (tylko konfiguracje bez degradacji/preprocessingu)")
            continue
        for mode in ("omp1", "ompN"):
            if mode == "ompN":
                tess._env = lambda: {k: v for k, v in os.environ.items() if k != "OMP_THREAD_LIMIT"}
            else:
                tess._env = lambda: {**os.environ, "OMP_THREAD_LIMIT": "1"}
            for d, page in sample:
                t0 = time.perf_counter()
                img = render_gray(d.pdf_path, page - 1, cfg["dpi"])
                png = encode_png(img, cfg["dpi"])
                t1 = time.perf_counter()
                _, secs = tess.run_tesseract(png, cfg["model"], cfg["psm"], cfg["dpi"])
                rows.append({"config": cid, "mode": mode, "set": d.set, "doc_id": d.doc_id, "label": d.label,
                             "render_s": round(t1 - t0, 3), "ocr_s": round(secs, 3)})
            r = [x["ocr_s"] for x in rows if x["config"] == cid and x["mode"] == mode]
            print(f"[timing] {cid} {mode}: mediana {st.median(r):.2f} s/str., max {max(r):.2f}", flush=True)
    write_csv(OUT / "timing.csv", rows)
