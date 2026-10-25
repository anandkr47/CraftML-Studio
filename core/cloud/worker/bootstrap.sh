#!/usr/bin/env bash
# CraftML remote worker bootstrap. Runs on the GPU host (Linux), inside the extracted bundle.
set -euo pipefail
cd "$(dirname "$0")"

PY="${CRAFTML_PYTHON:-python3}"
if [ "${CRAFTML_USE_VENV:-1}" = "1" ]; then
  # --system-site-packages reuses torch from the base image instead of re-downloading it.
  [ -d .venv ] || "$PY" -m venv --system-site-packages .venv
  PY=".venv/bin/python"
fi

"$PY" -c "import torch" 2>/dev/null || "$PY" -m pip install --quiet --disable-pip-version-check torch
"$PY" -m pip install --quiet --disable-pip-version-check -r requirements.txt

exec "$PY" worker_main.py --job "${CRAFTML_JOB_FILE:-job.json}" "$@"
