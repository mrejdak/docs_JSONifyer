"""Ocena tekstu strony: czy warstwa tekstowa PDF jest kompletna i czytelna, czy trzeba OCR.

Warstwa tekstowa bywa: (1) częściowa — skan z dodanym tekstem (stopka podpisu elektronicznego, numeracja
stron, pieczęć wpływu), (2) nieczytelna — font bez mapy znaków (znaki zastępcze, obszar prywatny Unicode)
albo z błędnym kodowaniem (losowe litery), (3) słaba — warstwa OCR dodana przez skaner.
Miary są ogólne (bez słownika dziedzinowego): udział znaków nieprawidłowych, udział częstych słów
funkcyjnych (pl/en — odróżnia język od losowych liter), liczba słów wyglądających na słowa.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

from ..config import dictionary

_VOWELS = set("aeiouy")


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(ch for ch in s if not unicodedata.combining(ch)).replace("ł", "l")


@lru_cache(maxsize=1)
def _stopwords() -> frozenset[str]:
    try:
        words = dictionary("stopwords").get("words", [])
    except Exception:  # noqa: BLE001 — brak słownika nie może zatrzymać odczytu dokumentu
        words = []
    return frozenset(_fold(w) for w in words)


def _invalid_char(ch: str) -> bool:
    """Znak, którego nie ma w czytelnym tekście pisma: zastępczy, prywatny, sterujący, nieprzypisany
    albo litera spoza alfabetu łacińskiego (typowy objaw złego kodowania fontu)."""
    if ch in "\n\t\r ":
        return False
    if ch == "�":
        return True
    cat = unicodedata.category(ch)
    if cat in ("Co", "Cn", "Cs") or (cat == "Cc"):
        return True
    if cat.startswith("L"):
        return not unicodedata.name(ch, "").startswith("LATIN")
    return False


def text_stats(text: str) -> dict:
    """Miary tekstu strony. score = słowa wyglądające na słowa × czynnik języka (0–1, z udziału słów
    funkcyjnych); losowe litery i znaki zastępcze dają score bliski 0, krótka stopka — mały."""
    chars = [ch for ch in text if not ch.isspace()]
    n_chars = len(chars)
    invalid = sum(_invalid_char(ch) for ch in chars)
    toks = [_fold(t) for t in re.findall(r"[^\W\d_]+(?:\.[^\W\d_]+)?|\d+", text)]
    words = [t for t in toks if not t.isdigit()]
    stop = sum(t in _stopwords() for t in words)
    wordlike = sum(1 for t in words if len(t) >= 2 and any(c in _VOWELS for c in t) and t.isascii())
    numbers = sum(1 for t in toks if t.isdigit())
    stop_ratio = stop / len(words) if words else 0.0
    lang = min(1.0, stop_ratio / 0.1)  # tekst pisma: 0,15–0,35; tabele wydruków bankowych: ok. 0,1
    return {
        "chars": n_chars,
        "words": len(words),
        "invalid_ratio": round(invalid / n_chars, 4) if n_chars else 0.0,
        "stop_ratio": round(stop_ratio, 4),
        "score": round((wordlike + stop + 0.5 * numbers) * lang, 1),
    }


def suspicious(stats: dict, cfg: dict) -> str | None:
    """Powód, dla którego warstwa tekstowa wymaga porównania z OCR, albo None."""
    if stats["invalid_ratio"] > float(cfg.get("suspicious_invalid_ratio", 0.05)):
        return f"znaki nieprawidłowe {stats['invalid_ratio']:.0%}"
    if stats["words"] >= 20 and stats["stop_ratio"] < float(cfg.get("suspicious_stop_ratio", 0.03)):
        return f"mało słów funkcyjnych ({stats['stop_ratio']:.1%}) — możliwe błędne kodowanie fontu"
    return None


def image_coverage(page, grid: int = 40) -> float:
    """Część strony pokryta obrazami (siatka grid×grid — nakładające się obrazy liczone raz)."""
    r = page.rect
    if r.width <= 0 or r.height <= 0:
        return 0.0
    cells = set()
    for info in page.get_image_info():
        x0, y0, x1, y1 = info.get("bbox", (0, 0, 0, 0))
        x0, x1 = max(x0, r.x0), min(x1, r.x1)
        y0, y1 = max(y0, r.y0), min(y1, r.y1)
        if x1 <= x0 or y1 <= y0:
            continue
        cx0, cx1 = int((x0 - r.x0) / r.width * grid), int((x1 - r.x0) / r.width * grid - 1e-9)
        cy0, cy1 = int((y0 - r.y0) / r.height * grid), int((y1 - r.y0) / r.height * grid - 1e-9)
        cells.update((cx, cy) for cx in range(cx0, cx1 + 1) for cy in range(cy0, cy1 + 1))
    return len(cells) / (grid * grid)
