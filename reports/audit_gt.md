# Audyt GT względem schematów (krok 3)

Dokumenty z GT: 210 (S: 180, skany K: 30), wartości ≠ null: 2341. Tekst: warstwa tekstowa / OCR (konfiguracja z kroku 1), pierwsze `pages` stron typu.

Wyniki: `verbatim` = dosłownie w tekście; `normalized` = przez kandydatów i normalizatory pola; `odmiana` = imię/nazwisko w innej formie; `fuzzy` = z błędem OCR; `absent` = brak; `inferred` = pole wnioskowane.

## Zestaw S

| pole | x-source | n | verbatim | normalized | odmiana | fuzzy | absent | inferred | kandydaci: GT wśród | GT = nr 1 |
|---|---|---|---|---|---|---|---|---|---|---|
| OdwolanieKIO.czynnosc_dzien | inferred | 60 | 0 | 60 | 0 | 0 | 0 | 0 | 60/60 | 0/60 |
| OdwolanieKIO.czynnosc_opis | derived | 60 | 0 | 0 | 0 | 0 | 0 | 60 | — | — |
| OdwolanieKIO.czynnosc_powod_id | inferred | 60 | 0 | 0 | 0 | 0 | 0 | 60 | — | — |
| OdwolanieKIO.data | normalized | 45 | 0 | 45 | 0 | 0 | 0 | 0 | 45/45 | 45/45 |
| OdwolanieKIO.miejscowosc | verbatim | 45 | 45 | 0 | 0 | 0 | 0 | 0 | 45/45 | 45/45 |
| Odwolujacy.krs | verbatim | 56 | 56 | 0 | 0 | 0 | 0 | 0 | 56/56 | 36/56 |
| Odwolujacy.nazwa | verbatim | 60 | 60 | 0 | 0 | 0 | 0 | 0 | — | — |
| Odwolujacy.nip | normalized | 60 | 60 | 0 | 0 | 0 | 0 | 0 | 60/60 | 34/60 |
| Odwolujacy.pelnomocnik.imie_nazwisko | normalized | 60 | 60 | 0 | 0 | 0 | 0 | 0 | — | — |
| Odwolujacy.pelnomocnik.mail | verbatim | 60 | 60 | 0 | 0 | 0 | 0 | 0 | 60/60 | 34/60 |
| Odwolujacy.pelnomocnik.nazwa | verbatim | 60 | 60 | 0 | 0 | 0 | 0 | 0 | — | — |
| Odwolujacy.przez-pelnomocnika | inferred | 60 | 0 | 0 | 0 | 0 | 0 | 60 | — | — |
| Odwolujacy.regon | normalized | 60 | 60 | 0 | 0 | 0 | 0 | 0 | 60/60 | 34/60 |
| Zamawiajacy.krs | verbatim | 58 | 58 | 0 | 0 | 0 | 0 | 0 | 58/58 | 23/58 |
| Zamawiajacy.nazwa | verbatim | 63 | 63 | 0 | 0 | 0 | 0 | 0 | — | — |
| Zamawiajacy.nip | normalized | 63 | 63 | 0 | 0 | 0 | 0 | 0 | 63/63 | 26/63 |
| Zamawiajacy.prowadzacy_postepowanie | inferred | 6 | 0 | 0 | 0 | 0 | 0 | 6 | — | — |
| Zamawiajacy.regon | normalized | 63 | 63 | 0 | 0 | 0 | 0 | 0 | 63/63 | 26/63 |
| ZamowieniePubliczne.numer_bzp | normalized | 48 | 33 | 15 | 0 | 0 | 0 | 0 | 48/48 | 48/48 |
| ZamowieniePubliczne.numer_postepowania | verbatim | 60 | 60 | 0 | 0 | 0 | 0 | 0 | 60/60 | 60/60 |
| ZamowieniePubliczne.numer_ted | normalized | 47 | 14 | 33 | 0 | 0 | 0 | 0 | 47/47 | 47/47 |
| ZamowieniePubliczne.tytul | verbatim | 60 | 56 | 0 | 0 | 4 | 0 | 0 | 56/60 | 56/60 |
| mocodawca.data.imie_nazwisko | normalized | 4 | 4 | 0 | 0 | 0 | 0 | 0 | — | — |
| mocodawca.data.krs | verbatim | 62 | 62 | 0 | 0 | 0 | 0 | 0 | 62/62 | 56/62 |
| mocodawca.data.nazwa | verbatim | 66 | 66 | 0 | 0 | 0 | 0 | 0 | — | — |
| mocodawca.data.nip | normalized | 66 | 66 | 0 | 0 | 0 | 0 | 0 | 66/66 | 60/66 |
| mocodawca.data.typ | inferred | 66 | 0 | 0 | 0 | 0 | 0 | 66 | — | — |
| mocodawca.podpisujacy.imie_nazwisko | normalized | 95 | 95 | 0 | 0 | 0 | 0 | 0 | — | — |
| pelnomocnicy.imie_nazwisko | normalized | 98 | 98 | 0 | 0 | 0 | 0 | 0 | — | — |
| pelnomocnicy.pesel | verbatim | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1/1 | 1/1 |
| przelew_bankowy.data_operacji | normalized | 60 | 13 | 43 | 0 | 0 | 4 | 0 | 55/55 | 55/55 |
| przelew_bankowy.kwota | normalized | 60 | 0 | 50 | 0 | 7 | 3 | 0 | 50/52 | 50/52 |
| przelew_bankowy.na_rachunek | normalized | 60 | 24 | 33 | 0 | 0 | 3 | 0 | 54/54 | 54/54 |
| przelew_bankowy.numer_transakcji | verbatim | 60 | 60 | 0 | 0 | 0 | 0 | 0 | 51/52 | 51/52 |
| przelew_bankowy.tytul | verbatim | 60 | 60 | 0 | 0 | 0 | 0 | 0 | 0/60 | 0/60 |
| przelew_bankowy.z_rachunku | normalized | 60 | 24 | 33 | 0 | 0 | 3 | 0 | 54/54 | 54/54 |

