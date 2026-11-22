# Benchmark OCR — raport (krok 1)

Generowany przez `python -m tools.ocr_bench report`. Opis metod: `docs/01_ocr_tesseract.md`.

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


## 1. Dane

| zestaw | typ (z nazwy) | dokumenty | strony |
|---|---|---|---|
| K | brak | 3 | 7 |
| K | odwolanie | 11 | 59 |
| K | pelnomocnictwo | 10 | 10 |
| K | przelew | 10 | 10 |
| S | brak | 14 | 183 |
| S | odwolanie | 60 | 306 |
| S | pelnomocnictwo | 60 | 61 |
| S | przelew | 60 | 60 |

## 2. Ranking konfiguracji — zestaw S (idealne rendery), wspólne strony

CER mikro = suma błędów znakowych / suma znaków referencji. CER łagodny = bez wielkości liter i ogonków. CER natywny = kolejność linii Tesseracta zamiast wierszy wizualnych (różnica ⇒ problem układu). Pominięte = tokeny referencji, których OCR w ogóle nie zwrócił (np. zgubione linie pod kropkami do podpisu); „w polach” = należące do wartości pól GT. Czas: patrz §7 (pomiar pod obciążeniem równoległym).

| konfiguracja | strony | CER mikro | CER śr. | CER mediana | CER łagodny | CER natywny | WER | pominięte | pominięte w polach | s/stronę |
|---|---|---|---|---|---|---|---|---|---|---|
| d200_none_none__psm4_best | 66 | 0.0025 | 0.0075 | 0.0014 | 0.0074 | 0.0097 | 0.0192 | 17 | 7 | 11.55 |
| d200_none_none__psm3_best | 66 | 0.0029 | 0.0078 | 0.0015 | 0.0076 | 0.0171 | 0.0200 | 23 | 7 | 11.67 |
| d200_none_none__psm4_poleng | 66 | 0.0030 | 0.0092 | 0.0013 | 0.0089 | 0.0114 | 0.0227 | 17 | 7 | 5.21 |
| d200_none_none__psm3_poleng | 66 | 0.0034 | 0.0095 | 0.0014 | 0.0092 | 0.0187 | 0.0237 | 23 | 7 | 5.89 |
| d300_none_none__psm4_best | 66 | 0.0038 | 0.0112 | 0.0015 | 0.0110 | 0.0139 | 0.0252 | 17 | 7 | 13.24 |
| d200_none_none__psm4_std | 66 | 0.0039 | 0.0113 | 0.0014 | 0.0112 | 0.0135 | 0.0249 | 18 | 7 | 4.31 |
| d200_none_none__psm6_best | 66 | 0.0040 | 0.0086 | 0.0013 | 0.0084 | 0.0086 | 0.0181 | 14 | 0 | 10.39 |
| d200_none_none__psm3_std | 66 | 0.0043 | 0.0116 | 0.0016 | 0.0115 | 0.0209 | 0.0259 | 24 | 7 | 4.31 |
| d300_none_none__psm4_poleng | 66 | 0.0044 | 0.0128 | 0.0015 | 0.0126 | 0.0159 | 0.0306 | 18 | 7 | 8.32 |
| d300_none_none__psm3_best | 66 | 0.0049 | 0.0125 | 0.0018 | 0.0122 | 0.0218 | 0.0289 | 24 | 7 | 13.79 |
| d300_none_none__psm3_poleng | 66 | 0.0049 | 0.0132 | 0.0015 | 0.0130 | 0.0225 | 0.0319 | 24 | 7 | 7.77 |
| d300_none_none__psm6_poleng | 66 | 0.0050 | 0.0108 | 0.0008 | 0.0106 | 0.0108 | 0.0256 | 21 | 0 | 5.91 |
| d200_none_none__psm6_poleng | 66 | 0.0054 | 0.0131 | 0.0009 | 0.0129 | 0.0131 | 0.0254 | 14 | 0 | 5.33 |
| d300_none_none__psm6_best | 66 | 0.0058 | 0.0123 | 0.0013 | 0.0120 | 0.0123 | 0.0226 | 20 | 0 | 12.25 |
| d200_none_none__psm6_std | 66 | 0.0065 | 0.0162 | 0.0015 | 0.0161 | 0.0162 | 0.0218 | 15 | 0 | 3.83 |
| d300_none_none__psm4_std | 66 | 0.0070 | 0.0205 | 0.0017 | 0.0204 | 0.0232 | 0.0425 | 19 | 7 | 5.75 |
| d300_none_none__psm6_std | 66 | 0.0071 | 0.0166 | 0.0016 | 0.0165 | 0.0166 | 0.0253 | 22 | 0 | 4.64 |
| d300_none_none__psm3_std | 66 | 0.0075 | 0.0209 | 0.0019 | 0.0208 | 0.0302 | 0.0436 | 26 | 7 | 5.59 |
| d200_none_none__psm11_poleng | 66 | 0.0115 | 0.0138 | 0.0035 | 0.0135 | 0.0148 | 0.0339 | 83 | 0 | 5.31 |
| d200_none_none__psm11_best | 66 | 0.0119 | 0.0149 | 0.0038 | 0.0146 | 0.0158 | 0.0307 | 82 | 0 | 11.60 |
| d200_none_none__psm11_std | 66 | 0.0121 | 0.0152 | 0.0046 | 0.0151 | 0.0162 | 0.0248 | 84 | 0 | 4.18 |
| d300_none_none__psm11_std | 66 | 0.0212 | 0.0368 | 0.0071 | 0.0367 | 0.0401 | 0.0407 | 80 | 0 | 5.65 |
| d300_none_none__psm11_best | 66 | 0.0216 | 0.0382 | 0.0056 | 0.0378 | 0.0415 | 0.0431 | 78 | 0 | 12.81 |
| d300_none_none__psm11_poleng | 66 | 0.0220 | 0.0329 | 0.0070 | 0.0324 | 0.0362 | 0.0616 | 79 | 0 | 6.98 |

## 3. CER per typ dokumentu i strona (wszystkie strony danej konfiguracji)

