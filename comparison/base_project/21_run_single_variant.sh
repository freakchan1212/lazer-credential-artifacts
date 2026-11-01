#!/usr/bin/env bash
# Switch to a specific optimization variant (V0..V5), rebuild, and run full correctness + security + performance benchmarks.
# Usage:
#   bash 21_run_single_variant.sh <VARIANT_ID> [SESSIONS] [EXTRA_ARGS...]
# Examples:
#   bash 21_run_single_variant.sh V0 30 --cpu 2
#   bash 21_run_single_variant.sh V1 30 --cpu 2
#   bash 21_run_single_variant.sh V5 30 --cpu 2
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

VARIANT="${1:-V0}"
shift || true
SESSIONS="${1:-30}"
shift || true

echo "================================================================================"
echo "[1/5] Switching active code to variant: $VARIANT"
echo "================================================================================"
python3 "$ROOT/switch_variant.py" "$VARIANT"

echo "================================================================================"
echo "[2/5] Rebuilding C shared library & Python CFFI bindings for $VARIANT"
echo "================================================================================"
bash "$ROOT/06_rebuild_fast.sh"

echo "================================================================================"
echo "[3/5] Running Correctness Audit Suite (static checks + smoke + C blindsig demo)"
echo "================================================================================"
bash "$ROOT/10_audit_correctness.sh"

echo "================================================================================"
echo "[4/5] Running Security Negative & Boundary Suite (9 attack cases + H2 + strict=True)"
echo "================================================================================"
bash "$ROOT/11_audit_security.sh"

echo "================================================================================"
echo "[5/5] Running Performance & 92/92 Acceptance Benchmark ($SESSIONS sessions)"
echo "================================================================================"
bash "$ROOT/12_audit_performance.sh" "$SESSIONS" "$@"

python3 "$ROOT/compare_all_variants.py" || true
echo "================================================================================"
echo "VARIANT $VARIANT COMPLETED SUCCESSFULLY!"
echo "================================================================================"
