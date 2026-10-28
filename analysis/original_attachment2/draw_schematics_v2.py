"""按V2正文图1、图2及真实源码重绘，不生成实验数据。"""
import argparse
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
from matplotlib import pyplot as plt
from matplotlib.patches import Rectangle,FancyArrowPatch
from paper_fonts import configure,validate_text
R=Path(__file__).resolve().parent.parent

def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=R);a=p.parse_args();configure('zh')
 def save(fig,name):
  validate_text(fig,'zh')
  for ext in ['svg','pdf','png']:
   d=a.output/ext.upper();d.mkdir(parents=True,exist_ok=True);fig.savefig(d/(name+'.'+ext),dpi=400,bbox_inches='tight')
  plt.close(fig)
 def box(ax,x,y,w,h,title,body,color):
  ax.add_patch(Rectangle((x,y),w,h,facecolor=color,edgecolor='#777777',lw=.8))
  ax.text(x+w/2,y+h-.20,title,ha='center',va='top',fontsize=12,fontweight='bold')
  ax.plot([x+.16,x+w-.16],[y+h-.62]*2,color='#c8cccd',lw=.65)
  ax.text(x+w/2,y+h/2-.18,body,ha='center',va='center',linespacing=1.65,fontsize=10)
 def arrow(ax,p,q):ax.add_patch(FancyArrowPatch(p,q,arrowstyle='-|>',mutation_scale=10,lw=.85,color='#666666'))
 fig,ax=plt.subplots(figsize=(9.1,4.1));ax.set(xlim=(0,9.1),ylim=(0,4.1));ax.axis('off')
 xs=[.06,2.37,4.68,6.99];w=2.04;y=1.78;h=2.18
 titles=['静态声明','首次准备','后续复用','动态处理']
 bodies=['同一公钥\n同一披露集合\n固定矩阵 $A$','编码 $D_s$（不结束）\n保存 SHAKE128 前缀\n计算自同构与 CRT','复制前缀状态\n复用 $D_s$、$oD_s$\n及其 CRT 表示',"继续编码 $u'$\n写入唯一终止标志\n生成声明哈希"]
 for i,(x,t,b) in enumerate(zip(xs,titles,bodies)):box(ax,x,y,w,h,t,b,['#f6f7f7','#eff5f8','#eff5f8','#f0f6f2'][i])
 for i in range(3):arrow(ax,(xs[i]+w,y+h/2),(xs[i+1],y+h/2))
 ax.text(4.55,1.31,'状态更新与失效',ha='center',fontsize=12,fontweight='bold')
 ax.text(4.55,.96,'以 $D_s$ 指针为键；设置声明时重建，清理对象时失效。',ha='center',fontsize=10)
 ax.text(4.55,.60,'矩阵及相关元数据保持不变；通过受支持接口更新，限单线程。',ha='center',fontsize=10)
 ax.text(4.55,.24,'前缀保存点不写终止标志；$d=64$ 保证系数编码的字节对齐。',ha='center',fontsize=10)
 save(fig,'fig1_statement_lifecycle')
 fig,ax=plt.subplots(figsize=(9.1,3.6));ax.set(xlim=(0,9.1),ylim=(0,3.6));ax.axis('off')
 box(ax,.08,1.15,3.64,2.32,'填充关系','应用列数 $n_{app}=48$\n公开属性对应见证坐标填零\n二进制约束：16 个多项式\n余量 $Z=2$，内部 $m_{int}=50$','#f6f7f7')
 box(ax,5.38,1.15,3.64,2.32,'紧致关系','应用列数 $n_{app}=48-k$\n仅保留隐藏属性列与坐标\n二进制约束：$16-k$ 个多项式\n余量 $Z=2$，内部 $m_{int}=50-k$','#f0f6f2')
 arrow(ax,(3.74,2.63),(5.36,2.63));ax.text(4.55,2.84,'投影',ha='center',fontsize=11)
 arrow(ax,(5.36,1.80),(3.74,1.80));ax.text(4.55,1.46,'补零',ha='center',fontsize=11)
 ax.text(4.55,.66,'同步更新矩阵列、见证顺序、范数组与二进制约束索引',ha='center',fontsize=10)
 ax.text(4.55,.22,'保持应用关系的见证存在性；证明参数与提取界单独核查',ha='center',fontsize=10)
 save(fig,'fig2_witness_compaction')
if __name__=='__main__':main()
