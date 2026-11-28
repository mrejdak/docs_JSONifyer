# Odwołania2JSON

### Projekt zrealizowany w ramach jednego z zadań podczas hackathonu HackNation 2026, zakwalifikowany do finału.

## Problem

Sprawa odwoławcza przed KIO to zestaw PDF-ów: odwołanie, pełnomocnictwo, potwierdzenie przelewu i inne pisma z akt. Część ma warstwę tekstową, część to skany.
Układ dokumentów jest różny, niektóre informacje nie są obowiązkowe a nazwy plików nic nie mówią o ich typie. Aplikacja rozpoznaje typ każdego dokumentu z treści i zapisuje jego dane jako plik JSON w formacie o z góry określonej specyfikacji. Dokument, który nie jest żadnym z trzech typów, dostaje `{}`.

## Działanie

1. **Tekst:** warstwa tekstowa PDF-a albo OCR (Tesseract 5.5). Każde słowo ma współrzędne na stronie.
2. **Układ strony:** ze współrzędnych heurystycznie odtwarzane są wiersze i kolumny, tak żeby etykieta została przy
   swojej wartości.
3. **Typ dokumentu:** model językowy (Bielik 11B) ocenia wymagania każdego typu opisanego w configu. Kod
   sprawdza spójność tej oceny i to, czy cytaty podane przez model są w tekście.
4. **Pola:** model wypełnia pola w 1–3 wywołaniach na dokument. Format odpowiedzi jest generowany ze
   schematu typu.
5. **Weryfikacja:** każda wartość od modelu musi wystąpić w tekście dokumentu, inaczej pole dostaje null.
   Potem normalizacja, walidacja i reguły spójności.
6. **Wynik i ślad:** JSON trafia do `output/`, a do `trace/` uzasadnienie każdej decyzji.

Opis typu dokumentu, pola, prompty i reguły leżą w `config/types/<typ>/`. Nowy typ dokumentu to nowy
katalog w configu, bez zmian w kodzie.

# Uruchomienie

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

## Podgląd wyników (GUI, opcjonalnie)

Dokument z `input/` (po lewej) obok wyniku JSON z `output/` (po prawej), w przeglądarce; lista wszystkich
dokumentów ze statusem wyniku, przechodzenie strzałkami ←/→, szczegóły decyzji (typ, uzasadnienie
klasyfikacji, strony z OCR). Gdy dokument nie ma wyniku w `output/`, komenda i podgląd o tym informują.

```bash
bash /opt/solution/docs_JSONifyer/deploy/view.sh /opt/solution/input/<plik>   # albo bez argumentu: lista
```

Podgląd jest dostępny tylko na serwerze (127.0.0.1:8000) — z własnego komputera przez tunel SSH:
`ssh -L 8000:localhost:8000 <użytkownik>@<adres-VM>`, potem adres z tokenem wypisany przez komendę.
Opcja `--public` udostępnia go na otwartym porcie 8000 VM (adres z losowym tokenem). Ctrl+C kończy.
Lokalnie (bez Dockera): `python -m odw2json view input/<plik>` — otwiera przeglądarkę.

## Diagnostyka (opcjonalnie)

```bash
docker compose -f /opt/solution/docs_JSONifyer/docker-compose.yml run --rm odw2json python -m odw2json check     # config, dostawcy LLM
docker compose -f /opt/solution/docs_JSONifyer/docker-compose.yml run --rm odw2json python -m tools.check_output  # czy każdy plik ma wynik
```
