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
 ap=argparse.ArgumentParser();ap.add_argument('--batch',type=Path,required=True);ap.add_argument('--lang',choices=['en','zh','both'],default='both');ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();B=a.output.resolve();D=B/'derived'
 data=json.loads((D/'summary.json').read_text());mainrows=data['main'];samples=read(D/'samples.csv')
 from paper_fonts import configure,validate_text
 status=[];errors=[]
 for lang in (['en','zh'] if a.lang=='both' else [a.lang]):
  configure(lang)
  def label(en,zh):return zh if lang=='zh' else en
  names_zh={'B1':'修正基线','V0':'复用组合','V1':'双层复用','G3':'填充优化','C3':'紧致优化'}
  names_en={'B1':'Corrected baseline','V0':'Reuse bundle','V1':'Two-level reuse','G3':'Padded optimization','C3':'Compact optimization'}
  def name(v):return (names_zh if lang=='zh' else names_en)[v]
  def tickname(v):return name(v) if lang=='zh' else name(v).replace(' ','\n',1)
  def load_title(life):return label({'steady':'Repeated presentation','fresh':'Session reconstruction'}[life],{'steady':'重复出示','fresh':'会话重建'}[life])+(' / 严格验证' if lang=='zh' else '\nStrict verification')
  def save(fig,name):
   validate_text(fig,lang)
   fig.canvas.draw()
   for ax in fig.axes:
    labels=[t for t in ax.get_xticklabels() if t.get_visible() and t.get_text()]
    boxes=[t.get_window_extent(fig.canvas.get_renderer()) for t in labels]
    if any(a.overlaps(b) for a,b in zip(boxes,boxes[1:])):raise RuntimeError('Overlapping x-axis labels: '+name)
   for ext in ['png','pdf','svg']:
    p=B/'figures'/lang/ext/(name+'.'+ext);p.parent.mkdir(parents=True,exist_ok=True);fig.savefig(p,dpi=300)
   plt.close(fig)
  # 1 Main strict performance: stage decomposition, without pretending CI.
  fig,axes=plt.subplots(1,2,figsize=(7.2,2.8),sharey=True)
  for ax,life in zip(axes,['steady','fresh']):
   rr=[next(x for x in mainrows if x['variant']==v and x['lifecycle']==life and x['verification_mode']=='strict') for v in ['B1','G3','C3']]
   ax.bar(range(3),[x['prove_mean_ms'] for x in rr],color='#0072B2',label=label('Generation','证明生成'))
   ax.bar(range(3),[x['verify_mean_ms'] for x in rr],bottom=[x['prove_mean_ms'] for x in rr],color='#E69F00',edgecolor='#555555',hatch='//',label=label('Verification','证明验证'))
   ax.set_xticks(range(3),[tickname(v) for v in ['B1','G3','C3']]);ax.set_title(load_title(life));ax.grid(axis='y',alpha=.2)
  axes[0].set_ylabel(label('Mean local time (ms)','本地耗时均值 (ms)'));axes[1].legend(frameon=False);fig.tight_layout();save(fig,'fig3_main_strict')
  # 2 ECDF preserves tail, no smoothing.
  fig,axes=plt.subplots(1,2,figsize=(7.2,2.8))
  for ax,life in zip(axes,['steady','fresh']):
   for v in ['B1','G3','C3']:
    z=sorted(float(x['show_ms']) for x in samples if x['task']=='main' and x['variant']==v and x['lifecycle']==life and x['verification_mode']=='strict')
    ax.step(z,np.arange(1,len(z)+1)/len(z),where='post',label=name(v),color=COLORS[v],linestyle={'B1':':','G3':'-','C3':'--'}[v])
   ax.set_title(load_title(life));ax.set_xlabel(label('Local show time (ms)','本地出示合计 (ms)'));ax.grid(alpha=.2)
  axes[0].set_ylabel(label('Cumulative sample proportion','样本累计比例'));axes[1].legend(frameon=False);fig.tight_layout();save(fig,'fig5_latency_ecdf')
  # 3 First-use and amortized service cost (includes user/verifier initialization).
  rr=read(D/'reuse.csv');fig,ax=plt.subplots(figsize=(5.6,3.1))
  for v in ['B1','V0','V1','G3','C3']:
   ns=sorted({int(x['N']) for x in rr if x['variant']==v});ys=[np.mean([float(x['amortized_local_service_ms']) for x in rr if x['variant']==v and int(x['N'])==n]) for n in ns]
   lo=[min(float(x['amortized_local_service_ms']) for x in rr if x['variant']==v and int(x['N'])==n) for n in ns];hi=[max(float(x['amortized_local_service_ms']) for x in rr if x['variant']==v and int(x['N'])==n) for n in ns]
   ax.fill_between(ns,lo,hi,color=COLORS[v],alpha=.10)
   ax.errorbar(ns,ys,yerr=[np.array(ys)-lo,np.array(hi)-ys],fmt=STYLES[v],markersize=3,capsize=2,label=name(v),color=COLORS[v])
  ax.set_xscale('log',base=2);ax.set_xlabel(label('Presentations per object N','每个对象出示次数 N'));ax.set_ylabel(label('Amortized local service time (ms)','本地服务摊销耗时 (ms)'));ax.legend(frameon=False,ncol=3 if lang=='zh' else 2);ax.grid(alpha=.2);fig.tight_layout();save(fig,'fig6_reuse_amortization')
  # 4 Same-k padded versus compact, with actual sample range, not fabricated error bars.
  rr=read(D/'k_sweep.csv');fig,ax=plt.subplots(figsize=(5.6,3.1))
  for v in ['G3','C3']:
   r=sorted((x for x in rr if x['variant']==v),key=lambda x:int(x['k']));k=np.array([int(x['k']) for x in r]);y=np.array([float(x['proof_mean_bytes']) for x in r]);lo=np.array([float(x['proof_min_bytes']) for x in r]);hi=np.array([float(x['proof_max_bytes']) for x in r])
   ax.errorbar(k,y,yerr=[y-lo,hi-y],fmt=STYLES[v],label=name(v),color=COLORS[v],capsize=2,markersize=3)
  ax.set_xlabel(label('Disclosed attributes k','披露属性数量 k'));ax.set_ylabel(label('Proof size (B), mean and range','证明大小 (B)，均值与范围'));ax.legend(frameon=False);ax.grid(alpha=.2);fig.tight_layout();save(fig,'fig7_same_k_size')
  # Paper Fig4: descriptive common-K OLS predictions and all 30 block differences.
  rr=read(D/'block_effects.csv');fig,axes=plt.subplots(2,2,figsize=(7.2,5.0),sharex='row')
  for j,life in enumerate(['steady','fresh']):
   ax=axes[0,j];group=[next(x for x in mainrows if x['variant']==v and x['lifecycle']==life and x['verification_mode']=='strict') for v in ['B1','G3','C3']]
   ax.bar(range(3),[x['ols_at_5_5'] for x in group],color=[COLORS[x['variant']] for x in group]);ax.set_xticks(range(3),[tickname(v) for v in ['B1','G3','C3']]);ax.set_title(load_title(life));ax.grid(axis='y',alpha=.2)
   for i,x in enumerate(group):ax.text(i,x['ols_at_5_5']+1,f"{x['ols_at_5_5']:.2f}",ha='center',fontsize=8)
   bx=axes[1,j];z=sorted((x for x in rr if x['lifecycle']==life and x['verification_mode']=='strict' and x['base']=='G3' and x['target']=='C3'),key=lambda x:(int(x['round']),int(x['block'])))
   effects=[float(x['reduction_percent']) for x in z];xx=np.arange(1,len(z)+1);bx.bar(xx,effects,color=['#009E73' if y>=0 else '#D55E00' for y in effects]);bx.axhline(0,color='#555555',lw=.8)
   for n in range(1,len(z)):
    if z[n]['round']!=z[n-1]['round']:bx.axvline(n+.5,color='#888888',ls=':',lw=.8)
   bx.set_xlabel(label('Measurement block (10 per timing batch)','测量块编号（每批10块）'));bx.grid(axis='y',alpha=.2)
  axes[0,0].set_ylabel(label('OLS generation at K=5.5\n(ms)','K=5.5 生成耗时预测 (ms)'));axes[1,0].set_ylabel(label('Compact vs padded\nreduction (%)','紧致化相对填充优化的降幅 (%)'));fig.tight_layout();save(fig,'fig4_ols_and_block_effects')
  status.append(dict(lang=lang,status='COMPLETE',figures=5))
 (B/'paper_plot_status.json').write_text(json.dumps(dict(languages=status,ignored_invalid_fonts=errors),indent=2))
 if any(x['status']!='COMPLETE' for x in status):raise SystemExit('Some requested languages could not be rendered; data and English figures preserved')
 print('PLOTS_COMPLETE: 5 data figures per language (schematics separate); PNG/PDF/SVG; source tables in derived/')
if __name__=='__main__':main()