| konfiguracja | grupa | strony | CER mikro | WER śr. |
|---|---|---|---|---|
| d200_none_none__psm3_best | odwolanie | 306 | 0.0020 | 0.0181 |
| d200_none_none__psm3_best | pelnomocnictwo | 61 | 0.0089 | 0.0242 |
| d200_none_none__psm3_best | przelew | 60 | 0.0110 | 0.0353 |
| d200_none_none__psm3_best | strony 1–2 | 241 | 0.0047 | 0.0231 |
| d200_none_none__psm3_best | strony 3+ | 186 | 0.0019 | 0.0192 |
| d200_none_none__psm6_best | odwolanie | 306 | 0.0013 | 0.0095 |
| d200_none_none__psm6_best | pelnomocnictwo | 61 | 0.0042 | 0.0187 |
| d200_none_none__psm6_best | przelew | 60 | 0.0377 | 0.0457 |
| d200_none_none__psm6_best | strony 1–2 | 241 | 0.0073 | 0.0248 |
| d200_none_none__psm6_best | strony 3+ | 186 | 0.0009 | 0.0043 |
| d200_none_none__psm6_std | odwolanie | 306 | 0.0016 | 0.0132 |
| d200_none_none__psm6_std | pelnomocnictwo | 61 | 0.0046 | 0.0215 |
| d200_none_none__psm6_std | przelew | 60 | 0.0583 | 0.0480 |
| d200_none_none__psm6_std | strony 1–2 | 241 | 0.0103 | 0.0263 |
| d200_none_none__psm6_std | strony 3+ | 186 | 0.0013 | 0.0102 |
| d300_none_none__psm6_poleng | odwolanie | 306 | 0.0026 | 0.0109 |
| d300_none_none__psm6_poleng | pelnomocnictwo | 61 | 0.0049 | 0.0222 |
| d300_none_none__psm6_poleng | przelew | 60 | 0.0453 | 0.0865 |
| d300_none_none__psm6_poleng | strony 1–2 | 241 | 0.0087 | 0.0353 |
| d300_none_none__psm6_poleng | strony 3+ | 186 | 0.0026 | 0.0074 |
| d200_none_none__psm4_best | odwolanie | 46 | 0.0016 | 0.0157 |
| d200_none_none__psm4_best | pelnomocnictwo | 10 | 0.0086 | 0.0329 |
| d200_none_none__psm4_best | przelew | 10 | 0.0055 | 0.0216 |
| d200_none_none__psm4_best | strony 1–2 | 40 | 0.0039 | 0.0200 |
| d200_none_none__psm4_best | strony 3+ | 26 | 0.0014 | 0.0179 |

## 4. Zestaw D (syntetycznie zdegradowane rendery) i preprocessing

| konfiguracja | strony | CER mikro | WER śr. |
|---|---|---|---|
| d200_bin_deskew+noleader__psm3_best | 66 | 0.0025 | 0.0186 |
| d200_bin_none__psm3_best | 66 | 0.0039 | 0.0236 |
| d200_blur10_deskew+noleader__psm3_best | 66 | 0.0025 | 0.0199 |
| d200_blur10_none__psm3_best | 66 | 0.0043 | 0.0286 |
| d200_jpeg30_deskew+noleader__psm3_best | 66 | 0.0045 | 0.0286 |
| d200_jpeg30_none__psm3_best | 66 | 0.0047 | 0.0312 |
| d200_noise10_deskew+noleader__psm3_best | 66 | 0.0049 | 0.0340 |
| d200_noise10_none__psm3_best | 66 | 0.0050 | 0.0324 |
| d200_none_deskew+noleader__psm3_best | 427 | 0.0024 | 0.0158 |
| d200_none_noleader__psm3_best | 427 | 0.0024 | 0.0155 |
| d200_real_bin_deskew+noleader__psm3_best | 66 | 0.0145 | 0.0989 |
| d200_real_bin_none__psm3_best | 66 | 0.0206 | 0.1348 |
| d200_real_deskew+noleader__psm3_best | 66 | 0.0050 | 0.0323 |
| d200_real_none__psm3_best | 66 | 0.0086 | 0.0464 |
| d200_rot1_deskew+noleader__psm3_best | 66 | 0.0051 | 0.0259 |
| d200_rot1_none__psm3_best | 66 | 0.0056 | 0.0326 |
| omp-deskew_none_none__psm3_best | 66 | 0.0068 | 0.0344 |
| omp-deskew_none_none__psm6_best | 66 | 0.0064 | 0.0294 |
| omp-plain_none_none__psm3_best | 66 | 0.0072 | 0.0352 |
| omp-plain_none_none__psm6_best | 66 | 0.0060 | 0.0284 |

## 5. Przeżywalność wartości pól GT (A7/B1)

L0 dokładnie · L1 łagodnie (wielkość liter/ogonki/spacje) · L2 rozmyto (≤1 edycja do 12 zn., ≤10% dłuższe) · L3 brak. Na S/D mianownik = pola, których zapis jest w tekście referencyjnym. **Porównuj tylko wiersze o tej samej liczbie pól** (siatka liczona na podzbiorze 10 spraw = 296 pól, kandydaci na całym S = 1780 pól).

### Zestaw S + D — wszystkie pola (tekst w wierszach wizualnych; w nawiasie: kolejność natywna Tesseracta)

