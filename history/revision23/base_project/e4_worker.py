#!/usr/bin/env python3
"""One fresh process per block. Formal timings never use deterministic RNG."""
import argparse, ctypes, hashlib, itertools, json, os, random, resource, sys, time
from pathlib import Path
R=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--spec',required=True);p.add_argument('--out',required=True)
a=p.parse_args();spec=json.loads(Path(a.spec).read_text());out=Path(a.out).resolve()
if spec.get('formal') and (os.environ.get('FAKE_RNG_SEED') or os.environ.get('LD_PRELOAD') or os.environ.get('E4_FORCE_GENERIC')):
    raise RuntimeError('Formal benchmark must not use fake RNG or forced paths')
import baseline_api as b
b.native.baseline_get_counter.argtypes=[ctypes.c_uint]
b.native.baseline_get_counter.restype=ctypes.c_uint64
if spec['task']=='fixed':
    # Python 3.12 may bypass libc getrandom. Fix Python coins explicitly as well
    # as the LD_PRELOAD native RNG. This is NEVER active for formal benchmarks.
    import secrets
    test_seed=int(os.environ['FAKE_RNG_SEED']);coin_index=0
    def test_coins(n=32):
        global coin_index
        coin_index+=1
        return hashlib.shake_256(b'E4_FIXED_COINS_ONLY'+test_seed.to_bytes(8,'little')+coin_index.to_bytes(8,'little')).digest(n)
    secrets.token_bytes=test_coins
    original_prove=b.lz.lin_prover_state_t.prove
    def test_prove(self,coins=None):return original_prove(self,test_coins(32) if coins is None else coins)
    b.lz.lin_prover_state_t.prove=test_prove

def counters():return [int(b.native.baseline_get_counter(i)) for i in range(64)]
def timed(fn):
    b.reset_counts();t=time.perf_counter_ns();c=time.process_time_ns();value=fn()
    return value,(time.perf_counter_ns()-t)/1e6,(time.process_time_ns()-c)/1e6,counters()
def reject(fn):
    try:fn()
    except (b.ac.InvalidSignature,b.ac.InvalidMaskedMsg,b.lz.VerificationError,ValueError,IndexError):return True
    return False
def pubmsg(msg,D):return b.ac.zero_out_bytes(msg,[i for i in range(8) if i not in D],8)
def sha(x):return hashlib.sha256(x).hexdigest()
def write(x):
    x.update(variant=spec['variant'],task=spec['task'],round=spec.get('round',0),block=spec.get('block',0),formal=bool(spec.get('formal')),verification_mode=spec.get('verification_mode','strict'))
    f.write(json.dumps(x,sort_keys=True)+'\n');f.flush()
def prepare(pk,sk,strict,msg=None):
    u,ui,_,_=timed(lambda:b.ac.user_t(pk));v,vi,_,_=timed(lambda:b.ac.verifier_t(pk));iss,ii,_,_=timed(lambda:b.ac.signer_t(pk,sk))
    msg=msg if msg is not None else os.urandom(64)
    req,p1,_,_=timed(lambda:u.maskmsg(msg));blind,issue,_,_=timed(lambda:iss.sign(req,strict=strict))
    return (u,v,msg,blind),dict(user_init_ms=ui,verifier_init_ms=vi,issuer_init_ms=ii,p1_prove_ms=p1,p1_verify_issue_ms=issue,request_bytes=len(req),blind_bytes=len(blind),request_sha=sha(req),blind_sha=sha(blind))
def show(state,D,strict):
    u,v,msg,blind=state
    proof,prove,pcpu,cp=timed(lambda:u.sign(blind,D));pub=pubmsg(msg,D)
    _,verify,vcpu,cv=timed(lambda:v.verify(pub,D,proof,strict=strict))
    return proof,dict(prove_ms=prove,verify_ms=verify,show_ms=prove+verify,prove_cpu_ms=pcpu,verify_cpu_ms=vcpu,
      proof_bytes=len(proof),minimal_payload_bytes=len(proof)+8*len(D),K=cp[3],arp_attempts=cp[0],
      prove_counters=cp,verify_counters=cv,proof_sha=sha(proof),D=D,k=len(D),status='ACCEPTED',rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)

