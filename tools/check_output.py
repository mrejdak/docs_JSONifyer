"""Sprawdzenie wyników wsadu tak, jak zobaczy je oceniający: każdy plik z input/ ma w output/ poprawny
JSON o tej samej ścieżce względnej; opcjonalnie F1 względem oczekiwanych JSON-ów (--expected).

    python -m tools.check_output                                  # input/ ↔ output/
    python -m tools.check_output --expected selftest/expected     # + micro-F1 (null/null = TP)

Na VM uruchamiać w kontenerze (tam są zależności):
    docker compose run --rm odw2json python -m tools.check_output --expected selftest/expected
Kod wyjścia 1, gdy brakuje wyniku albo wynik nie jest poprawnym JSON-em.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from odw2json.config import doc_types, settings  # noqa: E402
from odw2json.pipeline import find_inputs  # noqa: E402
from tools.eval_extraction import prf, score_doc  # noqa: E402


def detect_type(obj: dict) -> str:
    if obj == {}:
        return "{}"
    for name, dt in doc_types().items():
        if set(obj) == set(dt.schema.get("properties", {})):
            return name
    return "nieznany układ kluczy"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m tools.check_output")
    ap.add_argument("--input", default="input")
    ap.add_argument("--output", default="output")
    ap.add_argument("--expected", default=None, help="katalog z oczekiwanymi JSON-ami (ta sama struktura co output/)")
    a = ap.parse_args(argv)
    inp, out = Path(a.input), Path(a.output)
    rcfg = settings().get("run") or {}
    exts = {e.lower() for e in rcfg.get("extensions", [".pdf"])}
    files = [f for f in find_inputs(inp) if f.suffix.lower() in exts or rcfg.get("other_files", "empty") == "empty"]

    missing, invalid, types = [], [], {}
    for f in files:
        rel = f.relative_to(inp).with_suffix(".json")
        p = out / rel
        if not p.exists():
            missing.append(str(rel))
            continue
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            invalid.append(f"{rel}: {e}")
            continue
        t = detect_type(obj) if isinstance(obj, dict) else "nie-obiekt"
        types[t] = types.get(t, 0) + 1
    wanted = {f.relative_to(inp).with_suffix(".json") for f in files}
    extra = sorted(str(p.relative_to(out)) for p in out.rglob("*")
                   if p.is_file() and not p.name.startswith(".") and p.relative_to(out) not in wanted)
    print(f"plików wejściowych: {len(files)}, wyników: {len(files) - len(missing)}; typy: "
          + ", ".join(f"{k}: {v}" for k, v in sorted(types.items())))
    for m in missing:
        print(f"  BRAK WYNIKU: {m}")
    for m in invalid:
        print(f"  NIEPOPRAWNY JSON: {m}")
    if extra:
        print(f"  pliki w output/ bez odpowiednika w input/ (np. z poprzedniego przebiegu): {len(extra)}")

    if a.expected:
        exp_root = Path(a.expected)
        rows_all = []
        for e in sorted(exp_root.rglob("*.json")):
            rel = e.relative_to(exp_root)
            gt = json.loads(e.read_text(encoding="utf-8"))
            pp = out / rel
            pred = json.loads(pp.read_text(encoding="utf-8")) if pp.exists() else {}
            rows = score_doc(gt, pred)
            rows_all += rows
            f1 = prf(rows)[2]
            errs = [r for r in rows if not r["tp"]]
            print(f"  {rel}: F1 {f1:.3f}" + (f" — błędy: {len(errs)}" if errs else ""))
            for r in errs[:6]:
                print(f"      {r['path']}: oczekiwane {r['gt']!r}, jest {r['pred']!r}")
        p, r, f, tp, fp, fn = prf(rows_all)
        print(f"micro-F1 (null/null = TP): {f:.4f}  (P {p:.4f}, R {r:.4f}, TP {tp}, FP {fp}, FN {fn})")
    return 1 if missing or invalid else 0


if __name__ == "__main__":
    sys.exit(main())