| zestaw | konfiguracja | pola | L0 | L0+L1 | L0+L1+L2 | L3 | L0+L1 natywnie |
|---|---|---|---|---|---|---|---|
| D | d200_real_deskew+noleader__psm3_best | 296 | 93.92% | 94.93% | 100.00% | 0.00% | 94.93% |
| D | d200_noise10_none__psm3_best | 296 | 94.26% | 94.59% | 100.00% | 0.00% | 94.59% |
| D | d200_rot1_deskew+noleader__psm3_best | 296 | 94.26% | 94.59% | 100.00% | 0.00% | 94.59% |
| D | d200_bin_deskew+noleader__psm3_best | 296 | 93.58% | 94.59% | 100.00% | 0.00% | 94.59% |
| D | d200_jpeg30_deskew+noleader__psm3_best | 296 | 94.26% | 94.26% | 100.00% | 0.00% | 94.26% |
| D | d200_noise10_deskew+noleader__psm3_best | 296 | 94.26% | 94.26% | 100.00% | 0.00% | 94.26% |
| D | d200_jpeg30_none__psm3_best | 296 | 93.92% | 94.26% | 100.00% | 0.00% | 94.26% |
| D | d200_blur10_none__psm3_best | 296 | 93.58% | 94.26% | 100.00% | 0.00% | 94.26% |
| D | d200_blur10_deskew+noleader__psm3_best | 296 | 93.24% | 93.92% | 100.00% | 0.00% | 93.92% |
| D | d200_rot1_none__psm3_best | 296 | 92.91% | 93.24% | 100.00% | 0.00% | 93.24% |
| D | d200_real_none__psm3_best | 296 | 92.57% | 93.24% | 100.00% | 0.00% | 93.24% |
| D | d200_bin_none__psm3_best | 296 | 92.91% | 92.91% | 100.00% | 0.00% | 92.91% |
| D | d200_real_bin_deskew+noleader__psm3_best | 296 | 86.49% | 89.19% | 99.66% | 0.34% | 89.19% |
| D | d200_real_bin_none__psm3_best | 296 | 82.43% | 85.81% | 100.00% | 0.00% | 85.81% |
| S | d300_none_none__psm6_poleng | 1780 | 95.79% | 96.46% | 99.94% | 0.06% | 96.46% |
| S | d300_none_none__psm4_poleng | 296 | 94.93% | 95.61% | 100.00% | 0.00% | 95.61% |
| S | d300_none_none__psm3_poleng | 296 | 94.93% | 95.27% | 100.00% | 0.00% | 95.27% |
| S | d200_none_none__psm3_poleng | 296 | 94.93% | 94.93% | 100.00% | 0.00% | 94.93% |
| S | d200_none_none__psm4_poleng | 296 | 94.93% | 94.93% | 100.00% | 0.00% | 94.93% |
| S | d300_none_none__psm6_best | 296 | 94.93% | 94.93% | 100.00% | 0.00% | 94.93% |
| S | d200_none_none__psm11_poleng | 296 | 94.26% | 94.93% | 100.00% | 0.00% | 94.93% |
| S | d300_none_none__psm11_poleng | 296 | 94.26% | 94.93% | 100.00% | 0.00% | 94.93% |
| S | d300_none_none__psm4_best | 296 | 94.26% | 94.93% | 100.00% | 0.00% | 94.93% |
| S | d200_none_deskew+noleader__psm3_best | 1780 | 94.55% | 94.83% | 100.00% | 0.00% | 94.66% |
| S | d200_none_noleader__psm3_best | 1780 | 94.27% | 94.61% | 100.00% | 0.00% | 94.44% |
| S | d200_none_none__psm3_best | 1780 | 94.27% | 94.61% | 100.00% | 0.00% | 94.44% |
| S | d300_none_none__psm3_best | 296 | 93.92% | 94.59% | 100.00% | 0.00% | 94.59% |
| S | d200_none_none__psm6_best | 1780 | 94.10% | 94.49% | 99.94% | 0.06% | 94.49% |
| S | d200_none_none__psm6_poleng | 296 | 94.26% | 94.26% | 100.00% | 0.00% | 94.26% |
| S | d200_none_none__psm11_best | 296 | 93.58% | 94.26% | 100.00% | 0.00% | 94.26% |
| S | d300_none_none__psm11_best | 296 | 93.58% | 94.26% | 100.00% | 0.00% | 94.26% |
| S | omp-deskew_none_none__psm3_best | 296 | 93.92% | 93.92% | 100.00% | 0.00% | 93.92% |
| S | omp-plain_none_none__psm3_best | 296 | 93.92% | 93.92% | 100.00% | 0.00% | 93.92% |
| S | omp-plain_none_none__psm6_best | 296 | 93.92% | 93.92% | 100.00% | 0.00% | 93.92% |
| S | d200_none_none__psm4_best | 296 | 93.58% | 93.92% | 100.00% | 0.00% | 93.92% |
| S | omp-deskew_none_none__psm6_best | 296 | 93.58% | 93.92% | 100.00% | 0.00% | 93.92% |
| S | d300_none_none__psm3_std | 296 | 92.57% | 93.58% | 100.00% | 0.00% | 93.58% |
| S | d300_none_none__psm6_std | 296 | 91.55% | 93.58% | 100.00% | 0.00% | 93.58% |
| S | d200_none_none__psm6_std | 1780 | 93.15% | 93.31% | 99.94% | 0.06% | 93.31% |
| S | d200_none_none__psm3_std | 296 | 93.24% | 93.24% | 100.00% | 0.00% | 93.24% |
| S | d200_none_none__psm11_std | 296 | 92.91% | 93.24% | 100.00% | 0.00% | 93.24% |
| S | d200_none_none__psm4_std | 296 | 92.91% | 93.24% | 100.00% | 0.00% | 93.24% |
| S | d300_none_none__psm4_std | 296 | 92.57% | 93.24% | 100.00% | 0.00% | 93.24% |
| S | d300_none_none__psm11_std | 296 | 91.55% | 93.24% | 100.00% | 0.00% | 93.24% |

Najlepsza konfiguracja na S: `d300_none_none__psm6_poleng` — per klasa pola:

| klasa pola | pola | L0 | L1 | L2 | L3 |
|---|---|---|---|---|---|
| email | 60 | 76.67% | 0.00% | 23.33% | 0.00% |
| nazwa_podmiotu | 249 | 85.54% | 1.61% | 12.85% | 0.00% |
| tytul | 120 | 91.67% | 1.67% | 6.67% | 0.00% |
| rachunek | 120 | 95.00% | 1.67% | 3.33% | 0.00% |
| numer | 215 | 97.21% | 0.93% | 1.86% | 0.00% |
| osoba | 257 | 98.83% | 0.78% | 0.00% | 0.39% |
| data | 165 | 100.00% | 0.00% | 0.00% | 0.00% |
| identyfikator | 489 | 100.00% | 0.00% | 0.00% | 0.00% |
| kwota | 60 | 100.00% | 0.00% | 0.00% | 0.00% |
| miejscowosc | 45 | 100.00% | 0.00% | 0.00% | 0.00% |

Pola L2/L3 w `d300_none_none__psm6_poleng` (max 40):

