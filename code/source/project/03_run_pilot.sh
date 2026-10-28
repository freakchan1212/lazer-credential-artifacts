#!/usr/bin/env bash
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
start_log pilot_metrics
"$ROOT/.venv/bin/python3" -u "$ROOT/experiment.py" --mode pilot --sessions "${1:-30}" "${@:2}"
"$ROOT/.venv/bin/python3" "$ROOT/acceptance.py"
echo PILOT_METRICS_PASSED
