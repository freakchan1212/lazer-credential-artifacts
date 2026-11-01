#!/usr/bin/env python3
"""E4 source generator. Legacy E3 switcher is retained for provenance only."""
import argparse, difflib, hashlib, json, subprocess, sys
from pathlib import Path
import switch_variant as legacy
R=Path(__file__).resolve().parent
VARIANTS={'B1':'B1','V0':'V0','V1':'V1','G3':'V3','C3':'V3','D3':'V4','DC3':'V4'}
GUARD=r'''
/* E4: conservative sign-magnitude int64 preflight, before ANY int_get_i64.
 * The absolute-sum bound covers all dot-product prefixes, beta=-1 and final y.
 * Rejected ranges use the original multi-precision branch; no RNG is consumed.
 */
static int e4_sum_bound_ok (__uint128_t sum, uint64_t max_y)
{ return sum <= (__uint128_t)INT64_MAX &&
         sum + max_y <= (__uint128_t)INT64_MAX; }
int e4_guard_probe (const uint64_t *s, unsigned int n,
                    const uint64_t *y, unsigned int m)
{
  __uint128_t sum=0; uint64_t max_y=0; unsigned int j;
  for (j=0;j<n;j++) { if(s[j]>(uint64_t)INT64_MAX) return 0;
    sum+=s[j]; if(sum>(__uint128_t)INT64_MAX) return 0; }
  for (j=0;j<m;j++) { if(y[j]>(uint64_t)INT64_MAX) return 0;
    if(y[j]>max_y) max_y=y[j]; }
  return e4_sum_bound_ok(sum,max_y);
}
static int e4_arp_range_ok (const intvec_t s, const intvec_t y)
{
  static __thread int force_generic=-1;
  __uint128_t sum=0; uint64_t max_y=0; unsigned int j;
  if(force_generic<0) force_generic=getenv("E4_FORCE_GENERIC")!=NULL;
  if(force_generic) return 0;
  for(j=0;j<s->nelems;j++) {
    int_srcptr a=intvec_get_elem_src(s,j);
    if(a->nlimbs!=1 || a->limbs[0]>(uint64_t)INT64_MAX) return 0;
    sum+=a->limbs[0]; if(sum>(__uint128_t)INT64_MAX) return 0;
  }
  for(j=0;j<y->nelems;j++) {
    int_srcptr a=intvec_get_elem_src(y,j);
    if(a->nlimbs!=1 || a->limbs[0]>(uint64_t)INT64_MAX) return 0;
    if(a->limbs[0]>max_y) max_y=a->limbs[0];
  }
  return e4_sum_bound_ok(sum,max_y);
}
'''

def checked_arp(text):
    anchor='static __thread _lin_ds_cache_entry_t *_lin_ds_cache = NULL;'
    assert text.count(anchor)==1
    text=text.replace(anchor,GUARD+'\n'+anchor)
    for name,idx in [('3',12),('4',14)]:
        marker=f'/* Direction 6 (V2): flat int64_t buffer + branchless AVX2 dot product for z{name} */'
        pos=text.index(marker);start=text.rfind('if (Rq->q->nlimbs == 1)',0,pos)
        text=text[:start]+text[start:].replace('if (Rq->q->nlimbs == 1)',f'if (Rq->q->nlimbs == 1 && e4_arp_range_ok(s{name}coeffs,z{name}coeffs))',1)
        pos=text.index(marker);text=text[:pos]+f'baseline_counts[{idx}]++;\n              '+text[pos:]
        epos=text.index('          else\n            {',pos)
        end=epos+len('          else\n            {')
        text=text[:end]+f'\n              baseline_counts[{idx+1}]++;'+text[end:]
    return text

