#!/usr/bin/env python3
import difflib,hashlib,json,zipfile,subprocess
from pathlib import Path
R=Path(__file__).resolve().parent
def sub(t,a,b,count=1):
 if t.count(a)!=count:raise RuntimeError('Patch anchor mismatch: '+a[:60])
 return t.replace(a,b)
def main():
 m=json.loads((R/'UPSTREAM_SHA256.json').read_text());changes={};diff=[]
 with zipfile.ZipFile(R/'pristine/upstream_snapshot.zip') as z:
  for n in ['lazer/src/lazer.c','lazer/src/lin-proofs.c','lazer/src/lnp-quad.c']:
   raw=z.read('BLNS_LAZER_BASELINE_20261014/'+n)
   assert hashlib.sha256(raw).hexdigest()==m[n]
   old=raw.decode();t=old
   if n.endswith('/lazer.c'):t='#include "baseline_hooks.h"\n'+t
   elif n.endswith('/lin-proofs.c'):
    t=sub(t,'  while (1)\n    {\n      /* sample signs */','  while (1)\n    {\n      baseline_counts[0]++;\n      /* sample signs */')
    t=sub(t,'DEBUG_PRINTF (DEBUG_PRINT_REJ, "%s", "reject s3");\n              continue;', 'baseline_counts[1]++;\n              DEBUG_PRINTF (DEBUG_PRINT_REJ, "%s", "reject s3");\n              continue;',2)
    pos=t.find('if (nprime > 0 && params->rej4)')
    assert pos>0
    t=t[:pos]+t[pos:].replace('baseline_counts[1]++','baseline_counts[2]++',1)
   else:
    t=sub(t,'  while (1)\n    {\n      /* y1, y2 */','  while (1)\n    {\n      baseline_counts[3]++;\n      /* y1, y2 */')
    for a,b in [('DEBUG_PRINTF (DEBUG_PRINT_REJ, "%s", "reject on s1");\n              continue;','baseline_counts[4]++;\n              DEBUG_PRINTF (DEBUG_PRINT_REJ, "%s", "reject on s1");\n              continue;'),('DEBUG_PRINTF (DEBUG_PRINT_REJ, "%s", "reject compr");\n              continue;','baseline_counts[5]++;\n              DEBUG_PRINTF (DEBUG_PRINT_REJ, "%s", "reject compr");\n              continue;'),('DEBUG_PRINTF (DEBUG_PRINT_REJ, "%s", "reject on s1");\n          continue;','baseline_counts[6]++;\n          DEBUG_PRINTF (DEBUG_PRINT_REJ, "%s", "reject on s1");\n          continue;')]:t=sub(t,a,b)
   (R/n).write_text(t)
   changes[n]={'original_sha256':m[n],'patched_sha256':hashlib.sha256(t.encode()).hexdigest()}
   diff.extend(difflib.unified_diff(old.splitlines(True),t.splitlines(True),fromfile=n+'.original',tofile=n))
 # Falcon's outer preimage-sampling attempt loop is in a separately built unit.
 fd=R/'lazer/third_party/Falcon-impl-20211101'
 with zipfile.ZipFile(R/'lazer/third_party/Falcon-impl-20211101.zip') as z:
  if not fd.exists():
   z.extractall(fd.parent)
   subprocess.run(['patch','-d',str(fd),'-p1'],input=(R/'lazer/src/falcon.patch').read_text(),text=True,check=True)
  raw=z.read('Falcon-impl-20211101/sign.c')
 old=raw.decode();t=old.replace('#include "inner.h"','#include "inner.h"\nextern void baseline_count_falcon_attempt(void);',1)
 pos=t.index('Zf(sign_dyn)(int16_t *sig,')
 t=t[:pos]+sub(t[pos:],'\tfor (;;) {','\tfor (;;) {\n\t\tbaseline_count_falcon_attempt();')
 n='lazer/third_party/Falcon-impl-20211101/sign.c';(R/n).write_text(t)
 changes[n]={'original_sha256':hashlib.sha256(raw).hexdigest(),'patched_sha256':hashlib.sha256(t.encode()).hexdigest(),'archive_member':'Falcon-impl-20211101/sign.c'}
 diff.extend(difflib.unified_diff(old.splitlines(True),t.splitlines(True),fromfile=n+'.original',tofile=n))
 hook=(R/'baseline_hooks.h').read_bytes();(R/'lazer/src/baseline_hooks.h').write_bytes(hook)
 changes['lazer/src/baseline_hooks.h']={'added_sha256':hashlib.sha256(hook).hexdigest()}
 (R/'PATCHES.json').write_text(json.dumps(changes,indent=2));(R/'SOURCE_CHANGES.diff').write_text(''.join(diff))
 from audit_apply import run as apply_audit
 apply_audit()
 print('SOURCE_HOOKS_PREPARED: measurement counters only; original FS transcript unchanged')
if __name__=='__main__':main()