| dokument | pole | wartość GT | poziom | dyst. | najbliższe okno OCR (squash) |
|---|---|---|---|---|---|
| przyklad_01__przelew | przelew_bankowy.tytul | opłata skarbowa od pełnomocnictwa dla Aleksandra Marciniak i Jolanta Zajkowski w postępowaniu przed KIO w przetargu ZS.791.2026 CEN2604016344389 | L2 | 2 | isoptataskarbowaodpetnomocnictwadlaaleksandramarciniakijolantazajkowskiwpostepowaniuprzedkiowprzetarguzs.791.2026cen2604016344389 |
| przyklad_03__odwolanie | Odwolujacy[0].pelnomocnik.mail | biuro@biuro.example | L2 | 1 | 0,biuroqbiuro.example |
| przyklad_03__odwolanie | Zamawiajacy[0].nazwa | Lunareth Automatyka sp. z o.o. | L2 | 2 | y:lunarethautomatykasp.z0.0. |
| przyklad_04__pelnomocnictwo | mocodawca[0].podpisujacy[0].imie_nazwisko | Ewa Szulc | L3 | 5 | u"dostawal |
| przyklad_04__potwierdzenie_przelewu | przelew_bankowy.tytul | opłata skarbowa od pełnomocnictwa dla Patrycja Furman i Sławomir Ostrowczyk w postępowaniu przed KIO w przetargu ZP.447.2026 CEN2608246932582 | L2 | 3 | utoptataskarbowaodpetnomocnictwadlapatrycjafurmanistawomirostrowczykwpostepowaniuprzedkiowprzetarguzp.447.2026cen2608246932582 |
| przyklad_05__pelnomocnictwo | mocodawca[0].data.nazwa | Corvantis Wyposażenie sp. z o.o. | L2 | 2 | ikcorvantiswyposazeniesp.z0.0. |
| przyklad_06__pelnomocnictwo | mocodawca[0].data.nazwa | Silvatica Technologie sp. z o.o. | L2 | 2 | wesilvaticatechnologiesp.z0.0. |
| przyklad_09__odwolanie | ZamowieniePubliczne.numer_ted | 999923-2026 | L2 | 1 | d:2026/5189-999923 |
| przyklad_09__potwierdzenie_przelewu | przelew_bankowy.tytul | opłata skarbowa od pełnomocnictwa dla Weronika Kaczmarek i Weronika Chmielewski w postępowaniu przed KIO w przetargu SWZ.613.2026 CEN2610289710500 | L2 | 2 | utoptataskarbowaodpetnomocnictwadlaweronikakaczmarekiweronikachmielewskiwpostepowaniuprzedkiowprzetarguswz.613.2026cen2610289710500 |
| przyklad_11__odwolanie | Zamawiajacy[0].nazwa | Zorina Technologie sp. z o.o. | L2 | 2 | y:zorinatechnologiesp.z0.0. |
| przyklad_13__odwolanie | Zamawiajacy[0].nazwa | Wexoria Serwis sp. z o.o. | L2 | 2 | y:wexoriaserwissp.z0.0. |
| przyklad_13__odwolanie | ZamowieniePubliczne.numer_ted | 999000-2026 | L2 | 1 | d:2026/5013-999000 |
| przyklad_17__pelnomocnictwo | mocodawca[0].data.nazwa | Kavendis Infrastruktura sp. z o.o. | L2 | 2 | ikkavendisinfrastrukturasp.z0.0. |
| przyklad_19__pelnomocnictwo | mocodawca[0].data.nazwa | Corvantis Sieci sp. z o.o. | L2 | 2 | stcorvantissiecisp.z0.0. |
| przyklad_20__pelnomocnictwo | mocodawca[0].data.nazwa | Quentavis Usługi sp. z o.o. | L2 | 2 | caquentavisuslugisp.z0.0. |
| przyklad_21__odwolanie | ZamowieniePubliczne.numer_ted | 999431-2026 | L2 | 1 | e:2026/8195-999431 |
| przyklad_22__odwolanie | Odwolujacy[0].pelnomocnik.mail | biuro@kontakt.example | L2 | 1 | 0,biuroqkontakt.example |
| przyklad_23__odwolanie | Zamawiajacy[0].nazwa | Galdaris Technologie sp. z o.o. | L2 | 2 | y:galdaristechnologiesp.z0.0. |
| przyklad_23__pelnomocnictwo | mocodawca[0].data.nazwa | Wexford Systemy sp. z o.o. | L2 | 2 | ikwexfordsystemysp.z0.0. |
| przyklad_28__odwolanie | Zamawiajacy[0].nazwa | Uldaris Usługi sp. z o.o. | L2 | 2 | y:uldarisuslugisp.z0.0. |
| przyklad_28__potwierdzenie_przelewu | przelew_bankowy.na_rachunek | 02985526938978681496365038 | L2 | 1 | taplo2985526938978681496365038 |
| przyklad_29__odwolanie | Zamawiajacy[0].nazwa | Rubiconis Wyposażenie sp. z o.o. | L2 | 2 | y:rubiconiswyposazeniesp.z0.0. |
| przyklad_30__odwolanie | Zamawiajacy[0].nazwa | Veltra Infrastruktura sp. z o.o. | L2 | 2 | y:veltrainfrastrukturasp.z0.0. |
| przyklad_31__odwolanie | Odwolujacy[0].pelnomocnik.mail | biuro@poczta.example | L2 | 1 | 0,biuro©poczta.example |
| przyklad_32__odwolanie | Zamawiajacy[0].nazwa | Elarion Technologie sp. z o.o. | L2 | 2 | y:elariontechnologiesp.z0.0. |
| przyklad_34__odwolanie | Zamawiajacy[0].nazwa | Wexoria Systemy sp. z o.o. | L2 | 2 | y:wexoriasystemysp.z0.0. |
| przyklad_34__odwolanie | ZamowieniePubliczne.numer_ted | 999808-2026 | L2 | 1 | d:2026/5074-999808 |
| przyklad_36__odwolanie | Odwolujacy[0].pelnomocnik.mail | biuro@kontakt.example | L2 | 1 | 0,biuroqkontakt.example |
| przyklad_37__odwolanie | Odwolujacy[0].pelnomocnik.mail | biuro@sekretariat.example | L2 | 1 | 0,biuro©sekretariat.example |
| przyklad_38__odwolanie | Zamawiajacy[0].nazwa | Umbria Automatyka sp. z o.o. | L2 | 2 | y:umbriaautomatykasp.z0.0. |
| przyklad_38__potwierdzenie_przelewu | przelew_bankowy.tytul | opłata skarbowa od pełnomocnictwa dla Oliwia Wierzbicka i Jolanta Jabłończyk w postępowaniu przed KIO w przetargu SWZ.702.2026 CEN2608122277227 | L2 | 2 | s:optataskarbowaodpetnomocnictwadlaoliwiawierzbickaijolantajablonczykwpostepowaniuprzedkiowprzetarguswz.702.2026cen2608122277227 |
| przyklad_39__odwolanie | Odwolujacy[0].pelnomocnik.mail | biuro@biuro.example | L2 | 1 | 0,biuroqbiuro.example |
| przyklad_39__odwolanie | Zamawiajacy[0].nazwa | Corvella Systemy sp. z o.o. | L2 | 2 | y:corvellasystemysp.z0.0. |
| przyklad_40__odwolanie | Zamawiajacy[0].nazwa | Regionalne Centrum Usług Medycznych sp. z o.o. | L2 | 2 | y-regionalnecentrumuslugmedycznychsp.z0.0. |
| przyklad_40__odwolanie | ZamowieniePubliczne.tytul | Dostawa, instalacja i konfiguracja zintegrowanego systemu informatycznego klasy HIS wraz ze świadczeniem usług serwisu pogwarancyjnego przez okres 36 miesięcy | L2 | 1 | ."dostawa,instalacja1konfiguracjazintegrowanegosystemuinformatycznegoklasyhiswrazzeswiadczeniemuslugserwisupogwarancyjnegoprzezokres36miesiecy |
| przyklad_40__pelnomocnictwo | mocodawca[0].data.nazwa | Valtrix Systemy Informatyczne sp. z o.o. | L2 | 2 | wovaltrixsystemyinformatycznesp.z0.0. |
| przyklad_41__odwolanie | Odwolujacy[0].pelnomocnik.mail | p.zalewski@adwokat.example | L2 | 1 | l:p.zalewskiqadwokat.example |
| przyklad_42__odwolanie | ZamowieniePubliczne.tytul | Kompleksowe usługi utrzymania czystości, ochrony fizycznej i obsługi technicznej obiektów Zamawiających w latach 2026–2029 | L2 | 1 | "kompleksoweuslugiutrzymaniaczystosci,ochronyfizycznejiobslugitechnicznejobiektowzamawiajacych'wlatach2026-2029 |
| przyklad_42__potwierdzenie_przelewu | przelew_bankowy.z_rachunku | 55994774587693681405727867 | L2 | 1 | cypls5994774587693681405727867 |
| przyklad_44__odwolanie | Odwolujacy[0].pelnomocnik.mail | kancelaria@goreckasikora.example | L2 | 1 | l:kancelariaqgoreckasikora.example |

### Zestaw K — wszystkie pola (tekst w wierszach wizualnych; w nawiasie: kolejność natywna Tesseracta)

