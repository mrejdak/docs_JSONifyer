"""Pola GT: klasa pola, zapisy tekstowe wartości (formy) i przeżywalność w tekście (A7/B1).

Poziomy przeżywalności:
  L0 — dokładnie (regex formy, elastyczne białe znaki)
  L1 — łagodnie (casefold, bez ogonków, bez spacji; identyfikatory: same znaki alfanumeryczne)
  L2 — rozmyto (odległość edycyjna podciągu ≤ k: 1 dla ≤12 znaków, inaczej ceil(10% długości))
  L3 — nie znaleziono
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from .common import field_key, lenient, norm_text, squash

MONTHS_GEN = [
    "stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca",
    "lipca", "sierpnia", "września", "października", "listopada", "grudnia",
]

DIGIT_CLASSES = {"identyfikator", "rachunek"}


def field_class(path: str) -> str | None:
    name = field_key(path).split(".")[-1]
    if name in ("krs", "nip", "regon", "pesel"):
        return "identyfikator"
    if name in ("na_rachunek", "z_rachunku"):
        return "rachunek"
    if name in ("data", "czynnosc_dzien", "data_operacji"):
        return "data"
    if name == "kwota":
        return "kwota"
    if name == "imie_nazwisko":
        return "osoba"
    if name == "nazwa":
        return "nazwa_podmiotu"
    if name == "miejscowosc":
        return "miejscowosc"
    if name == "mail":
        return "email"
    if name in ("numer_bzp", "numer_ted", "numer_postepowania", "numer_transakcji"):
        return "numer"
    if name == "tytul":
        return "tytul"
    return None  # pola inferowane (czynnosc_powod_id, typ, ...) — nie szukamy w tekście


@dataclass
class Forms:
    cls: str
    regexes: list[re.Pattern]
    samples: list[str]  # przykładowe zapisy do L1/L2

    @property
    def digits(self) -> bool:
        return self.cls in DIGIT_CLASSES


def _flex(s: str) -> str:
    """Wartość -> regex z elastycznymi białymi znakami."""
    parts = [re.escape(p) for p in norm_text(s).split()]
    return r"\s+".join(parts)


def _digits_rx(d: str, prefix: str = "") -> str:
    return rf"(?<![0-9]){prefix}" + r"[\s\-]?".join(d) + r"(?![0-9])"


def forms(path: str, value) -> Forms | None:
    cls = field_class(path)
    if cls is None or value is None or value == "":
        return None
    v = str(value)
    name = field_key(path).split(".")[-1]
    if cls in DIGIT_CLASSES:
        d = re.sub(r"\D", "", v)
        prefix = r"(?:PL\s?)?" if cls == "rachunek" else ""
        samples = [d]
        if cls == "rachunek":
            samples.append(d[:2] + " " + " ".join(d[i : i + 4] for i in range(2, len(d), 4)))
        return Forms(cls, [re.compile(_digits_rx(d, prefix))], samples)
    if cls == "data":
        m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", v)
        if not m:
            return Forms(cls, [re.compile(_flex(v))], [v])
        y, mo, dd = m.group(1), int(m.group(2)), int(m.group(3))
        rx = [
            rf"(?<!\d)0?{dd}\s?[.\-/]\s?0?{mo}\s?[.\-/]\s?{y}(?!\d)",
            rf"(?<!\d){y}[.\-/]{mo:02d}[.\-/]{dd:02d}(?!\d)",
            rf"(?<!\d)0?{dd}\s+{MONTHS_GEN[mo - 1]}\s+{y}",
        ]
        samples = [f"{dd:02d}.{mo:02d}.{y}", f"{dd:02d}-{mo:02d}-{y}", f"{y}-{mo:02d}-{dd:02d}", f"{dd} {MONTHS_GEN[mo - 1]} {y}"]
        return Forms(cls, [re.compile(r, re.I) for r in rx], samples)
    if cls == "kwota":
        f = float(value)
        ip, cents = int(f), round((f - int(f)) * 100)
        grouped = f"{ip:,}".replace(",", " ")
        int_rx = r"[\s.]?".join(re.escape(g) for g in grouped.split(" "))
        rx = [rf"(?<![\d.,]){int_rx}[,.]{cents:02d}(?!\d)"]
        if cents == 0:
            rx.append(rf"(?<![\d.,]){int_rx}\s*(?:zł|PLN)")
        samples = [f"{grouped},{cents:02d}", f"{ip},{cents:02d}"]
        return Forms(cls, [re.compile(r) for r in rx], samples)
    if name == "numer_bzp":
        m = re.fullmatch(r"(\d{4})/BZP\s?(\d+)(/\d+)?", v)
        if m:
            rx = rf"{m.group(1)}/BZP\s?{m.group(2)}" + (re.escape(m.group(3)) if m.group(3) else r"(?!/\d)")
            return Forms(cls, [re.compile(rx)], [v, f"{m.group(1)}/BZP {m.group(2)}{m.group(3) or ''}"])
    if name == "numer_ted":
        m = re.fullmatch(r"(\d{6})-(\d{4})", v)
        if m:
            rx = [rf"(?<!\d){m.group(1)}-{m.group(2)}(?!\d)", rf"{m.group(2)}/S\s?\d{{3}}-{m.group(1)}(?!\d)"]
            return Forms(cls, [re.compile(r) for r in rx], [v])
    return Forms(cls, [re.compile(_flex(v))], [norm_text(v)])


# ----------------------------------------------------------------------------- wyszukiwanie


def find_spans(fm: Forms, text: str) -> list[tuple[int, int]]:
    spans = []
    for rx in fm.regexes:
        spans += [(m.start(), m.end()) for m in rx.finditer(text)]
    return sorted(set(spans))


def _semi_global(p: str, t: str) -> tuple[int, int]:
    """Minimalna odległość edycyjna p od dowolnego podciągu t. Zwraca (dystans, koniec)."""
    m = len(p)
    prev = list(range(m + 1))
    best, best_end = m, 0
    for j in range(1, len(t) + 1):
        cur = [0] * (m + 1)
        tj = t[j - 1]
        for i in range(1, m + 1):
            cur[i] = min(prev[i] + 1, cur[i - 1] + 1, prev[i - 1] + (p[i - 1] != tj))
        if cur[m] < best:
            best, best_end = cur[m], j
        prev = cur
    return best, best_end


def fuzzy_find(needle: str, hay: str) -> tuple[int, str]:
    """Najbliższe okno w `hay` dla `needle` (oba już po squash). Zwraca (dystans, okno)."""
    from rapidfuzz import fuzz

    if not needle or not hay:
        return len(needle), ""
    al = fuzz.partial_ratio_alignment(needle, hay)
    k = len(needle) // 4 + 2
    lo, hi = max(0, al.dest_start - k), min(len(hay), al.dest_end + k)
    window = hay[lo:hi]
    dist, end = _semi_global(needle, window)
    return dist, window[max(0, end - len(needle) - 2) : end]


def threshold(n: int) -> int:
    return 1 if n <= 12 else math.ceil(0.10 * n)


def survival_level(fm: Forms, text: str, ref_form: str | None = None) -> dict:
    """Poziom przeżywalności w `text`. Dla zestawu S `ref_form` = dosłowny zapis z referencji."""
    if ref_form is not None:
        rxs = [re.compile(_flex(ref_form))]
        samples = [ref_form]
    else:
        rxs, samples = fm.regexes, fm.samples
    for rx in rxs:
        if rx.search(text):
            return {"level": "L0", "distance": 0, "window": ""}
    sq_text = squash(text, fm.digits)
    sq_samples = [squash(s, fm.digits) for s in samples]
    for s in sq_samples:
        if s and s in sq_text:
            return {"level": "L1", "distance": 0, "window": ""}
    best = (10**9, "", "")
    for s in sq_samples:
        dist, win = fuzzy_find(s, sq_text)
        if dist < best[0]:
            best = (dist, win, s)
    dist, win, s = best
    level = "L2" if dist <= threshold(len(s)) else "L3"
    return {"level": level, "distance": dist, "window": win}


def lenient_eq(a: str, b: str) -> bool:
    return lenient(a) == lenient(b)
