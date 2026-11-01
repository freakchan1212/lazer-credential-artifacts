#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")"
[[ -x .venv/bin/python3 ]] || { echo 'Build first';exit 2; }
SESSIONS="${1:-30}"
shift || true
.venv/bin/python3 experiment.py --mode pilot --sessions "$SESSIONS" "$@"
.venv/bin/python3 acceptance.py
.venv/bin/python3 regression_compare.py
