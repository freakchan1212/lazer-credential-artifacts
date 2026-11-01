#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")"
python3 audit_tests.py
if [[ ! -x .venv/bin/python3 ]];then echo 'NATIVE_NOT_BUILT';exit 2;fi
# 1. Existing suite exercises tamper, issuer, disclosure, trailing bytes and hidden-slot injection (default raw API compatibility).
.venv/bin/python3 experiment.py --mode smoke --attacks-only
# 2. Verify H2 holder blind-signature checks and strict=True boundary checks (and record per-variant security evidence JSON).
.venv/bin/python3 - <<'PY'
import json, os, sys
from pathlib import Path
ROOT = Path.cwd()
vinfo = json.loads((ROOT / "ACTIVE_VARIANT.json").read_text()) if (ROOT / "ACTIVE_VARIANT.json").exists() else {"active_variant": "V0"}
vid = vinfo.get("active_variant", "V0").upper()
has_bugfixes = (vid != "B0")

os.chdir(ROOT / "lazer" / "python" / "anon_cred")
sys.path.insert(0, str(ROOT / "lazer" / "python"))
sys.path.insert(0, str(ROOT / "lazer" / "python" / "anon_cred"))
from lazer import falcon_keygen
from anon_cred import (
    signer_t, user_t, verifier_t,
    InvalidBlindSig, InvalidSignature,
)

msg = bytes((i * 7 + 3) % 256 for i in range(64))
pub_mvec = [0, 4, 5]
pub_msg_arr = bytearray(64)
for idx in pub_mvec:
    pub_msg_arr[idx * 8:(idx + 1) * 8] = msg[idx * 8:(idx + 1) * 8]
pub_msg = bytes(pub_msg_arr)

sk, pk, _ = falcon_keygen()
signer = signer_t(pk, sk)
user = user_t(pk)
verifier = verifier_t(pk)

masked = user.maskmsg(msg)
blindsig = signer.sign(masked)

checks = {}
if has_bugfixes:
    # (a) Test H2 holder verification rejects corrupted blind signature with InvalidBlindSig
    bad_bs = bytearray(blindsig)
    bad_bs[16] ^= 0x01
    try:
        user.sign(bytes(bad_bs), pub_mvec)
        raise SystemExit("FAIL: H2 holder verification did not reject corrupted blindsig")
    except InvalidBlindSig:
        checks["h2_corrupted_blindsig_rejected"] = True
        print(f"PASS [{vid}]: H2 holder verification rejected corrupted blindsig with InvalidBlindSig")

    # (b) Honest presentation proof succeeds under both default and strict=True
    sig = user.sign(blindsig, pub_mvec)
    verifier.verify(pub_msg, pub_mvec, sig, strict=False)
    verifier.verify(pub_msg, pub_mvec, sig, strict=True)
    checks["honest_proof_strict_accepted"] = True
    print(f"PASS [{vid}]: Honest proof accepted under strict=True")

    # (c) Trailing byte rejected when strict=True
    try:
        verifier.verify(pub_msg, pub_mvec, sig + b"\x00", strict=True)
        raise SystemExit("FAIL: strict=True did not reject trailing byte")
    except InvalidSignature:
        checks["strict_trailing_byte_rejected"] = True
        print(f"PASS [{vid}]: strict=True rejected proof with trailing bytes")

    # (d) Non-zero hidden attribute slot rejected when strict=True
    injected_pub_msg = bytearray(pub_msg)
    injected_pub_msg[1 * 8] ^= 0xFF
    try:
        verifier.verify(bytes(injected_pub_msg), pub_mvec, sig, strict=True)
        raise SystemExit("FAIL: strict=True did not reject non-zero hidden slot injection")
    except InvalidSignature:
        checks["strict_hidden_slot_injection_rejected"] = True
        print(f"PASS [{vid}]: strict=True rejected non-zero hidden attribute slot injection")
else:
    sig = user.sign(blindsig, pub_mvec)
    verifier.verify(pub_msg, pub_mvec, sig)
    checks["b0_pristine_honest_verify_accepted"] = True
    checks["bugfixes_enabled"] = False
    print(f"PASS [{vid}]: B0 pristine baseline honest proof accepted (bugfixes intentionally disabled in B0)")

out_dir = ROOT / "results" / "security_suites"
out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / f"security_suite_{vid}.json").write_text(json.dumps({
    "active_variant": vid,
    "has_bugfixes": has_bugfixes,
    "checks": checks,
    "status": "PASSED",
}, indent=2) + "\n")
PY
echo 'SECURITY_NEGATIVE_SUITE_AND_STRICT_CHECKS_PASSED'
