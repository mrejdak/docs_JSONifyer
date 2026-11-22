"""PyMuPDF: tekst referencyjny z warstwy tekstowej oraz render stron do obrazu."""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pymupdf

from .common import CACHE, Doc
from .layout import clean_tokens, make_line

PL_DIACRITICS = re.compile(r"[ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]")
PRIVATE_USE = re.compile(r"[-�]")


def reference_page(page: pymupdf.Page) -> dict:
    w, h = page.rect.width, page.rect.height
    lines: dict[tuple[int, int], list[dict]] = {}
    for x0, y0, x1, y1, txt, block, line, _wno in page.get_text("words", sort=False):
        lines.setdefault((block, line), []).append(
            {"t": txt, "bbox": [x0 / w, y0 / h, x1 / w, y1 / h], "conf": None}
        )
    out = []
    for key in sorted(lines):
        toks = clean_tokens(lines[key])
        if toks:
            out.append(make_line(toks))
    return {"w": w, "h": h, "lines": out}


def ref_path(doc: Doc) -> Path:
    return CACHE / "ref" / f"{doc.doc_id}.json"


def extract_reference(doc: Doc) -> dict:
    """A1: tekst referencyjny + kontrola jakości. Wynik cache'owany w cache/ref/<doc_id>.json."""
    p = ref_path(doc)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    pages, qc = [], []
    with pymupdf.open(doc.pdf_path) as d:
        for i, page in enumerate(d):
            pg = reference_page(page)
            raw = page.get_text()
            n = len(raw.strip())
            qc.append(
                {
                    "page": i + 1,
                    "chars": n,
                    "pl_diacritics": len(PL_DIACRITICS.findall(raw)),
                    "bad_chars": len(PRIVATE_USE.findall(raw)),
                    "ok": n >= 20 and not PRIVATE_USE.search(raw) and (n < 500 or PL_DIACRITICS.search(raw) is not None),
                }
            )
            pages.append(pg)
    data = {"doc_id": doc.doc_id, "pages": pages, "qc": qc}
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


def render_gray(pdf: Path, page_no: int, dpi: int) -> np.ndarray:
    with pymupdf.open(pdf) as d:
        pix = d[page_no].get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY, alpha=False)
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.stride)[:, : pix.width]
    return arr.copy()


def encode_png(img: np.ndarray, dpi: int) -> bytes:
    img = np.ascontiguousarray(img, dtype=np.uint8)
    h, w = img.shape
    pix = pymupdf.Pixmap(pymupdf.csGRAY, w, h, img.tobytes(), 0)
    pix.set_dpi(dpi, dpi)
    return pix.tobytes("png")
