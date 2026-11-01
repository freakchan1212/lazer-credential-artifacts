#!/usr/bin/env python3
"""Combined reviewer-2/3 randomized blocks; default full is 3600+600 sessions."""
import argparse, datetime, fcntl, json, os, random, shutil, subprocess, sys, tarfile
from pathlib import Path
from revision_common import *

PROFILES={'smoke':(1,1,2),'pilot':(2,2,5),'full':(3,5,20)}

def plan(mode,external):
    rounds,blocks,sessions=PROFILES[mode];rng=random.Random(20261030);jobs=[]
    for r in range(1,rounds+1):
        for block in range(1,blocks+1):
            group=[]
            for compiler in ['gcc','clang']:
                for variant in ['B1','G3','C3']:
                    for life in ['steady','fresh']:
                        group.append(dict(compiler=compiler,variant=variant,lifecycle=life))
            if external:
                for life in ['steady','fresh']:
                    group.append(dict(compiler='clang',variant='PQZK_BLNS',lifecycle=life))
            rng.shuffle(group)
            for j in group:
                j.update(task='main',round=r,block=block,sessions=sessions,warmup=2,
                         verification_mode='strict' if j['variant']!='PQZK_BLNS' else 'external_native',formal=True)
                j['id']=f'{len(jobs):04d}_{j["compiler"]}_{j["variant"]}_{j["lifecycle"]}'
                jobs.append(j)
    return jobs

def verify_builds(workspace,external):
    identity={}
    for c in ['gcc','clang']:
        for v in ['B1','G3','C3']+(['external'] if external and c=='clang' else []):
            root=workspace/c/v;p=root/'BUILD_COMPLETE.json'
            m=json.loads(p.read_text())
            for rel,h in m['files'].items():
                if sha(root/rel)!=h:raise RuntimeError('build modified: '+str(root/rel))
            identity[f'{c}/{v}']=m
    return identity

