#!/usr/bin/env bash
# Fast incremental rebuild after switching optimization variants via switch_variant.py.
# Uses content-addressed SHA-256 caching in .build/variant_cache/ so repeated variant switches
# (e.g. in interleaved ABBA runs or differential verification) are instantaneous while
# guaranteeing that every unique C source tree produces its own verified binary.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

HEXL_ARCHIVE="$ROOT/lazer/third_party/hexl-development/build/hexl/lib/libhexl.a"
if [[ ! -f "$HEXL_ARCHIVE" ]]; then
  HEXL_ARCHIVE="$ROOT/lazer/third_party/hexl-development/build/hexl/lib64/libhexl.a"
fi

if [[ ! -x "$ROOT/.venv/bin/python3" || ! -f "$HEXL_ARCHIVE" || ! -f "$ROOT/.deps/lib/libcpu_features.a" ]]; then
  echo "Initial dependencies not yet built; running full compatible build (05_build_compatible.sh)..."
  bash "$ROOT/05_build_compatible.sh"
  exit 0
fi

if [[ -d "$ROOT/.compat-bin" ]]; then
  export PATH="$ROOT/.compat-bin:$PATH"
fi
if [[ -d "$ROOT/.deps/include" ]]; then
  export CPATH="$ROOT/.deps/include${CPATH:+:$CPATH}"
  export LIBRARY_PATH="$ROOT/.deps/lib${LIBRARY_PATH:+:$LIBRARY_PATH}"
  export LD_LIBRARY_PATH="$ROOT/.deps/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi

export CC="${CC:-gcc}" CXX="${CXX:-g++}"

source "$ROOT/.venv/bin/activate"
python3 "$ROOT/verify_baseline.py"

SRC_HASH="$(sha256sum \
  "$ROOT/lazer/src/lazer.c" \
  "$ROOT/lazer/src/lin-proofs.c" \
  "$ROOT/lazer/src/lnp-quad.c" \
  "$ROOT/lazer/src/poly.c" \
  "$ROOT/lazer/src/rejection.c" \
  "$ROOT/lazer/src/blindsig.c" \
  "$ROOT/baseline_hooks.h" "$ROOT/06_rebuild_fast.sh" "$ROOT/lazer/lazer.h" | sha256sum | awk '{print $1}')"

CACHE_DIR="$ROOT/.build/variant_cache/$SRC_HASH"
mkdir -p "$CACHE_DIR"

if [[ -f "$CACHE_DIR/liblazer.so" && -f "$CACHE_DIR/liblazer.a" && -f "$CACHE_DIR/blindsig-demo" ]]; then
  cp -f "$CACHE_DIR/liblazer.so" "$ROOT/lazer/liblazer.so"
  cp -f "$CACHE_DIR/liblazer.a" "$ROOT/lazer/liblazer.a"
  cp -f "$CACHE_DIR/blindsig-demo" "$ROOT/lazer/demos/blindsig/blindsig-demo"
  chmod +x "$ROOT/lazer/demos/blindsig/blindsig-demo"
