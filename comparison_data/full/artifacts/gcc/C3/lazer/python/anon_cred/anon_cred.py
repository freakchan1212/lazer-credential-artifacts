import sys
sys.path.append('..')   # path to lazer module
from lazer import *     # import lazer modules
import hashlib          # for SHAKE128
import secrets          # for internal coins
import sys
import time

try:
    from _anon_cred_params_cffi import lib
except ModuleNotFoundError:
    import importlib.util, os, sysconfig
    _so = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_anon_cred_params_cffi" + (sysconfig.get_config_var("EXT_SUFFIX") or ".so"))
    _spec = importlib.util.spec_from_file_location("_anon_cred_params_cffi", _so)
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    lib = _mod.lib
from anon_cred_p1_params import mod, deg, wl2

# 64-deg ring
RING = polyring_t(deg, mod)

# public randomness
shake128 = hashlib.shake_128(bytes.fromhex("00"))
BLINDSIGPP = shake128.digest(32)
shake128 = hashlib.shake_128(bytes.fromhex("01"))
P1PP = shake128.digest(32)
shake128 = hashlib.shake_128(bytes.fromhex("02"))
P2PP = shake128.digest(32)

# expand blindsig public parameters from seeds
#BND = int((mod-1)/2)
AR=polymat_t.urandom_static(RING,8,16,mod,BLINDSIGPP,1)
AM=polymat_t.urandom_static(RING,8,8,mod,BLINDSIGPP,2)
ATAU=polymat_t.urandom_static(RING,8,8,mod,BLINDSIGPP,3)
B1 = polymat_t.identity(RING,8)


class InvalidMaskedMsg(Exception):
    pass


class InvalidBlindSig(Exception):
    pass


class InvalidSignature(Exception):
    pass


AR.redc(); AM.redc(); ATAU.redc(); B1.redc()
A_P1_STATIC = polymat_t(RING, 8, 24, [AR, AM])


AR.redc(); AM.redc(); ATAU.redc(); B1.redc()


