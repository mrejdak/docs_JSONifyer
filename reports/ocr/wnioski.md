## Wnioski (stan na 2026-11-21, wersja robocza)

> Ręcznie pisane podsumowanie. Szczegółowe tabele poniżej są generowane automatycznie.
> Status: zrobione A1–A10, B1, B2, czysty pomiar czasu, porównanie z OCRmyPDF.
> Nie zrobione (świadomie odłożone): A9 user-words/user-patterns i drugi przebieg z whitelistą cyfr, B3 ręczna referencja skanów.

### Rekomendowana konfiguracja OCR (decyzja kroku 1)

**Render PyMuPDF 200 dpi (skala szarości) → preprocessing `deskew + noleader` → Tesseract 5.5 `tessdata_best/pol`, `--oem 1 --psm 3` → TSV → linearyzacja „wiersze wizualne”.**

| Element | Dlaczego |
|---|---|
| 200 dpi | lepsze niż 300 dpi na każdym zestawie; skany i tak mają 200 dpi |
| `tessdata_best` | niższy CER niż `pol` standardowy na S, lepsza przeżywalność pól na skanach; koszt ~2× czasu (~1,5 s/str.) |
| `psm 3` | najlepszy na skanach (tytuły, dwie kolumny); `psm 6` miesza kolumny (tytuły na skanach 40–60% L0 vs 65–80%) |
| `deskew` (własny, profil projekcji, ±3° → w aplikacji ±5°) | skany: L0 90,2% → **92,5%**, tytuły 65% → 80%, **bez psucia cyfr** (w przeciwieństwie do `--deskew` OCRmyPDF); degradacje z obrotem: +1,4 pp |
| `noleader` (usuwanie kropek do podpisu) | S: tokeny pól gubione przez psm 3 **62 → 4**, CER 0,30% → 0,24%; na skanach neutralny |
| bez binaryzacji | Otsu nic nie daje, adaptacyjna wyraźnie szkodzi (L0 81%); mediana (`denoise`) szkodzi identyfikatorom |

Wynik konfiguracji rekomendowanej:

| Zestaw | CER | tokeny pól pominięte | pola L0 | pola ≤ L2 |
|---|---|---|---|---|
| S pełny (427 str., 1780 pól) | **0,24%** (bez preproc.: 0,30%) | **4** (bez: 62) | **94,55%** (bez: 94,27%) | 100% |
| K skany (266 pól) | — | — | **92,5%** (bez: 90,2%) | 99,6% |
| D `real` (296 pól) | 0,50% (bez: 0,86%) | — | 93,9% (bez: 92,6%) | 100% |

Pozostałe 4 tokeny gubione na S: podpisy obok ramki „miejsce na pieczęć firmową” (psm 3 i psm 6) — kandydat na kolejną operację preprocessingu (usuwanie ramek/długich linii) albo na podwójny OCR tylko bloku podpisów; do decyzji w kroku 4 na podstawie F1 pól podpisujących.

### Preprocessing skanów (B2) — skany K, 266 pól, 200 dpi, model `best`

| Preprocessing | psm | L0 | L0+L1 | ≤ L2 | L3 | identyfikatory | rachunki | nazwy | tytuły |
|---|---|---|---|---|---|---|---|---|---|
| **deskew** (+ noleader — identycznie) | 3 | **92,5%** | **93,2%** | 99,6% | 0,4% | 100% | 95% | 85% | **80%** |
| otsu | 3 | 91,3% | 91,7% | 100% | 0% | 100% | 95% | 87,5% | 70% |
| deskew | 6 | 91,0% | 91,3% | 100% | 0% | 98,3% | 100% | 85% | 60% |
| brak / noleader | 3 | 90,2% | 92,9% | 100% | 0% | 100% | 95% | 80% | 65% |
| denoise + deskew | 3 | 89,8% | 90,2% | 97,0% | 3,0% | 93,3% | 95% | 90% | 65% |
| brak | 6 | 88,3% | 91,0% | 99,6% | 0,4% | 100% | 95% | 80% | 40% |
| adaptive | 3 | 81,2% | 84,6% | 96,6% | 3,4% | 93,3% | 90% | 70% | 35% |

(Pole L2 po deskew to tytuł przelewu skanu 0008 z odległością 5 — niższy próg L2 dla długich tytułów; jakościowo tytuł jest czytelny.)

### Degradacja syntetyczna (A10) — podzbiór 10 spraw, 66 stron, 296 pól, `d200 psm3 best`

