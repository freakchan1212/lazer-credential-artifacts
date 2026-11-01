#!/usr/bin/env bash
set -euo pipefail
TASK_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$TASK_ROOT"
TASK_PYTHON_BIN="${TASK_PYTHON_BIN:-/usr/bin/python3}"
TASK_PYTHON_ABI="$("$TASK_PYTHON_BIN" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
sudo apt-get update
sudo apt-get install -y build-essential clang cmake autoconf automake libtool m4 \
  libgmp-dev libmpfr-dev libntl-dev libffi-dev \
  "python${TASK_PYTHON_ABI}-dev" "python${TASK_PYTHON_ABI}-venv" unzip patch
"$TASK_PYTHON_BIN" -m venv .venv
.venv/bin/python -m pip install 'cffi>=1.15,<3' 'setuptools>=68,<83' wheel
export REV_GCC_CC="${REV_GCC_CC:-/usr/bin/gcc}"
export REV_GCC_CXX="${REV_GCC_CXX:-/usr/bin/g++}"
export REV_CLANG_CC="${REV_CLANG_CC:-/usr/bin/clang}"
export REV_CLANG_CXX="${REV_CLANG_CXX:-/usr/bin/clang++}"
if [ "$#" -eq 0 ]; then set -- --mode full --jobs 4 --cpu 0; fi
exec .venv/bin/python run_two_baselines.py "$@"
