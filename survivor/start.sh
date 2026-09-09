#!/usr/bin/env bash
# Launch the NFL survivor pool dashboard.
#
#   ./survivor/start.sh              # first free port from 8765, opens a browser
#   ./survivor/start.sh --port 9000  # a specific port
#   ./survivor/start.sh --no-open    # do not open a browser
#
# Installs the three Python dependencies into survivor/.venv the first time if
# they are not already importable. Nothing else is written outside the repo.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$REPO/survivor/.venv"
REQ="$REPO/survivor/requirements.txt"
PORT=""
OPEN="--open"
EXTRA=()

while [ $# -gt 0 ]; do
  case "$1" in
    --port) PORT="$2"; shift 2 ;;
    --port=*) PORT="${1#*=}"; shift ;;
    --no-open) OPEN=""; shift ;;
    -h|--help) sed -n '2,9p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) EXTRA+=("$1"); shift ;;
  esac
done

command -v python3 >/dev/null 2>&1 || { echo "survivor: python3 is required but not on PATH." >&2; exit 1; }

# ---- interpreter: reuse the venv if it exists, else the system python --------
PY="python3"
[ -x "$VENV/bin/python" ] && PY="$VENV/bin/python"

if ! "$PY" -c "import pandas, numpy, scipy" >/dev/null 2>&1; then
  echo "survivor: installing dependencies (pandas, numpy, scipy)..."
  if ! python3 -m venv "$VENV" >/dev/null 2>&1; then
    echo "survivor: could not create a virtualenv at $VENV." >&2
    echo "          Install python3-venv, or run: pip install -r $REQ" >&2
    exit 1
  fi
  PY="$VENV/bin/python"
  "$PY" -m pip install --quiet --upgrade pip >/dev/null 2>&1 || true
  if ! "$PY" -m pip install --quiet -r "$REQ"; then
    echo "survivor: dependency install failed. Try: $PY -m pip install -r $REQ" >&2
    exit 1
  fi
  echo "survivor: dependencies ready."
fi

# ---- port: use the requested one, or the first free port from 8765 ----------
free_port() {
  "$PY" - "$1" <<'PYEOF'
import socket, sys
start = int(sys.argv[1])
for port in range(start, start + 40):
    with socket.socket() as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", port))
        except OSError:
            continue
    print(port)
    break
else:
    sys.exit(1)
PYEOF
}

if [ -n "$PORT" ]; then
  CHOSEN="$PORT"
else
  CHOSEN="$(free_port 8765)" || { echo "survivor: no free port in 8765-8804." >&2; exit 1; }
  [ "$CHOSEN" != "8765" ] && echo "survivor: port 8765 is busy, using $CHOSEN."
fi

echo "survivor: starting on http://127.0.0.1:$CHOSEN  (Ctrl+C to stop)"
cd "$REPO"
exec "$PY" -m survivor.dashboard --port "$CHOSEN" $OPEN ${EXTRA+"${EXTRA[@]}"}
