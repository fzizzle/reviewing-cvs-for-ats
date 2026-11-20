#!/usr/bin/env bash
# Create (or update) the CV ATS toolkit venv. Prints the venv path.
# "$VENV/.cvats-ready" is written only after every dependency installed, so an interrupted or failed
# install is retried on the next cvats run instead of leaving a venv that looks usable but isn't.
set -euo pipefail
VENV="${CV_ATS_VENV:-$HOME/.cache/cv-ats/venv}"
REQ="$(cd "$(dirname "$0")" && pwd)/requirements.txt"
rm -f "$VENV/.cvats-ready"
if [ ! -x "$VENV/bin/python" ]; then
  mkdir -p "$(dirname "$VENV")"
  python3 -m venv "$VENV"
fi
"$VENV/bin/pip" install -q --upgrade pip
"$VENV/bin/pip" install -q -r "$REQ"
cp "$REQ" "$VENV/.cvats-ready"
echo "$VENV"
