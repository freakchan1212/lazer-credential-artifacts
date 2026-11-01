#!/usr/bin/env python3
import json, os, platform, shutil, subprocess, sys, sysconfig
from pathlib import Path
from revision_common import ROOT, envinfo, clean_env
print(json.dumps(envinfo(),ensure_ascii=False,indent=2))
missing=[]
for tool in ['gcc','g++','clang','clang++','make','patch','ar']:
    path=shutil.which(tool);print(tool,path)
    if not path:missing.append(tool)
try:import cffi,setuptools
except ImportError:missing.append('Python cffi/setuptools (install in venv)')
if not (Path(sysconfig.get_paths()['include'])/'Python.h').is_file():missing.append('matching python development headers')
env=clean_env()
for compiler,code,lang in [('gcc','#include <gmp.h>\n#include <mpfr.h>\n','c'),('g++','#include <NTL/ZZ.h>\n','c++')]:
    if shutil.which(compiler):
        p=subprocess.run([compiler,'-x',lang,'-E','-'],input=code,text=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,env=env)
        if p.returncode:missing.append(code.strip())
flags=next((x.split(':',1)[1].split() for x in Path('/proc/cpuinfo').read_text().splitlines() if x.startswith('flags')),[])
if platform.machine()!='x86_64':missing.append('x86_64 Linux')
missing+=list(set(['avx2','aes','fma'])-set(flags))
print('Allowed logical CPUs:',sorted(os.sched_getaffinity(0)))
print('Choose one available core, inspect thread_siblings_list, keep sibling idle. No automatic frequency changes.')
if missing:raise SystemExit('MISSING: '+repr(missing))
print('PREFLIGHT PASSED')
