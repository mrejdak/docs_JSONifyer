"""A3/B2/A10: przebiegi Tesseracta po siatce konfiguracji, z cache.

Konfiguracja = wariant obrazu (dpi, degradacja, preprocessing) + wariant OCR (psm, model).
Identyfikator: d300_none_none__psm3_std. Wyniki: cache/ocr/<config>/<doc_id>/pNN.tsv (+ pNN.json z czasem).
"""

from __future__ import annotations

import itertools
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from .common import CACHE, Doc


@dataclass(frozen=True)
class ImgVariant:
    dpi: int
    degrade: str = "none"
    preproc: str = "none"

    @property
    def id(self) -> str:
        return f"d{self.dpi}_{self.degrade}_{self.preproc}"


@dataclass(frozen=True)
class OcrVariant:
    psm: int
    model: str

    @property
    def id(self) -> str:
        return f"psm{self.psm}_{self.model}"


def config_id(img: ImgVariant, ocr: OcrVariant) -> str:
    return f"{img.id}__{ocr.id}"


def parse_config_id(cid: str) -> dict:
    """d300_none_none__psm3_std (Tesseract bezpośrednio) albo omp-<flagi>_none_none__psm3_best (OCRmyPDF)."""
    img, ocr = cid.split("__")
    first, rest = img.split("_", 1)
    degrade, preproc = rest.rsplit("_", 1)  # degradacja może zawierać '_' (np. real_bin), preprocessing nie
    psm, model = ocr.split("_", 1)
    if first.startswith("omp-"):
        return {"config": cid, "engine": "ocrmypdf", "dpi": 0, "degrade": degrade, "preproc": first[4:],
                "psm": int(psm[3:]), "model": model}
    return {"config": cid, "engine": "tesseract", "dpi": int(first[1:]), "degrade": degrade, "preproc": preproc,
            "psm": int(psm[3:]), "model": model}


def tsv_path(cid: str, doc_id: str, page: int) -> Path:
    return CACHE / "ocr" / cid / doc_id / f"p{page:02d}.tsv"


def list_configs() -> list[str]:
    d = CACHE / "ocr"
    return sorted(p.name for p in d.iterdir() if p.is_dir()) if d.exists() else []


def _work(pdf: str, doc_id: str, page: int, img: ImgVariant, ocrs: list[OcrVariant]) -> list[dict]:
    from .pdfio import encode_png, render_gray
    from .tess import detect_rotation, run_tesseract

    t0 = time.perf_counter()
    im = render_gray(Path(pdf), page - 1, img.dpi)
    meta = {}
    if img.degrade != "none" or img.preproc != "none":
        from . import imageproc

        im = imageproc.degrade(im, img.degrade, f"{doc_id}|{page}", img.dpi)
        im, meta = imageproc.preprocess(
            im, img.preproc, img.dpi, osd=lambda a: detect_rotation(encode_png(a, img.dpi), img.dpi)
        )
    png = encode_png(im, img.dpi)
    prep_secs = time.perf_counter() - t0
    results = []
    for o in ocrs:
        cid = config_id(img, o)
        out = tsv_path(cid, doc_id, page)
        tsv, secs = run_tesseract(png, o.model, o.psm, img.dpi)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(tsv, encoding="utf-8")
        info = {"ocr_seconds": round(secs, 3), "prep_seconds": round(prep_secs, 3), "w": im.shape[1], "h": im.shape[0], **meta}
        out.with_suffix(".json").write_text(json.dumps(info), encoding="utf-8")
        results.append({"config": cid, "doc_id": doc_id, "page": page, **info})
    return results


def run(
    docs: list[Doc],
    dpis: list[int],
    psms: list[int],
    models: list[str],
    degrades: list[str],
    preprocs: list[str],
    max_pages: int | None = None,
    workers: int | None = None,
) -> None:
    workers = workers or max(1, (os.cpu_count() or 4) - 2)
    ocrs_all = [OcrVariant(p, m) for p, m in itertools.product(psms, models)]
    tasks = []
    for d in docs:
        n = d.pages if not max_pages else min(d.pages, max_pages)
        for page in range(1, n + 1):
            for dpi, deg, pre in itertools.product(dpis, degrades, preprocs):
                img = ImgVariant(dpi, deg, pre)
                todo = [o for o in ocrs_all if not tsv_path(config_id(img, o), d.doc_id, page).exists()]
                if todo:
                    tasks.append((d.pdf, d.doc_id, page, img, todo))
    total_ocr = sum(len(t[4]) for t in tasks)
    print(f"[ocr] {len(docs)} dokumentów, {len(tasks)} obrazów do przetworzenia, {total_ocr} przebiegów OCR, {workers} procesów", flush=True)
    if not tasks:
        return
    t0 = time.perf_counter()
    done = finished = errors = 0
    step = max(1, len(tasks) // 20)
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_work, *t): t for t in tasks}
        for f in as_completed(futs):
            t = futs[f]
            finished += 1
            try:
                done += len(f.result())
            except Exception as e:  # noqa: BLE001 — raportujemy i jedziemy dalej
                errors += 1
                print(f"[ocr] BŁĄD {t[1]} p{t[2]} {t[3].id}: {e}", flush=True)
            if finished % step == 0 or finished == len(tasks):
                el = time.perf_counter() - t0
                eta = el / finished * (len(tasks) - finished)
                print(f"[ocr] {done}/{total_ocr} przebiegów  {el:.0f}s  ETA {eta:.0f}s", flush=True)
    print(f"[ocr] koniec: {done} przebiegów, {errors} błędów, {time.perf_counter() - t0:.0f}s", flush=True)