| zestaw | konfiguracja | pola | L0 | L0+L1 | L0+L1+L2 | L3 | L0+L1 natywnie |
|---|---|---|---|---|---|---|---|
| K | d200_none_deskew+noleader__psm3_best | 266 | 92.48% | 93.23% | 99.62% | 0.38% | 93.61% |
| K | d200_none_deskew__psm3_best | 266 | 92.48% | 93.23% | 99.62% | 0.38% | 93.61% |
| K | d200_none_noleader__psm3_best | 266 | 90.23% | 92.86% | 100.00% | 0.00% | 92.86% |
| K | d200_none_none__psm3_best | 266 | 90.23% | 92.86% | 100.00% | 0.00% | 92.86% |
| K | d300_none_none__psm3_std | 266 | 90.23% | 92.48% | 99.25% | 0.75% | 92.48% |
| K | d300_none_none__psm3_best | 266 | 89.85% | 92.11% | 100.00% | 0.00% | 92.11% |
| K | d200_none_otsu__psm3_best | 266 | 91.35% | 91.73% | 100.00% | 0.00% | 91.73% |
| K | d300_none_none__psm4_best | 266 | 89.47% | 91.73% | 99.62% | 0.38% | 88.72% |
| K | omp-plain_none_none__psm3_best | 266 | 89.47% | 91.73% | 99.25% | 0.75% | 92.48% |
| K | d200_none_none__psm4_best | 266 | 88.35% | 91.73% | 99.62% | 0.38% | 89.85% |
| K | d200_none_deskew__psm6_best | 266 | 90.98% | 91.35% | 100.00% | 0.00% | 91.35% |
| K | d200_none_noleader__psm6_best | 266 | 88.35% | 90.98% | 99.62% | 0.38% | 90.98% |
| K | d200_none_none__psm6_best | 266 | 88.35% | 90.98% | 99.62% | 0.38% | 90.98% |
| K | omp-plain_none_none__psm6_best | 266 | 89.10% | 90.60% | 99.25% | 0.75% | 90.23% |
| K | d200_none_none__psm3_std | 266 | 88.35% | 90.60% | 98.87% | 1.13% | 90.60% |
| K | omp-deskew+thr-sauvola_none_none__psm3_best | 266 | 90.23% | 90.23% | 98.50% | 1.50% | 90.23% |
| K | d200_none_denoise+deskew__psm3_best | 266 | 89.85% | 90.23% | 96.99% | 3.01% | 90.60% |
| K | omp-deskew+rot_none_none__psm3_best | 266 | 89.47% | 90.23% | 99.62% | 0.38% | 90.23% |
| K | omp-deskew_none_none__psm3_best | 266 | 89.47% | 90.23% | 99.62% | 0.38% | 90.23% |
| K | d300_none_none__psm4_std | 266 | 87.59% | 89.85% | 99.25% | 0.75% | 87.22% |
| K | d300_none_none__psm6_best | 266 | 87.59% | 89.47% | 99.62% | 0.38% | 89.47% |
| K | d300_none_none__psm6_std | 266 | 86.84% | 89.10% | 99.25% | 0.75% | 89.10% |
| K | d200_none_none__psm4_std | 266 | 85.71% | 88.72% | 98.50% | 1.50% | 86.84% |
| K | omp-deskew+rot_none_none__psm6_best | 266 | 88.35% | 88.35% | 98.50% | 1.50% | 88.35% |
| K | omp-deskew+thr-sauvola_none_none__psm6_best | 266 | 88.35% | 88.35% | 98.12% | 1.88% | 88.35% |
| K | omp-deskew_none_none__psm6_best | 266 | 88.35% | 88.35% | 98.50% | 1.50% | 88.35% |
| K | d200_none_none__psm6_std | 266 | 86.47% | 88.35% | 98.50% | 1.50% | 88.35% |
| K | d200_none_adaptive__psm3_best | 266 | 81.20% | 84.59% | 96.62% | 3.38% | 84.59% |

Najlepsza konfiguracja na K: `d200_none_deskew+noleader__psm3_best` — per klasa pola:

| klasa pola | pola | L0 | L1 | L2 | L3 |
|---|---|---|---|---|---|
| email | 9 | 0.00% | 0.00% | 88.89% | 11.11% |
| tytul | 20 | 80.00% | 5.00% | 15.00% | 0.00% |
| nazwa_podmiotu | 40 | 85.00% | 2.50% | 12.50% | 0.00% |
| rachunek | 20 | 95.00% | 0.00% | 5.00% | 0.00% |
| data | 30 | 100.00% | 0.00% | 0.00% | 0.00% |
| identyfikator | 60 | 100.00% | 0.00% | 0.00% | 0.00% |
| kwota | 10 | 100.00% | 0.00% | 0.00% | 0.00% |
| miejscowosc | 10 | 100.00% | 0.00% | 0.00% | 0.00% |
| numer | 26 | 100.00% | 0.00% | 0.00% | 0.00% |
| osoba | 41 | 100.00% | 0.00% | 0.00% | 0.00% |

Pola L2/L3 w `d200_none_deskew+noleader__psm3_best` (max 40):

