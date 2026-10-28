#!/usr/bin/env bash
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
start_log build
choose_python
export CC="${CC:-gcc}" CXX="${CXX:-g++}"
JOBS="${JOBS:-2}"
[[ "$JOBS" =~ ^[1-9][0-9]*$ ]] || { echo 'JOBS must be a positive integer'; exit 1; }

# Provide minimal ABI-compatible headers/symlinks in .deps if /usr/include lacks gmp.h/mpfr.h
# while runtime shared libraries libgmp.so.10 and libmpfr.so.6 are present.
if [[ ! -f /usr/include/gmp.h && ! -f /usr/include/x86_64-linux-gnu/gmp.h ]]; then
  mkdir -p "$ROOT/.deps/include" "$ROOT/.deps/lib"
  if [[ -f /usr/lib/x86_64-linux-gnu/libgmp.so.10 ]]; then
    ln -sf /usr/lib/x86_64-linux-gnu/libgmp.so.10 "$ROOT/.deps/lib/libgmp.so"
  fi
  if [[ -f /usr/lib/x86_64-linux-gnu/libmpfr.so.6 ]]; then
    ln -sf /usr/lib/x86_64-linux-gnu/libmpfr.so.6 "$ROOT/.deps/lib/libmpfr.so"
  fi
  cat > "$ROOT/.deps/include/gmp.h" << 'EOF'
