"""Measurement adapter: original upstream classes, checks, parameters and FS."""
import ctypes,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
DEMO=Path(os.environ.get('BASELINE_DEMO_ROOT',ROOT/'lazer/python/anon_cred')).resolve()
os.chdir(DEMO);sys.path[:0]=[str(DEMO),str(DEMO.parent)]
import anon_cred as ac
import lazer as lz
native=ctypes.CDLL(str(DEMO.parent.parent/'liblazer.so'))
HAS_HOOKS=hasattr(native,'baseline_get_counter')
if HAS_HOOKS:
 native.baseline_get_counter.argtypes=[ctypes.c_uint];native.baseline_get_counter.restype=ctypes.c_uint64
 native.baseline_reset_counters.restype=None
COUNTERS=['range_attempts','range_reject_z3','range_reject_z4','quadratic_attempts','quadratic_reject_z1','quadratic_reject_z2','quadratic_reject_norm','falcon_preimage_attempts']
PUBLIC=[0,4,5];HIDDEN=[1,2,3,6,7]
def reset_counts():
 if HAS_HOOKS:native.baseline_reset_counters()
def counts():return {n:int(native.baseline_get_counter(i)) for i,n in enumerate(COUNTERS)} if HAS_HOOKS else {}
def fastpath_counts():
 if not HAS_HOOKS:return {'rej_fastpath_decisions':0,'rej_mpfr_fallbacks':0,'ds_cache_hits':0,'ds_cache_populates':0}
 return {
  'rej_fastpath_decisions':int(native.baseline_get_counter(8)),
  'rej_mpfr_fallbacks':int(native.baseline_get_counter(9)),
  'ds_cache_hits':int(native.baseline_get_counter(10)),
  'ds_cache_populates':int(native.baseline_get_counter(11)),
 }
def pkbytes(pk):return bytes(lz.ffi.buffer(pk.ptr,897))
def skbytes(sk):return bytes(lz.ffi.buffer(sk.ptr,1281))
def public_message(msg):return ac.zero_out_bytes(msg,HIDDEN,8)
def show(user,blind,pk,profile='raw',ctx=None):
 if profile!='raw':raise ValueError('Original baseline supports raw only')
 return user.sign(blind,PUBLIC)
def verify(verifier,pub,pk,profile,presentation,expected_ctx=None,seen=None):
 if profile!='raw':raise ValueError('Original baseline supports raw only')
 return verifier.verify(pub,PUBLIC,presentation)
def issue(pk,sk,msg=None):
 import secrets
 msg=msg or secrets.token_bytes(64)
 user=ac.user_t(pk);issuer=ac.signer_t(pk,sk);verifier=ac.verifier_t(pk)
 req=user.maskmsg(msg);blind=issuer.sign(req)
 return user,issuer,verifier,msg,req,blind
