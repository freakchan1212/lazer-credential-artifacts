#!/usr/bin/env python3
"""Derive tables only from recorded E4 rows; never fill missing measurements."""
import argparse, csv, hashlib, json, math, statistics as st
from collections import defaultdict
from pathlib import Path
def dumpcsv(p,rows):
 if not rows:return
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--batch',required=True,type=Path);ap.add_argument('--output',type=Path);a=ap.parse_args();B=a.batch.resolve();D=a.output.resolve() if a.output else B/'derived';D.mkdir(parents=True,exist_ok=True)
 plan=json.loads((B/'plan.json').read_text());rows=[];allrows=[]
 for job in plan:
  p=B/'raw'/(job['id']+'.jsonl');receipt=p.with_suffix('.receipt.json')
  if not p.exists() or not receipt.exists():raise RuntimeError(f'Missing completed job: {job["id"]}')
  r=json.loads(receipt.read_text())
  if hashlib.sha256(p.read_bytes()).hexdigest()!=r['sha256']:raise RuntimeError(f'Changed data: {p}')
  rr=[json.loads(s) for s in p.read_text().splitlines()]
  if not rr:raise RuntimeError('Empty job')
  if r['rows']!=len(rr):raise RuntimeError('Receipt row count mismatch: '+job['id'])
  for x in rr:
   for key in ['variant','task','round','block','lifecycle','verification_mode','formal','repeat','pattern']:
    if key in job and x.get(key)!=job[key]:raise RuntimeError(f'Job metadata mismatch: {job["id"]} / {key}')
   for key in ['prove_ms','verify_ms','show_ms','K','proof_bytes']:
    if key in x and (not math.isfinite(x[key]) or x[key]<0):raise RuntimeError('Nonfinite/negative measurement')
   if 'show_ms' in x and not math.isclose(x['show_ms'],x['prove_ms']+x['verify_ms'],rel_tol=1e-12,abs_tol=1e-8):raise RuntimeError('Timing stage sum mismatch')
  expected=job.get('sessions',len(rr))
  formal=[x for x in rr if not x.get('warmup')]
  if job['task']!='subsets' and len(formal)!=expected:raise RuntimeError(f'Count mismatch {job["id"]}')
  if any(x.get('status') not in ['ACCEPTED','PASSED'] for x in rr):raise RuntimeError(f'Failure in {p}')
  allrows+=rr;rows+=formal
 groups=defaultdict(list)
 for x in rows:
  if x['task']=='main':groups[(x['variant'],x['lifecycle'],x['verification_mode'])].append(x)
 summary=[];rounds=[]
 def stats(key,rr):
  v,life,mode=key;n=len(rr);z=[r['show_ms'] for r in rr];k=[r['K'] for r in rr];t=[r['prove_ms'] for r in rr]
  km=st.mean(k);tm=st.mean(t);den=sum((x-km)**2 for x in k)
  slope=sum((x-km)*(y-tm) for x,y in zip(k,t))/den if den else None
  intercept=tm-slope*km if slope is not None else None
  sst=sum((x-tm)**2 for x in t);sse=sum((y-intercept-slope*x)**2 for x,y in zip(k,t)) if slope is not None else None
  return dict(variant=v,lifecycle=life,verification_mode=mode,n=n,prove_mean_ms=tm,verify_mean_ms=st.mean(r['verify_ms'] for r in rr),
   show_mean_ms=st.mean(z),show_median_ms=st.median(z),show_p95_ms=sorted(z)[math.ceil(.95*n)-1],show_max_ms=max(z),
   proof_mean_bytes=st.mean(r['proof_bytes'] for r in rr),K_mean=km,ols_a=intercept,ols_b=slope,
   ols_at_5_5=intercept+slope*5.5 if slope is not None else None,ols_r2=1-sse/sst if sse is not None and sst else None,
   above100=sum(t>100 for t in z),prove_cpu_mean_ms=st.mean(r['prove_cpu_ms'] for r in rr),verify_cpu_mean_ms=st.mean(r['verify_cpu_ms'] for r in rr),rss_max_MiB=max(r['rss_kib'] for r in rr)/1024,int_fast_z3=sum(r['prove_counters'][12] for r in rr),int_fallback_z3=sum(r['prove_counters'][13] for r in rr),
   int_fast_z4=sum(r['prove_counters'][14] for r in rr),int_fallback_z4=sum(r['prove_counters'][15] for r in rr))
 for key,rr in sorted(groups.items()):
  summary.append(stats(key,rr))
  for rnd in sorted(set(x['round'] for x in rr)):rounds.append(dict(round=rnd,**stats(key,[x for x in rr if x['round']==rnd])))
 dumpcsv(D/'main_summary.csv',summary);dumpcsv(D/'main_by_round.csv',rounds)
 # Block-level paired differences preserve experimental time structure; these are not iid CIs.
 byblock=defaultdict(dict)
 for x in rows:
  if x['task']=='main':byblock[(x['round'],x['block'],x['lifecycle'],x['verification_mode'])].setdefault(x['variant'],[]).append(x['show_ms'])
 pairs=[]
 for (rnd,blk,life,mode),vals in sorted(byblock.items()):
  for left,right in [('B1','G3'),('G3','C3'),('B1','C3')]:
   l=st.mean(vals[left]);r=st.mean(vals[right]);pairs.append(dict(round=rnd,block=blk,lifecycle=life,verification_mode=mode,base=left,target=right,base_mean_ms=l,target_mean_ms=r,reduction_percent=100*(1-r/l)))
 dumpcsv(D/'block_effects.csv',pairs)
 reuse=[]
 for job in plan:
  if job['task']!='reuse':continue
  rr=[x for x in rows if x['task']=='reuse' and x['variant']==job['variant'] and x.get('repeat')==job['repeat']]
  for n in [1,2,4,8,16,32,64,128,256]:
   if n>len(rr):continue
   r=rr[:n];setup=r[0]['user_init_ms']+r[0]['verifier_init_ms'];total=setup+sum(x['show_ms'] for x in r)
   reuse.append(dict(variant=job['variant'],repeat=job['repeat'],N=n,user_verifier_init_ms=setup,total_local_service_ms=total,amortized_local_service_ms=total/n,
     prove_verify_ms=sum(x['show_ms'] for x in r),cache_hits=sum(x['prove_counters'][10]+x['verify_counters'][10] for x in r),cache_populates=sum(x['prove_counters'][11]+x['verify_counters'][11] for x in r)))
 dumpcsv(D/'reuse.csv',reuse)
 policy=[];kg=defaultdict(list)
 for x in rows:
  if x['task']=='policy':kg[(x['variant'],x['pattern'])].append(x)
 for (v,p),rr in sorted(kg.items()):policy.append(dict(variant=v,pattern=p,n=len(rr),K_mean=st.mean(x['K'] for x in rr),show_mean_ms=st.mean(x['show_ms'] for x in rr),cache_hits=sum(x['prove_counters'][10]+x['verify_counters'][10] for x in rr),cache_populates=sum(x['prove_counters'][11]+x['verify_counters'][11] for x in rr)))
 dumpcsv(D/'policy.csv',policy)
 ks=[];kg=defaultdict(list)
 for x in rows:
  if x['task']=='k_sweep':kg[(x['variant'],x['k'])].append(x)
 for (v,k),rr in sorted(kg.items()):ks.append(dict(variant=v,k=k,n=len(rr),proof_mean_bytes=st.mean(x['proof_bytes'] for x in rr),proof_min_bytes=min(x['proof_bytes'] for x in rr),proof_max_bytes=max(x['proof_bytes'] for x in rr),show_mean_ms=st.mean(x['show_ms'] for x in rr)))
 dumpcsv(D/'k_sweep.csv',ks)
 labels={18:'std_limb',19:'std_positive_exponent',20:'std_other_domain',21:'std_nonfinite',22:'std_guard_band',23:'bim_limb',24:'bim_domain',25:'bim_nonfinite',26:'bim_guard_band'}
 dr=[]
 for v in ['D3','DC3']:
  rr=[r for r in rows if r['task']=='diagnostic' and r['variant']==v];counts=[sum(r['prove_counters'][i] for r in rr) for i in range(64)]
  dr.append(dict(variant=v,n=len(rr),standard_calls=counts[16],bimodal_calls=counts[17],candidate_fast=counts[8],candidate_fallback=counts[9],
    **{name:counts[i] for i,name in labels.items()},standard_reference_mpfr_ns=counts[28],bimodal_reference_mpfr_ns=counts[29],candidate_reference_disagreements=counts[30],
    meaning='shadow timing includes MPFR setup/conversion/compare/clear; extra clock calls; not pure exp/cosh microbenchmark'))
 dumpcsv(D/'float_shadow.csv',dr)
 subsets=[dict(variant=x['variant'],mask=x.get('mask'),k=x['k'],checks=len(x.get('checks',{})),passed=all(x.get('checks',{}).values()),lifecycle_recreated=bool(x.get('lifecycle_recreated'))) for x in rows if x['task']=='subsets']
 dumpcsv(D/'subsets.csv',subsets)
 flat=[{k:x.get(k) for k in ['task','variant','round','block','verification_mode','lifecycle','formal','index','k','prove_ms','verify_ms','show_ms','proof_bytes','K','arp_attempts','proof_sha','rss_kib']} for x in rows if 'show_ms' in x]
 dumpcsv(D/'samples.csv',flat)
 meta=dict(status='COMPLETE',formal_main_samples=sum(len(v) for v in groups.values()),all_nonwarmup_rows=len(rows),all_rows=len(allrows),main_groups=len(summary),
   diagnostic_disagreements=sum(x['candidate_reference_disagreements'] for x in dr),numeric_protocol_security_certified=False)
 (D/'summary.json').write_text(json.dumps(dict(meta=meta,main=summary,float_shadow=dr),indent=2))
 text=['# E4 实验结果回填依据','','模式：'+json.loads((B/'config.json').read_text())['mode']+'。smoke/pilot 不作为最终 full 结论。',
  '', '|版本|负载|验证模式|n|生成 ms|验证 ms|本地合计 ms|中位/P95 ms|证明均值 B|','|---|---|---|---:|---:|---:|---:|---:|---:|']
 for x in summary:text.append(f"|{x['variant']}|{x['lifecycle']}|{x['verification_mode']}|{x['n']}|{x['prove_mean_ms']:.2f}|{x['verify_mean_ms']:.2f}|{x['show_mean_ms']:.2f}|{x['show_median_ms']:.2f}/{x['show_p95_ms']:.2f}|{x['proof_mean_bytes']:.2f}|")
 text+=['','图表见 figures。主结论优先用strict组；raw用于与E3默认验证口径对照。',
  'reuse包含用户/验证者对象初始化与前N次出示，不含发行者初始化、签发、网络或导入；首次H2在第一次出示内。',
  '分块相对变化为描述性结果，不是独立同分布置信区间；k_sweep同k比较，跨k改变披露任务。',
  'float_shadow的输出始终由原MPFR路径决定；候选匹配只说明测试过的比较，不构成数值全范围证明。',
  '安全模型文件见security；未执行完整Sage估计器，不认证整协议128位安全。']
 (D/'PAPER_INSERT_ZH.md').write_text('\n'.join(text)+'\n')
 print(json.dumps(meta))
if __name__=='__main__':main()