else
  "$CC" -DNDEBUG -Wall -Wextra -O3 -march=native -mtune=native -fomit-frame-pointer \
    -DFALCON_FPNATIVE -DFALCON_AVX2 -DFALCON_FMA \
    -I"$ROOT/lazer/third_party/Falcon-impl-20211101" -I"$ROOT/lazer" \
    -c -fPIC -o "$ROOT/lazer/src/lazer_shared.o" "$ROOT/lazer/src/lazer.c"

  FALCON_SHARED_OBJS=(
    "$ROOT/lazer/third_party/Falcon-impl-20211101/codec_shared.o"
    "$ROOT/lazer/third_party/Falcon-impl-20211101/common_shared.o"
    "$ROOT/lazer/third_party/Falcon-impl-20211101/falcon_shared.o"
    "$ROOT/lazer/third_party/Falcon-impl-20211101/fft_shared.o"
    "$ROOT/lazer/third_party/Falcon-impl-20211101/fpr_shared.o"
    "$ROOT/lazer/third_party/Falcon-impl-20211101/keygen_shared.o"
    "$ROOT/lazer/third_party/Falcon-impl-20211101/rng_shared.o"
    "$ROOT/lazer/third_party/Falcon-impl-20211101/shake_shared.o"
    "$ROOT/lazer/third_party/Falcon-impl-20211101/sign_shared.o"
    "$ROOT/lazer/third_party/Falcon-impl-20211101/vrfy_shared.o"
  )

  ar rcs "$ROOT/lazer/liblazer.a" "$ROOT/lazer/src/lazer_shared.o" "$ROOT/lazer/src/hexl_shared.o" "${FALCON_SHARED_OBJS[@]}"

  "$CXX" -shared -Wl,-z,defs -o "$ROOT/lazer/liblazer.so" \
    "$ROOT/lazer/src/lazer_shared.o" "$ROOT/lazer/src/hexl_shared.o" \
    "${FALCON_SHARED_OBJS[@]}" \
    "$HEXL_ARCHIVE" "$ROOT/.deps/lib/libcpu_features.a" \
    ${LIBRARY_PATH:+-L"$ROOT/.deps/lib"} -lmpfr -lgmp -lm

  "$CC" -Wall -Wextra -Wshadow -Wundef -O3 \
    -I"$ROOT/lazer" -I"$ROOT/lazer/demos/blindsig" \
    "$ROOT/lazer/demos/blindsig/blindsig-demo.c" \
    -o "$ROOT/lazer/demos/blindsig/blindsig-demo" \
    "$ROOT/lazer/liblazer.a" "$HEXL_ARCHIVE" "$ROOT/.deps/lib/libcpu_features.a" \
    ${LIBRARY_PATH:+-L"$ROOT/.deps/lib"} -lmpfr -lgmp -lm -lstdc++

  cp -f "$ROOT/lazer/liblazer.so" "$CACHE_DIR/liblazer.so"
  cp -f "$ROOT/lazer/liblazer.a" "$CACHE_DIR/liblazer.a"
  cp -f "$ROOT/lazer/demos/blindsig/blindsig-demo" "$CACHE_DIR/blindsig-demo"
fi

if ! compgen -G "$ROOT/lazer/python/_lazer_cffi*.so" > /dev/null; then
  make -C "$ROOT/lazer/python"
fi

PARAMS_HASH="$(sha256sum "$ROOT/lazer/python/anon_cred/anon_cred_params.h" | awk '{print $1}')"
PCACHE_DIR="$ROOT/.build/params_cffi_cache/$PARAMS_HASH"
mkdir -p "$PCACHE_DIR"
STAMP_FILE="$ROOT/lazer/python/anon_cred/.params_cffi_sha256"
if ! compgen -G "$ROOT/lazer/python/anon_cred/_anon_cred_params_cffi*.so" > /dev/null || [[ ! -f "$STAMP_FILE" ]] || [[ "$(cat "$STAMP_FILE")" != "$PARAMS_HASH" ]]; then
  if compgen -G "$PCACHE_DIR/_anon_cred_params_cffi*.so" > /dev/null; then
    cp -f "$PCACHE_DIR"/_anon_cred_params_cffi*.so "$ROOT/lazer/python/anon_cred/"
  else
    rm -f "$ROOT/lazer/python/anon_cred/_anon_cred_params_cffi"*
    (
      cd "$ROOT/lazer/python/anon_cred"
      python3 ../params_cffi_build.py anon_cred_params.h ../..
    )
    cp -f "$ROOT/lazer/python/anon_cred"/_anon_cred_params_cffi*.so "$PCACHE_DIR/"
  fi
  echo "$PARAMS_HASH" > "$STAMP_FILE"
fi

(
  cd "$ROOT/lazer/python/anon_cred"
  python3 -c 'import anon_cred; print("ANON_CRED_IMPORT_OK")'
)
echo "FAST_REBUILD_PASSED"
