import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties,fontManager
from matplotlib.patches import FancyArrowPatch,Rectangle
from pathlib import Path
import numpy as np
import os
import argparse, csv
ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
ROOT=Path(__file__).resolve().parents[1];out=args.output;out.mkdir(parents=True,exist_ok=True)
fontfile=os.environ.get('LAZER_CJK_FONT','')
if fontfile:
 fontManager.addfont(fontfile)
 fontname=FontProperties(fname=fontfile).get_name()
else:
 fontname='Noto Serif CJK SC'
plt.rcParams.update({'font.family':fontname,'font.size':8.5,'axes.unicode_minus':False,'axes.spines.top':False,'axes.spines.right':False,'lines.linewidth':1,'pdf.fonttype':42,'svg.fonttype':'path'})
def save(fig,n):
 labels=['图1_声明复用与紧致关系','图2_严格验证耗时','图3_紧致化增量与区间','图4_完整服务摊销曲线','图5_同披露数证明大小']
 for ext in ['svg','png']:
  dest=out/ext.upper();dest.mkdir(exist_ok=True);fig.savefig(dest/f'{labels[n-1]}.{ext}',dpi=600,facecolor='white')
 plt.close(fig)
mm=1/25.4
f,ax=plt.subplots(figsize=(146*mm,63*mm));ax.set(xlim=(0,146),ylim=(0,63));ax.axis('off')
BLUE='#0072B2'; ORANGE='#E69F00'; GREEN='#009E73'; PURPLE='#AA4499'
def box(x,y,w,h,t,fs=8.5):
 ax.add_patch(Rectangle((x,y),w,h,facecolor=('#E7F4EF' if x>=89 else '#E8F2FA'),edgecolor=(GREEN if x>=89 else BLUE),linewidth=.65));ax.text(x+w/2,y+h/2,t,ha='center',va='center',fontsize=fs)
def arrow(a,b,ls='-'):
 ax.add_patch(FancyArrowPatch(a,b,arrowstyle='-|>',mutation_scale=7,color=BLUE,linewidth=.7,linestyle=ls))
ax.text(1,62,'(a) 声明状态复用',fontsize=9,va='top')
for x,t in [(1,'声明矩阵及元数据\n保持不变'),(38,'首次：编码不终止\n保存前缀及CRT'),(75,'后续：复制前缀\n续写公开向量'),(112,'只终止一次\n生成声明哈希')]:box(x,42,33,14,t)
for x in [34,71,108]:arrow((x,49),(x+4,49))
ax.text(73,37,'设置接口更新 → 重建/失效；清理及地址复用前 → 旧条目失效',ha='center',fontsize=8)
ax.text(1,30,'(b) 公开零坐标的同步收缩',fontsize=9)
box(1,5,56,20,'填充关系\n应用列数 48；二进制约束 16\n公开属性列及见证坐标置零',8.5)
box(89,5,56,20,'紧致关系\n应用列数 48−k；二进制约束 16−k\n保留隐藏属性，同步更新索引/参数',8.5)
arrow((58,19),(88,19));arrow((88,10),(58,10));ax.text(73,21,'投影',ha='center');ax.text(73,4,'补零',ha='center')
f.subplots_adjust(0,0,1,1);save(f,1)
# Main performance: source table4, strict, n600 each
f,ax=plt.subplots(figsize=(69*mm,56*mm));x=np.array([0,1,2,4,5,6]);pro=np.array([76.32,50.17,48.45,78.10,63.16,58.16]);ver=np.array([32.97,19.28,18.34,35.95,27.21,26]);total=[109.30,69.45,66.79,114.05,90.37,84.16]
ax.bar(x,pro,color=BLUE,edgecolor='#005886',width=.68,label='生成');ax.bar(x,ver,bottom=pro,color=ORANGE,edgecolor='#9F6E00',width=.68,hatch='///',label='验证')
for xx,v in zip(x,total):ax.text(xx,v+2,f'{v:.2f}',ha='center',fontsize=7.5)
ax.set(xticks=x,xticklabels=['基线','填充','紧致']*2,ylim=(0,138),ylabel='本地耗时 / ms');ax.text(1,126,'重复出示',ha='center');ax.text(5,126,'会话重建',ha='center');ax.legend(loc='upper center',bbox_to_anchor=(.5,1.18),ncol=2,frameon=False,fontsize=8)
ax.tick_params(axis='x',labelsize=8);ax.set_axisbelow(True);ax.grid(axis='y',color='.85',linewidth=.5);f.subplots_adjust(left=.22,right=.99,bottom=.14,top=.85);save(f,2)
# Increment and uncertainty, exact original reported intervals
f,ax=plt.subplots(figsize=(69*mm,50*mm));m=np.array([3.83,6.87]);lo=np.array([-.41,2.82]);hi=np.array([8.39,10.69]);y=[1,0]
for j,c in enumerate([BLUE,GREEN]): ax.errorbar(m[j],y[j],xerr=[[m[j]-lo[j]],[hi[j]-m[j]]],fmt='o',color=c,capsize=3,markersize=3)
ax.axvline(0,color='.5',ls='--',lw=.7)
ax.set(yticks=y,yticklabels=['重复出示\n15/30块改善','会话重建\n21/30块改善'],xlim=(-2,12),ylim=(-.65,1.65),xticks=[0,5,10],xlabel='填充→紧致的出示均值降幅 / %')
for yy,mm0,l,h in zip(y,m,lo,hi):ax.text(5,yy+.28,f'{mm0:.2f}% [{l:.2f}, {h:.2f}]',ha='center',fontsize=8)
f.subplots_adjust(left=.34,right=.98,bottom=.27,top=.96);save(f,3)
plt.rcParams.update({'font.family':fontname,'font.size':7.5,'axes.unicode_minus':False,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'path','lines.linewidth':.9})
rows=list(csv.DictReader((ROOT/'data/derived/reuse.csv').open()))
cx,cy=2484000,2159204
from matplotlib.ticker import NullFormatter
variants=['B1','V0','V1','G3','C3'];colors=['#333333','#999999','#984ea3','#0072B2','#009E73'];styles=['o-','s--','^-.','D-','v--'];labels=['修正基线','复用组合','双层复用','填充优化','紧致优化']
f,ax=plt.subplots(figsize=(cx/914400,cy/914400));audit=[]
for v,col,sty,lab in zip(variants,colors,styles,labels):
 ns=sorted({int(r['N']) for r in rows if r['variant']==v});assert ns==[1,2,4,8,16,32,64,128,256]
 samples=[[float(r['amortized_local_service_ms']) for r in rows if r['variant']==v and int(r['N'])==n] for n in ns];assert all(len(vs)==3 for vs in samples)
 y=np.array([np.mean(vs) for vs in samples]);lo=np.array([min(vs) for vs in samples]);hi=np.array([max(vs) for vs in samples])
 ax.fill_between(ns,lo,hi,color=col,alpha=.1)
 ax.errorbar(ns,y,yerr=[y-lo,hi-y],fmt=sty,markersize=2.6,capsize=1.6,color=col,label=lab,lw=.85)
 audit.append({'variant':v,'N':ns,'mean':y.tolist(),'min':lo.tolist(),'max':hi.tolist()})
