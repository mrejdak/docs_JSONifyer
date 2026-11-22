"""Testy linearyzacji świadomej kolumn na sztucznych stronach (bez PDF i OCR).

Każdy przypadek to strona z liniami o zadanym położeniu (x0, y — ułamki strony) i oczekiwana kolejność
wybranych fragmentów w tekście dla LLM. Uruchomienie:
    python -m tools.test_layout
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from odw2json.text.layout import columns_text, make_line  # noqa: E402

CH, SP, H = 0.008, 0.004, 0.012  # szerokość znaku, odstęp między słowami, wysokość linii


def line(text: str, x0: float, y: float) -> dict:
    toks, x = [], x0
    for w in text.split():
        toks.append({"t": w, "bbox": [x, y, x + CH * len(w), y + H], "conf": None})
        x += CH * len(w) + SP
    return make_line(toks)


def page(*lines: tuple) -> dict:
    """lines: (tekst, x0, y) albo [(tekst, x0, y), …] — kilka linii PDF w tym samym wierszu wizualnym."""
    out = []
    for ln in lines:
        for t, x0, y in (ln if isinstance(ln, list) else [ln]):
            out.append(line(t, x0, y))
    return {"lines": out}


def order_ok(text: str, parts: list[str]) -> bool:
    pos = [text.find(p) for p in parts]
    return all(p >= 0 for p in pos) and pos == sorted(pos)


CASES = [
    (
        "etykiety wyśrodkowane w lewej kolumnie (prawdziwy skan) → przed swoim blokiem",
        page(
            ("Firma Alfa sp. z o.o.", 0.26, 0.260),
            ("ul. Polna 1, Warszawa", 0.26, 0.275),
            ("Odwołujący:", 0.11, 0.283),
            ("KRS: 0000123456", 0.26, 0.291),
            ("reprezentowana przez adw. Jan Nowak", 0.26, 0.306),
            [("Adres do doręczeń", 0.10, 0.321), ("ul. Długa 5, Kraków", 0.26, 0.321)],
            ("e-mail: biuro@kancelaria.pl", 0.26, 0.336),
            ("Gmina Beta", 0.26, 0.380),          # przerwa = nowy blok
            ("ul. Rynek 1, Beta", 0.26, 0.395),
            ("Zamawiający:", 0.11, 0.402),
            ("NIP: 1234567890", 0.26, 0.410),
            ("Dotyczy: postępowania o udzielenie zamówienia publicznego pn. Budowa drogi", 0.10, 0.450),
        ),
        ["Odwołujący:", "Firma Alfa", "KRS: 0000123456", "Adres do doręczeń", "ul. Długa", "biuro@kancelaria.pl",
         "Zamawiający:", "Gmina Beta", "NIP: 1234567890", "Dotyczy:"],
    ),
    (
        "tabela etykieta | wartość bez dwukropków (wydruk bankowy) → wierszami",
        page(
            [("Data operacji", 0.10, 0.200), ("2024-03-15", 0.30, 0.200)],
            [("Kwota", 0.10, 0.215), ("1 250,50 PLN", 0.30, 0.215)],
            [("Odbiorca", 0.10, 0.230), ("Firma Alfa sp. z o.o.", 0.30, 0.230)],
        ),
        ["Data operacji | 2024-03-15", "Kwota | 1 250,50 PLN", "Odbiorca | Firma Alfa"],
    ),
    (
        "nagłówki nad wartościami (kwota | data) → kolumnami: nagłówek, pod nim jego wartość",
        page(
            [("Kwota operacji", 0.10, 0.200), ("Data transakcji", 0.50, 0.200)],
            [("200,00 PLN", 0.10, 0.215), ("2026-03-21", 0.50, 0.215)],
        ),
        ["Kwota operacji\n200,00 PLN", "Data transakcji\n2026-03-21"],
    ),
    (
        "równorzędne kolumny stron przelewu (nazwy, adresy, rachunki) → kolumnami",
        page(
            [("Zleceniodawca", 0.10, 0.200), ("Beneficjent", 0.50, 0.200)],
            [("Firma Alfa sp. z o.o.", 0.10, 0.215), ("Gmina Beta", 0.50, 0.215)],
            [("ul. Polna 1, 00-001 Warszawa", 0.10, 0.230), ("ul. Rynek 1, 30-001 Kraków", 0.50, 0.230)],
        ),
        ["Zleceniodawca\nFirma Alfa", "ul. Polna 1", "Beneficjent\nGmina Beta", "ul. Rynek 1"],
    ),
    (
        "etykiety nad danymi (wcięte dane), bez przerw → bez zmian",
        page(
            ("Odwołujący:", 0.10, 0.200),
            ("Firma Alfa sp. z o.o.", 0.26, 0.215),
            ("ul. Polna 1, Warszawa", 0.26, 0.230),
            ("Zamawiający:", 0.10, 0.245),
            ("Gmina Beta", 0.26, 0.260),
        ),
        ["Odwołujący:", "Firma Alfa", "ul. Polna 1", "Zamawiający:", "Gmina Beta"],
    ),
    (
        "etykieta w wierszu z pierwszą linią danych → „etykieta | wartość”, bez zmian",
        page(
            [("Zamawiający:", 0.10, 0.200), ("Gmina Beta", 0.30, 0.200)],
            ("ul. Rynek 1, Beta", 0.30, 0.215),
            [("Odwołujący:", 0.10, 0.260), ("Firma Alfa sp. z o.o.", 0.30, 0.260)],
        ),
        ["Zamawiający: | Gmina Beta", "ul. Rynek 1", "Odwołujący: | Firma Alfa"],
    ),
    (
        "jedna kolumna jak w danych treningowych (etykieta nad danymi, ten sam x) → bez zmian",
        page(
            ("Odwołujący:", 0.10, 0.200),
            ("Firma Alfa sp. z o.o.", 0.10, 0.215),
            ("KRS: 0000123456", 0.10, 0.230),
            ("Zamawiający:", 0.10, 0.245),
            ("Gmina Beta", 0.10, 0.260),
        ),
        ["Odwołujący:", "Firma Alfa", "KRS: 0000123456", "Zamawiający:", "Gmina Beta"],
    ),
    (
        "potwierdzenie przelewu: „Tytuł” wyśrodkowany przy 3 liniach tytułu → przed tytułem, po „Data”",
        page(
            [("Data operacji", 0.10, 0.200), ("2024-03-15", 0.30, 0.200)],
            ("wpis od odwołania", 0.30, 0.215),
            ("postępowanie ZP.271.14.2023", 0.30, 0.230),
            ("Tytuł", 0.10, 0.237),
            ("Firma Alfa", 0.30, 0.245),
            [("Status", 0.10, 0.260), ("zrealizowany", 0.30, 0.260)],
        ),
        ["Data operacji | 2024-03-15", "Tytuł", "wpis od odwołania", "ZP.271.14.2023", "Firma Alfa", "Status"],
    ),
    (
        "nagłówek wyśrodkowany pod blokiem adresata po prawej → bez zmian",
        page(
            ("Prezes Krajowej Izby Odwoławczej", 0.56, 0.140),
            ("ul. Postępu 17a, Warszawa", 0.56, 0.155),
            ("ODWOŁANIE", 0.42, 0.170),
        ),
        ["Prezes Krajowej", "ul. Postępu", "ODWOŁANIE"],
    ),
    (
        "numer punktu listy obok akapitu nie jest etykietą",
        page(
            ("w dniu 14 lutego 2024 r. Zamawiający odrzucił ofertę", 0.20, 0.300),
            ("1.", 0.10, 0.308),
            ("Odwołującego, naruszając art. 226 ust. 1 Pzp", 0.20, 0.315),
        ),
        ["w dniu 14 lutego", "1.", "Odwołującego, naruszając"],
    ),
]


def main() -> int:
    ok = fail = 0
    print("== linearyzacja świadoma kolumn ==")
    for name, pg, parts in CASES:
        txt = columns_text(pg)
        good = order_ok(txt, parts)
        ok += good
        fail += not good
        print(f"  {'OK  ' if good else 'FAIL'} {name}")
        if not good:
            print("       " + txt.replace("\n", "\n       "))
    print(f"\n{ok} OK, {fail} FAIL")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
