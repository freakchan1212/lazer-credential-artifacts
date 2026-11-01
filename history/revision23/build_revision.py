#!/usr/bin/env python3
"""Build each compiler/variant in a new tree. Never invoke legacy fast caches."""
import argparse, difflib, json, os, shutil, subprocess, sys, zipfile
from pathlib import Path
from revision_common import *

HEXL_SOURCES = ['eltwise/eltwise-mult-mod.cpp','eltwise/eltwise-reduce-mod.cpp',
    'eltwise/eltwise-sub-mod.cpp','eltwise/eltwise-add-mod.cpp','eltwise/eltwise-fma-mod.cpp',
    'eltwise/eltwise-cmp-add.cpp','eltwise/eltwise-cmp-sub-mod.cpp','ntt/ntt-internal.cpp',
    'ntt/ntt-radix-2.cpp','ntt/ntt-radix-4.cpp','number-theory/number-theory.cpp']

def compile_one(cc, src, obj, flags, includes, env, log):
    execute([cc,*flags,*['-I'+str(x) for x in includes],'-c',src,'-o',obj],obj.parent,log,env)

def copy_base(dst):
    shutil.copytree(ROOT/'base_project',dst)

def dependencies(base, dest, cc, cxx, env, log):
    """Same portable HEXL backend as original no-CMake fallback, for BOTH compilers."""
    dest.mkdir(parents=True)
    hdr=dest/'include'; lib=dest/'lib'; hdr.mkdir();lib.mkdir()
    cpu=base/'vendor/cpu_features'
    shutil.copytree(cpu/'include',hdr,dirs_exist_ok=True)
    objects=[]
    for name in ['filesystem','stack_line_reader','string_view','cpuinfo_x86','hwcaps']:
        obj=dest/(name+'.o')
        compile_one(cc,cpu/f'src/{name}.c',obj,
            [*FLAGS,'-fPIC','-DSTACK_LINE_READER_BUFFER_SIZE=1024','-DHAVE_STRONG_GETAUXVAL','-DHAVE_DLFCN_H'],
            [hdr,hdr/'internal'],env,log); objects.append(obj)
    execute(['ar','rcs',lib/'libcpu_features.a',*objects],dest,log,env)
    with zipfile.ZipFile(base/'lazer/third_party/hexl-development.zip') as z: z.extractall(dest)
    h=dest/'hexl-development'
    # Disable architecture auto-detection: no CMake try_run and no AVX-512 objects.
    (h/'hexl/include/hexl/util/defines.hpp').write_text('#pragma once\n#define HEXL_USE_GNU 1\n#define HEXL_UNUSED(x) (void)(x)\n')
    objects=[]
    for i,name in enumerate(HEXL_SOURCES):
        obj=dest/f'hexl_{i}.o'
        compile_one(cxx,h/'hexl'/name,obj,[*FLAGS,'-std=c++17','-fPIC'],
                    [h/'hexl/include',h/'hexl',hdr],env,log); objects.append(obj)
    execute(['ar','rcs',lib/'libhexl.a',*objects],dest,log,env)

def build_lazer(dest, dep, cc, cxx, variant, env, log):
    copy_base(dest)
    execute([sys.executable,'e4_select.py',variant],dest,log,env)
    execute([sys.executable,'verify_baseline.py'],dest,log,env)
    l=dest/'lazer'; fal=l/'third_party/Falcon-impl-20211101'
    if not fal.exists():
        with zipfile.ZipFile(l/'third_party/Falcon-impl-20211101.zip') as z:z.extractall(l/'third_party')
        execute(['patch','-p1','-i',l/'src/falcon.patch'],fal,log,env)
    # Generate the public header using upstream rule, without building library targets.
    execute(['make','lazer.h'],l,log,env)
    inc=[fal,l,dep/'include']
    cf=[*FLAGS,'-fPIC','-DNDEBUG','-DFALCON_FPNATIVE','-DFALCON_AVX2','-DFALCON_FMA']
    objects=[]
    for name in FALCON:
        obj=fal/f'{name}_revision.o';compile_one(cc,fal/f'{name}.c',obj,cf,inc,env,log);objects.append(obj)
    for name in ['lazer']:
        obj=l/'src'/f'{name}_revision.o';compile_one(cc,l/'src'/f'{name}.c',obj,cf,inc,env,log);objects.append(obj)
    obj=l/'src/hexl_revision.o'
    compile_one(cxx,l/'src/hexl.cpp',obj,[*FLAGS,'-fPIC','-std=c++17'],
        [l/'src',dep/'hexl-development/hexl/include'],env,log);objects.append(obj)
    # CFFI's upstream linker expects libhexl.a at these paths.
    hp=l/'third_party/hexl-development/build/hexl/lib';hp.mkdir(parents=True,exist_ok=True)
    shutil.copy2(dep/'lib/libhexl.a',hp/'libhexl.a')
    execute([cxx,'-shared','-Wl,-z,defs','-Wl,-soname,liblazer.so','-o',l/'liblazer.so',
        *objects,dep/'lib/libhexl.a',dep/'lib/libcpu_features.a','-lmpfr','-lgmp','-lm'],dest,log,env)
    execute(['ar','rcs',l/'liblazer.a',*objects],dest,log,env)
    # cffi may invoke compiler through distutils: set CC/CXX and append common flags.
    e=env.copy(); e.update(CC=cc,CXX=cxx,CFLAGS=' '.join(FLAGS),CXXFLAGS=' '.join(FLAGS))
    e['LD_LIBRARY_PATH']=str(l)+os.pathsep+e.get('LD_LIBRARY_PATH','')
    execute([sys.executable,'lazer_cffi_build.py','..'],l/'python',log,e)
    execute([sys.executable,'../params_cffi_build.py','anon_cred_params.h','../..'],l/'python/anon_cred',log,e)
    execute([sys.executable,'-c','import anon_cred; print("REV_IMPORT_OK")'],l/'python/anon_cred',log,e)

