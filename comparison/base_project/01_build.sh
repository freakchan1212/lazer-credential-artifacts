#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
if [[ -z "${PYTHON_BIN:-}" ]]; then
  if [[ -x /usr/bin/python3.10 ]]; then export PYTHON_BIN=/usr/bin/python3.10
  else export PYTHON_BIN=/usr/bin/python3; fi
fi
"$PYTHON_BIN" prepare_sources.py
bash 05_build_compatible.sh
"$ROOT/.venv/bin/python3" security_audit.py --output "$ROOT/results/security_static"
echo EXPERIMENT_BUILD_PASSED
