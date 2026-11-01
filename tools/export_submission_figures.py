#!/usr/bin/env python3
"""Copy exact manuscript vectors, vector PDFs and raster fallbacks to a new directory."""
from pathlib import Path
import argparse,shutil,json,hashlib
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output.resolve()
if out==ROOT or ROOT in out.parents:raise SystemExit('Choose an output directory outside the frozen package')
out.mkdir(parents=True,exist_ok=True)
for name in ['SVG','PDF','PNG']:shutil.copytree(ROOT/'figures'/name,out/name,dirs_exist_ok=True)
shutil.copy2(ROOT/'figures/FIGURE_DATA_MAP.json',out/'FIGURE_DATA_MAP.json')
print('Exported exact manuscript figures: 5 main + 3 supplemental, SVG/PDF/PNG')

