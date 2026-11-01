#!/usr/bin/env bash
# Sequentially verify and benchmark the full E2 variant ladder:
#   - Step 0: Run verify_e2_all.py (fixed-coin byte equivalence across B1..V4, V3 poly_scale 64-bit boundary,
#             V1 40-instance dynamic cache, V5 k=0..8 all-cardinality subspace projection)
#   - Step 1: Benchmark B0 (pristine upstream + hooks), B1 (bugfix-only), and V0..V5 under identical CPU affinity
#   - Step 2: Generate dynamic comparison report (compare_all_variants.py) and package results ZIP
#
# Usage:
#   bash 20_run_all_6_variants.sh [SESSIONS] [EXTRA_ARGS...]
# Example (recommended on i5-13400F P-Core 2):
#   bash 20_run_all_6_variants.sh 30 --cpu 2
# To run a subset of variants:
#   LAZER_VARIANTS="B0 B1 V0 V1 V2 V3 V4 V5" bash 20_run_all_6_variants.sh 30 --cpu 2
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

SESSIONS="${1:-30}"
shift || true

VARIANT_LIST="${LAZER_VARIANTS:-B0 B1 V0 V1 V2 V3A V3 V4 V5}"

python3 "$ROOT/switch_variant.py" --export-all-patches

echo "================================================================================"
echo "[0/3] Running E2 Differential, Boundary & Cross-Variant Verification Suite..."
echo "================================================================================"
python3 "$ROOT/verify_e2_all.py"

for V in $VARIANT_LIST; do
  bash "$ROOT/21_run_single_variant.sh" "$V" "$SESSIONS" "$@"
done

echo "================================================================================"
echo "Generating Unified Multi-Variant Performance & Dynamic Security Report..."
echo "================================================================================"
python3 "$ROOT/compare_all_variants.py"

# Restore default variant V0 so repository state matches lazer-baseline-Google-E2 default
python3 "$ROOT/switch_variant.py" V0
bash "$ROOT/06_rebuild_fast.sh"

bash "$ROOT/04_collect_results.sh"
echo "ALL_VARIANTS_BENCHMARK_AND_COLLECTION_COMPLETED"
