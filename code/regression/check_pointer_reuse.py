#!/usr/bin/env python3
"""E4 single-thread LaZer cached Ds lifetime/address-reuse regression.

Runs genuine issuance/presentation/strict verification in the supplied, already
built E4 project. Does not patch the project or rewrite experimental results.
This is a finite correctness stress test, NOT a protocol security proof.
"""
import argparse
import ctypes
import gc
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

parser = argparse.ArgumentParser()
parser.add_argument('--root', type=Path, default=Path('.'), help='LaZer_E4_Supplement root')
parser.add_argument('--cycles', type=int, default=80)
parser.add_argument('--out', type=Path, default=Path('e4_cache_pointer_stress.json'))
args = parser.parse_args()
root = args.root.resolve()
outfile = args.out.resolve()
project = root/'project'
if args.cycles < 2: parser.error('--cycles must be >=2')
active_path = project/'ACTIVE_VARIANT.json'
if active_path.exists():
    active = json.loads(active_path.read_text()).get('active_variant')
    if active != 'C3':
        parser.error('Active variant is '+str(active)+'. First run: python3 project/e4_select.py C3 && bash project/06_rebuild_fast.sh')
if not (project/'baseline_api.py').exists() or not (project/'lazer'/'lazer.h').exists():
    parser.error('Wrong --root: cannot locate project/baseline_api.py and project/lazer/lazer.h')