#ifndef __GMP_H__
#define __GMP_H__
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#ifdef __cplusplus
extern "C" {
#endif
#define GMP_LIMB_BITS 64
#define GMP_NAIL_BITS 0
#define GMP_NUMB_BITS (GMP_LIMB_BITS - GMP_NAIL_BITS)
typedef unsigned long int mp_limb_t;
typedef long int mp_limb_signed_t;
typedef unsigned long int mp_bitcnt_t;
typedef struct { int _mp_alloc; int _mp_size; mp_limb_t *_mp_d; } __mpz_struct;
typedef __mpz_struct mpz_t[1];
typedef __mpz_struct *mpz_ptr;
typedef const __mpz_struct *mpz_srcptr;
typedef long int mp_size_t;
typedef long int mp_exp_t;

#define mpz_init __gmpz_init
#define mpz_init2 __gmpz_init2
#define mpz_clear __gmpz_clear
#define mpz_set_ui __gmpz_set_ui
#define mpz_set_si __gmpz_set_si
#define mpz_import __gmpz_import
#define mpz_export __gmpz_export
#define mpz_out_str __gmpz_out_str
#define mpz_roinit_n __gmpz_roinit_n
#define mpz_limbs_read __gmpz_limbs_read
#define mpz_size __gmpz_size

void __gmpz_init(mpz_ptr);
void __gmpz_init2(mpz_ptr, mp_bitcnt_t);
void __gmpz_clear(mpz_ptr);
void __gmpz_set_ui(mpz_ptr, unsigned long int);
void __gmpz_set_si(mpz_ptr, signed long int);
void __gmpz_import(mpz_ptr, size_t, int, size_t, int, size_t, const void *);
void *__gmpz_export(void *, size_t *, int, size_t, int, size_t, mpz_srcptr);
size_t __gmpz_out_str(FILE *, int, mpz_srcptr);
mpz_srcptr __gmpz_roinit_n(mpz_ptr, const mp_limb_t *, mp_size_t);
const mp_limb_t *__gmpz_limbs_read(mpz_srcptr);
size_t __gmpz_size(mpz_srcptr);

#define mpn_add_n __gmpn_add_n
#define mpn_sub_n __gmpn_sub_n
#define mpn_mul __gmpn_mul
#define mpn_mul_n __gmpn_mul_n
#define mpn_tdiv_qr __gmpn_tdiv_qr
#define mpn_addmul_1 __gmpn_addmul_1
#define mpn_submul_1 __gmpn_submul_1
#define mpn_lshift __gmpn_lshift
#define mpn_rshift __gmpn_rshift
#define mpn_copyi __gmpn_copyi
#define mpn_com __gmpn_com
#define mpn_cnd_swap __gmpn_cnd_swap
#define mpn_sec_add_1 __gmpn_sec_add_1
#define mpn_sec_add_1_itch __gmpn_sec_add_1_itch
#define mpn_sec_mul __gmpn_sec_mul
#define mpn_sec_mul_itch __gmpn_sec_mul_itch
#define mpn_sec_sqr __gmpn_sec_sqr
#define mpn_sec_sqr_itch __gmpn_sec_sqr_itch
#define mpn_sec_div_qr __gmpn_sec_div_qr
#define mpn_sec_div_qr_itch __gmpn_sec_div_qr_itch
#define mpn_sec_div_r __gmpn_sec_div_r
#define mpn_sec_div_r_itch __gmpn_sec_div_r_itch
#define mpn_sec_invert __gmpn_sec_invert
#define mpn_sec_invert_itch __gmpn_sec_invert_itch

mp_limb_t __gmpn_add_n(mp_limb_t *, const mp_limb_t *, const mp_limb_t *, mp_size_t);
mp_limb_t __gmpn_sub_n(mp_limb_t *, const mp_limb_t *, const mp_limb_t *, mp_size_t);
mp_limb_t __gmpn_mul(mp_limb_t *, const mp_limb_t *, mp_size_t, const mp_limb_t *, mp_size_t);
void __gmpn_mul_n(mp_limb_t *, const mp_limb_t *, const mp_limb_t *, mp_size_t);
void __gmpn_tdiv_qr(mp_limb_t *, mp_limb_t *, mp_size_t, const mp_limb_t *, mp_size_t, const mp_limb_t *, mp_size_t);
mp_limb_t __gmpn_addmul_1(mp_limb_t *, const mp_limb_t *, mp_size_t, mp_limb_t);
mp_limb_t __gmpn_submul_1(mp_limb_t *, const mp_limb_t *, mp_size_t, mp_limb_t);
mp_limb_t __gmpn_lshift(mp_limb_t *, const mp_limb_t *, mp_size_t, unsigned int);
mp_limb_t __gmpn_rshift(mp_limb_t *, const mp_limb_t *, mp_size_t, unsigned int);
void __gmpn_copyi(mp_limb_t *, const mp_limb_t *, mp_size_t);
void __gmpn_com(mp_limb_t *, const mp_limb_t *, mp_size_t);
void __gmpn_cnd_swap(mp_limb_t, volatile mp_limb_t *, volatile mp_limb_t *, mp_size_t);
mp_limb_t __gmpn_sec_add_1(mp_limb_t *, const mp_limb_t *, mp_size_t, mp_limb_t, mp_limb_t *);
mp_size_t __gmpn_sec_add_1_itch(mp_size_t);
void __gmpn_sec_mul(mp_limb_t *, const mp_limb_t *, mp_size_t, const mp_limb_t *, mp_size_t, mp_limb_t *);
mp_size_t __gmpn_sec_mul_itch(mp_size_t, mp_size_t);
void __gmpn_sec_sqr(mp_limb_t *, const mp_limb_t *, mp_size_t, mp_limb_t *);
mp_size_t __gmpn_sec_sqr_itch(mp_size_t);
mp_limb_t __gmpn_sec_div_qr(mp_limb_t *, mp_limb_t *, mp_size_t, const mp_limb_t *, mp_size_t, mp_limb_t *);
mp_size_t __gmpn_sec_div_qr_itch(mp_size_t, mp_size_t);
void __gmpn_sec_div_r(mp_limb_t *, mp_size_t, const mp_limb_t *, mp_size_t, mp_limb_t *);
mp_size_t __gmpn_sec_div_r_itch(mp_size_t, mp_size_t);
int __gmpn_sec_invert(mp_limb_t *, mp_limb_t *, const mp_limb_t *, mp_size_t, mp_bitcnt_t, mp_limb_t *);
mp_size_t __gmpn_sec_invert_itch(mp_size_t);
#ifdef __cplusplus
}
#endif
#endif
EOF
  cat > "$ROOT/.deps/include/mpfr.h" << 'EOF'
