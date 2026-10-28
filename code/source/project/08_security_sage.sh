#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
if ! command -v sage >/dev/null; then
  echo 'SageMath is not installed. The declared generic GSA/Core-SVP model still runs via bash 06_security.sh.'
  echo 'For an actual estimator scan on Ubuntu: sudo apt install sagemath'
  echo 'Then run bash 08_security_sage.sh (or append --all-attacks).'
  exit 2
fi
mkdir -p logs
sage -python security_sage.py "$@" 2>&1 | tee "logs/security_sage_$(date +%Y%m%d_%H%M%S).log"
