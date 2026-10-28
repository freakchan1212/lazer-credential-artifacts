#!/usr/bin/env python3
"""Resumable, randomized block experiments. Run smoke, pilot, then full."""
import argparse, datetime, fcntl, hashlib, json, os, platform, random, shutil, subprocess, sys, tarfile, time, uuid
from pathlib import Path
R=Path(__file__).resolve().parent;P=R/'project'
PROFILES={'smoke':dict(rounds=1,n=3,block=3,reuse=4,repeats=1,policy=4,ksweep=1,diag=3,seeds=[1],all_subsets=False),
 'pilot':dict(rounds=2,n=30,block=10,reuse=32,repeats=2,policy=20,ksweep=5,diag=20,seeds=[1,2,3],all_subsets=True),
 'full':dict(rounds=3,n=200,block=20,reuse=256,repeats=3,policy=100,ksweep=30,diag=100,seeds=[1,2,3],all_subsets=True)}
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,obj):
 p.parent.mkdir(parents=True,exist_ok=True);temp=p.with_suffix(p.suffix+'.tmp');temp.write_text(json.dumps(obj,ensure_ascii=False,indent=2));temp.replace(p)
def readrows(p):return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
def envinfo(cpu):
 def rd(p):
  try:return Path(p).read_text().strip()
  except OSError:return None
 return dict(platform=platform.platform(),python=sys.version,cpuinfo=rd('/proc/cpuinfo'),affinity=sorted(os.sched_getaffinity(0)),logical_cpu=cpu,
   governor=rd(f'/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_governor'),frequency_khz_snapshot=rd(f'/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_cur_freq'),
   core_type=rd(f'/sys/devices/system/cpu/cpu{cpu}/topology/core_type'),core_id=rd(f'/sys/devices/system/cpu/cpu{cpu}/topology/core_id'),
   epp=rd(f'/sys/devices/system/cpu/cpu{cpu}/cpufreq/energy_performance_preference'),
   temperatures={str(x):rd(x) for x in Path('/sys/class/thermal').glob('thermal_zone*/temp')},
   clock='perf_counter_ns',build_profile='AVX2_AES_FMA_NO_AVX512',environment_modified=False)