def build_external(dest, cc,cxx,env,log):
    shutil.copytree(ROOT/'vendor/pqzk-blns',dest)
    param=dest/'params.h';old=param.read_text();new=old
    replacements={'#define lm0     2 //1':'#define lm0     1 // task adapter: eight 64-coefficient attributes',
        '#define l0          16 //8':'#define l0          8 // task adapter',
        '// #define USE_ISSUER_BLIND_SIGNATURE':'#define USE_ISSUER_BLIND_SIGNATURE',
        '#define USE_ISSUER_SIGNATURE        ':'// #define USE_ISSUER_SIGNATURE        '}
    for a,b in replacements.items():
        # lm0 occurs in all three security branches; adapt ONLY selected 128 branch.
        expected=3 if a.startswith('#define lm0') else 1
        if new.count(a)!=expected: raise RuntimeError('external upstream changed: '+a)
        new=new.replace(a,b,1)
    param.write_text(new)
    patch=list(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='params.h.upstream',tofile='params.h'))
    # Observational hook: capture actual allocated serialized proof length, no formula guess.
    p=dest/'ISIS.cc';old=p.read_text();new='#include <cstddef>\nsize_t revision_last_proof_bytes = 0;\n'+old
    token='*Pi_ptr = new uint8_t[len_Pi];'
    if new.count(token)!=1:raise RuntimeError('unexpected proof allocation')
    new=new.replace(token,'revision_last_proof_bytes = len_Pi;\n    '+token);p.write_text(new)
    patch+=list(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='ISIS.cc.upstream',tofile='ISIS.cc'))
    # Upstream blind-issuance path frees the same Pi in Verify_Com AND I_VerCred.
    # Match ISIS verifier ownership: caller retains/frees serialized proof.
    p=dest/'Com.cc';old=p.read_text();token='delete[] (*Pi_ptr);'
    if old.count(token)!=1:raise RuntimeError('unexpected Com proof ownership')
    new=old.replace(token,'/* Revision: caller owns/frees Pi; avoid double-free in I_VerCred. */')
    p.write_text(new)
    patch+=list(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='Com.cc.upstream',tofile='Com.cc'))
    (dest/'REVISION.diff').write_text(''.join(patch))
    # External uses ORIGINAL Falcon, never the LaZer-patched Falcon.
    with zipfile.ZipFile(ROOT/'base_project/lazer/third_party/Falcon-impl-20211101.zip') as z:z.extractall(dest)
    fal=dest/'Falcon-impl-20211101';objects=[]
    for name in FALCON:
        obj=fal/f'{name}_revision.o'
        compile_one(cc,fal/f'{name}.c',obj,[*FLAGS,'-fPIC'],[fal],env,log);objects.append(obj)
    for p in sorted(dest.glob('*.cc')):
        if p.name in ['bench.cc','BLNS.cc']:continue
        obj=dest/(p.stem+'_revision.o')
        compile_one(cxx,p,obj,[*FLAGS,'-std=gnu++11','-pthread','-Drestrict=__restrict__','-DENABLE_FALCON'],[dest,fal],env,log);objects.append(obj)
    shutil.copy2(ROOT/'external_worker.cc',dest/'revision_worker.cc')
    obj=dest/'revision_worker.o'
    compile_one(cxx,dest/'revision_worker.cc',obj,[*FLAGS,'-std=gnu++11','-pthread','-Drestrict=__restrict__','-DENABLE_FALCON'],[dest,fal],env,log);objects.append(obj)
    execute([cxx,*FLAGS,'-pthread','-o',dest/'revision_worker',*objects,'-lntl','-lgmp','-lm'],dest,log,env)

