#!/usr/bin/env python3
"""Fail closed if any frozen metric disappears or summary disagrees with samples."""
import argparse, csv, hashlib, json, math, statistics, subprocess, sys
from pathlib import Path

R = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--result', type=Path)
    a = ap.parse_args()
    out = a.result or R / (R / 'results/LATEST_METRICS.txt').read_text().strip()
    if not out.is_absolute():
        out = R / out
    subprocess.run([sys.executable, str(R / 'verify_baseline.py')], check=True)
    s = json.loads((out / 'summary.json').read_text())
    contract = json.loads((R / 'metric_contract.json').read_text())
    checks = []

    def require(ok, name):
        checks.append({'check': name, 'passed': bool(ok)})

    require(s['baseline_id'] == contract['baseline_id'], 'frozen identity')
    require(set(s['groups']) == set(contract['workloads']), 'both original-protocol workloads present')
    require(s['status'] == 'EXPERIMENT_CHECKS_PASSED', 'all honest/API checks successful')
    samples = list(csv.DictReader((out / 'samples.csv').open()))
    for name, g in s['groups'].items():
        rows = [r for r in samples if r['profile'] + '_' + r['lifecycle'] == name and r['warmup'] == 'False']
        require(len(rows) == g['completed'] == g['planned'] == g['accepted'], name + ': complete honest samples')
        require(g['counter_accounting_passed'], name + ': rejection count identities')
        require(g['process_peak_rss_kib'] > 0, name + ': lifetime peak RSS recorded')
        for key, stat in g['metrics'].items():
            vals = [float(r[key]) for r in rows if r.get(key) not in [None, '']]
            if vals:
                expected = sorted(vals)[math.ceil(.95 * len(vals)) - 1]
                require(
                    stat['n'] == len(vals)
                    and math.isclose(stat['mean'], statistics.mean(vals), rel_tol=1e-10, abs_tol=1e-8)
                    and math.isclose(stat['median'], statistics.median(vals), rel_tol=1e-10, abs_tol=1e-8)
                    and math.isclose(stat['p95_nearest_rank'], expected, rel_tol=1e-10, abs_tol=1e-8),
                    name + ': independently recompute ' + key,
                )
        for item in contract['performance'][:3]:
            for key in item['fields']:
                require(key in g['metrics'], name + ': ' + item['id'] + ' ' + key)
        setup = g['setup'][0]
        credential = setup['steady_credential_setup']
        for item in contract['performance'][3:5]:
            for key in item['fields']:
                require(key in (g['metrics'] if name.endswith('fresh') else credential), name + ': ' + item['id'] + ' ' + key)
        require(
            set(g['retry_metrics']) == set(contract['performance'][6]['counter_phases'])
            and all(len(v) == 8 for v in g['retry_metrics'].values()),
            name + ': all three phases and eight counters',
        )
        require(all(key in g for key in contract['performance'][6]['fields']), name + ': failure/deadline/worker timeout denominators')
        require(setup['module_import_and_public_parameter_expansion_ms'] > 0 and setup['keygen_ms'] > 0, name + ': import and keygen separate')
        require(len({r['proof_sha256'] for r in rows}) == len(rows), name + ': no duplicate presentation proof observed')
    sec = json.loads((out / 'security/security_metrics.json').read_text())
    require([p['id'] for p in sec['properties']] == contract['security_ids'], 'all six security dimensions and explicit evidence/limits')
    require(len(sec['attack_rows']) == 5 and all(0 < x['quantum_log2_cost'] < x['classical_log2_cost'] for x in sec['attack_rows']), 'classical/quantum declared attack models computed')
    require(len(sec.get('assumption_coverage', [])) == 7, 'all related proof/commitment/auxiliary-preimage/FS assumptions explicitly mapped')
    require(all(x['minus_log2_epsilon'] >= x['header_minus_log2_bound'] for x in sec['knowledge_bounds']), 'knowledge-error formula agrees with upstream conservative bound')
    active_vid = (s.get('variant') or {}).get('active_variant', sec.get('active_variant', 'V0')).upper()
    expected_param_changed = (active_vid == 'V5')
    require(sec['protocol_parameters_changed'] == expected_param_changed and not sec['numeric_protocol_security_certified'], 'original parameters and honest security scope')
    require(len(s['attacks']) == 9 and all(t['passed'] for t in s['attacks']), 'nine original API behavior controls')
    require(len(sec.get('sampling_metadata', [])) == 2 and all(len(p['reported_standard_deviations']) == 4 and len(p['reported_rejection_factors']) == 4 for p in sec.get('sampling_metadata', [])), 'both proof samplers and original rejection factors recorded')
    for name in ['performance_metrics.csv', 'retry_metrics.csv', 'setup_metrics.csv', 'attacks.csv', 'CURRENT_BASELINE_ZH.md', 'report.html', 'security/attack_costs.csv', 'security/security_properties.csv', 'security/assumption_coverage.csv', 'security/knowledge_bounds.json', 'security/sampling_metadata.json', 'security/SECURITY_METRICS_ZH.md']:
        require((out / name).is_file() and (out / name).stat().st_size > 0, 'output ' + name)
    result = {
        'status': 'FROZEN_METRICS_ACCEPTANCE_PASSED' if all(c['passed'] for c in checks) else 'FROZEN_METRICS_ACCEPTANCE_FAILED',
        'active_variant': active_vid,
        'checks': checks,
        'scope': 'metric collection and variant-accurate security metadata; no new cryptographic theorem',
    }
    (out / 'acceptance.json').write_text(json.dumps(result, indent=2) + '\n')
    print(result['status'], f"{sum(c['passed'] for c in checks)}/{len(checks)}")
    if result['status'].endswith('FAILED'):
        print([c['check'] for c in checks if not c['passed']])
        raise SystemExit(1)


if __name__ == '__main__':
    main()
