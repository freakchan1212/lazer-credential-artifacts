#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
[[ -f UPSTREAM_SHA256.json && -f 01_build.sh ]] || {
  echo 'Extract this patch into BLNS_LAZER_BASELINE_20261014 first.'; exit 1;
}
if [[ -z "${PYTHON_BIN:-}" ]]; then
  if [[ -x /usr/bin/python3.10 ]]; then
    export PYTHON_BIN=/usr/bin/python3.10
  else
    export PYTHON_BIN=/usr/bin/python3
  fi
fi
[[ -x "$PYTHON_BIN" ]] || { echo "Python not found: $PYTHON_BIN"; exit 1; }
bash 00_check_env.sh
"$PYTHON_BIN" verify_baseline.py
mkdir -p .compat-bin logs
# Append the CPU profile AFTER upstream -march=native. No protocol source edits.
for tool in gcc g++; do
  [[ -x "/usr/bin/$tool" ]] || { echo "Missing /usr/bin/$tool"; exit 1; }
  cat > ".compat-bin/$tool" <<EOF
#!/usr/bin/env bash
exec /usr/bin/$tool "\$@" -march=x86-64 -mtune=generic -mavx2 -maes -mfma -mno-avx512f
EOF
  chmod +x ".compat-bin/$tool"
done
export CC="$ROOT/.compat-bin/gcc" CXX="$ROOT/.compat-bin/g++"
export PATH="$ROOT/.compat-bin:$PATH"
# Remove only reproducible build outputs; keep sources, parameters and old logs.
"$PYTHON_BIN" - <<'PY'
from pathlib import Path
import shutil
root = Path.cwd()
lazer = root / 'lazer'
optional = sorted(lazer.glob('liblabrador*.so'))
if optional:
    raise SystemExit('Optional LaBRADOR libraries found. Use a fresh original baseline directory.')
for pattern in ('*.o', '*.so', '*.a'):
    for path in lazer.rglob(pattern):
        path.unlink()
demo_bin = lazer / 'demos' / 'blindsig' / 'blindsig-demo'
if demo_bin.exists():
    demo_bin.unlink()
for path in (root / '.build' / 'cpu_features',
             lazer / 'third_party' / 'hexl-development' / 'build'):
    if path.exists():
        shutil.rmtree(path)
PY
cat > logs/cpu_build_profile.txt <<'EOF'
profile=AVX2_AES_FMA_NO_AVX512
compiler_suffix=-march=x86-64 -mtune=generic -mavx2 -maes -mfma -mno-avx512f
parameters=variant_specific; see ACTIVE_VARIANT.json and PATCHES.json
performance_comparison=compare experiments using this same build profile
EOF
bash build_backend.sh
# Prevent silently accepting an accidental AVX-512 HEXL build.
HEXL_FLAGS=lazer/third_party/hexl-development/build/hexl/CMakeFiles/hexl.dir/flags.make
[[ -f "$HEXL_FLAGS" ]] || { echo 'HEXL compiler configuration missing'; exit 1; }
if grep -Eq -- '-DHEXL_HAS_AVX512(DQ|IFMA|VBMI2)([=[:space:]]|$)' "$HEXL_FLAGS"; then
  echo 'Unexpected AVX-512 HEXL configuration'; exit 1
fi
"$PYTHON_BIN" verify_baseline.py
echo COMPAT_BUILD_PASSED
