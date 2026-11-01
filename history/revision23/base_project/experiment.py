#!/usr/bin/env python3
"""Crash-isolated experimental baseline orchestrator. Standard-library only."""
import argparse, csv, hashlib, html, json, math, os, platform, random, statistics, subprocess, sys, time, uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CASES = ['raw_honest', 'raw_repeat_same_proof', 'raw_changed_public_attribute', 'raw_wrong_issuer', 'raw_bitflip', 'raw_wrong_disclosure', 'raw_trailing', 'raw_hidden_slot_injection', 'p1_bitflip']


def stats(xs):
    xs = sorted(xs)
    n = len(xs)
    if not n:
        return None
    mean = statistics.mean(xs)
    sd = statistics.stdev(xs) if n > 1 else 0
    return {
        'n': n, 'mean': mean, 'median': statistics.median(xs), 'min': xs[0], 'max': xs[-1], 'stddev': sd,
        'p95_nearest_rank': xs[math.ceil(.95 * n) - 1],
        'p99_nearest_rank': xs[math.ceil(.99 * n) - 1] if n >= 100 else None,
        'mean_95ci_normal_approx': [mean - 1.96 * sd / math.sqrt(n), mean + 1.96 * sd / math.sqrt(n)] if n >= 30 else None,
    }


def dump_csv(path, rows):
    if not rows:
        return
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: json.dumps(v, sort_keys=True) if isinstance(v, (dict, list)) else v for k, v in r.items()})


def process(args, path, timeout):
    with path.open('w') as f:
        try:
            p = subprocess.run([sys.executable, str(ROOT / 'experiment_worker.py'), *args], stdout=f, stderr=subprocess.PIPE, text=True, timeout=timeout)
        except subprocess.TimeoutExpired as e:
            (path.with_suffix('.stderr')).write_text(str(e))
            return {'returncode': None, 'status': 'TIMEOUT'}
    (path.with_suffix('.stderr')).write_text(p.stderr)
    return {'returncode': p.returncode, 'status': 'EXIT_OK' if p.returncode == 0 else ('NATIVE_CRASH' if p.returncode < 0 else 'WORKER_ERROR')}


def read_events(path):
    out = []
    for line in path.read_text().splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            pass
    return out


