"""Strona jako linie tokenów z bbox (0..1) i linearyzacja do tekstu.

Strona: {"lines": [{"bbox": [x0,y0,x1,y1], "tokens": [{"t": str, "bbox": [...], "conf": float|None}]}]}
"""

from __future__ import annotations

import re
import unicodedata

_CHAR_MAP = str.maketrans(
    {
        # tylko warianty bez znaczenia; cudzysłowy („”) i półpauzy (–) ZOSTAJĄ — pola dosłowne mają je
        # w GT (np. „w latach 2026–2029”); porównania są na nie odporne (verify.fold)
        "‐": "-", "‑": "-", "−": "-",
        " ": " ", " ": " ", " ": " ", "­": "",
    }
)


def norm_text(s: str) -> str:
    """NFC, ujednolicone spacje, bez miękkich dywizów. Litery, cudzysłowy i myślniki bez zmian."""
    s = unicodedata.normalize("NFC", s).translate(_CHAR_MAP)
    return s.replace(",,", '"')


def clean_tokens(tokens: list[dict]) -> list[dict]:
    out = []
    for t in tokens:
        txt = norm_text(t["t"]).strip()
        for part in txt.split():
            out.append({**t, "t": part})
    return out


def make_line(tokens: list[dict]) -> dict:
    return {
        "bbox": [min(t["bbox"][0] for t in tokens), min(t["bbox"][1] for t in tokens),
                 max(t["bbox"][2] for t in tokens), max(t["bbox"][3] for t in tokens)],
        "tokens": tokens,
    }


def _vov(a: list[float], b: list[float]) -> float:
    ov = min(a[3], b[3]) - max(a[1], b[1])
    return ov / max(min(a[3] - a[1], b[3] - b[1]), 1e-6)


def rows(page: dict, overlap: float = 0.5) -> list[list[dict]]:
    """Wiersze wizualne odporne na lekkie przekrzywienie.

    Linie sortowane po lewym tokenie; linia dołącza do wiersza tylko, gdy leży obok niego (na prawo
    lub na lewo, bez pokrycia w poziomie) i sąsiednie tokeny są na tej samej wysokości
    (etykieta | wartość). Linie jedna pod drugą nigdy nie są łączone.
    """
    eps = 0.002
    lines = [ln for ln in page["lines"] if ln["tokens"]]
    lines.sort(key=lambda ln: ((ln["tokens"][0]["bbox"][1] + ln["tokens"][0]["bbox"][3]) / 2, ln["bbox"][0]))
    out: list[list[dict]] = []
    for ln in lines:
        first, last_t = ln["tokens"][0]["bbox"], ln["tokens"][-1]["bbox"]
        placed = False
        for r in reversed(out[-3:]):
            toks = [t for l in r for t in l["tokens"]]
            r_x0, r_x1 = min(l["bbox"][0] for l in r), max(l["bbox"][2] for l in r)
            if ln["bbox"][0] >= r_x1 - eps:
                ok = _vov(first, max(toks, key=lambda t: t["bbox"][2])["bbox"]) >= overlap
            elif ln["bbox"][2] <= r_x0 + eps:
                ok = _vov(last_t, min(toks, key=lambda t: t["bbox"][0])["bbox"]) >= overlap
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


def rows_text(page: dict) -> str:
    return "\n".join(" ".join(t["t"] for t in r) for r in rows(page))


def native_text(page: dict) -> str:
    return "\n".join(" ".join(t["t"] for t in ln["tokens"]) for ln in page["lines"] if ln["tokens"])


# ----------------------------------------------------------------------------- linearyzacja świadoma kolumn

CELL_GAP = 0.025  # min. odstęp poziomy (ułamek szerokości strony) rozdzielający komórki w wierszu
COL_TOL = 0.015  # tolerancja dopasowania komórki do kolumny


def _cells(row: list[dict]) -> list[dict]:
    """Tokeny wiersza → komórki (fragmenty rozdzielone szeroką przerwą)."""
    cells: list[dict] = []
    for t in sorted(row, key=lambda t: t["bbox"][0]):
        if cells and t["bbox"][0] - cells[-1]["x1"] < CELL_GAP:
            c = cells[-1]
            c["tokens"].append(t)
            c["x1"] = max(c["x1"], t["bbox"][2])
        else:
            cells.append({"tokens": [t], "x0": t["bbox"][0], "x1": t["bbox"][2]})
    for c in cells:
        c["text"] = " ".join(t["t"] for t in c["tokens"])
    return cells


