"""CLI benchmarku OCR.  python -m tools.ocr_bench <komenda> --help"""

from __future__ import annotations

import argparse
import sys
import warnings

warnings.filterwarnings("ignore", category=FutureWarning)


def _ints(s: str) -> list[int]:
    return [int(x) for x in s.split(",") if x]


def _strs(s: str) -> list[str]:
    return [x for x in s.split(",") if x]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m tools.ocr_bench", description="Benchmark OCR (docs/01_ocr_tesseract.md)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("manifest", help="zbuduj manifest danych (reports/ocr/manifest.csv)")
    sub.add_parser("reference", help="A1: tekst referencyjny z warstwy tekstowej + kontrola jakości")

    p = sub.add_parser("ocr", help="A3/B2/A10: przebiegi Tesseracta po siatce konfiguracji")
    p.add_argument("--set", default="S", choices=["S", "K"])
    p.add_argument("--subset", default="all", help="all | strat10 | regex po doc_id")
    p.add_argument("--labels", default="", help="np. odwolanie,przelew")
    p.add_argument("--dpi", type=_ints, default=[300])
    p.add_argument("--psm", type=_ints, default=[3])
    p.add_argument("--model", type=_strs, default=["std"], help="std,best,poleng")
    p.add_argument("--degrade", type=_strs, default=["none"], help="none,rot1,blur05,noise10,bin,jpeg30,real,... (łączone '+')")
    p.add_argument("--preproc", type=_strs, default=["none"], help="none,otsu,adaptive,deskew,denoise,osd (łączone '+')")
    p.add_argument("--max-pages", type=int, default=None)
    p.add_argument("--workers", type=int, default=None)

    p = sub.add_parser("ocrmypdf", help="silnik porównawczy: OCRmyPDF → PDF → tekst warstwy (PyMuPDF)")
    p.add_argument("--set", default="S", choices=["S", "K"])
    p.add_argument("--subset", default="all")
    p.add_argument("--labels", default="")
    p.add_argument("--psm", type=_ints, default=[3])
    p.add_argument("--model", type=_strs, default=["best"])
    p.add_argument("--flags", type=_strs, default=["plain"], help="plain,deskew,rot,thr-sauvola,thr-otsu,os300 (łączone '+')")
    p.add_argument("--max-pages", type=int, default=None)
    p.add_argument("--workers", type=int, default=None)

    p = sub.add_parser("compare", help="A4–A8: CER/WER, lokalizacja i kategorie błędów (zestaw S i D)")
    p.add_argument("--configs", default="", help="regex filtrujący konfiguracje (domyślnie wszystkie)")

    p = sub.add_parser("survival", help="A7/B1: przeżywalność wartości pól GT w tekście OCR")
    p.add_argument("--set", default="S", choices=["S", "K"])
    p.add_argument("--configs", default="")

    p = sub.add_parser("timing", help="Q7: czysty pomiar czasu OCR na stronę (sekwencyjnie)")
    p.add_argument("--configs", type=_strs, required=True, help="lista identyfikatorów konfiguracji")
    p.add_argument("--n", type=int, default=3, help="stron na typ dokumentu i zestaw")

    sub.add_parser("report", help="zbiorczy reports/ocr/summary.md")

    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    from . import common

    if a.cmd == "manifest":
        docs = common.build_manifest()
        from collections import Counter

        c = Counter((d.set, d.label) for d in docs)
        for k in sorted(c):
            print(k, c[k])
        print(f"zapisano {common.MANIFEST}")
    elif a.cmd == "reference":
        from .pdfio import extract_reference

        docs = common.select_docs(common.load_manifest(), "S")
        bad = []
        rows = []
        for d in docs:
            ref = extract_reference(d)
            for q in ref["qc"]:
                rows.append({"doc_id": d.doc_id, "label": d.label, **q})
                if not q["ok"]:
                    bad.append((d.doc_id, q))
        common.write_csv(common.OUT / "reference_qc.csv", rows)
        print(f"referencja: {len(docs)} dokumentów, {len(rows)} stron, podejrzanych stron: {len(bad)}")
        for b in bad[:20]:
            print("  ", b)
    elif a.cmd == "ocr":
        from .run_ocr import run

        docs = common.select_docs(common.load_manifest(), a.set, a.subset, a.labels)
        run(docs, a.dpi, a.psm, a.model, a.degrade, a.preproc, a.max_pages, a.workers)
    elif a.cmd == "ocrmypdf":
        from .ocrmypdf_run import run as run_omp

        docs = common.select_docs(common.load_manifest(), a.set, a.subset, a.labels)
        run_omp(docs, a.psm, a.model, a.flags, a.max_pages, a.workers)
    elif a.cmd == "compare":
        from .compare import run_compare

        run_compare(a.configs)
    elif a.cmd == "survival":
        from .survival import run_survival

        run_survival(a.set, a.configs)
    elif a.cmd == "timing":
        from .timing import run_timing

        run_timing(a.configs, a.n)
    elif a.cmd == "report":
        from .report import build_report

        build_report()
    return 0


if __name__ == "__main__":
    sys.exit(main())
