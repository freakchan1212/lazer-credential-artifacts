#!/usr/bin/env python3
"""
Multi-Variant Optimization & Ablation Manager for lazer-baseline-Google-E2.

Supports clean separation of baseline, security bugfixes, and incremental optimizations:
  - B0 (B0_pristine_hooked):
      Upstream LaZer (10eafeca) + measurement counter hooks only (no bugfixes, no optimizations).
      Enables benchmarking the pristine baseline under identical P-Core affinity & governor.
  - B1 (B1_bugfix_only):
      B0 + 4 Security/Correctness Audit Fixes ONLY (lnp-quad.c stdev2sqr, blindsig.c r2 norm loop,
      anon_cred.py H2 holder blind-signature check, strict=True boundary checks). Zero optimizations.
  - V0 (V0_google_base):
      B1 + Direction 1 (lnp-quad.c R2*s loop hoisting) + Direction 2 (lin-proofs.c branchless int64_t svR AVX2)
      + Direction 4a (Python-level A_P1 & A_P2 statement matrix caching).
  - V1 (V1_opt5_c_statement_cache):
      V0 + Direction 5: C-level lin-proofs.c thread-local dynamic cache for Ds SHAKE128 prefix state
      (byte-aligned without premature coder_enc_end) & precomputed oDs = polymat_auto(Ds) in CRT domain.
  - V2 (V2_opt6_arp_z34_avx2):
      V1 + Direction 6: Prover-side __lnp_tbox_compute_z34 flat int64_t array extraction & branchless
      AVX2 dot product for z3 (256x3200) and z4 (256x512).
  - V3A (V3a_opt7a_lazy_cs2_only):
      V2 + Direction 7a: Lazy evaluation of cs2 = c*s2 and y2 += cs2 in lnp-quad.c only AFTER z1 passes rej1.
  - V3 (V3_opt7_lazy_cs2_and_crt_scale):
      V3A + Direction 7b: Unsigned-reduced uint64_t single-limb __int128 modular scaling fast path in poly_scale,
      100% exact across all 1-limb integers in [-(2^64 - 1), +(2^64 - 1)].
  - V4 (V4_opt8_double_fastpath_rejection):
      V3 + Direction 8: IEEE-754 double hi-53 fast-path filter (_int_to_double_hi53) with 1e-11 relative
      guard band in rej_standard & rej_bimodal, explicit ULP error bound, and runtime fastpath/fallback counters.
  - V5 (V5_opt9_dynamic_dim_pruning):
      V4 + Direction 9: Disclosure-parameterized subspace projection supporting all k in {1..8} disclosed
      attributes via p2_compact{k}_param (m1 = 48 - k, nbin = 16 - k, nex = 50 - k), with k=3 pre-initialized
      on the primary fast path and k=0 / duplicate-index fallback via p2_param (m1 = 48).
"""
import argparse
import difflib
import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent

VARIANTS = {
    "B0": {
        "id": "B0",
        "code": "B0_pristine_hooked",
        "name": "B0（上游原装代码 + 仅计数探针，不含漏洞修复与任何优化）",
        "direction_added": "Baseline 0: 上游 10eafeca + baseline_hooks.h 计数探针（用于在相同 P-Core + performance 调频下复测纯净原装基线）",
        "byte_identical_to_b1": False,
        "byte_identical_to_v0": False,
        "bugfixes_applied": False,
        "optimizations_applied": False,
        "protocol_parameters_changed": False,
    },
    "B1": {
        "id": "B1",
        "code": "B1_bugfix_only",
        "name": "B1（仅 4 项安全与正确性修复，0 性能优化）",
        "direction_added": "Baseline 1: 仅启用 4 项审计修复（lnp-quad.c stdev2sqr + blindsig.c r2 范数 + H2 持有者验签 + strict=True 边界检查），不含任何性能优化",
        "byte_identical_to_b1": True,
        "byte_identical_to_v0": True,
        "bugfixes_applied": True,
        "optimizations_applied": False,
        "protocol_parameters_changed": False,
    },
    "V0": {
        "id": "V0",
        "code": "V0_google_base",
        "name": "V0（B1 + 方向 1 R2*s 外提 + 方向 2 svR AVX2 + 方向 4a Python 矩阵缓存）",
        "direction_added": "方向 1（lnp-quad.c R2*s 循环外提）+ 方向 2（lin-proofs.c 无分支 int64_t svR AVX2）+ 方向 4a（Python 层 A_P1/A_P2 静态矩阵缓存）",
        "byte_identical_to_b1": True,
        "byte_identical_to_v0": True,
        "bugfixes_applied": True,
        "optimizations_applied": True,
        "protocol_parameters_changed": False,
    },
    "V1": {
        "id": "V1",
        "code": "V1_opt5_c_statement_cache",
        "name": "V1（V0 + 方向 5：C 层 Ds SHAKE128 字节对齐前缀缓存与 oDs/Ds CRT 域常驻）",
        "direction_added": "方向 5：lin-proofs.c 静态矩阵 Ds 的 SHAKE128 无尾填充前缀缓存（修复 coder_enc_end 偏移）+ oDs 预计算与 CRT 域常驻（线程局部动态扩容表）",
        "byte_identical_to_b1": True,
        "byte_identical_to_v0": True,
        "bugfixes_applied": True,
        "optimizations_applied": True,
        "protocol_parameters_changed": False,
    },
    "V2": {
        "id": "V2",
        "code": "V2_opt6_arp_z34_avx2",
        "name": "V2（V1 + 方向 6：Prover 端 ARP z3/z4 紧凑数组无分支 AVX2 向量化）",
        "direction_added": "方向 6：lin-proofs.c 中 __lnp_tbox_compute_z34 预提取 s3/s4 紧凑 int64_t 数组并消除内层分支，激活 AVX2 点积",
        "byte_identical_to_b1": True,
        "byte_identical_to_v0": True,
        "bugfixes_applied": True,
        "optimizations_applied": True,
        "protocol_parameters_changed": False,
    },
    "V3A": {
        "id": "V3A",
        "code": "V3a_opt7a_lazy_cs2_only",
        "name": "V3A（V2 + 方向 7a：仅启用 lnp-quad.c 惰性 cs2 计算，不改 poly_scale）",
        "direction_added": "方向 7a：lnp-quad.c 惰性延迟计算 cs2 = c * s2（仅在 z1 通过 rej1 后才计算，消除 ~57% 失败轮次的 s2 运算）",
        "byte_identical_to_b1": True,
        "byte_identical_to_v0": True,
        "bugfixes_applied": True,
        "optimizations_applied": True,
        "protocol_parameters_changed": False,
    },
    "V3": {
        "id": "V3",
        "code": "V3_opt7_lazy_cs2_and_crt_scale",
        "name": "V3（V2 + 方向 7：惰性 cs2 计算 + 修复无符号预约减的单 limb poly_scale 快速路径）",
        "direction_added": "方向 7：lnp-quad.c 惰性延迟计算 cs2 = c * s2 + poly.c 无符号 uint64_t 预约减的原生 __int128 单 limb 标量模乘（全 64-bit 范围精确）",
        "byte_identical_to_b1": True,
        "byte_identical_to_v0": True,
        "bugfixes_applied": True,
        "optimizations_applied": True,
        "protocol_parameters_changed": False,
    },
    "V4": {
        "id": "V4",
        "code": "V4_opt8_double_fastpath_rejection",
        "name": "V4（V3 + 方向 8：rejection.c IEEE-754 双精度保护带快速过滤 + 计数器）",
        "direction_added": "方向 8：rejection.c 在 rej_standard 与 rej_bimodal 中引入 _int_to_double_hi53 硬件浮点快速过滤（1e-11 保护带 + 显式 ULP 误差界 + 命中/回退计数）",
        "byte_identical_to_b1": True,
        "byte_identical_to_v0": True,
        "bugfixes_applied": True,
        "optimizations_applied": True,
        "protocol_parameters_changed": False,
    },
    "V5": {
        "id": "V5",
        "code": "V5_opt9_dynamic_dim_pruning",
        "name": "V5（V4 + 方向 9：披露参数化子空间投影，支持 k=1..8 全基数动态降维）",
        "direction_added": "方向 9：anon_cred_params.h 导出 k=1..8 全套紧致参数集 p2_compact{k}_param（m1=48-k, nbin=16-k），k=3 时见证维度 48->45，证明体积缩减 ~619 B",
        "byte_identical_to_b1": False,
        "byte_identical_to_v0": False,
        "bugfixes_applied": True,
        "optimizations_applied": True,
        "protocol_parameters_changed": True,
    },
}

TOUCHED_FILES = [
    "lazer/src/lazer.c",
    "lazer/src/lin-proofs.c",
    "lazer/src/lnp-quad.c",
    "lazer/src/blindsig.c",
    "lazer/src/poly.c",
    "lazer/src/rejection.c",
    "lazer/python/lazer.py",
    "lazer/python/anon_cred/anon_cred.py",
    "lazer/python/anon_cred/anon_cred_params.h",
]


def _sub(text: str, old: str, new: str, count: int = 1, label: str = "") -> str:
    actual = text.count(old)
    if actual != count:
        raise RuntimeError(
            f"Patch anchor mismatch ({label or old[:50]!r}): expected {count}, found {actual}"
        )
    return text.replace(old, new, count)


def _read_upstream(rel_path: str) -> str:
    with zipfile.ZipFile(ROOT / "pristine" / "upstream_snapshot.zip") as z:
        return z.read(f"BLNS_LAZER_BASELINE_20261014/{rel_path}").decode("utf-8")


def _generate_compact_params_block() -> str:
    """Generate p2_compact1_param .. p2_compact8_param C definitions verified against lnp-tbox-codegen.sage."""
    lines = [
        "",
        "/* Direction 9 (V5): Disclosure-Parameterized Subspace Projection parameter sets",
        " * p2_compact{k}_param for k in {1..8} disclosed attributes (h = 8 - k hidden attributes).",
        " * Verified against lnp-tbox-codegen.sage:",
        " *   - Secret witness dimension: m1(k) = 48 - k (tbox->m1 = 50 - k including Z=2 exact-l2 slack polys)",
        " *   - Binary norm proof dimension: nbin(k) = 16 - k (8 tag polys + h hidden attribute polys)",
        " *   - Total exact-l2 + binary dimension: nex(k) = 50 - k",
        " *   - Ring R_q2 (d=64, q=1125899906843221), kmsis=20, m2=64, kmlwe=32, Bsq=floor(Bound_()^2)=143158532224272924UL,",
        " *     stdev1..4, scM1..4, Bz3sqr, Bz4, and knowledge error <= 2^-127 are strictly preserved.",
        " *   - MSIS Bound(k) = sqrt((2*stdev1*sqrt(2*(m1(k)+Z)*d))^2 + (2*Bound_())^2):",
        " *       k=0 (m1=48): log2(Bound) = 40.173114, MSIS_RHF = 1.0043793",
        " *       k=3 (m1=45): log2(Bound) = 40.133841, MSIS_RHF = 1.0043707",
        " *       k=8 (m1=40): log2(Bound) = 40.063167, MSIS_RHF = 1.0043554",
        " */",
    ]
    for k in range(1, 9):
        h = 8 - k
        m1 = 40 + h
        nbin = 8 + h
        nex = m1 + 2
        max_bytes = 30064 - 192 * k
        ps_list = list(range(16, 24)) + list(range(40, 40 + h))
        s1_list = list(range(0, m1))
        ps_str = ", ".join(str(x) for x in ps_list)
        s1_str = ", ".join(str(x) for x in s1_list)
        cname = f"p2_compact{k}_param"
        lines.extend([
            f"static const abdlop_params_t _{cname}_tbox = {{{{ _p2_param_ring, _p2_param_dcomp, {nex}, 64, 0, 12, 20, _p2_param_Bsq, 1, 8, 5, 140, 1, 23, _p2_param_scM1, _p2_param_stdev1sq, 2, 12, _p2_param_scM2, _p2_param_stdev2sq}}}};',"[0:-2],
            f"static const abdlop_params_t _{cname}_quad_eval_ = {{{{ _p2_param_ring, _p2_param_dcomp, {nex}, 64, 9, 3, 20, _p2_param_Bsq, 1, 8, 5, 140, 1, 23, _p2_param_scM1, _p2_param_stdev1sq, 2, 12, _p2_param_scM2, _p2_param_stdev2sq}}}};',"[0:-2],
            f"static const abdlop_params_t _{cname}_quad_many_ = {{{{ _p2_param_ring, _p2_param_dcomp, {nex}, 64, 11, 1, 20, _p2_param_Bsq, 1, 8, 5, 140, 1, 23, _p2_param_scM1, _p2_param_stdev1sq, 2, 12, _p2_param_scM2, _p2_param_stdev2sq}}}};',"[0:-2],
            f"static const lnp_quad_eval_params_t _{cname}_quad_eval = {{{{ _{cname}_quad_eval_, _{cname}_quad_many_, 4}}}};',"[0:-2],
            f"static const lnp_tbox_params_t _{cname} = {{{{ _{cname}_tbox, _{cname}_quad_eval, {nbin}, _p2_param_n, 8, 2, {nex}, 2, 18, _p2_param_scM3, _p2_param_stdev3sq, 2, 29, _p2_param_scM4, _p2_param_stdev4sq, _p2_param_Bz3sqr, _p2_param_Bz4, &_p2_param_l2Bsq[0], _p2_param_inv4, {max_bytes}UL }}}};',"[0:-2],
            f"static const unsigned int {cname}_Ps[{nbin}] = {{{ps_str}}};",
            f"static const unsigned int {cname}_s1_indices[{m1}] = {{{s1_str}}};",
            f"static const lin_params_t {cname} = {{{{ _{cname}, 64, p2_param_p, p2_param_pinv, 1, {cname}_s1_indices, {m1}, NULL, 0, {cname}_Ps, {nbin}, p2_param_Es, p2_param_Es_nrows, NULL, NULL }}}};",
            "",
        ])
    return "\n".join(lines)


