#!/usr/bin/env python3
"""Redraw the eight V6 figures without changing frozen figures or raw data."""
from pathlib import Path
import argparse, tempfile, shutil, subprocess, sys, os
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output.resolve()
if out==ROOT or ROOT in out.parents:raise SystemExit('Choose an output directory outside this frozen package.')
out.mkdir(parents=True,exist_ok=True)
subprocess.run([sys.executable,str(ROOT/'tools/redraw_main.py'),'--output',str(out)],check=True)
with tempfile.TemporaryDirectory() as td:
 stage=Path(td);shutil.copytree(ROOT/'data/derived',stage/'derived')
 subprocess.run([sys.executable,str(ROOT/'analysis/original_attachment2/plot_paper.py'),'--batch',str(ROOT/'data'),'--lang','zh','--output',str(stage)],check=True)
 names={'fig4_ols_and_block_effects':'图S1_回归与分块效果','fig5_latency_ecdf':'图S2_耗时经验分布','fig6_reuse_amortization':'图S3_完整服务摊销'}
 for old,new in names.items():
  for ext in ['svg','png']:shutil.copy2(stage/'figures/zh'/ext/(old+'.'+ext),out/ext.upper()/(new+'.'+ext))
print('V6: 8 figures, SVG + PNG; generated outputs: '+str(out))