def plan(c):
 jobs=[];rng=random.Random(20261018)
 for rnd in range(1,c['rounds']+1):
  for block,offset in enumerate(range(0,c['n'],c['block']),1):
   group=[]
   for v in ['B1','G3','C3']:
    for life in ['steady','fresh']:
     for mode in ['raw','strict']:
      group.append(dict(task='main',variant=v,round=rnd,block=block,lifecycle=life,verification_mode=mode,sessions=min(c['block'],c['n']-offset),warmup=2,formal=True))
   rng.shuffle(group);jobs+=group
 for v in ['B1','V0','V1','G3','C3']:
  for rep in range(c['repeats']):jobs.append(dict(task='reuse',variant=v,sessions=c['reuse'],warmup=0,formal=True,repeat=rep,verification_mode='strict'))
 for v in ['V1','G3','C3']:
  for pattern in ['fixed','alternating','random']:
   jobs.append(dict(task='policy',variant=v,pattern=pattern,sessions=c['policy'],warmup=2,formal=True,verification_mode='strict',seed=1729))
 for v in ['G3','C3']:
  for k in range(9):jobs.append(dict(task='k_sweep',variant=v,k=k,sessions=c['ksweep'],warmup=2,formal=True,verification_mode='strict'))
 for v in ['G3','C3']:
  jobs.append(dict(task='subsets',variant=v,all_subsets=c['all_subsets'],formal=False,seed=20261018))
 for v in ['D3','DC3']:
  jobs.append(dict(task='diagnostic',variant=v,sessions=c['diag'],warmup=2,formal=False,verification_mode='strict'))
 return [dict(j,id=f'{i:04d}_{j["task"]}_{j["variant"]}') for i,j in enumerate(jobs)]

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=PROFILES,default='smoke');ap.add_argument('--cpu',type=int,default=0);ap.add_argument('--resume',type=Path);ap.add_argument('--plots-only',type=Path);ap.add_argument('--no-plots',action='store_true');a=ap.parse_args()
 if a.plots_only:
  plot_python=P/'.venv/bin/python3'
  subprocess.run([str(plot_python) if plot_python.exists() else sys.executable,str(R/'plot_e4.py'),'--batch',str(a.plots_only.resolve()),'--lang','both'],check=True);return
 if a.cpu not in os.sched_getaffinity(0):raise SystemExit(f'CPU {a.cpu} unavailable; allowed={sorted(os.sched_getaffinity(0))}')
 os.sched_setaffinity(0,{a.cpu});lock=(P/'.e4.lock').open('w')
 try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:raise SystemExit('Another E4 run is using this project. Use another extracted copy.')
 c=PROFILES[a.mode];batch=a.resume.resolve() if a.resume else R/'results'/f'e4_{a.mode}_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}_{uuid.uuid4().hex[:6]}'
 batch.mkdir(parents=True,exist_ok=True)
 baseenv=os.environ.copy()
 for key in ['LD_PRELOAD','FAKE_RNG_SEED','E4_FORCE_GENERIC']:baseenv.pop(key,None)
 baseenv['PYTHONHASHSEED']='0';baseenv['MPLCONFIGDIR']=str(batch/'matplotlib_cache')
 source_files=[R/'run_e4.py',R/'plot_e4.py',R/'summarize_e4.py',P/'e4_select.py',P/'e4_worker.py',P/'switch_variant.py',P/'pristine/upstream_snapshot.zip',P/'build_backend.sh',P/'05_build_compatible.sh',P/'06_rebuild_fast.sh',P/'baseline_hooks.h',P/'security_audit.py',P/'security_models_optional.py',P/'security_metrics.py']
 script_hashes={str(p.relative_to(R)):digest(p) for p in source_files}
 configuration=dict(mode=a.mode,profile=c,cpu=a.cpu,script_hashes=script_hashes,schema='E4-20261018')
 if a.resume:
  old=json.loads((batch/'config.json').read_text())
  if old!=configuration:raise SystemExit('Resume configuration/source mismatch; start a new batch')
 else:dump(batch/'config.json',configuration);dump(batch/'plan.json',plan(c));dump(batch/'environment_start.json',envinfo(a.cpu))
 def execute(cmd,log,env=None):
  print('RUN:', ' '.join(map(str,cmd)),flush=True);log.parent.mkdir(parents=True,exist_ok=True)
  with log.open('w') as f:
   rc=subprocess.run(list(map(str,cmd)),cwd=P,env=env or baseenv,stdout=f,stderr=subprocess.STDOUT).returncode
  if rc:raise RuntimeError(f'Exit {rc}; log: {log}')
 vpy=P/'.venv/bin/python3';last=None
 def select(v):
  nonlocal last
  if last==v:return
  execute([sys.executable,P/'e4_select.py',v],batch/'logs'/f'select_{v}.log')
  execute(['bash',P/'06_rebuild_fast.sh'],batch/'logs'/f'build_{v}.log');last=v
  if not (batch/'worker_runtime.json').exists():
   code='import sys,platform,json;print(json.dumps(dict(python=sys.version,executable=sys.executable,platform=platform.platform())))'
   info=json.loads(subprocess.check_output([str(vpy),'-c',code],cwd=P,env=baseenv,text=True))
   info['compiler_versions']={tool:subprocess.check_output([tool,'--version'],text=True).splitlines()[0] for tool in ['gcc','g++']}
   dump(batch/'worker_runtime.json',info)
  dest=batch/'artifacts'/v;dest.mkdir(parents=True,exist_ok=True)
  for rel in ['ACTIVE_VARIANT.json','PATCHES.json','E4_SOURCE_CHANGES.diff','baseline_hooks.h','06_rebuild_fast.sh']:
   shutil.copy2(P/rel,dest/Path(rel).name)
  # Store actual native library and key sources, not just recorded binary digests.
  for rel in ['lazer/liblazer.so','lazer/src/lin-proofs.c','lazer/src/rejection.c','lazer/src/lnp-quad.c','lazer/src/poly.c','lazer/lazer.h','lazer/python/anon_cred/anon_cred.py','lazer/python/anon_cred/anon_cred_params.h','lazer/python/lazer.py']:
   target=dest/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(P/rel,target)
  dump(dest/'SHA256.json',{str(p.relative_to(dest)):digest(p) for p in dest.rglob('*') if p.is_file() and p.name!='SHA256.json'})
  execute([vpy,P/'security_audit.py','--output',batch/'security'/v],batch/'logs'/f'security_{v}.log')
 def worker(spec,target,extra=None):
  sp=batch/'specs'/(target.stem+'.json');dump(sp,spec);temp=target.with_suffix('.partial')
  env=baseenv.copy();env.update(extra or {})
  execute([vpy,P/'e4_worker.py','--spec',sp,'--out',temp],batch/'logs'/(target.stem+'.log'),env)
  rows=readrows(temp)
  if not rows:raise RuntimeError('Empty worker output')
  temp.replace(target);dump(target.with_suffix('.receipt.json'),dict(sha256=digest(target),rows=len(rows)))
  return rows
 if not (batch/'verification/PASSED.json').exists():
  sys.path.insert(0,str(P));import verify_e2_all as old
  (batch/'artifacts').mkdir(exist_ok=True)
  fake=old._build_fake_rng_so(batch/'artifacts');fixed={};testdir=batch/'verification';testdir.mkdir(exist_ok=True)
  for v in ['B1','G3','C3']:
   select(v);fixed[v]={}
   for seed in c['seeds']:
    rows=worker(dict(task='fixed',variant=v,formal=False),testdir/f'fixed_{v}_{seed}.jsonl',{'LD_PRELOAD':str(fake),'FAKE_RNG_SEED':str(seed)})
    fixed[v][str(seed)]=rows[0]
   if v in ['G3','C3']:
    worker(dict(task='guard',variant=v,formal=False),testdir/f'guard_{v}.jsonl')
    force=worker(dict(task='fixed',variant=v,formal=False),testdir/f'generic_{v}.jsonl',{'LD_PRELOAD':str(fake),'FAKE_RNG_SEED':str(c['seeds'][0]),'E4_FORCE_GENERIC':'1'})[0]
    native=fixed[v][str(c['seeds'][0])]
    assert force['proof_hex']==native['proof_hex'] and force['request_sha']==native['request_sha']
    assert force['prove_counters'][13]>0 and force['prove_counters'][15]>0
  for seed in c['seeds']:
   x,y=fixed['B1'][str(seed)],fixed['G3'][str(seed)]
   for field in ['pk_hex','request_sha','blind_sha','proof_hex']:assert x[field]==y[field],(seed,field)
  for target in ['B1','G3']:
   select(target);inp=testdir/f'cross_{target}_inputs.json';dump(inp,[fixed[src][str(seed)] for src in ['B1','G3'] for seed in c['seeds']])
   worker(dict(task='cross',variant=target,inputs=str(inp),formal=False),testdir/f'cross_{target}.jsonl')
  select('G3')
  # Retain E3 native boundary and >32-instance residency tests, executed on checked code.
  dump(testdir/'poly_scale.json',old._test_poly_scale_v3());dump(testdir/'cache_residency.json',old._test_v1_dynamic_cache_stress())
  dump(testdir/'PASSED.json',dict(status='PASSED',seeds=c['seeds'],fixed_identity=['B1','G3'],forced_generic_identity=['G3','C3'],cross_verification='all B1/G3 proofs into both verifiers; strict',range_guard_cases_each=1009,scope='finite regression; not full security proof'))
 for job in json.loads((batch/'plan.json').read_text()):
  path=batch/'raw'/(job['id']+'.jsonl');receipt=path.with_suffix('.receipt.json')
  if path.exists() and receipt.exists():
   saved=json.loads(receipt.read_text())
   if digest(path)!=saved['sha256']:raise RuntimeError(f'Modified completed output: {path}')
   continue
  select(job['variant']);worker(job,path)
 dump(batch/'environment_end.json',envinfo(a.cpu))
 execute([vpy,R/'summarize_e4.py','--batch',batch],batch/'logs/summarize.log')
 plot_status='SKIPPED'
 if not a.no_plots:
  try:
   try:execute([vpy,'-c','import matplotlib,numpy'],batch/'logs/plot_dependencies.log')
   except RuntimeError:execute([vpy,'-m','pip','install','matplotlib>=3.7,<4','numpy>=1.23,<3'],batch/'logs/install_plots.log')
   execute([vpy,R/'plot_e4.py','--batch',batch,'--lang','both'],batch/'logs/plots.log');plot_status='COMPLETE'
  except RuntimeError:plot_status='PLOT_FAILED_DATA_PRESERVED';print('Plots failed; measurements are saved. See plots.log and use --plots-only.')
 dump(batch/'COMPLETE.json',dict(measurements='COMPLETE',verification='PASSED',plots=plot_status,mode=a.mode))
 archive=batch.with_suffix('.tar.gz')
 with tarfile.open(archive,'w:gz') as z:
  for q in batch.rglob('*'):
   if q.is_file() and 'matplotlib_cache' not in q.parts:z.add(q,arcname=str(Path(batch.name)/q.relative_to(batch)))
 print(f'COMPLETE: {batch}\nRETURN THIS FILE: {archive}',flush=True)

if __name__=='__main__':
 try:main()
 except Exception as e:print(f'STOPPED: {e}\nPartial batch retained. Fix the cause and resume with the same mode/cpu and --resume PATH.',file=sys.stderr);raise
