"""CLI: python -m odw2json <komenda>

  run       — przetwórz katalog input/ → output/ (domyślnie: ./input, ./output); kod wyjścia 0 po
              przetworzeniu wszystkich plików (błędy pojedynczych plików: log + trace/, wynik {} lub szkielet)
  classify  — klasyfikacja pojedynczych PDF-ów z uzasadnieniem (diagnostyka)
  check     — walidacja configu (typy, schematy, wzorce, słowniki)
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", category=FutureWarning)


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="python -m odw2json", description="Odwołania2JSON")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("run", help="przetwórz input/ → output/")
    p.add_argument("--input", default="input")
    p.add_argument("--output", default="output")
    p.add_argument("--workers", type=int, default=None)
    p.add_argument("--force-ocr", action="store_true", help="OCR także stron z warstwą tekstową")
    p.add_argument("--no-trace", action="store_true")
    p = sub.add_parser("classify", help="klasyfikacja PDF-ów z uzasadnieniem")
    p.add_argument("pdf", nargs="+")
    p.add_argument("--force-ocr", action="store_true")
    sub.add_parser("check", help="walidacja configu")
    a = ap.parse_args(argv)

    if a.cmd == "check":
        from .checkconfig import check
        from .config import doc_types

        from . import llm

        errors, warns = check()
        print(f"typy: {', '.join(doc_types())}")
        if llm.available():
            print(f"LLM (kolejność użycia): {', '.join(llm.providers())}")
        for w in warns:
            print(f"  UWAGA: {w}")
        for e in errors:
            print(f"  BŁĄD:  {e}")
        print("config OK" if not errors else f"config: {len(errors)} błędów")
        return 1 if errors else 0

    if a.cmd == "classify":
        from .classify import classify
        from .text import DocumentText

        for pdf in a.pdf:
            doc = DocumentText(pdf, force_ocr=a.force_ocr)
            c = classify(doc)
            print(f"{pdf}: {c.type or 'brak typu'}  [{c.path}] {c.reason}")
            for n, s in c.scores.items():
                print(f"    {n:16s} {s['score']:4d} (dowody {s['evidence']})  +{','.join(s['hits'])}  -{','.join(s['neg_hits'])}")
            if c.llm:
                print("    LLM:", json.dumps(c.llm, ensure_ascii=False)[:400])
        return 0

    if a.cmd == "run":
        from .config import load_env
        from .pipeline import run

        load_env()
        inp, out = Path(a.input), Path(a.output)
        if not inp.is_dir():
            print(f"brak katalogu wejściowego {inp}")
            return 2
        out.mkdir(parents=True, exist_ok=True)
        run(inp, out, a.workers, a.force_ocr, trace=not a.no_trace)
        # 0 = wsad zakończony; błędy pojedynczych plików są w logu i w trace/ (ich wynik i tak jest zapisany)
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