def build_variant_sources(variant_id: str) -> dict[str, str]:
    variant_id = variant_id.upper()
    if variant_id not in VARIANTS:
        raise ValueError(f"Unknown variant {variant_id!r}. Valid variants: {list(VARIANTS)}")

    out = {p: _read_upstream(p) for p in TOUCHED_FILES}

    # =========================================================================
    # Step 0: Measurement counter hooks (present in ALL variants B0, B1, V0..V5)
    # =========================================================================
    out["lazer/src/lazer.c"] = '#include "baseline_hooks.h"\n' + out["lazer/src/lazer.c"]

    lin = out["lazer/src/lin-proofs.c"]
    lin = _sub(
        lin,
        "  while (1)\n    {\n      /* sample signs */",
        "  while (1)\n    {\n      baseline_counts[0]++;\n      /* sample signs */",
        label="lin baseline_counts[0]",
    )
    lin = _sub(
        lin,
        'DEBUG_PRINTF (DEBUG_PRINT_REJ, "%s", "reject s3");\n              continue;',
        'baseline_counts[1]++;\n              DEBUG_PRINTF (DEBUG_PRINT_REJ, "%s", "reject s3");\n              continue;',
        count=2,
        label="lin baseline_counts[1]",
    )
    pos = lin.find("if (nprime > 0 && params->rej4)")
    assert pos > 0
    lin = lin[:pos] + lin[pos:].replace("baseline_counts[1]++", "baseline_counts[2]++", 1)

    quad = out["lazer/src/lnp-quad.c"]
    quad = _sub(
        quad,
        "  while (1)\n    {\n      /* y1, y2 */",
        "  while (1)\n    {\n      baseline_counts[3]++;\n      /* y1, y2 */",
        label="quad baseline_counts[3]",
    )
    for a, b in [
        (
            'DEBUG_PRINTF (DEBUG_PRINT_REJ, "%s", "reject on s1");\n              continue;',
            'baseline_counts[4]++;\n              DEBUG_PRINTF (DEBUG_PRINT_REJ, "%s", "reject on s1");\n              continue;',
        ),
        (
            'DEBUG_PRINTF (DEBUG_PRINT_REJ, "%s", "reject compr");\n              continue;',
            'baseline_counts[5]++;\n              DEBUG_PRINTF (DEBUG_PRINT_REJ, "%s", "reject compr");\n              continue;',
        ),
        (
            'DEBUG_PRINTF (DEBUG_PRINT_REJ, "%s", "reject on s1");\n          continue;',
            'baseline_counts[6]++;\n          DEBUG_PRINTF (DEBUG_PRINT_REJ, "%s", "reject on s1");\n          continue;',
        ),
    ]:
        quad = _sub(quad, a, b, label="quad baseline_counts[4..6]")

    # CFFI module import fallback (needed when running worker scripts from root dir)
    lazer_py = out["lazer/python/lazer.py"]
    lazer_py = _sub(
        lazer_py,
        "from _lazer_cffi import ffi, lib",
        """try:
    from _lazer_cffi import ffi, lib
except ModuleNotFoundError:
    import importlib.util, os, sysconfig
    _so = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_lazer_cffi" + (sysconfig.get_config_var("EXT_SUFFIX") or ".so"))
    _spec = importlib.util.spec_from_file_location("_lazer_cffi", _so)
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    ffi, lib = _mod.ffi, _mod.lib""",
        label="lazer.py cffi loader",
    )
    lazer_py = _sub(
        lazer_py,
        """        elif type(val) == polymat_t:
            lib.polymat_set(self.ptr,val.ptr)""",
        """        elif type(val) == polymat_t:
            lib.polymat_set(self.ptr,val.ptr)
        else:
            lib.polymat_set(self.ptr,val)""",
        label="lazer.py polymat_set",
    )

    anon_py = out["lazer/python/anon_cred/anon_cred.py"]
    anon_py = _sub(
        anon_py,
        "from _anon_cred_params_cffi import lib",
        """try:
    from _anon_cred_params_cffi import lib
except ModuleNotFoundError:
    import importlib.util, os, sysconfig
    _so = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_anon_cred_params_cffi" + (sysconfig.get_config_var("EXT_SUFFIX") or ".so"))
    _spec = importlib.util.spec_from_file_location("_anon_cred_params_cffi", _so)
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    lib = _mod.lib""",
        label="anon_cred.py cffi loader",
    )

    # If B0 (pristine hooked baseline), return immediately without any bugfixes or optimizations!
    if variant_id == "B0":
        out["lazer/src/lin-proofs.c"] = lin
        out["lazer/src/lnp-quad.c"] = quad
        out["lazer/python/lazer.py"] = lazer_py
        out["lazer/python/anon_cred/anon_cred.py"] = anon_py
        return out

    # =========================================================================
    # Step 1: 4 Security & Correctness Audit Fixes (present in B1 and V0..V5)
    # =========================================================================
    # Audit Fix 0: C-level input coefficient normalization in _lin_set_statement_A and _lin_set_statement_t
    lin = _sub(
        lin,
        """  if (A->ring->d == 64 || A->ring->d == 128)
    polymat_fromcrt (A);""",
        """  if (A->ring->d == 64 || A->ring->d == 128)
    polymat_fromcrt (A);
  polymat_mod (A, A);
  polymat_redc (A, A);""",
        label="Audit Fix 0a: _lin_set_statement_A mod/redc",
    )
    lin = _sub(
        lin,
        """      if (t->ring->d == 64 || t->ring->d == 128)
        polyvec_fromcrt (t);""",
        """      if (t->ring->d == 64 || t->ring->d == 128)
        polyvec_fromcrt (t);
      polyvec_mod (t, t);
      polyvec_redc (t, t);""",
        label="Audit Fix 0b: _lin_set_statement_t mod/redc",
    )

    # Audit Fix 1: lnp-quad.c stdev2sqr in rej_bimodal
    quad = _sub(
        quad,
        """          if (params->rej2 == 2)
            rej = rej_bimodal (rngstate, z2coeffs, cs2coeffs, params->scM2,
                               params->stdev1sqr);""",
        """          if (params->rej2 == 2)
            rej = rej_bimodal (rngstate, z2coeffs, cs2coeffs, params->scM2,
                               params->stdev2sqr);""",
        label="Audit Fix 1: quad stdev2sqr",
    )

    # Audit Fix 2: blindsig.c r2 norm loop coeff update
    out["lazer/src/blindsig.c"] = _sub(
        out["lazer/src/blindsig.c"],
        """      intvec_grandom (coeffvec, 1, protoseed, dom++);
      for (i = 0; i < 512; i++)
        {
          state->r2[i] = (int32_t)intvec_get_elem_i64 (coeffvec, i);
          l2sqr += (int64_t)coeff * coeff;
        }""",
        """      intvec_grandom (coeffvec, 1, protoseed, dom++);
      for (i = 0; i < 512; i++)
        {
          coeff = (int32_t)intvec_get_elem_i64 (coeffvec, i);
          state->r2[i] = coeff;
          l2sqr += (int64_t)coeff * coeff;
        }""",
        label="Audit Fix 2: blindsig r2 coeff",
    )

    # Audit Fix 4a: lazer.py optional strict=True trailing-byte check
    lazer_py = _sub(
        lazer_py,
        """    def verify(self, proof: bytes):
        \"\"\"Verifies the ZK proof

        Args:
            proof (bytes): the ZK proof
        
        Returns:
            nothing, or throws exception if the proof is invalid

        \"\"\"
        prooflen = ffi.new("size_t[1]")
        accept = lib.lin_verifier_verify(self.ptr, proof, prooflen)
        if accept != 1:
            raise VerificationError("Verification failed.")""",
        """    def verify(self, proof: bytes, strict: bool = False):
        \"\"\"Verifies the ZK proof

        Args:
            proof (bytes): the ZK proof
            strict (bool): if True, reject trailing bytes after the encoded proof
        
        Returns:
            nothing, or throws exception if the proof is invalid
        \"\"\"
        prooflen = ffi.new("size_t[1]")
        accept = lib.lin_verifier_verify(self.ptr, proof, prooflen)
        if accept != 1:
            raise VerificationError("Verification failed.")
        if strict and prooflen[0] != len(proof):
            raise VerificationError("Trailing bytes in proof.")

    def verify_strict(self, proof: bytes):
        return self.verify(proof, strict=True)""",
        label="Audit Fix 4a: lazer.py strict verify",
    )
    out["lazer/python/lazer.py"] = lazer_py

    # If B1 (bugfix-only baseline), apply H2 check + strict=True in anon_cred.py WITHOUT A_P1/A_P2 statement caching!
    if variant_id == "B1":
        anon_py_b1 = _sub(
            anon_py,
            'class user_t:\n    def __init__(self, pk: falcon_pkenc):\n        self.B2 = falcon_decode_pk(pk,RING) #\n        self.p1_prover = lin_prover_state_t(P1PP, lib.get_params("p1_param"))\n        self.p2_prover = lin_prover_state_t(P2PP, lib.get_params("p2_param"))\n\n    def maskmsg(self, msg: bytes):\n        m = polyvec_t(RING,8,msg)\n        seed = secrets.token_bytes(32)  # internal coins\n        logsigma = 1                    # sigma = 1.55*2^logsigma\n        l2sqr_bnd = wl2[0] * wl2[0]     # l2(r1,r2)^2\n        r=polyvec_t.grandom_static(RING,16,logsigma,seed,0,0,l2sqr_bnd)\n        t = AR*r + AM*m\n\n        # prove [Ar,Am]*(r,m) + (-t) = 0\n        # as PoK(w): Aw + u = 0\n        A = polymat_t(RING, 8, 24, [AR, AM])\n        u = polyvec_t(RING, 8, [-t])\n        w = polyvec_t(RING, 24, [r, m])\n   \n        self.p1_prover.set_statement(A, u)\n        self.p1_prover.set_witness(w)\n        \n        proof = self.p1_prover.prove()\n\n        # encode t\n        coder = coder_t()\n        coder.enc_begin(22000)\n        coder.enc_urandom(mod, t)\n        tenc = coder.enc_end()\n\n        # save randomness and message\n        self.r = r\n        self.m = m\n        # return masked message t,p1enc\n        return tenc + proof\n\n    def sign(self, blindsig: bytes, pub_mvec: list):\n        # decode blindsig tau,s1,s2\n        \n        tau, s1, s2 = bytes(64), polyvec_t(RING,8), polyvec_t(RING,8)\n        try:\n            coder = coder_t()\n            coder.dec_begin(blindsig)\n            coder.dec_bytes(tau)\n            coder.dec_grandom(165, s1)\n            coder.dec_grandom(165, s2)\n            coder.dec_end()\n        except DecodingError:\n            raise InvalidMaskedMsg\n\n        tau_ = polyvec_t(RING, 8, tau)\n\n        # prove [Ar,Atau,-B1,-B2]*(r,tau,s1,s2) + Am*m = 0\n        # as PoK(w): Aw + u = 0\n        \n        m_priv=self.m.zero_out_pols(pub_mvec)\n        #m_priv=self.m.copy()\n        AM_priv=AM.zero_out_cols(pub_mvec)\n        if len(pub_mvec)==0:\n            u=polyvec_t(RING,8)\n        else:\n            m_pub=self.m.get_pol_list(pub_mvec)\n            AM_pub=AM.get_col_list(pub_mvec)\n            u=polyvec_t(RING, 8, [AM_pub * m_pub])\n      \n\n        A = polymat_t(RING, 8, 48, [AR, ATAU, -B1, -self.B2, AM_priv])        \n        w = polyvec_t(RING, 48, [self.r, tau_, s1, s2, m_priv])\n\n        self.p2_prover.set_statement(A, u)\n        self.p2_prover.set_witness(w)\n        proof = self.p2_prover.prove()\n\n        return proof\n\n\nclass signer_t:\n    def __init__(self, pk: falcon_pkenc, sk: falcon_skenc):\n        self.sk = sk\n        self.p1_verifier = lin_verifier_state_t(P1PP, lib.get_params("p1_param"))\n\n    def sign(self, masked_msg: bytes):\n        # decode masked message\n        t = polyvec_t(RING,8)\n        try:\n            coder = coder_t()\n            coder.dec_begin(masked_msg)\n            coder.dec_urandom(mod, t)\n            tlen = coder.dec_end()\n        except DecodingError:\n            raise InvalidMaskedMsg\n        \n        # verify proof for PoK(w): Aw + u = 0\n        A = polymat_t(RING, 8, 24, [AR, AM])\n        u = polyvec_t(RING, 8, [-t])\n        proof = masked_msg[tlen:]\n\n        self.p1_verifier.set_statement(A, u)\n        try:\n            self.p1_verifier.verify(proof)\n        except VerificationError:\n            raise InvalidMaskedMsg("Masked message invalid.")\n\n        # internal coins\n        tau_ = secrets.token_bytes(64)\n        tau = polyvec_t(RING,8,tau_)\n\n        # preimage sampling\n        s1, s2 = falcon_preimage_sample(self.sk, ATAU * tau + t,RING)\n        #s1, s2 = falcon_preimage_sample(self.sk, ATAU * tau + t)\n\n        # encode blindsig tau,s1,s2\n        coder = coder_t()\n        coder.enc_begin(2000)\n        coder.enc_bytes(tau_)\n        coder.enc_grandom(165, s1)\n        coder.enc_grandom(165, s2)\n        blindsig = coder.enc_end()\n\n        return blindsig\n\n\nclass verifier_t:\n    def __init__(self, pk: falcon_pkenc):\n        self.B2 = falcon_decode_pk(pk,RING)\n        self.p2_verifier = lin_verifier_state_t(P2PP, lib.get_params("p2_param"))\n\n    #the private part should already be zeroed out in pub_msg \n    def verify(self, pub_msg: bytes, pub_mvec:list, sig: bytes):\n        \n        m = polyvec_t(RING, 8, pub_msg)\n        AM_priv=AM.zero_out_cols(pub_mvec)\n        if len(pub_mvec)==0:\n            u=polyvec_t(RING,8)\n        else:\n            m_pub=m.get_pol_list(pub_mvec)\n            AM_pub=AM.get_col_list(pub_mvec)\n            u=polyvec_t(RING, 8, [AM_pub * m_pub])\n\n        # verify proof for PoK(w): Aw + u = 0\n        A = polymat_t(RING, 8, 48, [AR, ATAU, -B1, -self.B2, AM_priv])\n        #u = polyvec_t(RING, 8, [AM_pub * m_pub])\n        proof = sig\n        \n        self.p2_verifier.set_statement(A, u)\n        try:\n            self.p2_verifier.verify(proof)\n        except VerificationError:\n            raise InvalidSignature("Signature invalid.")',
            'AR.redc(); AM.redc(); ATAU.redc(); B1.redc()\n\n\nclass user_t:\n    def __init__(self, pk: falcon_pkenc):\n        self.B2 = falcon_decode_pk(pk,RING) #\n        self.B2.redc()\n        self._B2_h2 = falcon_decode_pk(pk,RING)\n        self.p1_prover = lin_prover_state_t(P1PP, lib.get_params("p1_param"))\n        self.p2_prover = lin_prover_state_t(P2PP, lib.get_params("p2_param"))\n\n    def maskmsg(self, msg: bytes):\n        m = polyvec_t(RING,8,msg)\n        seed = secrets.token_bytes(32)  # internal coins\n        logsigma = 1                    # sigma = 1.55*2^logsigma\n        l2sqr_bnd = wl2[0] * wl2[0]     # l2(r1,r2)^2\n        r=polyvec_t.grandom_static(RING,16,logsigma,seed,0,0,l2sqr_bnd)\n        t = AR*r + AM*m\n\n        # prove [Ar,Am]*(r,m) + (-t) = 0\n        # as PoK(w): Aw + u = 0\n        A = polymat_t(RING, 8, 24, [AR, AM])\n        u = polyvec_t(RING, 8, [-t])\n        w = polyvec_t(RING, 24, [r, m])\n   \n        self.p1_prover.set_statement(A, u)\n        self.p1_prover.set_witness(w)\n        \n        proof = self.p1_prover.prove()\n\n        # encode t\n        coder = coder_t()\n        coder.enc_begin(22000)\n        coder.enc_urandom(mod, t)\n        tenc = coder.enc_end()\n\n        # save randomness and message\n        self.r = r\n        self.m = m\n        # return masked message t,p1enc\n        return tenc + proof\n\n    def verify_blindsig(self, blindsig: bytes):\n        """BLNS23 Fig. 19 H2 check (B1 uncached): decode and validate (tau, s1, s2) from issuer."""\n        tau, s1, s2 = bytes(64), polyvec_t(RING,8), polyvec_t(RING,8)\n        try:\n            coder = coder_t()\n            coder.dec_begin(blindsig)\n            coder.dec_bytes(tau)\n            coder.dec_grandom(165, s1)\n            coder.dec_grandom(165, s2)\n            blindsig_len = coder.dec_end()\n        except DecodingError:\n            raise InvalidBlindSig("Blind signature decoding failed.")\n        if blindsig_len != len(blindsig):\n            raise InvalidBlindSig("Trailing bytes in blind signature.")\n        tau_ = polyvec_t(RING, 8, tau)\n        if s1.l2sqr() + s2.l2sqr() > 34034726:\n            raise InvalidBlindSig("Blind signature (s1, s2) l2-norm exceeds bound.")\n        if hasattr(self, "r") and hasattr(self, "m"):\n            lhs = B1 * s1.copy() + self._B2_h2 * s2.copy()\n            rhs = AR * self.r.copy() + AM * self.m.copy() + ATAU * tau_.copy()\n            if lhs != rhs:\n                raise InvalidBlindSig("Blind signature linear relation check failed.")\n        return tau_, s1, s2\n\n    def sign(self, blindsig: bytes, pub_mvec: list):\n        # decode and H2-validate blindsig tau,s1,s2\n        tau_, s1, s2 = self.verify_blindsig(blindsig)\n        pub_mvec = list(dict.fromkeys(pub_mvec))\n\n        # prove [Ar,Atau,-B1,-B2]*(r,tau,s1,s2) + Am*m = 0\n        # as PoK(w): Aw + u = 0\n        m_priv=self.m.zero_out_pols(pub_mvec)\n        AM_priv=AM.zero_out_cols(pub_mvec)\n        if len(pub_mvec)==0:\n            u=polyvec_t(RING,8)\n        else:\n            m_pub=self.m.get_pol_list(pub_mvec)\n            AM_pub=AM.get_col_list(pub_mvec)\n            u=polyvec_t(RING, 8, [AM_pub * m_pub])\n\n        A = polymat_t(RING, 8, 48, [AR, ATAU, -B1, -self.B2, AM_priv])\n        w = polyvec_t(RING, 48, [self.r, tau_, s1, s2, m_priv])\n\n        self.p2_prover.set_statement(A, u)\n        self.p2_prover.set_witness(w)\n        proof = self.p2_prover.prove()\n\n        return proof\n\n\nclass signer_t:\n    def __init__(self, pk: falcon_pkenc, sk: falcon_skenc):\n        self.sk = sk\n        self.p1_verifier = lin_verifier_state_t(P1PP, lib.get_params("p1_param"))\n\n    def sign(self, masked_msg: bytes, strict: bool = False):\n        # decode masked message\n        t = polyvec_t(RING,8)\n        try:\n            coder = coder_t()\n            coder.dec_begin(masked_msg)\n            coder.dec_urandom(mod, t)\n            tlen = coder.dec_end()\n        except DecodingError:\n            raise InvalidMaskedMsg\n        \n        # verify proof for PoK(w): Aw + u = 0\n        A = polymat_t(RING, 8, 24, [AR, AM])\n        u = polyvec_t(RING, 8, [-t])\n        proof = masked_msg[tlen:]\n\n        self.p1_verifier.set_statement(A, u)\n        try:\n            self.p1_verifier.verify(proof, strict=strict)\n        except VerificationError:\n            raise InvalidMaskedMsg("Masked message invalid.")\n\n        # internal coins\n        tau_ = secrets.token_bytes(64)\n        tau = polyvec_t(RING,8,tau_)\n\n        # preimage sampling\n        s1, s2 = falcon_preimage_sample(self.sk, ATAU * tau + t,RING)\n\n        # encode blindsig tau,s1,s2\n        coder = coder_t()\n        coder.enc_begin(2000)\n        coder.enc_bytes(tau_)\n        coder.enc_grandom(165, s1)\n        coder.enc_grandom(165, s2)\n        blindsig = coder.enc_end()\n\n        return blindsig\n\n\nclass verifier_t:\n    def __init__(self, pk: falcon_pkenc):\n        self.B2 = falcon_decode_pk(pk,RING)\n        self.B2.redc()\n        self.p2_verifier = lin_verifier_state_t(P2PP, lib.get_params("p2_param"))\n\n    #the private part should already be zeroed out in pub_msg \n    def verify(self, pub_msg: bytes, pub_mvec:list, sig: bytes, strict: bool = False):\n        if strict:\n            if len(pub_msg) != 64:\n                raise InvalidSignature("Public message container must be 64 bytes.")\n            pub_set = set(pub_mvec)\n            if len(pub_set) != len(pub_mvec) or any(i < 0 or i >= 8 for i in pub_mvec):\n                raise InvalidSignature("Invalid disclosed attribute indices.")\n            for i in range(8):\n                if i not in pub_set and any(pub_msg[i*8:(i+1)*8]):\n                    raise InvalidSignature("Undisclosed attribute slot in pub_msg is non-zero.")\n        pub_mvec = list(dict.fromkeys(pub_mvec))\n        m = polyvec_t(RING, 8, pub_msg)\n        AM_priv=AM.zero_out_cols(pub_mvec)\n        if len(pub_mvec)==0:\n            u=polyvec_t(RING,8)\n        else:\n            m_pub=m.get_pol_list(pub_mvec)\n            AM_pub=AM.get_col_list(pub_mvec)\n            u=polyvec_t(RING, 8, [AM_pub * m_pub])\n\n        # verify proof for PoK(w): Aw + u = 0\n        A = polymat_t(RING, 8, 48, [AR, ATAU, -B1, -self.B2, AM_priv])\n        proof = sig\n        \n        self.p2_verifier.set_statement(A, u)\n        try:\n            self.p2_verifier.verify(proof, strict=strict)\n        except VerificationError:\n            raise InvalidSignature("Signature invalid.")\n\n    def verify_strict(self, pub_msg: bytes, pub_mvec: list, sig: bytes):\n        return self.verify(pub_msg, pub_mvec, sig, strict=True)',
            label="B1 anon_cred bugfix-only",
        )
        out["lazer/src/lin-proofs.c"] = lin
        out["lazer/src/lnp-quad.c"] = quad
        out["lazer/python/anon_cred/anon_cred.py"] = anon_py_b1
        return out

    # =========================================================================
    # V0..V5: Performance Optimizations on top of B1
    # =========================================================================
    vorder = {"V0": 0, "V1": 1, "V2": 2, "V3A": 3, "V3": 3, "V4": 4, "V5": 5}
    vnum = vorder[variant_id]

    # V0 Opt 1: Hoist R2 * s outside while(1) in lnp-quad.c
    quad = _sub(
        quad,
        """  dom = 0;
  while (1)
    {
      baseline_counts[3]++;
      /* y1, y2 */""",
        """  /* Optimization 1 (P0): Hoist invariant R2 * s outside rejection sampling loop */
  polyvec_mulsparse (tmp, R2, s);
  polyvec_fromcrt (tmp);

  dom = 0;
  while (1)
    {
      baseline_counts[3]++;
      /* y1, y2 */""",
        label="V0 quad hoist R2*s",
    )
    quad = _sub(
        quad,
        """      /* g1 */

      polyvec_dot2 (g1, r1, y);
      polyvec_mulsparse (R2y, R2, y);
      polyvec_fromcrt (R2y); // reduce XXX
      poly_adddot (g1, s, R2y, 0);
      polyvec_mulsparse (tmp, R2, s);
      polyvec_fromcrt (tmp); // reduce XXX
      poly_adddot (g1, y, tmp, 0);
      poly_fromcrt (g1);""",
        """      /* g1 (tmp = R2 * s is already precomputed outside the rejection loop) */

      polyvec_dot2 (g1, r1, y);
      polyvec_mulsparse (R2y, R2, y);
      polyvec_fromcrt (R2y); // reduce XXX
      poly_adddot (g1, s, R2y, 0);
      poly_adddot (g1, y, tmp, 0);
      poly_fromcrt (g1);""",
        label="V0 quad g1 remove R2*s",
    )

    # V0 Opt 2: Branchless int64_t svR in lin-proofs.c (_z4 and _z3)
    lin = _sub(
        lin,
        """  if (Rq->q->nlimbs == 1 && 1) // XXX add condition on q
    {
      const limb_t sq = Rq->q->limbs[0];
      __int128 svR[lambda * nprime * d];
      __int128 *sacc;
      int64_t schal;

      memset (&svR, 0, sizeof (svR));

      for (i = 0; i < 256; i++)
        {
          __expand_Rprime_i (Rprimei, nprime * d, i, seed);

          for (k = 0; k < lambda; k++)
            {
              chal = intmat_get_elem (V, k, i);
              schal = int_get_i64 (chal);

              for (j = 0; j < nprime * d; j++)
                {
                  if (Rprimei[j] == 0)
                    {
                    }
                  else
                    {
                      ASSERT_ERR (Rprimei[j] == 1 || Rprimei[j] == -1);

                      sacc = svR + (k * nprime * d) + j;

                      *sacc += schal * Rprimei[j];
                    }
                }
            }
        }

      for (k = 0; k < lambda; k++)
        {
          for (j = 0; j < nprime * d; j++)
            {
              coeff2 = intmat_get_elem (vR_, k, j); // XXX correct
              int_set_i64 (coeff2, svR[(k * nprime * d) + j] % sq);
            }
        }
    }""",
        """  if (Rq->q->nlimbs == 1 && Rq->q->limbs[0] < (1ULL << 55))
    {
      const int64_t sq = (int64_t)Rq->q->limbs[0];
      int64_t svR[lambda * nprime * d];
      int64_t *sacc;
      int64_t schal;

      memset (&svR, 0, sizeof (svR));

      for (i = 0; i < 256; i++)
        {
          __expand_Rprime_i (Rprimei, nprime * d, i, seed);

          for (k = 0; k < lambda; k++)
            {
              chal = intmat_get_elem (V, k, i);
              schal = int_get_i64 (chal);
              sacc = svR + (k * nprime * d);

              for (j = 0; j < nprime * d; j++)
                {
                  sacc[j] += schal * (int64_t)Rprimei[j];
                }
            }
        }

      for (k = 0; k < lambda; k++)
        {
          for (j = 0; j < nprime * d; j++)
            {
              coeff2 = intmat_get_elem (vR_, k, j);
              int_set_i64 (coeff2, svR[(k * nprime * d) + j] % sq);
            }
        }
    }""",
        label="V0 lin svR z4",
    )

    lin = _sub(
        lin,
        """  if (Rq->q->nlimbs == 1 && 1) // XXX add condition on q
    {
      const limb_t sq = Rq->q->limbs[0];
      __int128 svR[lambda * nex * d];
      __int128 *sacc;
      int64_t schal;

      memset (&svR, 0, sizeof (svR));

      for (i = 0; i < 256; i++)
        {
          __expand_R_i (Ri, nex * d, i, seed);

          for (k = 0; k < lambda; k++)
            {
              chal = intmat_get_elem (V, k, i);
              schal = int_get_i64 (chal);

              for (j = 0; j < nex * d; j++)
                {
                  if (Ri[j] == 0)
                    {
                    }
                  else
                    {
                      ASSERT_ERR (Ri[j] == 1 || Ri[j] == -1);

                      sacc = svR + (k * nex * d) + j;

                      *sacc += schal * Ri[j];
                    }
                }
            }
        }

      for (k = 0; k < lambda; k++)
        {
          for (j = 0; j < nex * d; j++)
            {
              coeff2 = intmat_get_elem (vR_, k, j); // XXX correct
              int_set_i64 (coeff2, svR[(k * nex * d) + j] % sq);
            }
        }
    }""",
        """  if (Rq->q->nlimbs == 1 && Rq->q->limbs[0] < (1ULL << 55))
    {
      const int64_t sq = (int64_t)Rq->q->limbs[0];
      int64_t svR[lambda * nex * d];
      int64_t *sacc;
      int64_t schal;

      memset (&svR, 0, sizeof (svR));

      for (i = 0; i < 256; i++)
        {
          __expand_R_i (Ri, nex * d, i, seed);

          for (k = 0; k < lambda; k++)
            {
              chal = intmat_get_elem (V, k, i);
              schal = int_get_i64 (chal);
              sacc = svR + (k * nex * d);

              for (j = 0; j < nex * d; j++)
                {
                  sacc[j] += schal * (int64_t)Ri[j];
                }
            }
        }

      for (k = 0; k < lambda; k++)
        {
          for (j = 0; j < nex * d; j++)
            {
              coeff2 = intmat_get_elem (vR_, k, j);
              int_set_i64 (coeff2, svR[(k * nex * d) + j] % sq);
            }
        }
    }""",
        label="V0 lin svR z3",
    )

    # V0 Opt 4a: anon_cred.py Python-level A_P1 / A_P2 statement caching + H2 cache
    anon_py_v0 = _sub(
        anon_py,
        'class user_t:\n    def __init__(self, pk: falcon_pkenc):\n        self.B2 = falcon_decode_pk(pk,RING) #\n        self.p1_prover = lin_prover_state_t(P1PP, lib.get_params("p1_param"))\n        self.p2_prover = lin_prover_state_t(P2PP, lib.get_params("p2_param"))\n\n    def maskmsg(self, msg: bytes):\n        m = polyvec_t(RING,8,msg)\n        seed = secrets.token_bytes(32)  # internal coins\n        logsigma = 1                    # sigma = 1.55*2^logsigma\n        l2sqr_bnd = wl2[0] * wl2[0]     # l2(r1,r2)^2\n        r=polyvec_t.grandom_static(RING,16,logsigma,seed,0,0,l2sqr_bnd)\n        t = AR*r + AM*m\n\n        # prove [Ar,Am]*(r,m) + (-t) = 0\n        # as PoK(w): Aw + u = 0\n        A = polymat_t(RING, 8, 24, [AR, AM])\n        u = polyvec_t(RING, 8, [-t])\n        w = polyvec_t(RING, 24, [r, m])\n   \n        self.p1_prover.set_statement(A, u)\n        self.p1_prover.set_witness(w)\n        \n        proof = self.p1_prover.prove()\n\n        # encode t\n        coder = coder_t()\n        coder.enc_begin(22000)\n        coder.enc_urandom(mod, t)\n        tenc = coder.enc_end()\n\n        # save randomness and message\n        self.r = r\n        self.m = m\n        # return masked message t,p1enc\n        return tenc + proof\n\n    def sign(self, blindsig: bytes, pub_mvec: list):\n        # decode blindsig tau,s1,s2\n        \n        tau, s1, s2 = bytes(64), polyvec_t(RING,8), polyvec_t(RING,8)\n        try:\n            coder = coder_t()\n            coder.dec_begin(blindsig)\n            coder.dec_bytes(tau)\n            coder.dec_grandom(165, s1)\n            coder.dec_grandom(165, s2)\n            coder.dec_end()\n        except DecodingError:\n            raise InvalidMaskedMsg\n\n        tau_ = polyvec_t(RING, 8, tau)\n\n        # prove [Ar,Atau,-B1,-B2]*(r,tau,s1,s2) + Am*m = 0\n        # as PoK(w): Aw + u = 0\n        \n        m_priv=self.m.zero_out_pols(pub_mvec)\n        #m_priv=self.m.copy()\n        AM_priv=AM.zero_out_cols(pub_mvec)\n        if len(pub_mvec)==0:\n            u=polyvec_t(RING,8)\n        else:\n            m_pub=self.m.get_pol_list(pub_mvec)\n            AM_pub=AM.get_col_list(pub_mvec)\n            u=polyvec_t(RING, 8, [AM_pub * m_pub])\n      \n\n        A = polymat_t(RING, 8, 48, [AR, ATAU, -B1, -self.B2, AM_priv])        \n        w = polyvec_t(RING, 48, [self.r, tau_, s1, s2, m_priv])\n\n        self.p2_prover.set_statement(A, u)\n        self.p2_prover.set_witness(w)\n        proof = self.p2_prover.prove()\n\n        return proof\n\n\nclass signer_t:\n    def __init__(self, pk: falcon_pkenc, sk: falcon_skenc):\n        self.sk = sk\n        self.p1_verifier = lin_verifier_state_t(P1PP, lib.get_params("p1_param"))\n\n    def sign(self, masked_msg: bytes):\n        # decode masked message\n        t = polyvec_t(RING,8)\n        try:\n            coder = coder_t()\n            coder.dec_begin(masked_msg)\n            coder.dec_urandom(mod, t)\n            tlen = coder.dec_end()\n        except DecodingError:\n            raise InvalidMaskedMsg\n        \n        # verify proof for PoK(w): Aw + u = 0\n        A = polymat_t(RING, 8, 24, [AR, AM])\n        u = polyvec_t(RING, 8, [-t])\n        proof = masked_msg[tlen:]\n\n        self.p1_verifier.set_statement(A, u)\n        try:\n            self.p1_verifier.verify(proof)\n        except VerificationError:\n            raise InvalidMaskedMsg("Masked message invalid.")\n\n        # internal coins\n        tau_ = secrets.token_bytes(64)\n        tau = polyvec_t(RING,8,tau_)\n\n        # preimage sampling\n        s1, s2 = falcon_preimage_sample(self.sk, ATAU * tau + t,RING)\n        #s1, s2 = falcon_preimage_sample(self.sk, ATAU * tau + t)\n\n        # encode blindsig tau,s1,s2\n        coder = coder_t()\n        coder.enc_begin(2000)\n        coder.enc_bytes(tau_)\n        coder.enc_grandom(165, s1)\n        coder.enc_grandom(165, s2)\n        blindsig = coder.enc_end()\n\n        return blindsig\n\n\nclass verifier_t:\n    def __init__(self, pk: falcon_pkenc):\n        self.B2 = falcon_decode_pk(pk,RING)\n        self.p2_verifier = lin_verifier_state_t(P2PP, lib.get_params("p2_param"))\n\n    #the private part should already be zeroed out in pub_msg \n    def verify(self, pub_msg: bytes, pub_mvec:list, sig: bytes):\n        \n        m = polyvec_t(RING, 8, pub_msg)\n        AM_priv=AM.zero_out_cols(pub_mvec)\n        if len(pub_mvec)==0:\n            u=polyvec_t(RING,8)\n        else:\n            m_pub=m.get_pol_list(pub_mvec)\n            AM_pub=AM.get_col_list(pub_mvec)\n            u=polyvec_t(RING, 8, [AM_pub * m_pub])\n\n        # verify proof for PoK(w): Aw + u = 0\n        A = polymat_t(RING, 8, 48, [AR, ATAU, -B1, -self.B2, AM_priv])\n        #u = polyvec_t(RING, 8, [AM_pub * m_pub])\n        proof = sig\n        \n        self.p2_verifier.set_statement(A, u)\n        try:\n            self.p2_verifier.verify(proof)\n        except VerificationError:\n            raise InvalidSignature("Signature invalid.")',
        'AR.redc(); AM.redc(); ATAU.redc(); B1.redc()\nA_P1_STATIC = polymat_t(RING, 8, 24, [AR, AM])\n\n\nAR.redc(); AM.redc(); ATAU.redc(); B1.redc()\n\n\nclass user_t:\n    def __init__(self, pk: falcon_pkenc):\n        self.B2 = falcon_decode_pk(pk,RING) #\n        self.B2.redc()\n        self._B2_h2 = falcon_decode_pk(pk,RING)\n        self.p1_prover = lin_prover_state_t(P1PP, lib.get_params("p1_param"))\n        self.p2_prover = lin_prover_state_t(P2PP, lib.get_params("p2_param"))\n        self.p1_prover.set_statement_A(A_P1_STATIC)\n        self._p2_cached_pub_key = None\n        self._verified_blindsig_cache = None\n\n    def maskmsg(self, msg: bytes):\n        m = polyvec_t(RING,8,msg)\n        seed = secrets.token_bytes(32)  # internal coins\n        logsigma = 1                    # sigma = 1.55*2^logsigma\n        l2sqr_bnd = wl2[0] * wl2[0]     # l2(r1,r2)^2\n        r=polyvec_t.grandom_static(RING,16,logsigma,seed,0,0,l2sqr_bnd)\n        t = AR*r + AM*m\n\n        # prove [Ar,Am]*(r,m) + (-t) = 0\n        # as PoK(w): Aw + u = 0\n        u = polyvec_t(RING, 8, [-t])\n        w = polyvec_t(RING, 24, [r, m])\n   \n        self.p1_prover.set_statement_t(u)\n        self.p1_prover.set_witness(w)\n        \n        proof = self.p1_prover.prove()\n\n        # encode t\n        coder = coder_t()\n        coder.enc_begin(22000)\n        coder.enc_urandom(mod, t)\n        tenc = coder.enc_end()\n\n        # save randomness and message\n        self.r = r\n        self.m = m\n        self._verified_blindsig_cache = None\n        # return masked message t,p1enc\n        return tenc + proof\n\n    def verify_blindsig(self, blindsig: bytes):\n        """BLNS23 Fig. 19 H2 check: decode and validate (tau, s1, s2) from issuer without mutating self.B2."""\n        if self._verified_blindsig_cache is not None and self._verified_blindsig_cache[0] == blindsig:\n            return self._verified_blindsig_cache[1:]\n        tau, s1, s2 = bytes(64), polyvec_t(RING,8), polyvec_t(RING,8)\n        try:\n            coder = coder_t()\n            coder.dec_begin(blindsig)\n            coder.dec_bytes(tau)\n            coder.dec_grandom(165, s1)\n            coder.dec_grandom(165, s2)\n            blindsig_len = coder.dec_end()\n        except DecodingError:\n            raise InvalidBlindSig("Blind signature decoding failed.")\n        if blindsig_len != len(blindsig):\n            raise InvalidBlindSig("Trailing bytes in blind signature.")\n        tau_ = polyvec_t(RING, 8, tau)\n        if s1.l2sqr() + s2.l2sqr() > 34034726:\n            raise InvalidBlindSig("Blind signature (s1, s2) l2-norm exceeds bound.")\n        if hasattr(self, "r") and hasattr(self, "m"):\n            lhs = B1 * s1.copy() + self._B2_h2 * s2.copy()\n            rhs = AR * self.r.copy() + AM * self.m.copy() + ATAU * tau_.copy()\n            if lhs != rhs:\n                raise InvalidBlindSig("Blind signature linear relation check failed.")\n        self._verified_blindsig_cache = (blindsig, tau_, s1, s2)\n        return tau_, s1, s2\n\n    def sign(self, blindsig: bytes, pub_mvec: list):\n        # decode and H2-validate blindsig tau,s1,s2\n        tau_, s1, s2 = self.verify_blindsig(blindsig)\n        pub_mvec = list(dict.fromkeys(pub_mvec))\n\n        # prove [Ar,Atau,-B1,-B2]*(r,tau,s1,s2) + Am*m = 0\n        # as PoK(w): Aw + u = 0\n        m_priv=self.m.zero_out_pols(pub_mvec)\n        if len(pub_mvec)==0:\n            u=polyvec_t(RING,8)\n        else:\n            m_pub=self.m.get_pol_list(pub_mvec)\n            AM_pub=AM.get_col_list(pub_mvec)\n            u=polyvec_t(RING, 8, [AM_pub * m_pub])\n\n        pub_key = tuple(pub_mvec)\n        if self._p2_cached_pub_key != pub_key:\n            AM_priv=AM.zero_out_cols(pub_mvec)\n            A = polymat_t(RING, 8, 48, [AR, ATAU, -B1, -self.B2, AM_priv])\n            self.p2_prover.set_statement_A(A)\n            self._p2_cached_pub_key = pub_key\n\n        w = polyvec_t(RING, 48, [self.r, tau_, s1, s2, m_priv])\n        self.p2_prover.set_statement_t(u)\n        self.p2_prover.set_witness(w)\n        proof = self.p2_prover.prove()\n\n        return proof\n\n\nclass signer_t:\n    def __init__(self, pk: falcon_pkenc, sk: falcon_skenc):\n        self.sk = sk\n        self.p1_verifier = lin_verifier_state_t(P1PP, lib.get_params("p1_param"))\n        self.p1_verifier.set_statement_A(A_P1_STATIC)\n\n    def sign(self, masked_msg: bytes, strict: bool = False):\n        # decode masked message\n        t = polyvec_t(RING,8)\n        try:\n            coder = coder_t()\n            coder.dec_begin(masked_msg)\n            coder.dec_urandom(mod, t)\n            tlen = coder.dec_end()\n        except DecodingError:\n            raise InvalidMaskedMsg\n        \n        # verify proof for PoK(w): Aw + u = 0\n        u = polyvec_t(RING, 8, [-t])\n        proof = masked_msg[tlen:]\n\n        self.p1_verifier.set_statement_t(u)\n        try:\n            self.p1_verifier.verify(proof, strict=strict)\n        except VerificationError:\n            raise InvalidMaskedMsg("Masked message invalid.")\n\n        # internal coins\n        tau_ = secrets.token_bytes(64)\n        tau = polyvec_t(RING,8,tau_)\n\n        # preimage sampling\n        s1, s2 = falcon_preimage_sample(self.sk, ATAU * tau + t,RING)\n        #s1, s2 = falcon_preimage_sample(self.sk, ATAU * tau + t)\n\n        # encode blindsig tau,s1,s2\n        coder = coder_t()\n        coder.enc_begin(2000)\n        coder.enc_bytes(tau_)\n        coder.enc_grandom(165, s1)\n        coder.enc_grandom(165, s2)\n        blindsig = coder.enc_end()\n\n        return blindsig\n\n\nclass verifier_t:\n    def __init__(self, pk: falcon_pkenc):\n        self.B2 = falcon_decode_pk(pk,RING)\n        self.B2.redc()\n        self.p2_verifier = lin_verifier_state_t(P2PP, lib.get_params("p2_param"))\n        self._p2_cached_pub_key = None\n\n    #the private part should already be zeroed out in pub_msg \n    def verify(self, pub_msg: bytes, pub_mvec:list, sig: bytes, strict: bool = False):\n        if strict:\n            if len(pub_msg) != 64:\n                raise InvalidSignature("Public message container must be 64 bytes.")\n            pub_set = set(pub_mvec)\n            if len(pub_set) != len(pub_mvec) or any(i < 0 or i >= 8 for i in pub_mvec):\n                raise InvalidSignature("Invalid disclosed attribute indices.")\n            for i in range(8):\n                if i not in pub_set and any(pub_msg[i*8:(i+1)*8]):\n                    raise InvalidSignature("Undisclosed attribute slot in pub_msg is non-zero.")\n        pub_mvec = list(dict.fromkeys(pub_mvec))\n        m = polyvec_t(RING, 8, pub_msg)\n        if len(pub_mvec)==0:\n            u=polyvec_t(RING,8)\n        else:\n            m_pub=m.get_pol_list(pub_mvec)\n            AM_pub=AM.get_col_list(pub_mvec)\n            u=polyvec_t(RING, 8, [AM_pub * m_pub])\n\n        # verify proof for PoK(w): Aw + u = 0\n        pub_key = tuple(pub_mvec)\n        if self._p2_cached_pub_key != pub_key:\n            AM_priv=AM.zero_out_cols(pub_mvec)\n            A = polymat_t(RING, 8, 48, [AR, ATAU, -B1, -self.B2, AM_priv])\n            self.p2_verifier.set_statement_A(A)\n            self._p2_cached_pub_key = pub_key\n        proof = sig\n        \n        self.p2_verifier.set_statement_t(u)\n        try:\n            self.p2_verifier.verify(proof, strict=strict)\n        except VerificationError:\n            raise InvalidSignature("Signature invalid.")\n\n    def verify_strict(self, pub_msg: bytes, pub_mvec: list, sig: bytes):\n        return self.verify(pub_msg, pub_mvec, sig, strict=True)',
        label="V0 anon_cred body",
    )
    out["lazer/python/anon_cred/anon_cred.py"] = anon_py_v0

    # -------------------------------------------------------------------------
    # V1: Direction 5 — C-level Ds SHAKE128 prefix (without premature coder_enc_end!)
    #                   & oDs/Ds CRT caching in thread-local dynamically-sized table
    # -------------------------------------------------------------------------
    if vnum >= 1:
        cache_helper = """
/* Direction 5 (V1): Thread-local dynamically-sized cache for static statement matrix Ds:
 * Precomputes and caches:
 *   (1) SHAKE128 absorbed prefix state after byte-aligned encoding of Ds (and Dm if l > 0),
 *       WITHOUT calling coder_enc_end() prematurely so the Fiat-Shamir stream is 100% identical to V0/B1!
 *   (2) oDs = polymat_auto(Ds) already converted to CRT representation
 *   (3) Keeps state->Ds in CRT representation so prove() never triggers _fromcrt/_tocrt on Ds
 *   (4) Dynamically grows via realloc so active entries are NEVER evicted while alive.
 */
typedef struct {
  polymat_ptr ds_key;
  polymat_t oDs;
  shake128_state_t hstate_prefix;
  int valid;
} _lin_ds_cache_entry_t;

static __thread _lin_ds_cache_entry_t *_lin_ds_cache = NULL;
static __thread size_t _lin_ds_cache_cap = 0;

static _lin_ds_cache_entry_t *
_lin_ds_cache_lookup (polymat_t Ds)
{
  size_t i;
  if (Ds == NULL || _lin_ds_cache == NULL)
    return NULL;
  for (i = 0; i < _lin_ds_cache_cap; i++)
    {
      if (_lin_ds_cache[i].valid && _lin_ds_cache[i].ds_key == Ds)
        {
          baseline_counts[10]++;
          return &_lin_ds_cache[i];
        }
    }
  return NULL;
}

static void
_lin_ds_cache_evict (polymat_t Ds)
{
  size_t i;
  if (Ds == NULL || _lin_ds_cache == NULL)
    return;
  for (i = 0; i < _lin_ds_cache_cap; i++)
    {
      if (_lin_ds_cache[i].valid && _lin_ds_cache[i].ds_key == Ds)
        {
          polymat_free (_lin_ds_cache[i].oDs);
          shake128_clear (_lin_ds_cache[i].hstate_prefix);
          _lin_ds_cache[i].valid = 0;
          _lin_ds_cache[i].ds_key = NULL;
        }
    }
}

static void
_lin_ds_cache_populate (_lin_state_t state)
{
  lin_params_srcptr params = state->params;
  lnp_tbox_params_srcptr tbox_params = params->tbox_params;
  abdlop_params_srcptr tbox = tbox_params->tbox;
  polyring_srcptr Rq = tbox->ring;
  int_srcptr q = Rq->q;
  const unsigned int log2q = polyring_get_log2q (Rq);
  const unsigned int d = Rq->d;
  const unsigned int Z = tbox_params->Z;
  const unsigned int m1 = tbox->m1 - Z;
  const unsigned int l = tbox->l;
  const unsigned int nprime = tbox_params->nprime;
  const size_t buflen = CEIL ((m1 * nprime + l * nprime) * d * log2q, 8) + 1;
  coder_state_t cstate;
  size_t len, i;
  uint8_t *buf;
  _lin_ds_cache_entry_t *slot = NULL;

  _lin_ds_cache_evict (state->Ds);
  for (i = 0; i < _lin_ds_cache_cap; i++)
    {
      if (!_lin_ds_cache[i].valid)
        {
          slot = &_lin_ds_cache[i];
          break;
        }
    }
  if (slot == NULL)
    {
      size_t new_cap = (_lin_ds_cache_cap == 0) ? 32 : (_lin_ds_cache_cap * 2);
      _lin_ds_cache_entry_t * grown = (_lin_ds_cache_entry_t *)realloc (
          _lin_ds_cache, new_cap * sizeof (_lin_ds_cache_entry_t));
      ASSERT_ERR (grown != NULL);
      memset (grown + _lin_ds_cache_cap, 0,
              (new_cap - _lin_ds_cache_cap) * sizeof (_lin_ds_cache_entry_t));
      _lin_ds_cache = grown;
      slot = &_lin_ds_cache[_lin_ds_cache_cap];
      _lin_ds_cache_cap = new_cap;
    }

  /* 1. Reduce Ds (and Dm) in coeff domain and pre-absorb into SHAKE128 prefix.
   * CRITICAL: Do NOT call coder_enc_end(cstate) here! Since d=64 is a multiple of 8,
   * coder_enc_urandom4 writes an exact multiple of 8 bits (cstate->bit_off == 0).
   * Deferring coder_enc_end(cstate) to __lnp_hash_statement_arp after encoding state->u
   * ensures the absorbed byte stream is 100% bit-for-bit identical to V0/B1. */
  polymat_redp (state->Ds, state->Ds);
  if (l > 0 && state->Dm != NULL)
    polymat_redp (state->Dm, state->Dm);

  buf = _alloc (buflen);
  coder_enc_begin (cstate, buf);
  coder_enc_urandom4 (cstate, state->Ds, q, log2q);
  if (l > 0 && state->Dm != NULL)
    coder_enc_urandom4 (cstate, state->Dm, q, log2q);
  ASSERT_ERR (cstate->bit_off == 0);
  len = coder_get_offset (cstate);
  ASSERT_ERR (len % 8 == 0);
  len >>= 3;

  shake128_init (slot->hstate_prefix);
  shake128_absorb (slot->hstate_prefix, buf, len);
  _free (buf, buflen);

  /* 2. Precompute oDs = polymat_auto(Ds) and convert both oDs and Ds to CRT domain */
  polymat_alloc (slot->oDs, Rq, nprime, m1);
  polymat_auto (slot->oDs, state->Ds);
  polymat_tocrt (slot->oDs);
  polymat_tocrt (state->Ds);

  slot->ds_key = state->Ds;
  slot->valid = 1;
  baseline_counts[11]++;
}
"""
        lin = _sub(
            lin,
            "void\n_lnp_tbox_prove (",
            cache_helper + "\nvoid\n_lnp_tbox_prove (",
            label="V1 insert _lin_ds_cache helper",
        )
        lin = _sub(
            lin,
            """  DEBUG_PRINTF (DEBUG_LEVEL >= 2, "%s", "precompute automorphisms");
  if (Ds != NULL)
    {
      polymat_alloc (oDs, Rq, nprime, m1);
      polymat_auto (oDs, Ds);
    }""",
            """  DEBUG_PRINTF (DEBUG_LEVEL >= 2, "%s", "precompute automorphisms");
  _lin_ds_cache_entry_t *_ds_ce = _lin_ds_cache_lookup (Ds);
  if (Ds != NULL && _ds_ce == NULL)
    {
      polymat_alloc (oDs, Rq, nprime, m1);
      polymat_auto (oDs, Ds);
    }""",
            label="V1 _lnp_tbox_prove oDs lookup",
        )
        lin = _sub(
            lin,
            """          r0prime_sz2, R2t, r1t, r0t, Ds, Dm, u, oDs, oDm, z4,
          hash0, // XXX why hash0 needed ??""",
            """          r0prime_sz2, R2t, r1t, r0t, Ds, Dm, u,
          (_ds_ce != NULL) ? _ds_ce->oDs : oDs, oDm, z4,
          hash0, // XXX why hash0 needed ??""",
            label="V1 _lnp_tbox_prove pass cached oDs",
        )
        lin = _sub(
            lin,
            """  if (Ds != NULL)
    polymat_free (oDs);""",
            """  if (Ds != NULL && _ds_ce == NULL)
    polymat_free (oDs);""",
            count=2,
            label="V1 _lnp_tbox_prove_and_verify free oDs",
        )
        lin = _sub(
            lin,
            """  /* precompute automorphisms */
  if (Ds != NULL)
    {
      polymat_alloc (oDs, Rq, nprime, m1);
      polymat_auto (oDs, Ds);
    }""",
            """  /* precompute automorphisms */
  _lin_ds_cache_entry_t *_ds_ce = _lin_ds_cache_lookup (Ds);
  if (Ds != NULL && _ds_ce == NULL)
    {
      polymat_alloc (oDs, Rq, nprime, m1);
      polymat_auto (oDs, Ds);
    }""",
            label="V1 _lnp_tbox_verify oDs lookup",
        )
        lin = _sub(
            lin,
            """          r0prime_sz2, R2t, r1t, r0t, Ds, Dm, u, oDs, oDm, z4, hash0,
          lambda * (2 * (d - 1) + 2 + Z), params, u0, u1, t0, t1);""",
            """          r0prime_sz2, R2t, r1t, r0t, Ds, Dm, u,
          (_ds_ce != NULL) ? _ds_ce->oDs : oDs, oDm, z4, hash0,
          lambda * (2 * (d - 1) + 2 + Z), params, u0, u1, t0, t1);""",
            label="V1 _lnp_tbox_verify pass cached oDs",
        )

        # In __lnp_hash_statement_arp: use cached SHAKE128 prefix state and call coder_enc_end ONCE at the end
        lin = _sub(
            lin,
            """  buf = _alloc (buflen);

  coder_enc_begin (cstate, buf);
  if (state->Ds != NULL)
    {
      polymat_redp (state->Ds, state->Ds);
      coder_enc_urandom4 (cstate, state->Ds, q, log2q);
    }
  if (state->Dm != NULL)
    {
      polymat_redp (state->Dm, state->Dm);
      coder_enc_urandom4 (cstate, state->Dm, q, log2q);
    }
  if (state->u != NULL)
    {
      polyvec_redp (state->u, state->u);
      coder_enc_urandom3 (cstate, state->u, q, log2q);
    }
  coder_enc_end (cstate);
  len = coder_get_offset (cstate);
  ASSERT_ERR (len % 8 == 0);
  ASSERT_ERR (len / 8 <= buflen);
  len >>= 3; /* nbits to nbytes */

  shake128_init (hstate);
  shake128_absorb (hstate, buf, len);
  shake128_squeeze (hstate, state->hash_arp, 32);
  shake128_clear (hstate);

  _free (buf, buflen);""",
            """  _lin_ds_cache_entry_t *_ds_ce = _lin_ds_cache_lookup (state->Ds);
  if (_ds_ce != NULL)
    {
      const size_t u_buflen = CEIL (nprime * d * log2q, 8) + 1;
      buf = _alloc (u_buflen);
      memcpy (hstate, _ds_ce->hstate_prefix, sizeof (shake128_state_t));
      coder_enc_begin (cstate, buf);
      if (state->u != NULL)
        {
          polyvec_redp (state->u, state->u);
          coder_enc_urandom3 (cstate, state->u, q, log2q);
        }
      coder_enc_end (cstate);
      len = coder_get_offset (cstate);
      ASSERT_ERR (len % 8 == 0);
      len >>= 3;
      shake128_absorb (hstate, buf, len);
      shake128_squeeze (hstate, state->hash_arp, 32);
      shake128_clear (hstate);
      _free (buf, u_buflen);
    }
  else
    {
      buf = _alloc (buflen);

      coder_enc_begin (cstate, buf);
      if (state->Ds != NULL)
        {
          polymat_redp (state->Ds, state->Ds);
          coder_enc_urandom4 (cstate, state->Ds, q, log2q);
        }
      if (state->Dm != NULL)
        {
          polymat_redp (state->Dm, state->Dm);
          coder_enc_urandom4 (cstate, state->Dm, q, log2q);
        }
      if (state->u != NULL)
        {
          polyvec_redp (state->u, state->u);
          coder_enc_urandom3 (cstate, state->u, q, log2q);
        }
      coder_enc_end (cstate);
      len = coder_get_offset (cstate);
      ASSERT_ERR (len % 8 == 0);
      ASSERT_ERR (len / 8 <= buflen);
      len >>= 3; /* nbits to nbytes */

      shake128_init (hstate);
      shake128_absorb (hstate, buf, len);
      shake128_squeeze (hstate, state->hash_arp, 32);
      shake128_clear (hstate);

      _free (buf, buflen);
    }""",
            label="V1 __lnp_hash_statement_arp prefix",
        )
        lin = _sub(
            lin,
            """  polymat_free (state->Ds);
  _free (state->Ds, sizeof (polymat_t));
  state->Ds = NULL;""",
            """  _lin_ds_cache_evict (state->Ds);
  polymat_free (state->Ds);
  _free (state->Ds, sizeof (polymat_t));
  state->Ds = NULL;""",
            label="V1 _lin_clear evict",
        )
        lin = _sub(
            lin,
            """  if (A == NULL)
    {
      polymat_set_zero (state->Ds);
      return;
    }""",
            """  if (A == NULL)
    {
      _lin_ds_cache_evict (state->Ds);
      polymat_set_zero (state->Ds);
      return;
    }""",
            label="V1 _lin_set_statement_A null evict",
        )
        lin = _sub(
            lin,
            """  if (l > 0)
    polymat_free (Dm_);
  polymat_free (Ds_);
}""",
            """  if (l > 0)
    polymat_free (Dm_);
  polymat_free (Ds_);
  _lin_ds_cache_populate (state);
}""",
            label="V1 _lin_set_statement_A populate",
        )

    # -------------------------------------------------------------------------
    # V2: Direction 6 — Prover ARP z3/z4 flat-array branchless AVX2 inner product
    # -------------------------------------------------------------------------
    if vnum >= 2:
        lin = _sub(
            lin,
            """          if (Rq->q->nlimbs == 1)
            {
              int64_t sRs3coeff[256];
              int64_t scoeff;
              int_ptr iptr;

              memset (sRs3coeff, 0, sizeof (sRs3coeff));

              for (i = 0; i < 256; i++)
                {
                  __expand_R_i (Ri, nex * d, i, cseed);

                  for (j = 0; j < nex * d; j++)
                    {
                      if (Ri[j] == 0)
                        {
                        }
                      else
                        {
                          ASSERT_ERR (Ri[j] == 1 || Ri[j] == -1);

                          s3coeff = intvec_get_elem (s3coeffs, j);
                          scoeff = int_get_i64 (s3coeff);

                          sRs3coeff[i] += Ri[j] * scoeff;
                        }
                    }
                }
              for (i = 0; i < 256; i++)
                {
                  iptr = intvec_get_elem (z3coeffs, i);
                  scoeff = int_get_i64 (iptr);
                  scoeff += beta3 * sRs3coeff[i];
                  int_set_i64 (iptr, scoeff);
                }
            }""",
            """          if (Rq->q->nlimbs == 1)
            {
              /* Direction 6 (V2): flat int64_t buffer + branchless AVX2 dot product for z3 */
              int64_t s3_flat[nex * d];
              int64_t scoeff;
              int_ptr iptr;

              for (j = 0; j < nex * d; j++)
                s3_flat[j] = int_get_i64 (intvec_get_elem (s3coeffs, j));

              for (i = 0; i < 256; i++)
                {
                  int64_t acc = 0;
                  __expand_R_i (Ri, nex * d, i, cseed);

                  for (j = 0; j < nex * d; j++)
                    acc += (int64_t)Ri[j] * s3_flat[j];

                  iptr = intvec_get_elem (z3coeffs, i);
                  scoeff = int_get_i64 (iptr) + beta3 * acc;
                  int_set_i64 (iptr, scoeff);
                }
            }""",
            label="V2 ARP z3 flat AVX2",
        )
        lin = _sub(
            lin,
            """          if (Rq->q->nlimbs == 1)
            {
              int64_t sRs4coeff[256];
              int64_t scoeff;
              int_ptr iptr;

              memset (sRs4coeff, 0, sizeof (sRs4coeff));

              for (i = 0; i < 256; i++)
                {
                  __expand_Rprime_i (Rprimei, nprime * d, i, cseed);

                  for (j = 0; j < nprime * d; j++)
                    {
                      if (Rprimei[j] == 0)
                        {
                        }
                      else
                        {
                          ASSERT_ERR (Rprimei[j] == 1 || Rprimei[j] == -1);

                          s4coeff = intvec_get_elem (s4coeffs, j);
                          scoeff = int_get_i64 (s4coeff);

                          sRs4coeff[i] += Rprimei[j] * scoeff;
                        }
                    }
                }
              for (i = 0; i < 256; i++)
                {
                  iptr = intvec_get_elem (z4coeffs, i);
                  scoeff = int_get_i64 (iptr);
                  scoeff += beta4 * sRs4coeff[i];
                  int_set_i64 (iptr, scoeff);
                }
            }""",
            """          if (Rq->q->nlimbs == 1)
            {
              /* Direction 6 (V2): flat int64_t buffer + branchless AVX2 dot product for z4 */
              int64_t s4_flat[nprime * d];
              int64_t scoeff;
              int_ptr iptr;

              for (j = 0; j < nprime * d; j++)
                s4_flat[j] = int_get_i64 (intvec_get_elem (s4coeffs, j));

              for (i = 0; i < 256; i++)
                {
                  int64_t acc = 0;
                  __expand_Rprime_i (Rprimei, nprime * d, i, cseed);

                  for (j = 0; j < nprime * d; j++)
                    acc += (int64_t)Rprimei[j] * s4_flat[j];

                  iptr = intvec_get_elem (z4coeffs, i);
                  scoeff = int_get_i64 (iptr) + beta4 * acc;
                  int_set_i64 (iptr, scoeff);
                }
            }""",
            label="V2 ARP z4 flat AVX2",
        )

    # -------------------------------------------------------------------------
    # V3A / V3: Direction 7a (Lazy cs2 evaluation after rej1) + Direction 7b (single-limb poly_scale)
    # -------------------------------------------------------------------------
    if vnum >= 3:
        quad = _sub(
            quad,
            """      polyvec_scale2 (cs1, c, s1);
      polyvec_scale2 (cs2, c, s2); // XXX correct
      polyvec_add (y1, y1, cs1, 0);
      polyvec_add (y2, y2, cs2,
                   0); // XXX correct, XXX sample sign with bimodal ?

      ASSERT_ERR (params->rej1 == 0 || params->rej1 == 1);
      if (params->rej1)
        {
          /* to coeff rep */
          polyvec_fromcrt (y1);
          polyvec_fromcrt (cs1);

          rej = rej_standard (rngstate, z1coeffs, cs1coeffs, params->scM1,
                              params->stdev1sqr);
          if (rej)
            {
              baseline_counts[4]++;
              DEBUG_PRINTF (DEBUG_PRINT_REJ, "%s", "reject on s1");
              continue;
            }
        }
      ASSERT_ERR (params->rej2 == 0 || params->rej2 == 1 || params->rej2 == 2);""",
            """      /* Direction 7a (V3A/V3): Lazy cs2 evaluation — only compute cs2 = c*s2 and y2 += cs2
       * AFTER z1 passes rej1 (~56.9% of iterations reject on z1). */
      polyvec_scale2 (cs1, c, s1);
      polyvec_add (y1, y1, cs1, 0);

      ASSERT_ERR (params->rej1 == 0 || params->rej1 == 1);
      if (params->rej1)
        {
          /* to coeff rep */
          polyvec_fromcrt (y1);
          polyvec_fromcrt (cs1);

          rej = rej_standard (rngstate, z1coeffs, cs1coeffs, params->scM1,
                              params->stdev1sqr);
          if (rej)
            {
              baseline_counts[4]++;
              DEBUG_PRINTF (DEBUG_PRINT_REJ, "%s", "reject on s1");
              continue;
            }
        }

      polyvec_scale2 (cs2, c, s2); // XXX correct
      polyvec_add (y2, y2, cs2,
                   0); // XXX correct, XXX sample sign with bimodal ?

      ASSERT_ERR (params->rej2 == 0 || params->rej2 == 1 || params->rej2 == 2);""",
            label="V3 lazy cs2 in lnp-quad.c",
        )

        if variant_id != "V3A":
            poly = out["lazer/src/poly.c"]
            poly = _sub(
                poly,
                """  INTVEC_T (tmp, polyring_get_deg (ring), 2 * a->nlimbs);

  _fromcrt (b); // XXX can also do this in crt dom

  r->crt = 0;
  intvec_scale (tmp, a, _get_coeffvec_src (b));
  intvec_mod (r->coeffs, tmp, ring->q);
  intvec_redc (r->coeffs, r->coeffs, ring->q);""",
                """  _fromcrt (b); // XXX can also do this in crt dom

  r->crt = 0;
  if (ring->q->nlimbs == 1 && !ring->q->neg && (uint64_t)ring->q->limbs[0] > 0
      && (uint64_t)ring->q->limbs[0] <= (uint64_t)INT64_MAX && a->nlimbs == 1
      && _get_coeffvec_src (b)->nlimbs == 1)
    {
      /* Direction 7b (V3): single-limb native __int128 modular scaling fast path.
       * Reduce unsigned magnitudes modulo uq BEFORE applying sign bits (a->neg, belem->neg)
       * so all 1-limb integers in [-(2^64 - 1), +(2^64 - 1)] (including 2^63) are 100% exact. */
      const uint64_t uq = (uint64_t)ring->q->limbs[0];
      const int64_t sq = (int64_t)uq;
      const int64_t half_q = sq >> 1;
      const uint64_t ua_mod = ((uint64_t)a->limbs[0]) % uq;
      const int64_t sa = a->neg ? -(int64_t)ua_mod : (int64_t)ua_mod;
      const unsigned int deg = polyring_get_deg (ring);
      intvec_srcptr bcoeffs = _get_coeffvec_src (b);
      unsigned int k;

      for (k = 0; k < deg; k++)
        {
          int_srcptr belem = intvec_get_elem_src (bcoeffs, k);
          const uint64_t ub_mod = ((uint64_t)belem->limbs[0]) % uq;
          const int64_t sb = belem->neg ? -(int64_t)ub_mod : (int64_t)ub_mod;
          int64_t rem = (int64_t)(((__int128)sa * (__int128)sb) % (__int128)sq);
          if (rem > half_q)
            rem -= sq;
          else if (rem < -half_q)
            rem += sq;
          int_set_i64 (intvec_get_elem (r->coeffs, k), rem);
        }
    }
  else
    {
      INTVEC_T (tmp, polyring_get_deg (ring), 2 * a->nlimbs);
      intvec_scale (tmp, a, _get_coeffvec_src (b));
      intvec_mod (r->coeffs, tmp, ring->q);
      intvec_redc (r->coeffs, r->coeffs, ring->q);
    }""",
                label="V3 single-limb poly_scale fast path",
            )
            out["lazer/src/poly.c"] = poly

    # -------------------------------------------------------------------------
    # V4: Direction 8 — IEEE-754 double hi-53 fast-path filter in rejection.c
    # -------------------------------------------------------------------------
    if vnum >= 4:
        rej = out["lazer/src/rejection.c"]
        rej = _sub(
            rej,
            "#include <mpfr.h>",
            """#include <math.h>
#include <mpfr.h>

/* Direction 8 (V4): Lazy floating-point pre-filter (cf. Ducas & Nguyen, ASIACRYPT 2012, Alg. 5)
 * adapted to LNP22/LaZer rej_standard and rej_bimodal.
 * Converts multi-limb integer x (nlimbs <= 6) into IEEE-754 binary64 (53-bit significand, u = 2^-53)
 * with relative conversion error <= 6 * u < 6.67e-16.
 * Under the explicitly enforced runtime domain check |arg| <= 32 andnlimbs <= 6,
 * allowing up to 4 ULP for glibc libm exp/cosh, the total relative error is bounded by:
 *   delta_max <= (32 * 14 + 12) * 2^-53 < 5.2e-14 << gamma = 1e-11 (> 190x safety margin).
 * Any sample inside [1 - 1e-11, 1 + 1e-11] or outside |arg| <= 32 falls back to 128-bit MPFR.
 */
static inline double
_int_to_double_hi53 (const int_t x)
{
  double acc = 0.0;
  double base = 1.0;
  unsigned int i;
  for (i = 0; i < x->nlimbs; i++)
    {
      acc += (double)(x->limbs[i]) * base;
      base *= 18446744073709551616.0; /* 2^64 */
    }
  return x->neg ? -acc : acc;
}""",
            label="V4 rejection.c _int_to_double_hi53 helper",
        )
        rej = _sub(
            rej,
            """  mpfr_init2 (t3, 128);

  /* u <- {0, ..., 2^128 - 1} */
  int_set_i64 (u, 0);
  rng_urandom (state, (uint8_t *)u->limbs, 128 / 8);

  int_mul (mu, scM, u); /* M * u */

  intvec_dot (t1, z, v);  /* <z,v> */
  int_lshift (t1, t1, 1); /* 2*<z,v> */
  intvec_dot (t2, v, v);  /* <v,v>*/
  int_sub (t2, t2, t1);   /* <v,v> - 2*<z,v> */

  int_lshift (sigma2dbl, sigma2, 1); /* 2*sigma^2 */

  _int2mpfr (nom, t2, 128);""",
            """  /* u <- {0, ..., 2^128 - 1} */
  int_set_i64 (u, 0);
  rng_urandom (state, (uint8_t *)u->limbs, 128 / 8);

  int_mul (mu, scM, u); /* M * u */

  intvec_dot (t1, z, v);  /* <z,v> */
  int_lshift (t1, t1, 1); /* 2*<z,v> */
  intvec_dot (t2, v, v);  /* <v,v>*/
  int_sub (t2, t2, t1);   /* <v,v> - 2*<z,v> */

  int_lshift (sigma2dbl, sigma2, 1); /* 2*sigma^2 */

  /* Direction 8 (V4): IEEE-754 double fast-path filter with explicit domain check & 1e-11 guard band */
  if (t2->nlimbs <= 6 && sigma2dbl->nlimbs <= 6 && mu->nlimbs <= 6)
    {
      const double d_nom = _int_to_double_hi53 (t2);
      const double d_den = _int_to_double_hi53 (sigma2dbl);
      if (d_den > 0.0 && d_nom <= 0.0 && -d_nom <= 32.0 * d_den)
        {
          const double d_mu = ldexp (_int_to_double_hi53 (mu), -256);
          const double d_rhs = exp (d_nom / d_den);
          if (isfinite (d_rhs) && isfinite (d_mu))
            {
              if (d_mu > d_rhs * (1.0 + 1e-11))
                {
                  baseline_counts[8]++;
                  return 1;
                }
              if (d_mu < d_rhs * (1.0 - 1e-11))
                {
                  baseline_counts[8]++;
                  return 0;
                }
            }
        }
    }
  baseline_counts[9]++;

  mpfr_init2 (t3, 128);

  _int2mpfr (nom, t2, 128);""",
            label="V4 rej_standard fastpath",
        )
        rej = _sub(
            rej,
            """  mpfr_init2 (t3, 128);
  mpfr_init2 (t4, 128);
  mpfr_init2 (t6, 128);

  /* u <- {0, ..., 2^128 - 1} */
  int_set_i64 (u, 0);
  rng_urandom (state, (uint8_t *)u->limbs,
               128 / 8); /* XXX not endian neutral */

  int_mul (Mu, scM, u); /* M * u */

  intvec_dot (t1, z, v); /* <z,v> */
  intvec_dot (t2, v, v); /* <v,v>*/
  int_neg (t2, t2);      /* -<v,v>*/

  int_lshift (sigma2dbl, sigma2, 1); /* 2*sigma^2 */
  int_set (_sigma2, sigma2);

  _int2mpfr (nom, t2, 128);""",
            """  /* u <- {0, ..., 2^128 - 1} */
  int_set_i64 (u, 0);
  rng_urandom (state, (uint8_t *)u->limbs,
               128 / 8); /* XXX not endian neutral */

  int_mul (Mu, scM, u); /* M * u */

  intvec_dot (t1, z, v); /* <z,v> */
  intvec_dot (t2, v, v); /* <v,v>*/
  int_neg (t2, t2);      /* -<v,v>*/

  int_lshift (sigma2dbl, sigma2, 1); /* 2*sigma^2 */
  int_set (_sigma2, sigma2);

  /* Direction 8 (V4): IEEE-754 double fast-path filter with explicit domain check & 1e-11 guard band */
  if (t2->nlimbs <= 6 && t1->nlimbs <= 6 && _sigma2->nlimbs <= 6 && Mu->nlimbs <= 6)
    {
      const double d_t2 = _int_to_double_hi53 (t2);
      const double d_t1 = fabs (_int_to_double_hi53 (t1));
      const double d_sig2 = _int_to_double_hi53 (_sigma2);
      if (d_sig2 > 0.0 && d_t2 <= 0.0 && -d_t2 <= 64.0 * d_sig2 && d_t1 <= 32.0 * d_sig2)
        {
          const double d_mu = ldexp (_int_to_double_hi53 (Mu), -256);
          const double d_val = d_mu * exp (d_t2 / (2.0 * d_sig2)) * cosh (d_t1 / d_sig2);
          if (isfinite (d_val))
            {
              if (d_val > 1.0 + 1e-11)
                {
                  baseline_counts[8]++;
                  return 1;
                }
              if (d_val < 1.0 - 1e-11)
                {
                  baseline_counts[8]++;
                  return 0;
                }
            }
        }
    }
  baseline_counts[9]++;

  mpfr_init2 (t3, 128);
  mpfr_init2 (t4, 128);
  mpfr_init2 (t6, 128);

  _int2mpfr (nom, t2, 128);""",
            label="V4 rej_bimodal fastpath",
        )
        out["lazer/src/rejection.c"] = rej

    # -------------------------------------------------------------------------
    # V5: Direction 9 — Disclosure-Parameterized Subspace Projection for k in {1..8}
    # -------------------------------------------------------------------------
    if vnum >= 5:
        params_h = out["lazer/python/anon_cred/anon_cred_params.h"]
        params_h = params_h.rstrip() + "\n" + _generate_compact_params_block() + "\n"
        out["lazer/python/anon_cred/anon_cred_params.h"] = params_h

        anon_py_v5 = _sub(
            anon_py_v0,
            """        self.p1_prover = lin_prover_state_t(P1PP, lib.get_params("p1_param"))
        self.p2_prover = lin_prover_state_t(P2PP, lib.get_params("p2_param"))
        self.p1_prover.set_statement_A(A_P1_STATIC)
        self._p2_cached_pub_key = None
        self._verified_blindsig_cache = None""",
            """        self.p1_prover = lin_prover_state_t(P1PP, lib.get_params("p1_param"))
        self.p2_prover = lin_prover_state_t(P2PP, lib.get_params("p2_compact3_param"))
        self.p2_prover_full = None
        self._p2_compact_provers = {3: self.p2_prover}
        self._p2_compact_cached_keys = {3: None}
        self.p1_prover.set_statement_A(A_P1_STATIC)
        self._p2_cached_pub_key = None
        self._p2_full_cached_pub_key = None
        self._verified_blindsig_cache = None""",
            label="V5 user_t init compact",
        )
        anon_py_v5 = _sub(
            anon_py_v5,
            """        m_priv=self.m.zero_out_pols(pub_mvec)
        if len(pub_mvec)==0:
            u=polyvec_t(RING,8)
        else:
            m_pub=self.m.get_pol_list(pub_mvec)
            AM_pub=AM.get_col_list(pub_mvec)
            u=polyvec_t(RING, 8, [AM_pub * m_pub])

        pub_key = tuple(pub_mvec)
        if self._p2_cached_pub_key != pub_key:
            AM_priv=AM.zero_out_cols(pub_mvec)
            A = polymat_t(RING, 8, 48, [AR, ATAU, -B1, -self.B2, AM_priv])
            self.p2_prover.set_statement_A(A)
            self._p2_cached_pub_key = pub_key

        w = polyvec_t(RING, 48, [self.r, tau_, s1, s2, m_priv])
        self.p2_prover.set_statement_t(u)
        self.p2_prover.set_witness(w)
        proof = self.p2_prover.prove()""",
            """        if len(pub_mvec)==0:
            u=polyvec_t(RING,8)
        else:
            m_pub=self.m.get_pol_list(pub_mvec)
            AM_pub=AM.get_col_list(pub_mvec)
            u=polyvec_t(RING, 8, [AM_pub * m_pub])

        pub_key = tuple(pub_mvec)
        pub_set = set(pub_mvec)
        k_disc = len(pub_set)
        if 1 <= k_disc <= 8 and k_disc == len(pub_mvec) and all(0 <= idx < 8 for idx in pub_set):
            h_priv = 8 - k_disc
            priv_indices = [i for i in range(8) if i not in pub_set]
            if k_disc == 3:
                prover = self.p2_prover
                if self._p2_cached_pub_key != pub_key:
                    AM_priv_compact = AM.get_col_list(priv_indices)
                    A = polymat_t(RING, 8, 45, [AR, ATAU, -B1, -self.B2, AM_priv_compact])
                    prover.set_statement_A(A)
                    self._p2_cached_pub_key = pub_key
            else:
                prover = self._p2_compact_provers.get(k_disc)
                if prover is None:
                    prover = lin_prover_state_t(P2PP, lib.get_params(f"p2_compact{k_disc}_param"))
                    self._p2_compact_provers[k_disc] = prover
                    self._p2_compact_cached_keys[k_disc] = None
                if self._p2_compact_cached_keys.get(k_disc) != pub_key:
                    if h_priv > 0:
                        AM_priv_compact = AM.get_col_list(priv_indices)
                        A = polymat_t(RING, 8, 40 + h_priv, [AR, ATAU, -B1, -self.B2, AM_priv_compact])
                    else:
                        A = polymat_t(RING, 8, 40, [AR, ATAU, -B1, -self.B2])
                    prover.set_statement_A(A)
                    self._p2_compact_cached_keys[k_disc] = pub_key
            if h_priv > 0:
                m_priv_compact = self.m.get_pol_list(priv_indices)
                w = polyvec_t(RING, 40 + h_priv, [self.r, tau_, s1, s2, m_priv_compact])
            else:
                w = polyvec_t(RING, 40, [self.r, tau_, s1, s2])
            prover.set_statement_t(u)
            prover.set_witness(w)
            proof = prover.prove()
        else:
            if self.p2_prover_full is None:
                self.p2_prover_full = lin_prover_state_t(P2PP, lib.get_params("p2_param"))
            m_priv = self.m.zero_out_pols(pub_mvec)
            if self._p2_full_cached_pub_key != pub_key:
                AM_priv = AM.zero_out_cols(pub_mvec)
                A = polymat_t(RING, 8, 48, [AR, ATAU, -B1, -self.B2, AM_priv])
                self.p2_prover_full.set_statement_A(A)
                self._p2_full_cached_pub_key = pub_key
            w = polyvec_t(RING, 48, [self.r, tau_, s1, s2, m_priv])
            self.p2_prover_full.set_statement_t(u)
            self.p2_prover_full.set_witness(w)
            proof = self.p2_prover_full.prove()""",
            label="V5 user_t sign compact_k",
        )
        anon_py_v5 = _sub(
            anon_py_v5,
            """class verifier_t:
    def __init__(self, pk: falcon_pkenc):
        self.B2 = falcon_decode_pk(pk,RING)
        self.B2.redc()
        self.p2_verifier = lin_verifier_state_t(P2PP, lib.get_params("p2_param"))
        self._p2_cached_pub_key = None""",
            """class verifier_t:
    def __init__(self, pk: falcon_pkenc):
        self.B2 = falcon_decode_pk(pk,RING)
        self.B2.redc()
        self.p2_verifier = lin_verifier_state_t(P2PP, lib.get_params("p2_compact3_param"))
        self.p2_verifier_full = None
        self._p2_compact_verifiers = {3: self.p2_verifier}
        self._p2_compact_cached_keys = {3: None}
        self._p2_cached_pub_key = None
        self._p2_full_cached_pub_key = None""",
            label="V5 verifier_t init compact_k",
        )
        anon_py_v5 = _sub(
            anon_py_v5,
            """        # verify proof for PoK(w): Aw + u = 0
        pub_key = tuple(pub_mvec)
        if self._p2_cached_pub_key != pub_key:
            AM_priv=AM.zero_out_cols(pub_mvec)
            A = polymat_t(RING, 8, 48, [AR, ATAU, -B1, -self.B2, AM_priv])
            self.p2_verifier.set_statement_A(A)
            self._p2_cached_pub_key = pub_key
        proof = sig
        
        self.p2_verifier.set_statement_t(u)
        try:
            self.p2_verifier.verify(proof, strict=strict)
        except VerificationError:
            raise InvalidSignature("Signature invalid.")""",
            """        # verify proof for PoK(w): Aw + u = 0
        pub_key = tuple(pub_mvec)
        pub_set = set(pub_mvec)
        k_disc = len(pub_set)
        proof = sig
        if 1 <= k_disc <= 8 and k_disc == len(pub_mvec) and all(0 <= idx < 8 for idx in pub_set):
            h_priv = 8 - k_disc
            priv_indices = [i for i in range(8) if i not in pub_set]
            if k_disc == 3:
                verifier = self.p2_verifier
                if self._p2_cached_pub_key != pub_key:
                    AM_priv_compact = AM.get_col_list(priv_indices)
                    A = polymat_t(RING, 8, 45, [AR, ATAU, -B1, -self.B2, AM_priv_compact])
                    verifier.set_statement_A(A)
                    self._p2_cached_pub_key = pub_key
            else:
                verifier = self._p2_compact_verifiers.get(k_disc)
                if verifier is None:
                    verifier = lin_verifier_state_t(P2PP, lib.get_params(f"p2_compact{k_disc}_param"))
                    self._p2_compact_verifiers[k_disc] = verifier
                    self._p2_compact_cached_keys[k_disc] = None
                if self._p2_compact_cached_keys.get(k_disc) != pub_key:
                    if h_priv > 0:
                        AM_priv_compact = AM.get_col_list(priv_indices)
                        A = polymat_t(RING, 8, 40 + h_priv, [AR, ATAU, -B1, -self.B2, AM_priv_compact])
                    else:
                        A = polymat_t(RING, 8, 40, [AR, ATAU, -B1, -self.B2])
                    verifier.set_statement_A(A)
                    self._p2_compact_cached_keys[k_disc] = pub_key
            verifier.set_statement_t(u)
            try:
                verifier.verify(proof, strict=strict)
            except VerificationError:
                raise InvalidSignature("Signature invalid.")
        else:
            if self.p2_verifier_full is None:
                self.p2_verifier_full = lin_verifier_state_t(P2PP, lib.get_params("p2_param"))
            if self._p2_full_cached_pub_key != pub_key:
                AM_priv = AM.zero_out_cols(pub_mvec)
                A = polymat_t(RING, 8, 48, [AR, ATAU, -B1, -self.B2, AM_priv])
                self.p2_verifier_full.set_statement_A(A)
                self._p2_full_cached_pub_key = pub_key
            self.p2_verifier_full.set_statement_t(u)
            try:
                self.p2_verifier_full.verify(proof, strict=strict)
            except VerificationError:
                raise InvalidSignature("Signature invalid.")""",
            label="V5 verifier_t verify compact_k",
        )
        out["lazer/python/anon_cred/anon_cred.py"] = anon_py_v5

    out["lazer/src/lin-proofs.c"] = lin
    out["lazer/src/lnp-quad.c"] = quad
    return out


