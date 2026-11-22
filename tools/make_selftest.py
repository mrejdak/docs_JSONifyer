"""Paczka do testu na VM (lokalnie, z danych organizatora): selftest/input/<sprawa>/<dokument>.pdf
+ selftest/expected/<sprawa>/<dokument>.json (oczekiwany wynik o NAZWIE PDF-a; dla negatywów {}).

    python -m tools.make_selftest              # domyślny zestaw (~15 dokumentów, ok. 10 MB)
    python -m tools.make_selftest --all        # wszystkie dokumenty z GT (długi test)

Katalog selftest/ jest w .gitignore (dane organizatora nie trafiają do repozytorium) — na VM kopiować
przez scp (docs/05_wdrozenie_vm.md).
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from odw2json.config import APP_ROOT  # noqa: E402
from tools.ocr_bench.common import load_manifest  # noqa: E402

# przykład z 3 dokumentami + negatyw, skany każdego typu, negatywy spoza przykładów, prawdziwy skan
DEFAULT = r"^(przyklad_0[1-4]__|skany__.*__000[16]$|negatywne__(KIO_KIO|2025_S_112)|szablon__)"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m tools.make_selftest")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--subset", default=DEFAULT, help="regex na doc_id")
    ap.add_argument("--out", default="selftest")
    a = ap.parse_args(argv)
    root = APP_ROOT / a.out
    shutil.rmtree(root, ignore_errors=True)
    n = 0
    for d in load_manifest():
        if not a.all and not re.search(a.subset, d.doc_id):
            continue
        pdf = Path(d.pdf)
        case = d.doc_id.split("__")[0] if not d.doc_id.startswith(("skany__", "szablon__")) else "__".join(d.doc_id.split("__")[:-1])
        dst = root / "input" / case / pdf.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(pdf, dst)
        if d.gt:
            exp = json.loads(Path(d.gt).read_text(encoding="utf-8"))
        elif d.label == "brak":
            exp = {}
        else:
            exp = None  # dokument bez GT (np. prawdziwy skan z szablonu) — tylko w input/
        if exp is not None:
            e = root / "expected" / case / pdf.with_suffix(".json").name
            e.parent.mkdir(parents=True, exist_ok=True)
            e.write_text(json.dumps(exp, ensure_ascii=False, indent=2), encoding="utf-8")
        n += 1
    size = sum(p.stat().st_size for p in root.rglob("*") if p.is_file()) / 1e6
    print(f"{n} dokumentów → {root} ({size:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
