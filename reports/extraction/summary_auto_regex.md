# Ekstrakcja — F1 (tekst `auto`, LLM `wyłączony`, zestaw `all`, klasyfikacja z etykiety)

Dokumentów: 210, czas: 1 s. Błędy wywołań LLM: 350.

| miara | precision | recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| **micro (null/null = TP)** | 0.9204 | 0.5761 | **0.7086** | 1526 | 132 | 1123 |
| tylko wartości niepuste | 0.9022 | 0.5203 | 0.6600 | | | |

## Per typ i zestaw

| typ | zestaw | dok. | P | R | F1 |
|---|---|---|---|---|---|
| odwolanie | K | 10 | 0.911 | 0.599 | 0.723 |
| odwolanie | S | 60 | 0.947 | 0.609 | 0.741 |
| pelnomocnictwo | K | 10 | 1.000 | 0.417 | 0.588 |
| pelnomocnictwo | S | 60 | 1.000 | 0.409 | 0.581 |
| przelew | K | 10 | 0.788 | 0.683 | 0.732 |
| przelew | S | 60 | 0.807 | 0.733 | 0.769 |

## Per pole

| pole | n | TP | FP | FN | F1 | błędy: decyzje |
|---|---|---|---|---|---|---|
| OdwolanieKIO.czynnosc_dzien | 70 | 0 | 54 | 70 | 0.000 | regex_fallback 54, absent 16 |
| OdwolanieKIO.czynnosc_opis | 70 | 0 | 0 | 70 | 0.000 | derived 70 |
| OdwolanieKIO.czynnosc_powod_id | 70 | 0 | 0 | 70 | 0.000 | absent 70 |
| OdwolanieKIO.data | 70 | 58 | 0 | 12 | 0.906 | absent 12 |
| OdwolanieKIO.miejscowosc | 70 | 58 | 0 | 12 | 0.906 | absent 12 |
| Odwolujacy.krs | 70 | 70 | 0 | 0 | 1.000 |  |
| Odwolujacy.nazwa | 70 | 0 | 0 | 70 | 0.000 | absent 70 |
| Odwolujacy.nip | 70 | 70 | 0 | 0 | 1.000 |  |
| Odwolujacy.pelnomocnik.imie_nazwisko | 70 | 1 | 0 | 69 | 0.028 | absent 69 |
| Odwolujacy.pelnomocnik.mail | 70 | 65 | 1 | 5 | 0.956 | absent 4, regex_fallback 1 |
| Odwolujacy.pelnomocnik.nazwa | 70 | 1 | 0 | 69 | 0.028 | absent 69 |
| Odwolujacy.przez-pelnomocnika | 70 | 0 | 0 | 70 | 0.000 | absent 70 |
| Odwolujacy.regon | 70 | 70 | 0 | 0 | 1.000 |  |
| Zamawiajacy.krs | 73 | 69 | 1 | 3 | 0.972 | ? 3, regex_fallback 1 |
| Zamawiajacy.nazwa | 74 | 0 | 0 | 74 | 0.000 | absent 70, ? 4 |
| Zamawiajacy.nip | 73 | 69 | 0 | 4 | 0.972 | ? 3, absent 1 |
| Zamawiajacy.prowadzacy_postepowanie | 74 | 66 | 0 | 8 | 0.943 | absent 4, ? 4 |
| Zamawiajacy.regon | 74 | 69 | 1 | 4 | 0.965 | ? 4, regex_fallback 1 |
| ZamowieniePubliczne.numer_bzp | 70 | 70 | 0 | 0 | 1.000 |  |
| ZamowieniePubliczne.numer_postepowania | 70 | 70 | 0 | 0 | 1.000 |  |
| ZamowieniePubliczne.numer_ted | 70 | 70 | 0 | 0 | 1.000 |  |
| ZamowieniePubliczne.tytul | 70 | 69 | 1 | 1 | 0.986 | regex_fallback 1 |
| mocodawca.data.imie_nazwisko | 70 | 65 | 0 | 5 | 0.963 | absent 5 |
| mocodawca.data.krs | 77 | 70 | 0 | 7 | 0.952 | ? 7 |
| mocodawca.data.nazwa | 77 | 1 | 0 | 76 | 0.026 | absent 69, ? 7 |
| mocodawca.data.nip | 77 | 70 | 0 | 7 | 0.952 | ? 7 |
| mocodawca.data.typ | 77 | 0 | 0 | 77 | 0.000 | absent 70, ? 7 |
| mocodawca.podpisujacy.imie_nazwisko | 109 | 0 | 0 | 109 | 0.000 | absent 70, ? 39 |
| pelnomocnicy.imie_nazwisko | 115 | 0 | 0 | 115 | 0.000 | absent 70, ? 45 |
| pelnomocnicy.pesel | 71 | 70 | 0 | 1 | 0.993 | ? 1 |
| przelew_bankowy.data_operacji | 70 | 65 | 0 | 5 | 0.963 | absent 5 |
| przelew_bankowy.kwota | 70 | 59 | 2 | 11 | 0.901 | absent 9, regex_fallback 2 |
| przelew_bankowy.na_rachunek | 70 | 61 | 0 | 9 | 0.931 | absent 9 |
| przelew_bankowy.numer_transakcji | 70 | 60 | 1 | 10 | 0.916 | absent 9, regex_fallback 1 |
| przelew_bankowy.tytul | 70 | 0 | 70 | 70 | 0.000 | regex_fallback 70 |
| przelew_bankowy.z_rachunku | 70 | 60 | 1 | 10 | 0.916 | absent 9, regex_fallback 1 |

## Najsłabsze dokumenty

| dokument | typ | F1 | wywołania |
|---|---|---|---|
| przyklad_48__pelnomocnictwo | pelnomocnictwo→pelnomocnictwo | 0.4 | {"main": "LLM wyłączony / niedostępny"} |
| przyklad_46__pelnomocnictwo | pelnomocnictwo→pelnomocnictwo | 0.4211 | {"main": "LLM wyłączony / niedostępny"} |
| przyklad_49__pelnomocnictwo | pelnomocnictwo→pelnomocnictwo | 0.4211 | {"main": "LLM wyłączony / niedostępny"} |
| przyklad_16__potwierdzenie_przelewu | przelew→przelew | 0.4444 | {"main": "LLM wyłączony / niedostępny"} |
| przyklad_30__potwierdzenie_przelewu | przelew→przelew | 0.4444 | {"main": "LLM wyłączony / niedostępny"} |
| przyklad_41__pelnomocnictwo | pelnomocnictwo→pelnomocnictwo | 0.4444 | {"main": "LLM wyłączony / niedostępny"} |
| przyklad_50__pelnomocnictwo | pelnomocnictwo→pelnomocnictwo | 0.4444 | {"main": "LLM wyłączony / niedostępny"} |
| przyklad_60__pelnomocnictwo | pelnomocnictwo→pelnomocnictwo | 0.4444 | {"main": "LLM wyłączony / niedostępny"} |
| skany__potwierdzenia__0008 | przelew→przelew | 0.4444 | {"main": "LLM wyłączony / niedostępny"} |
| skany__pelnomocnictwa__0007 | pelnomocnictwo→pelnomocnictwo | 0.4706 | {"main": "LLM wyłączony / niedostępny"} |
