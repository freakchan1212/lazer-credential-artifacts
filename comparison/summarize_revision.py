#!/usr/bin/env python3
"""Summarize qualified measurements; preserve parameter, codec and lifecycle limitations."""
import argparse, collections, csv, math, random, statistics
from revision_common import *

def csvwrite(path,data):
    if not data:return
    keys=list(dict.fromkeys(k for r in data for k in r))
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(data)

def mean(x):return statistics.mean(x)
def percentile(x,p):return sorted(x)[max(0,math.ceil(len(x)*p)-1)]

def block_effects(data,compiler,life,base,target,reps=25000):
    groups=collections.defaultdict(list)
    for r in data:
        if r['compiler']==compiler and r['lifecycle']==life and r['variant'] in [base,target]:
            groups[(r['round'],r['block'],r['variant'])].append(r)
    pairs=[]
    for rnd,block,v in sorted(groups):
        if v!=base:continue
        a=groups[rnd,block,base];b=groups[rnd,block,target]
        if not b or len(a)!=len(b):continue
        row=dict(compiler=compiler,lifecycle=life,base=base,target=target,round=rnd,block=block,
            base_ms=mean([r['show_ms'] for r in a]),target_ms=mean([r['show_ms'] for r in b]),
            delta_K=mean([r['K'] for r in b])-mean([r['K'] for r in a]),
            delta_prove_ms=mean([r['prove_ms'] for r in b])-mean([r['prove_ms'] for r in a]),
            delta_verify_ms=mean([r['verify_ms'] for r in b])-mean([r['verify_ms'] for r in a]))
        row['reduction_pct']=100*(1-row['target_ms']/row['base_ms']);pairs.append(row)
    rounds=collections.defaultdict(list)
    for r in pairs:rounds[r['round']].append(r)
    if not pairs:return None,[]
    rng=random.Random(20261030);samples=[]
    for _ in range(reps):
        drawn=[rng.choice(rs) for rs in rounds.values() for _ in rs]
        samples.append(100*(1-sum(r['target_ms'] for r in drawn)/sum(r['base_ms'] for r in drawn)))
    dx=[r['delta_K'] for r in pairs];dy=[r['delta_prove_ms'] for r in pairs]
    corr=None
    if len(dx)>1 and statistics.pstdev(dx)>0 and statistics.pstdev(dy)>0:
        corr=sum((x-mean(dx))*(y-mean(dy)) for x,y in zip(dx,dy))/math.sqrt(sum((x-mean(dx))**2 for x in dx)*sum((y-mean(dy))**2 for y in dy))
    summary=dict(compiler=compiler,lifecycle=life,base=base,target=target,blocks=len(pairs),
        reduction_pct=100*(1-sum(r['target_ms'] for r in pairs)/sum(r['base_ms'] for r in pairs)),
        bootstrap_low_pct=percentile(samples,.025),bootstrap_high_pct=percentile(samples,.975),
        improved_blocks=sum(r['reduction_pct']>0 for r in pairs),
        K_vs_prove_difference_correlation=corr)
    return summary,pairs

