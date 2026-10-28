#!/usr/bin/env python3
"""Frozen, explicitly scoped security evidence (variant-aware for E2). Never writes crypto parameters."""
import argparse, csv, hashlib, json, math, re
from decimal import Decimal, localcontext
from pathlib import Path
from security_models_optional import collect as model_collect

R = Path(__file__).resolve().parent
MODEL_ID = 'ADPS16_CoreSVP_C0.292_Q0.265_no_BKZ_overhead'


def build(upstream):
    active_vid = upstream.get('active_variant', 'V0').upper()
    is_v5 = (active_vid in ['V5','C3','DC3'])
    models = model_collect()
    rows = []
    for p in models['proofs']:
        for kind in ['MSIS', 'MLWE']:
            x = p[kind]
            if kind == 'MLWE':
                rhf_val = x['header_root_hermite_factor']
                x = x['fresh_primal_usvp_gsa']
                beta = x['bkz_blocksize']
                attack = 'primal_uSVP_GSA'
            else:
                rhf_val = round(x['root_hermite_factor'], 7)
                beta = x['bkz_blocksize']
                attack = 'generic_SIS_subdimension_GSA'
            rows.append(dict(
                component=p['name'] + '_' + kind, attack=attack, n=x['n'], q=x['q'],
                root_hermite_factor_delta0=rhf_val, beta=beta,
                classical_log2_cost=.292 * beta, quantum_log2_cost=.265 * beta,
                model=MODEL_ID, evidence='HEURISTIC_GENERIC_ATTACK_ESTIMATE',
                coverage='one declared attack family; no structured or auxiliary-hint attacks',
            ))
    x = models['Falcon_NTRU_512_preimage_generic_model']
    beta = x['bkz_blocksize']
    rows.append(dict(
        component='Falcon_NTRU_preimage_generic', attack='generic_SIS_subdimension_GSA',
        n=x['n'], q=x['q'], root_hermite_factor_delta0=round(x['root_hermite_factor'], 7),
        beta=beta, classical_log2_cost=.292 * beta, quantum_log2_cost=.265 * beta,
        model=MODEL_ID, evidence='HEURISTIC_UNSTRUCTURED_PREIMAGE_PROXY',
        coverage='generic proxy only; not BLNS auxiliary-hint unforgeability',
    ))
    assumptions = [{'component': x['component'], 'numeric_evidence': x['evidence'], 'numeric_output': 'attack_costs.csv', 'scope': x['coverage']} for x in rows[:4]]
    assumptions += [
        dict(component='issuance_commitment_hiding', numeric_evidence='UPSTREAM_CONDITIONAL_ASSUMPTION_NOT_INDEPENDENTLY_ESTIMATED', numeric_output='not instantiated', scope='Ar*r+Am*m uses original Gaussian r, sigma=3.1 and norm bound 109; proof-system MLWE is not a substitute for commitment hiding'),
        dict(component='BLNS_NTRU_ISISf_auxiliary_preimages', numeric_evidence='UPSTREAM_CONDITIONAL_ASSUMPTION_WITH_GENERIC_PROXY_ONLY', numeric_output='Falcon_NTRU_preimage_generic is a proxy, not this assumption security', scope='original construction needs preimage security with auxiliary samples and extraction/reduction conditions'),
        dict(component='Fiat_Shamir_hash_and_ROM_QROM', numeric_evidence='ORIGINAL_TRANSCRIPT_RETAINED_NO_NEW_REDUCTION', numeric_output='no whole-protocol query-bound number', scope='original SHAKE128 transcript; interactive knowledge error cannot be substituted for total ROM/QROM advantage'),
    ]
    properties = [
        dict(id='S01', metric='经典攻击成本', status='MODEL_ESTIMATE', value='attack_costs.csv: classical_log2_cost', evidence='fixed inputs, generic GSA attacks, explicit Core-SVP model', limits='minimum only within declared attacks; not certified whole-protocol bits'),
        dict(id='S02', metric='量子攻击成本', status='MODEL_ESTIMATE', value='attack_costs.csv: quantum_log2_cost', evidence='separate ADPS16 quantum coefficient 0.265*beta', limits='not half of classical bits; excludes quantum algorithm overhead and structured attacks'),
        dict(id='S03', metric='不可伪造性', status='UPSTREAM_CONDITIONAL_PROPERTY', value='original BLNS-style construction retained', evidence='LaZer docs/source/anoncred.rst + BLNS 2023/560', limits='auxiliary-preimage assumption, extraction and reduction required; no independently instantiated numeric advantage/query bound'),
        dict(id='S04', metric='匿名性与不可关联性', status='UPSTREAM_CONDITIONAL_PROPERTY', value='hidden blocks [1,2,3,6,7]; disclosed blocks [0,4,5]; fresh proof randomness', evidence='original P1/P2 statements and computational simulation under header MLWE assumptions', limits='revealed attributes may identify users; no traffic anonymity or arbitrary collusion claim; unique proof hashes are only a randomness regression check'),
        dict(id='S05', metric='证明知识可靠性', status='UPSTREAM_BOUND_AND_FORMULA_RECOMPUTATION', value='P1 and P2 header epsilon <= 2^-127 under MSIS', evidence='lnp-tbox-codegen.sage eknow formula; knowledge_bounds.json', limits='interactive proof declaration; not full Fiat-Shamir/QROM advantage after hash queries/extraction losses'),
        dict(id='S06', metric='零知识误差', status='UPSTREAM_COMPUTATIONAL_SIMULATION_ASSUMPTION', value='P1 MLWE(26,29,[-1,1]); P2 MLWE(32,32,[-1,1])', evidence='original parameter header simulatability comments + unchanged sampling/rejection parameters', limits='no standalone numeric statistical-distance/full advantage bound instantiated; cannot infer from observed acceptance or KAPPA=128'),
    ]
    bounds = []
    for p, u in zip(models['proofs'], upstream['proofs']):
        q = p['proof_modulus']
        degree = p['proof_ring_degree']
        lam = 2 * math.ceil(128 / (2 * math.log2(q)))
        with localcontext() as ctx:
            ctx.prec = 90
            terms = {
                'challenge_collision': Decimal(2) ** -130,
                'ring_splitting': Decimal(q) ** (-degree // 2),
                'soundness_amplification': Decimal(q) ** (-lam),
                'range_error': Decimal(2) ** -128,
                'additional_error': Decimal(2) ** -256,
            }
            eps = float(sum(terms.values()))
            terms = {k: str(v) for k, v in terms.items()}
        bounds.append(dict(
            component=p['name'], epsilon=eps, minus_log2_epsilon=-math.log2(eps),
            header_minus_log2_bound=-u['knowledge_error_log2_upstream'],
            lambda_repetitions=lam, challenge_cardinality_log2=129,
            terms=terms, assumption=u['MSIS_original'],
            source='upstream lnp-tbox-codegen.sage eknow; prime modulus q1=q; L=2',
            scope='recomputed ideal-arithmetic expression, not whole-protocol FS security',
        ))
    hashes = {str(p.relative_to(R)): hashlib.sha256(p.read_bytes()).hexdigest() for p in [R / 'security_metrics.py', R / 'security_models_optional.py', R / 'vendor/ESTIMATOR_PROVENANCE.json']}
    return dict(
        schema_version=2, active_variant=active_vid, baseline_name='LaZer E4 supplement',
        upstream_target_bits=128, protocol_parameters_changed=is_v5, model=MODEL_ID,
        attack_rows=rows, assumption_coverage=assumptions,
        minimum_among_declared_attack_rows={
            'classical_log2_cost': min(x['classical_log2_cost'] for x in rows),
            'quantum_log2_cost': min(x['quantum_log2_cost'] for x in rows),
            'scope': 'ONLY declared generic attacks, not full-protocol security level',
        },
        properties=properties, knowledge_bounds=bounds, model_details=models,
        source_hashes=hashes, full_sage_estimator_status='OPTIONAL_SEPARATE_TOOL_NOT_REQUIRED_FOR_THIS_DECLARED_GENERIC_MODEL',
        numeric_protocol_security_certified=False,
    )


def write(output, upstream):
    output.mkdir(parents=True, exist_ok=True)
    d = build(upstream)
    sections = (R / 'lazer/python/anon_cred/anon_cred_params.h').read_text().split('// auto-generated by lnp-tbox.sage.')[1:]
    sampling = []
    for name, t in zip(['P1', 'P2'], sections):
        comments = t.split('#include')[0]
        sampling.append({
            'component': name,
            'source': 'unchanged upstream generated header comments',
            'reported_standard_deviations': {f'stdev{i}': float(re.search(rf'// stdev{i} = ([\d.]+)', comments)[1]) for i in range(1, 5)},
            'reported_rejection_factors': {f'M{i}': float(re.search(rf'// M{i} = ([\d.]+)', comments)[1]) for i in range(1, 5)},
            'challenge_omega': 8, 'challenge_eta': 140,
            'original_metadata_comments': comments.strip(),
            'numeric_ZK_distance_bound_instantiated': False,
        })
    d['sampling_metadata'] = sampling
    (output / 'sampling_metadata.json').write_text(json.dumps(sampling, indent=2) + '\n')
    (output / 'security_metrics.json').write_text(json.dumps(d, indent=2, ensure_ascii=False) + '\n')
    (output / 'knowledge_bounds.json').write_text(json.dumps(d['knowledge_bounds'], indent=2) + '\n')
    for filename, rows in [('attack_costs.csv', d['attack_rows']), ('security_properties.csv', d['properties']), ('assumption_coverage.csv', d['assumption_coverage'])]:
        with (output / filename).open('w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    text = [
        f"# 安全指标：原配置证据与固定模型估计（当前变体：{d['active_variant']}）", '',
        f"原装生成器目标128位，协议参数集变更标志：`protocol_parameters_changed = {d['protocol_parameters_changed']}`。以下攻击成本是声明范围内的启发式估计，不能当作整套协议已证明位数。", '',
        '| 分量 | 攻击 | RHF δ0 | beta | 经典log2成本 | 量子log2成本 |', '|---|---|---:|---:|---:|---:|',
    ]
    for x in d['attack_rows']:
        text.append(f"| {x['component']} | {x['attack']} | {x['root_hermite_factor_delta0']:.7f} | {x['beta']} | {x['classical_log2_cost']:.3f} | {x['quantum_log2_cost']:.3f} |")
    text += [
        '', f'模型：{MODEL_ID}。MLWE采用三元均匀秘密/误差、无限样本的无结构模型。Falcon/NTRU行仅是通用格原像攻击代理。', '',
        '| 安全指标 | 证据类型 | 内容 | 边界 |', '|---|---|---|---|',
    ]
    for x in d['properties']:
        text.append(f"| {x['metric']} | {x['status']} | {x['value']} | {x['limits']} |")
    text += ['', '逐项假设覆盖见assumption_coverage.csv。', '', '## 知识错误公式复算', '']
    for x in d['knowledge_bounds']:
        text.append(f"- {x['component']}: epsilon={x['epsilon']:.8e}, -log2(epsilon)={x['minus_log2_epsilon']:.6f}; 原头文件保守界2^-{int(x['header_minus_log2_bound'])}；放大参数lambda={x['lambda_repetitions']}；MSIS假设：{x['assumption']}。")
    (output / 'SECURITY_METRICS_ZH.md').write_text('\n'.join(text) + '\n')
    return d


if __name__ == '__main__':
    from security_audit import collect
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', type=Path, default=R / 'results/security_static')
    a = ap.parse_args()
    write(a.output, collect())
    print('SECURITY_METRICS_RECORDED: six dimensions; declared generic C/Q models')
