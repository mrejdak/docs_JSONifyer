# tools/ocr_bench — benchmark OCR (krok 1)

Opis metod: [docs/01_ocr_tesseract.md](../../docs/01_ocr_tesseract.md). Wyniki: `reports/ocr/` (cache w `reports/ocr/cache/`, nie do repo).

Uruchamiać z katalogu `final_product/`:

```bat
.venv\Scripts\python -m tools.ocr_bench manifest      :: manifest danych (zestawy S = z warstwą tekstową, K = skany)
.venv\Scripts\python -m tools.ocr_bench reference     :: A1: tekst referencyjny + kontrola jakości

:: A3: pełna siatka na podzbiorze 10 spraw
.venv\Scripts\python -m tools.ocr_bench ocr --set S --subset strat10 --labels odwolanie,pelnomocnictwo,przelew ^
    --dpi 200,300 --psm 3,4,6,11 --model std,best,poleng
:: najlepsze konfiguracje na całym S (negatywy: tylko 2 pierwsze strony)
.venv\Scripts\python -m tools.ocr_bench ocr --set S --labels odwolanie,pelnomocnictwo,przelew --dpi 300 --psm 4 --model best
:: A10: degradacja syntetyczna (wymaga opencv)
.venv\Scripts\python -m tools.ocr_bench ocr --set S --subset strat10 --labels odwolanie,pelnomocnictwo,przelew ^
    --dpi 300 --psm 4 --model best --degrade rot1,blur10,noise10,bin,jpeg30,real,real_bin
:: B: skany, B2: preprocessing (wymaga opencv dla wariantów innych niż none)
.venv\Scripts\python -m tools.ocr_bench ocr --set K --dpi 200,300 --psm 3,4,6 --model std,best
.venv\Scripts\python -m tools.ocr_bench ocr --set K --dpi 300 --psm 4 --model best --preproc otsu,adaptive,deskew,deskew+otsu,denoise+deskew

.venv\Scripts\python -m tools.ocr_bench compare           :: A4–A8 → per_page.csv, errors.csv, char_confusion.csv, conf_bins.csv, heatmap.csv
.venv\Scripts\python -m tools.ocr_bench survival --set S  :: A7 (S i D) → survival_S.csv, survival_summary_S.csv, fields_not_in_ref.csv
.venv\Scripts\python -m tools.ocr_bench survival --set K  :: B1 → survival_K.csv, survival_summary_K.csv
.venv\Scripts\python -m tools.ocr_bench report            :: summary.md (+ ręczne wnioski z reports/ocr/wnioski.md)
```

Identyfikator konfiguracji: `d<dpi>_<degradacja>_<preprocessing>__psm<N>_<model>`, np. `d300_none_none__psm4_best`.

| Element | Warianty |
|---|---|
| model | `std` (systemowy `pol`), `best` (`tessdata_best/pol.traineddata`), `poleng` (`pol+eng`) |
| degradacja (`+` łączy) | `rot05 rot1 rot2 blur05 blur10 noise5 noise10 sp bin jpeg50 jpeg30 shade`, aliasy `real`, `real_bin` |
| preprocessing (`+` łączy) | `otsu adaptive deskew denoise osd noleader` (noleader = usunięcie kropek do podpisu) |

Uwagi:
- Tesseract wywoływany bezpośrednio (`stdin` → TSV), `OMP_THREAD_LIMIT=1`, równolegle w procesach (`--workers`).
- Porównanie na „wierszach wizualnych” (linie o wspólnym zakresie pionowym scalone, od lewej do prawej) — tak samo dla referencji i OCR; CER natywny = kolejność linii Tesseracta.
- Z porównania wyłączone są kropki/kreski do podpisu; rozstrzelone nagłówki (`P E Ł N O …`) scalane w jedno słowo.
- Etykiety typów (z nazw plików) służą wyłącznie ewaluacji.
