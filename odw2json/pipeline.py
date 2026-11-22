"""Przetwarzanie wsadowe: input/<dowolne podkatalogi>/<plik> → output/<te same podkatalogi>/<nazwa>.json
(+ trace/ poza output/).

Typ nierozpoznany → {}. Typ rozpoznany → JSON wg schema.json typu (ekstrakcja: odw2json/extract.py).
Błąd przetwarzania dokumentu nie przerywa wsadu (settings.output.on_error); awaria procesu roboczego —
też nie (plik ponawiany osobno, w ostateczności {}).
"""

from __future__ import annotations

import json
import os
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Callable

from .classify import classify
from .config import app_path, doc_types, settings
from .schema import skeleton
from .text import DocumentText


def extract(doc: DocumentText, type_name: str) -> tuple[dict, dict]:
    """Ekstrakcja pól wg schema.json typu (odw2json/extract.py)."""
    from .extract import extract as run_extract

    return run_extract(doc, doc_types()[type_name])


def process_file(pdf: Path, out_json: Path, trace_json: Path | None = None, force_ocr: bool = False) -> dict:
    t0 = time.perf_counter()
    trace: dict = {"file": str(pdf)}
    result: dict = {}
    type_name = None
    try:
        doc = DocumentText(pdf, force_ocr=force_ocr)
        cls = classify(doc)
        type_name = cls.type
        trace["classification"] = cls.to_dict()
        if type_name:
            result, trace["extraction"] = extract(doc, type_name)
        trace["text"] = doc.summary()
    except Exception as e:  # noqa: BLE001 — jeden dokument nie może zatrzymać wsadu
        trace["error"] = f"{type(e).__name__}: {e}"
        trace["traceback"] = traceback.format_exc()
        if type_name and settings()["output"].get("on_error", "skeleton") == "skeleton":
            result = skeleton(doc_types()[type_name].schema)
        else:
            result = {}
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    trace["seconds"] = round(time.perf_counter() - t0, 2)
    if trace_json:
        trace_json.parent.mkdir(parents=True, exist_ok=True)
        trace_json.write_text(json.dumps(trace, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    return {"file": str(pdf), "type": type_name, "error": trace.get("error"), "seconds": trace["seconds"]}


def find_inputs(input_dir: Path) -> list[Path]:
    """Wszystkie pliki z input/ (rekurencyjnie), bez ukrytych (.DS_Store, .gitkeep, katalogi z kropką)."""
    return sorted(p for p in input_dir.rglob("*")
                  if p.is_file() and not any(part.startswith(".") for part in p.relative_to(input_dir).parts))


def find_pdfs(input_dir: Path) -> list[Path]:
    return [p for p in find_inputs(input_dir) if p.suffix.lower() == ".pdf"]


def _write_empty(out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("{}\n", encoding="utf-8")


def _isolated(job: Callable, args: tuple) -> dict:
    """Ponowienie dokumentu, który przewrócił proces roboczy (np. awaria biblioteki natywnej na
    uszkodzonym pliku), w osobnym procesie — kolejna awaria dotyczy już tylko tego pliku."""
    try:
        with ProcessPoolExecutor(max_workers=1) as ex:
            return ex.submit(job, *args).result()
    except Exception as e:  # noqa: BLE001
        _write_empty(args[1])
        return {"file": str(args[0]), "type": None, "error": f"awaria procesu: {type(e).__name__}: {e}", "seconds": 0}


def run(input_dir: Path, output_dir: Path, workers: int | None = None, force_ocr: bool = False, trace: bool = True,
        job: Callable = process_file) -> list[dict]:
    """Przetwarza wszystkie pliki z input_dir; dla każdego zapisuje output_dir/<ścieżka względna>.json.
    Obsługiwane rozszerzenia (PDF i obrazy skanów) — settings.run.extensions; pozostałe pliki → {}
    (settings.run.other_files: empty) albo pominięte (skip). Żaden pojedynczy plik nie przerywa wsadu."""
    rcfg = settings().get("run") or {}
    exts = {e.lower() for e in rcfg.get("extensions", [".pdf"])}
    trace_dir = app_path(settings()["output"].get("trace_dir", "trace")) if trace else None
    workers = workers or int(rcfg.get("workers") or max(1, (os.cpu_count() or 2) - 1))
    jobs, results = [], []
    for f in find_inputs(input_dir):
        rel = f.relative_to(input_dir)
        out = output_dir / rel.with_suffix(".json")
        if f.suffix.lower() in exts:
            tr = (trace_dir / rel.with_suffix(".trace.json")) if trace_dir else None
            jobs.append((f, out, tr, force_ocr))
        elif rcfg.get("other_files", "empty") == "empty":
            _write_empty(out)
            results.append({"file": str(f), "type": None, "error": None, "seconds": 0, "skipped": True})
            print(f"  {rel}: nieobsługiwany format → {{}}", flush=True)
    print(f"[odw2json] {len(jobs)} dokumentów w {input_dir} → {output_dir} ({workers} procesów)", flush=True)
    t0 = time.perf_counter()

    def report(r: dict) -> None:
        results.append(r)
        status = f"BŁĄD: {r['error']}" if r["error"] else (r["type"] or "brak typu → {}")
        print(f"  [{len(results)}/{len(jobs)}] {Path(r['file']).relative_to(input_dir)}: {status} ({r['seconds']} s)", flush=True)

    retry = []
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(job, *j): j for j in jobs}
        for fut in as_completed(futs):
            try:
                report(fut.result())
            except Exception:  # noqa: BLE001 — proces roboczy padł (BrokenProcessPool) albo błąd poza process_file
                retry.append(futs[fut])
    for j in retry:  # po awarii puli: każdy nieukończony plik osobno
        report(_isolated(job, j))
    errors = [r for r in results if r["error"]]
    types: dict[str, int] = {}
    for r in results:
        types[r["type"] or "{}"] = types.get(r["type"] or "{}", 0) + 1
    print(f"[odw2json] gotowe: {len(results)} plików, {time.perf_counter() - t0:.1f} s; "
          + ", ".join(f"{k}: {v}" for k, v in sorted(types.items())) + (f"; błędy: {len(errors)}" if errors else ""), flush=True)
    return results
