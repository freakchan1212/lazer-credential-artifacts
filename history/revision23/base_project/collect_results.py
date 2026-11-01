#!/usr/bin/env python3
import datetime, zipfile
from pathlib import Path

R = Path(__file__).resolve().parent
out = R / f"lazer_metrics_results_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
    for folder in ['results', 'logs', 'reference_user', 'variants_patches']:
        if (R / folder).exists():
            for p in sorted((R / folder).rglob('*')):
                if p.is_file() and p.suffix in ['.json', '.jsonl', '.csv', '.md', '.html', '.txt', '.log', '.stderr', '.patch']:
                    z.write(p, p.relative_to(R))
    for n in [
        'ACTIVE_VARIANT.json', 'PROVENANCE.json', 'UPSTREAM_SHA256.json', 'PATCHES.json',
        'SOURCE_CHANGES.diff', 'BLNS23_AUDIT_SOURCE_DIFF.patch',
        'BLNS23_AUDIT_PATCH_NOTES_ZH.md', 'BLNS23_1_2_3_RUN_ZH.md',
        'AUDIT_DELIVERY_MANIFEST.json', 'ORIGINAL_FROZEN_SHA256_REFERENCE.json',
        'README_ZH.md', 'SECURITY_SCOPE_ZH.md', 'metric_contract.json',
        'FROZEN_SHA256.json', 'FREEZE_ACCEPTANCE_ZH.md', 'METRIC_COVERAGE_ZH.md',
        'PAPERS_ZH.md', 'KNOWN_SCOPE.json',
        'switch_variant.py', 'compare_all_variants.py', 'verify_e2_all.py',
    ]:
        if (R / n).exists():
            z.write(R / n, n)
print('RESULT_PACKAGE:', out)
print('Send this ZIP back. No issuer secret keys or credential witnesses are included.')
