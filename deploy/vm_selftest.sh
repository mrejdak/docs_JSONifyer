#!/usr/bin/env bash
# Test na VM dokładnie tak, jak zrobią to oceniający (docs/05_wdrozenie_vm.md, krok 7):
#   1) czyści /opt/solution/input i /opt/solution/output (oraz trace/ repozytorium),
#   2) kopiuje paczkę testową <repo>/selftest/input/ do /opt/solution/input/
#      (paczka: python -m tools.make_selftest na laptopie + scp do <repo>/selftest),
#   3) uruchamia z /opt/solution PIERWSZĄ komendę z bloku ```bash w /opt/solution/RUN.md (przez sudo),
#   4) sprawdza, czy każdy plik ma poprawny wynik, i liczy F1 względem selftest/expected/.
# Uruchomienie:  bash deploy/vm_selftest.sh            (--fresh: także bez cache OCR/LLM — pomiar czasu)
# Układ: repozytorium = katalog nad tym skryptem; katalog rozwiązania = jego rodzic (zmienna SOLUTION_DIR).
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
SOL="${SOLUTION_DIR:-$(dirname "$REPO")}"

if [ ! -d "$REPO/selftest/input" ]; then
  echo "Brak $REPO/selftest/input — skopiuj paczkę z laptopa: scp -r selftest <user>@<vm>:$REPO/" >&2
  exit 1
fi
# komenda: pierwsza niepusta linia bloku ```bash, a bez bloku — pierwsza linia zaczynająca się od „docker”/„sudo docker”
CMD=$(awk '/^```bash/{f=1; next} /^```/{if (f) exit} f && NF {print; exit}' "$SOL/RUN.md")
[ -n "$CMD" ] || CMD=$(grep -m1 -E '^[[:space:]]*(sudo[[:space:]]+)?docker[[:space:]]' "$SOL/RUN.md" | sed -E 's/^[[:space:]]+//' || true)
if [ -z "$CMD" ]; then
  echo "Nie znalazłem komendy w $SOL/RUN.md" >&2
  exit 1
fi

echo "== czyszczenie $SOL/input, $SOL/output, trace/"
sudo find "$SOL/input" "$SOL/output" -mindepth 1 -delete
sudo rm -rf "$REPO/trace"
if [ "${1:-}" = "--fresh" ]; then
  echo "== bez cache (.cache/) — pomiar czasu jak przy pierwszym uruchomieniu"
  sudo rm -rf "$REPO/.cache"
fi
cp -r "$REPO/selftest/input/." "$SOL/input/"
echo "== plików w input/: $(find "$SOL/input" -type f | wc -l)"

echo "== komenda z RUN.md (przez sudo, z $SOL): $CMD"
cd "$SOL"
start=$(date +%s)
if sudo bash -c "$CMD"; then rc=0; else rc=$?; fi
echo "== kod wyjścia: $rc, czas: $(( $(date +%s) - start )) s"

echo "== sprawdzenie wyników"
docker compose -f "$REPO/docker-compose.yml" run --rm odw2json python -m tools.check_output --expected selftest/expected
