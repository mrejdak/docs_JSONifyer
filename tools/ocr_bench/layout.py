"""Reprezentacja strony (linie, tokeny z bbox) i składanie wierszy wizualnych.

Strona: {"w": float, "h": float, "lines": [{"bbox": [x0,y0,x1,y1], "tokens": [tok, ...]}]}
Token:  {"t": str, "bbox": [x0,y0,x1,y1], "conf": float|None}; bbox znormalizowane do 0..1.

Referencja (warstwa tekstowa) i OCR są składane tą samą funkcją `rows()` — linie o pokrywającym się
zakresie pionowym łączone są w jeden wiersz (etykieta i wartość w tabeli przelewu trafiają do jednej
linii), wiersze od góry, tokeny od lewej. Dzięki temu CER nie karze za różnice w kolejności bloków;
osobno liczymy CER na natywnej kolejności Tesseracta (kategoria „układ”).
"""

from __future__ import annotations

from .common import norm_text


def make_line(tokens: list[dict]) -> dict:
    xs0 = [t["bbox"][0] for t in tokens]
    ys0 = [t["bbox"][1] for t in tokens]
    xs1 = [t["bbox"][2] for t in tokens]
    ys1 = [t["bbox"][3] for t in tokens]
    return {"bbox": [min(xs0), min(ys0), max(xs1), max(ys1)], "tokens": tokens}


def clean_tokens(tokens: list[dict]) -> list[dict]:
    out = []
    for t in tokens:
        txt = norm_text(t["t"]).strip()
        if not txt:
            continue
        for part in txt.split():  # normalizacja mogła wprowadzić spacje
            out.append({**t, "t": part})
    return out


def _vov(a: list[float], b: list[float]) -> float:
    """Pionowe pokrycie dwóch bbox względem niższego z nich (0..1)."""
    ov = min(a[3], b[3]) - max(a[1], b[1])
    return ov / max(min(a[3] - a[1], b[3] - b[1]), 1e-6)


def rows(page: dict, overlap: float = 0.5) -> list[list[dict]]:
    """Wiersze wizualne, odporne na lekkie przekrzywienie skanu.

    Linie sortowane po pozycji LEWEGO tokenu (nie środku bbox — przy obrocie długa linia ma środek
    przesunięty). Linia dołączana do wiersza tylko wtedy, gdy leży w całości obok niego (na prawo
    albo na lewo, brak pokrycia w poziomie), a sąsiadujące tokeny są na tej samej wysokości
    (etykieta | wartość). Linie jedna pod drugą nigdy nie są łączone.
    """
    eps = 0.002
    lines = [ln for ln in page["lines"] if ln["tokens"]]
    lines.sort(key=lambda ln: ((ln["tokens"][0]["bbox"][1] + ln["tokens"][0]["bbox"][3]) / 2, ln["bbox"][0]))
    out: list[list[dict]] = []  # wiersze jako listy linii
    for ln in lines:
        first, lastl = ln["tokens"][0]["bbox"], ln["tokens"][-1]["bbox"]
        placed = False
        for r in reversed(out[-3:]):  # kilka ostatnich wierszy (kolumny tabeli mogą przyjść w innej kolejności)
            toks = [t for l in r for t in l["tokens"]]
            r_x0, r_x1 = min(l["bbox"][0] for l in r), max(l["bbox"][2] for l in r)
            if ln["bbox"][0] >= r_x1 - eps:  # linia na prawo od wiersza
                ok = _vov(first, max(toks, key=lambda t: t["bbox"][2])["bbox"]) >= overlap
            elif ln["bbox"][2] <= r_x0 + eps:  # linia na lewo od wiersza
                ok = _vov(lastl, min(toks, key=lambda t: t["bbox"][0])["bbox"]) >= overlap
            else:
                ok = False
            if ok:
                r.append(ln)
                placed = True
                break
        if not placed:
            out.append([ln])
    result = []
    for r in out:
        r.sort(key=lambda l: l["bbox"][0])
        result.append([t for l in r for t in l["tokens"]])
    return result


def row_tokens(page: dict) -> list[dict]:
    return [t for r in rows(page) for t in r]


def rows_text(page: dict) -> str:
    return "\n".join(" ".join(t["t"] for t in r) for r in rows(page))


def native_text(page: dict) -> str:
    return "\n".join(" ".join(t["t"] for t in ln["tokens"]) for ln in page["lines"] if ln["tokens"])