class user_t:
    def __init__(self, pk: falcon_pkenc):
        self.B2 = falcon_decode_pk(pk,RING) #
        self.B2.redc()
        self._B2_h2 = falcon_decode_pk(pk,RING)
        self.p1_prover = lin_prover_state_t(P1PP, lib.get_params("p1_param"))
        self.p2_prover = lin_prover_state_t(P2PP, lib.get_params("p2_compact3_param"))
        self.p2_prover_full = None
        self._p2_compact_provers = {3: self.p2_prover}
        self._p2_compact_cached_keys = {3: None}
        self.p1_prover.set_statement_A(A_P1_STATIC)
        self._p2_cached_pub_key = None
        self._p2_full_cached_pub_key = None
        self._verified_blindsig_cache = None

    def maskmsg(self, msg: bytes):
        m = polyvec_t(RING,8,msg)
        seed = secrets.token_bytes(32)  # internal coins
        logsigma = 1                    # sigma = 1.55*2^logsigma
        l2sqr_bnd = wl2[0] * wl2[0]     # l2(r1,r2)^2
        r=polyvec_t.grandom_static(RING,16,logsigma,seed,0,0,l2sqr_bnd)
        t = AR*r + AM*m

        # prove [Ar,Am]*(r,m) + (-t) = 0
        # as PoK(w): Aw + u = 0
        u = polyvec_t(RING, 8, [-t])
        w = polyvec_t(RING, 24, [r, m])
   
        self.p1_prover.set_statement_t(u)
        self.p1_prover.set_witness(w)
        
        proof = self.p1_prover.prove()

        # encode t
        coder = coder_t()
        coder.enc_begin(22000)
        coder.enc_urandom(mod, t)
        tenc = coder.enc_end()

        # save randomness and message
        self.r = r
        self.m = m
        self._verified_blindsig_cache = None
        # return masked message t,p1enc
        return tenc + proof

    def verify_blindsig(self, blindsig: bytes):
        """BLNS23 Fig. 19 H2 check: decode and validate (tau, s1, s2) from issuer without mutating self.B2."""
        if self._verified_blindsig_cache is not None and self._verified_blindsig_cache[0] == blindsig:
            return self._verified_blindsig_cache[1:]
        tau, s1, s2 = bytes(64), polyvec_t(RING,8), polyvec_t(RING,8)
        try:
            coder = coder_t()
            coder.dec_begin(blindsig)
            coder.dec_bytes(tau)
            coder.dec_grandom(165, s1)
            coder.dec_grandom(165, s2)
            blindsig_len = coder.dec_end()
        except DecodingError:
            raise InvalidBlindSig("Blind signature decoding failed.")
        if blindsig_len != len(blindsig):
            raise InvalidBlindSig("Trailing bytes in blind signature.")
        tau_ = polyvec_t(RING, 8, tau)
        if s1.l2sqr() + s2.l2sqr() > 34034726:
            raise InvalidBlindSig("Blind signature (s1, s2) l2-norm exceeds bound.")
        if hasattr(self, "r") and hasattr(self, "m"):
            lhs = B1 * s1.copy() + self._B2_h2 * s2.copy()
            rhs = AR * self.r.copy() + AM * self.m.copy() + ATAU * tau_.copy()
            if lhs != rhs:
                raise InvalidBlindSig("Blind signature linear relation check failed.")
        self._verified_blindsig_cache = (blindsig, tau_, s1, s2)
        return tau_, s1, s2

    def sign(self, blindsig: bytes, pub_mvec: list):
        # decode and H2-validate blindsig tau,s1,s2
        tau_, s1, s2 = self.verify_blindsig(blindsig)
        pub_mvec = list(dict.fromkeys(pub_mvec))

        # prove [Ar,Atau,-B1,-B2]*(r,tau,s1,s2) + Am*m = 0
        # as PoK(w): Aw + u = 0
        if len(pub_mvec)==0:
            u=polyvec_t(RING,8)
        else:
            m_pub=self.m.get_pol_list(pub_mvec)
            AM_pub=AM.get_col_list(pub_mvec)
            u=polyvec_t(RING, 8, [AM_pub * m_pub])

        pub_key = tuple(pub_mvec)
        pub_set = set(pub_mvec)
        k_disc = len(pub_set)
        if 1 <= k_disc <= 8 and k_disc == len(pub_mvec) and all(0 <= idx < 8 for idx in pub_set):
            h_priv = 8 - k_disc
            priv_indices = [i for i in range(8) if i not in pub_set]
            if k_disc == 3:
                prover = self.p2_prover
                if self._p2_cached_pub_key != pub_key:
                    AM_priv_compact = AM.get_col_list(priv_indices)
                    A = polymat_t(RING, 8, 45, [AR, ATAU, -B1, -self.B2, AM_priv_compact])
                    prover.set_statement_A(A)
                    self._p2_cached_pub_key = pub_key
            else:
                prover = self._p2_compact_provers.get(k_disc)
                if prover is None:
                    prover = lin_prover_state_t(P2PP, lib.get_params(f"p2_compact{k_disc}_param"))
                    self._p2_compact_provers[k_disc] = prover
                    self._p2_compact_cached_keys[k_disc] = None
                if self._p2_compact_cached_keys.get(k_disc) != pub_key:
                    if h_priv > 0:
                        AM_priv_compact = AM.get_col_list(priv_indices)
                        A = polymat_t(RING, 8, 40 + h_priv, [AR, ATAU, -B1, -self.B2, AM_priv_compact])
                    else:
                        A = polymat_t(RING, 8, 40, [AR, ATAU, -B1, -self.B2])
                    prover.set_statement_A(A)
                    self._p2_compact_cached_keys[k_disc] = pub_key
            if h_priv > 0:
                m_priv_compact = self.m.get_pol_list(priv_indices)
                w = polyvec_t(RING, 40 + h_priv, [self.r, tau_, s1, s2, m_priv_compact])
            else:
                w = polyvec_t(RING, 40, [self.r, tau_, s1, s2])
            prover.set_statement_t(u)
            prover.set_witness(w)
            proof = prover.prove()
        else:
            if self.p2_prover_full is None:
                self.p2_prover_full = lin_prover_state_t(P2PP, lib.get_params("p2_param"))
            m_priv = self.m.zero_out_pols(pub_mvec)
            if self._p2_full_cached_pub_key != pub_key:
                AM_priv = AM.zero_out_cols(pub_mvec)
                A = polymat_t(RING, 8, 48, [AR, ATAU, -B1, -self.B2, AM_priv])
                self.p2_prover_full.set_statement_A(A)
                self._p2_full_cached_pub_key = pub_key
            w = polyvec_t(RING, 48, [self.r, tau_, s1, s2, m_priv])
            self.p2_prover_full.set_statement_t(u)
            self.p2_prover_full.set_witness(w)
            proof = self.p2_prover_full.prove()

        return proof