def apply_variant(variant_id: str, update_freeze: bool = True) -> dict:
    variant_id = variant_id.upper()
    meta = VARIANTS[variant_id]
    sources = build_variant_sources(variant_id)

    upstream_sha = json.loads((ROOT / "UPSTREAM_SHA256.json").read_text())
    patches = json.loads((ROOT / "PATCHES.json").read_text()) if (ROOT / "PATCHES.json").exists() else {}

    diff_all = []
    audit_diff = []

    # Keep Falcon sign.c counter hook in SOURCE_CHANGES.diff
    with zipfile.ZipFile(ROOT / "lazer" / "third_party" / "Falcon-impl-20211101.zip") as z:
        falcon_orig = z.read("Falcon-impl-20211101/sign.c").decode("utf-8")
    falcon_cur = (ROOT / "lazer" / "third_party" / "Falcon-impl-20211101" / "sign.c").read_text()
    diff_all.extend(
        difflib.unified_diff(
            falcon_orig.splitlines(True),
            falcon_cur.splitlines(True),
            fromfile="lazer/third_party/Falcon-impl-20211101/sign.c.original",
            tofile="lazer/third_party/Falcon-impl-20211101/sign.c",
        )
    )

    for rel, content in sources.items():
        target = ROOT / rel
        target.write_text(content)
        orig = _read_upstream(rel)
        if content != orig:
            patches[rel] = {
                "original_sha256": upstream_sha[rel],
                "patched_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                "variant": variant_id,
            }
            diff_all.extend(
                difflib.unified_diff(
                    orig.splitlines(True),
                    content.splitlines(True),
                    fromfile=f"{rel}.original",
                    tofile=rel,
                )
            )
            if rel != "lazer/src/lazer.c":
                audit_diff.extend(
                    difflib.unified_diff(
                        orig.splitlines(True),
                        content.splitlines(True),
                        fromfile=f"{rel}.upstream",
                        tofile=f"{rel}.patched",
                    )
                )
        else:
            patches.pop(rel, None)

    hook = (ROOT / "baseline_hooks.h").read_bytes()
    (ROOT / "lazer" / "src" / "baseline_hooks.h").write_bytes(hook)
    patches["lazer/src/baseline_hooks.h"] = {"added_sha256": hashlib.sha256(hook).hexdigest()}

    (ROOT / "PATCHES.json").write_text(json.dumps(patches, indent=2))
    (ROOT / "SOURCE_CHANGES.diff").write_text("".join(diff_all))
    (ROOT / "BLNS23_AUDIT_SOURCE_DIFF.patch").write_text("".join(audit_diff))

    state_info = {
        "active_variant": variant_id,
        "variant_code": meta["code"],
        "variant_name": meta["name"],
        "direction_added": meta["direction_added"],
        "byte_identical_to_b1": meta["byte_identical_to_b1"],
        "byte_identical_to_v0": meta["byte_identical_to_v0"],
        "bugfixes_applied": meta["bugfixes_applied"],
        "optimizations_applied": meta["optimizations_applied"],
        "protocol_parameters_changed": meta["protocol_parameters_changed"],
    }
    (ROOT / "ACTIVE_VARIANT.json").write_text(json.dumps(state_info, indent=2, ensure_ascii=False))

    if update_freeze and (ROOT / "release_freeze.py").exists():
        subprocess.run([sys.executable, str(ROOT / "release_freeze.py"), "--create"], cwd=ROOT, check=True)

    return state_info


