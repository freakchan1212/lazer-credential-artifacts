#!/usr/bin/env python3
"""Offline source invariant tests for active variant (B0, B1, V0..V5)."""
import json, re, sys
from pathlib import Path

R = Path(__file__).resolve().parent
vinfo = json.loads((R / 'ACTIVE_VARIANT.json').read_text()) if (R / 'ACTIVE_VARIANT.json').exists() else {'active_variant': 'V0'}
vid = vinfo.get('active_variant', 'V0').upper()

cases = {}


def check(n, ok):
    cases[n] = {'passed': bool(ok)}
    print(('PASS' if ok else 'FAIL'), f"[{vid}]", n)


quad = (R / 'lazer/src/lnp-quad.c').read_text()
blind = (R / 'lazer/src/blindsig.c').read_text()
lin = (R / 'lazer/src/lin-proofs.c').read_text()
poly = (R / 'lazer/src/poly.c').read_text()
rej = (R / 'lazer/src/rejection.c').read_text()
lazer_py = (R / 'lazer/python/lazer.py').read_text()
anon_py = (R / 'lazer/python/anon_cred/anon_cred.py').read_text()
params_h = (R / 'lazer/python/anon_cred/anon_cred_params.h').read_text()
prepare = (R / 'prepare_sources.py').read_text()
src_diff = (R / 'SOURCE_CHANGES.diff').read_text()
audit_diff = (R / 'BLNS23_AUDIT_SOURCE_DIFF.patch').read_text()


def valid_py(code, name):
    try:
        compile(code, name, 'exec')
        return True
    except SyntaxError:
        return False


check('python_syntax_lazer_and_anon_cred', valid_py(lazer_py, 'lazer.py') and valid_py(anon_py, 'anon_cred.py'))

has_bugfixes = (vid != 'B0')
has_opt_v0 = vid in ('V0', 'V1', 'V2', 'V3A', 'V3', 'V4', 'V5')
has_opt_v1 = vid in ('V1', 'V2', 'V3A', 'V3', 'V4', 'V5')
has_opt_v2 = vid in ('V2', 'V3A', 'V3', 'V4', 'V5')
has_opt_v3a = vid in ('V3A', 'V3', 'V4', 'V5')
has_opt_v3b = vid in ('V3', 'V4', 'V5')
has_opt_v4 = vid in ('V4', 'V5')
has_opt_v5 = (vid == 'V5')

# 1. Audit Fix invariants (expected True in B1 and V0..V5, False in B0)
check('quad_rej2_bimodal_uses_stdev2',
      bool(re.search(r'if \(params->rej2 == 2\).*?rej_bimodal \(rngstate, z2coeffs, cs2coeffs, params->scM2,\s*params->stdev2sqr\)', quad, re.S)) == has_bugfixes)
check('blind_r2_each_coefficient_loaded',
      bool(re.search(r'coeff = \(int32_t\)intvec_get_elem_i64 \(coeffvec, i\);\s*state->r2\[i\] = coeff;\s*l2sqr \+= \(int64_t\)coeff \* coeff;', blind)) == has_bugfixes)
check('anon_cred_h2_holder_verification',
      ('Blind signature linear relation check failed.' in anon_py and 's1.l2sqr() + s2.l2sqr() > 34034726' in anon_py) == has_bugfixes)
check('anon_cred_strict_hidden_slot_and_trailing_support',
      ('def verify(self, pub_msg: bytes, pub_mvec:list, sig: bytes, strict: bool = False)' in anon_py and 'def verify(self, proof: bytes, strict: bool = False)' in lazer_py) == has_bugfixes)

# 2. V0 optimization invariants
check('quad_R2s_hoisted_outside_rejection_loop',
      bool(re.search(r'polyvec_mulsparse \(tmp, R2, s\);\s*polyvec_fromcrt \(tmp\);\s*dom = 0;\s*while \(1\)', quad, re.S)) == has_opt_v0)
check('lin_proofs_branchless_int64_svR_z4_and_z3',
      ('int64_t svR[lambda * nprime * d];' in lin and 'int64_t svR[lambda * nex * d];' in lin) == has_opt_v0)
check('anon_cred_p1_and_p2_matrix_cached',
      ('A_P1_STATIC = polymat_t(RING, 8, 24, [AR, AM])' in anon_py and 'self.p1_prover.set_statement_A(A_P1_STATIC)' in anon_py) == has_opt_v0)

# 3. V1..V5 optimization invariants (including E2 bug fixes!)
if has_opt_v1:
    # Ensure _lin_ds_cache_populate does NOT call coder_enc_end(cstate) before absorbing Ds!
    pop_body = lin.split('_lin_ds_cache_populate')[1].split('void\n_lnp_tbox_prove')[0]
    check('v1_ds_cache_no_premature_coder_enc_end', 'coder_enc_end (cstate);' not in pop_body and 'ASSERT_ERR (cstate->bit_off == 0);' in pop_body)
    check('v1_ds_cache_thread_local_dynamic_realloc', 'static __thread _lin_ds_cache_entry_t *_lin_ds_cache' in lin and 'realloc' in pop_body)
if has_opt_v2:
    check('v2_arp_z34_flat_int64_avx2', 'int64_t s3_flat[nex * d];' in lin and 'int64_t s4_flat[nprime * d];' in lin)
if has_opt_v3a:
    check('v3a_lazy_cs2_after_rej1', 'Lazy cs2 evaluation' in quad)
if has_opt_v3b:
    check('v3b_poly_scale_unsigned_pre_reduction', 'const uint64_t ua_mod = ((uint64_t)a->limbs[0]) % uq;' in poly and 'const uint64_t ub_mod = ((uint64_t)belem->limbs[0]) % uq;' in poly)
if has_opt_v4:
    check('v4_rejection_hi53_and_counters', '_int_to_double_hi53' in rej and '32.0 * d_den' in rej and 'baseline_counts[8]++' in rej and 'baseline_counts[9]++' in rej)
if has_opt_v5:
    check('v5_all_compact_k_params_present', all(f'p2_compact{k}_param' in params_h for k in range(1, 9)) and '_p2_compact_provers' in anon_py)

# 4. Repository & patch integrity
check('prepare_reapplies_audit_patch', 'apply_audit()' in prepare)
check('source_integrity_sha_manifest', __import__('subprocess').run([sys.executable, str(R / 'verify_baseline.py')], capture_output=True).returncode == 0)
check('bimodal_sign_still_unresolved_and_flagged', 'XXX sample sign with bimodal' in quad)
check('original_frozen_hashes_archived', (R / 'ORIGINAL_FROZEN_SHA256_REFERENCE.json').exists())

out = R / 'results/audit_static'
out.mkdir(parents=True, exist_ok=True)
payload = {'active_variant': vid, 'status': 'STATIC_PASS' if all(x['passed'] for x in cases.values()) else 'STATIC_FAIL', 'tests': cases, 'zk_soundness_certified': False}
(out / 'source_checks.json').write_text(json.dumps(payload, indent=2))
(out / f'source_checks_{vid}.json').write_text(json.dumps(payload, indent=2))
sys.exit(0 if all(x['passed'] for x in cases.values()) else 1)
