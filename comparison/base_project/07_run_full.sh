#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
"$ROOT/.venv/bin/python3" "$ROOT/experiment.py" --mode full --sessions "${1:-1000}" "${@:2}"
"$ROOT/.venv/bin/python3" "$ROOT/acceptance.py"
