"""Testy wyboru źródła tekstu strony (warstwa tekstowa PDF vs OCR) na sztucznych PDF-ach (wymaga Tesseracta).

Strona z tekstem pisma jest renderowana do obrazu („skan”), a potem składana w warianty, które spotyka się
w prawdziwych aktach: sam skan; skan z dodaną stopką podpisu elektronicznego (warstwa tekstowa częściowa);
skan z niewidoczną poprawną warstwą OCR skanera; skan z niewidoczną warstwą losowych liter (błędne
kodowanie fontu — tekst na stronie widać dobrze, a odczytuje się śmieci). Uruchomienie:
    python -m tools.test_text_layer
"""

from __future__ import annotations

import codecs
import copy
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pymupdf  # noqa: E402

from odw2json.config import settings  # noqa: E402
from odw2json.text import DocumentText  # noqa: E402
from odw2json.text.quality import suspicious, text_stats  # noqa: E402

BODY = (
    "Zamawiajacy w dniu 14 lutego 2024 r. odrzucil oferte Odwolujacego, uznajac ja za niezgodna z warunkami "
    "zamowienia. Odwolujacy wnosi odwolanie od tej czynnosci i zarzuca Zamawiajacemu naruszenie art. 226 "
    "ust. 1 pkt 5 ustawy Prawo zamowien publicznych przez odrzucenie oferty, ktora jest zgodna z opisem "
    "przedmiotu zamowienia. Odwolujacy wnosi o uwzglednienie odwolania oraz nakazanie Zamawiajacemu "
    "uniewaznienia czynnosci odrzucenia oferty i powtorzenia badania i oceny ofert. Postepowanie prowadzone "
    "jest w trybie podstawowym pod nazwa Dostawa sprzetu komputerowego dla szkol w gminie, numer "
    "referencyjny ZP.271.14.2023. Odwolanie zostalo wniesione w terminie, a wpis zostal uiszczony na "
    "rachunek Urzedu Zamowien Publicznych. Do odwolania dolaczono pelnomocnictwo oraz dowod uiszczenia wpisu."
)
STAMP = ("Dokument podpisany elektronicznie kwalifikowanym podpisem elektronicznym przez Jan Nowak "
         "dnia 15.02.2024 10:22:33 CET")
RECT = pymupdf.Rect(60, 60, 535, 760)


def make_pdfs(root: Path) -> dict[str, Path]:
    src = pymupdf.open()
    src.new_page().insert_textbox(RECT, BODY, fontsize=12, fontname="helv")
    png = src[0].get_pixmap(dpi=200).tobytes("png")
    out = {}

    def scan(name: str, extra=None) -> None:
        d = pymupdf.open()
        pg = d.new_page()
        pg.insert_image(pg.rect, stream=png)
        if extra:
            extra(pg)
        out[name] = root / f"{name}.pdf"
        d.save(out[name])

    scan("sam_skan")
    scan("skan_ze_stopka", lambda pg: pg.insert_text((60, 815), STAMP, fontsize=7, fontname="helv"))
    scan("skan_z_dobra_warstwa", lambda pg: pg.insert_textbox(RECT, BODY, fontsize=12, fontname="helv", render_mode=3))
    scan("skan_z_losowa_warstwa",
         lambda pg: pg.insert_textbox(RECT, codecs.encode(BODY, "rot13"), fontsize=12, fontname="helv", render_mode=3))
    src.save(root / "cyfrowy.pdf")
    out["cyfrowy"] = root / "cyfrowy.pdf"
    return out


def main() -> int:
    cfg = copy.deepcopy(settings())
    cfg["ocr"]["cache_dir"] = None  # bez zapisu do cache aplikacji
    root = Path(tempfile.mkdtemp(prefix="odw_textlayer_test_"))
    pdfs = make_pdfs(root)
    ok = fail = 0

    def check(name: str, cond: bool, info=""):
        nonlocal ok, fail
        ok += cond
        fail += not cond
        print(f"  {'OK  ' if cond else 'FAIL'} {name}" + (f" — {info}" if info and not cond else ""))

    print("== miary tekstu ==")
    st = text_stats(BODY)
    check("tekst pisma nie jest podejrzany", suspicious(st, cfg["text"]) is None, st)
    check("losowe litery (błędne kodowanie) są podejrzane",
          suspicious(text_stats(codecs.encode(BODY, "rot13")), cfg["text"]) is not None)
    check("znaki zastępcze (font bez mapy znaków) są podejrzane",
          suspicious(text_stats("��� �� " * 20 + BODY[:100]), cfg["text"]) is not None)
    check("znaki z obszaru prywatnego Unicode są podejrzane",
          suspicious(text_stats(" " * 40), cfg["text"]) is not None)

    print("== wybór źródła tekstu strony ==")
    expect = {
        "cyfrowy": ("text_layer", False),             # zwykły PDF z tekstem — bez OCR
        "sam_skan": ("ocr", False),                   # brak warstwy → OCR (jak dotąd)
        "skan_ze_stopka": ("ocr", True),              # warstwa = sama stopka → porównanie, OCR wygrywa
        "skan_z_dobra_warstwa": ("text_layer", True),  # porównanie, remis → warstwa tekstowa
        "skan_z_losowa_warstwa": ("ocr", True),       # podejrzana warstwa → OCR
    }
    for name, (source, checked) in expect.items():
        p = DocumentText(pdfs[name], cfg=cfg).page(1)
        tc = p.meta.get("text_check")
        good = p.source == source and (tc is not None) == checked
        info = f"źródło {p.source}, porównanie: {tc and {k: tc[k] for k in ('reason', 'chosen')}}"
        check(f"{name}: {source}" + (" (po porównaniu z OCR)" if checked else ""), good, info)
        if name == "skan_ze_stopka":
            check("  skan ze stopką: treść pisma odczytana", "odrzucil oferte" in p.text.replace("\n", " "), p.text[:120])

    shutil.rmtree(root, ignore_errors=True)
    print(f"\n{ok} OK, {fail} FAIL")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
