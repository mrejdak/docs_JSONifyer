# Ekstrakcja — F1 (tekst `auto`, LLM `bielik-11b-v3.1`, zestaw `all`, klasyfikacja z etykiety)

Dokumentów: 24, czas: 34 s. Błędy wywołań LLM: 0.

| miara | precision | recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| **micro (null/null = TP)** | 0.9898 | 0.9832 | **0.9865** | 292 | 3 | 5 |
| tylko wartości niepuste | 0.9880 | 0.9802 | 0.9841 | | | |

## Per typ i zestaw

| typ | zestaw | dok. | P | R | F1 |
|---|---|---|---|---|---|
| odwolanie | K | 3 | 1.000 | 0.985 | 0.992 |
| odwolanie | S | 5 | 1.000 | 1.000 | 1.000 |
| pelnomocnictwo | K | 3 | 1.000 | 1.000 | 1.000 |
| pelnomocnictwo | S | 5 | 1.000 | 1.000 | 1.000 |
| przelew | K | 3 | 0.812 | 0.765 | 0.788 |
| przelew | S | 5 | 1.000 | 1.000 | 1.000 |

## Per pole

| pole | n | TP | FP | FN | F1 | błędy: decyzje |
|---|---|---|---|---|---|---|
| OdwolanieKIO.czynnosc_dzien | 8 | 8 | 0 | 0 | 1.000 |  |
| OdwolanieKIO.czynnosc_opis | 8 | 8 | 0 | 0 | 1.000 |  |
| OdwolanieKIO.czynnosc_powod_id | 8 | 8 | 0 | 0 | 1.000 |  |
| OdwolanieKIO.data | 8 | 8 | 0 | 0 | 1.000 |  |
| OdwolanieKIO.miejscowosc | 8 | 8 | 0 | 0 | 1.000 |  |
| Odwolujacy.krs | 8 | 8 | 0 | 0 | 1.000 |  |
| Odwolujacy.nazwa | 8 | 8 | 0 | 0 | 1.000 |  |
| Odwolujacy.nip | 8 | 8 | 0 | 0 | 1.000 |  |
| Odwolujacy.pelnomocnik.imie_nazwisko | 8 | 8 | 0 | 0 | 1.000 |  |
| Odwolujacy.pelnomocnik.mail | 8 | 7 | 0 | 1 | 0.933 | unparsable 1 |
| Odwolujacy.pelnomocnik.nazwa | 8 | 8 | 0 | 0 | 1.000 |  |
| Odwolujacy.przez-pelnomocnika | 8 | 8 | 0 | 0 | 1.000 |  |
| Odwolujacy.regon | 8 | 8 | 0 | 0 | 1.000 |  |
| Zamawiajacy.krs | 8 | 8 | 0 | 0 | 1.000 |  |
| Zamawiajacy.nazwa | 8 | 8 | 0 | 0 | 1.000 |  |
| Zamawiajacy.nip | 8 | 8 | 0 | 0 | 1.000 |  |
| Zamawiajacy.prowadzacy_postepowanie | 8 | 8 | 0 | 0 | 1.000 |  |
| Zamawiajacy.regon | 8 | 8 | 0 | 0 | 1.000 |  |
| ZamowieniePubliczne.numer_bzp | 8 | 8 | 0 | 0 | 1.000 |  |
| ZamowieniePubliczne.numer_postepowania | 8 | 8 | 0 | 0 | 1.000 |  |
| ZamowieniePubliczne.numer_ted | 8 | 8 | 0 | 0 | 1.000 |  |
| ZamowieniePubliczne.tytul | 8 | 8 | 0 | 0 | 1.000 |  |
| mocodawca.data.imie_nazwisko | 8 | 8 | 0 | 0 | 1.000 |  |
| mocodawca.data.krs | 8 | 8 | 0 | 0 | 1.000 |  |
| mocodawca.data.nazwa | 8 | 8 | 0 | 0 | 1.000 |  |
| mocodawca.data.nip | 8 | 8 | 0 | 0 | 1.000 |  |
| mocodawca.data.typ | 8 | 8 | 0 | 0 | 1.000 |  |
| mocodawca.podpisujacy.imie_nazwisko | 8 | 8 | 0 | 0 | 1.000 |  |
| pelnomocnicy.imie_nazwisko | 13 | 13 | 0 | 0 | 1.000 |  |
| pelnomocnicy.pesel | 13 | 13 | 0 | 0 | 1.000 |  |
| przelew_bankowy.data_operacji | 8 | 8 | 0 | 0 | 1.000 |  |
| przelew_bankowy.kwota | 8 | 6 | 0 | 2 | 0.857 | rejected_not_in_text 2 |
| przelew_bankowy.na_rachunek | 8 | 8 | 0 | 0 | 1.000 |  |
| przelew_bankowy.numer_transakcji | 8 | 7 | 1 | 0 | 0.933 | in_text 1 |
| przelew_bankowy.tytul | 8 | 6 | 2 | 2 | 0.750 | in_text 2 |
| przelew_bankowy.z_rachunku | 8 | 8 | 0 | 0 | 1.000 |  |

## Najsłabsze dokumenty

| dokument | typ | F1 | wywołania |
|---|---|---|---|
| skany__potwierdzenia__0001 | przelew→przelew | 0.7273 | {"main": "ok"} |
| skany__potwierdzenia__0003 | przelew→przelew | 0.8 | {"main": "ok"} |
| skany__potwierdzenia__0002 | przelew→przelew | 0.8333 | {"main": "ok"} |
| skany__odwolania__0002 | odwolanie→odwolanie | 0.9767 | {"strony": "ok", "postepowanie": "ok", "zarzut": "ok"} |
| przyklad_01__pelnomocnictwo | pelnomocnictwo→pelnomocnictwo | 1.0 | {"main": "ok"} |
| przyklad_01__przelew | przelew→przelew | 1.0 | {"main": "ok"} |
| przyklad_01__odwolanie | odwolanie→odwolanie | 1.0 | {"strony": "ok", "postepowanie": "ok", "zarzut": "ok"} |
| przyklad_02__pelnomocnictwo | pelnomocnictwo→pelnomocnictwo | 1.0 | {"main": "ok"} |
| przyklad_02__przelew | przelew→przelew | 1.0 | {"main": "ok"} |
| przyklad_02__odwolanie | odwolanie→odwolanie | 1.0 | {"strony": "ok", "postepowanie": "ok", "zarzut": "ok"} |
