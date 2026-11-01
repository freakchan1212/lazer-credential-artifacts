#!/usr/bin/env bash
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
start_log smoke_metrics
[[ -x "$ROOT/.venv/bin/python3" ]] || { echo 'Run bash 01_build.sh first'; exit 1; }
cd "$ROOT/lazer/python/anon_cred"
"$ROOT/.venv/bin/python3" -u anon_cred.py
cd "$ROOT"
"$ROOT/.venv/bin/python3" -u experiment.py --mode smoke "$@"
"$ROOT/.venv/bin/python3" "$ROOT/acceptance.py"
echo SMOKE_METRICS_PASSED
