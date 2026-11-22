"""Testy klasyfikacji na ręcznie napisanych tekstach (bez PDF).

A. Trudne negatywy z akt sprawy KIO i pozytywy o innej budowie niż dane syntetyczne (teksty wzorowane na
   publicznych wzorach i opisach pism). Domyślnie przez REGEX (tryb awaryjny bez LLM) — wynik informacyjny:
   reguł NIE dostrajamy pod te przypadki, rozstrzyga LLM.  --live: te same przypadki przez prawdziwy LLM z .env.
B. Polityka łączenia regex + LLM (decide) z atrapą LLM: weto „inny”, korekta regexu, ochrona przed
   halucynacją, niska pewność, błąd/nieznany typ, LLM wyłączony, tryb oszczędny.

  .venv\\Scripts\\python -m tools.test_classification_cases               # A (regex) + B
  .venv\\Scripts\\python -m tools.test_classification_cases --live        # A przez LLM (wymaga .env) + B
  .venv\\Scripts\\python -m tools.test_classification_cases --show-prompt # prompt dla 1. przypadku
"""

from __future__ import annotations

import argparse
import os
import sys

from odw2json import classify as C
from odw2json import llm
from odw2json.config import settings


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


CASES: list[tuple[str, str | None, list[str]]] = [
    # ------------------------------------------------------------------ trudne negatywy z akt sprawy KIO
    ("odpowiedź na odwołanie", None, ["""Warszawa, dnia 12.05.2026 r.
Krajowa Izba Odwoławcza
ul. Postępu 17A, 02-676 Warszawa
Sygn. akt: KIO 1234/26
Odwołujący: Alfa Budownictwo sp. z o.o., ul. Leśna 5, 00-001 Warszawa
Zamawiający: Gmina Miasto Przykładowo, ul. Rynek 1, 11-111 Przykładowo
ODPOWIEDŹ NA ODWOŁANIE
Działając w imieniu Zamawiającego, w odpowiedzi na odwołanie z dnia 5 maja 2026 r. wnoszę o oddalenie
odwołania w całości. Zarzut nr 1 dotyczący zaniechania odrzucenia oferty jest bezzasadny, ponieważ czynność
Zamawiającego była zgodna z przepisami ustawy Pzp. Wnoszę o zasądzenie kosztów postępowania."""]),
    ("zgłoszenie przystąpienia (wzór UZP)", None, ["""Kraków, 14.05.2026
Prezes Krajowej Izby Odwoławczej
ul. Postępu 17A, 02-676 Warszawa
Sygn. akt KIO 1234/26
Zgłoszenie przystąpienia do postępowania odwoławczego
Zamawiający: Gmina Miasto Przykładowo
Odwołujący: Alfa Budownictwo sp. z o.o.
Przystępujący: Beta Serwis S.A., KRS 0000123456
Działając na podstawie art. 525 ust. 1 ustawy Pzp zgłaszam przystąpienie do postępowania odwoławczego
po stronie Zamawiającego. Przystępujący ma interes w rozstrzygnięciu na korzyść Zamawiającego, gdyż jego
oferta została wybrana jako najkorzystniejsza. Zarzuty odwołania są bezzasadne. Wnoszę o oddalenie odwołania."""]),
    ("pismo procesowe odwołującego", None, ["""Warszawa, 20.05.2026
Krajowa Izba Odwoławcza
Sygn. akt: KIO 1234/26
Odwołujący: Alfa Budownictwo sp. z o.o.
Zamawiający: Gmina Miasto Przykładowo
PISMO PROCESOWE ODWOŁUJĄCEGO
W nawiązaniu do odpowiedzi na odwołanie Odwołujący podtrzymuje wszystkie zarzuty odwołania i wnosi o
uwzględnienie odwołania. Czynność Zamawiającego narusza art. 226 ust. 1 Pzp."""]),
    ("skarga na wyrok KIO", None, ["""Warszawa, 2 czerwca 2026 r.
Sąd Okręgowy w Warszawie
XXIII Wydział Gospodarczy Odwoławczy i Zamówień Publicznych
za pośrednictwem Prezesa Krajowej Izby Odwoławczej
Skarżący: Alfa Budownictwo sp. z o.o. (Odwołujący w postępowaniu przed KIO)
Przeciwnik skargi: Gmina Miasto Przykładowo (Zamawiający)
Sygn. akt KIO 1234/26
SKARGA
na wyrok Krajowej Izby Odwoławczej z dnia 25 maja 2026 r. Zaskarżam wyrok w całości i zarzucam
naruszenie art. 226 ust. 1 pkt 5 Pzp. Wnoszę o zmianę wyroku i uwzględnienie odwołania."""]),
    ("wyrok KIO", None, ["""Sygn. akt: KIO 1234/26
WYROK
z dnia 25 maja 2026 r.
Krajowa Izba Odwoławcza - w składzie:
Przewodniczący: Jan Nowak
po rozpoznaniu na rozprawie odwołania wniesionego do Prezesa Krajowej Izby Odwoławczej przez wykonawcę
Alfa Budownictwo sp. z o.o. w postępowaniu prowadzonym przez Zamawiającego: Gmina Miasto Przykładowo
orzeka: oddala odwołanie."""]),
    ("odpis KRS", None, ["""CENTRALNA INFORMACJA KRAJOWEGO REJESTRU SĄDOWEGO
Stan na dzień 01.05.2026 r.
Numer KRS: 0000123456
ODPIS AKTUALNY Z REJESTRU PRZEDSIĘBIORCÓW
Dział 1 Rubryka 1 - Dane podmiotu
Forma prawna: SPÓŁKA Z OGRANICZONĄ ODPOWIEDZIALNOŚCIĄ
Numer REGON/NIP: REGON: 123456789, NIP: 1234567890
Firma, pod którą spółka działa: ALFA BUDOWNICTWO SPÓŁKA Z OGRANICZONĄ ODPOWIEDZIALNOŚCIĄ
Dział 2 Rubryka 1 - Organ uprawniony do reprezentacji podmiotu
Sposób reprezentacji: Do reprezentowania spółki uprawniony jest Prezes Zarządu samodzielnie. Prokura."""]),
    ("wyciąg bankowy", None, ["""Bank Przykładowy S.A.
WYCIĄG Z RACHUNKU nr 5/2026 za okres 01.05.2026 - 31.05.2026
Rachunek: PL61 1090 1014 0000 0712 1981 2874
Saldo początkowe: 125 000,00 PLN
Data operacji Opis Kwota
05.05.2026 Przelew wychodzący - wpis od odwołania ZP.271.5.2026, odbiorca: Urząd Zamówień Publicznych -15 000,00
06.05.2026 Przelew przychodzący - faktura 12/2026 +4 920,00
Saldo końcowe: 114 920,00 PLN"""]),
    ("faktura VAT", None, ["""FAKTURA VAT nr FV/12/2026
Data wystawienia: 06.05.2026
Sprzedawca: Alfa Budownictwo sp. z o.o., NIP 1234567890
Nabywca: Gmina Miasto Przykładowo, NIP 9876543210
Lp. Nazwa usługi Ilość Cena netto Wartość netto VAT Wartość brutto
1. Roboty budowlane 1 4 000,00 4 000,00 23% 4 920,00
Do zapłaty: 4 920,00 PLN. Termin płatności: 20.05.2026. Przelew na rachunek: 61 1090 1014 0000 0712 1981 2874"""]),
    ("ogłoszenie o zamówieniu (BZP)", None, ["""Ogłoszenie nr 2026/BZP 00123456/01 z dnia 2026-04-01
Ogłoszenie o zamówieniu
Roboty budowlane
SEKCJA I - ZAMAWIAJĄCY
1.1.) Rola zamawiającego: Postępowanie prowadzone jest samodzielnie przez zamawiającego
SEKCJA II - INFORMACJE PODSTAWOWE"""]),
    # ---------------------------------------- inne pisma z akt KIO, które cytują lub streszczają odwołanie
    ("uzasadnienie wyroku KIO streszczające odwołanie", None, ["""Sygn. akt: KIO 1234/26
UZASADNIENIE
Zamawiający – Gmina Miasto Przykładowo – prowadzi postępowanie o udzielenie zamówienia publicznego pn.
„Przebudowa drogi gminnej nr 123”, nr ZP.271.5.2026, ogłoszenie nr 2026/BZP 00123456/01.
W dniu 5 maja 2026 r. wykonawca Alfa Budownictwo sp. z o.o. wniósł odwołanie do Prezesa Krajowej Izby
Odwoławczej wobec czynności odrzucenia jego oferty, zarzucając Zamawiającemu naruszenie art. 226 ust. 1
pkt 5 ustawy Pzp. Odwołujący wniósł o: „uwzględnienie odwołania i nakazanie Zamawiającemu unieważnienia
czynności odrzucenia oferty Odwołującego oraz powtórzenia czynności badania i oceny ofert”.
Zamawiający w odpowiedzi na odwołanie wniósł o jego oddalenie.
Izba ustaliła i zważyła, co następuje:
Odwołanie nie zasługuje na uwzględnienie.""", """Izba nie podzieliła stanowiska Odwołującego, że treść oferty odpowiada warunkom zamówienia.
Mając powyższe na uwadze, orzeczono jak w sentencji. O kosztach postępowania orzeczono stosownie do
jego wyniku na podstawie art. 557 ustawy Pzp.
Przewodniczący: ……………………"""]),
    ("odpowiedź na odwołanie cytująca zarzuty (bez nagłówka)", None, ["""Gmina Miasto Przykładowo
ul. Rynek 1, 11-111 Przykładowo
Przykładowo, 12 maja 2026 r.
Krajowa Izba Odwoławcza
Sygn. akt KIO 1234/26
Działając w imieniu Zamawiającego, ustosunkowuję się do odwołania wniesionego przez Alfa Budownictwo
sp. z o.o. Odwołujący w odwołaniu podniósł: „Zarzucam Zamawiającemu naruszenie art. 226 ust. 1 pkt 5
Pzp poprzez odrzucenie oferty Odwołującego i wnoszę o nakazanie Zamawiającemu unieważnienia tej
czynności”. Zarzut ten jest chybiony. Oferta Odwołującego nie odpowiadała wymaganiom SWZ.
Wobec powyższego Zamawiający wnosi o oddalenie odwołania w całości."""]),
    ("cofnięcie odwołania", None, ["""Warszawa, 18 maja 2026 r.
Prezes Krajowej Izby Odwoławczej
Sygn. akt KIO 1234/26
Odwołujący: Alfa Budownictwo sp. z o.o.
Zamawiający: Gmina Miasto Przykładowo
Działając w imieniu Odwołującego, na podstawie pełnomocnictwa znajdującego się w aktach sprawy, cofam
odwołanie wniesione w dniu 5 maja 2026 r. od czynności odrzucenia oferty Odwołującego w postępowaniu
nr ZP.271.5.2026 i wnoszę o umorzenie postępowania odwoławczego oraz zwrot 90% wpisu.
r. pr. Anna Kowalska"""]),
    ("zawiadomienie KIO o posiedzeniu i rozprawie", None, ["""KRAJOWA IZBA ODWOŁAWCZA
ul. Postępu 17A, 02-676 Warszawa
Warszawa, dnia 10 maja 2026 r.
Sygn. akt KIO 1234/26
Alfa Budownictwo sp. z o.o. (Odwołujący)
Gmina Miasto Przykładowo (Zamawiający)
ZAWIADOMIENIE
Uprzejmie zawiadamia się, że posiedzenie z udziałem stron i rozprawa w sprawie z odwołania wniesionego
przez Alfa Budownictwo sp. z o.o. w postępowaniu prowadzonym przez Gminę Miasto Przykładowo odbędą się
w dniu 20 maja 2026 r. o godz. 10:00 w siedzibie Urzędu Zamówień Publicznych, sala nr 2."""]),
    ("postanowienie KIO o umorzeniu", None, ["""Sygn. akt: KIO 1234/26
POSTANOWIENIE
z dnia 21 maja 2026 r.
Krajowa Izba Odwoławcza – w składzie: Przewodniczący: Jan Nowak
po rozpoznaniu na posiedzeniu niejawnym bez udziału stron odwołania wniesionego do Prezesa Krajowej
Izby Odwoławczej w dniu 5 maja 2026 r. przez wykonawcę Alfa Budownictwo sp. z o.o., w postępowaniu
prowadzonym przez Zamawiającego: Gmina Miasto Przykładowo
postanawia: 1. umorzyć postępowanie odwoławcze; 2. nakazać zwrot z rachunku Urzędu Zamówień Publicznych
na rzecz Odwołującego kwoty 13 500 zł stanowiącej 90% uiszczonego wpisu."""]),
    # ------------------------------------------------------------------ pozytywy o innej budowie
    ("odwołanie bez nagłówka 'ODWOŁANIE' w osobnej linii", "odwolanie", ["""Pełnomocnik Odwołującego: adw. Jan Kowalski
Kancelaria Adwokacka Jan Kowalski, ul. Prosta 1, 00-002 Warszawa
Warszawa, dnia 5 maja 2026 r.
Do Prezesa Krajowej Izby Odwoławczej
Odwołujący: Alfa Budownictwo sp. z o.o., KRS 0000123456
Zamawiający: Gmina Miasto Przykładowo
Odwołanie od czynności Zamawiającego polegającej na odrzuceniu oferty Odwołującego w postępowaniu
nr ZP.271.5.2026. Na podstawie art. 513 pkt 1 Pzp wnoszę odwołanie i zarzucam Zamawiającemu naruszenie
art. 226 ust. 1 pkt 5 Pzp. Wnoszę o nakazanie unieważnienia czynności odrzucenia oferty."""]),
    ("pełnomocnictwo jako akapit (osoba fizyczna)", "pelnomocnictwo", ["""Ja, niżej podpisany Jan Nowak, prowadzący działalność gospodarczą pod firmą NOWAK-BUD Jan Nowak,
NIP 1234567890, udzielam pełnomocnictwa radcy prawnemu Annie Kowalskiej do reprezentowania mnie
w postępowaniu odwoławczym przed Krajową Izbą Odwoławczą, w tym do wniesienia odwołania.
Warszawa, 4 maja 2026 r.
Jan Nowak"""]),
    ("upoważnienie/pełnomocnictwo z nagłówkiem 'Pełnomocnictwo szczególne'", "pelnomocnictwo", ["""Pełnomocnictwo szczególne
Alfa Budownictwo sp. z o.o. z siedzibą w Warszawie (KRS 0000123456), reprezentowana przez Prezesa Zarządu,
niniejszym ustanawia pełnomocnikiem adw. Jana Kowalskiego i upoważnia go do wniesienia odwołania do Prezesa
Krajowej Izby Odwoławczej oraz do zastępowania Mocodawcy na rozprawie."""]),
    ("potwierdzenie: 'Szczegóły transakcji'", "przelew", ["""mBank S.A.
Szczegóły transakcji
Typ: przelew wychodzący
Z rachunku: 12 1140 2004 0000 3102 1234 5678
Na rachunek: 41 1010 1010 0081 3622 3100 0000
Odbiorca: Urząd Zamówień Publicznych
Tytułem: wpis od odwołania ZP.271.5.2026
Kwota: 15 000,00 PLN
Data realizacji: 05.05.2026"""]),
    ("odwołanie cytujące wyrok KIO (2 strony)", "odwolanie", ["""Warszawa, dnia 5 maja 2026 r.
Prezes Krajowej Izby Odwoławczej
ul. Postępu 17A, 02-676 Warszawa
Odwołujący: Alfa Budownictwo sp. z o.o., ul. Leśna 5, 00-001 Warszawa, KRS 0000123456, NIP 1234567890
reprezentowany przez r. pr. Annę Kowalską
Zamawiający: Gmina Miasto Przykładowo, ul. Rynek 1, 11-111 Przykładowo
Dotyczy: postępowania o udzielenie zamówienia publicznego pn. „Przebudowa drogi gminnej nr 123”,
nr ZP.271.5.2026, ogłoszenie nr 2026/BZP 00123456/01
Działając w imieniu Odwołującego, wnoszę odwołanie od czynności Zamawiającego z dnia 30 kwietnia 2026 r.
polegającej na odrzuceniu oferty Odwołującego. Zarzucam Zamawiającemu naruszenie art. 226 ust. 1 pkt 5
ustawy Pzp. Wnoszę o uwzględnienie odwołania i nakazanie Zamawiającemu unieważnienia czynności
odrzucenia oferty Odwołującego.""", """UZASADNIENIE
Stanowisko Odwołującego znajduje potwierdzenie w orzecznictwie. W wyroku z dnia 12 stycznia 2025 r.,
sygn. akt KIO 45/25, Krajowa Izba Odwoławcza w składzie: Przewodniczący: Piotr Wiśniewski, wskazała:
„Izba uwzględnia odwołanie i nakazuje Zamawiającemu unieważnienie czynności odrzucenia oferty, gdyż
niezgodność treści oferty z warunkami zamówienia musi być jednoznaczna”.
Załączniki: pełnomocnictwo, dowód uiszczenia wpisu, dowód przekazania kopii odwołania Zamawiającemu."""]),
    ("pełnomocnictwo konsorcjum", "pelnomocnictwo", ["""PEŁNOMOCNICTWO
My, niżej podpisani, działając w imieniu wykonawców wspólnie ubiegających się o udzielenie zamówienia:
1) Alfa Budownictwo sp. z o.o. z siedzibą w Warszawie, KRS 0000123456 – Lider,
2) Beta Instalacje S.A. z siedzibą w Krakowie, KRS 0000654321 – Partner,
udzielamy pełnomocnictwa Liderowi oraz r. pr. Annie Kowalskiej do reprezentowania wykonawców w
postępowaniu o udzielenie zamówienia nr ZP.271.5.2026 oraz w postępowaniu odwoławczym przed Krajową
Izbą Odwoławczą, w tym do wniesienia odwołania.
Za Alfa Budownictwo sp. z o.o.: Jan Nowak – Prezes Zarządu
Za Beta Instalacje S.A.: Ewa Zielińska – Członek Zarządu"""]),
    ("potwierdzenie przelewu z błędami OCR", "przelew", ["""BANK PRZYKLADOWY S.A.
POTWIERDZENIE WYKONANIA PRZELEWU
Data operacji | 05.05.2O26
Rachunek nadawcy | 12 1140 2004 OOOO 3102 1234 5678
Nadawca | ALFA BUDOWNICTWO SP. Z 0.0.
Rachunek odbiorcy | 41 1010 1010 0081 3622 3100 0000
Odbiorca | URZAD ZAMOWIEN PUBLICZNYCH
Tytul | Wpis od odwolania ZP.271.5.2026
Kwota | 15 000,00 PLN
Status | Zrealizowany"""]),
]


