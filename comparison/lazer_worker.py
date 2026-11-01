#!/usr/bin/env python3
"""Attest actual loaded library, then execute the UNCHANGED E4 measurement worker."""
import argparse, json, os, runpy, sys
from pathlib import Path
from revision_common import sha,dump
p=argparse.ArgumentParser();p.add_argument('--project',type=Path,required=True)
p.add_argument('--spec',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
p.add_argument('--attestation',type=Path,required=True);a=p.parse_args()
project=a.project.resolve();spec=json.loads(a.spec.read_text())
sys.path.insert(0,str(project));os.environ['BASELINE_DEMO_ROOT']=str(project/'lazer/python/anon_cred')
import baseline_api as b
import _lazer_cffi, _anon_cred_params_cffi
expected=(project/'lazer/liblazer.so').resolve()
mapped={Path(s.split()[-1]).resolve() for s in Path('/proc/self/maps').read_text().splitlines()
        if 'liblazer.so' in s and s.split()[-1].startswith('/')}
if mapped!={expected}:raise RuntimeError('wrong loaded native library: '+repr(mapped))
build=json.loads((project/'BUILD_COMPLETE.json').read_text())
actual={str(p.relative_to(project)):sha(p) for p in [expected,Path(_lazer_cffi.__file__),Path(_anon_cred_params_cffi.__file__)]}
for rel,h in actual.items():
    if build['files'].get(rel)!=h:raise RuntimeError('binary fingerprint mismatch: '+rel)
dump(a.attestation,dict(actual_library=actual,compiler=build['compiler'],variant=build['variant'],
                       affinity=sorted(os.sched_getaffinity(0)),
                       runtime_libraries={s.split()[-1]:sha(s.split()[-1])
                         for s in Path('/proc/self/maps').read_text().splitlines()
                         if s.split()[-1].startswith('/') and any(x in s.split()[-1]
                            for x in ['libgmp.so','libmpfr.so','libstdc++.so'])}))
sys.argv=[str(project/'e4_worker.py'),'--spec',str(a.spec.resolve()),'--out',str(a.out.resolve())]
runpy.run_path(str(project/'e4_worker.py'),run_name='__main__')
