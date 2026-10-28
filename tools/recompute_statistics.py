#!/usr/bin/env python3
"""Run the preserved independent statistics algorithm into a separate directory."""
from pathlib import Path
import argparse
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output.resolve()
if out==ROOT or ROOT in out.parents:raise SystemExit('Choose an output directory outside this frozen package.')
out.mkdir(parents=True,exist_ok=True)
source=ROOT/'analysis/original_attachment2/independent_recompute.py'
s=source.read_text();old="R=Path(__file__).resolve().parent.parent;B=R/'data';O=B/'independent_checks';O.mkdir(exist_ok=True);"
assert s.count(old)==1
s=s.replace(old,"R=ROOT;B=ROOT/'data';O=OUTPUT;O.mkdir(exist_ok=True);",1)
exec(compile(s,str(source),'exec'),{'__file__':str(source),'ROOT':ROOT,'OUTPUT':out})