class signer_t:
    def __init__(self, pk: falcon_pkenc, sk: falcon_skenc):
        self.sk = sk
        self.p1_verifier = lin_verifier_state_t(P1PP, lib.get_params("p1_param"))
        self.p1_verifier.set_statement_A(A_P1_STATIC)

    def sign(self, masked_msg: bytes, strict: bool = False):
        # decode masked message
        t = polyvec_t(RING,8)
        try:
            coder = coder_t()
            coder.dec_begin(masked_msg)
            coder.dec_urandom(mod, t)
            tlen = coder.dec_end()
        except DecodingError:
            raise InvalidMaskedMsg
        
        # verify proof for PoK(w): Aw + u = 0
        u = polyvec_t(RING, 8, [-t])
        proof = masked_msg[tlen:]

        self.p1_verifier.set_statement_t(u)
        try:
            self.p1_verifier.verify(proof, strict=strict)
        except VerificationError:
            raise InvalidMaskedMsg("Masked message invalid.")

        # internal coins
        tau_ = secrets.token_bytes(64)
        tau = polyvec_t(RING,8,tau_)

        # preimage sampling
        s1, s2 = falcon_preimage_sample(self.sk, ATAU * tau + t,RING)
        #s1, s2 = falcon_preimage_sample(self.sk, ATAU * tau + t)

        # encode blindsig tau,s1,s2
        coder = coder_t()
        coder.enc_begin(2000)
        coder.enc_bytes(tau_)
        coder.enc_grandom(165, s1)
        coder.enc_grandom(165, s2)
        blindsig = coder.enc_end()

        return blindsig


class verifier_t:
    def __init__(self, pk: falcon_pkenc):
        self.B2 = falcon_decode_pk(pk,RING)
        self.B2.redc()
        self.p2_verifier = lin_verifier_state_t(P2PP, lib.get_params("p2_compact3_param"))
        self.p2_verifier_full = None
        self._p2_compact_verifiers = {3: self.p2_verifier}
        self._p2_compact_cached_keys = {3: None}
        self._p2_cached_pub_key = None
        self._p2_full_cached_pub_key = None

    #the private part should already be zeroed out in pub_msg 
    def verify(self, pub_msg: bytes, pub_mvec:list, sig: bytes, strict: bool = False):
        if strict:
            if len(pub_msg) != 64:
                raise InvalidSignature("Public message container must be 64 bytes.")
            pub_set = set(pub_mvec)
            if len(pub_set) != len(pub_mvec) or any(i < 0 or i >= 8 for i in pub_mvec):
                raise InvalidSignature("Invalid disclosed attribute indices.")
            for i in range(8):
                if i not in pub_set and any(pub_msg[i*8:(i+1)*8]):
                    raise InvalidSignature("Undisclosed attribute slot in pub_msg is non-zero.")
        pub_mvec = list(dict.fromkeys(pub_mvec))
        m = polyvec_t(RING, 8, pub_msg)
        if len(pub_mvec)==0:
            u=polyvec_t(RING,8)
        else:
            m_pub=m.get_pol_list(pub_mvec)
            AM_pub=AM.get_col_list(pub_mvec)
            u=polyvec_t(RING, 8, [AM_pub * m_pub])

        # verify proof for PoK(w): Aw + u = 0
        pub_key = tuple(pub_mvec)
        pub_set = set(pub_mvec)
        k_disc = len(pub_set)
        proof = sig
        if 1 <= k_disc <= 8 and k_disc == len(pub_mvec) and all(0 <= idx < 8 for idx in pub_set):
            h_priv = 8 - k_disc
            priv_indices = [i for i in range(8) if i not in pub_set]
            if k_disc == 3:
                verifier = self.p2_verifier
                if self._p2_cached_pub_key != pub_key:
                    AM_priv_compact = AM.get_col_list(priv_indices)
                    A = polymat_t(RING, 8, 45, [AR, ATAU, -B1, -self.B2, AM_priv_compact])
                    verifier.set_statement_A(A)
                    self._p2_cached_pub_key = pub_key
            else:
                verifier = self._p2_compact_verifiers.get(k_disc)
                if verifier is None:
                    verifier = lin_verifier_state_t(P2PP, lib.get_params(f"p2_compact{k_disc}_param"))
                    self._p2_compact_verifiers[k_disc] = verifier
                    self._p2_compact_cached_keys[k_disc] = None
                if self._p2_compact_cached_keys.get(k_disc) != pub_key:
                    if h_priv > 0:
                        AM_priv_compact = AM.get_col_list(priv_indices)
                        A = polymat_t(RING, 8, 40 + h_priv, [AR, ATAU, -B1, -self.B2, AM_priv_compact])
                    else:
                        A = polymat_t(RING, 8, 40, [AR, ATAU, -B1, -self.B2])
                    verifier.set_statement_A(A)
                    self._p2_compact_cached_keys[k_disc] = pub_key
            verifier.set_statement_t(u)
            try:
                verifier.verify(proof, strict=strict)
            except VerificationError:
                raise InvalidSignature("Signature invalid.")
        else:
            if self.p2_verifier_full is None:
                self.p2_verifier_full = lin_verifier_state_t(P2PP, lib.get_params("p2_param"))
            if self._p2_full_cached_pub_key != pub_key:
                AM_priv = AM.zero_out_cols(pub_mvec)
                A = polymat_t(RING, 8, 48, [AR, ATAU, -B1, -self.B2, AM_priv])
                self.p2_verifier_full.set_statement_A(A)
                self._p2_full_cached_pub_key = pub_key
            self.p2_verifier_full.set_statement_t(u)
            try:
                self.p2_verifier_full.verify(proof, strict=strict)
            except VerificationError:
                raise InvalidSignature("Signature invalid.")

    def verify_strict(self, pub_msg: bytes, pub_mvec: list, sig: bytes):
        return self.verify(pub_msg, pub_mvec, sig, strict=True)


