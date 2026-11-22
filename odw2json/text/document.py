"""Tekst dokumentu PDF: strony z warstwą tekstową czytane bezpośrednio, pozostałe przez OCR (leniwie)."""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

from ..config import settings
from .layout import clean_tokens, linearize, make_line
from .ocr import ocr_page
from .quality import image_coverage, suspicious, text_stats


@dataclass
class PageText:
    number: int  # od 1
    source: str  # text_layer | ocr
    page: dict  # linie z tokenami (layout)
    text: str  # linearyzacja (wiersze wizualne)
    mean_conf: float | None = None
    meta: dict = field(default_factory=dict)

    @property
    def low_conf_ratio(self) -> float | None:
        confs = [t["conf"] for ln in self.page["lines"] for t in ln["tokens"] if t.get("conf") is not None]
        if not confs:
            return None
        thr = settings()["ocr"].get("low_confidence", 85)
        return sum(c < thr for c in confs) / len(confs)


def _text_layer_page(page: pymupdf.Page) -> dict:
    w, h = page.rect.width, page.rect.height
    lines: dict[tuple[int, int], list[dict]] = {}
    for x0, y0, x1, y1, txt, block, line, _ in page.get_text("words", sort=False):
        lines.setdefault((block, line), []).append({"t": txt, "bbox": [x0 / w, y0 / h, x1 / w, y1 / h], "conf": None})
    out = []
    for key in sorted(lines):
        toks = clean_tokens(lines[key])
        if toks:
            out.append(make_line(toks))
    return {"lines": out}


class DocumentText:
    """Leniwy dostęp do tekstu stron. `force_ocr=True` — OCR także stron z warstwą tekstową (testy odporności)."""

    def __init__(self, pdf: str | Path, force_ocr: bool = False, cfg: dict | None = None):
        self.path = Path(pdf)
        self.cfg = cfg or settings()
        self.force_ocr = force_ocr
        with pymupdf.open(self.path) as d:
            self.page_count = d.page_count
        self._pages: dict[int, PageText] = {}

    def page(self, number: int) -> PageText:
        if number not in self._pages:
            self._pages[number] = self._extract(number)
        return self._pages[number]

    def pages(self, n: int | None = None) -> list[PageText]:
        n = self.page_count if n is None else min(n, self.page_count)
        return [self.page(i) for i in range(1, n + 1)]

    def text(self, n: int | None = None) -> str:
        return "\n".join(p.text for p in self.pages(n))

    @property
    def any_ocr(self) -> bool:
        return any(p.source == "ocr" for p in self._pages.values())

    def summary(self) -> dict:
        ps = list(self._pages.values())
        confs = [p.mean_conf for p in ps if p.mean_conf is not None]
        return {
            "pages_total": self.page_count,
            "pages_read": sorted(self._pages),
            "ocr_pages": [p.number for p in ps if p.source == "ocr"],
            "mean_conf": round(statistics.mean(confs), 1) if confs else None,
            # strony, na których warstwa tekstowa była niepewna i porównana z OCR (powód, miary, wybór)
            "text_checks": {p.number: p.meta["text_check"] for p in ps if "text_check" in p.meta},
        }

    def _ocr(self, number: int, mode: str) -> PageText:
        layout, meta = ocr_page(self.path, number - 1, self.cfg["ocr"])
        confs = [t["conf"] for ln in layout["lines"] for t in ln["tokens"] if t.get("conf") is not None and t["conf"] >= 0]
        return PageText(number, "ocr", layout, linearize(layout, mode), round(statistics.mean(confs), 1) if confs else None, meta)

    def _extract(self, number: int) -> PageText:
        """Warstwa tekstowa, gdy jest i jest wiarygodna; inaczej OCR. Strona w większości pokryta obrazem
        (skan z dodanym tekstem, warstwa OCR skanera) albo z podejrzanym tekstem (znaki nieprawidłowe,
        losowe litery) → OCR i wybór lepszego wyniku (text/quality.py; settings.text)."""
        mode = self.cfg["layout"].get("linearization", "rows")
        tcfg = self.cfg["text"]
        if self.force_ocr:
            return self._ocr(number, mode)
        with pymupdf.open(self.path) as d:
            pg = d[number - 1]
            n_chars = len(pg.get_text().strip())
            if n_chars < int(tcfg.get("min_text_chars", 50)):
                tl = None
            else:
                layout = _text_layer_page(pg)
                tl = PageText(number, "text_layer", layout, linearize(layout, mode), None, {"chars": n_chars})
                reason = None
                if tcfg.get("verify_text_layer", True):
                    st = text_stats(tl.text)
                    cov = image_coverage(pg)
                    reason = suspicious(st, tcfg) or (
                        f"obraz pokrywa {cov:.0%} strony" if cov >= float(tcfg.get("image_coverage_ocr", 0.3)) else None)
                if not reason:
                    return tl
        if tl is None:
            return self._ocr(number, mode)
        # warstwa tekstowa niepewna → OCR i porównanie (remis = warstwa tekstowa)
        check = {"reason": reason, "image_coverage": round(cov, 3), "text_layer": st}
        try:
            oc = self._ocr(number, mode)
        except Exception as e:  # noqa: BLE001 — błąd OCR: zostaje warstwa tekstowa
            tl.meta["text_check"] = {**check, "ocr_error": f"{type(e).__name__}: {e}", "chosen": "text_layer"}
            return tl
        ost = text_stats(oc.text)
        use_ocr = ost["score"] > float(tcfg.get("ocr_better_ratio", 1.2)) * st["score"]
        check.update(ocr=ost, chosen="ocr" if use_ocr else "text_layer")
        chosen = oc if use_ocr else tl
        chosen.meta["text_check"] = check
        return chosen
