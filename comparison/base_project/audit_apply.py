#!/usr/bin/env python3
"""Idempotent BLNS23 bugfixes + multi-variant optimization applier (delegates to switch_variant.py)."""
import os
from switch_variant import apply_variant


def run():
    variant = os.environ.get('LAZER_VARIANT', 'V0')
    apply_variant(variant, update_freeze=False)
    print('AUDIT_PATCH_APPLIED_AND_HASHED')


if __name__ == '__main__':
    run()
