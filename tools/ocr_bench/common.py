"""Wspólne elementy benchmarku: ścieżki, manifest danych, GT, normalizacja tekstu."""

from __future__ import annotations

import csv
import json
import os
import re
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # final_product/
DATA_ROOT = Path(os.environ.get("ODW_DATA", ROOT.parent / "hacknation-2026"))
OUT = ROOT / "reports" / "ocr"
CACHE = OUT / "cache"
MANIFEST = OUT / "manifest.csv"

# Podzbiór warstwowy do pełnej siatki konfiguracji (co 6. sprawa).
STRAT10 = [f"przyklad_{i:02d}" for i in (1, 7, 13, 19, 25, 31, 37, 43, 49, 55)]

TEXT_LAYER_MIN_CHARS = 50


# --------------------------------------------------------------------------- manifest

@dataclass
class Doc:
    doc_id: str
    set: str  # "S" = z warstwą tekstową (referencja), "K" = skan (bez referencji)
    label: str  # odwolanie | pelnomocnictwo | przelew | brak  (z nazwy — TYLKO do ewaluacji)
    case: str
    pdf: str
    gt: str  # ścieżka do JSON GT lub ""
    pages: int

    @property
    def pdf_path(self) -> Path:
        return Path(self.pdf)

    def load_gt(self) -> dict | None:
        if not self.gt:
            return None
        txt = Path(self.gt).read_text(encoding="utf-8").strip()
        return json.loads(txt) if txt else None


def label_from_path(p: Path) -> str:
    """Etykieta referencyjna z nazwy pliku/katalogu. Używana wyłącznie przez narzędzia ewaluacyjne."""
    s = p.as_posix().lower()
    name = p.stem.lower()
    if "/negatywne/" in s or name.startswith("negatywny"):
        return "brak"
    if "/skany/odwolania/" in s or "odwolanie" in name:
        return "odwolanie"
    if "/skany/pelnomocnictwa/" in s or "pelnomocnictw" in name:
        return "pelnomocnictwo"
    if "/skany/potwierdzenia/" in s or "przelew" in name or "potwierdzeni" in name:
        return "przelew"
    return "brak"


def _gt_for(pdf: Path, label: str) -> Path | None:
    s = pdf.as_posix()
    if "/skany/" in s:
        g = pdf.with_suffix(".json")
    elif "/szablon-aplikacja/input/" in s:
        g = Path(s.replace("/input/", "/output/")).with_suffix(".json")
    elif label in ("odwolanie", "pelnomocnictwo", "przelew"):
        g = pdf.parent / f"{label}.json"
    else:
        return None
    if g.exists() and g.stat().st_size > 0:
        return g
    return None


def _doc_id(pdf: Path) -> str:
    try:
        rel = pdf.relative_to(DATA_ROOT / "dane")
    except ValueError:
        rel = Path("szablon") / pdf.relative_to(DATA_ROOT / "szablon-aplikacja" / "input")
    parts = list(rel.parent.parts) + [rel.stem]
    out = []
    for part in parts:  # skany/odwolania/0001/0001 -> skany__odwolania__0001 (bez powtórzenia)
        if out and part == out[-1]:
            continue
        out.append(part)
    return re.sub(r"[^\w.\-]+", "_", "__".join(out))


def build_manifest() -> list[Doc]:
    import pymupdf

    pdfs = sorted((DATA_ROOT / "dane").rglob("*.pdf")) + sorted(
        (DATA_ROOT / "szablon-aplikacja" / "input").rglob("*.pdf")
    )
    docs = []
    for pdf in pdfs:
        label = label_from_path(pdf)
        with pymupdf.open(pdf) as d:
            pages = d.page_count
            first = d[0].get_text() if pages else ""
        has_text = len(first.strip()) >= TEXT_LAYER_MIN_CHARS
        gt = _gt_for(pdf, label)
        case = pdf.parent.name if pdf.parent.name.startswith("przyklad_") else ""
        docs.append(
            Doc(
                doc_id=_doc_id(pdf),
                set="S" if has_text else "K",
                label=label,
                case=case,
                pdf=str(pdf),
                gt=str(gt) if gt else "",
                pages=pages,
            )
        )
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(asdict(docs[0]).keys()))
        w.writeheader()
        for d in docs:
            w.writerow(asdict(d))
    return docs


def load_manifest() -> list[Doc]:
    if not MANIFEST.exists():
        return build_manifest()
    with MANIFEST.open(encoding="utf-8") as f:
        return [Doc(**{**r, "pages": int(r["pages"])}) for r in csv.DictReader(f)]


def select_docs(docs: list[Doc], set_: str, subset: str = "all", labels: str = "") -> list[Doc]:
    out = [d for d in docs if d.set == set_]
    if subset == "strat10":
        out = [d for d in out if d.case in STRAT10]
    elif subset not in ("all", ""):
        rx = re.compile(subset)
        out = [d for d in out if rx.search(d.doc_id)]
    if labels:
        wanted = set(labels.split(","))
        out = [d for d in out if d.label in wanted]
    return out


# --------------------------------------------------------------------------- GT

def flatten(obj, prefix: str = ""):
    """Spłaszcza JSON do par (ścieżka, wartość); listy jako [i]."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from flatten(v, f"{prefix}.{k}" if prefix else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from flatten(v, f"{prefix}[{i}]")
    else:
        yield prefix, obj


def field_key(path: str) -> str:
    return re.sub(r"\[\d+\]", "", path)


# --------------------------------------------------------------------------- tekst

_CHAR_MAP = str.maketrans(
    {
        "„": '"', "”": '"', "“": '"', "«": '"', "»": '"', "″": '"',
        "‚": "'", "’": "'", "‘": "'", "`": "'",
        "–": "-", "—": "-", "‐": "-", "‑": "-", "−": "-",
        " ": " ", " ": " ", " ": " ", "­": "",
        "…": "...",
    }
)


def norm_text(s: str) -> str:
    """Normalizacja porównawcza (A4): NFC, cudzysłowy, myślniki, spacje. Bez zmiany liter."""
    s = unicodedata.normalize("NFC", s).translate(_CHAR_MAP)
    return s.replace(",,", '"')


_DIACRITICS = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")


def strip_diacritics(s: str) -> str:
    s = s.translate(_DIACRITICS)
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


def lenient(s: str) -> str:
    """Wariant łagodny: casefold + bez ogonków (spacje zostają)."""
    return strip_diacritics(norm_text(s)).casefold()


def squash(s: str, digits_only: bool = False) -> str:
    """Do wyszukiwania L1/L2: łagodny i bez białych znaków; dla identyfikatorów tylko alfanumeryczne."""
    s = lenient(s)
    if digits_only:
        return re.sub(r"[^0-9a-z]", "", s)
    return re.sub(r"\s+", "", s)


def write_csv(path: Path, rows: list[dict], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows and not fieldnames:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = fieldnames or list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def read_csv(path: Path) -> list[dict]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))
