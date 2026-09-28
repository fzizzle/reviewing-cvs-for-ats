#!/usr/bin/env bash
# Create (or update) the CV ATS toolkit venv. Prints the venv path.
set -euo pipefail
VENV="${CV_ATS_VENV:-$HOME/.cache/cv-ats/venv}"
if [ ! -x "$VENV/bin/python" ]; then
  mkdir -p "$(dirname "$VENV")"
  python3 -m venv "$VENV"
fi
"$VENV/bin/pip" install -q --upgrade pip
"$VENV/bin/pip" install -q -r "$(cd "$(dirname "$0")" && pwd)/requirements.txt"
echo "$VENV"