## Zestaw K

| pole | x-source | n | verbatim | normalized | odmiana | fuzzy | absent | inferred | kandydaci: GT wśród | GT = nr 1 |
|---|---|---|---|---|---|---|---|---|---|---|
| OdwolanieKIO.czynnosc_dzien | inferred | 10 | 0 | 10 | 0 | 0 | 0 | 0 | 10/10 | 0/10 |
| OdwolanieKIO.czynnosc_opis | derived | 10 | 0 | 0 | 0 | 0 | 0 | 10 | — | — |
| OdwolanieKIO.czynnosc_powod_id | inferred | 10 | 0 | 0 | 0 | 0 | 0 | 10 | — | — |
| OdwolanieKIO.data | normalized | 10 | 0 | 10 | 0 | 0 | 0 | 0 | 10/10 | 10/10 |
| OdwolanieKIO.miejscowosc | verbatim | 10 | 10 | 0 | 0 | 0 | 0 | 0 | 10/10 | 10/10 |
| Odwolujacy.krs | verbatim | 8 | 8 | 0 | 0 | 0 | 0 | 0 | 8/8 | 8/8 |
| Odwolujacy.nazwa | verbatim | 10 | 7 | 0 | 0 | 3 | 0 | 0 | — | — |
| Odwolujacy.nip | normalized | 10 | 4 | 6 | 0 | 0 | 0 | 0 | 10/10 | 10/10 |
| Odwolujacy.pelnomocnik.imie_nazwisko | normalized | 9 | 9 | 0 | 0 | 0 | 0 | 0 | — | — |
| Odwolujacy.pelnomocnik.mail | verbatim | 9 | 0 | 4 | 0 | 3 | 2 | 0 | 4/9 | 4/9 |
| Odwolujacy.pelnomocnik.nazwa | verbatim | 9 | 8 | 0 | 0 | 1 | 0 | 0 | — | — |
| Odwolujacy.przez-pelnomocnika | inferred | 10 | 0 | 0 | 0 | 0 | 0 | 10 | — | — |
| Odwolujacy.regon | normalized | 6 | 6 | 0 | 0 | 0 | 0 | 0 | 6/6 | 6/6 |
| Zamawiajacy.nazwa | verbatim | 11 | 11 | 0 | 0 | 0 | 0 | 0 | — | — |
| Zamawiajacy.nip | normalized | 8 | 4 | 4 | 0 | 0 | 0 | 0 | 8/8 | 0/8 |
| Zamawiajacy.prowadzacy_postepowanie | inferred | 2 | 0 | 0 | 0 | 0 | 0 | 2 | — | — |
| Zamawiajacy.regon | normalized | 3 | 3 | 0 | 0 | 0 | 0 | 0 | 3/3 | 1/3 |
| ZamowieniePubliczne.numer_bzp | normalized | 5 | 0 | 5 | 0 | 0 | 0 | 0 | 5/5 | 5/5 |
| ZamowieniePubliczne.numer_postepowania | verbatim | 10 | 10 | 0 | 0 | 0 | 0 | 0 | 10/10 | 10/10 |
| ZamowieniePubliczne.numer_ted | normalized | 7 | 4 | 3 | 0 | 0 | 0 | 0 | 7/7 | 7/7 |
| ZamowieniePubliczne.tytul | verbatim | 10 | 8 | 0 | 0 | 2 | 0 | 0 | 8/10 | 8/10 |
| mocodawca.data.imie_nazwisko | normalized | 1 | 1 | 0 | 0 | 0 | 0 | 0 | — | — |
| mocodawca.data.krs | verbatim | 10 | 10 | 0 | 0 | 0 | 0 | 0 | 10/10 | 9/10 |
| mocodawca.data.nazwa | verbatim | 10 | 8 | 0 | 0 | 2 | 0 | 0 | — | — |
| mocodawca.data.nip | normalized | 11 | 4 | 7 | 0 | 0 | 0 | 0 | 11/11 | 10/11 |
| mocodawca.data.typ | inferred | 11 | 0 | 0 | 0 | 0 | 0 | 11 | — | — |
| mocodawca.podpisujacy.imie_nazwisko | normalized | 14 | 14 | 0 | 0 | 0 | 0 | 0 | — | — |
| pelnomocnicy.imie_nazwisko | normalized | 17 | 17 | 0 | 0 | 0 | 0 | 0 | — | — |
| pelnomocnicy.pesel | verbatim | 4 | 4 | 0 | 0 | 0 | 0 | 0 | 4/4 | 3/4 |
| przelew_bankowy.data_operacji | normalized | 10 | 6 | 3 | 0 | 0 | 1 | 0 | 9/9 | 9/9 |
| przelew_bankowy.kwota | normalized | 10 | 0 | 9 | 0 | 1 | 0 | 0 | 9/9 | 9/9 |
| przelew_bankowy.na_rachunek | normalized | 10 | 2 | 5 | 0 | 0 | 3 | 0 | 7/7 | 7/7 |
| przelew_bankowy.numer_transakcji | verbatim | 4 | 4 | 0 | 0 | 0 | 0 | 0 | 2/2 | 2/2 |
| przelew_bankowy.tytul | verbatim | 10 | 8 | 0 | 0 | 2 | 0 | 0 | 0/10 | 0/10 |
| przelew_bankowy.z_rachunku | normalized | 10 | 0 | 6 | 0 | 0 | 4 | 0 | 6/7 | 6/7 |