| Degradacja | CER bez preproc. | CER `deskew+noleader` | L0 bez | L0 z | ≤ L2 |
|---|---|---|---|---|---|
| brak | 0,29% | **0,28%** | 93,6% | **94,9%** | 100% |
| obrót 1° (`rot1`) | 0,56% | 0,51% | 92,9% | **94,3%** | 100% |
| rozmycie σ=1 (`blur10`) | 0,43% | **0,25%** | 93,6% | 93,2% | 100% |
| szum σ=10 (`noise10`) | 0,50% | 0,49% | 94,3% | 94,3% | 100% |
| binaryzacja (`bin`) | 0,39% | **0,25%** | 92,9% | 93,6% | 100% |
| JPEG q=30 (`jpeg30`) | 0,47% | 0,45% | 93,9% | 94,3% | 100% |
| realistyczna (`real` = obrót 1° + rozmycie + JPEG + szum) | 0,86% | **0,50%** | 92,6% | 93,9% | 100% |
| ciężka (`real_bin` = obrót + rozmycie + binaryzacja + sól-pieprz) | 2,06% | **1,45%** | 82,4% | 86,5% | 99,7% |

- Kalibracja: wariant `real` (L0 92,6%) jest zbliżony do skanów K (L0 90,2%) → degradacja syntetyczna jest wiarygodnym przybliżeniem; `real_bin` to scenariusz pesymistyczny (słaby skan 1-bit).
- `deskew+noleader` nie szkodzi w żadnym wariancie i pomaga tam, gdzie jest obrót/rozmycie/binaryzacja.

### Liczby kluczowe

| Zestaw | Konfiguracja | CER | Przeżywalność pól: dokładnie (L0) | ≤ 1–2 edycje (L0–L2) | utracone (L3) |
|---|---|---|---|---|---|
| S — idealne rendery, 427 stron, 1780 pól | `d200_psm3_best` | 0,31% | 94,3% | 100% | 0% |
| | `d200_psm6_best` | 0,35% | 94,1% | 99,94% | 0,06% (1 pole) |
| | `d300_psm6_poleng` | 0,51% | **95,8%** | 99,94% | 0,06% |
| K — 30 skanów z GT, 266 pól | `d200_psm3_best` | — | **90,2%** | **100%** | **0%** |
| | `d200_psm6_best` | — | 88,3% | 99,6% | 0,4% |

- **Skany są istotnie trudniejsze niż rendery** (L0 90% vs 94–96%), ale przy tolerancji 1–2 edycji praktycznie każda wartość pola jest w tekście → ekstrakcja musi mieć dopasowanie tolerancyjne (krok 4, E6).
- Na skanach **identyfikatory (KRS/NIP/REGON), daty, kwoty, imiona i nazwiska, miejscowości: 100% L0**. Słabe są: e-maile (0% L0), nazwy z `Sp. z o.o.`, długie tytuły (kursywa, łamanie), rachunki (pojedyncze cyfry).
- **Czas** (czysty pomiar, 1 wątek): model `best` ~1,2–1,7 s/str., `std` ~0,6–0,8 s/str. Wielowątkowość Tesseracta nic nie daje → równoleglić strony w procesach. Sprawa (~6–10 stron) to ~10–15 s na jednym rdzeniu, kilka sekund przy stronach przetwarzanych równolegle na laptopie z i7.

### Systematyczne błędy OCR (do obsłużenia w krokach 2–4)

