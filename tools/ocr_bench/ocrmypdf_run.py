"""Silnik porównawczy: OCRmyPDF → PDF z warstwą tekstową → tekst (słowa + bbox) przez PyMuPDF.

Wynik każdej strony zapisywany jest jako TSV w formacie Tesseracta (conf = -1, bo warstwa tekstowa
nie niesie pewności), więc compare/survival/report działają bez zmian.

Identyfikator konfiguracji: omp-<flagi>_none_none__psm<N>_<model>, np. omp-deskew+rot_none_none__psm3_best.
Flagi: plain | deskew | rot | thr-sauvola | thr-otsu | os300 (łączone '+').
Zestaw S: --force-ocr (pomiar jakości OCR; w aplikacji cyfrowe PDF-y używają oryginalnej warstwy tekstowej).
Zestaw K: --skip-text (strony bez tekstu są OCR-owane, z tekstem — zostawiane).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pymupdf

from .common import CACHE, Doc
from .run_ocr import tsv_path
from .tess import MODELS

OCRMYPDF = os.environ.get("OCRMYPDF_CMD") or shutil.which("ocrmypdf") or "ocrmypdf"

FLAG_ARGS = {
    "plain": [],
    "deskew": ["--deskew"],
    "rot": ["--rotate-pages"],
    "thr-sauvola": ["--tesseract-thresholding", "sauvola"],
    "thr-otsu": ["--tesseract-thresholding", "otsu"],
    "os300": ["--oversample", "300"],
}


def omp_config_id(flags: str, psm: int, model: str) -> str:
    return f"omp-{flags}_none_none__psm{psm}_{model}"


def _pdf_to_tsv(pdf: Path, cid: str, doc_id: str, secs_per_page: float) -> int:
    """Warstwa tekstowa wynikowego PDF-a → pliki TSV (format Tesseracta) per strona."""
    scale = 300 / 72  # współrzędne w „pikselach 300 dpi” (normalizowane i tak do 0..1)
    with pymupdf.open(pdf) as d:
        for i, page in enumerate(d):
            w, h = page.rect.width * scale, page.rect.height * scale
            out = ["level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext",
                   f"1\t1\t0\t0\t0\t0\t0\t0\t{int(w)}\t{int(h)}\t-1\t"]
            for x0, y0, x1, y1, txt, b, ln, wn in page.get_text("words", sort=False):
                txt = txt.replace("\t", " ")
                out.append(f"5\t1\t{b + 1}\t1\t{ln + 1}\t{wn + 1}\t{int(x0 * scale)}\t{int(y0 * scale)}\t"
                           f"{max(1, int((x1 - x0) * scale))}\t{max(1, int((y1 - y0) * scale))}\t-1\t{txt}")
            tp = tsv_path(cid, doc_id, i + 1)
            tp.parent.mkdir(parents=True, exist_ok=True)
            tp.write_text("\n".join(out) + "\n", encoding="utf-8")
            tp.with_suffix(".json").write_text(json.dumps({"ocr_seconds": round(secs_per_page, 3), "engine": "ocrmypdf"}), encoding="utf-8")
        return d.page_count


def _work(doc: Doc, flags: str, psm: int, model: str, max_pages: int | None) -> dict:
    cid = omp_config_id(flags, psm, model)
    out_pdf = CACHE / "ompdf" / cid / f"{doc.doc_id}.pdf"
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    args = [OCRMYPDF, "-l", MODELS[model]["lang"], "--output-type", "pdf", "--rasterizer", "pypdfium",
            "--tesseract-oem", "1", "--tesseract-pagesegmode", str(psm), "-j", "1", "--optimize", "0", "-q",
            "--force-ocr" if doc.set == "S" else "--skip-text"]
    for f in flags.split("+"):
        args += FLAG_ARGS[f]
    if max_pages and doc.pages > max_pages:
        args += ["--pages", f"1-{max_pages}"]
    env = {**os.environ, "OMP_THREAD_LIMIT": "1"}
    if MODELS[model]["tessdata_dir"]:
        env["TESSDATA_PREFIX"] = str(Path(MODELS[model]["tessdata_dir"]))
    t0 = time.perf_counter()
    p = subprocess.run(args + [doc.pdf, str(out_pdf)], capture_output=True, env=env, timeout=1800)
    secs = time.perf_counter() - t0
    if p.returncode != 0:
        raise RuntimeError(f"ocrmypdf rc={p.returncode}: {p.stderr.decode('utf-8', 'replace')[-600:]}")
    n = min(doc.pages, max_pages or doc.pages)
    _pdf_to_tsv(out_pdf, cid, doc.doc_id, secs / max(1, n))
    return {"config": cid, "doc_id": doc.doc_id, "seconds": secs, "pages": n}


def run(docs: list[Doc], psms: list[int], models: list[str], flag_sets: list[str],
        max_pages: int | None = None, workers: int | None = None) -> None:
    workers = workers or max(1, (os.cpu_count() or 4) - 2)
    tasks = []
    for d in docs:
        for flags in flag_sets:
            for psm in psms:
                for model in models:
                    cid = omp_config_id(flags, psm, model)
                    if not tsv_path(cid, d.doc_id, 1).exists():
                        tasks.append((d, flags, psm, model, max_pages))
    print(f"[ocrmypdf] {len(tasks)} przebiegów (dokument × konfiguracja), {workers} równolegle; {OCRMYPDF}", flush=True)
    t0 = time.perf_counter()
    done = errors = 0
    pages = 0
    step = max(1, len(tasks) // 20)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_work, *t): t for t in tasks}
        for f in as_completed(futs):
            done += 1
            try:
                pages += f.result()["pages"]
            except Exception as e:  # noqa: BLE001
                errors += 1
                t = futs[f]
                print(f"[ocrmypdf] BŁĄD {t[0].doc_id} {t[1]} psm{t[2]} {t[3]}: {e}", flush=True)
            if done % step == 0 or done == len(tasks):
                el = time.perf_counter() - t0
                print(f"[ocrmypdf] {done}/{len(tasks)}  {el:.0f}s  ETA {el / done * (len(tasks) - done):.0f}s", flush=True)
    print(f"[ocrmypdf] koniec: {done} przebiegów, {pages} stron, {errors} błędów, {time.perf_counter() - t0:.0f}s", flush=True)
