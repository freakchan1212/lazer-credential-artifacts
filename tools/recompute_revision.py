import csv,json,hashlib,collections,statistics,random,math
from pathlib import Path
import argparse
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description='Independently recompute full revision batch, including verification intervals.')
p.add_argument('--output',type=Path,required=True);args=p.parse_args()
b=ROOT/'history/revision_data/full';out=args.output.resolve()
if out==ROOT or ROOT in out.parents:raise SystemExit('Choose an output directory outside the frozen package.')
out.mkdir(parents=True,exist_ok=True)
config=json.loads((b/'config.json').read_text());data=[]
for j in config['plan']:
 for s in (b/'raw'/(j['id']+'.jsonl')).read_text().splitlines():
  r=json.loads(s)
  if not r['warmup']:data.append(r)
mean=statistics.mean
def quantile(a,p):return sorted(a)[math.ceil(p*len(a))-1]
g=collections.defaultdict(list)
for r in data:g[r['compiler'],r['variant'],r['lifecycle']].append(r)
summ=[]
for (c,v,l),rs in sorted(g.items()):
 t=dict(compiler=c,variant=v,lifecycle=l,n=len(rs))
 for field in ['prove_ms','verify_ms','show_ms','proof_bytes','K']:t[field+'_mean']=mean(r[field] for r in rs)
 t.update(show_ms_median=statistics.median(r['show_ms'] for r in rs),show_ms_p95=quantile([r['show_ms'] for r in rs],.95),process_peak_rss_MiB=max(r['rss_kib'] for r in rs)/1024)
 if v!='PQZK_BLNS':
  xs=[r['K'] for r in rs];ys=[r['prove_ms'] for r in rs]
  slope=sum((x-mean(xs))*(y-mean(ys)) for x,y in zip(xs,ys))/sum((x-mean(xs))**2 for x in xs)
  intercept=mean(ys)-slope*mean(xs)
  t.update(ols_a=intercept,ols_b=slope,ols_R2=1-sum((y-intercept-slope*x)**2 for x,y in zip(xs,ys))/sum((y-mean(ys))**2 for y in ys),predicted_prove_K55=intercept+slope*5.5)
 summ.append(t)
saved=list(csv.DictReader((b/'derived/summary.csv').open()))
errors=[]
for r in summ:
 old=next(x for x in saved if all(x[k]==r[k] for k in ['compiler','variant','lifecycle']))
 for k,val in r.items():
  if k in old and k not in ['compiler','variant','lifecycle'] and abs(float(old[k])-val)>1e-8:errors.append((r['compiler'],r['variant'],r['lifecycle'],k))
effects=[]
for c in ['gcc','clang']:
 for life in ['steady','fresh']:
  for base,target in [('B1','G3'),('B1','C3'),('G3','C3')]:
   for metric in ['show_ms','verify_ms']:
    by=collections.defaultdict(list)
    for r in data:
     if r['compiler']==c and r['lifecycle']==life and r['variant'] in [base,target]:by[r['round'],r['block'],r['variant']].append(r)
    pairs=[]
    for rnd in [1,2,3]:
     for block in range(1,6):
      a=by[rnd,block,base];d=by[rnd,block,target]
      pairs.append(dict(round=rnd,a=mean(r[metric] for r in a),b=mean(r[metric] for r in d),dk=mean(r['K'] for r in d)-mean(r['K'] for r in a),dp=mean(r['prove_ms'] for r in d)-mean(r['prove_ms'] for r in a)))
    rng=random.Random(20261030);boots=[]
    for _ in range(25000):
     draw=[rng.choice(pairs[k:k+5]) for k in [0,5,10] for _ in range(5)]
     boots.append(100*(1-sum(r['b'] for r in draw)/sum(r['a'] for r in draw)))
    dk=[r['dk'] for r in pairs];dp=[r['dp'] for r in pairs]
    corr=sum((x-mean(dk))*(y-mean(dp)) for x,y in zip(dk,dp))/math.sqrt(sum((x-mean(dk))**2 for x in dk)*sum((y-mean(dp))**2 for y in dp))
    e=dict(compiler=c,lifecycle=life,base=base,target=target,metric=metric,reduction_pct=100*(1-sum(r['b'] for r in pairs)/sum(r['a'] for r in pairs)),bootstrap_low_pct=quantile(boots,.025),bootstrap_high_pct=quantile(boots,.975),improved_blocks=sum(r['b']<r['a'] for r in pairs),K_prove_block_correlation=corr)
    effects.append(e)
old_effects=list(csv.DictReader((b/'derived/effects.csv').open()))
for e in effects:
 if e['metric']!='show_ms':continue
 old=next(x for x in old_effects if all(x[k]==e[k] for k in ['compiler','lifecycle','base','target']))
 for k in ['reduction_pct','bootstrap_low_pct','bootstrap_high_pct','improved_blocks']:
  if abs(float(old[k])-e[k])>1e-8:errors.append(('effect',e['compiler'],e['lifecycle'],e['base'],e['target'],k))
result=dict(independent_recompute_errors=errors,sessions=len(data),summary=summ,effects=effects)
(out/'independent_results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print('Recompute errors:',errors)
for e in effects:
 if e['base']=='G3':print(e)
for s in summ:
 if s['variant'] in ['G3','C3']:print('OLS',s['compiler'],s['variant'],s['lifecycle'],s['ols_a'],s['ols_b'],s['ols_R2'],s['predicted_prove_K55'])
