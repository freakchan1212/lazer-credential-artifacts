#!/usr/bin/env python3
import argparse, hashlib, json, resource, secrets, time, traceback
from pathlib import Path

IMPORT_START = time.perf_counter_ns()
import baseline_api as b
IMPORT_MS = (time.perf_counter_ns() - IMPORT_START) / 1e6
if not b.HAS_HOOKS:
    raise RuntimeError('Build the metrics native counters first: bash 01_build.sh')


def emit(x):
    print(json.dumps(x, sort_keys=True), flush=True)


def timed(fn):
    b.reset_counts()
    w = time.perf_counter_ns()
    c = time.process_time_ns()
    value = fn()
    return value, (time.perf_counter_ns() - w) / 1e6, (time.process_time_ns() - c) / 1e6, b.counts(), b.fastpath_counts()


def benchmark(a):
    (sk, pk, _), keyms, keycpu, _, _ = timed(b.ac.falcon_keygen)
    state = None
    setup = {}

    def prepare():
        row = {}
        user, row['user_init_ms'], row['user_init_cpu_ms'], _, _ = timed(lambda: b.ac.user_t(pk))
        issuer, row['issuer_init_ms'], row['issuer_init_cpu_ms'], _, _ = timed(lambda: b.ac.signer_t(pk, sk))
        verifier, row['verifier_init_ms'], row['verifier_init_cpu_ms'], _, _ = timed(lambda: b.ac.verifier_t(pk))
        msg = secrets.token_bytes(64)
        req, row['p1_prove_ms'], row['p1_prove_cpu_ms'], row['p1_counters'], row['p1_fastpath'] = timed(lambda: user.maskmsg(msg))
        blind, row['p1_verify_and_issue_ms'], row['p1_verify_and_issue_cpu_ms'], row['issue_counters'], _ = timed(lambda: issuer.sign(req))
        row.update(
            issue_flow_ms=row['p1_prove_ms'] + row['p1_verify_and_issue_ms'],
            masked_request_bytes=len(req),
            blind_credential_bytes=len(blind),
            issuance_payload_total_bytes=len(req) + len(blind),
        )
        return (user, verifier, msg, blind), row

    if a.lifecycle == 'steady':
        state, setup = prepare()
    emit({
        'event': 'setup',
        'module_import_and_public_parameter_expansion_ms': IMPORT_MS,
        'keygen_ms': keyms,
        'keygen_cpu_ms': keycpu,
        'issuer_public_key_encoded_bytes': 897,
        'issuer_secret_key_encoded_bytes': 1281,
        'issuer_public_key_buffer_bytes': b.lz.ffi.sizeof(pk.ptr),
        'issuer_secret_key_buffer_bytes': b.lz.ffi.sizeof(sk.ptr),
        'steady_credential_setup': setup,
        'public_disclosed_bytes': 24,
        'public_container_bytes': 64,
        'public_parameter_seed_bytes': len(b.ac.BLINDSIGPP) + len(b.ac.P1PP) + len(b.ac.P2PP),
        'process_peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    })
    seen = set()
    proof_digests = set()
    for i in range(-a.warmup, a.sessions):
        emit({'event': 'start', 'index': i})
        row = {'event': 'sample', 'index': i, 'warmup': i < 0, 'profile': a.profile, 'lifecycle': a.lifecycle, 'status': 'RUNNING'}
        w = time.perf_counter_ns()
        try:
            if a.lifecycle == 'fresh':
                state, prepared = prepare()
                row.update(prepared)
            user, verifier, msg, blind = state
            ctx = None
            presentation, row['p2_prove_ms'], row['p2_prove_cpu_ms'], row['p2_counters'], row['p2_fastpath'] = timed(lambda: b.show(user, blind, pk, a.profile, ctx))
            pub = b.public_message(msg)
            _, row['p2_verify_ms'], row['p2_verify_cpu_ms'], _, _ = timed(lambda: b.verify(verifier, pub, pk, a.profile, presentation, ctx, seen))
            proof = presentation
            d = hashlib.sha256(proof).hexdigest()
            if d in proof_digests:
                raise RuntimeError('Duplicate presentation proof in fresh-randomness check')
            proof_digests.add(d)
            row.update(
                status='HONEST_ACCEPTED',
                show_flow_ms=row['p2_prove_ms'] + row['p2_verify_ms'],
                presentation_proof_bytes=len(proof),
                presentation_payload_minimal_bytes=len(proof) + 24,
                presentation_api_input_bytes=len(proof) + 64,
                proof_sha256=d,
            )
            row['deadline_exceeded'] = row['show_flow_ms'] > a.deadline_ms
        except Exception as e:
            row.update(status='HONEST_FAILED', error_type=type(e).__name__, error=str(e))
        row['trial_wall_ms'] = (time.perf_counter_ns() - w) / 1e6
        row['deadline_exceeded'] = row.get('show_flow_ms', row['trial_wall_ms']) > a.deadline_ms
        row['process_peak_rss_kib'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        emit(row)
    emit({'event': 'done', 'status': 'COMPLETED', 'process_peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss})


CASES = {
    'raw_honest': 'ACCEPT',
    'raw_repeat_same_proof': 'ACCEPT_ORIGINAL_BEHAVIOR',
    'raw_changed_public_attribute': 'REJECT',
    'raw_wrong_issuer': 'REJECT',
    'raw_bitflip': 'REJECT',
    'raw_wrong_disclosure': 'REJECT',
    'raw_trailing': 'ACCEPT_ORIGINAL_BEHAVIOR',
    'raw_hidden_slot_injection': 'ACCEPT_ORIGINAL_BEHAVIOR',
    'p1_bitflip': 'REJECT',
}


def attack(name):
    sk, pk, _ = b.ac.falcon_keygen()
    user, issuer, v, msg, req, blind = b.issue(pk, sk)
    proof = user.sign(blind, b.PUBLIC)
    pub = b.public_message(msg)
    v.verify(pub, b.PUBLIC, proof)
    fn = lambda: v.verify(pub, b.PUBLIC, proof)
    if name == 'raw_changed_public_attribute':
        x = bytearray(pub)
        x[0] ^= 1
        fn = lambda: v.verify(bytes(x), b.PUBLIC, proof)
    elif name == 'raw_wrong_issuer':
        _, pk2, _ = b.ac.falcon_keygen()
        v2 = b.ac.verifier_t(pk2)
        fn = lambda: v2.verify(pub, b.PUBLIC, proof)
    elif name == 'raw_bitflip':
        x = bytearray(proof)
        x[len(x) // 2] ^= 1
        fn = lambda: v.verify(pub, b.PUBLIC, bytes(x))
    elif name == 'raw_wrong_disclosure':
        fn = lambda: v.verify(pub, [0, 1, 5], proof)
    elif name == 'raw_trailing':
        fn = lambda: v.verify(pub, b.PUBLIC, proof + b'x')
    elif name == 'raw_hidden_slot_injection':
        x = bytearray(pub)
        x[8] = 1
        fn = lambda: v.verify(bytes(x), b.PUBLIC, proof)
    elif name == 'p1_bitflip':
        x = bytearray(req)
        x[len(x) // 2] ^= 1
        fn = lambda: issuer.sign(bytes(x))
    start = time.perf_counter_ns()
    try:
        fn()
        actual = 'ACCEPT'
        error = None
    except (b.ac.InvalidSignature, b.ac.InvalidMaskedMsg, b.lz.VerificationError, ValueError) as e:
        actual = 'REJECT'
        error = type(e).__name__
    except Exception as e:
        actual = 'ERROR'
        error = type(e).__name__ + ': ' + str(e)
    expected = CASES[name]
    passed = actual == ('ACCEPT' if expected.startswith('ACCEPT') else expected)
    emit({'event': 'attack', 'case': name, 'expected': expected, 'actual': actual, 'passed': passed, 'elapsed_ms': (time.perf_counter_ns() - start) / 1e6, 'error': error, 'evidence': 'original upstream API behavior; no added rejection checks; not a cryptographic security proof'})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--task', choices=['benchmark', 'attack'], required=True)
    ap.add_argument('--profile', choices=['raw'], default='raw')
    ap.add_argument('--lifecycle', choices=['fresh', 'steady'], default='fresh')
    ap.add_argument('--sessions', type=int, default=3)
    ap.add_argument('--warmup', type=int, default=1)
    ap.add_argument('--deadline-ms', type=float, default=250)
    ap.add_argument('--case', choices=list(CASES))
    a = ap.parse_args()
    if a.task == 'benchmark':
        benchmark(a)
    else:
        attack(a.case)


if __name__ == '__main__':
    main()
