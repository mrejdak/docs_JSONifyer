# Odwołania2JSON — uruchomienie

## Komenda

Z katalogu `/opt/solution`:

```bash
docker compose -f /opt/solution/docs_JSONifyer/docker-compose.yml run --rm odw2json
```

Komenda nie wymaga interakcji i kończy się sama po przetworzeniu wszystkich plików (kod wyjścia 0).
Nie korzysta z usług działających w tle — kontener startuje na czas przetwarzania i jest usuwany.
Obraz Dockera jest już zbudowany na serwerze (`odw2json-odw2json`); uruchomienie niczego nie buduje ani
nie pobiera — poza zapytaniami do API modelu językowego.

## Układ katalogów

```
/opt/solution/
├── RUN.md                 ← ten plik
├── .env                   ← klucze API (poniżej)
├── input/                 ← dokumenty do przetworzenia
├── output/                ← wyniki
└── docs_JSONifyer/        ← rozwiązanie (kod, konfiguracja, model OCR, Dockerfile, docker-compose.yml)
```

## Wejście i wyjście

- **Wejście:** wszystkie pliki z `/opt/solution/input`, także w podkatalogach — PDF z warstwą tekstową,
  PDF ze skanami oraz obrazy skanów (`.png`, `.jpg`, `.tif`, `.bmp`). Rodzaj dokumentu rozpoznawany jest
  z treści; nazwy plików nie mają znaczenia.
- **Wyjście:** dla każdego pliku `/opt/solution/output/<ta sama ścieżka względna>/<nazwa pliku>.json`:
  - odwołanie do KIO, pełnomocnictwo, potwierdzenie przelewu → JSON zgodny ze schematem danego typu;
  - każdy inny dokument (oraz plik, którego nie da się odczytać) → `{}`.
- Ślady decyzji (diagnostyka, poza `output/`): `/opt/solution/docs_JSONifyer/trace/`.
- Czas: 4 dokumenty przetwarzane równolegle; skany wolniej (OCR na 2 vCPU).

## Usługi zewnętrzne

Klucze w `/opt/solution/.env` (nie ma ich w repozytorium; nazwy zmiennych:
`docs_JSONifyer/.env.example`).

| Usługa | Do czego | Zmienne w `.env` |
|---|---|---|
| **Bielik 11B v3.1** (model open-weight, SpeakLeash) przez API zgodne z OpenAI na **fabryka.ai** (serwer w UE) | klasyfikacja dokumentów i ekstrakcja pól | `LLM_API_URL`, `LLM_API_KEY`, `LLM_MODEL` |
| ten sam model na **Cyfronet AGH / PLGrid** (`llmlab.plgrid.pl`) — dostawca zapasowy, używany automatycznie, gdy fabryka.ai nie odpowiada | jw. | `CYFRO_LLM_API_URL`, `CYFRO_LLM_API_KEY`, `CYFRO_LLM_MODEL` |

OCR działa lokalnie (Tesseract 5.5, model `tessdata_best` dla języka polskiego w
`docs_JSONifyer/models/tessdata`). Gdy żaden dostawca LLM nie jest osiągalny, rozwiązanie działa dalej
w trybie awaryjnym (reguły bez LLM), z niższą jakością ekstrakcji.

## Diagnostyka (opcjonalnie)

```bash
docker compose -f /opt/solution/docs_JSONifyer/docker-compose.yml run --rm odw2json python -m odw2json check     # config, dostawcy LLM
docker compose -f /opt/solution/docs_JSONifyer/docker-compose.yml run --rm odw2json python -m tools.check_output  # czy każdy plik ma wynik
```
