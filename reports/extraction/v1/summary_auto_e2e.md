# Ekstrakcja — F1 (tekst `auto`, LLM `bielik-11b-v3.1`, zestaw `all`, klasyfikacja tak)

Dokumentów: 227, czas: 536 s. Błędy wywołań LLM: 0.

| miara | precision | recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| **micro (null/null = TP)** | 0.9934 | 0.9904 | **0.9919** | 2693 | 18 | 26 |
| tylko wartości niepuste | 0.9923 | 0.9890 | 0.9907 | | | |

## Per typ i zestaw

| typ | zestaw | dok. | P | R | F1 |
|---|---|---|---|---|---|
| brak | K | 3 | 1.000 | 1.000 | 1.000 |
| brak | S | 14 | 1.000 | 1.000 | 1.000 |
| odwolanie | K | 10 | 0.991 | 0.982 | 0.987 |
| odwolanie | S | 60 | 0.997 | 0.993 | 0.995 |
| pelnomocnictwo | K | 10 | 0.981 | 0.990 | 0.985 |
| pelnomocnictwo | S | 60 | 1.000 | 0.997 | 0.998 |
| przelew | K | 10 | 0.933 | 0.933 | 0.933 |
| przelew | S | 60 | 0.983 | 0.983 | 0.983 |

## Per pole

| pole | n | TP | FP | FN | F1 | błędy: decyzje |
|---|---|---|---|---|---|---|
| (dokument negatywny) | 17 | 17 | 0 | 0 | 1.000 |  |
| OdwolanieKIO.czynnosc_dzien | 70 | 70 | 0 | 0 | 1.000 |  |
| OdwolanieKIO.czynnosc_opis | 70 | 68 | 2 | 2 | 0.971 | derived 2 |
| OdwolanieKIO.czynnosc_powod_id | 70 | 68 | 2 | 2 | 0.971 | inferred 2 |
| OdwolanieKIO.data | 70 | 70 | 0 | 0 | 1.000 |  |
| OdwolanieKIO.miejscowosc | 70 | 70 | 0 | 0 | 1.000 |  |
| Odwolujacy.krs | 70 | 70 | 0 | 0 | 1.000 |  |
| Odwolujacy.nazwa | 70 | 70 | 0 | 0 | 1.000 |  |
| Odwolujacy.nip | 70 | 70 | 0 | 0 | 1.000 |  |
| Odwolujacy.pelnomocnik.imie_nazwisko | 70 | 70 | 0 | 0 | 1.000 |  |
| Odwolujacy.pelnomocnik.mail | 70 | 67 | 1 | 3 | 0.971 | unparsable 2, agree 1 |
| Odwolujacy.pelnomocnik.nazwa | 70 | 69 | 1 | 1 | 0.986 | in_text 1 |
| Odwolujacy.przez-pelnomocnika | 70 | 70 | 0 | 0 | 1.000 |  |
| Odwolujacy.regon | 70 | 70 | 0 | 0 | 1.000 |  |
| Zamawiajacy.krs | 73 | 73 | 0 | 0 | 1.000 |  |
| Zamawiajacy.nazwa | 74 | 73 | 0 | 1 | 0.993 | in_text 1 |
| Zamawiajacy.nip | 74 | 73 | 0 | 1 | 0.993 | agree 1 |
| Zamawiajacy.prowadzacy_postepowanie | 74 | 72 | 0 | 2 | 0.986 | inferred 1, ? 1 |
| Zamawiajacy.regon | 74 | 73 | 0 | 1 | 0.993 | agree 1 |
| ZamowieniePubliczne.numer_bzp | 70 | 70 | 0 | 0 | 1.000 |  |
| ZamowieniePubliczne.numer_postepowania | 70 | 70 | 0 | 0 | 1.000 |  |
| ZamowieniePubliczne.numer_ted | 70 | 70 | 0 | 0 | 1.000 |  |
| ZamowieniePubliczne.tytul | 70 | 70 | 0 | 0 | 1.000 |  |
| mocodawca.data.imie_nazwisko | 77 | 77 | 0 | 0 | 1.000 |  |
| mocodawca.data.krs | 77 | 77 | 0 | 0 | 1.000 |  |
| mocodawca.data.nazwa | 77 | 75 | 2 | 1 | 0.980 | in_text 2 |
| mocodawca.data.nip | 77 | 77 | 0 | 0 | 1.000 |  |
| mocodawca.data.typ | 77 | 77 | 0 | 0 | 1.000 |  |
| mocodawca.podpisujacy.imie_nazwisko | 109 | 107 | 0 | 2 | 0.991 | ? 2 |
| pelnomocnicy.imie_nazwisko | 115 | 115 | 0 | 0 | 1.000 |  |
| pelnomocnicy.pesel | 115 | 115 | 0 | 0 | 1.000 |  |
| przelew_bankowy.data_operacji | 70 | 70 | 0 | 0 | 1.000 |  |
| przelew_bankowy.kwota | 70 | 70 | 0 | 0 | 1.000 |  |
| przelew_bankowy.na_rachunek | 70 | 70 | 0 | 0 | 1.000 |  |
| przelew_bankowy.numer_transakcji | 70 | 70 | 0 | 0 | 1.000 |  |
| przelew_bankowy.tytul | 70 | 61 | 9 | 9 | 0.871 | in_text 9 |
| przelew_bankowy.z_rachunku | 70 | 69 | 1 | 1 | 0.986 | agree 1 |

## Najsłabsze dokumenty

| dokument | typ | F1 | wywołania |
|---|---|---|---|
| przyklad_15__potwierdzenie_przelewu | przelew→przelew | 0.8333 | {"main": "ok"} |
| przyklad_18__potwierdzenie_przelewu | przelew→przelew | 0.8333 | {"main": "ok"} |
| przyklad_22__potwierdzenie_przelewu | przelew→przelew | 0.8333 | {"main": "ok"} |
| przyklad_31__potwierdzenie_przelewu | przelew→przelew | 0.8333 | {"main": "ok"} |
| przyklad_32__potwierdzenie_przelewu | przelew→przelew | 0.8333 | {"main": "ok"} |
| przyklad_39__potwierdzenie_przelewu | przelew→przelew | 0.8333 | {"main": "ok"} |
| skany__potwierdzenia__0004 | przelew→przelew | 0.8333 | {"main": "ok"} |
| skany__potwierdzenia__0006 | przelew→przelew | 0.8333 | {"main": "ok"} |
| skany__potwierdzenia__0007 | przelew→przelew | 0.8333 | {"main": "ok"} |
| skany__potwierdzenia__0008 | przelew→przelew | 0.8333 | {"main": "ok"} |
