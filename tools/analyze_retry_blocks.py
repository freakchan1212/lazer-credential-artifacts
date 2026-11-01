#!/usr/bin/env python3
"""Original strict G3/C3 block associations; no new performance measurements."""
import json,collections,statistics,math,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output.resolve()
if out==ROOT or ROOT in out.parents:raise SystemExit('Choose an output directory outside the frozen package.')
out.mkdir(parents=True,exist_ok=True);mean=statistics.mean
plan=json.loads((ROOT/'data/plan.json').read_text());by=collections.defaultdict(list)
for j in plan:
 if j['task']!='main' or j['verification_mode']!='strict' or j['variant'] not in ['G3','C3']:continue
 for line in (ROOT/'data/raw'/(j['id']+'.jsonl')).read_text().splitlines():
  r=json.loads(line)
  if not r['warmup']:by[j['lifecycle'],j['round'],j['block'],j['variant']].append(r)
summary={}
for life in ['steady','fresh']:
 rows=[]
 for rnd in [1,2,3]:
  for block in range(1,11):
   base=by[life,rnd,block,'G3'];target=by[life,rnd,block,'C3'];assert len(base)==len(target)==20
   def delta(k):return mean(r[k] for r in target)-mean(r[k] for r in base)
   rows.append(dict(round=rnd,block=block,dK=delta('K'),dprove=delta('prove_ms'),dshow=delta('show_ms')))
 x=[r['dK'] for r in rows];y=[r['dprove'] for r in rows]
 corr=sum((i-mean(x))*(j-mean(y)) for i,j in zip(x,y))/math.sqrt(sum((i-mean(x))**2 for i in x)*sum((j-mean(y))**2 for j in y))
 saved=json.loads((ROOT/'data/independent_checks'/('retry_'+life+'_blocks.json')).read_text())
 assert all(abs(r[k]-s[k])<1e-8 for r,s in zip(rows,saved) for k in ['dK','dprove','dshow'])
 bad=[r for r in rows if r['dshow']>=0]
 summary[life]=dict(blocks=len(rows),not_improved=len(bad),not_improved_with_higher_K=sum(r['dK']>0 for r in bad),K_prove_correlation=corr)
 (out/('retry_'+life+'_blocks.json')).write_text(json.dumps(rows,ensure_ascii=False,indent=2))
(out/'retry_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));print(json.dumps(summary,indent=2))
