"""Fixed-coin functional probes ONLY, always separate from performance data."""
import importlib.util, json, os, sys
from pathlib import Path
from revision_common import *

def run(workspace,batch,baseenv):
    dest=batch/'equivalence';dest.mkdir(exist_ok=True)
    if (dest/'PASSED.json').exists():
        m=json.loads((dest/'PASSED.json').read_text())
        for rel,h in m['files'].items():
            if sha(dest/rel)!=h:raise RuntimeError('modified equivalence evidence')
        return
    modspec=importlib.util.spec_from_file_location('legacy_probe',ROOT/'base_project/verify_e2_all.py')
    mod=importlib.util.module_from_spec(modspec);modspec.loader.exec_module(mod)
    # Build the legacy RNG interposer with the configured GCC, never an inherited CC.
    (dest/'fake_rng.c').write_text(mod.FAKE_RNG_C)
    build=json.loads((workspace/'build_config.json').read_text())
    cc=build['compilers']['gcc']['cc']['path']
    execute([cc,'-shared','-fPIC','-O2',dest/'fake_rng.c','-o',dest/'libfake_rng.so','-ldl'],dest,dest/'build.log',baseenv)
    fixed={}
    def probe(c,v,seed,generic=False):
        name=f'{c}_{v}_{seed}'+('_generic' if generic else '')
        sp=dest/(name+'.spec.json');out=dest/(name+'.jsonl');project=workspace/c/v
        dump(sp,dict(task='fixed',variant=v,formal=False))
        env=baseenv.copy();env.update(LD_PRELOAD=str(dest/'libfake_rng.so'),FAKE_RNG_SEED=str(seed))
        env['LD_LIBRARY_PATH']=str(project/'lazer')+os.pathsep+env.get('LD_LIBRARY_PATH','')
        if generic:env['E4_FORCE_GENERIC']='1'
        execute([sys.executable,ROOT/'lazer_worker.py','--project',project,'--spec',sp,'--out',out,
            '--attestation',dest/(name+'.loaded.json')],project,dest/(name+'.log'),env)
        data=rows(out)
        if len(data)!=1 or data[0]['status']!='ACCEPTED':raise RuntimeError('fixed-coin probe failed')
        return data[0]
    fields=['pk_hex','request_sha','blind_sha','proof_hex']
    for c in ['gcc','clang']:
        for v in ['B1','G3','C3']:
            for seed in [1,2,3]:fixed[c,v,seed]=probe(c,v,seed)
    for seed in [1,2,3]:
        for c in ['gcc','clang']:
            for field in fields:
                if fixed[c,'B1',seed][field]!=fixed[c,'G3',seed][field]:raise RuntimeError('B1/G3 fixed identity failed')
        for v in ['B1','G3','C3']:
            for field in fields:
                if fixed['gcc',v,seed][field]!=fixed['clang',v,seed][field]:raise RuntimeError('compiler fixed identity failed')
    for c in ['gcc','clang']:
        for v in ['G3','C3']:
            generic=probe(c,v,1,True)
            if any(generic[f]!=fixed[c,v,1][f] for f in fields):raise RuntimeError('forced fallback identity failed')
            if not (generic['prove_counters'][13]>0 and generic['prove_counters'][15]>0):raise RuntimeError('fallback not exercised')
    dump(dest/'PASSED.json',dict(status='PASSED',seeds=[1,2,3],
        comparisons=['B1/G3 byte identity','same variant GCC/Clang byte identity','G3/C3 own forced-generic identity'],
        scope='finite fixed-coin functional regression; NEVER performance measurements',files=manifest(dest)))
