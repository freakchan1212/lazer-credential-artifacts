#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
mkdir -p logs results
start_log() {
  LOGFILE="$ROOT/logs/$1_$(date +%Y%m%d_%H%M%S)_$$.log"
  exec > >(tee "$LOGFILE") 2>&1
  trap 'rc=$?; if ((rc)); then echo "FAILED (exit=$rc). Log: $LOGFILE"; fi' EXIT
  echo "Log: $LOGFILE"
}
choose_python() {
  if [[ -n "${PYTHON_BIN:-}" ]]; then
    PY="$PYTHON_BIN"
  elif [[ -x /usr/bin/python3 ]]; then
    PY=/usr/bin/python3
  else
    PY=python3
  fi
}
