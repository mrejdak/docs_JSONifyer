"""OCR strony: render PyMuPDF → preprocessing → Tesseract (stdin → TSV) → strona w formacie layout.

Ustawienia z config/settings.yaml (sekcja `ocr`). Wyniki cache'owane w .cache/ocr.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import numpy as np
import pymupdf

from ..config import app_path
from .layout import clean_tokens, make_line
from .preprocess import preprocess

_WIN_DEFAULT = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def tesseract_cmd(cfg: dict) -> str:
    return cfg.get("tesseract_cmd") or os.environ.get("TESSERACT_CMD") or shutil.which("tesseract") or _WIN_DEFAULT


def check_tesseract(cfg: dict) -> str:
    """Zwraca wersję Tesseracta albo rzuca czytelny błąd (brak binarki / modelu)."""
    cmd = tesseract_cmd(cfg)
    try:
        out = subprocess.run([cmd, "--version"], capture_output=True, text=True, timeout=30)
    except FileNotFoundError as e:
        raise RuntimeError(f"Nie znaleziono Tesseracta ({cmd}). Zainstaluj Tesseract 5 lub ustaw TESSERACT_CMD.") from e
    td = app_path(cfg.get("tessdata_dir"))
    if td and not (td / f"{cfg.get('lang', 'pol').split('+')[0]}.traineddata").exists():
        raise RuntimeError(f"Brak modelu OCR {cfg.get('lang')} w {td}")
    return (out.stdout or out.stderr).splitlines()[0].strip()


def render_gray(pdf: Path, index: int, dpi: int) -> np.ndarray:
    with pymupdf.open(pdf) as d:
        pix = d[index].get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY, alpha=False)
    return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.stride)[:, : pix.width].copy()


def encode_png(img: np.ndarray, dpi: int) -> bytes:
    img = np.ascontiguousarray(img, dtype=np.uint8)
    h, w = img.shape
    pix = pymupdf.Pixmap(pymupdf.csGRAY, w, h, img.tobytes(), 0)
    pix.set_dpi(dpi, dpi)
    return pix.tobytes("png")


def run_tesseract(png: bytes, cfg: dict) -> str:
    cmd = [tesseract_cmd(cfg), "stdin", "stdout", "-l", cfg.get("lang", "pol"),
           "--psm", str(cfg.get("psm", 3)), "--oem", str(cfg.get("oem", 1)), "--dpi", str(cfg.get("dpi", 200))]
    td = app_path(cfg.get("tessdata_dir"))
    if td:
        cmd += ["--tessdata-dir", str(td)]
    cmd += ["-c", "tessedit_create_tsv=1"]
    env = {**os.environ, "OMP_THREAD_LIMIT": "1"}
    p = subprocess.run(cmd, input=png, capture_output=True, env=env, timeout=600)
    if p.returncode != 0:
        raise RuntimeError(f"tesseract rc={p.returncode}: {p.stderr.decode('utf-8', 'replace')[:300]}")
    return p.stdout.decode("utf-8", "replace")


def parse_tsv(tsv: str) -> dict:
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
        if level != 5 or not c[11].strip():
            continue
        key = (int(c[1]), int(c[2]), int(c[3]), int(c[4]))
        if key not in lines:
            lines[key] = []
            order.append(key)
        lines[key].append({"t": c[11], "bbox": [left / w, top / h, (left + width) / w, (top + height) / h], "conf": float(c[10])})
    out = []
    for key in order:
        toks = clean_tokens(lines[key])
        if toks:
            out.append(make_line(toks))
    return {"lines": out}


def _cache_key(pdf: Path, index: int, cfg: dict) -> str:
    h = hashlib.sha1()
    with open(pdf, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    sub = {k: cfg.get(k) for k in ("lang", "dpi", "oem", "psm", "preprocess", "deskew_max_angle", "tessdata_dir")}
    h.update(json.dumps(sub, sort_keys=True).encode())
    h.update(str(index).encode())
    return h.hexdigest()[:24]


def ocr_page(pdf: Path, index: int, cfg: dict) -> tuple[dict, dict]:
    """OCR jednej strony (index od 0). Zwraca (strona layout, meta)."""
    cache = app_path(cfg.get("cache_dir"))
    key = _cache_key(pdf, index, cfg) if cache else ""
    if cache and (cache / f"{key}.tsv").exists():
        meta = json.loads((cache / f"{key}.json").read_text(encoding="utf-8"))
        return parse_tsv((cache / f"{key}.tsv").read_text(encoding="utf-8")), {**meta, "cached": True}
    t0 = time.perf_counter()
    dpi = int(cfg.get("dpi", 200))
    img = render_gray(pdf, index, dpi)
    img, meta = preprocess(img, list(cfg.get("preprocess") or []), dpi, float(cfg.get("deskew_max_angle", 5.0)))
    tsv = run_tesseract(encode_png(img, dpi), cfg)
    meta["seconds"] = round(time.perf_counter() - t0, 3)
    if cache:
        cache.mkdir(parents=True, exist_ok=True)
        (cache / f"{key}.tsv").write_text(tsv, encoding="utf-8")
        (cache / f"{key}.json").write_text(json.dumps(meta), encoding="utf-8")
    return parse_tsv(tsv), meta
