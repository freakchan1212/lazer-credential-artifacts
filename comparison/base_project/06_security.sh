#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
"$ROOT/.venv/bin/python3" "$ROOT/security_audit.py" --output "$ROOT/results/security_static"
