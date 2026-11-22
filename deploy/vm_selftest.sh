#!/usr/bin/env bash
# Test na VM dokładnie tak, jak zrobią to oceniający (docs/05_wdrozenie_vm.md, krok 7):
#   1) czyści input/, output/ i trace/,
#   2) kopiuje paczkę testową selftest/input/ do input/ (paczka: python -m tools.make_selftest na laptopie + scp),
#   3) uruchamia z /opt/solution PIERWSZĄ komendę z bloku ```bash w RUN.md (przez sudo, jak oceniający),
#   4) sprawdza, czy każdy plik ma poprawny wynik, i liczy F1 względem selftest/expected/.
# Uruchomienie:  bash deploy/vm_selftest.sh            (opcja --fresh: także bez cache OCR/LLM — pomiar czasu)
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -d selftest/input ]; then
  echo "Brak selftest/input — skopiuj paczkę z laptopa: scp -r selftest <user>@<vm>:/opt/solution/" >&2
  exit 1
fi

CMD=$(awk '/^```bash/{f=1; next} /^```/{if (f) exit} f && NF {print; exit}' RUN.md)
if [ -z "$CMD" ]; then
  echo "Nie znalazłem komendy w RUN.md (pierwsza linia bloku \`\`\`bash)" >&2
  exit 1
fi

echo "== czyszczenie input/, output/, trace/"
sudo find input output -mindepth 1 -delete
sudo rm -rf trace
if [ "${1:-}" = "--fresh" ]; then
  echo "== bez cache (.cache/) — pomiar czasu jak przy pierwszym uruchomieniu"
  sudo rm -rf .cache
fi
cp -r selftest/input/. input/
echo "== plików w input/: $(find input -type f | wc -l)"

echo "== komenda z RUN.md (przez sudo, z $(pwd)): $CMD"
start=$(date +%s)
if sudo bash -c "$CMD"; then rc=0; else rc=$?; fi
echo "== kod wyjścia: $rc, czas: $(( $(date +%s) - start )) s"

echo "== sprawdzenie wyników"
docker compose run --rm odw2json python -m tools.check_output --expected selftest/expected