| dokument | pole | wartość GT | poziom | dyst. | najbliższe okno OCR (squash) |
|---|---|---|---|---|---|
| skany__odwolania__0001 | Odwolujacy[0].pelnomocnik.mail | a.rybak@rybak-kancelaria.example | L2 | 1 | l:a.rybakgrybak-kancelaria.example |
| skany__odwolania__0002 | Odwolujacy[0].pelnomocnik.mail | m.wierzbicki@wierzbicki-kancelaria.example | L2 | 3 | m.wierzbickiowierzbicki-kancelararia.example |
| skany__odwolania__0003 | Odwolujacy[0].pelnomocnik.mail | z.olszewska@sikora-kancelaria.example | L2 | 2 | :z.olszewska()sikora-kancelaria.example |
| skany__odwolania__0004 | Odwolujacy[0].pelnomocnik.mail | k.jodlowski@jodlowski-kancelaria.example | L3 | 9 | :e-mail:k.jwski(qjodlowski-kancelaria.exam |
| skany__odwolania__0005 | Odwolujacy[0].pelnomocnik.mail | g.kaczmarek@kaczmarek-kancelaria.example | L2 | 1 | l:g.kaczmarekqkaczmarek-kancelaria.example |
| skany__odwolania__0006 | Odwolujacy[0].nazwa | Nordenix Automatyka Sp. z o.o. | L2 | 2 | o-nordenixautomatykasp.z0.0. |
| skany__odwolania__0006 | Odwolujacy[0].pelnomocnik.nazwa | Kancelaria Prawna Olszewski & Partnerzy sp. k. | L2 | 1 | kancelariaprawnaolszewski£partnerzysp.k. |
| skany__odwolania__0006 | Odwolujacy[0].pelnomocnik.mail | s.sikora@olszewski-kancelaria.example | L2 | 1 | l:s.sikora(olszewski-kancelaria.example |
| skany__odwolania__0007 | Odwolujacy[0].pelnomocnik.mail | d.kubiak@kubiak-kancelaria.example | L2 | 2 | :d.kubiak(okubiak-kancelaria.example |
| skany__odwolania__0008 | Odwolujacy[0].nazwa | Orbisol Budownictwo Sp. z o.o. | L2 | 2 | y:orbisolbudownictwosp.z0.0. |
| skany__odwolania__0008 | Odwolujacy[0].pelnomocnik.mail | r.malinowski@cieslak-kancelaria.example | L2 | 2 | :r.malinowski(acieslak-kancelaria.example |
| skany__odwolania__0009 | Odwolujacy[0].nazwa | Asterion Drogi i Mosty Sp. z o.o. | L2 | 2 | y:asteriondrogiimostysp.z0.0. |
| skany__odwolania__0010 | Odwolujacy[0].pelnomocnik.mail | a.wrobel@wrobel-kancelaria.example | L2 | 1 | l:a.wrobelowrobel-kancelaria.example |
| skany__odwolania__0010 | ZamowieniePubliczne.tytul | Dostawa energii elektrycznej do obiektów Zamawiającego w latach 2027-2028 | L2 | 1 | "dostawaenergiielektrycznej\|doobiektowzamawiajacegowlatach2027-2028 |
| skany__pelnomocnictwa__0008 | mocodawca[0].data.nazwa | Orbisol Budownictwo Sp. z o.o. | L2 | 2 | woorbisolbudownictwosp.z0.0. |
| skany__potwierdzenia__0004 | przelew_bankowy.tytul | OPŁATA SKARBOWA OD PEŁNOMOCNICTWA DLA RADCA PRAWNY KRZYSZTOF JODŁOWSKI W POSTĘPOWANIU PRZED KIO W PRZETARGU DZP.260.69.2026 | L2 | 1 | ;oplataskarbowaodpelnomocnictwadlaradcaprawnykrzysztofjodlowskiw.postepowaniuprzedkiowprzetargudzp.260.69.2026 |
| skany__potwierdzenia__0007 | przelew_bankowy.z_rachunku | 66109010980387304538982666 | L2 | 1 | ku66109010980367304538982666 |
| skany__potwierdzenia__0008 | przelew_bankowy.tytul | opłata skarbowa od pełnomocnictwa dla adw. Rafał Malinowski w postępowaniu przed KIO w przetargu ZP/134/2026 | L2 | 5 | oscioplataskarbowaodpelnomocnectwadiaadwrafalmaknowskiwpostepowaniuprzedkiowprzetarguzp/134/2026 |

## 6. Błędy OCR — `d200_none_none__psm4_best` (zestaw S)

Operacji błędu: 153.

| typ błędu | liczba |
|---|---|
| znaki_specjalne | 59 |
| cyfra_litera | 21 |
| podzial_slow | 17 |
| interpunkcja | 17 |
| pominiete | 17 |
| wielkosc_liter | 14 |
| nadmiarowe | 11 |
| inne | 6 |
| diakrytyki | 1 |

| typ tokenu | liczba |
|---|---|
| zwykle | 84 |
| skrot | 28 |
| nazwa_wlasna | 14 |
| liczba | 11 |
| - | 11 |
| identyfikator | 5 |

| pole GT | błędów |
|---|---|
| (poza polami GT) | 122 |
| Odwolujacy.pelnomocnik.mail | 10 |
| pelnomocnicy.imie_nazwisko | 4 |
| Zamawiajacy.nazwa | 3 |
| Odwolujacy.nazwa | 3 |
| Odwolujacy.pelnomocnik.imie_nazwisko | 3 |
| przelew_bankowy.z_rachunku | 2 |
| mocodawca.data.nazwa | 2 |
| ZamowieniePubliczne.numer_postepowania | 1 |
| ZamowieniePubliczne.tytul | 1 |
| OdwolanieKIO.czynnosc_dzien | 1 |
| Odwolujacy.pelnomocnik.nazwa | 1 |

| typ dokumentu | błędów |
|---|---|
| odwolanie | 82 |
| pelnomocnictwo | 51 |
| przelew | 20 |

Najczęstsze pomyłki znaków (ref → ocr):

| ref | ocr | liczba |
|---|---|---|
| o | 0 | 28 |
| § | 8 | 19 |
| ∅ | . | 16 |
| § | $ | 14 |
| . | ∅ | 13 |
| r | ∅ | 12 |
| ∅ | S | 10 |
| @ | Q | 9 |
| a | ∅ | 8 |
| o | ∅ | 6 |
| w | W | 6 |
| k | ∅ | 6 |
| @ | © | 5 |
| ∅ | ( | 5 |
| ∅ | \| | 5 |
| ∅ | Q | 4 |
| z | Z | 4 |
| ∅ | 0 | 4 |
| e | ∅ | 4 |
| z | ∅ | 4 |
| y | ∅ | 4 |
| i | ∅ | 4 |
| p | ∅ | 4 |
| s | S | 3 |
| ∅ | + | 3 |
| @ | ) | 3 |
| I | ∅ | 3 |
| · | : | 2 |
| 0 | O | 2 |
| @ | G | 2 |

Najczęściej psute tokeny referencji:

| token | liczba |
|---|---|
| § | 34 |
| o.o. | 14 |
| w | 6 |
| · | 5 |
| z | 4 |
| r. | 4 |
| pr. | 4 |
| 1 z 2 | 3 |
| kontakt@biuro.example | 3 |
| kontakt@poczta.example | 3 |
| o.o., | 3 |
| biuro@poczta.example | 2 |
| biuro@kontakt.example | 2 |
| 1 z | 2 |
| biuro@biuro.example | 2 |
| sp. | 2 |
| i | 2 |
| 1 | 2 |
| . | 2 |
| III. | 2 |
| z art. | 2 |
| Cezary | 2 |
| Renata | 2 |
| kontakt@sekretariat.example | 1 |
| 2 z 2 | 1 |
| PL05470680287581539721455024 | 1 |
| 000 | 1 |
| dobę. | 1 |
| 2 z | 1 |
| z o.o. § | 1 |

Przykłady (max 40, priorytet: błędy w polach GT):

| dokument | str. | rodzaj | ref | ocr | typ | pole | conf |
|---|---|---|---|---|---|---|---|
| przyklad_01__odwolanie | 1 | sub | biuro@poczta.example | biuroQpoczta.example | znaki_specjalne | Odwolujacy.pelnomocnik.mail | 44.666321 |
| przyklad_01__przelew | 1 | sub | PL05470680287581539721455024 | PLO05470680287581539721455024 | inne | przelew_bankowy.z_rachunku | 22.767113 |
| przyklad_07__odwolanie | 1 | sub | biuro@kontakt.example | biuroGQkontakt.example | znaki_specjalne | Odwolujacy.pelnomocnik.mail | 42.93243 |
| przyklad_13__odwolanie | 1 | sub | biuro@biuro.example | biuroQbiuro.example | znaki_specjalne | Odwolujacy.pelnomocnik.mail | 59.080688 |
| przyklad_13__odwolanie | 1 | sub | z | Z | wielkosc_liter | Zamawiajacy.nazwa | 92.186203 |
| przyklad_13__odwolanie | 1 | sub | o.o. | 0.0. | cyfra_litera | Zamawiajacy.nazwa | 94.141106 |
| przyklad_19__odwolanie | 1 | sub | o.o. | 0.0. | cyfra_litera | Odwolujacy.nazwa | 95.407867 |
| przyklad_19__odwolanie | 1 | sub | biuro@kontakt.example | biuroQkontakt.example | znaki_specjalne | Odwolujacy.pelnomocnik.mail | 82.447853 |
| przyklad_19__odwolanie | 1 | sub | DI.578.2026, | Dl.578.2026, | inne | ZamowieniePubliczne.numer_postepowania | 37.583485 |
| przyklad_19__pelnomocnictwo | 1 | sub | o.o., | 0.o., | cyfra_litera | mocodawca.data.nazwa | 59.89547 |
| przyklad_25__odwolanie | 1 | sub | biuro@biuro.example | biuroGbiuro.example | znaki_specjalne | Odwolujacy.pelnomocnik.mail | 63.419415 |
| przyklad_31__odwolanie | 1 | sub | biuro@poczta.example | biuroQpoczta.example | znaki_specjalne | Odwolujacy.pelnomocnik.mail | 14.593262 |
| przyklad_31__odwolanie | 1 | sub | o.o. | 0.0. | cyfra_litera | Zamawiajacy.nazwa | 87.025841 |
| przyklad_31__odwolanie | 1 | sub | "Świadczenie | "świadczenie | wielkosc_liter | ZamowieniePubliczne.tytul | 81.0084 |
| przyklad_37__odwolanie | 1 | sub | biuro@sekretariat.example | biuroQsekretariat.example | znaki_specjalne | Odwolujacy.pelnomocnik.mail | 89.275681 |
| przyklad_43__odwolanie | 1 | sub | o.o. | 0.0. | cyfra_litera | Odwolujacy.nazwa | 96.330902 |
| przyklad_43__odwolanie | 1 | sub | k.michalak@michalaklegal.example | k.michalak(Qmichalaklegal.example | interpunkcja\|znaki_specjalne | Odwolujacy.pelnomocnik.mail | 48.190758 |
| przyklad_49__odwolanie | 1 | sub | sikorski@sikorskikancelaria.example | sikorskiQsikorskikancelaria.example | znaki_specjalne | Odwolujacy.pelnomocnik.mail | 2.961189 |
| przyklad_49__odwolanie | 2 | merge | 2026 r.; | 2026r.; | podzial_slow | OdwolanieKIO.czynnosc_dzien | 78.411812 |
| przyklad_49__odwolanie | 10 | del | Cezary |  | pominiete | Odwolujacy.pelnomocnik.imie_nazwisko |  |
| przyklad_49__odwolanie | 10 | del | Sikorski, |  | pominiete | Odwolujacy.pelnomocnik.imie_nazwisko |  |
| przyklad_49__pelnomocnictwo | 1 | del | Cezary |  | pominiete | pelnomocnicy.imie_nazwisko |  |
| przyklad_49__pelnomocnictwo | 1 | del | Sikorski |  | pominiete | pelnomocnicy.imie_nazwisko |  |
| przyklad_55__odwolanie | 1 | sub | o.o. | 0.0. | cyfra_litera | Odwolujacy.nazwa | 96.483536 |
| przyklad_55__odwolanie | 1 | sub | o.o., | 0.o., | cyfra_litera | Odwolujacy.pelnomocnik.nazwa | 48.409809 |
| przyklad_55__odwolanie | 1 | sub | sekretariat@kowalczyk.example | sekretariat()kowalczyk.example | interpunkcja\|znaki_specjalne | Odwolujacy.pelnomocnik.mail | 88.45929 |
| przyklad_55__odwolanie | 11 | del | Kowalczyk, |  | pominiete | Odwolujacy.pelnomocnik.imie_nazwisko |  |
| przyklad_55__pelnomocnictwo | 1 | sub | o.o., | o0.o0., | inne | mocodawca.data.nazwa | 38.310936 |
| przyklad_55__pelnomocnictwo | 1 | del | Renata |  | pominiete | pelnomocnicy.imie_nazwisko |  |
| przyklad_55__pelnomocnictwo | 1 | del | Kowalczyk |  | pominiete | pelnomocnicy.imie_nazwisko |  |
| przyklad_55__potwierdzenie_przelewu | 1 | sub | PL02 | PLO2 | cyfra_litera | przelew_bankowy.z_rachunku | 76.211296 |
| przyklad_01__odwolanie | 1 | sub | kontakt@sekretariat.example | kontaktQsekretariat.example | znaki_specjalne |  | 66.822815 |
| przyklad_01__odwolanie | 1 | merge | 1 z 2 | 1z2 | podzial_slow |  | 69.953491 |
| przyklad_01__odwolanie | 2 | merge | 2 z 2 | 2z2 | podzial_slow |  | 77.540359 |
| przyklad_01__pelnomocnictwo | 1 | sub | § | S | znaki_specjalne |  | 84.400482 |
| przyklad_01__pelnomocnictwo | 1 | sub | § | S$ | znaki_specjalne |  | 33.728874 |
| przyklad_01__pelnomocnictwo | 1 | sub | § | $ | znaki_specjalne |  | 60.777622 |
| przyklad_01__pelnomocnictwo | 1 | sub | § | $ | znaki_specjalne |  | 68.103851 |
| przyklad_01__pelnomocnictwo | 1 | sub | § | $ | znaki_specjalne |  | 83.50885 |
| przyklad_01__przelew | 1 | sub | · | : | interpunkcja |  | 91.350067 |

### Confidence a błędy (A8)

| klasa tokenu | przedział conf | tokeny | błędne | odsetek błędnych |
|---|---|---|---|---|
| identyfikator | 0-50 | 3 | 2 | 0.6667 |
| identyfikator | 50-70 | 2 | 0 | 0.0 |
| identyfikator | 70-85 | 18 | 4 | 0.2222 |
| identyfikator | 85-95 | 149 | 0 | 0.0 |
| identyfikator | 95-100 | 441 | 0 | 0.0 |
| inne | 0-50 | 46 | 34 | 0.7391 |
| inne | 50-70 | 41 | 21 | 0.5122 |
| inne | 70-85 | 68 | 23 | 0.3382 |
| inne | 85-95 | 1656 | 39 | 0.0236 |
| inne | 95-100 | 13247 | 18 | 0.0014 |
| wszystkie | 0-50 | 49 | 36 | 0.7347 |
| wszystkie | 50-70 | 43 | 21 | 0.4884 |
| wszystkie | 70-85 | 86 | 27 | 0.314 |
| wszystkie | 85-95 | 1805 | 39 | 0.0216 |
| wszystkie | 95-100 | 13688 | 18 | 0.0013 |

### Położenie błędów na stronie
```
odsetek błędnych tokenów referencji [%] na siatce 10×10 strony (wiersz = wysokość, kolumna = szerokość)
  0.0   0.0   0.0   0.0   0.0   0.0   1.0   0.9   0.0   0.0
  0.0   4.2   1.3   1.1   0.8   1.5   2.1   1.0   3.4   0.0
  0.0   3.1   2.0   1.8   0.6   0.0   0.4   1.7   0.0   0.0
  0.0   3.4   1.8   1.0   0.7   0.0   0.0   1.0   0.0     .
  0.0   1.8   0.3   0.0   1.2   0.4   0.9   0.0   0.0     .
  0.0   0.8   0.7   0.9   0.5   1.0   0.0   0.0   0.0   0.0
  0.0   2.6   0.9   0.5   0.0   0.0   0.0   0.0   0.0   0.0
  0.0   3.3   0.0   0.0   0.0   0.0   0.5   0.0   0.0     .
  0.0   1.5   0.5   0.0   0.0   0.0   0.0   0.0   0.0   0.0
    .   0.0   0.0   0.0   0.0  12.0   0.0   0.0   0.0     .
```

## 7a. Czas OCR — czysty pomiar sekwencyjny (`timing`)

omp1 = 1 wątek Tesseracta (tryb wsadowy), ompN = domyślna liczba wątków. Bez renderu PDF.

| konfiguracja | wątki | zestaw | stron | mediana s/str. | max s/str. |
|---|---|---|---|---|---|
| d200_none_none__psm3_best | omp1 | K | 9 | 1.63 | 2.57 |
| d200_none_none__psm3_best | omp1 | S | 9 | 1.22 | 2.80 |
| d200_none_none__psm3_best | ompN | K | 9 | 1.63 | 2.52 |
| d200_none_none__psm3_best | ompN | S | 9 | 1.25 | 2.81 |
| d200_none_none__psm6_best | omp1 | K | 9 | 1.70 | 2.68 |
| d200_none_none__psm6_best | omp1 | S | 9 | 1.33 | 2.90 |
| d200_none_none__psm6_best | ompN | K | 9 | 1.45 | 2.56 |
| d200_none_none__psm6_best | ompN | S | 9 | 1.29 | 2.92 |
| d200_none_none__psm6_std | omp1 | K | 9 | 0.7850 | 1.24 |
| d200_none_none__psm6_std | omp1 | S | 9 | 0.5850 | 1.25 |
| d200_none_none__psm6_std | ompN | K | 9 | 0.8510 | 1.26 |
| d200_none_none__psm6_std | ompN | S | 9 | 0.5820 | 1.33 |
| d300_none_none__psm6_poleng | omp1 | K | 9 | 1.30 | 1.87 |
| d300_none_none__psm6_poleng | omp1 | S | 9 | 0.8260 | 1.67 |
| d300_none_none__psm6_poleng | ompN | K | 9 | 1.21 | 1.86 |
| d300_none_none__psm6_poleng | ompN | S | 9 | 0.8110 | 1.74 |

## 7. Czas OCR zapisany przy przebiegach (pod obciążeniem równoległym — tylko orientacyjnie)

| konfiguracja | stron | mediana s/str. | p95 s/str. |
|---|---|---|---|
| d200_bin_deskew+noleader__psm3_best | 66 | 7.98 | 11.95 |
| d200_bin_none__psm3_best | 66 | 7.90 | 11.91 |
| d200_blur10_deskew+noleader__psm3_best | 66 | 7.87 | 12.48 |
| d200_blur10_none__psm3_best | 66 | 7.58 | 12.28 |
| d200_jpeg30_deskew+noleader__psm3_best | 66 | 7.95 | 12.43 |
| d200_jpeg30_none__psm3_best | 66 | 8.36 | 12.39 |
| d200_noise10_deskew+noleader__psm3_best | 66 | 8.70 | 13.64 |
| d200_noise10_none__psm3_best | 66 | 9.05 | 13.60 |
| d200_none_deskew+noleader__psm3_best | 427 | 7.13 | 11.82 |
| d200_none_noleader__psm3_best | 427 | 7.85 | 13.12 |
| d200_none_none__psm11_best | 66 | 11.60 | 24.10 |
| d200_none_none__psm11_poleng | 66 | 5.31 | 12.03 |
| d200_none_none__psm11_std | 66 | 4.18 | 8.38 |
| d200_none_none__psm3_best | 427 | 9.74 | 18.37 |
| d200_none_none__psm3_poleng | 66 | 5.89 | 8.92 |
| d200_none_none__psm3_std | 66 | 4.31 | 9.12 |
| d200_none_none__psm4_best | 66 | 11.55 | 21.87 |
| d200_none_none__psm4_poleng | 66 | 5.21 | 9.60 |
| d200_none_none__psm4_std | 66 | 4.31 | 8.73 |
| d200_none_none__psm6_best | 427 | 9.44 | 18.59 |
| d200_none_none__psm6_poleng | 66 | 5.33 | 10.67 |
| d200_none_none__psm6_std | 427 | 4.15 | 9.12 |
| d200_real_bin_deskew+noleader__psm3_best | 66 | 7.58 | 12.70 |
| d200_real_bin_none__psm3_best | 66 | 7.36 | 11.59 |
| d200_real_deskew+noleader__psm3_best | 66 | 8.75 | 13.06 |
| d200_real_none__psm3_best | 66 | 7.95 | 12.55 |
| d200_rot1_deskew+noleader__psm3_best | 66 | 7.62 | 12.45 |
| d200_rot1_none__psm3_best | 66 | 7.01 | 11.58 |
| d300_none_none__psm11_best | 66 | 12.81 | 28.38 |
| d300_none_none__psm11_poleng | 66 | 6.98 | 13.60 |
| d300_none_none__psm11_std | 66 | 5.65 | 13.80 |
| d300_none_none__psm3_best | 66 | 13.79 | 25.08 |
| d300_none_none__psm3_poleng | 66 | 7.77 | 12.37 |
| d300_none_none__psm3_std | 66 | 5.59 | 10.55 |
| d300_none_none__psm4_best | 66 | 13.24 | 22.33 |
| d300_none_none__psm4_poleng | 66 | 8.32 | 12.60 |
| d300_none_none__psm4_std | 66 | 5.75 | 11.02 |
| d300_none_none__psm6_best | 66 | 12.25 | 25.59 |
| d300_none_none__psm6_poleng | 427 | 6.17 | 10.63 |
| d300_none_none__psm6_std | 66 | 4.64 | 10.82 |
| omp-deskew_none_none__psm3_best | 66 | 17.52 | 19.84 |
| omp-deskew_none_none__psm6_best | 66 | 16.94 | 18.20 |
| omp-plain_none_none__psm3_best | 66 | 13.61 | 14.89 |
| omp-plain_none_none__psm6_best | 66 | 12.66 | 13.93 |

## 8. Wybór automatyczny

- najniższy CER na S (wspólne strony): `d200_none_none__psm4_best`
- najwyższa przeżywalność L0+L1 na skanach K: `d200_none_deskew+noleader__psm3_best`