## Zgodność x-source z danymi

| pole | obserwacja | liczba |
|---|---|---|
| mocodawca.data.nip | normalized → występuje dosłownie (normalizacja nie zmienia wartości) | 70 |
| Zamawiajacy.nip | normalized → występuje dosłownie (normalizacja nie zmienia wartości) | 67 |
| Odwolujacy.regon | normalized → występuje dosłownie (normalizacja nie zmienia wartości) | 66 |
| Zamawiajacy.regon | normalized → występuje dosłownie (normalizacja nie zmienia wartości) | 66 |
| Odwolujacy.nip | normalized → występuje dosłownie (normalizacja nie zmienia wartości) | 64 |
| ZamowieniePubliczne.numer_bzp | normalized → występuje dosłownie (normalizacja nie zmienia wartości) | 33 |
| przelew_bankowy.na_rachunek | normalized → występuje dosłownie (normalizacja nie zmienia wartości) | 26 |
| przelew_bankowy.z_rachunku | normalized → występuje dosłownie (normalizacja nie zmienia wartości) | 24 |
| przelew_bankowy.data_operacji | normalized → występuje dosłownie (normalizacja nie zmienia wartości) | 19 |
| ZamowieniePubliczne.numer_ted | normalized → występuje dosłownie (normalizacja nie zmienia wartości) | 18 |
| Odwolujacy.pelnomocnik.mail | verbatim → znajdowane tylko po normalizacji | 4 |

