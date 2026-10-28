#!/usr/bin/env bash
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
"$ROOT/.venv/bin/python3" "$ROOT/collect_results.py"