def _case_text(name: str) -> list[str]:
    return next(pages for n, _, pages in CASES if n == name)


def _sc(evidence: dict[str, int], score: dict[str, int] | None = None) -> dict:
    """Sztuczne wyniki regex do testów decide(): evidence = suma wag sygnałów pozytywnych."""
    score = score or evidence
    return {t: {"score": score.get(t, 0), "evidence": evidence.get(t, 0), "accept": 8, "reject": 4, "margin": 4,
                "hits": [], "neg_hits": []} for t in ("odwolanie", "pelnomocnictwo", "przelew")}


def _v(typ, lvl=3, g=1.0, err=None, spojny=True) -> dict:
    v = {"typ": typ, "pewnosc": {3: "wysoka", 2: "srednia", 1: "niska"}.get(lvl), "poziom": lvl, "spojny": spojny,
         "spelnia": {}, "dowody": [], "uzasadnienie": "", "grounding": g, "rodzaj_dokumentu": ""}
    if err:
        v["error"] = err
    return v


def _wym(**met) -> dict:
    """Odpowiedź „wymagania” atrapy: typ → wszystkie wymagania tak/nie."""
    ids = {"odwolanie": ["autor_adresat", "wnosi_odwolanie", "postepowanie"],
           "pelnomocnictwo": ["udziela", "pelnomocnik_zakres", "podpis"], "przelew": ["operacja", "dane_przelewu"]}
    return {t: {i: ("tak" if met.get(t) else "nie") for i in ids[t]} for t in ids}


