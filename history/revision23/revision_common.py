"""Revision experiments: explicit provenance, no legacy binary cache."""
import hashlib, json, os, platform, subprocess, sys, sysconfig
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FLAGS = ['-O3', '-march=x86-64', '-mtune=generic', '-mavx2', '-maes', '-mfma',
         '-mno-avx512f', '-mno-avx512dq', '-mno-avx512bw', '-mno-avx512vl',
         '-fomit-frame-pointer']
FALCON = ['codec', 'common', 'falcon', 'fft', 'fpr', 'keygen', 'rng', 'shake', 'sign', 'vrfy']
UPSTREAM_COMMIT = 'b622225950bd1b486d96bf191eb835e60eff775f'

def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for part in iter(lambda: f.read(1024*1024), b''): h.update(part)
    return h.hexdigest()

def dump(p, value):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    temp = p.with_suffix(p.suffix+'.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')
    temp.replace(p)

def manifest(root):
    return {str(p.relative_to(root)): sha(p) for p in sorted(Path(root).rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}

def execute(cmd, cwd, log, env=None):
    log = Path(log); log.parent.mkdir(parents=True, exist_ok=True)
    with log.open('a') as f:
        f.write('\nCOMMAND '+json.dumps(list(map(str, cmd)))+'\n'); f.flush()
        rc = subprocess.run(list(map(str, cmd)), cwd=cwd, env=env,
                            stdout=f, stderr=subprocess.STDOUT).returncode
    if rc: raise RuntimeError(f'command failed ({rc}); inspect {log}')

def clean_env():
    e = os.environ.copy()
    for k in ['LD_PRELOAD', 'FAKE_RNG_SEED', 'E4_FORCE_GENERIC', 'BASELINE_DEMO_ROOT',
              'PYTHONPATH', 'PYTHONHOME', 'CC', 'CXX', 'CFLAGS', 'CXXFLAGS',
              'CPATH', 'LIBRARY_PATH', 'LD_LIBRARY_PATH']:
        e.pop(k, None)
    # Explicit local toolchain support for validation; not required on user machines.
    for name in ['CPATH', 'LIBRARY_PATH', 'LD_LIBRARY_PATH']:
        if os.environ.get('REV_'+name): e[name] = os.environ['REV_'+name]
    e.update(PYTHONHASHSEED='0', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1',
             MKL_NUM_THREADS='1', PYTHONNOUSERSITE='1')
    return e

def envinfo(cpu=None):
    def read(p):
        try: return Path(p).read_text().strip()
        except OSError: return None
    return dict(platform=platform.platform(), python=sys.version, executable=sys.executable,
                affinity=sorted(os.sched_getaffinity(0)), logical_cpu=cpu,
                topology={str(c): {key: read(f'/sys/devices/system/cpu/cpu{c}/topology/{key}')
                    for key in ['core_type', 'core_id', 'physical_package_id', 'thread_siblings_list']}
                    for c in sorted(os.sched_getaffinity(0))},
                cpuinfo=read('/proc/cpuinfo'),
                governor=read(f'/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_governor'),
                frequency_khz_snapshot=read(f'/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_cur_freq'),
                temperatures={str(p):read(p) for p in Path('/sys/class/thermal').glob('thermal_zone*/temp')},
                environment_modified=False)

def tool_info(cc, cxx):
    def info(p):
        p=Path(p).resolve()
        return dict(path=str(p), sha256=sha(p), version=subprocess.check_output(
            [str(p),'--version'],text=True,env=clean_env()).splitlines()[0])
    return dict(cc=info(cc), cxx=info(cxx))

def rows(path):
    return [json.loads(s) for s in Path(path).read_text().splitlines() if s.strip()]

def check_rows(data, job):
    n=job['sessions']; warm=job.get('warmup',2)
    if len(data)!=n+warm: raise ValueError(f'expected {n+warm} records, got {len(data)}')
    seen=set()
    for i,r in enumerate(data):
        if r['index']!=i-warm or r['warmup']!=(i<warm): raise ValueError('index/warmup mismatch')
        if r['status']!='ACCEPTED': raise ValueError('honest proof not accepted')
        for k in ['prove_ms','verify_ms','show_ms']:
            import math
            if not math.isfinite(r[k]) or r[k]<=0: raise ValueError('invalid timing')
        if abs(r['show_ms']-r['prove_ms']-r['verify_ms'])>1e-5: raise ValueError('timing sum mismatch')
        if r['proof_bytes']<=0 or r['rss_kib']<=0: raise ValueError('invalid size/RSS')
        for k in ['variant','lifecycle']:
            if r[k]!=job[k]: raise ValueError(f'{k} mismatch')
        if r.get('proof_sha'):
            if r['proof_sha'] in seen: raise ValueError('repeated proof within block')
            seen.add(r['proof_sha'])

