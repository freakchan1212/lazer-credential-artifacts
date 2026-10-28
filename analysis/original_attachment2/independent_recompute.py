from pathlib import Path
import json,hashlib,collections,statistics,math,csv
import numpy as np
R=Path(__file__).resolve().parent.parent;B=R/'data';O=B/'independent_checks';O.mkdir(exist_ok=True);allrows=[];jobs=json.loads((B/'plan.json').read_text());out=[];metrics=[]
for j in jobs:
 p=B/'raw'/(j['id']+'.jsonl');rs=[json.loads(s) for s in p.read_text().splitlines()];rc=json.loads(p.with_suffix('.receipt.json').read_text());assert hashlib.sha256(p.read_bytes()).hexdigest()==rc['sha256'];assert len(rs)==rc['rows'];allrows+=rs
rows=[r for r in allrows if not r.get('warmup')];main=[r for r in rows if r['task']=='main'];counts=collections.Counter((r['task'],bool(r.get('formal'))) for r in rows)
for life in ['steady','fresh']:
 for mode in ['strict','raw']:
  for v in ['B1','G3','C3']:
   a=[r for r in main if (r['lifecycle'],r['verification_mode'],r['variant'])==(life,mode,v)];assert len(a)==600
   k=np.array([x['K'] for x in a]);pr=np.array([x['prove_ms'] for x in a]);ve=np.array([x['verify_ms'] for x in a]);sh=pr+ve;sl,inter=np.polyfit(k,pr,1)
   out.append(dict(lifecycle=life,mode=mode,variant=v,n=len(a),prove_mean=float(pr.mean()),verify_mean=float(ve.mean()),show_mean=float(sh.mean()),median=float(np.median(sh)),p95=float(sorted(sh)[math.ceil(.95*len(sh))-1]),maximum=float(sh.max()),K=float(k.mean()),ols_a=float(inter),ols_b=float(sl),ols_at_5_5=float(inter+sl*5.5),proof_mean=statistics.mean(x['proof_bytes'] for x in a),above100=int((sh>100).sum())))
 a=[x for x in main if x['lifecycle']==life and x['verification_mode']=='strict'];blocks=[]
 for rnd in range(1,4):
  for bl in range(1,11):
   b={v:statistics.mean(x['show_ms'] for x in a if x['round']==rnd and x['block']==bl and x['variant']==v) for v in ['B1','G3','C3']};blocks.append(dict(lifecycle=life,round=rnd,block=bl,**b))
 rng=np.random.default_rng(20261020);base=np.array([b['G3'] for b in blocks]).reshape(3,10);comp=np.array([b['C3'] for b in blocks]).reshape(3,10)
 ix=rng.integers(0,10,size=(25000,3,10));av=np.take_along_axis(np.broadcast_to(base,(25000,3,10)),ix,axis=2).mean((1,2));bv=np.take_along_axis(np.broadcast_to(comp,(25000,3,10)),ix,axis=2).mean((1,2));boot=100*(1-bv/av)
 metrics.append(dict(lifecycle=life,mean_reduction_percent=float(100*(1-comp.mean()/base.mean())),absolute_ms=float((base-comp).mean()),improved_blocks=int((base>comp).sum()),ci_low=float(np.quantile(boot,.025)),ci_high=float(np.quantile(boot,.975)),algorithm='numpy.default_rng; one independent generator reset per lifecycle; stratified pairs; 25000 draws'))
 with (O/f'independent_paired_blocks_{life}.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=list(blocks[0]));w.writeheader();w.writerows(blocks)
with (O/'independent_main.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
proofs=[r['proof_sha'] for r in rows if r.get('formal')];assert len(proofs)==12480
report=dict(total_jobs=len(jobs),all_rows=len(allrows),nonwarmup_rows=len(rows),formal_timing_rows=len(proofs),formal_main_rows=len(main),unique_formal_proofs=len(set(proofs)),counts=[dict(task=k[0],formal=k[1],n=v) for k,v in counts.items()],bootstrap=metrics,failed_statuses=[r for r in rows if r.get('status') not in ['ACCEPTED','PASSED']])
(O/'independent_summary.json').write_text(json.dumps(report,indent=2,ensure_ascii=False));print(json.dumps(report,indent=2,ensure_ascii=False))
