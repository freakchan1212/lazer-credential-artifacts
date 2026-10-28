#!/usr/bin/env python3
"""Source for the two revised manuscript schematics; no experiment values invented."""
from pathlib import Path
import argparse
import matplotlib
matplotlib.use('Agg')
from matplotlib import pyplot as plt,font_manager
from matplotlib.patches import Rectangle,FancyArrowPatch
R=Path(__file__).resolve().parent
def main():
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=R/'schematics');a=p.parse_args()
 font_manager.fontManager.addfont(str(R/'fonts/E4-CJK.otf'))
 plt.rcParams.update({'font.family':'Noto Sans CJK SC','font.size':10,'svg.fonttype':'path','pdf.fonttype':42})
 for lang in ['zh','en']:
  def t(zh,en):return zh if lang=='zh' else en
  def box(ax,x,y,w,h,title,body,color='#f3f3f3'):
   ax.add_patch(Rectangle((x,y),w,h,facecolor=color,edgecolor='#666666',lw=.8))
   ax.text(x+w/2,y+h-.13,title,ha='center',va='top',fontsize=10.5,fontweight='bold');ax.text(x+w/2,y+h/2-.04,body,ha='center',va='center',linespacing=1.6,fontsize=9.5)
  def arrow(ax,a,b):ax.add_patch(FancyArrowPatch(a,b,arrowstyle='-|>',mutation_scale=11,color='#555555',lw=.9))
  def save(fig,name):
   for ext in ['png','pdf','svg']:
    q=a.out/lang/ext/(name+'.'+ext);q.parent.mkdir(parents=True,exist_ok=True);fig.savefig(q,dpi=300,bbox_inches='tight')
   plt.close(fig)
  fig,ax=plt.subplots(figsize=(8,4.6));ax.set(xlim=(0,8),ylim=(0,4.6));ax.axis('off')
  box(ax,.2,2.8,2.25,1.4,t('静态声明','Static statement'),t('同一公钥与披露集合\n矩阵 A 及其缩放 Ds','Same issuer and disclosure set\nA and scaled Ds'))
  box(ax,2.9,2.8,2.35,1.4,t('首次准备与保存','Prepare once and retain'),t('Ds 编码前缀状态\n自同构 oDs 与 CRT 表示','SHAKE prefix after Enc(Ds)\noDs and CRT representations'),'#eaf3f8')
  box(ax,5.7,2.8,2.1,1.4,t('后续调用','Subsequent calls'),t('复制前缀状态\n复用矩阵与变换结果','Clone prefix state\nReuse transformed matrices'),'#eaf5ee')
  arrow(ax,(2.45,3.5),(2.9,3.5));arrow(ax,(5.25,3.5),(5.7,3.5))
  box(ax,5.7,.8,2.1,1.35,t('动态公开向量','Dynamic public vector'),t("编码 u′ 与终止标志\n继续吸收并生成哈希","Encode u′ and terminator\nContinue SHAKE absorption"))
  arrow(ax,(6.75,2.8),(6.75,2.15))
  box(ax,.2,.8,5.05,1.35,t('状态更新与适用边界','Update and lifetime conditions'),t('指针键查找；设置声明时重建；清除时失效\n设置接口控制更新；单线程对象生命周期','Pointer-key lookup; rebuild on setter; evict on clear\nSetter-managed updates; tested single-thread lifetime'))
  ax.text(4,.25,t('缓存点不调用 coder_enc_end；当前 d=64 保证系数编码的字节对齐','No coder_enc_end at cached prefix; d=64 gives byte-aligned coefficient encoding'),ha='center',fontsize=9)
  save(fig,'fig1_statement_lifecycle')
  fig,ax=plt.subplots(figsize=(8,3.8));ax.set(xlim=(0,8),ylim=(0,3.8));ax.axis('off')
  box(ax,.2,1.35,3.2,2.1,t('填充关系','Padded relation'),t('应用见证 48 个多项式\n已披露属性坐标填零\n二进制约束 16 个多项式\nP2 余量 Z=2，内部 m1=50','48 application witness polynomials\nDisclosed coordinates set to zero\n16 binary-constrained polynomials\nP2 slack Z=2; internal m1=50'))
  box(ax,4.6,1.35,3.2,2.1,t('紧致关系','Compact relation'),t('应用见证 48−k 个多项式\n仅保留隐藏属性列与坐标\n二进制约束 16−k 个多项式\nP2 余量 Z=2，内部 m1=50−k','48−k application witness polynomials\nKeep hidden attribute columns only\n16−k binary-constrained polynomials\nP2 slack Z=2; internal m1=50−k'),'#eaf5ee')
  arrow(ax,(3.4,2.7),(4.6,2.7));ax.text(4,2.95,t('投影','Project'),ha='center')
  arrow(ax,(4.6,1.8),(3.4,1.8));ax.text(4,1.5,t('补零','Zero-extend'),ha='center')
  ax.text(4,.85,t('同步更新矩阵列、见证顺序、范数分组与二进制约束索引','Update matrix columns, witness order, norm groups and binary indices together'),ha='center',fontsize=9.5)
  ax.text(4,.35,t('保持应用关系的见证存在性；证明参数与提取界单独核查','Preserve application witness existence; audit proof parameters and extraction bounds separately'),ha='center',fontsize=9)
  save(fig,'fig2_witness_compaction')
if __name__=='__main__':main()
