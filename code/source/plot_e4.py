#!/usr/bin/env python3
"""Bilingual, true-vector PDF/SVG and 300-dpi PNG. Invalid fonts are skipped."""
import argparse,csv,json,os,warnings
from pathlib import Path
os.environ.setdefault('MPLBACKEND','Agg')
import matplotlib
matplotlib.use('Agg')
from matplotlib import pyplot as plt,font_manager,ft2font
import numpy as np
R=Path(__file__).resolve().parent
COLORS={'B1':'#333333','V0':'#999999','V1':'#984ea3','G3':'#0072B2','C3':'#009E73'}
STYLES={'B1':'o-','V0':'s--','V1':'^-.','G3':'D-','C3':'v--'}
def read(p):
 with p.open() as f:return list(csv.DictReader(f))
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--batch',type=Path,required=True);ap.add_argument('--lang',choices=['en','zh','both'],default='both');a=ap.parse_args();B=a.batch.resolve();D=B/'derived'
 data=json.loads((D/'summary.json').read_text());mainrows=data['main'];samples=read(D/'samples.csv')
 valid=[];errors=[]
 for p in sorted((R/'fonts').glob('*')):
  if p.suffix.lower() not in ['.ttf','.otf','.ttc']:continue
  try:face=ft2font.FT2Font(str(p));font_manager.fontManager.addfont(str(p));valid.append((face.family_name,set(face.get_charmap())))
  except (RuntimeError,OSError,ValueError) as e:errors.append(dict(font=p.name,error=str(e)))
 status=[]
 for lang in (['en','zh'] if a.lang=='both' else [a.lang]):
  if lang=='zh' and not valid:status.append(dict(lang=lang,status='MISSING_CJK_FONT'));continue
  family=valid[0][0] if lang=='zh' else 'DejaVu Sans'
  plt.rcParams.update({'font.family':family,'font.size':9,'axes.labelsize':10,'legend.fontsize':8,'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42,'ps.fonttype':42,'svg.fonttype':'path','axes.unicode_minus':False,'savefig.bbox':'tight'})
  def label(en,zh):return zh if lang=='zh' else en
  def save(fig,name):
   for ext in ['png','pdf','svg']:
    p=B/'figures'/lang/ext/(name+'.'+ext);p.parent.mkdir(parents=True,exist_ok=True);fig.savefig(p,dpi=300)
   plt.close(fig)
  # 1 Main strict performance: stage decomposition, without pretending CI.
  fig,axes=plt.subplots(1,2,figsize=(7.2,2.8),sharey=True)
  for ax,life in zip(axes,['steady','fresh']):
   rr=[next(x for x in mainrows if x['variant']==v and x['lifecycle']==life and x['verification_mode']=='strict') for v in ['B1','G3','C3']]
   ax.bar(range(3),[x['prove_mean_ms'] for x in rr],color=[COLORS[x['variant']] for x in rr],label=label('Generation','证明生成'))
   ax.bar(range(3),[x['verify_mean_ms'] for x in rr],bottom=[x['prove_mean_ms'] for x in rr],color='#cccccc',edgecolor='#555555',hatch='//',label=label('Verification','证明验证'))
   ax.set_xticks(range(3),['B1','G3','C3']);ax.set_title(life+' / strict');ax.grid(axis='y',alpha=.2)
  axes[0].set_ylabel(label('Mean local time (ms)','本地耗时均值 (ms)'));axes[1].legend(frameon=False);fig.tight_layout();save(fig,'E4_01_main_strict')
  # 2 ECDF preserves tail, no smoothing.
  fig,axes=plt.subplots(1,2,figsize=(7.2,2.8))
  for ax,life in zip(axes,['steady','fresh']):
   for v in ['B1','G3','C3']:
    z=sorted(float(x['show_ms']) for x in samples if x['task']=='main' and x['variant']==v and x['lifecycle']==life and x['verification_mode']=='strict')
    ax.step(z,np.arange(1,len(z)+1)/len(z),where='post',label=v,color=COLORS[v],linestyle={'B1':':','G3':'-','C3':'--'}[v])
   ax.set_title(life+' / strict');ax.set_xlabel(label('Local show time (ms)','本地出示合计 (ms)'));ax.grid(alpha=.2)
  axes[0].set_ylabel('ECDF');axes[1].legend(frameon=False);fig.tight_layout();save(fig,'E4_02_latency_ecdf')
  # 3 First-use and amortized service cost (includes user/verifier initialization).
  rr=read(D/'reuse.csv');fig,ax=plt.subplots(figsize=(5.6,3.1))
  for v in ['B1','V0','V1','G3','C3']:
   ns=sorted({int(x['N']) for x in rr if x['variant']==v});ys=[np.mean([float(x['amortized_local_service_ms']) for x in rr if x['variant']==v and int(x['N'])==n]) for n in ns]
   ax.plot(ns,ys,STYLES[v],markersize=3,label=v,color=COLORS[v])
  ax.set_xscale('log',base=2);ax.set_xlabel(label('Presentations per object N','每个对象出示次数 N'));ax.set_ylabel(label('Amortized local service time (ms)','本地服务摊销耗时 (ms)'));ax.legend(frameon=False,ncol=3);ax.grid(alpha=.2);fig.tight_layout();save(fig,'E4_03_reuse_amortization')
  # 4 Same-k padded versus compact, with actual sample range, not fabricated error bars.
  rr=read(D/'k_sweep.csv');fig,ax=plt.subplots(figsize=(5.6,3.1))
  for v in ['G3','C3']:
   r=sorted((x for x in rr if x['variant']==v),key=lambda x:int(x['k']));k=np.array([int(x['k']) for x in r]);y=np.array([float(x['proof_mean_bytes']) for x in r]);lo=np.array([float(x['proof_min_bytes']) for x in r]);hi=np.array([float(x['proof_max_bytes']) for x in r])
   ax.errorbar(k,y,yerr=[y-lo,hi-y],fmt=STYLES[v],label=v,color=COLORS[v],capsize=2,markersize=3)
  ax.set_xlabel(label('Disclosed attributes k','披露属性数量 k'));ax.set_ylabel(label('Proof size (B), mean and range','证明大小 (B)，均值与范围'));ax.legend(frameon=False);ax.grid(alpha=.2);fig.tight_layout();save(fig,'E4_04_same_k_size')
  # 5 Policy stability.
  rr=read(D/'policy.csv');fig,ax=plt.subplots(figsize=(5.6,3.1));patterns=['fixed','alternating','random']
  for j,v in enumerate(['V1','G3','C3']):
   y=[float(next(x for x in rr if x['variant']==v and x['pattern']==p)['show_mean_ms']) for p in patterns];ax.bar(np.arange(3)+(j-1)*.22,y,width=.22,label=v,color=COLORS[v])
  ax.set_xticks(range(3),patterns if lang=='en' else ['固定','交替','随机']);ax.set_ylabel(label('Mean local time (ms)','本地耗时均值 (ms)'));ax.legend(frameon=False);ax.grid(axis='y',alpha=.2);fig.tight_layout();save(fig,'E4_05_policy')
  # 6 Show all fallback reason counts; diagnostics use MPFR decisions regardless of candidate.
  rr=read(D/'float_shadow.csv');fig,ax=plt.subplots(figsize=(6.5,3.1));keys=['std_limb','std_positive_exponent','std_other_domain','std_nonfinite','std_guard_band','bim_limb','bim_domain','bim_nonfinite','bim_guard_band']
  for j,r in enumerate(rr):ax.bar(np.arange(9)+(j-.5)*.36,[int(r[k]) for k in keys],width=.36,label=r['variant'])
  ax.set_xticks(range(9),['S limb','S positive','S domain','S finite','S band','B limb','B domain','B finite','B band'],rotation=35,ha='right');ax.set_ylabel(label('Fallback count','回退次数'));ax.legend(frameon=False);ax.grid(axis='y',alpha=.2);fig.tight_layout();save(fig,'E4_06_fallback_reasons')
  # 7 raw and strict are explicitly different measured interfaces.
  fig,axes=plt.subplots(1,2,figsize=(7.2,2.8),sharey=True)
  for ax,life in zip(axes,['steady','fresh']):
   for j,mode in enumerate(['raw','strict']):
    rr=[next(x for x in mainrows if x['variant']==v and x['lifecycle']==life and x['verification_mode']==mode) for v in ['B1','G3','C3']]
    ax.bar(np.arange(3)+(j-.5)*.34,[x['verify_mean_ms'] for x in rr],width=.34,label=mode,color=['#777777','#0072B2'][j])
   ax.set_xticks(range(3),['B1','G3','C3']);ax.set_title(life);ax.grid(axis='y',alpha=.2)
  axes[0].set_ylabel(label('Mean verification time (ms)','验证耗时均值 (ms)'));axes[1].legend(frameon=False);fig.tight_layout();save(fig,'E4_07_raw_strict')
  status.append(dict(lang=lang,status='COMPLETE',figures=7))
 (B/'plot_status.json').write_text(json.dumps(dict(languages=status,ignored_invalid_fonts=errors),indent=2))
 if any(x['status']!='COMPLETE' for x in status):raise SystemExit('Some requested languages could not be rendered; data and English figures preserved')
 print('PLOTS_COMPLETE: 7 figures per language; PNG/PDF/SVG; source tables in derived/')
if __name__=='__main__':main()