| Błąd | Przykład | Gdzie wystąpi | Obsługa |
|---|---|---|---|
| `@` → `Q`, `©`, `g`, `e`, `(`, `()`, `(a` | `biuroQpoczta.example` | **każdy e-mail** (S i K) | kandydat e-mail: `lokalna` + 1–3 dowolne znaki + `domena.tld` → odtworzenie `@` |
| `o` → `0` w formie prawnej | `Sp. z 0.0.`, `0.o.`, `o0.o0.` | nazwy podmiotów | normalizacja form prawnych (`sp. z o.o.`, `S.A.`, `sp. k.`, `sp. j.`) przed porównaniem/snapem |
| `§` → `8`, `$`, `S` | `$ 1. Mocodawca` | pełnomocnictwa (nagłówki) | sygnały klasyfikacji/sekcji: `[§$8S]\s*\d` |
| `&` → `8` | `Olszewski 8 Partnerzy` | nazwy kancelarii | tolerancja w dopasowaniu nazw |
| litera↔cyfra w identyfikatorach | `PLO2…`, `2026/5013-…`, `DI.578` → `Dl.578`, `0,00` → `O,OO` | rachunki, TED, numery postępowań, kwoty | mapa pomyłek (O→0, l/I→1, S→5) **tylko w kontekście cyfrowym** |
| wstawiona spacja / sklejenie | `2026/BZP009997 78`, `1)i2)wzw.zart.`, `2026r.` | numery, przepisy | wzorce z opcjonalnymi spacjami; porównanie po usunięciu spacji |
| **zgubione całe linie** | psm 3/4: nazwiska pod kropkami do podpisu (62 tokeny pól na S); psm 6: podpisy obok ramki „miejsce na pieczęć”, daty w lewej kolumnie tabel (5–9 tokenów) | blok podpisów (podpisujący, pełnomocnicy), tabele dat (czynnosc_dzien) | patrz decyzja OCR niżej |
| kolejność czytania | przelew: CER natywny 30% vs 0,3% w wierszach (synt.); na przekrzywionym skanie naiwne wiersze psuły komórki tabel | przelewy, dwukolumnowe nagłówki odwołań | linearyzacja „wiersze wizualne” z kontrolą przekrzywienia (`tools/ocr_bench/layout.py`) — do przeniesienia do aplikacji |
| pieczątki, wydruki | „WPŁYNĘŁO dnia 16.05.2026”, „Dokument wygenerowany w dniu …” | przelewy (skany) | dodatkowe daty-pułapki dla `data_operacji` → kandydaci z etykietą mają priorytet |

### OCRmyPDF + tekst z wynikowego PDF-a (porównanie silników)

Wariant: `ocrmypdf -l pol --rasterizer pypdfium --output-type pdf --tesseract-oem 1 --tesseract-pagesegmode N` (ten sam Tesseract 5.5, model `best`), potem słowa z warstwy tekstowej przez PyMuPDF i ta sama linearyzacja wierszy. Działa bez Ghostscripta.

**Skany K (266 pól, psm 3):**

| Konfiguracja | L0 | L0+L1 | ≤ L2 | L3 | identyfikatory L0 | rachunki L0 | tytuły L0 | nazwy L0 |
|---|---|---|---|---|---|---|---|---|
| Tesseract bezpośrednio, 200 dpi (`d200_psm3_best`) | **90,2%** | **92,9%** | **100%** | **0%** | **100%** | **95%** | 65% | 80% |
| OCRmyPDF bez opcji | 89,5% | 91,7% | 99,3% | 0,7% | 100% | 90% | 50% | 85% |
| OCRmyPDF `--deskew` | 89,5% | 90,2% | 99,6% | 0,4% | 96,7% | 80% | **75%** | 85% |
| OCRmyPDF `--deskew --rotate-pages` | 89,5% | 90,2% | 99,6% | 0,4% | 96,7% | 80% | 75% | 85% |
| OCRmyPDF `--deskew` + Sauvola | 90,2% | 90,2% | 98,5% | 1,5% | — | — | — | — |

- **Ogółem remis lub lekka przewaga bezpośredniego Tesseracta**; różnice to pojedyncze pola (1 pole = 0,38%).
- **`--deskew` w OCRmyPDF psuje cyfry**: NIP, rachunki, numer transakcji tracą pojedyncze cyfry (`60101010100…` → `60101010180…`, `…000000` → `…000d0`) — resampling obrotu na obrazach 1-bit/JPEG. Pomaga za to tytułom (kursywa, długie linie) i nazwom. Dla nas identyfikatory/rachunki są ważniejsze (dokładne pola, regex-walidowane).
- `--rotate-pages` nic nie zmienia (skany nie są obrócone o 90°/180°).
- OCRmyPDF **nie zwraca confidence** słów (warstwa tekstowa PDF go nie niesie) → tracimy sygnał `conf < 85` z A8; trzeba by dodatkowo czytać hOCR.
- Czas: przebieg przez OCRmyPDF ma narzut (start procesu, rasteryzacja, składanie PDF); pod tym samym obciążeniem równoległym mediana 12,9 s/str. vs 10,7 s/str. bezpośrednio (+20%), z `--deskew` +50%, z `--deskew --rotate-pages` +80%. (Pomiar pod obciążeniem — tylko względnie.)
- **Wniosek wstępny**: OCRmyPDF nie daje przewagi jakościowej nad bezpośrednim wywołaniem Tesseracta na naszym renderze 200 dpi, dokłada zależność (narzędzie CLI + pikepdf), narzut czasu i odbiera confidence. Wartość OCRmyPDF to głównie wygoda (PDF z warstwą tekstową, np. do podglądu w GUI). Deskew warto natomiast sprawdzić we własnym preprocessingu (B2, z kontrolą wpływu na cyfry).
**Zestaw S — podzbiór 10 spraw, wymuszony OCR (`--force-ocr`), te same 66 stron / 296 pól:**