# demo
def main():
    print("lazer anonymous credentials demo")
    print("--------------------------\n")

    msg = bytes.fromhex(
        "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef")
    sk, pk, _ = falcon_keygen()

    pub_mvec=[0,4,5]
    priv_mvec=list(set(range(8))-set(pub_mvec))

    print("Initialize user with public key ... ", end='')
    user = user_t(pk)
    print("[OK]\n")

    print("Initialize signer with public and private key ... ", end='')
    signer = signer_t(pk, sk)
    print("[OK]\n")

    print("Initialize verifier with public key ... ", end='')
    verifier = verifier_t(pk)
    print("[OK]\n")

    issue_start=time.perf_counter()
    print("User outputs masked credentials (including a proof of well-formedness) ... ", end='')
    masked_msg = user.maskmsg(msg)
    print("[OK]\n")


    print_stopwatch_lnp_prover_prove(0)
    print(f"masked credentials (t,P1): {len(masked_msg)} bytes\n")

    print("Signer checks the proof and if it verifies outputs blinded credentials ... ", end='')
    try:
        blindsig = signer.sign(masked_msg)
    except InvalidMaskedMsg:
        print("masked credentials are invalid.")
        sys.exit(1)
    print("[OK]\n")
    issue_end=time.perf_counter()
    print(f"blind credentials (tau,s1,s2): {len(blindsig)} bytes\n")

    show_start=time.perf_counter()
    print("User outputs a signature on the hidden credentials ... ", end='')
    try:
        sig = user.sign(blindsig,pub_mvec)
    except InvalidBlindSig:
        print("decoding failed.")
        sys.exit(1)
    print("[OK]\n")

    print(f"signature (P2): {len(sig)} bytes\n")

    print("Verfifier verifies the signature of the blinded credentials ... ", end='')
    try:
        msg_pub=zero_out_bytes(msg,priv_mvec,RING.deg//8)
        verifier.verify(msg_pub,pub_mvec,sig)
    except InvalidSignature:
        print("signature invalid.")
        sys.exit(1)
    print("[OK]\n")
    show_end=time.perf_counter()
    print_stopwatch_lnp_prover_prove(0)
    print("Issue time: ",-issue_start+issue_end)
    print("Show time: ",-show_start+show_end)

if __name__ == "__main__":
    main()
