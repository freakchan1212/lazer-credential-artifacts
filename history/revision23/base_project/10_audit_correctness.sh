#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")"
python3 audit_tests.py
if [[ ! -x .venv/bin/python3 ]]; then echo 'NATIVE_NOT_BUILT: bash 01_build.sh first';exit 2;fi
bash 02_run_smoke.sh
# Run native C blind signature demo to verify blindsig.c norm loop fix at runtime.
if [[ ! -x lazer/demos/blindsig/blindsig-demo ]]; then
  echo 'C_BLINDSIG_NATIVE_DEMO_MISSING: rebuild with bash 01_build.sh or bash 05_build_compatible.sh'
  exit 1
fi
echo "=== Running C blind signature native demo (lazer/demos/blindsig/blindsig-demo) ==="
timeout 120 lazer/demos/blindsig/blindsig-demo
echo "C_BLINDSIG_NATIVE_DEMO_PASSED"
