#!/usr/bin/env bash
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
start_log check_env
choose_python
echo "=== Host and compiler ==="
uname -a
for tool in gcc g++ make unzip patch; do
  command -v "$tool" || { echo "Missing $tool. See README_ZH.md dependency command."; exit 1; }
  if [[ "$tool" == unzip ]]; then
    unzip -v | sed -n '1p'
  else
    "$tool" --version | sed -n '1p'
  fi
done
if command -v cmake >/dev/null 2>&1; then
  cmake --version | sed -n '1p'
else
  echo "cmake not found in PATH; build_backend.sh will use direct GCC/G++ fallback builder."
fi
"$PY" - <<'PY'
import sys, platform, sysconfig
from pathlib import Path
print('Python:', sys.executable, sys.version)
print('Machine:', platform.machine())
if sys.version_info < (3,10): raise SystemExit('Python >= 3.10 required')
if platform.machine() != 'x86_64': raise SystemExit('Upstream baseline requires Linux x86_64')
if not Path(sysconfig.get_paths()['include'], 'Python.h').is_file():
    raise SystemExit('Python development headers missing; install matching python3-dev')
text = Path('/proc/cpuinfo').read_text()
flags = next((x.split(':',1)[1].split() for x in text.splitlines() if x.startswith('flags')), [])
missing = sorted(set(['avx2','aes','fma']) - set(flags))
print('AVX-512 present (optional for anon_cred):', 'avx512f' in flags)
print('Required CPU extensions missing:', missing)
if missing: raise SystemExit('This build requires AVX2, AES and FMA. Send this log if any are missing.')
PY
if ! printf '#include <gmp.h>\n#include <mpfr.h>\n' | gcc -x c -E - >/dev/null 2>&1; then
  if [[ -f "$ROOT/.deps/include/gmp.h" && -f "$ROOT/.deps/include/mpfr.h" ]]; then
    export CPATH="$ROOT/.deps/include${CPATH:+:$CPATH}"
    export LIBRARY_PATH="$ROOT/.deps/lib${LIBRARY_PATH:+:$LIBRARY_PATH}"
  else
    echo "System <gmp.h>/<mpfr.h> not in /usr/include; build_backend.sh will check .deps fallback."
  fi
fi
gcc -dumpfullversion
echo "Upstream recommended: GCC >=13.2, CMake >=3.26. Older installed versions may work; build log is authoritative."
echo "ENVIRONMENT_CHECK_PASSED"