def main():
    p=argparse.ArgumentParser();p.add_argument('--workspace',type=Path,required=True)
    p.add_argument('--compilers',nargs='+',choices=['gcc','clang'],default=['gcc','clang'])
    p.add_argument('--external',action='store_true');a=p.parse_args();w=a.workspace.resolve();w.mkdir(parents=True,exist_ok=True)
    env=clean_env(); compiler_map={}
    for label in a.compilers:
        cc=shutil.which(os.environ.get('REV_'+label.upper()+'_CC',label))
        cxx=shutil.which(os.environ.get('REV_'+label.upper()+'_CXX','g++' if label=='gcc' else 'clang++'))
        if not cc or not cxx:raise SystemExit('Missing '+label+' compiler; see README')
        compiler_map[label]=(str(Path(cc).absolute()),str(Path(cxx).absolute()))
    spec=dict(schema='REV23-v1',python=sys.executable,python_version=sys.version,
        source=manifest(ROOT/'base_project'),driver={name:sha(ROOT/name) for name in ['build_revision.py','revision_common.py']},
        external_sources=manifest(ROOT/'vendor/pqzk-blns'),external_worker_sha=sha(ROOT/'external_worker.cc'),
        flags=FLAGS,compilers={k:tool_info(*v) for k,v in compiler_map.items()},external=a.external,
        dependency_note='GMP/MPFR/NTL system binaries held fixed; HEXL/cpu_features/Falcon rebuilt',
        local_include=env.get('CPATH'),local_library=env.get('LIBRARY_PATH'))
    cfg=w/'build_config.json'
    if cfg.exists() and json.loads(cfg.read_text())!=spec:raise SystemExit('Build configuration changed; choose NEW workspace')
    dump(cfg,spec)
    for label,(cc,cxx) in compiler_map.items():
        d=w/label;d.mkdir(exist_ok=True);dep=d/'dependencies'
        if (dep/'COMPLETE.json').exists():
            for rel,h in json.loads((dep/'COMPLETE.json').read_text()).items():
                if sha(dep/rel)!=h:raise RuntimeError('dependency changed; use a new workspace: '+rel)
        else:
            if dep.exists():shutil.rmtree(dep)
            print('BUILD dependencies',label,flush=True)
            dependencies(ROOT/'base_project',dep,cc,cxx,env,w/'logs'/f'{label}_deps.log')
            dump(dep/'COMPLETE.json',manifest(dep))
        for v in ['B1','G3','C3']:
            dst=d/v
            if (dst/'BUILD_COMPLETE.json').exists():
                for rel,h in json.loads((dst/'BUILD_COMPLETE.json').read_text())['files'].items():
                    if sha(dst/rel)!=h:raise RuntimeError('build changed; use a new workspace: '+rel)
            else:
                if dst.exists():shutil.rmtree(dst)
                print('BUILD',label,v,flush=True)
                build_lazer(dst,dep,cc,cxx,v,env,w/'logs'/f'{label}_{v}.log')
                files={str(x.relative_to(dst)):sha(x) for x in dst.rglob('*') if x.is_file()
                    and (x.suffix=='.so' or x.name in ['anon_cred.py','anon_cred_params.h','lazer.h','ACTIVE_VARIANT.json'])}
                dump(dst/'BUILD_COMPLETE.json',dict(compiler=label,variant=v,files=files))
        if a.external and label=='clang':
            dst=d/'external'
            if not (dst/'BUILD_COMPLETE.json').exists():
                if dst.exists():shutil.rmtree(dst)
                print('BUILD external',label,flush=True)
                build_external(dst,cc,cxx,env,w/'logs'/f'{label}_external.log')
                dump(dst/'BUILD_COMPLETE.json',dict(commit=UPSTREAM_COMMIT,
                    files={str(x.relative_to(dst)):sha(x) for x in dst.iterdir() if x.is_file() and x.name in ['revision_worker','params.h','ISIS.cc','Com.cc','REVISION.diff']},
                    comparison='same machine, eight hashed attributes, blind issuance; security/encoding NOT identical'))
    print('BUILD COMPLETE',w,flush=True)

if __name__=='__main__':main()
