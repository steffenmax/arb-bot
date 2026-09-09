#!/usr/bin/env bash
# Launch the NFL survivor pool dashboard.
#
#   ./survivor/start.sh              # first free port from 8765, opens a browser
#   ./survivor/start.sh --port 9000  # a specific port
#   ./survivor/start.sh --no-open    # do not open a browser
#
# Installs the three Python dependencies into survivor/.venv the first time if
# they are not already importable. Nothing else is written outside the repo.
# Before opening a browser it waits for the server and builds the plan once, so
# any data or network problem is reported here in the terminal.
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$REPO/survivor/.venv"
REQ="$REPO/survivor/requirements.txt"
PORT=""
OPEN=1
EXTRA=()

while [ $# -gt 0 ]; do
  case "$1" in
    --port) PORT="$2"; shift 2 ;;
    --port=*) PORT="${1#*=}"; shift ;;
    --no-open) OPEN=0; shift ;;
    -h|--help) sed -n '2,11p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) EXTRA+=("$1"); shift ;;
  esac
done

command -v python3 >/dev/null 2>&1 || { echo "survivor: python3 is required but not on PATH." >&2; exit 1; }

# ---- interpreter: reuse the venv if it exists, else the system python --------
PY="python3"
[ -x "$VENV/bin/python" ] && PY="$VENV/bin/python"

if ! "$PY" -c "import pandas, numpy, scipy, certifi" >/dev/null 2>&1; then
  echo "survivor: installing dependencies (pandas, numpy, scipy). This takes a minute the first time..."
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
if [ -n "$PORT" ]; then
  CHOSEN="$PORT"
else
  CHOSEN="$("$PY" - 8765 <<'PYEOF'
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
)" || { echo "survivor: no free port in 8765-8804." >&2; exit 1; }
  [ "$CHOSEN" != "8765" ] && echo "survivor: port 8765 is busy, using $CHOSEN."
fi

URL="http://127.0.0.1:$CHOSEN"

# ---- start the server -------------------------------------------------------
cd "$REPO"
"$PY" -m survivor.dashboard --port "$CHOSEN" ${EXTRA+"${EXTRA[@]}"} &
SERVER_PID=$!
cleanup() { kill "$SERVER_PID" >/dev/null 2>&1; }
trap cleanup INT TERM EXIT

# ---- wait for it, then build the plan once so problems surface here ---------
"$PY" - "$URL" "$SERVER_PID" "$OPEN" <<'PYEOF'
import json, os, sys, time, urllib.error, urllib.request

url, pid, want_open = sys.argv[1], int(sys.argv[2]), sys.argv[3] == "1"

def alive():
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False

deadline = time.time() + 30
while time.time() < deadline:
    if not alive():
        print("survivor: the server exited during startup. The lines above say why.", file=sys.stderr)
        sys.exit(1)
    try:
        with urllib.request.urlopen(url + "/api/health", timeout=2):
            break
    except Exception:
        time.sleep(0.3)
else:
    print(f"survivor: the server did not answer at {url} within 30s.", file=sys.stderr)
    sys.exit(1)

print("survivor: loading NFL data (first run downloads about 15 MB)...")
req = urllib.request.Request(url + "/api/dashboard", data=b"{}",
                             headers={"Content-Type": "application/json"}, method="POST")
try:
    started = time.time()
    with urllib.request.urlopen(req, timeout=300) as resp:
        payload = json.load(resp)
    meta = payload.get("meta", {})
    took = time.time() - started
    print(f"survivor: ready in {took:.0f}s — {meta.get('season')} week {meta.get('currentWeek')}, "
          f"{len(payload.get('games', []))} games, {len(payload.get('entries', []))} entries.")
    for w in meta.get("warnings", []):
        print(f"survivor: warning — {w}")
except urllib.error.HTTPError as e:
    try:
        detail = json.load(e).get("error", "")
    except Exception:
        detail = e.reason
    print(f"survivor: the server started but could not build the plan.\n"
          f"          {detail}\n"
          f"          Most often this is no internet access to github.com or espn.com.\n"
          f"          The page will keep retrying; fix the connection and it recovers.", file=sys.stderr)
except Exception as e:
    print(f"survivor: could not reach {url} after startup: {e}", file=sys.stderr)

if want_open:
    import webbrowser
    webbrowser.open(url + "/")

print(f"survivor: open {url}/   (Ctrl+C here to stop)")
PYEOF

wait "$SERVER_PID"