#ifndef __MPFR_H
#define __MPFR_H
#include <gmp.h>
#include <stdint.h>
#include <stdio.h>
#ifdef __cplusplus
extern "C" {
#endif
typedef enum { MPFR_RNDN=0, MPFR_RNDZ, MPFR_RNDU, MPFR_RNDD, MPFR_RNDA, MPFR_RNDF, MPFR_RNDNA=-1 } mpfr_rnd_t;
typedef enum { MPFR_NAN_KIND=0, MPFR_INF_KIND=1, MPFR_ZERO_KIND=2, MPFR_REGULAR_KIND=3 } mpfr_kind_t;
typedef long mpfr_prec_t;
typedef int mpfr_sign_t;
typedef long mpfr_exp_t;
typedef struct { mpfr_prec_t _mpfr_prec; mpfr_sign_t _mpfr_sign; mpfr_exp_t _mpfr_exp; mp_limb_t *_mpfr_d; } __mpfr_struct;
typedef __mpfr_struct mpfr_t[1];
typedef __mpfr_struct *mpfr_ptr;
typedef const __mpfr_struct *mpfr_srcptr;

#define mpfr_out_str __gmpfr_out_str
void mpfr_init2(mpfr_ptr, mpfr_prec_t);
void mpfr_clear(mpfr_ptr);
int mpfr_set_ui(mpfr_ptr, unsigned long int, mpfr_rnd_t);
int mpfr_set_si(mpfr_ptr, long int, mpfr_rnd_t);
int mpfr_set_ui_2exp(mpfr_ptr, unsigned long int, mpfr_exp_t, mpfr_rnd_t);
int mpfr_set_z(mpfr_ptr, mpz_srcptr, mpfr_rnd_t);
int mpfr_set_z_2exp(mpfr_ptr, mpz_srcptr, mpfr_exp_t, mpfr_rnd_t);
int mpfr_mul(mpfr_ptr, mpfr_srcptr, mpfr_srcptr, mpfr_rnd_t);
int mpfr_mul_ui(mpfr_ptr, mpfr_srcptr, unsigned long int, mpfr_rnd_t);
int mpfr_mul_2ui(mpfr_ptr, mpfr_srcptr, unsigned long int, mpfr_rnd_t);
int mpfr_div(mpfr_ptr, mpfr_srcptr, mpfr_srcptr, mpfr_rnd_t);
int mpfr_exp(mpfr_ptr, mpfr_srcptr, mpfr_rnd_t);
int mpfr_cosh(mpfr_ptr, mpfr_srcptr, mpfr_rnd_t);
int mpfr_cmp(mpfr_srcptr, mpfr_srcptr);
size_t __gmpfr_out_str(FILE *, int, size_t, mpfr_srcptr, mpfr_rnd_t);
void mpfr_custom_init_set(mpfr_ptr, int, mpfr_exp_t, mpfr_prec_t, void *);
#ifdef __cplusplus
}
#endif
#endif
EOF
  export CPATH="$ROOT/.deps/include${CPATH:+:$CPATH}"
  export LIBRARY_PATH="$ROOT/.deps/lib${LIBRARY_PATH:+:$LIBRARY_PATH}"
  export LD_LIBRARY_PATH="$ROOT/.deps/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi

bash "$ROOT/00_check_env.sh"
"$PY" "$ROOT/verify_baseline.py"
if [[ ! -x "$ROOT/.venv/bin/python3" || ! -f "$ROOT/.venv/bin/activate" ]]; then
  rm -rf "$ROOT/.venv"
  "$PY" -m venv "$ROOT/.venv" >/dev/null 2>&1 || { rm -rf "$ROOT/.venv"; "$PY" -m venv --without-pip --system-site-packages "$ROOT/.venv"; }
fi
source "$ROOT/.venv/bin/activate"
if ! python3 -c "import cffi, setuptools" >/dev/null 2>&1; then
  python3 -m pip install 'cffi>=1.15,<3' 'setuptools>=68,<83' wheel
fi
python3 -m pip freeze > "$ROOT/logs/python_packages.txt" 2>/dev/null || true

if [[ ! -d "$ROOT/lazer/third_party/hexl-development" ]]; then
  unzip -q "$ROOT/lazer/third_party/hexl-development.zip" -d "$ROOT/lazer/third_party"
fi

if command -v cmake >/dev/null 2>&1; then
  cmake -S "$ROOT/vendor/cpu_features" -B "$ROOT/.build/cpu_features" \
    -DCMAKE_INSTALL_PREFIX="$ROOT/.deps" -DCMAKE_INSTALL_LIBDIR=lib -DBUILD_PIC=ON \
    -DBUILD_TESTING=OFF -DBUILD_SHARED_LIBS=OFF
  cmake --build "$ROOT/.build/cpu_features" --parallel "$JOBS"
  cmake --install "$ROOT/.build/cpu_features"
  export CMAKE_PREFIX_PATH="$ROOT/.deps${CMAKE_PREFIX_PATH:+:$CMAKE_PREFIX_PATH}"
  cmake -S "$ROOT/lazer/third_party/hexl-development" \
    -B "$ROOT/lazer/third_party/hexl-development/build" -DHEXL_BENCHMARK=OFF -DHEXL_TESTING=OFF
  cmake --build "$ROOT/lazer/third_party/hexl-development/build" --parallel "$JOBS"