def export_all_patches() -> None:
    patch_dir = ROOT / "variants_patches"
    patch_dir.mkdir(parents=True, exist_ok=True)
    v_order = ["B0", "B1", "V0", "V1", "V2", "V3A", "V3", "V4", "V5"]
    built = {vid: build_variant_sources(vid) for vid in v_order}

    manifest = {"variants": {}, "incremental_patches": []}
    for idx, vid in enumerate(v_order):
        meta = VARIANTS[vid]
        cum_diff = []
        for rel in TOUCHED_FILES:
            if rel == "lazer/src/lazer.c":
                continue
            orig = _read_upstream(rel)
            cur = built[vid][rel]
            if cur != orig:
                cum_diff.extend(
                    difflib.unified_diff(
                        orig.splitlines(True),
                        cur.splitlines(True),
                        fromfile=f"a/{rel}",
                        tofile=f"b/{rel}",
                    )
                )
        cum_file = patch_dir / f"{meta['code']}_cumulative.patch"
        cum_file.write_text("".join(cum_diff))
        manifest["variants"][vid] = {
            **meta,
            "cumulative_patch": str(cum_file.relative_to(ROOT)),
        }

        if idx > 0:
            prev_vid = "V2" if vid == "V3" else v_order[idx - 1]
            inc_diff = []
            for rel in TOUCHED_FILES:
                prev_src = built[prev_vid][rel]
                cur_src = built[vid][rel]
                if cur_src != prev_src:
                    inc_diff.extend(
                        difflib.unified_diff(
                            prev_src.splitlines(True),
                            cur_src.splitlines(True),
                            fromfile=f"{prev_vid}/{rel}",
                            tofile=f"{vid}/{rel}",
                        )
                    )
            inc_file = patch_dir / f"step_{prev_vid}_to_{meta['code']}.patch"
            inc_file.write_text("".join(inc_diff))
            manifest["incremental_patches"].append(
                {
                    "from": prev_vid,
                    "to": vid,
                    "direction": meta["direction_added"],
                    "patch_file": str(inc_file.relative_to(ROOT)),
                }
            )

    (patch_dir / "VARIANTS_MANIFEST.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    print(f"EXPORTED_ALL_PATCHES: {len(v_order)} cumulative + {len(v_order)-1} incremental patches in {patch_dir}")


def main():
    parser = argparse.ArgumentParser(description="Switch or export LaZer optimization variants (B0, B1, V0..V5).")
    parser.add_argument("variant", nargs="?", default="V0", help="Variant ID: B0, B1, V0, V1, V2, V3A, V3, V4, or V5")
    parser.add_argument("--list", action="store_true", help="List all variants")
    parser.add_argument("--export-all-patches", action="store_true", help="Export cumulative & step patches to variants_patches/")
    parser.add_argument("--no-freeze", action="store_true", help="Skip updating FROZEN_SHA256.json")
    args = parser.parse_args()

    if args.list:
        for vid, meta in VARIANTS.items():
            print(f"{vid} ({meta['code']}): {meta['name']}")
        return

    if args.export_all_patches:
        export_all_patches()
        return

    info = apply_variant(args.variant, update_freeze=not args.no_freeze)
    print(f"SWITCHED_TO_VARIANT: {info['active_variant']} ({info['variant_code']}) - {info['variant_name']}")


if __name__ == "__main__":
    main()