| Konfiguracja | CER | WER | pominięte tokeny (w polach) | pola L0 | pola ≤ L2 |
|---|---|---|---|---|---|
| Tesseract bezpośrednio, `d200_psm3_best` | **0,29%** | 2,0% | 23 (7) | 93,6% | 100% |
| Tesseract bezpośrednio, `d200_psm6_best` | 0,40% | **1,8%** | 14 (**0**) | 93,6% | 100% |
| OCRmyPDF psm 3 | 0,72% | 3,5% | 16 (4) | 93,9% | 100% |
| OCRmyPDF psm 6 | 0,60% | 2,8% | 24 (0) | 93,9% | 100% |
| OCRmyPDF `--deskew` psm 3 | 0,68% | 3,4% | 15 (4) | 93,9% | 100% |
| OCRmyPDF `--deskew` psm 6 | 0,64% | 2,9% | 25 (0) | 93,6% | 100% |

- Przeżywalność pól praktycznie identyczna (±1 pole), ale **CER OCRmyPDF ~2× wyższy**: przy `--force-ocr` OCRmyPDF rasteryzuje strony wektorowe w **400 dpi** (3307×4677 px) i pojawiają się błędy typowe dla zbyt dużej rozdzielczości: `i`→`1` (37×), wielkość liter (`jest`→`Jest`), rozbite liczby (`011`→`01 1`). Na skanach używa natywnych 200 dpi — tam wyniki są porównywalne (tabela wyżej).
- W psm 3 OCRmyPDF gubi nieco mniej tokenów pól pod kropkami do podpisu (4 vs 7), ale problem pozostaje — `noleader` rozwiązuje go u źródła.
- W aplikacji cyfrowe PDF-y i tak czytamy z warstwy tekstowej (CER 0), więc wynik S dotyczy tylko jakości samego OCR.

**Decyzja: zostajemy przy bezpośrednim Tesseract (render PyMuPDF 200 dpi → TSV)** — równa lub lepsza jakość, kontrola dpi i preprocessingu, confidence słów, mniej zależności i krótszy czas. OCRmyPDF ewentualnie jako opcjonalny eksport „PDF z warstwą tekstową” (np. do GUI).

### Confidence (A8)
Tokeny z `conf ≥ 95`: 0,13% błędnych; `85–95`: ~2%; `70–85`: ~31%; `< 70`: 49–73%. **Próg 85** dobrze oddziela pewne od niepewnych → flaga `low_ocr_confidence` w kroku 4 i sygnał do tolerancyjnego dopasowania / drugiego przebiegu.

### Historia decyzji OCR
- Najpierw: `psm 3` najlepszy na skanach, ale gubił linie pod kropkami do podpisu; `psm 6` nie gubił podpisów, ale mieszał kolumny na skanach i gubił daty w tabelach.
- Rozwiązanie: `noleader` usuwa przyczynę u `psm 3` (62 → 4 tokeny), a `deskew` dodatkowo poprawia skany → patrz „Rekomendowana konfiguracja” na górze. Podwójny OCR `psm 3 + psm 6` pozostaje opcją awaryjną (≈2× czas).
- `pol+eng` przy 300 dpi daje najwyższe L0 na renderach (95,8%), ale gubi więcej tokenów i jest gorszy na skanach — nie wybieramy.

### Wymagania dla kroków 2–4 (wynikające z benchmarku)
1. Regexy z tolerancją: opcjonalne ogonki, opcjonalne spacje w numerach, `[§$8S]`, `[@QG©(]` w e-mailach.
2. Mapa pomyłek cyfra↔litera w polach cyfrowych (rachunki, KRS, NIP, REGON, PESEL, TED, BZP).
3. Weryfikacja obecności wartości w tekście: dopasowanie rozmyte (≤1 edycja do 12 znaków, ≤10% dłuższe), po normalizacji form prawnych.
4. Linearyzacja tekstu „wiersze wizualne” (etykieta | wartość w jednej linii) — wspólna dla warstwy tekstowej i OCR.
5. Flaga niepewności przy `conf < 85`.
6. Polityka stron: pola leżą na stronach 1–3 odwołania; daty czynności także w tabelach na str. 3 → OCR co najmniej 3–4 pierwszych stron odwołania.