def build_fingerprint():
    """Record SHA-256 of loaded native binaries, CFFI extensions, and critical source files."""
    fp = {'sources': {}, 'binaries': {}}
    for rel in [
        'lazer/src/lin-proofs.c', 'lazer/src/lnp-quad.c', 'lazer/src/poly.c',
        'lazer/src/rejection.c', 'lazer/src/blindsig.c', 'lazer/src/lazer.c',
        'lazer/python/lazer.py', 'lazer/python/anon_cred/anon_cred.py',
        'lazer/python/anon_cred/anon_cred_params.h',
    ]:
        p = ROOT / rel
        if p.is_file():
            fp['sources'][rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    for bpath in [
        ROOT / 'lazer/liblazer.so',
        ROOT / 'lazer/liblazer.a',
        *sorted((ROOT / 'lazer/python').glob('_lazer_cffi*.so')),
        *sorted((ROOT / 'lazer/python/anon_cred').glob('_anon_cred_params_cffi*.so')),
    ]:
        if bpath.is_file():
            fp['binaries'][str(bpath.relative_to(ROOT))] = hashlib.sha256(bpath.read_bytes()).hexdigest()
    return fp


def environment():
    cpu = Path('/proc/cpuinfo').read_text()
    model = next((l.split(':', 1)[1].strip() for l in cpu.splitlines() if l.startswith('model name')), 'unknown')
    return {
        'utc': datetime.now(timezone.utc).isoformat(),
        'platform': platform.platform(),
        'python': sys.version,
        'cpu_model': model,
        'cpu_affinity': sorted(os.sched_getaffinity(0)),
        'cpu_profile': (ROOT / 'logs/cpu_build_profile.txt').read_text() if (ROOT / 'logs/cpu_build_profile.txt').exists() else 'UNKNOWN',
        'governors': {str(p): p.read_text().strip() for p in Path('/sys/devices/system/cpu').glob('cpu*/cpufreq/scaling_governor')},
        'measurement_scope': 'wall/per-process CPU time; no network; peak RSS is cumulative child process high-water including import and setup',
    }


def write_report(out, summary, security):
    vinfo = summary.get('variant') or {}
    vid = vinfo.get('active_variant', 'V0').upper()
    vcode = vinfo.get('variant_code', 'V0_google_base')
    vlabel = f"；当前变体：{vid} ({vcode})" if vinfo else ""
    p2_shape = security.get('credential_relation', {}).get('P2_relation_shape', [8, 48])
    scope_desc = (
        "本报告运行 V5 披露参数化子空间投影变体（k=3 时启用 p2_compact3_param，P2 矩阵 8×45，见证维度 m1=45，二进制证明维度 nbin=13）。"
        if vid == 'V5' else
        "本报告运行 B0 纯净原装基线（仅含计数探针，不含任何代码修复或算子优化，P2 矩阵 8×48）。"
        if vid == 'B0' else
        f"本报告运行 {vid} 变体（保持原协议 8×24 / 8×48 矩阵维度、参数头与证明分布不变）。"
    )
    lines = [
        f'# 实验评测报告（{vid}: {vcode}）', '',
        f"机器：{summary['environment']['cpu_model']}；状态：{summary['status']}{vlabel}", '',
        scope_desc, '',
        '| 负载 | 接受/计划 | 生成均值 ms | 验证均值 ms | P95总时间 ms | 证明 B | 进程峰值RSS MiB |',
        '|---|---:|---:|---:|---:|---:|---:|',
    ]
    for name, g in summary['groups'].items():
        def val(k, s='mean'):
            x = g['metrics'].get(k)
            return f'{x[s]:.2f}' if x and x.get(s) is not None else '未测'
        lines.append(f"| {name} | {g['accepted']}/{g['planned']} | {val('p2_prove_ms')} | {val('p2_verify_ms')} | {val('show_flow_ms','p95_nearest_rank')} | {val('presentation_proof_bytes')} | {g['process_peak_rss_kib']/1024:.2f} |")
    lines += [
        '', '时间不含网络；签发、初始化、CPU time、重试次数详见CSV/JSON。fresh每次重新签发，steady一次签发多次出示。RSS是子进程生命周期峰值。', '',
        '## 安全参数配置与重算指标', '',
        '上游生成器目标：128位。条件性安全声明仍依赖原方案假设和分析。', '',
        '| 项目 | P1 | P2 |', '|---|---|---|',
    ]
    p1, p2 = security['proofs']
    for key, label in [
        ('proof_degree', '证明环次数'),
        ('proof_modulus', '证明内部模数'),
        ('m1_secret_polys', '秘密见证多项式维数 m1'),
        ('binary_polys', '二进制证明多项式维数 nbin'),
        ('knowledge_error_log2_upstream', '原知识错误上界log2'),
        ('MSIS_rhf_original', 'MSIS根Hermite因子(5位)'),
        ('MSIS_rhf_recomputed', 'MSIS根Hermite因子(7位精确)'),
        ('MLWE_rhf_original', 'MLWE根Hermite因子'),
        ('theoretical_repetition_rate_original', '理论重复率'),
    ]:
        lines.append(f"| {label} | {p1.get(key)} | {p2.get(key)} |")
    lines += [
        '', f'关系环次数64、模数12289，P1矩阵8×24，当前变体 P2 矩阵 {p2_shape[0]}×{p2_shape[1]}；披露下标[0,4,5]。', '',
        '## 性能指标完整性', '',
        '| 负载 | 合法失败/已完成 | 未完成/计划 | 出示超预算/已完成 | 预算内接受/计划 |', '|---|---|---|---|---|',
    ]
    for name, g in summary['groups'].items():
        lines.append(f"| {name} | {g['honest_failed']}/{g['completed']} | {g['uncompleted']}/{g['planned']} | {g['deadline_exceeded_count']}/{g['completed']} | {g['deadline_successes']}/{g['planned']} |")
    lines += [
        '', '预算按出示生成+验证的实测墙钟时间事后判断，不中断或修改原协议；进程超时单列。详细统计见performance_metrics.csv、retry_metrics.csv和setup_metrics.csv。', '',
        '## 六类安全指标', '',
        '完整结果见security/SECURITY_METRICS_ZH.md；attack_costs.csv输出声明攻击范围下的经典/量子Core-SVP估计；security_properties.csv记录不可伪造性、匿名性、知识可靠性与零知识的原始依据和适用边界。', '',
        '## 原API预期行为检查', '',
        '| 用例 | 预期 | 实际 | 符合预期 |', '|---|---|---|---|',
    ]
    for row in summary['attacks']:
        lines.append(f"| {row['case']} | {row['expected']} | {row['actual']} | {row['passed']} |")
    lines += [
        '', '重复提交、证明后追加字节、未披露槽位内容被忽略，按原API默认行为记录（在 B1 及 V0..V5 中可通过 verifier.verify(..., strict=True) 开启严格拦截）。', '',
        '默认安全成本采用固定的通用GSA/Core-SVP模型；08_security_sage.sh提供另行运行完整Sage估计器的入口。', '',
        '本次测试是实现证据，不会产生新的密码学证明。',
    ]
    text = '\n'.join(lines) + '\n'
    (out / 'CURRENT_BASELINE_ZH.md').write_text(text)
    (out / 'report.html').write_text('<html lang="zh"><meta charset="utf-8"><title>实验报告</title><style>body{max-width:1100px;margin:30px auto;padding:20px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:16px/1.6 sans-serif}</style><pre>' + html.escape(text) + '</pre></html>')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=['smoke', 'pilot', 'full'], default='smoke')
    ap.add_argument('--sessions', type=int)
    ap.add_argument('--warmup', type=int)
    ap.add_argument('--cpu', type=int)
    ap.add_argument('--deadline-ms', type=float, default=250)
    ap.add_argument('--attacks-only', action='store_true')
    a = ap.parse_args()
    n = a.sessions if a.sessions is not None else {'smoke': 3, 'pilot': 30, 'full': 1000}[a.mode]
    warm = a.warmup if a.warmup is not None else (0 if a.mode == 'smoke' else 2)
    if not 1 <= n <= 100000 or not 0 <= warm <= 100 or a.deadline_ms <= 0:
        ap.error('sessions 1..100000; warmup 0..100; deadline must be positive')
    if a.cpu is not None:
        os.sched_setaffinity(0, {a.cpu})
    subprocess.run([sys.executable, str(ROOT / 'verify_baseline.py')], check=True)
    vinfo = json.loads((ROOT / 'ACTIVE_VARIANT.json').read_text()) if (ROOT / 'ACTIVE_VARIANT.json').exists() else {'active_variant': 'V0', 'variant_code': 'V0_google_base'}
    vtag = vinfo.get('active_variant', 'V0')
    prefix = 'attacks' if a.attacks_only else f'metrics_{a.mode}_{vtag}'
    out = ROOT / 'results' / f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    out.mkdir(parents=True)
    (out / 'workers').mkdir()
    subprocess.run([sys.executable, str(ROOT / 'security_audit.py'), '--output', str(out / 'security')], check=True)
    sec = json.loads((out / 'security/security.json').read_text())
    summary = {
        'schema_version': 4,
        'baseline_name': 'lazer基线-指标版 (E2)',
        'baseline_id': 'LAZER-ORIGINAL-METRICS-1.0-20261014',
        'variant': vinfo,
        'build_fingerprint': build_fingerprint(),
        'mode': a.mode,
        'attacks_only': bool(a.attacks_only),
        'environment': environment(),
        'deadline_ms': a.deadline_ms,
        'deadline_semantics': 'post-hoc show prove+verify wall time; no hard per-session interruption',
        'groups': {},
        'attacks': [],
        'status': 'RUNNING',
    }
    allsamples = []
    groups = [('raw', l) for l in ['fresh', 'steady']]
    random.Random(20261014).shuffle(groups)
    for profile, life in ([] if a.attacks_only else groups):
        name = profile + '_' + life
        path = out / 'workers' / f'{name}.jsonl'
        result = process(['--task', 'benchmark', '--profile', profile, '--lifecycle', life, '--sessions', str(n), '--warmup', str(warm), '--deadline-ms', str(a.deadline_ms)], path, max(90, (n + warm) * 10))
        events = read_events(path)
        samples = [e for e in events if e.get('event') == 'sample' and not e['warmup']]
        successes = [s for s in samples if s['status'] == 'HONEST_ACCEPTED']
        metrics = {}
        if successes:
            keys = {k for s in successes for k, v in s.items() if isinstance(v, (int, float)) and not isinstance(v, bool) and k not in ['index']}
            metrics = {k: stats([s[k] for s in successes if k in s]) for k in sorted(keys)}
        counterkeys = {k for s in successes for k in s['p2_counters']}
        fastpath_totals = {
            'p2_rej_fastpath_decisions_total': sum((s.get('p2_fastpath') or {}).get('rej_fastpath_decisions', 0) for s in successes),
            'p2_rej_mpfr_fallbacks_total': sum((s.get('p2_fastpath') or {}).get('rej_mpfr_fallbacks', 0) for s in successes),
        }
        g = {
            'planned': n, 'completed': len(samples), 'accepted': len(successes),
            'honest_failed': len(samples) - len(successes), 'uncompleted': n - len(samples),
            'worker': result, 'metrics_conditional_on_success': True, 'metrics': metrics,
            'p2_counters': {k: stats([s['p2_counters'][k] for s in successes]) for k in sorted(counterkeys)},
            'fastpath_accounting': fastpath_totals,
            'setup': [e for e in events if e.get('event') == 'setup'],
            'process_peak_rss_kib': max([e.get('process_peak_rss_kib', 0) for e in events] or [0]),
            'deadline_successes': sum(not s['deadline_exceeded'] for s in successes),
            'failure_probability_95_upper_if_zero_and_iid': 1 - .05 ** (1 / n) if len(successes) == n else None,
        }
        g.update(
            honest_failure_rate_observed=g['honest_failed'] / g['completed'] if g['completed'] else None,
            uncompleted_rate=g['uncompleted'] / n,
            deadline_exceeded_count=sum(s['deadline_exceeded'] for s in samples),
            deadline_success_rate_planned=g['deadline_successes'] / n,
            worker_timeout=result['status'] == 'TIMEOUT',
            metrics_all_completed_trials={'trial_wall_ms': stats([s['trial_wall_ms'] for s in samples])},
        )
        g['retry_metrics'] = {}
        for phase in ['p1_counters', 'issue_counters', 'p2_counters']:
            values = [s[phase] for s in samples if phase in s]
            if not values and life == 'steady' and phase in setup_values(events):
                values = [setup_values(events)[phase]]
            g['retry_metrics'][phase] = {k: stats([v[k] for v in values]) for k in sorted(values[0])} if values else {}
        g['counter_accounting_passed'] = (
            all(counter_accounting(v) for s in samples for phase in ['p1_counters', 'issue_counters', 'p2_counters'] if (v := s.get(phase)))
            and all(counter_accounting(v) for phase in ['p1_counters', 'issue_counters'] if (v := setup_values(events).get(phase)))
        )
        summary['groups'][name] = g
        allsamples += samples
        print(f"{name}: {len(successes)}/{n}; worker={result['status']}", flush=True)
        (out / 'summary.json').write_text(json.dumps(summary, indent=2))
    for case in CASES:
        p = out / 'workers' / f'attack_{case}.jsonl'
        result = process(['--task', 'attack', '--case', case], p, 45)
        events = read_events(p)
        found = [e for e in events if e.get('event') == 'attack']
        row = found[-1] if found and result['status'] == 'EXIT_OK' else {'case': case, 'expected': 'CONTROLLED_RESULT', 'actual': result['status'], 'passed': False}
        summary['attacks'].append(row)
        print(f"{case}: {row['actual']} ({'PASS' if row['passed'] else 'FAIL'})", flush=True)
    summary['status'] = (
        'EXPERIMENT_CHECKS_PASSED'
        if all(g['accepted'] == n and g['worker']['status'] == 'EXIT_OK' and g['counter_accounting_passed'] for g in summary['groups'].values()) and all(t['passed'] for t in summary['attacks'])
        else 'EXPERIMENT_CHECKS_FAILED'
    )
    (out / 'summary.json').write_text(json.dumps(summary, indent=2))
    dump_csv(out / 'samples.csv', allsamples)
    dump_csv(out / 'attacks.csv', summary['attacks'])
    write_report(out, summary, sec)
    export_metrics(out, summary)
    if a.attacks_only:
        (ROOT / 'results/LATEST_ATTACKS_ONLY.txt').write_text(str(out.relative_to(ROOT)) + '\n')
        (ROOT / f'results/LATEST_ATTACKS_{vtag}.txt').write_text(str(out.relative_to(ROOT)) + '\n')
    else:
        (ROOT / 'results/LATEST_METRICS.txt').write_text(str(out.relative_to(ROOT)) + '\n')
        (ROOT / f'results/LATEST_METRICS_{vtag}.txt').write_text(str(out.relative_to(ROOT)) + '\n')
    print('RESULT_DIRECTORY:', out)
    print(summary['status'])
    if summary['status'] != 'EXPERIMENT_CHECKS_PASSED':
        raise SystemExit(1)


