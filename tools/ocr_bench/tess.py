"""Wywołanie binarki Tesseracta (bez pytesseract) i parsowanie wyjścia TSV."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from pathlib import Path

from .common import ROOT
from .layout import clean_tokens, make_line

TESSERACT = (
    os.environ.get("TESSERACT_CMD")
    or shutil.which("tesseract")
    or r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

# Modele: std = instalacja systemowa, best = tessdata_best w repo narzędzi.
MODELS = {
    "std": {"lang": "pol", "tessdata_dir": None},
    "best": {"lang": "pol", "tessdata_dir": ROOT / "tools" / "ocr_bench" / "tessdata_best"},
    "poleng": {"lang": "pol+eng", "tessdata_dir": None},
}


def tesseract_version() -> str:
    out = subprocess.run([TESSERACT, "--version"], capture_output=True, text=True)
    return (out.stdout or out.stderr).splitlines()[0].strip()


def _env() -> dict:
    return {**os.environ, "OMP_THREAD_LIMIT": "1"}


def run_tesseract(png: bytes, model: str, psm: int, dpi: int, extra: dict | None = None) -> tuple[str, float]:
    m = MODELS[model]
    cmd = [TESSERACT, "stdin", "stdout", "-l", m["lang"], "--psm", str(psm), "--oem", "1", "--dpi", str(dpi)]
    if m["tessdata_dir"]:
        cmd += ["--tessdata-dir", str(Path(m["tessdata_dir"]))]
    for k, v in {"tessedit_create_tsv": 1, **(extra or {})}.items():
        cmd += ["-c", f"{k}={v}"]
    t0 = time.perf_counter()
    p = subprocess.run(cmd, input=png, capture_output=True, env=_env(), timeout=600)
    secs = time.perf_counter() - t0
    if p.returncode != 0:
        raise RuntimeError(f"tesseract rc={p.returncode}: {p.stderr.decode('utf-8', 'replace')[:500]}")
    return p.stdout.decode("utf-8", "replace"), secs


def detect_rotation(png: bytes, dpi: int) -> int:
    """OSD (--psm 0): kąt (0/90/180/270), o który trzeba obrócić obraz zgodnie z ruchem wskazówek zegara."""
    cmd = [TESSERACT, "stdin", "stdout", "--psm", "0", "--dpi", str(dpi), "-l", "osd"]
    p = subprocess.run(cmd, input=png, capture_output=True, env=_env(), timeout=300)
    m = re.search(r"Rotate:\s*(\d+)", p.stdout.decode("utf-8", "replace"))
    return int(m.group(1)) if m else 0


def parse_tsv(tsv: str) -> dict:
    """TSV -> strona w formacie layout (linie w natywnej kolejności Tesseracta)."""
    lines: dict[tuple, list[dict]] = {}
    order: list[tuple] = []
    w = h = 1.0
    for row in tsv.splitlines()[1:]:
        c = row.split("\t")
        if len(c) < 12:
            continue
        level = int(c[0])
        left, top, width, height = (int(c[i]) for i in (6, 7, 8, 9))
        if level == 1:
            w, h = float(width), float(height)
            continue
        if level != 5:
            continue
        text = c[11]
        if not text.strip():
            continue
        key = (int(c[1]), int(c[2]), int(c[3]), int(c[4]))
        if key not in lines:
            lines[key] = []
            order.append(key)
        lines[key].append(
            {"t": text, "bbox": [left, top, left + width, top + height], "conf": float(c[10])}
        )
    out = []
    for key in order:
        toks = [{**t, "bbox": [t["bbox"][0] / w, t["bbox"][1] / h, t["bbox"][2] / w, t["bbox"][3] / h]} for t in lines[key]]
        toks = clean_tokens(toks)
        if toks:
            out.append(make_line(toks))
    return {"w": w, "h": h, "lines": out}
