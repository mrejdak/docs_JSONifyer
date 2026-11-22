"""Degradacja syntetyczna (zestaw D, A10) i preprocessing skanów (B2). Wymaga opencv.

Warianty składa się operatorem '+', np. degrade="rot1+blur05+jpeg50", preproc="deskew+otsu".
"""

from __future__ import annotations

import zlib

import cv2
import numpy as np

# ----------------------------------------------------------------------------- degradacja (D)


def _rotate(img: np.ndarray, angle: float, border: int = 255) -> np.ndarray:
    h, w = img.shape
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(img, m, (w, h), flags=cv2.INTER_LINEAR, borderValue=border)


def _jpeg(img: np.ndarray, q: int) -> np.ndarray:
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, q])
    return cv2.imdecode(buf, cv2.IMREAD_GRAYSCALE)


def _noise(img: np.ndarray, sigma: float, rng: np.random.Generator) -> np.ndarray:
    n = rng.normal(0, sigma, img.shape)
    return np.clip(img.astype(np.float32) + n, 0, 255).astype(np.uint8)


def _salt_pepper(img: np.ndarray, frac: float, rng: np.random.Generator) -> np.ndarray:
    out = img.copy()
    mask = rng.random(img.shape)
    out[mask < frac / 2] = 0
    out[mask > 1 - frac / 2] = 255
    return out


def _shade(img: np.ndarray) -> np.ndarray:
    h, w = img.shape
    gx = np.linspace(0.82, 1.0, w, dtype=np.float32)[None, :]
    gy = np.linspace(1.0, 0.9, h, dtype=np.float32)[:, None]
    return np.clip(img.astype(np.float32) * gx * gy, 0, 255).astype(np.uint8)


def _blur(img: np.ndarray, sigma: float) -> np.ndarray:
    return cv2.GaussianBlur(img, (0, 0), sigma)


DEGRADE_OPS = {
    "rot05": lambda im, rng, dpi: _rotate(im, 0.5),
    "rot1": lambda im, rng, dpi: _rotate(im, 1.0),
    "rot2": lambda im, rng, dpi: _rotate(im, -2.0),
    "blur05": lambda im, rng, dpi: _blur(im, 0.5 * dpi / 200),
    "blur10": lambda im, rng, dpi: _blur(im, 1.0 * dpi / 200),
    "noise5": lambda im, rng, dpi: _noise(im, 5, rng),
    "noise10": lambda im, rng, dpi: _noise(im, 10, rng),
    "sp": lambda im, rng, dpi: _salt_pepper(im, 0.005, rng),
    "bin": lambda im, rng, dpi: np.where(im < 160, 0, 255).astype(np.uint8),
    "jpeg50": lambda im, rng, dpi: _jpeg(im, 50),
    "jpeg30": lambda im, rng, dpi: _jpeg(im, 30),
    "shade": lambda im, rng, dpi: _shade(im),
}
DEGRADE_ALIASES = {"real": "rot1+blur05+jpeg50+noise5", "real_bin": "rot05+blur05+bin+sp"}


def degrade(img: np.ndarray, spec: str, seed_key: str, dpi: int) -> np.ndarray:
    if spec in ("", "none"):
        return img
    spec = DEGRADE_ALIASES.get(spec, spec)
    rng = np.random.default_rng(zlib.crc32(f"{seed_key}|{spec}".encode()))
    for op in spec.split("+"):
        img = DEGRADE_OPS[op](img, rng, dpi)
    return img


# ----------------------------------------------------------------------------- preprocessing (B2)


def estimate_skew(img: np.ndarray, max_angle: float = 3.0) -> float:
    """Kąt prostowania metodą profilu projekcji (maksymalna „ostrość” profilu wierszy)."""
    h, w = img.shape
    scale = 800 / w
    small = cv2.resize(img, (800, int(h * scale)), interpolation=cv2.INTER_AREA)
    _, bw = cv2.threshold(small, 0, 1, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    sh, sw = bw.shape

    def score(a: float) -> float:
        m = cv2.getRotationMatrix2D((sw / 2, sh / 2), a, 1.0)
        rot = cv2.warpAffine(bw, m, (sw, sh), flags=cv2.INTER_NEAREST, borderValue=0)
        prof = rot.sum(axis=1).astype(np.float64)
        return float(np.sum(np.diff(prof) ** 2))

    coarse = np.arange(-max_angle, max_angle + 1e-9, 0.25)
    best = max(coarse, key=score)
    fine = np.arange(best - 0.25, best + 0.25 + 1e-9, 0.05)
    return float(max(fine, key=score))


def _adaptive(img: np.ndarray, dpi: int) -> np.ndarray:
    block = int(dpi * 0.15) | 1
    return cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, block, 15)


def remove_leaders(img: np.ndarray, dpi: int) -> tuple[np.ndarray, int]:
    """Usuwa kropkowane linie do podpisu ('.........'), które powodują gubienie sąsiednich linii przez
    analizę układu Tesseracta (psm 3/4). Pojedyncze kropki, przecinki i ogonki zostają: usuwane są
    tylko drobne komponenty tworzące długi (≥ 0.5 cala), płaski ciąg poziomy."""
    _, bw = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(bw, connectivity=8)
    s = dpi / 200
    max_side = max(2, int(7 * s))
    small = np.zeros(n, dtype=bool)
    small[1:] = (stats[1:, cv2.CC_STAT_WIDTH] <= max_side) & (stats[1:, cv2.CC_STAT_HEIGHT] <= max_side)
    small_mask = (small[labels]).astype(np.uint8) * 255
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (max(3, int(12 * s)), 1))
    joined = cv2.morphologyEx(small_mask, cv2.MORPH_CLOSE, k)
    m, lab2, st2, _ = cv2.connectedComponentsWithStats(joined, connectivity=8)
    lead = np.zeros(m, dtype=bool)
    lead[1:] = (st2[1:, cv2.CC_STAT_WIDTH] >= int(0.5 * dpi)) & (st2[1:, cv2.CC_STAT_HEIGHT] <= max_side * 2)
    region = lead[lab2] & (small_mask > 0)
    out = img.copy()
    out[region] = 255
    return out, int(lead.sum())


def preprocess(img: np.ndarray, spec: str, dpi: int, osd=None) -> tuple[np.ndarray, dict]:
    """Zwraca obraz i metadane (np. wykryty kąt). `osd` = funkcja(png)->kąt dla operacji 'osd'."""
    meta: dict = {}
    if spec in ("", "none"):
        return img, meta
    for op in spec.split("+"):
        if op == "otsu":
            _, img = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        elif op == "adaptive":
            img = _adaptive(img, dpi)
        elif op == "deskew":
            a = estimate_skew(img)
            meta["deskew_angle"] = round(a, 2)
            if abs(a) >= 0.05:
                img = _rotate(img, a)
        elif op == "denoise":
            img = cv2.medianBlur(img, 3)
        elif op == "noleader":
            img, nlead = remove_leaders(img, dpi)
            meta["leaders_removed"] = nlead
        elif op == "osd":
            rot = osd(img) if osd else 0
            meta["osd_rotate"] = rot
            if rot == 90:
                img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
            elif rot == 180:
                img = cv2.rotate(img, cv2.ROTATE_180)
            elif rot == 270:
                img = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
        else:
            raise ValueError(f"nieznana operacja preprocessingu: {op}")
    return img, meta
