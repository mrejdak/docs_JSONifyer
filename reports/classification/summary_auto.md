# Klasyfikacja — tryb tekstu `auto`, LLM: `bielik-11b-v3.1`

Dokumentów: 228, poprawnie: 228 (**100.00%**). Czas: 438 s.

## Macierz pomyłek (wiersz = prawda, kolumna = predykcja)

| prawda \ predykcja | odwolanie | pelnomocnictwo | przelew | brak |
|---|---|---|---|---|
| odwolanie | 71 | 0 | 0 | 0 |
| pelnomocnictwo | 0 | 70 | 0 | 0 |
| przelew | 0 | 0 | 70 | 0 |
| brak | 0 | 0 | 0 | 17 |

## Precision / recall

| klasa | precision | recall | n |
|---|---|---|---|
| odwolanie | 1.000 | 1.000 | 71 |
| pelnomocnictwo | 1.000 | 1.000 | 70 |
| przelew | 1.000 | 1.000 | 70 |
| brak | 1.000 | 1.000 | 17 |

## Decyzja końcowa vs sam regex vs sam LLM

| wariant | poprawnie | dokumentów | dokładność |
|---|---|---|---|
| końcowa | 228 | 228 | 100.00% |
| sam regex | 228 | 228 | 100.00% |
| sam LLM | 228 | 228 | 100.00% |

Błędy wywołań LLM: 0. Niezgodność regex vs LLM: 0 dokumentów.

## Ścieżka decyzji

| ścieżka | dokumenty |
|---|---|
| llm+regex | 211 |
| llm_inny | 17 |

## Zapas progów (dla każdej klasy prawdziwej: wynik własnego typu i najwyższy wynik innego typu)

| prawda | zestaw | n | min wynik własny | mediana własny | max wynik obcy | min (własny − obcy) |
|---|---|---|---|---|---|---|
| brak | K | 3 | 0 | 0 | 1 | -1 |
| brak | S | 14 | 0 | 0 | 1 | -1 |
| odwolanie | K | 11 | 15 | 17 | -8 | 24 |
| odwolanie | S | 60 | 16 | 17 | -2 | 18 |
| pelnomocnictwo | K | 10 | 16 | 17 | -6 | 22 |
| pelnomocnictwo | S | 60 | 13 | 19 | 0 | 13 |
| przelew | K | 10 | 11 | 16 | 0 | 11 |
| przelew | S | 60 | 15 | 22 | 0 | 15 |

## Błędy (0)