def main():
    p=argparse.ArgumentParser();p.add_argument('--workspace',type=Path,required=True)
    p.add_argument('--mode',choices=PROFILES,default='smoke');p.add_argument('--cpu',type=int,required=True)
    p.add_argument('--without-external',action='store_true',help='Explicit reviewer-2-only run; reviewer 3 remains pending')
    p.add_argument('--out',type=Path);p.add_argument('--resume',type=Path);p.add_argument('--plan-only',action='store_true')
    a=p.parse_args();external=not a.without_external;jobs=plan(a.mode,external)
    if a.plan_only:
        print(json.dumps(dict(tasks=len(jobs),formal_sessions=sum(j['sessions'] for j in jobs),plan=jobs),indent=2));return
    if a.cpu not in os.sched_getaffinity(0):raise SystemExit('CPU unavailable; run preflight.py')
    w=a.workspace.resolve();lock=(w/'.revision.lock').open('w')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    os.sched_setaffinity(0,{a.cpu});builds=verify_builds(w,external)
    config=dict(schema='REV23-v1',mode=a.mode,cpu=a.cpu,external=external,builds=builds,
        build_config=json.loads((w/'build_config.json').read_text()),
        drivers={p.name:sha(p) for p in ROOT.glob('*.py')},cpp_sha=sha(ROOT/'external_worker.cc'),plan=jobs)
    batch=(a.resume or a.out or ROOT/'results'/('rev23_'+a.mode+'_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))).resolve()
    if a.resume:
        if json.loads((batch/'config.json').read_text())!=config:raise SystemExit('Resume source/build/config mismatch')
    else:
        if batch.exists():raise SystemExit('Output already exists; use --resume or a new path')
        dump(batch/'config.json',config);dump(batch/'environment_start.json',envinfo(a.cpu))
    # Preserve actual binaries, parameters, differences and compiler command logs.
    if not (batch/'artifacts').exists():
        for name,m in builds.items():
            src=w/name;dst=batch/'artifacts'/name;dst.mkdir(parents=True)
            for rel in m['files']:
                target=dst/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src/rel,target)
            shutil.copy2(src/'BUILD_COMPLETE.json',dst/'BUILD_COMPLETE.json')
        shutil.copytree(w/'logs',batch/'build_logs')
    baseenv=clean_env()
    import check_equivalence
    check_equivalence.run(w,batch,baseenv)
    # New binaries are tested before measurements; checks are not mixed into performance rows.
    for c in ['gcc','clang']:
        for v in ['B1','G3','C3']:
            target=batch/'checks'/f'{c}_{v}.jsonl';rec=target.with_suffix('.receipt.json')
            if rec.exists():
                if sha(target)!=json.loads(rec.read_text())['sha256']:raise RuntimeError('modified check')
                continue
            root=w/c/v;spec=target.with_suffix('.spec.json')
            dump(spec,dict(task='subsets',variant=v,all_subsets=False,formal=False,verification_mode='strict',seed=20261030))
            env=baseenv.copy();env['LD_LIBRARY_PATH']=str(root/'lazer')+os.pathsep+env.get('LD_LIBRARY_PATH','')
            execute([sys.executable,ROOT/'lazer_worker.py','--project',root,'--spec',spec,'--out',target,
                '--attestation',target.with_suffix('.loaded.json')],root,batch/'logs'/f'check_{c}_{v}.log',env)
            data=rows(target)
            if len(data)!=10 or any(r['status']!='ACCEPTED' or not all(r.get('checks',{}).values()) for r in data):
                raise RuntimeError('subset regression failed')
            dump(rec,dict(sha256=sha(target),rows=len(data),scope='nine disclosure subsets plus recreation; finite regression'))
    for i,j in enumerate(jobs):
        target=batch/'raw'/(j['id']+'.jsonl');receipt=target.with_suffix('.receipt.json')
        if receipt.exists():
            r=json.loads(receipt.read_text())
            if sha(target)!=r['sha256']:raise RuntimeError('Modified output '+str(target))
            sp=batch/'specs'/(j['id']+'.json')
            if sha(sp)!=r['spec_sha256'] or json.loads(sp.read_text())!=j:raise RuntimeError('Modified task specification')
            data=rows(target);check_rows(data,j)
            if any(any(row[k]!=j[k] for k in ['compiler','round','block','formal','task']) for row in data):
                raise RuntimeError('Modified record metadata')
            continue
        print(f'[{i+1}/{len(jobs)}] {j["id"]}',flush=True)
        dump(batch/'environment_blocks'/(j['id']+'.json'),envinfo(a.cpu))
        sp=batch/'specs'/(j['id']+'.json');dump(sp,j);temp=target.with_suffix('.partial');temp.parent.mkdir(parents=True,exist_ok=True)
        log=batch/'logs'/(j['id']+'.log');env=baseenv.copy()
        if j['variant']=='PQZK_BLNS':
            root=w/'clang/external'
            execute([root/'revision_worker',str(j['sessions']),str(j['warmup']),j['lifecycle']],root,log,env)
            data=[]
            # Logs are fresh per task attempt; retain only this attempt's lines on retry.
            text=log.read_text();text=text[text.rfind('\nCOMMAND '):]
            for line in text.splitlines():
                if line.startswith('REVJSON '):data.append(json.loads(line[8:]))
            temp.write_text(''.join(json.dumps(r)+'\n' for r in data))
        else:
            root=w/j['compiler']/j['variant']
            env['LD_LIBRARY_PATH']=str(root/'lazer')+os.pathsep+env.get('LD_LIBRARY_PATH','')
            execute([sys.executable,ROOT/'lazer_worker.py','--project',root,'--spec',sp,'--out',temp,
                '--attestation',batch/'loaded'/(j['id']+'.json')],root,log,env)
            data=rows(temp)
        check_rows(data,j)
        for r in data:r.update(compiler=j['compiler'],variant=j['variant'],round=j['round'],block=j['block'],task='main',formal=True)
        temp.write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in data))
        temp.replace(target);dump(receipt,dict(sha256=sha(target),rows=len(data),spec_sha256=sha(sp)))
    dump(batch/'environment_end.json',envinfo(a.cpu))
    execute([sys.executable,ROOT/'summarize_revision.py','--batch',batch],ROOT,batch/'logs/summary.log',baseenv)
    dump(batch/'COMPLETE.json',dict(measurements='COMPLETE',formal_sessions=sum(j['sessions'] for j in jobs),
        reviewer2='MEASURED',reviewer3='NATIVE_CONFIG_REFERENCE_MEASURED' if external else 'NOT_RUN',
        security_equivalence_established=False,performance_platform='see environment_start.json'))
    archive=batch.with_suffix('.tar.gz')
    with tarfile.open(archive,'w:gz') as t:t.add(batch,arcname=batch.name)
    print('COMPLETE — return this file:',archive,flush=True)

if __name__=='__main__':main()
