#!/usr/bin/env python3
import hashlib,json,zipfile
from pathlib import Path
R=Path(__file__).resolve().parent
m=json.loads((R/'UPSTREAM_SHA256.json').read_text())
p=json.loads((R/'PATCHES.json').read_text()) if (R/'PATCHES.json').exists() else {}
bad=[];patched=0
with zipfile.ZipFile(R/'pristine/upstream_snapshot.zip') as z:
 for n,h in m.items():
  if hashlib.sha256(z.read('BLNS_LAZER_BASELINE_20261014/'+n)).hexdigest()!=h:bad.append('snapshot:'+n)
  expected=p.get(n,{}).get('patched_sha256',h)
  if not (R/n).is_file() or hashlib.sha256((R/n).read_bytes()).hexdigest()!=expected:bad.append(n)
  patched+=n in p
for n,record in p.items():
 if 'added_sha256' in record and hashlib.sha256((R/n).read_bytes()).hexdigest()!=record['added_sha256']:bad.append(n)
 if n not in m and 'patched_sha256' in record:
  if hashlib.sha256((R/n).read_bytes()).hexdigest()!=record['patched_sha256']:bad.append(n)
  with zipfile.ZipFile(R/'lazer/third_party/Falcon-impl-20211101.zip') as z:
   if hashlib.sha256(z.read(record['archive_member'])).hexdigest()!=record['original_sha256']:bad.append('dependency:'+n)
if bad:raise SystemExit('SOURCE_INTEGRITY_FAILED: '+repr(bad))
print(f'SOURCE_INTEGRITY_OK: {len(m)} pristine hashes; {patched} documented modified files')
if (R/'FROZEN_SHA256.json').exists():
 from release_freeze import verify
 verify()
