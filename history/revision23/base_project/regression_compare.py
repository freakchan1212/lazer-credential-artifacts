#!/usr/bin/env python3
"""Compare old/new summary.json and samples.csv (including retry-normalized fixed + per-attempt slope)."""
import argparse,csv,json,statistics
from pathlib import Path
R=Path(__file__).resolve().parent
p=argparse.ArgumentParser()
p.add_argument('--before',type=Path)
p.add_argument('--after',type=Path)
p.add_argument('--output',type=Path,default=R/'results/blns23_regression.csv')
a=p.parse_args()
latest=R/'results/LATEST_METRICS.txt'
if a.after is None and latest.exists():
 after_dir=Path(latest.read_text().strip())
 if not after_dir.is_absolute():after_dir=R/after_dir
 a.after=after_dir/'summary.json'
if a.before is None:
 ref=R/'reference_user/i5_13400F_pilot_20261015_summary.json'
 if ref.exists():
  a.before=ref
 else:
  candidates=sorted([
   x for x in (R/'results').glob('metrics_*/summary.json')
   if a.after is None or x.resolve()!=a.after.resolve()
  ])
  if candidates:
   a.before=candidates[0]
  else:
   print('BEFORE_NOT_SUPPLIED: run --before /path/original/summary.json --after /path/patched/summary.json');raise SystemExit(0)
if not a.after or not a.after.exists():raise SystemExit('After summary unavailable')

def fit_samples(summary_path):
 samples_path=summary_path.parent/'samples.csv'
 if not samples_path.exists() and summary_path.name.endswith('_summary.json'):
  alt=summary_path.with_name(summary_path.name.replace('_summary.json','_samples.csv'))
  if alt.exists():samples_path=alt
 if not samples_path.exists():return {}
 rows=list(csv.DictReader(samples_path.open()))
 out={}
 for grp in ['raw_steady','raw_fresh']:
  g_rows=[r for r in rows if f"{r['profile']}_{r['lifecycle']}"==grp and r['warmup']=='False']
  if len(g_rows)<2:continue
  xs=[json.loads(r['p2_counters'])['quadratic_attempts'] for r in g_rows]
  ys=[float(r['p2_prove_ms']) for r in g_rows]
  mx,my=statistics.mean(xs),statistics.mean(ys)
  denom=sum((x-mx)**2 for x in xs)
  slope=sum((x-mx)*(y-my) for x,y in zip(xs,ys))/denom if denom else 0.0
  intercept=my-slope*mx
  norm_5_5=intercept+slope*5.5
  out[grp]={'p2_fixed_ms':intercept,'p2_per_quad_attempt_ms':slope,'p2_prove_normalized_at_5_5_attempts_ms':norm_5_5}
 return out

b=json.loads(a.before.read_text());c=json.loads(a.after.read_text());rows=[]
fit_b=fit_samples(a.before);fit_c=fit_samples(a.after)
for group in sorted(set(b['groups'])&set(c['groups'])):
 x,y=b['groups'][group],c['groups'][group]
 for key in ['p1_prove_ms','p1_verify_and_issue_ms','p2_prove_ms','p2_verify_ms','show_flow_ms','end_to_end_fresh_ms','presentation_proof_bytes']:
  v=x.get('metrics',{}).get(key,{}).get('mean');w=y.get('metrics',{}).get(key,{}).get('mean')
  v_med=x.get('metrics',{}).get(key,{}).get('median');w_med=y.get('metrics',{}).get(key,{}).get('median')
  v_p95=x.get('metrics',{}).get(key,{}).get('p95_nearest_rank');w_p95=y.get('metrics',{}).get(key,{}).get('p95_nearest_rank')
  if v is not None and w is not None:
   rows.append({
    'group':group,'metric':key,
    'before_source':str(a.before.relative_to(R) if a.before.is_relative_to(R) else a.before),
    'after_source':str(a.after.relative_to(R) if a.after.is_relative_to(R) else a.after),
    'old_mean':round(v,4),'new_mean':round(w,4),
    'delta_mean':round(w-v,4),'relative_mean_pct':round((w/v-1)*100,2) if v else None,
    'old_median':round(v_med,4) if v_med is not None else None,
    'new_median':round(w_med,4) if w_med is not None else None,
    'old_p95':round(v_p95,4) if v_p95 is not None else None,
    'new_p95':round(w_p95,4) if w_p95 is not None else None,
    'old_n':x['planned'],'new_n':y['planned']
   })
 if group in fit_b and group in fit_c:
  for key in ['p2_fixed_ms','p2_per_quad_attempt_ms','p2_prove_normalized_at_5_5_attempts_ms']:
   v=fit_b[group][key];w=fit_c[group][key]
   rows.append({
    'group':group,'metric':key,
    'before_source':str(a.before.relative_to(R) if a.before.is_relative_to(R) else a.before),
    'after_source':str(a.after.relative_to(R) if a.after.is_relative_to(R) else a.after),
    'old_mean':round(v,4),'new_mean':round(w,4),
    'delta_mean':round(w-v,4),'relative_mean_pct':round((w/v-1)*100,2) if v else None,
    'old_median':None,'new_median':None,'old_p95':None,'new_p95':None,
    'old_n':x['planned'],'new_n':y['planned']
   })
a.output.parent.mkdir(exist_ok=True,parents=True)
with a.output.open('w',newline='') as f:
 if rows:writer=csv.DictWriter(f,fieldnames=list(rows[0].keys()));writer.writeheader();writer.writerows(rows)
print('REGRESSION_WRITTEN',a.output,'rows',len(rows),'before=',a.before,'after=',a.after)
for r in rows:
 if r['metric'] in ('p1_prove_ms','p2_prove_ms','p2_verify_ms','show_flow_ms','p2_fixed_ms','p2_per_quad_attempt_ms','p2_prove_normalized_at_5_5_attempts_ms'):
  print(f"  [{r['group']}] {r['metric']}: {r['old_mean']:.2f} -> {r['new_mean']:.2f} ({r['relative_mean_pct']:+.2f}%)")
