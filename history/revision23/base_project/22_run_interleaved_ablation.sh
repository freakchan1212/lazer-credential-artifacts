#!/usr/bin/env bash
# Interleaved (Round-Robin / ABBA) Multi-Round Ablation Runner for lazer-baseline-Google-E2.
# Addresses reviewer recommendation (Section 5.4) to eliminate thermal drift and random retry variance
# by running ROUNDS interleaved rounds across all variants on a pinned P-Core.
#
# Usage:
#   bash 22_run_interleaved_ablation.sh [ROUNDS] [SESSIONS_PER_ROUND] [EXTRA_ARGS...]
# Example:
#   bash 22_run_interleaved_ablation.sh 3 30 --cpu 2
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

ROUNDS="${1:-3}"
shift || true
SESSIONS="${1:-30}"
shift || true

VARIANT_LIST="${LAZER_VARIANTS:-B0 B1 V0 V1 V2 V3A V3 V4 V5}"

python3 "$ROOT/switch_variant.py" --export-all-patches
python3 "$ROOT/verify_e2_all.py"

for ((r=1; r<=ROUNDS; r++)); do
  echo "################################################################################"
  echo "### Interleaved Round $r / $ROUNDS (Sessions per round: $SESSIONS)"
  echo "################################################################################"
  if (( r % 2 == 1 )); then
    ORDER="$VARIANT_LIST"
  else
    # Reverse order (ABBA) on even rounds to cancel monotonic thermal drift
    ORDER="$(echo "$VARIANT_LIST" | awk '{for(i=NF;i>=1;i--) printf "%s ", $i}')"
  fi
  for V in $ORDER; do
    bash "$ROOT/21_run_single_variant.sh" "$V" "$SESSIONS" "$@"
  done
done

python3 "$ROOT/compare_all_variants.py"
python3 "$ROOT/switch_variant.py" V0
bash "$ROOT/06_rebuild_fast.sh"
bash "$ROOT/04_collect_results.sh"
echo "INTERLEAVED_ABLATION_COMPLETED"
