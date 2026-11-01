#!/usr/bin/env python3
"""Source/package readiness for two real implementations; not a security certificate."""
import argparse,json,math,re,tarfile
from pathlib import Path
from revision_common import ROOT,dump,sha

def run(out):
    required=['argo_worker.c','argo_wire.h','argo_public.h','external_worker.cc',
              'vendor/argo.tar.gz','vendor/flint.tar.gz','vendor/pqzk-blns/ISIS.cc',
              'vendor/pqzk-blns/Holder.cc','vendor/pqzk-blns/Verifier.cc',
              'base_project/e4_select.py','base_project/e4_worker.py',
              'base_project/lazer/python/anon_cred/anon_cred_params.h']
    missing=[p for p in required if not (ROOT/p).is_file()]
    if missing:raise RuntimeError('Incomplete package: '+repr(missing))
    header=(ROOT/required[-1]).read_text()
    q_match=re.search(r'_p2_param_q_limbs\[\]\s*=\s*\{(\d+)UL',header)
    if not q_match:raise RuntimeError('Cannot locate actual LaZer show modulus')
    with tarfile.open(ROOT/'vendor/argo.tar.gz') as tf:
        names=[m for m in tf.getmembers() if m.name.endswith('code/include/params.h')]
        if len(names)!=1:raise RuntimeError('Ambiguous Argo source archive')
        ah=tf.extractfile(names[0]).read().decode()
    def macro(text,name):
        m=re.search(r'^#define\s+'+re.escape(name)+r'\s+(\d+)',text,re.M)
        if not m:raise RuntimeError('Missing parameter '+name)
        return int(m.group(1))
    ph=(ROOT/'vendor/pqzk-blns/params.h').read_text()
    result=dict(schema='TWO-BASELINES-AUDIT-1',status='SOURCE_COMPLETE_RUNNABLE',
        selected=['argo','pqzk-blns'],external_compiler='gcc',
        application=dict(attributes=8,attribute_bytes=8,D=[0,4,5],
                         lifecycle=['steady','fresh'],control='steady PADDED_NOCACHE'),
        baseline=dict(p=12289,d=64,q_show=int(q_match.group(1)),variants=['B1','G3','C3']),
        implementations={
            'argo':dict(upstream_p=macro(ah,'PARAM_Q'),upstream_N=macro(ah,'PARAM_N'),
                q_show=macro(ah,'PARAM_Q_SHOW'),proof_size_kind='actual_fixed_width_wire',
                validation='Decoded bytes and independently reconstructed public statement',
                runtime_gates='Honest, wrong length, noncanonical coefficient, changed CRS/challenge/target/disclosed attribute',
                comparison_limits=['Different signature/proof parameters','Hidden zero-extension proof not added','Matched security analysis not established']),
            'pqzk-blns':dict(upstream_p=macro(ph,'q0'),q_show=macro(ph,'q2_hat'),
                proof_size_kind='actual_serialized',validation='Upstream verifier with public-only adapted preprocessing',
                runtime_gates='Honest, changed nonce, changed disclosed attribute and serialized proof in adapted modes',
                comparison_limits=['Input-bit mapping does not add hidden-bit proof predicates','Proof modulus is a multiple of p','Matched security analysis not established'])},
        common_parameter_security_equivalence=False,
        reporting_scope='Task-adapted and native-configuration measurements; do not label as a completed strict same-parameter/same-security comparison',
        source_sha256={p:sha(ROOT/p) for p in required})
    dump(out,result)
    print('双对照源码检查通过：Argo、pqzk-blns，可进入构建和运行验证。',flush=True)
    print('参数及安全等级差异保存在：',out,flush=True)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=ROOT/'source_audit.json')
    run(p.parse_args().out)
