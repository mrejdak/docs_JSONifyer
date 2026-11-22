"""Testy ekstrakcji z atrapą LLM (bez sieci): decyzje weryfikacji (verify.py) i złożenie wyniku (extract.py).

  .venv\\Scripts\\python -m tools.test_extraction
"""

from __future__ import annotations

import json
import sys

from odw2json import llm
from odw2json.config import doc_types
from odw2json.extract import extract


class _Page:
    def __init__(self, text: str):
        self.text = text


class FakeDoc:
    def __init__(self, pages: list[str]):
        self._pages = pages
        self.page_count = len(pages)

    def text(self, n: int | None = None) -> str:
        return "\n".join(self._pages[: n or len(self._pages)])

    def page(self, number: int) -> _Page:
        return _Page(self._pages[number - 1])


PRZELEW = """Bank Przykładowy S.A.
Potwierdzenie wykonania przelewu
Data operacji | 05.05.2026
Rachunek nadawcy | PL61 1090 1014 0000 0712 1981 2874
Rachunek odbiorcy | 41 1010 1O10 0081 3622 3100 0000
Tytuł | wpis od odwołania ZP.271.5.2026 | *
Kwota | 15 000,00 PLN
Numer referencyjny | CEN2605051234567
Dokument wygenerowany 06.05.2026"""

ODWOLANIE = """Warszawa, dnia 5 maja 2026 r.
Prezes Krajowej Izby Odwoławczej
Odwołujący: Alfa Budownictwo sp. z o.o., KRS 0000123456, NIP 1234567890, REGON 123456789
reprezentowana przez r. pr. Annę Kowalską, Kancelaria Radcy Prawnego Anna Kowalska, a.kowalska@kancelaria.example
Zamawiający: Gmina Miasto Przykładowo, NIP 9876543210
dotyczy: postępowania pn. "Przebudowa drogi gminnej nr 123", nr referencyjny ZP.271.5.2026,
ogłoszenie nr 2026/BZP 00123456/01
ODWOŁANIE
Zamawiający w dniu 30 kwietnia 2026 r. odrzucił ofertę Odwołującego. Zarzucam naruszenie art. 226 Pzp."""


def stub_for(answers: dict):
    """Odpowiedź atrapy wybierana po pierwszym kluczu formatu JSON w prompcie (= wywołanie)."""
    def stub(messages):
        user = messages[-1]["content"]
        fmt = user[user.rindex("Zwróć wyłącznie JSON"):]
        for marker, ans in answers.items():
            if marker in fmt:
                if isinstance(ans, Exception):
                    raise ans
                return json.loads(json.dumps(ans))
        raise AssertionError("nieznane wywołanie: " + fmt[:200])
    return stub


