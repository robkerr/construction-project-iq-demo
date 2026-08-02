#!/usr/bin/env bash
# Convenience wrapper: run setup_bigquery_mirror.py inside a local virtualenv.
#
# Creates .venv on first run, installs requirements, then forwards all
# arguments to setup_bigquery_mirror.py.
#
# Examples:
#   ./run.sh --list-connections
#   ./run.sh --list-mirrored-databases --workspace <WORKSPACE_ID>
#   ./run.sh mirroring.yaml            # start mirroring + poll status
#   ./run.sh mirroring.yaml --status   # status only
#   ./run.sh mirroring.yaml --stop     # stop mirroring

set -euo pipefail
cd "$(dirname "$0")"

VENV_DIR=".venv"

if [ ! -d "${VENV_DIR}" ]; then
  echo "Creating virtualenv in ${VENV_DIR}..."
  python3 -m venv "${VENV_DIR}"
  "${VENV_DIR}/bin/pip" install --quiet --upgrade pip
  "${VENV_DIR}/bin/pip" install --quiet -r requirements.txt
fi

exec "${VENV_DIR}/bin/python" setup_bigquery_mirror.py "$@"
