#!/usr/bin/env python3
"""TEST ONLY fixed coins: never imported by the real benchmark."""
import argparse,hashlib,json
from pathlib import Path
import baseline_api as b
ap=argparse.ArgumentParser();ap.add_argument('action',choices=['make','run']);ap.add_argument('fixture',type=Path);ap.add_argument('--test-seed',default='0');a=ap.parse_args()
test_seed=a.test_seed.encode()
b.ac.secrets.token_bytes=lambda n:hashlib.shake_256(b'TEST-ONLY-FIXED-COINS-DO-NOT-USE'+test_seed).digest(n)
original=b.lz.lin_prover_state_t.prove
b.lz.lin_prover_state_t.prove=lambda self,coins=None:original(self,hashlib.sha256(b'TEST-ONLY-PROOF-COINS'+test_seed).digest())
if a.action=='make':
 sk,pk,_=b.ac.falcon_keygen();user=b.ac.user_t(pk);issuer=b.ac.signer_t(pk,sk)
 msg=bytes(range(64));req=user.maskmsg(msg);blind=issuer.sign(req)
 a.fixture.write_text(json.dumps({'pk':b.pkbytes(pk).hex(),'msg':msg.hex(),'blind':blind.hex()}))
else:
 d=json.loads(a.fixture.read_text());pk=b.ac.falcon_pkenc();b.lz.ffi.memmove(pk.ptr,bytes.fromhex(d['pk']),897)
 msg=bytes.fromhex(d['msg']);u=b.ac.user_t(pk)
 req=u.maskmsg(msg);p=u.sign(bytes.fromhex(d['blind']),b.PUBLIC)
 b.ac.verifier_t(pk).verify(b.public_message(msg),b.PUBLIC,p)
 print(json.dumps({'request_sha256':hashlib.sha256(req).hexdigest(),'proof_sha256':hashlib.sha256(p).hexdigest(),'request_bytes':len(req),'proof_bytes':len(p),'verified':True,'fixed_coins':'TEST ONLY'}))