def main():
    p=argparse.ArgumentParser();p.add_argument('--batch',type=Path,required=True);a=p.parse_args();batch=a.batch.resolve()
    config=json.loads((batch/'config.json').read_text());data=[]
    seen_formal_proofs=set()
    for job in config['plan']:
        p=batch/'raw'/(job['id']+'.jsonl');receipt=json.loads(p.with_suffix('.receipt.json').read_text())
        if sha(p)!=receipt['sha256']:raise ValueError('raw receipt mismatch')
        rs=rows(p);check_rows(rs,job);check_proof_reuse(rs,job,seen_formal_proofs);data.extend(r for r in rs if not r['warmup'])
    groups=collections.defaultdict(list)
    for r in data:groups[r['compiler'],r['variant'],r['lifecycle']].append(r)
    summary=[]
    for (c,v,l),rs in sorted(groups.items()):
        x=dict(compiler=c,variant=v,lifecycle=l,n=len(rs),proof_size_kind=rs[0].get('proof_size_kind','lazer_native_codec'),same_parameters_cross_scheme=False,security_equivalence_established=False)
        for k in ['prove_ms','verify_ms','show_ms','proof_bytes','K']:
            x[k+'_mean']=mean([r[k] for r in rs])
        x.update(show_ms_median=statistics.median(r['show_ms'] for r in rs),
                 show_ms_p95=percentile([r['show_ms'] for r in rs],.95),
                 process_peak_rss_MiB=max(r['rss_kib'] for r in rs)/1024)
        summary.append(x)
    effects=[];blocks=[]
    candidate_pairs = [
        ('gcc', 'B1', 'G3'), ('gcc', 'B1', 'C3'), ('gcc', 'G3', 'C3'),
        ('clang', 'B1', 'G3'), ('clang', 'B1', 'C3'), ('clang', 'G3', 'C3'),
        ('gcc', 'PQZK_BLNS_PADDED', 'PQZK_BLNS_COMPACT'),
        ('gcc', 'ARGO_PADDED', 'ARGO_COMPACT'),

        ('gcc','PQZK_BLNS_PADDED_NOCACHE','PQZK_BLNS_PADDED'),
        ('gcc','ARGO_PADDED_NOCACHE','ARGO_PADDED'),

    ]
    for c, base, target in candidate_pairs:
        for life in ['steady','fresh']:
            s,b=block_effects(data,c,life,base,target)
            if s: effects.append(s); blocks+=b
    out=batch/'derived';csvwrite(out/'summary.csv',summary);csvwrite(out/'effects.csv',effects)
    csvwrite(out/'blocks.csv',blocks);csvwrite(out/'samples.csv',data)
    lines=['# 候选实现筛选及方案内优化实验结果','',f'模式：{config["mode"]}；正式会话：{len(data)}。','',
        '说明：跨方案尚未建立严格同参数、同安全等级。本表是不同配置的实测，不自动评定普遍优劣。',
        'Argo 使用新增固定宽度编码，pqzk-blns/LaZer 使用各自编码；体积差异包含编码差异。RSS 为整个进程的峰值，含初始化、签发和预热。',
        'B1→G3 包含多项工程优化；fresh→steady 还改变凭证生命周期，不能当成纯缓存收益。NOCACHE→PADDED 的 steady 组才用于同凭证缓存对照。',
        'smoke/pilot 仅为流程验证，不能代替 full 数据。Argo与pqzk-blns均使用GCC，与LaZer GCC组进行跨实现比较。',
        '',
        '|编译器/后端|方案/变体|生命周期|n|生成/ms|验证/ms|合计/ms|证明/B|进程峰值/MiB|',
        '|---|---|---|---:|---:|---:|---:|---:|---:|']
    for r in summary:
        lines.append(f'|{r["compiler"]}|{r["variant"]}|{r["lifecycle"]}|{r["n"]}|{r["prove_ms_mean"]:.3f}|{r["verify_ms_mean"]:.3f}|{r["show_ms_mean"]:.3f}|{r["proof_bytes_mean"]:.2f}|{r["process_peak_rss_MiB"]:.2f}|')
    if effects:
        lines+=['','## 方案内优化收益对比（零填充 vs 紧凑裁剪 / 状态复用）','', '|后端|生命周期|比较|均值降幅/%|95%区间/%|改善块|','|---|---|---|---:|---|---|']
        for r in effects:
            lines.append(f'|{r["compiler"]}|{r["lifecycle"]}|{r["base"]}→{r["target"]}|{r["reduction_pct"]:.2f}|[{r["bootstrap_low_pct"]:.2f}, {r["bootstrap_high_pct"]:.2f}]|{r["improved_blocks"]}/{r["blocks"]}|')
    (out/'RESULTS_ZH.md').write_text('\n'.join(lines)+'\n')
    dump(out/'integrity.json',dict(raw_tasks=len(config['plan']),formal_sessions=len(data),status='PASSED'))

if __name__=='__main__':main()
