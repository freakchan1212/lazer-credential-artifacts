#!/usr/bin/env python3
"""One command: verify -> preflight -> build -> smoke -> selected measurement profile."""
import argparse,datetime,os,subprocess,sys
from pathlib import Path
from revision_common import ROOT

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace',type=Path,default=ROOT/'builds_dual')
    p.add_argument('--cpu',type=int)
    p.add_argument('--jobs',type=int,default=4)
    p.add_argument('--mode',choices=['smoke','pilot','full'],default='full')
    a=p.parse_args();allowed=sorted(os.sched_getaffinity(0))
    cpu=a.cpu if a.cpu is not None else (0 if 0 in allowed else allowed[0])
    if cpu not in allowed:p.error('CPU unavailable: '+str(allowed))
    if a.jobs<1:p.error('--jobs must be positive')
    def call(name,*args):
        print('\nRUN',name,*map(str,args),flush=True)
        subprocess.run([sys.executable,str(ROOT/name),*map(str,args)],cwd=ROOT,check=True)
    call('verify_package.py')
    subprocess.run([sys.executable,'-m','unittest','-v','test_revision'],cwd=ROOT,check=True)
    call('audit_two_baselines.py','--out',ROOT/'source_audit.json')
    call('preflight.py')
    call('build_revision.py','--workspace',a.workspace.resolve(),'--all-baselines','--jobs',a.jobs)
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    for mode in (['smoke'] if a.mode=='smoke' else ['smoke',a.mode]):
        call('run_revision.py','--workspace',a.workspace.resolve(),'--mode',mode,'--cpu',cpu,
             '--all-baselines','--out',ROOT/'results'/('dual_'+mode+'_'+stamp))
    print('双对照所选批次完成；请回传最后生成的结果tar.gz。',flush=True)

if __name__=='__main__':main()