def policy_tests() -> int:
    cfg = {"min_level": "srednia", "no_evidence_level": "wysoka", "grounding_min": 0.5}
    T = [  # (opis, wyniki regex, werdykt LLM, oczekiwany typ, oczekiwana ścieżka)
        ("zgodność regex i LLM", _sc({"odwolanie": 15}), _v("odwolanie"), "odwolanie", "llm+regex"),
        ("weto LLM: regex pewny, LLM inny", _sc({"przelew": 12}), _v("inny", 2), None, "llm_inny"),
        ("korekta: regex wskazał inny typ, LLM T z dowodami", _sc({"przelew": 12, "pelnomocnictwo": 6}),
         _v("pelnomocnictwo"), "pelnomocnictwo", "llm"),
        ("korekta: regex brak, LLM T z dowodami", _sc({"pelnomocnictwo": 5}, {"pelnomocnictwo": 2}),
         _v("pelnomocnictwo"), "pelnomocnictwo", "llm"),
        ("halucynacja: LLM T bez dowodów, cytaty nie w tekście", _sc({}), _v("przelew", 3, 0.0), None, "llm_odrzucony"),
        ("LLM T bez dowodów regex, pewność wysoka i cytaty w tekście", _sc({}), _v("pelnomocnictwo", 3, 1.0),
         "pelnomocnictwo", "llm_bez_dowodow"),
        ("LLM T bez dowodów, pewność średnia", _sc({}), _v("pelnomocnictwo", 2, 1.0), None, "llm_odrzucony"),
        ("pewność niska → regex", _sc({"odwolanie": 15}), _v("inny", 1), "odwolanie", "regex_awaryjny"),
        ("niespójny (T bez wymagań koniecznych) + pewny regex", _sc({"odwolanie": 15}), _v("odwolanie", 3, 1.0, None, False),
         "odwolanie", "llm_niespojny"),
        ("niespójny + niepewny regex → brak", _sc({"odwolanie": 6}), _v("odwolanie", 3, 1.0, None, False),
         None, "llm_niespojny"),
        ("błąd LLM → regex", _sc({"odwolanie": 15}), _v("", 0, None, "HTTP 503"), "odwolanie", "regex_awaryjny"),
        ("LLM wyłączony → regex", _sc({"odwolanie": 15}), None, "odwolanie", "regex"),
    ]
    fails = 0
    print("\n== B. Polityka regex + LLM (decide) ==")
    for name, sc, v, exp_t, exp_p in T:
        t, path, reason = C.decide(sc, v, cfg)
        ok = t == exp_t and path == exp_p
        fails += not ok
        print(f"{'OK ' if ok else 'ŹLE'} {name:60s} → {t or 'brak':15s} [{path}]"
              + ("" if ok else f"  oczek. {exp_t} [{exp_p}] ({reason})"))

    # parsowanie odpowiedzi: stopnie pewności, tak/nie
    parse = [(C._level("Średnia"), 2), (C._level("wysoka"), 3), (C._level("NISKA"), 1), (C._level(0.9), 3),
             (C._level("bardzo"), 0), (C._yes("Tak"), True), (C._yes("nie"), False), (C._yes("częściowo"), None)]
    p_ok = all(a == b for a, b in parse)
    fails += not p_ok
    print(f"{'OK ' if p_ok else 'ŹLE'} {'parsowanie stopni pewności i tak/nie':60s} → {[a for a, _ in parse]}")

    # ucięta odpowiedź LLM (limit tokenów) → naprawa: decyzja zachowana, niedokończony cytat odrzucony
    cut = '{"rodzaj_dokumentu": "Pełnomocnictwo", "wymagania": {"pelnomocnictwo": {"udziela": "tak"}}, "typ": "pelnomocnictwo", "pewnosc": "wysoka", "dowody": ["Działając w imieniu \\"Wykonawcy\\", niniejszym udzielam pełnomocnictwa r. pr.'
    try:
        r = llm._extract_json(cut)
        r_ok = r.get("typ") == "pelnomocnictwo" and r.get("pewnosc") == "wysoka" and r.get("_naprawiony")
    except ValueError as e:
        r, r_ok = str(e), False
    fails += not r_ok
    print(f"{'OK ' if r_ok else 'ŹLE'} {'naprawa uciętego JSON (decyzja zachowana)':60s} → {r}")

    calls = []

    def stub_factory(ans):
        def stub(messages):
            calls.append(messages)
            if isinstance(ans, Exception):
                raise ans
            return ans
        return stub

    integ = [  # atrapa LLM w pełnym classify()
        ("atrapa: odpowiedź na odwołanie, LLM inny", "odpowiedź na odwołanie",
         {"rodzaj_dokumentu": "odpowiedź na odwołanie", "wymagania": _wym(), "dowody": ["ODPOWIEDŹ NA ODWOŁANIE"],
          "typ": "inny", "pewnosc": "wysoka"}, None, "llm_inny"),
        ("atrapa: odwołanie, LLM odwolanie (cytat z błędem OCR)", "odwołanie bez nagłówka 'ODWOŁANIE' w osobnej linii",
         {"wymagania": _wym(odwolanie=True), "dowody": ["wnosze odwolanie i zarzucam Zamawiajacemu"],
          "typ": "Odwołanie", "pewnosc": "wysoka"}, "odwolanie", "llm+regex"),
        ("atrapa: wyrok — „inny”, ale wymagania odwołania „tak” → niespójny", "wyrok KIO",
         {"wymagania": _wym(odwolanie=True), "typ": "inny", "pewnosc": "wysoka"}, None, "llm_niespojny"),
        ("atrapa: nieznany typ w odpowiedzi → regex", "faktura VAT",
         {"typ": "faktura", "pewnosc": "wysoka"}, None, "regex_awaryjny"),
        ("atrapa: odpowiedź bez JSON → regex", "potwierdzenie: 'Szczegóły transakcji'",
         ValueError("brak JSON w odpowiedzi"), "przelew", "regex_awaryjny"),
    ]
    for name, case, ans, exp_t, exp_p in integ:
        llm.set_stub(stub_factory(ans))
        c = C.classify(FakeDoc(_case_text(case)))
        ok = c.type == exp_t and c.path == exp_p
        fails += not ok
        print(f"{'OK ' if ok else 'ŹLE'} {name:60s} → {c.type or 'brak':15s} [{c.path}]"
              + ("" if ok else f"  oczek. {exp_t} [{exp_p}] ({c.reason})"))
        if name.startswith("atrapa: odwołanie") and c.llm:
            g_ok = c.llm.get("grounding") == 1.0
            fails += not g_ok
            print(f"{'OK ' if g_ok else 'ŹLE'} {'  cytat z błędami OCR odnaleziony w tekście (grounding)':60s} → {c.llm.get('grounding')}")

    lc = settings()["classification"].setdefault("llm", {})
    lc["call"] = "uncertain"
    calls.clear()
    llm.set_stub(stub_factory({"typ": "inny", "pewnosc": "wysoka"}))
    c = C.classify(FakeDoc(_case_text("potwierdzenie: 'Szczegóły transakcji'")))
    ok = c.path == "regex_pewny" and not calls
    fails += not ok
    print(f"{'OK ' if ok else 'ŹLE'} {'tryb oszczędny: regex pewny → bez wywołania LLM':60s} → "
          f"{c.type or 'brak':15s} [{c.path}], wywołań {len(calls)}")
    lc["call"] = "always"
    llm.set_stub(None)
    return fails


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="przypadki A przez prawdziwy LLM z .env")
    ap.add_argument("--show-prompt", action="store_true")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if a.show_prompt:
        from odw2json.config import doc_types
        lcfg = {"pages": 2, **settings()["classification"]["llm"]}
        for m in C.build_prompt(doc_types(), C.excerpt(FakeDoc(CASES[0][2]), lcfg)):
            print(f"--- {m['role']} ---\n{m['content']}")
        return 0
    if a.live and not llm.available():
        print("--live: LLM niedostępny (ustaw LLM_API_BASE, LLM_API_KEY, LLM_MODEL w .env)")
        return 2
    if not a.live:
        os.environ["ODW_LLM"] = "off"
    print(f"== A. Przypadki ręczne — {'LLM: ' + llm.model_name() if a.live else 'regex (tryb awaryjny, informacyjnie)'} ==")
    fails_a = 0
    for name, expected, pages in CASES:
        c = C.classify(FakeDoc(pages))
        ok = c.type == expected
        fails_a += not ok
        sc = ", ".join(f"{n}={s['score']}" for n, s in c.scores.items())
        print(f"{'OK ' if ok else 'ŹLE'} {name:58s} oczek.={expected or 'brak':15s} wynik={c.type or 'brak':15s} [{c.path}] {sc}")
        if c.llm and (a.live or not ok):
            print(f"      LLM: [{c.llm.get('rodzaj_dokumentu', '')}] → {c.llm.get('typ')} ({c.llm.get('pewnosc')}), "
                  f"spełnia={c.llm.get('spelnia')}, cytaty w tekście={c.llm.get('grounding')} {c.llm.get('error', '')}")
            if a.live:
                print(f"           {c.llm.get('uzasadnienie', '')}")
        if not ok:
            for n, s in c.scores.items():
                print(f"      {n}: +{','.join(s['hits'])}  -{','.join(s['neg_hits'])}")
    print(f"A: {len(CASES) - fails_a}/{len(CASES)} poprawnie")
    os.environ.pop("ODW_LLM", None)
    fails_b = policy_tests()
    print(f"B: {'wszystkie poprawne' if not fails_b else f'{fails_b} błędów'}")
    return 1 if fails_b or (a.live and fails_a) else 0


if __name__ == "__main__":
    sys.exit(main())