ax.set_xscale('log',base=2);ax.set_xticks([1,4,16,64,256],['1','4','16','64','256']);ax.xaxis.set_minor_formatter(NullFormatter())
ax.set(xlim=(.8,320),ylim=(55,200),xlabel='每个对象出示次数 N',ylabel='本地服务摊销耗时 / ms',yticks=[60,90,120,150,180]);ax.tick_params(labelsize=7)
ax.set_axisbelow(True);ax.grid(alpha=.22,linewidth=.5)
ax.legend(loc='lower center',bbox_to_anchor=(.51,1.005),ncol=2,frameon=False,fontsize=7.1,columnspacing=.8,handlelength=1.5,handletextpad=.4,labelspacing=.3,borderaxespad=0)
f.subplots_adjust(left=.23,right=.98,bottom=.21,top=.74)
save(f,4)
plt.rcParams.update({'font.size':8.5,'lines.linewidth':1})
# All disclosure counts, current supplementary table S6.
plt.rcParams['lines.linewidth']=1
a=np.array([29114.33,29116.03,29113.17,29118.77,29116.57,29114.30,29118,29123.73,29118.70]);b=np.array([29113.83,28911.77,28707.57,28497.03,28285.90,28079.57,27870,27663.97,27460.07]);amin=np.array([29094,29081,29069,29086,29081,29084,29074,29102,29072]);amax=np.array([29149,29154,29146,29151,29155,29140,29159,29154,29149]);bmin=np.array([29081,28882,28664,28464,28255,28045,27828,27635,27436]);bmax=np.array([29154,28944,28745,28522,28339,28107,27901,27706,27495])
f,ax=plt.subplots(figsize=(69*mm,53*mm))
for v,l,h,style,label,c in [(a,amin,amax,'o-','填充',BLUE),(b,bmin,bmax,'s--','紧致',GREEN)]:ax.errorbar(range(9),v/1000,yerr=[(v-l)/1000,(h-v)/1000],fmt=style,color=c,markersize=2.5,capsize=2,label=label)
ax.set(xlabel='披露属性数 k',ylabel='证明大小 / KB',xticks=range(9),ylim=(27.3,29.35));ax.legend(frameon=False,fontsize=8,loc='lower left');ax.grid(color='.87',lw=.5);f.subplots_adjust(left=.25,right=.98,bottom=.23,top=.98);save(f,5)
print('5 figures generated from existing values')
