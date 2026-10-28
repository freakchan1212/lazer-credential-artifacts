#!/usr/bin/env python3
"""Create/check the release source manifest and AUDIT_DELIVERY_MANIFEST.json; generated measurements are excluded."""
import argparse, hashlib, json
from pathlib import Path

R = Path(__file__).resolve().parent


def paths():
    for p in sorted(R.rglob('*')):
        if not p.is_file():
            continue
        rel = p.relative_to(R)
        if rel.parts[0] in ['.venv', '.build', '.deps', '.compat-bin', 'logs', 'results', 'verification_release', '__pycache__']:
            continue
        if '__pycache__' in rel.parts or 'build' in rel.parts:
            continue
        if p.suffix in ['.o', '.so', '.a', '.pyc', '.stderr'] or p.name == '.params_cffi_sha256':
            continue
        if rel.as_posix().startswith(('lazer/third_party/hexl-development/', 'lazer/third_party/Falcon-impl-20211101/')):
            continue
        if p.name in ['FROZEN_SHA256.json', 'DELIVERY_SHA256.json', 'AUDIT_DELIVERY_MANIFEST.json', '.e4.lock'] or p.name.startswith(('lazer_metrics_results_', 'original_baseline_results_')):
            continue
        if rel.parts[0] == 'lazer' and rel.as_posix() not in json.loads((R / 'UPSTREAM_SHA256.json').read_text()):
            continue
        yield p


def sync_audit_delivery_manifest():
    manifest_path = R / 'AUDIT_DELIVERY_MANIFEST.json'
    if not manifest_path.exists():
        return
    m = json.loads(manifest_path.read_text())
    m['package_name'] = 'LaZer_E4_Supplement'
    files = m.get('files', {})
    for rel in list(files.keys()):
        if (R / rel).is_file():
            files[rel] = hashlib.sha256((R / rel).read_bytes()).hexdigest()
        else:
            del files[rel]
    for ref_p in sorted((R / 'reference_user').glob('*')):
        if ref_p.is_file():
            files[ref_p.relative_to(R).as_posix()] = hashlib.sha256(ref_p.read_bytes()).hexdigest()
    for extra in ['switch_variant.py', 'compare_all_variants.py', 'verify_e2_all.py', '20_run_all_6_variants.sh', '21_run_single_variant.sh', '22_run_interleaved_ablation.sh']:
        if (R / extra).is_file():
            files[extra] = hashlib.sha256((R / extra).read_bytes()).hexdigest()
    m['files'] = files
    manifest_path.write_text(json.dumps(m, ensure_ascii=False, indent=2) + '\n')


def verify():
    m = json.loads((R / 'FROZEN_SHA256.json').read_text())
    bad = [n for n, h in m['files'].items() if not (R / n).is_file() or hashlib.sha256((R / n).read_bytes()).hexdigest() != h]
    if bad:
        raise SystemExit('FROZEN_RELEASE_HASH_FAILED: ' + repr(bad))
    manifest_path = R / 'AUDIT_DELIVERY_MANIFEST.json'
    if manifest_path.is_file():
        adm = json.loads(manifest_path.read_text())
        bad_adm = [n for n, h in adm.get('files', {}).items() if not (R / n).is_file() or hashlib.sha256((R / n).read_bytes()).hexdigest() != h]
        if bad_adm:
            raise SystemExit('AUDIT_DELIVERY_MANIFEST_HASH_FAILED: ' + repr(bad_adm))
    print(f"FROZEN_RELEASE_HASH_OK: {len(m['files'])} files; {m['baseline_id']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--create', action='store_true')
    a = ap.parse_args()
    if a.create:
        sync_audit_delivery_manifest()
        m = {
            'baseline_id': 'LAZER-E4-SUPPLEMENT-20261018',
            'display_name': 'LaZer E4 supplement',
            'files': {p.relative_to(R).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths()},
        }
        (R / 'FROZEN_SHA256.json').write_text(json.dumps(m, ensure_ascii=False, indent=2) + '\n')
    verify()


if __name__ == '__main__':
    main()