def shadow_rejection(text):
    # Keep E3 candidate guards and threshold. ALWAYS return original MPFR decision.
    a=text.index('/* Direction 8 (V4): Lazy');b=text.index('static inline double',a)
    text=text[:a]+'/* E4 shadow diagnostics: candidate binary64 is not a certified decision. */\n'+text[b:]
    text='#include <time.h>\n'+text
    start_marker='  /* Direction 8 (V4): IEEE-754 double fast-path filter with explicit domain check & 1e-11 guard band */'
    std=r'''  int e4_candidate=-1, e4_reason=18;
  struct timespec e4_start,e4_end;
  baseline_counts[16]++;
  if (t2->nlimbs<=6 && sigma2dbl->nlimbs<=6 && mu->nlimbs<=6) {
    double nomd=_int_to_double_hi53(t2), dend=_int_to_double_hi53(sigma2dbl);
    e4_reason=20;
    if (nomd>0.0) e4_reason=19;
    else if(dend>0.0 && -nomd<=32.0*dend) {
      double lhs=ldexp(_int_to_double_hi53(mu),-256),rhs=exp(nomd/dend);
      e4_reason=21;
      if(isfinite(lhs)&&isfinite(rhs)) {
        e4_reason=22;
        if(lhs>rhs*(1.0+1e-11)) e4_candidate=1;
        else if(lhs<rhs*(1.0-1e-11)) e4_candidate=0;
      }
    }
  }
  if(e4_candidate<0) {baseline_counts[9]++;baseline_counts[e4_reason]++;}
  else baseline_counts[8]++;
  clock_gettime(CLOCK_MONOTONIC,&e4_start);
'''
    bim=r'''  int e4_candidate=-1, e4_reason=23;
  struct timespec e4_start,e4_end;
  baseline_counts[17]++;
  if(t2->nlimbs<=6 && t1->nlimbs<=6 && _sigma2->nlimbs<=6 && Mu->nlimbs<=6) {
    double t2d=_int_to_double_hi53(t2),t1d=fabs(_int_to_double_hi53(t1));
    double sd=_int_to_double_hi53(_sigma2);e4_reason=24;
    if(sd>0.0 && t2d<=0.0 && -t2d<=64.0*sd && t1d<=32.0*sd) {
      double val=ldexp(_int_to_double_hi53(Mu),-256)*exp(t2d/(2.0*sd))*cosh(t1d/sd);
      e4_reason=25;
      if(isfinite(val)) {e4_reason=26;
        if(val>1.0+1e-11) e4_candidate=1;
        else if(val<1.0-1e-11) e4_candidate=0;
      }
    }
  }
  if(e4_candidate<0) {baseline_counts[9]++;baseline_counts[e4_reason]++;}
  else baseline_counts[8]++;
  clock_gettime(CLOCK_MONOTONIC,&e4_start);
'''
    for body in [std,bim]:
        a=text.index(start_marker);b=text.index('  baseline_counts[9]++;',a)+len('  baseline_counts[9]++;')
        text=text[:a]+body+text[b:]
    # Only these two functions have this exact tail in E3 rejection.c.
    begin=text.index('int\nrej_standard');middle=text.index('int\nrej_bimodal')
    for a,b,idx in [(middle,len(text),29),(begin,middle,28)]:
        part=text[a:b];needle='  return reject;';assert part.count(needle)==1
        tail=f'''  clock_gettime(CLOCK_MONOTONIC,&e4_end);
  baseline_counts[{idx}]+=(uint64_t)((e4_end.tv_sec-e4_start.tv_sec)*1000000000LL+e4_end.tv_nsec-e4_start.tv_nsec);
  if(e4_candidate>=0 && e4_candidate!=reject) baseline_counts[30]++;
  return reject;'''
        text=text[:a]+part.replace(needle,tail)+text[b:]
    return text

def select(vid):
    assert vid in VARIANTS
    legacy.apply_variant(VARIANTS[vid],update_freeze=False)
    touched=set(legacy.TOUCHED_FILES)
    if vid in ['C3','DC3']:
        compact=legacy.build_variant_sources('V5')
        for rel in ['lazer/python/anon_cred/anon_cred.py','lazer/python/anon_cred/anon_cred_params.h']:
            (R/rel).write_text(compact[rel])
        # Remove inherited E3 prose estimates; keep the actual parameter arrays.
        p=R/'lazer/python/anon_cred/anon_cred_params.h';text=p.read_text()
        a=text.index('/* Direction 9 (V5):');b=text.index('*/',a)+2
        text=text[:a]+'''/* E4 compact parameter sets inherited from E3.
 * Application columns: 48-k; internal m1: 50-k; binary polynomials: 16-k.
 * Current declared attack models are computed by security_audit.py;
 * source comments are not whole-protocol numerical security certificates.
 */'''+text[b:];p.write_text(text)
    if vid in ['G3','C3','D3','DC3']:
        p=R/'lazer/src/lin-proofs.c';p.write_text(checked_arp(p.read_text()))
    if vid in ['D3','DC3']:
        p=R/'lazer/src/rejection.c';p.write_text(shadow_rejection(p.read_text()))
    # Extend counters for every E4 build; baseline counter meanings 0..11 preserved.
    p=R/'baseline_hooks.h';s=p.read_text().replace('baseline_counts[12]','baseline_counts[64]').replace('i<12?','i<64?');p.write_text(s)
    (R/'lazer/src/baseline_hooks.h').write_text(s)
    patches=json.loads((R/'PATCHES.json').read_text());diff=[]
    for rel in touched:
        original=legacy._read_upstream(rel);current=(R/rel).read_text()
        if current!=original:
            patches[rel]={'original_sha256':hashlib.sha256(original.encode()).hexdigest(),'patched_sha256':hashlib.sha256(current.encode()).hexdigest(),'variant':vid}
            diff.extend(difflib.unified_diff(original.splitlines(True),current.splitlines(True),fromfile=rel+'.upstream',tofile=rel))
        else:patches.pop(rel,None)
    patches['lazer/src/baseline_hooks.h']={'added_sha256':hashlib.sha256(s.encode()).hexdigest()}
    (R/'PATCHES.json').write_text(json.dumps(patches,indent=2))
    (R/'E4_SOURCE_CHANGES.diff').write_text(''.join(diff))
    state={'active_variant':vid,'parent_e3_variant':VARIANTS[vid],
           'compact':vid in ['C3','DC3'],'arp_preflight':vid in ['G3','C3','D3','DC3'],
           'float_decisions_enabled':False,'float_shadow_diagnostic':vid in ['D3','DC3'],
           'main_variants':['B1','G3','C3'],'schema':'E4-20261018'}
    (R/'ACTIVE_VARIANT.json').write_text(json.dumps(state,indent=2))
    subprocess.run([sys.executable,str(R/'release_freeze.py'),'--create'],cwd=R,check=True,stdout=subprocess.DEVNULL)
    return state

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('variant',choices=VARIANTS);a=p.parse_args()
    print(json.dumps(select(a.variant)))
