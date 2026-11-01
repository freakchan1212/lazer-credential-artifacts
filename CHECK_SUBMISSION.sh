#!/usr/bin/env bash
set -euo pipefail
TASK_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TASK_OUTPUT="${1:-$(dirname "$TASK_ROOT")/recomputed_comparison_$(date +%Y%m%d_%H%M%S)}"
cd "$TASK_ROOT"
python3 tools/verify_submission.py
python3 tools/recompute_comparison.py --output "$TASK_OUTPUT"