def setup_values(events):
    return next((e.get('steady_credential_setup', {}) for e in events if e.get('event') == 'setup'), {})


def counter_accounting(c):
    return (c['range_attempts'] == 0 or c['range_attempts'] == 1 + c['range_reject_z3'] + c['range_reject_z4']) and (c['quadratic_attempts'] == 0 or c['quadratic_attempts'] == 1 + c['quadratic_reject_z1'] + c['quadratic_reject_z2'] + c['quadratic_reject_norm'])


def export_metrics(out, summary):
    perf = []
    retries = []
    setups = []
    for name, g in summary['groups'].items():
        for key, value in g['metrics'].items():
            perf.append(dict(group=name, metric=key, scope='accepted sessions; warmup excluded', **value))
        for phase, values in g['retry_metrics'].items():
            for key, value in values.items():
                retries.append(dict(group=name, phase=phase, counter=key, **value))
        for event in g['setup']:
            for key, value in event.items():
                if isinstance(value, (int, float)):
                    setups.append(dict(group=name, metric=key, value=value, scope='once per isolated workload process'))
            for key, value in event.get('steady_credential_setup', {}).items():
                if isinstance(value, (int, float)):
                    setups.append(dict(group=name, metric=key, value=value, scope='one issuance before repeated presentations'))
    dump_csv(out / 'performance_metrics.csv', perf)
    dump_csv(out / 'retry_metrics.csv', retries)
    dump_csv(out / 'setup_metrics.csv', setups)


if __name__ == '__main__':
    main()
