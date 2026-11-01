#!/usr/bin/env python3
"""Optional independent Sage/Lattice-Estimator runner; never mutates baseline results."""
import argparse, json, shutil, subprocess, sys
from pathlib import Path

R = Path(__file__).resolve().parent
CODE = r'''
import json, sys
sys.path.insert(0, sys.argv[1])
from estimator import LWE, SIS
from estimator.lwe_parameters import LWEParameters
from estimator.sis_parameters import SISParameters
from estimator.nd import CenteredBinomial, UniformMod
from estimator.reduction import ADPS16
out = {}
for label, params in [
    ("P1_MSIS", SISParameters(n=17 * 64, q=2199023256889, length_bound=19660535, m=80 * 64)),
    ("P2_MSIS_m1_48", SISParameters(n=20 * 64, q=1125899906843221, length_bound=1246260582373, m=114 * 64)),
    ("P2_MSIS_m1_45", SISParameters(n=20 * 64, q=1125899906843221, length_bound=1212803025534, m=111 * 64)),
]:
    out[label] = {
        mode: str(SIS.lattice(params, red_cost_model=ADPS16(mode=mode)))
        for mode in ["classical", "quantum"]
    }
for label, params in [
    ("P1_MLWE", LWEParameters(n=26 * 64, q=2199023256889, Xs=UniformMod(3), Xe=UniformMod(3), m=29 * 64)),
    ("P2_MLWE", LWEParameters(n=32 * 64, q=1125899906843221, Xs=UniformMod(3), Xe=UniformMod(3), m=32 * 64)),
    ("Credential_NTRU_LWE_proxy", LWEParameters(n=512, q=12289, Xs=CenteredBinomial(1), Xe=CenteredBinomial(1), m=512)),
]:
    out[label] = {
        mode: str(LWE.primal_usvp(params, red_cost_model=ADPS16(mode=mode)))
        for mode in ["classical", "quantum"]
    }
print(json.dumps(out, indent=2))
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', type=Path, default=R / 'results/sage_security_optional.json')
    a = ap.parse_args()
    sage = shutil.which('sage')
    if not sage:
        print('SAGE_NOT_INSTALLED: default GSA/Core-SVP security metrics were already generated without Sage.')
        raise SystemExit(2)
    p = subprocess.run([sage, '-python', '-c', CODE, str(R / 'vendor/lattice-estimator')], text=True, capture_output=True, check=True)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(p.stdout)
    print('SAGE_SECURITY_WRITTEN:', a.output)


if __name__ == '__main__':
    main()
