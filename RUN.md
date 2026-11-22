# Odwołania2JSON — uruchomienie

## Komenda

Z katalogu `/opt/solution`:

```bash
docker compose run --rm odw2json
```

Komenda nie wymaga interakcji i kończy się sama po przetworzeniu wszystkich plików (kod wyjścia 0).
Nie korzysta z usług działających w tle — kontener startuje na czas przetwarzania i jest usuwany.
Obraz Dockera jest zbudowany wcześniej na serwerze (`docker compose build`); uruchomienie nie pobiera
niczego poza zapytaniami do API modelu językowego.

## Wejście i wyjście

- **Wejście:** wszystkie pliki z `/opt/solution/input`, także w podkatalogach — PDF z warstwą tekstową,
  PDF ze skanami oraz obrazy skanów (`.png`, `.jpg`, `.tif`, `.bmp`). Rodzaj dokumentu rozpoznawany jest
  z treści; nazwy plików nie mają znaczenia.
- **Wyjście:** dla każdego pliku `/opt/solution/output/<ta sama ścieżka względna>/<nazwa pliku>.json`:
  - odwołanie do KIO, pełnomocnictwo, potwierdzenie przelewu → JSON zgodny ze schematem danego typu;
  - każdy inny dokument (oraz plik, którego nie da się odczytać) → `{}`.
- Ślady decyzji (diagnostyka, poza `output/`): `/opt/solution/trace/`.
- Czas: zwykle 5–15 s na dokument (4 dokumenty przetwarzane równolegle; skany wolniej — OCR).

## Usługi zewnętrzne

Klucze w `/opt/solution/.env` (nie ma ich w repozytorium; nazwy zmiennych: `.env.example`).

| Usługa | Do czego | Zmienne w `.env` |
|---|---|---|
| **Bielik 11B v3.1** (model open-weight, SpeakLeash) przez API zgodne z OpenAI na **fabryka.ai** (serwer w UE) | klasyfikacja dokumentów i ekstrakcja pól | `LLM_API_URL`, `LLM_API_KEY`, `LLM_MODEL` |
| ten sam model na **Cyfronet AGH / PLGrid** (`llmlab.plgrid.pl`) — dostawca zapasowy, używany automatycznie, gdy fabryka.ai nie odpowiada | jw. | `CYFRO_LLM_API_URL`, `CYFRO_LLM_API_KEY`, `CYFRO_LLM_MODEL` |

OCR działa lokalnie (Tesseract 5, model `tessdata_best` dla języka polskiego w `models/tessdata`).
Gdy żaden dostawca LLM nie jest osiągalny, rozwiązanie działa dalej w trybie awaryjnym (reguły bez LLM),
z niższą jakością ekstrakcji.

## Diagnostyka (opcjonalnie)

```bash
docker compose run --rm odw2json python -m odw2json check            # config, dostawcy LLM
docker compose run --rm odw2json python -m tools.check_output         # czy każdy plik ma poprawny wynik
```
