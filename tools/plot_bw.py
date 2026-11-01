#!/usr/bin/env python3
"""Redraw all eight Chinese manuscript figures from frozen CSV/JSON inputs."""
import argparse, csv, json, os, random, shutil
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Rectangle,FancyArrowPatch

ROOT=Path(__file__).resolve().parents[1]
LABELS={'B1':'修正基线','V0':'复用组合','V1':'双层复用','G3':'填充优化','C3':'紧致优化'}
STYLE={'B1':('o','-'),'V0':('s','--'),'V1':('^','-.'),'G3':('D',':'),'C3':('v',(0,(4,1,1,1)))}

def read(name):
    with (ROOT/'data/derived'/name).open() as f:return list(csv.DictReader(f))

def bootstrap(life):
    rr=sorted([r for r in read('block_effects.csv') if r['verification_mode']=='strict' and r['lifecycle']==life and r['base']=='G3' and r['target']=='C3'],key=lambda r:(int(r['round']),int(r['block'])))
    # Preserve original independent-recompute RNG and quantile convention exactly.
    rng=np.random.default_rng(20261020)
    base=np.array([float(r['base_mean_ms']) for r in rr]).reshape(3,10)
    comp=np.array([float(r['target_mean_ms']) for r in rr]).reshape(3,10)
    ix=rng.integers(0,10,size=(25000,3,10))
    av=np.take_along_axis(np.broadcast_to(base,(25000,3,10)),ix,axis=2).mean((1,2))
    bv=np.take_along_axis(np.broadcast_to(comp,(25000,3,10)),ix,axis=2).mean((1,2))
    boot=100*(1-bv/av)
    return 100*(1-comp.mean()/base.mean()),float(np.quantile(boot,.025)),float(np.quantile(boot,.975)),int((base>comp).sum())

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=ROOT.parent/'figures_from_data');a=p.parse_args()
    a.output=a.output.resolve()
    if a.output==ROOT or ROOT in a.output.parents:raise SystemExit('Choose output outside the frozen package')
    f=ROOT/'tools/fonts/LazerPaperCJK.otf'
    font_manager.fontManager.addfont(str(f));name=font_manager.FontProperties(fname=f).get_name()
    plt.rcParams.update({'font.family':name,'font.size':8.8,'axes.labelsize':9,'legend.fontsize':8,
        'axes.spines.top':False,'axes.spines.right':False,'axes.unicode_minus':False,
        'pdf.fonttype':42,'svg.fonttype':'path','lines.linewidth':1,'savefig.facecolor':'white'})
    mapping=[]
    def save(fig,label,inputs):
        # Keep the author-approved mechanism diagram in exact vector form.
        if label == '图1_声明复用与紧致关系' and (ROOT/'figures/SVG'/(label+'.svg')).exists():
            for ext in ['png','pdf','svg']:
                dest=a.output/ext.upper()/(label+'.'+ext);dest.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(ROOT/'figures'/ext.upper()/(label+'.'+ext),dest)
            mapping.append(dict(figure=label,input=inputs,style='exact approved vector diagram'))
            plt.close(fig);return
        for ext in ['png','pdf','svg']:
            out=a.output/ext.upper()/(label+'.'+ext);out.parent.mkdir(parents=True,exist_ok=True)
            fig.savefig(out,dpi=600,bbox_inches='tight',pad_inches=.035)
        mapping.append(dict(figure=label,input=inputs,style='black/white; distinct lines, markers and hatches; actual ranges where stated'))
        plt.close(fig)
    def grid(ax):ax.set_axisbelow(True);ax.grid(color='.82',lw=.45)
    mainrows=read('main_summary.csv')
    def row(v,life):return next(r for r in mainrows if r['variant']==v and r['lifecycle']==life and r['verification_mode']=='strict')

    # Figure 1: same mechanism and dimensions as the submitted schematic.
    fig,ax=plt.subplots(figsize=(5.74,2.22));ax.set(xlim=(0,146),ylim=(0,60));ax.axis('off')
    def box(x,y,w,h,t):
        ax.add_patch(Rectangle((x,y),w,h,fc='white',ec='black',lw=.7))
        ax.text(x+w/2,y+h/2,t,ha='center',va='center',fontsize=8.1,linespacing=1.35)
    def arrow(a,b):ax.add_patch(FancyArrowPatch(a,b,arrowstyle='-|>',mutation_scale=8,color='black',lw=.8))
    ax.text(1,59,'（a）声明状态复用',va='top',fontsize=9)
    for x,t in [(1,'声明矩阵及元数据\n保持不变'),(38,'首次：编码不终止\n保存前缀及CRT'),(75,'后续：复制前缀\n续写公开向量'),(112,'只终止一次\n生成声明哈希')]:box(x,40,33,12,t)
    for x in [34,71,108]:arrow((x,46),(x+4,46))
    ax.text(73,35,'设置接口更新→重建；清理及地址复用前→旧缓存失效',ha='center',fontsize=7.7)
    ax.text(1,28,'（b）公开零坐标的同步收缩',fontsize=9)
    box(1,3,56,19,'填充关系\n应用列数48；二进制约束16\n公开属性列及见证坐标置零')
    box(89,3,56,19,'紧致关系\n应用列数48−k；二进制约束16−k\n保留隐藏属性，同步更新索引/参数')
    arrow((58,17),(88,17));arrow((88,8),(58,8));ax.text(73,19,'投影',ha='center',fontsize=8);ax.text(73,1,'补零',ha='center',fontsize=8)
    fig.subplots_adjust(0,0,1,1);save(fig,'图1_声明复用与紧致关系',['manuscript sections 2.1-2.2; no measured values'])

    # Figure 2: explicit x-axis title required by the editor.
    fig,ax=plt.subplots(figsize=(2.85,2.16));x=np.array([0,1,2,4,5,6]);rr=[row(v,l) for l in ['steady','fresh'] for v in ['B1','G3','C3']]
    pro=np.array([float(r['prove_mean_ms']) for r in rr]);ver=np.array([float(r['verify_mean_ms']) for r in rr])
    ax.bar(x,pro,width=.7,fc='white',ec='black',lw=.7,label='生成')
    ax.bar(x,ver,bottom=pro,width=.7,fc='white',ec='black',lw=.7,hatch='////',label='验证')
    for xx,r in zip(x,rr):ax.text(xx,float(r['show_mean_ms'])+1.2,f"{float(r['show_mean_ms']):.2f}",ha='center',fontsize=8)
    ax.set(xticks=x,xticklabels=['基线','填充','紧致']*2,ylim=(0,150),ylabel='本地耗时/ms',xlabel='实现方案')
    ax.text(1,140,'重复出示',ha='center',fontsize=8.3);ax.text(5,140,'会话重建',ha='center',fontsize=8.3)
    ax.legend(ncol=2,frameon=False,loc='lower center',bbox_to_anchor=(.5,1.0));grid(ax)
    fig.subplots_adjust(left=.21,right=.995,bottom=.22,top=.85);save(fig,'图2_严格验证耗时',['data/derived/main_summary.csv; strict, n=600 per cell'])

    fig,ax=plt.subplots(figsize=(2.85,1.94))
    for life,y,marker in [('steady',1,'o'),('fresh',0,'s')]:
        m,lo,hi,n=bootstrap(life)
        ax.errorbar(m,y,xerr=[[m-lo],[hi-m]],fmt=marker,color='black',mfc='white',capsize=3,ms=4)
        ax.text(5.3,y+.24,f'{m:.2f}% [{lo:.2f}, {hi:.2f}]',ha='center',fontsize=7.8)
    ax.axvline(0,color='black',ls='--',lw=.7)
    ax.set(yticks=[1,0],yticklabels=['重复出示\n15/30块改善','会话重建\n21/30块改善'],xlim=(-2,12),ylim=(-.55,1.55),xticks=[0,5,10],xlabel='填充至紧致的出示均值降幅/%')
    fig.subplots_adjust(left=.34,right=.99,bottom=.25,top=.95);save(fig,'图3_紧致化增量与区间',['data/derived/block_effects.csv; stratified bootstrap 25000, seed 20261020'])

    reuse=read('reuse.csv')
    def amortized(size,label):
        fig,ax=plt.subplots(figsize=size)
        for v in ['B1','V0','V1','G3','C3']:
            ns=sorted({int(r['N']) for r in reuse if r['variant']==v})
            z=[[float(r['amortized_local_service_ms']) for r in reuse if r['variant']==v and int(r['N'])==n] for n in ns]
            ys=np.array([np.mean(a) for a in z]);low=np.array([min(a) for a in z]);high=np.array([max(a) for a in z]);mk,ls=STYLE[v]
            ax.errorbar(ns,ys,yerr=[ys-low,high-ys],marker=mk,ls=ls,color='black',mfc='white',ms=3,capsize=1.8,lw=.85,label=LABELS[v])
        ax.set_xscale('log',base=2);ax.set_xticks([1,4,16,64,256],['1','4','16','64','256']);ax.minorticks_off()
        ax.set(xlim=(.8,320),ylim=(55,200),xlabel='每个对象出示次数 $N$',ylabel='本地服务摊销耗时/ms',yticks=[60,90,120,150,180]);grid(ax)
        ax.legend(ncol=2 if size[0]<4 else 3,frameon=False,fontsize=8 if size[0]<4 else 8.5,loc='lower center',bbox_to_anchor=(.5,1.0),handlelength=2.4,columnspacing=.8)
        fig.subplots_adjust(left=.22 if size[0]<4 else .12,right=.99,bottom=.2,top=.74 if size[0]<4 else .84)
        save(fig,label,['data/derived/reuse.csv; three lifetimes; mean and observed min/max; shared prefixes'])
    amortized((2.85,2.26),'图4_完整服务摊销曲线')

    fig,ax=plt.subplots(figsize=(2.85,2.02));sweep=read('k_sweep.csv')
    for v,mk,ls in [('G3','o','-'),('C3','s','--')]:
        rr=sorted([r for r in sweep if r['variant']==v],key=lambda r:int(r['k']));k=[int(r['k']) for r in rr]
        y=np.array([float(r['proof_mean_bytes']) for r in rr]);lo=np.array([float(r['proof_min_bytes']) for r in rr]);hi=np.array([float(r['proof_max_bytes']) for r in rr])
        ax.errorbar(k,y/1000,yerr=[(y-lo)/1000,(hi-y)/1000],color='black',marker=mk,ls=ls,mfc='white',ms=3,capsize=2,label='填充' if v=='G3' else '紧致')
    ax.set(xlabel='披露属性数 $k$',ylabel='证明大小/KB',xticks=range(9),ylim=(27.3,29.35));ax.legend(frameon=False,loc='lower left');grid(ax)
    fig.subplots_adjust(left=.23,right=.99,bottom=.23,top=.98);save(fig,'图5_同披露数证明大小',['data/derived/k_sweep.csv; n=30 per k/variant; mean and observed range; 1 KB=1000 B'])

    fig,axes=plt.subplots(2,2,figsize=(5.74,4.08))
    for j,life in enumerate(['steady','fresh']):
        ax=axes[0,j];rr=[row(v,life) for v in ['B1','G3','C3']];yy=[float(r['ols_at_5_5']) for r in rr]
        bars=ax.bar(range(3),yy,color='white',ec='black',lw=.7)
        for b,h in zip(bars,['','//','xx']):b.set_hatch(h)
        for x,y in enumerate(yy):ax.text(x,y+1,f'{y:.2f}',ha='center',fontsize=8)
        ax.set_xticks(range(3),['修正基线','填充优化','紧致优化']);ax.tick_params(axis='x',labelsize=7.8)
        ax.set_title(('重复出示' if life=='steady' else '会话重建')+'/严格验证',fontsize=9);ax.set_ylim(0,85);grid(ax)
        bx=axes[1,j];rr=sorted([r for r in read('block_effects.csv') if r['verification_mode']=='strict' and r['lifecycle']==life and r['base']=='G3' and r['target']=='C3'],key=lambda r:(int(r['round']),int(r['block'])))
        for x,r in enumerate(rr,1):
            y=float(r['reduction_percent']);bx.bar(x,y,color='white',ec='black',lw=.35,hatch='///' if y<0 else None,width=.8)
        bx.axhline(0,color='black',lw=.7)
        for x in [10.5,20.5]:bx.axvline(x,color='black',ls=':',lw=.65)
        bx.set(xlabel='测量块编号（每批10块）',xticks=[1,5,10,15,20,25,30]);grid(bx)
    axes[0,0].set_ylabel('$K=5.5$时生成预测/ms');axes[1,0].set_ylabel('紧致化总时间降幅/%')
    fig.tight_layout(pad=.8,h_pad=1.2);save(fig,'图S1_回归与全部分块',['data/derived/main_summary.csv','data/derived/block_effects.csv; positive white, negative hatched; no trimming'])

    fig,axes=plt.subplots(1,2,figsize=(5.74,2.45));samples=read('samples.csv')
    for ax,life in zip(axes,['steady','fresh']):
        for v in ['B1','G3','C3']:
            z=sorted(float(r['show_ms']) for r in samples if r['task']=='main' and r['variant']==v and r['lifecycle']==life and r['verification_mode']=='strict')
            _,ls=STYLE[v];ax.step(z,np.arange(1,len(z)+1)/len(z),where='post',color='black',ls=ls,label=LABELS[v])
        ax.set_title(('重复出示' if life=='steady' else '会话重建')+'/严格验证',fontsize=9)
        ax.set(xlabel='本地出示合计/ms',ylim=(0,1.03));grid(ax)
    axes[0].set_ylabel('样本累计比例');axes[1].legend(frameon=False,loc='lower right',fontsize=8)
    fig.tight_layout(pad=.6);save(fig,'图S2_严格验证经验分布',['data/derived/samples.csv; strict main; full ECDF, no smoothing'])
    amortized((5.74,3.2),'图S3_完整服务摊销大图')
    (a.output/'FIGURE_DATA_MAP.json').write_text(json.dumps(mapping,ensure_ascii=False,indent=2)+'\n')
    print('8 black-and-white figures generated, SVG/PDF/PNG')

if __name__=='__main__':main()
