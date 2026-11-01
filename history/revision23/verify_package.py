#!/usr/bin/env python3
"""Validate only delivered source files; generated results/builds are separate."""
import json
from revision_common import ROOT,sha
m=json.loads((ROOT/'PACKAGE_MANIFEST.json').read_text())
bad=[rel for rel,h in m['files'].items() if not (ROOT/rel).is_file() or sha(ROOT/rel)!=h]
if bad:raise SystemExit('PACKAGE MODIFIED: '+repr(bad))
print('PACKAGE VERIFIED:',len(m['files']),'source/documentation files')