def check(name: str, got, exp) -> bool:
    ok = got == exp
    print(f"{'OK ' if ok else 'ŹLE'} {name:70s} → {got!r}" + ("" if ok else f"  (oczekiwano {exp!r})"))
    return ok


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    T = doc_types()
    ok = True

    # ---------------------------------------------------------------- przelew
    llm.set_stub(stub_for({"przelew_bankowy": {"przelew_bankowy": {
        "data_operacji": "2026-05-05", "kwota": "15000.0",
        "na_rachunek": "41101010100081362231000000",      # LLM poprawił O→0, bez spacji
        "numer_transakcji": "CEN2605059999999",          # halucynacja (nie ma w tekście)
        "tytul": "wpis od odwołania ZP.271.5.2026 | *",
        "z_rachunku": "61109010140000071219812874"}}}))  # LLM zgubił prefiks PL
    res, tr = extract(FakeDoc([PRZELEW]), T["przelew"])
    pb, f = res["przelew_bankowy"], tr["fields"]
    ok &= check("rachunek: prefiks PL z dokumentu (kandydat regex)", pb["z_rachunku"], "PL61109010140000071219812874")
    ok &= check("  decyzja", f["przelew_bankowy.z_rachunku"]["decision"], "agree")
    ok &= check("rachunek: błąd OCR (O→0) poprawiony przez LLM, w tekście ±1 znak", pb["na_rachunek"], "41101010100081362231000000")
    ok &= check("kwota 15 000,00 PLN ↔ 15000.0", pb["kwota"], 15000.0)
    ok &= check("data operacji w tekście", pb["data_operacji"], "2026-05-05")
    ok &= check("halucynacja numeru transakcji → null", pb["numer_transakcji"], None)
    ok &= check("  decyzja", f["przelew_bankowy.numer_transakcji"]["decision"], "rejected_not_in_text")
    ok &= check("tytuł bez artefaktu kolumn ' | *'", pb["tytul"], "wpis od odwołania ZP.271.5.2026")

    # data spoza tekstu
    llm.set_stub(stub_for({"przelew_bankowy": {"przelew_bankowy": {"data_operacji": "2026-05-07", "kwota": 15000}}}))
    res, _ = extract(FakeDoc([PRZELEW]), T["przelew"])
    ok &= check("data spoza tekstu → null", res["przelew_bankowy"]["data_operacji"], None)

    # LLM niedostępny → tryb awaryjny (kandydaci regex)
    llm.set_stub(stub_for({"przelew_bankowy": llm.LLMUnavailable("HTTP 503")}))
    res, tr = extract(FakeDoc([PRZELEW]), T["przelew"])
    ok &= check("błąd LLM → pola z kandydatów regex (kwota)", res["przelew_bankowy"]["kwota"], 15000.0)
    ok &= check("  ślad: wywołanie z błędem", "error" in tr["calls"]["main"], True)

    # ---------------------------------------------------------------- odwołanie
    strony = {"Odwolujacy": [{"krs": "0000123456", "nazwa": "Alfa Budownictwo sp. z o.o.", "nip": "1234567890",
                              "regon": "123456789", "przez-pelnomocnika": "1",
                              "pelnomocnik": {"imie_nazwisko": "r. pr. Anna Kowalska", "nazwa": "Kancelaria Radcy Prawnego Anna Kowalska",
                                              "mail": "a.kowalska@kancelaria.example"}}],
              "Zamawiajacy": [{"krs": None, "nazwa": "Gmina Miasto Przykładowo", "nip": "9876543210", "regon": None,
                               "prowadzacy_postepowanie": 0}]}
    post = {"_naglowek": "Warszawa, dnia 5 maja 2026 r.", "OdwolanieKIO": {"data": "2026-05-05", "miejscowosc": "Warszawa"},
            "ZamowieniePubliczne": {"numer_bzp": "2026/BZP 00123456/01", "numer_postepowania": "ZP.271.5.2026",
                                    "numer_ted": None, "tytul": "Przebudowa drogi gminnej nr 123"}}
    zarzut = {"_pierwsza_czynnosc": "odrzucił ofertę Odwołującego", "OdwolanieKIO": {"czynnosc_dzien": "2026-04-30", "czynnosc_powod_id": 1}}
    llm.set_stub(stub_for({'"Odwolujacy"': strony, '"_naglowek"': post, '"_pierwsza_czynnosc"': zarzut}))
    res, tr = extract(FakeDoc([ODWOLANIE]), T["odwolanie"])
    o = res["Odwolujacy"][0]
    ok &= check("pełnomocnik: odmiana w tekście (Annę Kowalską) → mianownik", o["pelnomocnik"]["imie_nazwisko"], "Anna Kowalska")
    ok &= check("przez-pelnomocnika '1' → 1", o["przez-pelnomocnika"], 1)
    ok &= check("jeden Zamawiający → prowadzacy_postepowanie null (reguła spójności)", res["Zamawiajacy"][0]["prowadzacy_postepowanie"], None)
    ok &= check("numer BZP bez spacji", res["ZamowieniePubliczne"]["numer_bzp"], "2026/BZP00123456/01")
    ok &= check("data z linii nagłówka (x-evidence)", res["OdwolanieKIO"]["data"], "2026-05-05")
    ok &= check("czynnosc_opis ze słownika (pole pochodne)", res["OdwolanieKIO"]["czynnosc_opis"], "Decyzja o odrzuceniu oferty")
    ok &= check("czynnosc_dzien w tekście", res["OdwolanieKIO"]["czynnosc_dzien"], "2026-04-30")

    # NIP wpisany przez LLM jako KRS (numer stoi przy etykiecie „NIP”) → null
    s1 = json.loads(json.dumps(strony))
    s1["Zamawiajacy"][0]["krs"] = "9876543210"
    llm.set_stub(stub_for({'"Odwolujacy"': s1, '"_naglowek"': post, '"_pierwsza_czynnosc"': zarzut}))
    res, tr = extract(FakeDoc([ODWOLANIE]), T["odwolanie"])
    ok &= check("NIP wpisany jako KRS → null (wartość innego pola)", res["Zamawiajacy"][0]["krs"], None)
    ok &= check("  decyzja", tr["fields"]["Zamawiajacy[0].krs"]["decision"], "other_field_value")
    ok &= check("  NIP Zamawiającego bez zmian", res["Zamawiajacy"][0]["nip"], "9876543210")

    # brak linii nagłówka: LLM podaje datę mimo _naglowek = null → null
    post2 = {**post, "_naglowek": None}
    llm.set_stub(stub_for({'"Odwolujacy"': strony, '"_naglowek"': post2, '"_pierwsza_czynnosc"': zarzut}))
    res, tr = extract(FakeDoc([ODWOLANIE]), T["odwolanie"])
    ok &= check("brak cytatu nagłówka → data null mimo wartości od LLM", res["OdwolanieKIO"]["data"], None)
    ok &= check("  decyzja", tr["fields"]["OdwolanieKIO.data"]["decision"], "no_evidence")
    # cytat nagłówka spoza tekstu (halucynacja) → null
    post3 = {**post, "_naglowek": "Kraków, 1 czerwca 2026 r.", "OdwolanieKIO": {"data": "2026-06-01", "miejscowosc": "Kraków"}}
    llm.set_stub(stub_for({'"Odwolujacy"': strony, '"_naglowek"': post3, '"_pierwsza_czynnosc"': zarzut}))
    res, _ = extract(FakeDoc([ODWOLANIE]), T["odwolanie"])
    ok &= check("cytat nagłówka spoza tekstu → miejscowość null", res["OdwolanieKIO"]["miejscowosc"], None)
    # przez-pelnomocnika 0 → dane pełnomocnika wyczyszczone (reguła spójności)
    s0 = json.loads(json.dumps(strony))
    s0["Odwolujacy"][0]["przez-pelnomocnika"] = 0
    s0["Odwolujacy"][0]["pelnomocnik"] = {"imie_nazwisko": None, "nazwa": "Kancelaria Radcy Prawnego Anna Kowalska", "mail": None}
    llm.set_stub(stub_for({'"Odwolujacy"': s0, '"_naglowek"': post, '"_pierwsza_czynnosc"': zarzut}))
    res, _ = extract(FakeDoc([ODWOLANIE]), T["odwolanie"])
    ok &= check("przez-pelnomocnika 0 → nazwa pełnomocnika null", res["Odwolujacy"][0]["pelnomocnik"]["nazwa"], None)

    llm.set_stub(None)
    print("\nwszystkie poprawne" if ok else "\nSĄ BŁĘDY")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
