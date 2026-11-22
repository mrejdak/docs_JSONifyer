"""Preprocessing obrazu strony przed OCR (wybrany w kroku 1): deskew + noleader."""

from __future__ import annotations

import cv2
import numpy as np


def _rotate(img: np.ndarray, angle: float) -> np.ndarray:
    h, w = img.shape
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(img, m, (w, h), flags=cv2.INTER_LINEAR, borderValue=255)


def estimate_skew(img: np.ndarray, max_angle: float = 5.0) -> float:
    """Kąt prostowania metodą profilu projekcji (maksymalna „ostrość” profilu wierszy)."""
    h, w = img.shape
    small = cv2.resize(img, (800, max(1, int(h * 800 / w))), interpolation=cv2.INTER_AREA)
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


def deskew(img: np.ndarray, max_angle: float = 5.0) -> tuple[np.ndarray, float]:
    a = estimate_skew(img, max_angle)
    return (_rotate(img, a) if abs(a) >= 0.05 else img), round(a, 2)


def remove_leaders(img: np.ndarray, dpi: int) -> tuple[np.ndarray, int]:
    """Usuwa kropkowane linie do podpisu (przez nie psm 3 gubi sąsiednie linie z nazwiskami).
    Usuwane są tylko drobne komponenty tworzące długi (≥ 0,5 cala), płaski ciąg poziomy."""
    _, bw = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(bw, connectivity=8)
    s = dpi / 200
    max_side = max(2, int(7 * s))
    small = np.zeros(n, dtype=bool)
    small[1:] = (stats[1:, cv2.CC_STAT_WIDTH] <= max_side) & (stats[1:, cv2.CC_STAT_HEIGHT] <= max_side)
    small_mask = small[labels].astype(np.uint8) * 255
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (max(3, int(12 * s)), 1))
    joined = cv2.morphologyEx(small_mask, cv2.MORPH_CLOSE, k)
    m, lab2, st2, _ = cv2.connectedComponentsWithStats(joined, connectivity=8)
    lead = np.zeros(m, dtype=bool)
    lead[1:] = (st2[1:, cv2.CC_STAT_WIDTH] >= int(0.5 * dpi)) & (st2[1:, cv2.CC_STAT_HEIGHT] <= max_side * 2)
    region = lead[lab2] & (small_mask > 0)
    out = img.copy()
    out[region] = 255
    return out, int(lead.sum())


def preprocess(img: np.ndarray, ops: list[str], dpi: int, deskew_max_angle: float = 5.0) -> tuple[np.ndarray, dict]:
    meta: dict = {}
    for op in ops:
        if op == "deskew":
            img, meta["deskew_angle"] = deskew(img, deskew_max_angle)
        elif op == "noleader":
            img, meta["leaders_removed"] = remove_leaders(img, dpi)
        else:
            raise ValueError(f"nieznana operacja preprocessingu: {op}")
    return img, meta
