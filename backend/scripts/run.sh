#!/usr/bin/env bash
# Create venv if missing, install deps, run ingestion script. Use from repo root.
set -e
cd "$(dirname "$0")/.."
VENV=".venv"
if [[ ! -d "$VENV" ]]; then
  python3 -m venv "$VENV"
fi
"$VENV/bin/pip" install -q -r requirements.txt
"$VENV/bin/python" scripts/run_ingestion.py "$@"
