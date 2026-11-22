#!/usr/bin/env bash
# Podgląd wyników na VM: dokument z /opt/solution/input obok wyniku JSON z /opt/solution/output (przeglądarka).
#
#   bash deploy/view.sh /opt/solution/input/<plik>        # jeden dokument (+ lista pozostałych)
#   bash deploy/view.sh                                    # lista wszystkich dokumentów
#   opcje: --port 8000   --public (dostęp z internetu przez otwarty port VM; adres z tokenem)
#
# Domyślnie podgląd jest dostępny tylko na samym serwerze (127.0.0.1) — to dokumenty z akt, nie wystawiamy
# ich publicznie. Z laptopa: w osobnym terminalu tunel SSH, potem adres wypisany przez komendę:
#   ssh -L 8000:localhost:8000 <user>@<adres-VM>
# Ctrl+C kończy podgląd (kontener jest usuwany).
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
SOL="${SOLUTION_DIR:-$(dirname "$REPO")}"

TARGET="$SOL/input"
PORT=8000
BIND=127.0.0.1
URL_HOST=localhost
while [ $# -gt 0 ]; do
  case "$1" in
    --public) BIND=0.0.0.0 ;;
    --port) PORT="$2"; shift ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) TARGET="$1" ;;
  esac
  shift
done

ABS="$(realpath -- "$TARGET" 2>/dev/null || true)"
case "$ABS" in
  "$SOL/input"|"$SOL/input/"*) ;;
  *) echo "Plik musi leżeć w $SOL/input (podano: $TARGET)" >&2; exit 2 ;;
esac
if [ ! -e "$ABS" ]; then
  echo "Nie ma takiego pliku: $TARGET" >&2
  exit 2
fi
REL="${ABS#"$SOL/"}"   # input/… — ścieżka w kontenerze (docker-compose.yml montuje $SOL/input jako /app/input)

if [ "$BIND" = 0.0.0.0 ]; then
  # publiczny adres VM z usługi metadanych Azure (wewnętrzny adres 169.254.169.254); inaczej symbol zastępczy
  URL_HOST="$(curl -s -m 2 -H Metadata:true "http://169.254.169.254/metadata/instance/network/interface/0/ipv4/ipAddress/0/publicIpAddress?api-version=2021-02-01&format=text" || true)"
  URL_HOST="${URL_HOST:-<adres-VM>}"
  echo "UWAGA: podgląd dostępny z internetu (port $PORT) dla każdego, kto ma adres z tokenem."
else
  echo "Podgląd tylko na tym serwerze. Z laptopa najpierw: ssh -L $PORT:localhost:$PORT $(whoami)@<adres-VM>"
fi

exec docker compose -f "$REPO/docker-compose.yml" run --rm -p "$BIND:$PORT:8000" odw2json \
  python -m odw2json view "$REL" --host 0.0.0.0 --port 8000 --no-browser --url-host "$URL_HOST" --url-port "$PORT"