## Sumy kontrolne w GT

| pole | poprawne | wszystkie |
|---|---|---|
| nip | 144 (66%) | 218 |
| pesel | 5 (100%) | 5 |
| regon | 94 (71%) | 132 |

## Prefiks PL rachunków: dokument vs GT

| PL w dokumencie | PL w GT | liczba |
|---|---|---|
| False | False | 42 |
| True | False | 96 |
| True | True | 2 |

## Wartości absent / fuzzy (48)

| dokument | pole | wartość GT | wynik | najbliższy fragment | podob. |
|---|---|---|---|---|---|
| przyklad_05__potwierdzenie_przelewu | przelew_bankowy.kwota | 17.0 | fuzzy | 17.0 | 100.0 |
| przyklad_12__potwierdzenie_przelewu | przelew_bankowy.data_operacji | 2026-07-09 | absent | 09-07-2026 | 60.0 |
| przyklad_12__potwierdzenie_przelewu | przelew_bankowy.kwota | 200.0 | fuzzy | 200.0 | 100.0 |
| przyklad_13__potwierdzenie_przelewu | przelew_bankowy.kwota | 50.0 | fuzzy | 50.0 | 100.0 |
| przyklad_15__potwierdzenie_przelewu | przelew_bankowy.kwota | 200.0 | fuzzy | 200.0 | 100.0 |
| przyklad_16__potwierdzenie_przelewu | przelew_bankowy.na_rachunek | 03712918442654893065427654 | absent | 129 1844 2654 8930 6542 76 | 80.8 |
| przyklad_16__potwierdzenie_przelewu | przelew_bankowy.z_rachunku | 33880525177402263989269409 | absent | 8805 2517 7402 2639 8926 9 | 80.8 |
| przyklad_19__potwierdzenie_przelewu | przelew_bankowy.data_operacji | 2026-04-26 | absent | 2026 CEN26 | 60.0 |
| przyklad_19__potwierdzenie_przelewu | przelew_bankowy.kwota | 100.0 | absent | 100,0 | 80.0 |
| przyklad_22__potwierdzenie_przelewu | przelew_bankowy.kwota | 17.0 | fuzzy | 17.0 | 100.0 |
| przyklad_23__potwierdzenie_przelewu | przelew_bankowy.na_rachunek | 31263692113897855587588527 | absent | 636 9211 3897 8555 8758 85 | 80.8 |
| przyklad_23__potwierdzenie_przelewu | przelew_bankowy.z_rachunku | 40507561379331317832598717 | absent | 075 6137 9331 3178 3259 87 | 80.8 |
| przyklad_26__potwierdzenie_przelewu | przelew_bankowy.data_operacji | 2026-06-07 | absent | 2026 CEN26 | 50.0 |
| przyklad_26__potwierdzenie_przelewu | przelew_bankowy.kwota | 34.0 | absent | 4.20 | 75.0 |
| przyklad_30__potwierdzenie_przelewu | przelew_bankowy.kwota | 34.0 | fuzzy | 34.0 | 100.0 |
| przyklad_31__potwierdzenie_przelewu | przelew_bankowy.kwota | 34.0 | fuzzy | 34.0 | 100.0 |
| przyklad_33__potwierdzenie_przelewu | przelew_bankowy.data_operacji | 2026-01-13 | absent | 26 CEN2601 | 50.0 |
| przyklad_33__potwierdzenie_przelewu | przelew_bankowy.kwota | 17.0 | absent | 1.20 | 75.0 |
| przyklad_37__potwierdzenie_przelewu | przelew_bankowy.na_rachunek | 85616619736856673630824436 | absent | 66 1973 6856 6736 3082 443 | 80.8 |
| przyklad_37__potwierdzenie_przelewu | przelew_bankowy.z_rachunku | 84576152426782305022174406 | absent | 5761 5242 6782 3050 2217 4 | 80.8 |
| przyklad_42__odwolanie | ZamowieniePubliczne.tytul | Kompleksowe usługi utrzymania czystości, ochrony fizycznej i | fuzzy | Kompleksowe usługi utrzymania czystości, ochrony fizycznej i obsługi t | 99.2 |
| przyklad_46__odwolanie | ZamowieniePubliczne.tytul | Usługa ochrony osób i mienia w obiektach Zamawiającego w lat | fuzzy | Usługa ochrony osób i mienia w obiektach Zamawiającego w latach 2026-2 | 98.6 |
| przyklad_53__odwolanie | ZamowieniePubliczne.tytul | Usługa ochrony osób i mienia w obiektach Zamawiającego w lat | fuzzy | Usługa ochrony osób i mienia w obiektach Zamawiającego w latach 2026-2 | 98.6 |
| przyklad_60__odwolanie | ZamowieniePubliczne.tytul | Prowadzenie Punktu Selektywnej Zbiórki Odpadów Komunalnych w | fuzzy | Prowadzenie Punktu Selektywnej Zbiórki Odpadów Komunalnych w latach 20 | 98.7 |
| skany__odwolania__0001 | Odwolujacy[0].pelnomocnik.mail | a.rybak@rybak-kancelaria.example | fuzzy | a.rybakGrybak-kancelaria.example | 96.9 |
| skany__odwolania__0001 | ZamowieniePubliczne.tytul | Odbiór i zagospodarowanie odpadów komunalnych z nieruchomośc | fuzzy | Odbiór i zagospodarowanie odpadów kómunalnych z nieruchomości zamieszk | 98.7 |
| skany__odwolania__0002 | Odwolujacy[0].pelnomocnik.mail | m.wierzbicki@wierzbicki-kancelaria.example | absent | erzbickiowierzbicki- kancelar aria.example | 88.1 |
| skany__odwolania__0004 | Odwolujacy[0].pelnomocnik.mail | k.jodlowski@jodlowski-kancelaria.example | absent | l: k.j wski(Qjodlowski-kancelaria.exam Z | 80.0 |
| skany__odwolania__0006 | Odwolujacy[0].nazwa | Nordenix Automatyka Sp. z o.o. | fuzzy | Nordenix Automatyka Sp. z 0.0. | 93.3 |
| skany__odwolania__0006 | Odwolujacy[0].pelnomocnik.nazwa | Kancelaria Prawna Olszewski & Partnerzy sp. k. | fuzzy | KANCELARIA PRAWNA OLSZEWSKI £ PARTNERZY SP. K. | 97.8 |
| skany__odwolania__0007 | Odwolujacy[0].pelnomocnik.mail | d.kubiak@kubiak-kancelaria.example | fuzzy | d.kubiak(Okubiak-kancelaria.exampl | 94.1 |
| skany__odwolania__0008 | Odwolujacy[0].nazwa | Orbisol Budownictwo Sp. z o.o. | fuzzy | Orbisol Budownictwo Sp. z 0.0. | 93.3 |
| skany__odwolania__0009 | Odwolujacy[0].nazwa | Asterion Drogi i Mosty Sp. z o.o. | fuzzy | Asterion Drogi i Mosty Sp. z 0.0. | 93.9 |
| skany__odwolania__0010 | Odwolujacy[0].pelnomocnik.mail | a.wrobel@wrobel-kancelaria.example | fuzzy | a.wrobelOwrobel-kancelaria.example | 97.1 |
| skany__odwolania__0010 | ZamowieniePubliczne.tytul | Dostawa energii elektrycznej do obiektów Zamawiającego w lat | fuzzy | ostawa energii elektrycznej | do obiektów Zamawiającego w latach 2027- | 97.3 |
| skany__pelnomocnictwa__0006 | mocodawca[0].data.nazwa | Nordenix Automatyka Sp. z o.o. | fuzzy |  Nordenix Automatyka Sp.z o.o. | 96.7 |
| skany__pelnomocnictwa__0008 | mocodawca[0].data.nazwa | Orbisol Budownictwo Sp. z o.o. | fuzzy | Orbisol Budownictwo Sp. z 0.0. | 93.3 |
| skany__potwierdzenia__0001 | przelew_bankowy.na_rachunek | 60101010100081362231000000 | absent | 60 1010 1010 0081 3622 310 | 80.8 |
| skany__potwierdzenia__0001 | przelew_bankowy.z_rachunku | PL62217000089152501756617062 | absent | PL62 2170 0008 9152 5017 566 | 82.1 |
| skany__potwierdzenia__0004 | przelew_bankowy.tytul | OPŁATA SKARBOWA OD PEŁNOMOCNICTWA DLA RADCA PRAWNY KRZYSZTOF | fuzzy | PŁATA SKARBOWA OD PEŁNOMOCNICTWA DLA RADCA PRAWNY KRZYSZTOF JODŁOWSKIW | 98.4 |
| skany__potwierdzenia__0006 | przelew_bankowy.na_rachunek | 61103015081403045696356736 | absent | 1 1030 1508 1403 0456 9635 | 80.8 |
| skany__potwierdzenia__0006 | przelew_bankowy.z_rachunku | PL75217000080889261999999470 | absent | PL75 2170 0008 0889 2619 999 | 82.1 |
| skany__potwierdzenia__0007 | przelew_bankowy.z_rachunku | 66109010980387304538982666 | absent | 090 1098 0367 3045 3898 26 | 76.9 |
| skany__potwierdzenia__0008 | przelew_bankowy.data_operacji | 2026-04-20 | absent | 2026.04.20 | 80.0 |
| skany__potwierdzenia__0008 | przelew_bankowy.kwota | 17.0 | fuzzy | 17.0 | 100.0 |
| skany__potwierdzenia__0008 | przelew_bankowy.na_rachunek | 25103015089486503556221675 | absent | 30 1508 9486 5035 5622 167 | 80.8 |
| skany__potwierdzenia__0008 | przelew_bankowy.tytul | opłata skarbowa od pełnomocnictwa dla adw. Rafał Malinowski  | fuzzy |  opłata skarbowa od pełnomocnectwa dia adw Rafał Maknowski w postępowa | 95.4 |
| skany__potwierdzenia__0008 | przelew_bankowy.z_rachunku | 11124011119078857050000455 | absent | 1240 1111 9078 8570 5000 0 | 80.8 |
