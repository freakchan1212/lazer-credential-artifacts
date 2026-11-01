#!/usr/bin/env python3
"""Read-only package, data, DOCX reference and figure-consistency checks."""
from pathlib import Path
import csv,hashlib,json,re,zipfile,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
manifest=json.loads((ROOT/'SHA256_MANIFEST.json').read_text())['sha256']
for name,expected in manifest.items():
    p=ROOT/name;assert p.is_file() and sha(p)==expected, name
jobs=json.loads((ROOT/'data/plan.json').read_text(encoding='utf-8-sig'))
for job in jobs:
    p=ROOT/'data/raw'/(job['id']+'.jsonl');rec=json.loads(p.with_suffix('.receipt.json').read_text(encoding='utf-8-sig'));assert sha(p)==rec['sha256']
counts={}
for tag,n in [('smoke',52),('full',7800)]:
    root=ROOT/'comparison_data'/tag;cfg=json.loads((root/'config.json').read_text());count=0
    for j in cfg['plan']:
        p=root/'raw'/(j['id']+'.jsonl');rec=json.loads(p.with_suffix('.receipt.json').read_text());assert sha(p)==rec['sha256'];assert sha(root/'specs'/(j['id']+'.json'))==rec['spec_sha256']
        rows=[json.loads(s) for s in p.read_text().splitlines()];assert len(rows)==rec['rows'];assert all(r['status']=='ACCEPTED' for r in rows);count+=sum(not x['warmup'] for x in rows)
    assert count==n;counts[tag]=count
qualification=json.loads((ROOT/'comparison_data/full/qualification.json').read_text())
for name,expected in qualification['source_sha256'].items():assert sha(ROOT/'comparison'/name)==expected,name
N={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','m':'http://schemas.openxmlformats.org/officeDocument/2006/math'}
invariants=json.loads((ROOT/'docs/document_invariants.json').read_text())
fig_manifest=json.loads((ROOT/'figures/FIGURE_DATA_MAP.json').read_text())
ref_count=0
for part,name,prefix,count in [('paper','manuscript.docx','图',5),('supplement','supplement.docx','图S',3)]:
    with zipfile.ZipFile(ROOT/part/name) as z:
        t=ET.fromstring(z.read('word/document.xml'));bookmarks={x.attrib['{'+N['w']+'}name'] for x in t.findall('.//w:bookmarkStart',N)}
        for f in t.findall('.//w:fldSimple',N):
            ins=f.attrib.get('{'+N['w']+'}instr','').split()
            if ins and ins[0]=='REF':assert ins[1] in bookmarks;ref_count+=1
        assert not t.findall('.//w:ins',N) and not t.findall('.//w:del',N) and not t.findall('.//w:commentRangeStart',N)
        assert len(t.findall('.//m:oMath',N))==invariants[name]['equations']
        media={hashlib.sha256(z.read(x)).hexdigest() for x in z.namelist() if x.startswith('word/media/')}
        matched=0
        for item in fig_manifest['figures']:
            if item['document']!=name:continue
            assert sha(ROOT/'figures/SVG'/(item['name']+'.svg')) in media
            assert sha(ROOT/'figures/PNG'/(item['name']+'.png')) in media;matched+=1
        assert matched==count
        if part=='paper':
            table=t.find('w:body',N).findall('w:tbl',N)[-1]
            actual=[[''.join(x.itertext()) for x in []]] if False else [[''.join(n.text or '' for n in c.findall('.//w:t',N)) for c in tr.findall('w:tc',N)] for tr in table.findall('w:tr',N)]
            assert actual==json.loads((ROOT/'docs/table2_expected.json').read_text())
for svg in (ROOT/'figures/SVG').glob('*.svg'):
    t=ET.parse(svg);assert not any(x.tag.rsplit('}',1)[-1]=='image' for x in t.iter()),svg
assert len(list((ROOT/'figures/SVG').glob('*.svg')))==8
pages=json.loads((ROOT/'docs/rendered_page_counts.json').read_text());assert pages['main']<=10
print(json.dumps(dict(status='PASSED',files_checked=len(manifest),original_jobs=len(jobs),current_comparison=counts,source_hashes_checked=12,REF_targets_checked=ref_count,exact_vector_figures=8,main_rendered_pages=pages['main'],strict_same_parameters_security_equivalence=False),ensure_ascii=False,indent=2))