# ABI-matched, read-only introspection of the pointer actually used as the C
# native cache key. This test helper is built in a TEMP directory, not the repo.
probe_source = r'''
#include <stdint.h>
#include "lazer.h"
uintptr_t e4_probe_prover_ds(void *ptr) {
  return (uintptr_t)((lin_prover_state_ptr)ptr)->state->Ds;
}
uintptr_t e4_probe_verifier_ds(void *ptr) {
  return (uintptr_t)((lin_verifier_state_ptr)ptr)->state->Ds;
}
'''
with tempfile.TemporaryDirectory(prefix='e4_cache_probe_') as work:
    src = Path(work)/'e4_cache_probe.c'
    so = Path(work)/'e4_cache_probe.so'
    src.write_text(probe_source)
    subprocess.run(['gcc','-O2','-fPIC','-shared', '-I',str(project/'lazer'),
                    str(src),'-o',str(so)], check=True)
    probe = ctypes.CDLL(str(so))
    for name in ('e4_probe_prover_ds','e4_probe_verifier_ds'):
        fn = getattr(probe,name)
        fn.argtypes = [ctypes.c_void_p]
        fn.restype = ctypes.c_size_t
    # Import LaZer with its own Python environment and native binary.
    sys.path.insert(0,str(project))
    import baseline_api as b
    if not b.HAS_HOOKS:
        raise RuntimeError('Native counters unavailable: incorrect/old E4 library?')
    libpath = (project/'lazer'/'liblazer.so').resolve()
    mapped = sorted(set(x.rsplit(None, 1)[-1] for x in
                 Path('/proc/self/maps').read_text().splitlines()
                 if '/liblazer.so' in x))
    mapped_resolved = sorted(set(str(Path(x).resolve()) for x in mapped
                              if x.startswith('/')))
    if mapped_resolved != [str(libpath)]:
        raise RuntimeError('Native library mismatch: mapped='+str(mapped_resolved)+
                           '; expected='+str(libpath))

    cfi = b.lz.ffi
    def ds_ptr(obj, prover):
        ptr = int(cfi.cast('unsigned long long',obj.ptr))
        fn = probe.e4_probe_prover_ds if prover else probe.e4_probe_verifier_ds
        ans = int(fn(ctypes.c_void_p(ptr)))
        if not ans: raise RuntimeError('Ds pointer unexpectedly null')
        return ans
    def counters():
        return [int(b.native.baseline_get_counter(i)) for i in range(64)]
    def pubmsg(msg,D):
        return b.ac.zero_out_bytes(msg,[i for i in range(8) if i not in D],8)
    def one_cycle(sk,pk,idx):
        D0 = [0,4,5]
        D1 = [1,3,7]
        m = hashlib.shake_256(b'E4_CACHE_BOUNDARY_MSG'+idx.to_bytes(8,'little')).digest(64)
        # Generate an independently issued credential per lifecycle; no fake RNG.
        u = b.ac.user_t(pk)
        v = b.ac.verifier_t(pk)
        issuer = b.ac.signer_t(pk,sk)
        req = u.maskmsg(m)
        blind = issuer.sign(req,strict=True)
        def show(D):
            proof = u.sign(blind,D)
            v.verify(pubmsg(m,D),D,proof,strict=True)
            return proof
        p0=show(D0)
        addr0=(ds_ptr(u.p2_prover,True),ds_ptr(v.p2_verifier,False))
        b.reset_counts()
        p1=show(D0)
        reuse=counters()
        if reuse[10] < 2:
            raise AssertionError(f'cycle {idx}: same-statement cache hits={reuse[10]} <2')
        b.reset_counts()
        p2=show(D1)
        switch=counters()
        if switch[11] < 2:
            raise AssertionError(f'cycle {idx}: policy switch cache populates={switch[11]} <2')
        addr1=(ds_ptr(u.p2_prover,True),ds_ptr(v.p2_verifier,False))
        if addr1 != addr0:
            raise AssertionError(f'cycle {idx}: unexpected Ds storage address change: {addr0} -> {addr1}')
        b.reset_counts()
        p3=show(D0)
        back=counters()
        if back[11] < 2:
            raise AssertionError(f'cycle {idx}: reverse switch populates={back[11]} <2')
        # Changed disclosed public value must not validate the old proof.
        pub = bytearray(pubmsg(m,D0)); pub[0] ^= 1
        try:
            v.verify(bytes(pub),D0,p3,strict=True)
        except (b.ac.InvalidSignature,b.lz.VerificationError,ValueError):
            rejected=True
        else:
            rejected=False
        if not rejected:
            raise AssertionError(f'cycle {idx}: wrong-public-value proof was accepted')
        hashes=[hashlib.sha256(p).hexdigest() for p in (p0,p1,p2,p3)]
        if len(set(hashes)) != 4:
            raise AssertionError(f'cycle {idx}: duplicate proof hash with fresh randomness')
        # Explicitly clear references to trigger normal owning-object destructor path.
        del p0,p1,p2,p3,u,v,issuer
        return addr0,dict(hits_same=reuse[10],populates_switch=switch[11],
                          populates_restore=back[11],tamper_rejected=rejected)

    (sk,pk,_)=b.ac.falcon_keygen()
    seen_prover={}; seen_verifier={}
    previous_reused=0
    reuse_examples=[]
    minimal={'hits_same':10**9,'populates_switch':10**9,'populates_restore':10**9}
    t0=time.time()
    try:
        for i in range(args.cycles):
            addresses,stats=one_cycle(sk,pk,i)
            for key in minimal:
                minimal[key]=min(minimal[key],stats[key])
            for kind,address,seen in [('prover',addresses[0],seen_prover),
                                      ('verifier',addresses[1],seen_verifier)]:
                if address in seen:
                    previous_reused+=1
                    if len(reuse_examples)<20:
                        reuse_examples.append({'kind':kind,'new_cycle':i,'prior_cycle':seen[address]})
                else:
                    seen[address]=i
            gc.collect()
            if (i+1)%10 == 0:
                print(f'progress {i+1}/{args.cycles}; freed-address reuse observations={previous_reused}',flush=True)
        # An address reused after object destruction was exercised successfully,
        # otherwise lifecycle correctness passed but ABA-address case remains unobserved.
        status=('PASSED_POINTER_REUSE_OBSERVED' if previous_reused else
                'PASSED_NO_POINTER_REUSE_OBSERVED')
        report=dict(status=status,cycles=args.cycles,strict_verifications=4*args.cycles,
                    negative_rejections=args.cycles,
                    freed_address_reuse_observations=previous_reused,
                    distinct_prover_Ds_addresses=len(seen_prover),
                    distinct_verifier_Ds_addresses=len(seen_verifier),
                    reuse_examples=reuse_examples,min_counters=minimal,
                    native_library=str(libpath),elapsed_seconds=round(time.time()-t0,3),
                    test_scope='single-thread native Ds pointer address reuse, cache invalidation, policy switching and strict proof verification',
                    limitations='Finite regression only. Does not test unsanctioned in-place matrix mutation, multithreading or all memory allocators.')
    except BaseException as exc:
        report=dict(status='FAILED',failed_at_cycle=i,error=repr(exc),
                    freed_address_reuse_observations=previous_reused,
                    native_library=str(libpath))
        outfile.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
        print('FAILED:',repr(exc),file=sys.stderr)
        raise
    outfile.parent.mkdir(parents=True,exist_ok=True)
    outfile.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
    print('SAVED:',outfile,flush=True)
