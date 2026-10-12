#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
export PYTHONPATH="$PWD/src"
export LIVE_TRADING=false
alpha_python=python3
if [[ -x .venv/bin/python ]]; then alpha_python=.venv/bin/python; fi
exec "$alpha_python" -m pm_alpha --root "$PWD" research-loop --open-browser "$@"