def _col_of(cell: dict, cols: list[list[float]]) -> int | None:
    best, best_ov = None, 0.0
    for i, (a, b) in enumerate(cols):
        ov = min(cell["x1"], b) - max(cell["x0"], a)
        if ov > best_ov:
            best, best_ov = i, ov
    return best


def _fits(cell: dict, cols: list[list[float]]) -> int | None:
    """Indeks kolumny, w której komórka mieści się w całości (kontynuacja komórki), albo None."""
    for i, (a, b) in enumerate(cols):
        nxt = cols[i + 1][0] if i + 1 < len(cols) else 1.0
        if cell["x0"] >= a - COL_TOL and cell["x1"] <= nxt - CELL_GAP / 2:
            return i
    return None


def _compatible(cells: list[dict], cols: list[list[float]]) -> bool:
    idx = [_col_of(c, cols) for c in cells]
    return None not in idx and len(set(idx)) == len(idx) and idx == sorted(idx)


def _vext(cells: list[dict]) -> tuple[float, float, float]:
    """Zakres pionowy wiersza i mediana wysokości tokenu."""
    toks = [t for c in cells for t in c["tokens"]]
    hs = sorted(t["bbox"][3] - t["bbox"][1] for t in toks)
    return min(t["bbox"][1] for t in toks), max(t["bbox"][3] for t in toks), hs[len(hs) // 2]


MAX_ROW_GAP = 1.2  # odstęp między wierszami bloku (w wysokościach linii); większy = nowy blok (np. nagłówek sekcji)

LABEL_MAX_TOKENS = 4  # etykieta w lewej kolumnie: krótka komórka („Odwołujący:”, „Adres do doręczeń”, „Tytuł”)
LABEL_MAX_CHARS = 40
LABEL_MAX_X0 = 0.35  # etykieta zaczyna się w lewej części strony


def _is_label_row(cells: list[dict]) -> bool:
    if len(cells) != 1:
        return False
    c = cells[0]
    return (len(c["tokens"]) <= LABEL_MAX_TOKENS and len(c["text"]) <= LABEL_MAX_CHARS
            and c["x0"] <= LABEL_MAX_X0 and re.search(r"[^\W\d_]{3,}", c["text"]) is not None)


BODY_ALIGN = 0.03  # wiersze bloku danych zaczynają się na wspólnej krawędzi (± tyle szerokości strony)


def _hoist_hanging_labels(rws: list[list[dict]]) -> list[list[dict]]:
    """Etykieta „wisząca” w lewej kolumnie — wyśrodkowana względem wieloliniowego bloku danych po
    prawej, np. „Odwołujący:” obok nazwy, adresu i KRS — w kolejności wierszy trafia w środek bloku
    i traci powiązanie z danymi. Przenosimy ją na początek jej bloku.

    Etykieta wisząca: krótki samodzielny wiersz w lewej części strony, a tuż nad nim i tuż pod nim
    (bez większej przerwy pionowej) wiersze danych leżące w całości na prawo od niej i zaczynające się
    na wspólnej krawędzi. Blok w górę kończy się na przerwie albo na wierszu spoza tej kolumny (akapit,
    wiersz „etykieta | wartość”, nagłówek). Gdy blok od góry zamyka inna samodzielna etykieta bez
    przerwy, układ to „etykieta nad danymi” (każda etykieta otwiera swój blok) — nic nie zmieniamy."""
    def gap_ok(upper: list[dict], lower: list[dict]) -> bool:
        _, y1, h = _vext(upper)
        return _vext(lower)[0] - y1 <= MAX_ROW_GAP * h

    out = list(rws)
    i = 0
    while i < len(out):
        if not _is_label_row(out[i]) or i + 1 >= len(out):
            i += 1
            continue
        edge = out[i][0]["x1"] + CELL_GAP / 2
        nxt = out[i + 1]
        if nxt[0]["x0"] < edge or not gap_ok(out[i], nxt):
            i += 1
            continue  # pod etykietą nie ma danych po prawej — etykieta nie stoi wewnątrz bloku
        body_x = nxt[0]["x0"]
        top, below, stop = i, out[i], None
        for k in range(i - 1, -1, -1):
            rk = out[k]
            if not gap_ok(rk, below):
                stop = "gap"
                break
            if rk[0]["x0"] < edge:
                stop = "label" if _is_label_row(rk) else "other"
                break
            if abs(rk[0]["x0"] - body_x) > BODY_ALIGN:
                stop = "other"
                break
            top, below = k, rk
        if top < i and stop != "label":
            out.insert(top, out.pop(i))
        i += 1
    return out


def structured_rows(page: dict) -> list[dict]:
    """Wiersze z komórkami i blokami kolumn. Element: {"kind": "row"|"block", ...}."""
    rws = _hoist_hanging_labels([_cells(r) for r in rows(page)])
    out, i = [], 0
    while i < len(rws):
        if len(rws[i]) < 2:
            out.append({"kind": "row", "cells": rws[i]})
            i += 1
            continue
        cols = [[c["x0"], c["x1"]] for c in rws[i]]
        members = [(rws[i], list(range(len(cols))))]
        j = i + 1
        while j < len(rws):
            r = rws[j]
            _, prev_y1, prev_h = _vext(members[-1][0])
            y0, _, _ = _vext(r)
            if y0 - prev_y1 > MAX_ROW_GAP * prev_h:
                break
            if len(r) >= 2 and len(r) <= len(cols) and _compatible(r, cols):
                idx = [_col_of(c, cols) for c in r]
                for c, k in zip(r, idx):
                    cols[k] = [min(cols[k][0], c["x0"]), max(cols[k][1], c["x1"])]
                members.append((r, idx))
            elif len(r) == 1 and _fits(r[0], cols) is not None and _fits(r[0], cols) > 0 or (
                len(r) == 1 and _fits(r[0], cols) == 0 and r[0]["x1"] < cols[1][0] - CELL_GAP / 2
                and any(len(m[0]) >= 2 for m in members[-2:])
            ):
                members.append((r, [_fits(r[0], cols)]))
            else:
                break
            j += 1
        out.append({"kind": "block", "cols": cols, "rows": members})
        i = j
    return out


def _label_like(c: dict) -> bool:
    """Komórka wyglądająca jak etykieta: krótka, ze słowem, bez cyfr („Data operacji”, „Odbiorca”)."""
    return (len(c["tokens"]) <= LABEL_MAX_TOKENS and len(c["text"]) <= LABEL_MAX_CHARS
            and re.search(r"[^\W\d_]{3,}", c["text"]) is not None and not re.search(r"\d", c["text"]))


def _is_key_value(block: dict, page_w: float = 1.0) -> bool:
    """Blok etykieta | wartość (czytany wierszami): lewa kolumna to etykiety — zwykle z dwukropkiem, wąska
    kolumna obok szerokiej albo co najmniej dwie komórki i wszystkie wyglądają jak etykiety. Inaczej blok to
    równorzędne kolumny, np. nagłówki nad wartościami („Płatnik | Beneficjent”, pod nimi nazwy, adresy,
    rachunki) — czytany kolumnami. Przy jednej etykiecie w lewej kolumnie obie kolejności dają ten sam sens."""
    cols = block["cols"]
    if len(cols) != 2:
        return False
    left = [c for r, idx in block["rows"] for c, k in zip(r, idx) if k == 0]
    if not left:
        return False
    colon = sum(c["text"].rstrip().endswith(":") for c in left) / len(left)
    lw, rw = cols[0][1] - cols[0][0], cols[1][1] - cols[1][0]
    short = sum(len(c["tokens"]) <= 4 for c in left) / len(left)
    labels = len(left) >= 2 and all(_label_like(c) for c in left)
    return colon >= 0.5 or (lw <= 0.28 * page_w and rw >= 1.5 * lw and short >= 0.8) or labels or len(block["rows"]) == 1


def columns_text(page: dict) -> str:
    """Linearyzacja świadoma kolumn (domyślna): bloki etykieta | wartość wierszami z separatorem ' | ',
    bloki równorzędnych kolumn (np. MOCODAWCA | PEŁNOMOCNIK, nagłówki tabeli nad wartościami) — kolumnami."""
    lines: list[str] = []
    for el in structured_rows(page):
        if el["kind"] == "row":
            lines.append(" ".join(c["text"] for c in el["cells"]))
            continue
        if _is_key_value(el):
            for r, idx in el["rows"]:
                lines.append(" | ".join(c["text"] for c in r))
        else:
            ncol = len(el["cols"])
            for k in range(ncol):
                for r, idx in el["rows"]:
                    for c, kk in zip(r, idx):
                        if kk == k:
                            lines.append(c["text"])
    return "\n".join(lines)


def grid_text(page: dict, width: int = 120) -> str:
    """Układ „jak na stronie” (spacje odwzorowują położenie) — czytelny dla LLM przy tabelach/kolumnach."""
    out = []
    for r in rows(page):
        cells = _cells(r)
        line = ""
        for c in cells:
            pos = int(c["x0"] * width)
            line = line + " " * max(1 if line else 0, pos - len(line)) + c["text"]
        out.append(line.rstrip())
    return "\n".join(out)


def linearize(page: dict, mode: str = "columns") -> str:
    return {"rows": rows_text, "native": native_text, "grid": grid_text}.get(mode, columns_text)(page)
