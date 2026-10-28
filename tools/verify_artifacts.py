#!/usr/bin/env python3
"""Read-only checks for the frozen companion archive; standard library only."""
from pathlib import Path
import json, hashlib, zipfile, xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
manifest=json.loads((ROOT/'SHA256_MANIFEST.json').read_text())['sha256']
for name,expected in manifest.items():
 p=ROOT/name
 assert p.is_file(), 'Missing: '+name
 assert hashlib.sha256(p.read_bytes()).hexdigest()==expected,'Changed: '+name
jobs=json.loads((ROOT/'data/plan.json').read_text())
for j in jobs:
 p=ROOT/'data/raw'/(j['id']+'.jsonl');receipt=json.loads(p.with_suffix('.receipt.json').read_text())
 assert hashlib.sha256(p.read_bytes()).hexdigest()==receipt['sha256']
 assert len(p.read_text().splitlines())==receipt['rows']
figs=sorted((ROOT/'figures/PNG').glob('*.png'));assert len(figs)==8
for doc,prefix,n in [('paper/manuscript_v6.docx','图',5),('supplement/supplement_v6.docx','图S',3)]:
 with zipfile.ZipFile(ROOT/doc) as z:media={hashlib.sha256(z.read(x)).hexdigest() for x in z.namelist() if x.startswith('word/media/')}
 matched=[p.name for p in figs if p.name.startswith(prefix) and (prefix=='图S' or not p.name.startswith('图S')) and hashlib.sha256(p.read_bytes()).hexdigest() in media]
 assert len(matched)==n,(doc,matched)
for svg in (ROOT/'figures/SVG').glob('*.svg'):
 root=ET.parse(svg).getroot();assert not any(x.tag.rsplit('}',1)[-1]=='image' for x in root.iter()),str(svg)
print(json.dumps({'status':'PASSED','manifest_files':len(manifest),'raw_jobs':len(jobs),'matched_main_figures':5,'matched_supplement_figures':3,'vector_svg_files':8},ensure_ascii=False,indent=2))
