#!/usr/bin/env python3
"""Recompute from receipted raw blocks, keep all samples and all regressions."""
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
        if not b or len(a)!=len(b):raise ValueError('unbalanced blocks')
        row=dict(compiler=compiler,lifecycle=life,base=base,target=target,round=rnd,block=block,
            base_ms=mean([r['show_ms'] for r in a]),target_ms=mean([r['show_ms'] for r in b]),
            delta_K=mean([r['K'] for r in b])-mean([r['K'] for r in a]),
            delta_prove_ms=mean([r['prove_ms'] for r in b])-mean([r['prove_ms'] for r in a]),
            delta_verify_ms=mean([r['verify_ms'] for r in b])-mean([r['verify_ms'] for r in a]))
        row['reduction_pct']=100*(1-row['target_ms']/row['base_ms']);pairs.append(row)
    rounds=collections.defaultdict(list)
    for r in pairs:rounds[r['round']].append(r)
    if not pairs:raise ValueError('no pairs')
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
        K_vs_prove_difference_correlation=corr,
        note='descriptive association; no causal cache/retry attribution; CI conditional on measured batches')
    return summary,pairs

def main():
    p=argparse.ArgumentParser();p.add_argument('--batch',type=Path,required=True);a=p.parse_args();batch=a.batch.resolve()
    config=json.loads((batch/'config.json').read_text());data=[]
    for job in config['plan']:
        p=batch/'raw'/(job['id']+'.jsonl');receipt=json.loads(p.with_suffix('.receipt.json').read_text())
        if sha(p)!=receipt['sha256']:raise ValueError('raw receipt mismatch')
        rs=rows(p);check_rows(rs,job);data.extend(r for r in rs if not r['warmup'])
    groups=collections.defaultdict(list)
    for r in data:groups[r['compiler'],r['variant'],r['lifecycle']].append(r)
    summary=[]
    for (c,v,l),rs in sorted(groups.items()):
        x=dict(compiler=c,variant=v,lifecycle=l,n=len(rs))
        for k in ['prove_ms','verify_ms','show_ms','proof_bytes','K']:
            x[k+'_mean']=mean([r[k] for r in rs])
        x.update(show_ms_median=statistics.median(r['show_ms'] for r in rs),
                 show_ms_p95=percentile([r['show_ms'] for r in rs],.95),
                 process_peak_rss_MiB=max(r['rss_kib'] for r in rs)/1024,
                 comparison_scope='native configuration reference, not equal-security speedup' if v=='PQZK_BLNS' else 'within-LaZer same task/parameters except compact dimensions')
        summary.append(x)
    effects=[];blocks=[]
    for c in ['gcc','clang']:
        for life in ['steady','fresh']:
            for base,target in [('B1','G3'),('B1','C3'),('G3','C3')]:
                s,b=block_effects(data,c,life,base,target);effects.append(s);blocks+=b
    out=batch/'derived';csvwrite(out/'summary.csv',summary);csvwrite(out/'effects.csv',effects)
    csvwrite(out/'blocks.csv',blocks);csvwrite(out/'samples.csv',data)
    lines=['# 本轮补实验结果','',f'模式：{config["mode"]}；正式会话：{len(data)}。',
        'smoke/pilot只用于流程和小样本检查；论文补实验使用预先确定的full。',
        '现有论文旧批次不并入本轮统计。所有区间均条件于本轮批次；不删除负收益块。','',
        '|编译器|实现|生命周期|n|生成/ms|验证/ms|合计/ms|证明/B|进程峰值/MiB|',
        '|---|---|---|---:|---:|---:|---:|---:|---:|']
    for r in summary:lines.append(f'|{r["compiler"]}|{r["variant"]}|{r["lifecycle"]}|{r["n"]}|{r["prove_ms_mean"]:.3f}|{r["verify_ms_mean"]:.3f}|{r["show_ms_mean"]:.3f}|{r["proof_bytes_mean"]:.2f}|{r["process_peak_rss_MiB"]:.2f}|')
    lines+=['','## 分块收益','', '|编译器|生命周期|比较|均值降幅/%|95%区间/%|改善块|','|---|---|---|---:|---|---|']
    for r in effects:lines.append(f'|{r["compiler"]}|{r["lifecycle"]}|{r["base"]}→{r["target"]}|{r["reduction_pct"]:.2f}|[{r["bootstrap_low_pct"]:.2f}, {r["bootstrap_high_pct"]:.2f}]|{r["improved_blocks"]}/{r["blocks"]}|')
    lines+=['','## 外部对照边界','',
        'PQZK_BLNS为独立C++实现的8属性任务适配，原生参数、安全估计、属性编码和nonce绑定不同。',
        '这里只提供同机配置参照，不自动计算跨实现倍率，也不声称已达到审稿要求的完全相同参数。',
        '两端分别使用原生验证；LaZer strict与外部验证接口的恶意输入覆盖不相同。',
        '证明大小仅计证明序列化字节，不含披露属性、公钥、策略或nonce。',
        'RSS为进程生命周期累计峰值，包含运行时、签发、初始化及预热，不是证明器增量内存。',
        '重试计数的定义在两套实现中可能不同，不能跨实现比较K。',
        '正式宣称同安全级别直接比较前，仍须核对完整安全估计及功能边界。']
    (out/'RESULTS_ZH.md').write_text('\n'.join(lines)+'\n')
    dump(out/'integrity.json',dict(raw_tasks=len(config['plan']),formal_sessions=len(data),status='PASSED'))

if __name__=='__main__':main()