out.parent.mkdir(parents=True,exist_ok=True)
with out.open('w') as f:
  kind=spec['task'];strict=spec.get('verification_mode','strict')=='strict'
  if kind=='guard':
    fun=b.native.e4_guard_probe;fun.argtypes=[ctypes.POINTER(ctypes.c_uint64),ctypes.c_uint,ctypes.POINTER(ctypes.c_uint64),ctypes.c_uint];fun.restype=ctypes.c_int
    M=2**63-1;rng=random.Random(70418);cases=[([],[]),([M],[0]),([M],[1]),([2**63],[0]),([2**64-1],[0]),([M-1,1],[0]),([M-1,1],[1]),([1],[M]),([0],[M])]
    for _ in range(1000):cases.append(([rng.randrange(2**64) for _ in range(rng.randrange(0,12))],[rng.randrange(2**64) for _ in range(rng.randrange(0,5))]))
    for s,y in cases:
      expected=int(all(v<=M for v in s+y) and sum(s)+max(y,default=0)<=M)
      actual=fun((ctypes.c_uint64*len(s))(*s),len(s),(ctypes.c_uint64*len(y))(*y),len(y))
      if actual!=expected:raise AssertionError((s,y,expected,actual))
    write(dict(status='PASSED',cases=len(cases),scope='native magnitude preflight against Python integer oracle'))
  elif kind=='cross':
    records=json.loads(Path(spec['inputs']).read_text());_,pk,_=b.ac.falcon_keygen();n=0
    for rec in records:
      key=bytes.fromhex(rec['pk_hex']);b.lz.ffi.memmove(pk.ptr,key,len(key));v=b.ac.verifier_t(pk)
      proof=bytes.fromhex(rec['proof_hex']);pub=bytes.fromhex(rec['pub_hex']);D=rec['D']
      v.verify(pub,D,proof,strict=True)
      assert reject(lambda:v.verify(pub,D,proof+b'x',strict=True))
      n+=1
    write(dict(status='PASSED',proofs_verified=n))
  else:
    (sk,pk,_),kg,_,_=timed(b.ac.falcon_keygen)
    if kind=='fixed':
      msg=bytes((i*13+7)%256 for i in range(64));state,setup=prepare(pk,sk,True,msg);proof,row=show(state,[0,4,5],True)
      row.update(setup);row.update(pk_hex=b.pkbytes(pk).hex(),pub_hex=pubmsg(msg,[0,4,5]).hex(),proof_hex=proof.hex(),pk_sha=sha(b.pkbytes(pk)))
      write(row)
    elif kind=='subsets':
      rng=random.Random(spec.get('seed',1));msg=bytes(rng.randrange(256) for _ in range(64));state,setup=prepare(pk,sk,True,msg)
      masks=list(range(256)) if spec['all_subsets'] else [0,1,3,7,15,31,63,127,255]
      for mask in masks:
        D=[i for i in range(8) if mask>>i&1];proof,row=show(state,D,True);v=state[1];pub=pubmsg(msg,D)
        bad=bytearray(proof);bad[len(bad)//2]^=1
        checks={'trailing':reject(lambda:v.verify(pub,D,proof+b'x',strict=True)),
          'bitflip':reject(lambda:v.verify(pub,D,bytes(bad),strict=True)),
          'duplicate_indices':reject(lambda:v.verify(pub,D+[D[0] if D else 0, D[0] if D else 0],proof,strict=True)),
          'invalid_index':reject(lambda:v.verify(pub,[8],proof,strict=True))}
        hidden=[i for i in range(8) if i not in D]
        if hidden:
          injected=bytearray(pub);injected[8*hidden[0]]=1
          checks['hidden_injection']=reject(lambda:v.verify(bytes(injected),D,proof,strict=True))
        if D:
          changed=bytearray(pub);changed[8*D[0]]^=1
          checks['changed_disclosed_value']=reject(lambda:v.verify(bytes(changed),D,proof,strict=True))
        # Reordered legal indices are an equivalent disclosure set; exercise setter invalidation.
        rev=list(reversed(D));p2=state[0].sign(state[3],rev);v.verify(pub,rev,p2,strict=True)
        checks['reordered_honest']=True
        if not all(checks.values()):raise AssertionError((mask,checks))
        row.update(mask=mask,checks=checks,message_sha=sha(msg));write(row)
      # Explicit clear/recreate through owning Python lifecycle, rather than arbitrary pointer mutation.
      del state
      import gc;gc.collect()
      state,_=prepare(pk,sk,True,msg);_,row=show(state,[0,4,5],True);row['lifecycle_recreated']=True;write(row)
    elif kind in ['main','reuse','policy','k_sweep','diagnostic']:
      D=[0,4,5];life=spec.get('lifecycle','steady');state=None;seen=set()
      if life=='steady':state,setup=prepare(pk,sk,strict)
      warmup=spec.get('warmup',2);count=spec['sessions'];rng=random.Random(spec.get('seed',1))
      for i in range(-warmup,count):
        if life=='fresh':state,setup=prepare(pk,sk,strict)
        if kind=='policy':
          pattern=spec['pattern']
          if pattern=='alternating':D=([0,4,5] if i%2==0 else [1,3,7])
          elif pattern=='random':D=sorted(rng.sample(range(8),3))
        elif kind=='k_sweep':D=list(range(spec['k']))
        proof,row=show(state,D,strict)
        if row['proof_sha'] in seen:raise AssertionError('Duplicate proof hash within block')
        seen.add(row['proof_sha']);row.update(index=i,warmup=i<0,lifecycle=life,keygen_ms=kg)
        if i==0 or life=='fresh':row.update(setup)
        if kind=='policy':row['pattern']=spec['pattern']
        if kind=='reuse':row['repeat']=spec.get('repeat',0)
        if kind=='diagnostic':
          cp=row['prove_counters']
          assert cp[8]+cp[9]==cp[16]+cp[17]
          assert sum(cp[18:27])==cp[9]
          # A disagreement is evidence about the candidate; reference MPFR still decides.
        write(row)
    else:raise ValueError(kind)
