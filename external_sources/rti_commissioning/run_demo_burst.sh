#!/usr/bin/env bash
#
# Demo helper: stream a commissioning-telemetry burst to the Eventstream so the
# Real-Time Dashboard (rtdCommissioning) and Activator (actCommissioningAlarms)
# light up live. ET-1001 ramps healthy -> warning -> alarm across the run.
#
# Usage (from anywhere in WSL):
#   ./run_demo_burst.sh              # default 180s run, 2s tick
#   ./run_demo_burst.sh 90           # 90s run  (alarm arrives faster)
#   ./run_demo_burst.sh 300 3        # 300s run, 3s tick
#
# Kick it off, then bring Fabric to the foreground and present while it streams.
# Stop early anytime with Ctrl-C.
set -euo pipefail

SECONDS_RUN="${1:-180}"
INTERVAL="${2:-2}"

# Resolve paths relative to this script so it works from any cwd.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PY="$SCRIPT_DIR/../../.venv/bin/python"
cd "$SCRIPT_DIR"

if [[ ! -x "$VENV_PY" ]]; then
  echo "ERROR: repo venv not found at $VENV_PY" >&2
  echo "Run from the cloned repo so ../../.venv exists." >&2
  exit 1
fi

# Reuse an already-exported connection string, else fetch it from Fabric
# (uses your az login; nothing secret is printed or stored).
if [[ -z "${ES_CONNECTION_STRING:-}" ]]; then
  echo "Resolving Eventstream endpoint via Fabric (az login)..."
  ES_CONNECTION_STRING="$("$VENV_PY" create_eventstream.py --endpoint \
    | "$VENV_PY" -c 'import sys,json; s=sys.stdin.read(); print(json.loads(s[s.find(chr(123)):])["accessKeys"]["primaryConnectionString"])')"
  export ES_CONNECTION_STRING
fi

if [[ -z "${ES_CONNECTION_STRING:-}" ]]; then
  echo "ERROR: could not resolve ES_CONNECTION_STRING." >&2
  exit 1
fi

# Preflight: make sure the Eventstream's Eventhouse destination isn't paused.
# A paused destination silently drops telemetry (events enter the Eventstream but
# never land in the KQL table), so the Activator never fires. Auto-resume it.
echo "Preflight: ensuring Eventstream destination is running..."
"$VENV_PY" create_eventstream.py --ensure-running || \
  echo "  (preflight check failed; continuing anyway)"

echo "Streaming ~${SECONDS_RUN}s (tick ${INTERVAL}s). ET-1001 will ramp to alarm."
echo "Tip: open rtdCommissioning first; the email fires ~1-2 min after alarm."
echo
exec "$VENV_PY" produce_telemetry.py --seconds "$SECONDS_RUN" --interval "$INTERVAL"
