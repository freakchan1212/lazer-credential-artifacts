#!/usr/bin/env python3
"""Independent read-only recomputation of the current 7,800-session batch."""
import argparse,collections,csv,hashlib,json,math,random,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def readcsv(p):return list(csv.DictReader(p.open()))
def writecsv(p,rows):
    with p.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def close(a,b):assert math.isclose(float(a),float(b),rel_tol=1e-10,abs_tol=1e-7),(a,b)
def recompute(output):
    out=Path(output).resolve()
    if out==ROOT or ROOT in out.parents:raise ValueError('Choose output outside frozen package')
    out.mkdir(parents=True,exist_ok=True)
    folder=ROOT/'comparison_data/full';cfg=json.loads((folder/'config.json').read_text());groups=collections.defaultdict(list);raw=[]
    for job in cfg['plan']:
        p=folder/'raw'/(job['id']+'.jsonl');receipt=json.loads(p.with_suffix('.receipt.json').read_text());spec=folder/'specs'/(job['id']+'.json')
        assert sha(p)==receipt['sha256'] and sha(spec)==receipt['spec_sha256']
        rs=[json.loads(x) for x in p.read_text().splitlines()];assert len(rs)==receipt['rows']==job['sessions']+job['warmup']
        for r in rs:
            assert r['status']=='ACCEPTED'
            if r['warmup']:continue
            for k in ['compiler','variant','lifecycle','round','block']:assert r[k]==job[k]
            close(r['show_ms'],r['prove_ms']+r['verify_ms'])
            groups[r['compiler'],r['variant'],r['lifecycle']].append(r);raw.append(r)
    assert len(raw)==7800 and len(groups)==26 and all(len(x)==300 for x in groups.values())
    recomputed=[]
    for saved in readcsv(folder/'derived/summary.csv'):
        rs=groups[saved['compiler'],saved['variant'],saved['lifecycle']]
        row={k:saved[k] for k in ['compiler','variant','lifecycle']};row['n']=len(rs)
        for k in ['prove_ms','verify_ms','show_ms','proof_bytes','K']:
            row[k+'_mean']=statistics.mean(r[k] for r in rs);close(row[k+'_mean'],saved[k+'_mean'])
        row['process_peak_rss_MiB']=max(r['rss_kib'] for r in rs)/1024;close(row['process_peak_rss_MiB'],saved['process_peak_rss_MiB']);recomputed.append(row)
    blocks=collections.defaultdict(list)
    for r in raw:blocks[r['compiler'],r['lifecycle'],r['variant'],r['round'],r['block']].append(r)
    effects=[]
    for saved in readcsv(folder/'derived/effects.csv'):
        c,l,a,b=(saved[k] for k in ['compiler','lifecycle','base','target']);pairs=[]
        for rnd,blk in sorted({(r['round'],r['block']) for r in groups[c,a,l]}):
            av=statistics.mean(r['show_ms'] for r in blocks[c,l,a,rnd,blk]);bv=statistics.mean(r['show_ms'] for r in blocks[c,l,b,rnd,blk]);pairs.append((rnd,av,bv))
        strata=[[x for x in pairs if x[0]==rnd] for rnd in sorted({x[0] for x in pairs})]
        rng=random.Random(20261030);boot=[]
        for _ in range(25000):
            draws=[rng.choice(s) for s in strata for _ in range(len(s))]
            boot.append(100*(1-sum(x[2] for x in draws)/sum(x[1] for x in draws)))
        boot.sort();result=dict(compiler=c,lifecycle=l,base=a,target=b,reduction_pct=100*(1-sum(x[2] for x in pairs)/sum(x[1] for x in pairs)),bootstrap_low_pct=boot[math.ceil(.025*len(boot))-1],bootstrap_high_pct=boot[math.ceil(.975*len(boot))-1],improved_blocks=sum(x[2]<x[1] for x in pairs),blocks=len(pairs))
        for key in ['reduction_pct','bootstrap_low_pct','bootstrap_high_pct','improved_blocks']:close(result[key],saved[key])
        effects.append(result)
    writecsv(out/'summary_recomputed.csv',recomputed);writecsv(out/'effects_recomputed.csv',effects)
    result=dict(status='PASSED',formal_samples=7800,conditions=26,jobs=len(cfg['plan']),samples_per_condition=300,summary_groups_checked=len(recomputed),effects_checked=len(effects),bootstrap_repetitions=25000,strict_same_parameter_security_equivalence_established=False)
    (out/'CHECK.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False,indent=2));return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();recompute(a.output)

