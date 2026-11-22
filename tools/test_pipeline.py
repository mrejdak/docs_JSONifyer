"""Testy wsadu (python -m odw2json run) bez LLM: każdy plik wejściowy ma wynik, awaria jednego pliku
(wyjątek, padnięty proces roboczy, uszkodzony PDF) nie przerywa przetwarzania, struktura katalogów
jest zachowana. Uruchomienie:
    python -m tools.test_pipeline
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from odw2json import pipeline  # noqa: E402


def fake_job(pdf: Path, out: Path, trace: Path | None, force_ocr: bool) -> dict:
    """Atrapa process_file: 'crash' → nagła śmierć procesu, 'raise' → wyjątek poza obsługą błędów."""
    if "crash" in pdf.name:
        os._exit(3)
    if "raise" in pdf.name:
        raise RuntimeError("błąd poza process_file")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"ok": pdf.name}), encoding="utf-8")
    return {"file": str(pdf), "type": "atrapa", "error": None, "seconds": 0}


def main() -> int:
    os.environ["ODW_LLM"] = "off"  # część B bez LLM (uszkodzone pliki i tak nie dochodzą do klasyfikacji)
    root = Path(tempfile.mkdtemp(prefix="odw_pipeline_test_"))
    inp, out = root / "input", root / "output"
    files = {
        "a.pdf": b"%PDF-atrapa", "sprawa1/b.PDF": b"x", "sprawa1/podkat/c.pdf": b"x", "skan.png": b"x",
        "crash_me.pdf": b"x", "raise_me.pdf": b"x", "notatka.txt": b"x", ".DS_Store": b"x", ".ukryty/d.pdf": b"x",
    }
    for rel, data in files.items():
        (inp / rel).parent.mkdir(parents=True, exist_ok=True)
        (inp / rel).write_bytes(data)

    ok = fail = 0

    def check(name: str, cond: bool, info=""):
        nonlocal ok, fail
        ok += cond
        fail += not cond
        print(f"  {'OK  ' if cond else 'FAIL'} {name}" + (f" — {info}" if info and not cond else ""))

    print("== A. wsad z atrapą przetwarzania (awarie procesów) ==")
    res = pipeline.run(inp, out, workers=2, trace=False, job=fake_job)
    produced = sorted(str(p.relative_to(out)).replace("\\", "/") for p in out.rglob("*.json"))
    expected = sorted(["a.json", "sprawa1/b.json", "sprawa1/podkat/c.json", "skan.json", "crash_me.json",
                       "raise_me.json", "notatka.json"])
    check("każdy plik (poza ukrytymi) ma wynik, struktura katalogów zachowana", produced == expected, produced)
    check("padnięty proces roboczy → {} tylko dla tego pliku",
          json.loads((out / "crash_me.json").read_text(encoding="utf-8")) == {}
          and json.loads((out / "a.json").read_text(encoding="utf-8")) == {"ok": "a.pdf"})
    check("wyjątek poza obsługą błędów → {}", json.loads((out / "raise_me.json").read_text(encoding="utf-8")) == {})
    check("nieobsługiwany format → {}", json.loads((out / "notatka.json").read_text(encoding="utf-8")) == {})
    check("obraz (.png) przetwarzany jak dokument", json.loads((out / "skan.json").read_text(encoding="utf-8")) == {"ok": "skan.png"})
    check("błędy zgłoszone w wynikach", sum(1 for r in res if r["error"]) == 2, [r for r in res if r["error"]])

    print("== B. prawdziwe przetwarzanie uszkodzonych plików ==")
    shutil.rmtree(out)
    for rel in list(files):
        if rel not in ("a.pdf", "sprawa1/b.PDF"):
            (inp / rel).unlink()
    (inp / "pusty.pdf").write_bytes(b"")
    pipeline.run(inp, out, workers=2, trace=False)
    for name in ("a.json", "sprawa1/b.json", "pusty.json"):
        p = out / name
        check(f"uszkodzony PDF {name} → {{}}", p.exists() and json.loads(p.read_text(encoding="utf-8")) == {})

    shutil.rmtree(root, ignore_errors=True)
    print(f"\n{ok} OK, {fail} FAIL")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