else
  echo "Building cpu_features and Intel HEXL directly via $CC/$CXX (cmake fallback)..."
  mkdir -p "$ROOT/.build/cpu_features" "$ROOT/.deps/lib" "$ROOT/.deps/include"
  cp -r "$ROOT/vendor/cpu_features/include/"* "$ROOT/.deps/include/"
  CPU_OBJS=()
  for src in filesystem.c stack_line_reader.c string_view.c cpuinfo_x86.c hwcaps.c; do
    obj="$ROOT/.build/cpu_features/${src%.c}.o"
    "$CC" -O3 -fPIC -DSTACK_LINE_READER_BUFFER_SIZE=1024 -DHAVE_STRONG_GETAUXVAL -DHAVE_DLFCN_H \
      -I"$ROOT/vendor/cpu_features/include" -I"$ROOT/vendor/cpu_features/include/internal" \
      -c "$ROOT/vendor/cpu_features/src/$src" -o "$obj"
    CPU_OBJS+=("$obj")
  done
  ar rcs "$ROOT/.deps/lib/libcpu_features.a" "${CPU_OBJS[@]}"

  HEXL_DIR="$ROOT/lazer/third_party/hexl-development"
  HEXL_BUILD="$HEXL_DIR/build/hexl"
  mkdir -p "$HEXL_BUILD/lib" "$HEXL_BUILD/lib64" "$HEXL_BUILD/CMakeFiles/hexl.dir" "$HEXL_DIR/hexl/include/hexl/util"
  cat > "$HEXL_DIR/hexl/include/hexl/util/defines.hpp" << 'EOF'
#pragma once
#define HEXL_USE_GNU 1
#define HEXL_UNUSED(x) (void)(x)
EOF
  cat > "$HEXL_BUILD/CMakeFiles/hexl.dir/flags.make" << 'EOF'
CXX_DEFINES = -DHEXL_USE_GNU=1
CXX_FLAGS = -O3 -std=c++17 -fPIC -mavx2
EOF
  HEXL_OBJS=()
  for src in \
    hexl/eltwise/eltwise-mult-mod.cpp \
    hexl/eltwise/eltwise-reduce-mod.cpp \
    hexl/eltwise/eltwise-sub-mod.cpp \
    hexl/eltwise/eltwise-add-mod.cpp \
    hexl/eltwise/eltwise-fma-mod.cpp \
    hexl/eltwise/eltwise-cmp-add.cpp \
    hexl/eltwise/eltwise-cmp-sub-mod.cpp \
    hexl/ntt/ntt-internal.cpp \
    hexl/ntt/ntt-radix-2.cpp \
    hexl/ntt/ntt-radix-4.cpp \
    hexl/number-theory/number-theory.cpp; do
    obj="$HEXL_BUILD/$(basename "${src%.cpp}").o"
    "$CXX" -O3 -std=c++17 -fPIC -mavx2 \
      -I"$HEXL_DIR/hexl/include" -I"$HEXL_DIR/hexl" -I"$ROOT/.deps/include" \
      -c "$HEXL_DIR/$src" -o "$obj"
    HEXL_OBJS+=("$obj")
  done
  ar rcs "$HEXL_BUILD/lib/libhexl.a" "${HEXL_OBJS[@]}"
  cp -f "$HEXL_BUILD/lib/libhexl.a" "$HEXL_BUILD/lib64/libhexl.a"
fi

make -C "$ROOT/lazer" -o third_party/hexl-development -o third_party/Falcon-impl-20211101 -j"$JOBS" lib

HEXL_ARCHIVE="$ROOT/lazer/third_party/hexl-development/build/hexl/lib/libhexl.a"
if [[ ! -f "$HEXL_ARCHIVE" ]]; then
  HEXL_ARCHIVE="$ROOT/lazer/third_party/hexl-development/build/hexl/lib64/libhexl.a"
fi
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
"$CXX" -shared -Wl,-z,defs -o "$ROOT/lazer/liblazer.so" \
  "$ROOT/lazer/src/lazer_shared.o" "$ROOT/lazer/src/hexl_shared.o" \
  "${FALCON_SHARED_OBJS[@]}" \
  "$HEXL_ARCHIVE" "$ROOT/.deps/lib/libcpu_features.a" \
  ${LIBRARY_PATH:+-L"$ROOT/.deps/lib"} -lmpfr -lgmp -lm

# Build C blind signature demo binary so 10_audit_correctness.sh can test blindsig.c natively
"$CC" -Wall -Wextra -Wshadow -Wundef -O3 -g \
  -I"$ROOT/lazer" -I"$ROOT/lazer/demos/blindsig" \
  "$ROOT/lazer/demos/blindsig/blindsig-demo.c" \
  -o "$ROOT/lazer/demos/blindsig/blindsig-demo" \
  "$ROOT/lazer/liblazer.a" "$HEXL_ARCHIVE" "$ROOT/.deps/lib/libcpu_features.a" \
  ${LIBRARY_PATH:+-L"$ROOT/.deps/lib"} -lmpfr -lgmp -lm -lstdc++

make -C "$ROOT/lazer/python"
cd "$ROOT/lazer/python/anon_cred"
python3 ../params_cffi_build.py anon_cred_params.h ../..
python3 -c 'import anon_cred; print("ANON_CRED_IMPORT_OK")'
echo "BUILD_PASSED"
