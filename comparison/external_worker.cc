// Measurement adapter for pqzk-blns (Margaria et al. [12], IEEE ISCC 2025).
// Native-HM and task-adapted padded/compact measurement adapters.
// Bit-mapped inputs do not add binary witness constraints to the upstream proof.
// Steady NOCACHE vs steady PADDED isolates this adapter's preprocessing cache.
// Fresh vs steady also changes credential lifecycle; neither equals all LaZer B1->G3 changes.
#include "params.h"
#include "Issuer.h"
#include "Holder.h"
#include "Verifier.h"
#include <chrono>
#include <fstream>
#include <iomanip>
#include <stdexcept>
#include <sys/resource.h>
#include <ctime>
#include <sstream>
#include "shake128.h"

extern long idx_Com, idx_ISIS;
extern size_t revision_last_proof_bytes;
extern bool revision_binary_hm;

static double now_ms() {
  return std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now().time_since_epoch()).count();
}
static double cpu_ms() {
  struct timespec ts;
  if(clock_gettime(CLOCK_PROCESS_CPUTIME_ID,&ts)) throw std::runtime_error("CPU clock");
  return ts.tv_sec*1000.0+ts.tv_nsec/1e6;
}

static string proof_fingerprint(const uint8_t* data,size_t length){
  shake128_state_t state;uint8_t digest[32];
  _shake128_init(&state);_shake128_absorb(&state,data,length);_shake128_squeeze(&state,digest,sizeof(digest));
  std::ostringstream out;out<<std::hex<<std::setfill('0');
  for(auto b:digest)out<<std::setw(2)<<static_cast<unsigned>(b);
  return out.str();
}

struct Session {
  CRS2_t crs;
  mat_zz_p bf;
  CRED_t cred;
  Vec<string> attrs;
  uint8_t seed[SEED_LEN];
};

struct CachedState {
  mat_zz_p mul_P;
  mat_zz_p mul_C;
  mat_zz_p mul_Bf;
  vec_zz_p coeffs_m_idx;
  vec_ZZ Bounds;
  Vec<vec_ZZ> sig_w0;
  vec_UL idx_hid_used;
  long num_idx_pub;
};

static void issue_cred(Session& s, const uint8_t* ipk, const ISK_t& isk, const vec_UL& pub, bool padded_crs) {
  const long crs_hid = padded_crs ? l0 : (l0 - pub.length());
  H_Init(s.crs, s.bf, s.seed, s.attrs, crs_hid);
  for(long j=0; j<l0; j++) {
    unsigned char a[8];
    GenRandBytes(a, 8);
    s.attrs[j] = string((char*)a, 8);
  }
  STATE_t state;
  RHO1_t r1{};
  uint8_t* r2 = nullptr;
  // Issuance uses standard compact blind commitment
  CRS2_t issue_crs;
  mat_zz_p issue_bf;
  if (padded_crs) {
    Hcrs(issue_crs, issue_bf, s.seed, l0 - pub.length());
  }
  const CRS2_t& crs_use = padded_crs ? issue_crs : s.crs;
  const mat_zz_p& bf_use = padded_crs ? issue_bf : s.bf;
  H_VerCred1(r1, state, s.seed, crs_use, ipk, s.attrs, pub);
  Vec<string> visible = s.attrs;
  auto hidden = Compute_idx_hid(pub);
  for(auto &i: hidden) visible[i] = "0";
  I_VerCred(&r2, s.seed, crs_use, bf_use, ipk, isk, visible, pub, r1);
  if(!r2) throw std::runtime_error("issuance returned no signature");
  H_VerCred2(s.cred, ipk, bf_use, &r2, state);
  if (padded_crs) {
    s.bf = issue_bf;
  }
  if(!s.cred.valid) throw std::runtime_error("invalid issued credential");
}

static void build_presentation_state(
    CachedState& st,
    const Session& s,
    const uint8_t* ipk_bytes,
    const vec_UL& idx_pub,
    bool padded_mode, bool with_witness = true)
{
  ulong i, j, k;
  IPK_t ipk;
  vec_zz_pX a;
  vec_ZZ m_i, coeffs_m, coeffs_s, coeffs_r, r_vect, coeffs_u;
  mat_zz_p P, C0, C1, C;

  const ulong num_idx_pub = idx_pub.length();
  const vec_UL idx_hid_real = Compute_idx_hid(idx_pub);
  vec_UL idx_hid_eff;
  if (padded_mode) {
    // Keep all 8 attribute blocks in the witness (5 hidden + 3 zero-padded disclosed blocks)
    idx_hid_eff.SetLength(l0);
    for (i = 0; i < (ulong)idx_hid_real.length(); i++) idx_hid_eff[i] = idx_hid_real[i];
    for (i = 0; i < num_idx_pub; i++) idx_hid_eff[idx_hid_real.length() + i] = idx_pub[i];
  } else {
    idx_hid_eff = idx_hid_real;
  }

  const ulong num_hid_blocks = idx_hid_eff.length();
  const ulong idxhlrd = (num_hid_blocks * h0) + (lr0 * d0);
  const ulong m2d = (m0 + 2) * d0;
  const ulong total_c_cols = (num_idx_pub + num_hid_blocks) * h0 + (lr0 * d0);

  CompleteIPK(ipk, ipk_bytes);

  coeffs_m.SetLength(l0 * h0);
  k = 0;
  clear(coeffs_m);
  for(i = 0; i < l0; i++) {
    bool is_public=false;for(auto idx: idx_pub)if(idx==i)is_public=true;
    if(!with_witness && !is_public){k+=h0;continue;}
    HM(m_i, s.attrs[i]);
    for(j = 0; j < h0; j++) {
      coeffs_m[k++] = m_i[j];
    }
  }

  a.SetLength(m0 + 2);
  a[0].SetLength(d0);
  a[0] = zz_pX(1);
  a[1] = ipk.a1;
  for(i = 0; i < m0; i++) a[2 + i] = ipk.a2[i];

  P.SetDims(d0, m2d + d_hat);
  rot_vect(P, a);

  C.SetDims(d0, total_c_cols + d_hat);
  C0.SetDims(d0, lm0 * d0);
  rot_vect(C0, ipk.c0);

  k = 0;
  // First copy disclosed attribute columns for public m_C inner product
  for(auto &idx: idx_pub) {
    for(j = idx * h0; j < (idx + 1) * h0; j++) {
      for(i = 0; i < d0; i++) C[i][k] = C0[i][j];
      k++;
    }
  }
  // Next copy hidden attribute columns
  for(auto &idx: idx_hid_real) {
    for(j = idx * h0; j < (idx + 1) * h0; j++) {
      for(i = 0; i < d0; i++) C[i][k] = C0[i][j];
      k++;
    }
  }
  // In padded mode, append 3 zero-padded attribute blocks (3 * h0 columns of zeros)
  if (padded_mode) {
    for(ulong z = 0; z < num_idx_pub * h0; z++) {
      for(i = 0; i < d0; i++) C[i][k] = zz_p(0);
      k++;
    }
  }
  C0.kill();

  C1.SetDims(d0, lr0 * d0);
  rot_vect(C1, ipk.c1);
  for(j = 0; j < lr0 * d0; j++) {
    for(i = 0; i < d0; i++) C[i][k] = C1[i][j];
    k++;
  }
  C1.kill();

  st.coeffs_m_idx.SetLength(num_idx_pub * h0);
  k = 0;
  for(auto &idx: idx_pub) {
    for(i = idx * h0; i < (idx + 1) * h0; i++) {
      st.coeffs_m_idx[k++] = conv<zz_p>(coeffs_m[i]);
    }
  }

  st.Bounds.SetLength(2);
  st.Bounds[0] = ZZ(sigma2) * ZZ((m0 + 2) * d0);
  st.Bounds[1] = sqr(ZZ(psi0)) * ZZ(idx_hid_real.length() * h0 + lr0 * d0);

  if(with_witness) {
  coeffs_s.SetLength(m2d + d_hat);
  CoeffsX(coeffs_s, s.cred.s, m0 + 2);

  r_vect.SetLength(idxhlrd + d_hat);
  coeffs_r.SetLength(lr0 * d0);
  CoeffsX(coeffs_r, s.cred.r, lr0);

  k = 0;
  for(auto &idx: idx_hid_real) {
    for(j = idx * h0; j < (idx + 1) * h0; j++) {
      r_vect[k++] = coeffs_m[j];
    }
  }
  if (padded_mode) {
    for(ulong z = 0; z < num_idx_pub * h0; z++) {
      r_vect[k++] = ZZ(0);
    }
  }
  for(j = 0; j < lr0 * d0; j++) {
    r_vect[k++] = coeffs_r[j];
  }

  coeffs_u.SetLength(t0);
  for(i = 0; i < t0; i++) {
    coeffs_u[i] = bit(s.cred.x - 1, i);
  }

  st.sig_w0.SetLength(3);
  st.sig_w0[0] = coeffs_s;
  st.sig_w0[1] = r_vect;
  st.sig_w0[2] = coeffs_u;
  }
  st.idx_hid_used = idx_hid_eff;
  st.num_idx_pub = static_cast<long>(num_idx_pub);

  long mul = long(q2_hat) / long(q0);
  {
    zz_pPush push(q2_hat);
    st.mul_P = mul * P;
    st.mul_C = mul * C;
    st.mul_Bf = mul * s.bf;
  }
  P.kill();
  C.kill();
}

int main(int argc, char** argv) {
 try {
  if(argc < 4 || argc > 5) throw std::runtime_error("usage: worker sessions warmup steady|fresh [PQZK_BLNS|PQZK_BLNS_PADDED|PQZK_BLNS_COMPACT]");
  const int n = std::stoi(argv[1]), w = std::stoi(argv[2]);
  const string life = argv[3];
  const string variant = (argc == 5) ? string(argv[4]) : "PQZK_BLNS";
  if(n <= 0 || w < 0 || (life != "steady" && life != "fresh")) throw std::runtime_error("bad arguments");
  if(variant != "PQZK_BLNS" && variant != "PQZK_BLNS_PADDED" && variant != "PQZK_BLNS_COMPACT" && variant != "PQZK_BLNS_PADDED_NOCACHE")
    throw std::runtime_error("unknown pqzk-blns variant: " + variant);

  const bool binary_mode = (variant != "PQZK_BLNS");
  const bool no_cache = (variant == "PQZK_BLNS_PADDED_NOCACHE");
  const bool padded_mode = (variant == "PQZK_BLNS_PADDED" || no_cache);
  revision_binary_hm = binary_mode;

  unsigned char entropy[32];
  std::ifstream ur("/dev/urandom", std::ios::binary);
  ur.read((char*)entropy, 32);
  if(ur.gcount() != 32) throw std::runtime_error("OS entropy unavailable");
  SetSeed(ZZFromBytes(entropy, 32));
  zz_p::init(q0);
  vec_UL pub = conv<vec_UL>("[0 4 5]");
  ISK_t isk;
  uint8_t* ipk = nullptr;
  I_KeyGen(&ipk, isk);

  Session* persistent = nullptr;
  CachedState* cached_st = nullptr;
  CachedState* cached_verifier_st = nullptr;
  if(life == "steady") {
    persistent = new Session;
    issue_cred(*persistent, ipk, isk, pub, padded_mode);
    if (binary_mode && !no_cache) {
      cached_st = new CachedState;
      build_presentation_state(*cached_st, *persistent, ipk, pub, padded_mode);
      cached_verifier_st = new CachedState;
      build_presentation_state(*cached_verifier_st, *persistent, ipk, pub, padded_mode, false);
    }
  }

  for(int i = -w; i < n; i++) {
    Session* s = persistent;
    if(life == "fresh") {
      s = new Session;
      issue_cred(*s, ipk, isk, pub, padded_mode);
    }
    uint8_t nonce[NONCE_LEN];
    GenRandBytes(nonce, NONCE_LEN);

    double prove = 0.0, pcpu = 0.0, verify = 0.0, vcpu = 0.0;
    size_t size = 0;
    string proof_hash;
    long attempts = 0;

    if (!binary_mode) {
      // Original upstream stateless H_VerPres / V_Verify
      VP_t vp{};
      const double p0 = now_ms(), pc0 = cpu_ms();
      H_VerPres(vp, s->cred, nonce, s->seed, s->crs, ipk, s->bf, s->attrs, pub);
      pcpu = cpu_ms() - pc0;
      prove = now_ms() - p0;
      size = revision_last_proof_bytes;
      attempts = idx_ISIS;
      if(!vp.valid || !vp.Pi || !size) throw std::runtime_error("invalid proof");

      const double v0 = now_ms(), vc0 = cpu_ms();
      const long valid = V_Verify(vp, nonce, s->seed, s->crs, s->bf, pub);
      vcpu = cpu_ms() - vc0;
      verify = now_ms() - v0;
      if(valid != 1) throw std::runtime_error("honest proof rejected");

      if(i == -w) {
        nonce[0] ^= 1;
        const long bad = V_Verify(vp, nonce, s->seed, s->crs, s->bf, pub);
        nonce[0] ^= 1;
        if(bad == 1) throw std::runtime_error("altered nonce accepted");
      }
      proof_hash=proof_fingerprint(vp.Pi,size);
      delete[] vp.Pi;
    } else {
      // Input-bit-mapped PADDED (m1=74) or COMPACT (m1=71) mode, with steady state caching vs fresh rebuild
      uint8_t* Pi = nullptr;
      CachedState local_st;
      CachedState* st_use = cached_st;

      const double p0 = now_ms(), pc0 = cpu_ms();
      if (life == "fresh" || no_cache) {
        build_presentation_state(local_st, *s, ipk, pub, padded_mode);
        st_use = &local_st;
      }
      {
        zz_pPush push(q2_hat);
        Prove_ISIS(&Pi, nonce, s->seed, s->crs[0], ipk,
                   st_use->mul_P, st_use->mul_C, st_use->coeffs_m_idx, st_use->mul_Bf,
                   st_use->Bounds, st_use->num_idx_pub, st_use->sig_w0, st_use->idx_hid_used);
      }
      pcpu = cpu_ms() - pc0;
      prove = now_ms() - p0;
      size = revision_last_proof_bytes;
      attempts = idx_ISIS;
      if(!Pi || !Pi[0] || !size) throw std::runtime_error("invalid aligned proof");

      const double v0 = now_ms(), vc0 = cpu_ms();
      CachedState v_st;
      const CachedState* vst_use = cached_verifier_st;
      if (life == "fresh" || no_cache) {
        build_presentation_state(v_st, *s, ipk, pub, padded_mode, false);
        vst_use = &v_st;
      }
      long valid = 0;
      {
        zz_pPush push(q2_hat);
        valid = Verify_ISIS(nonce, s->seed, s->crs[0], ipk,
                            vst_use->mul_P, vst_use->mul_C, vst_use->coeffs_m_idx, vst_use->mul_Bf,
                            vst_use->Bounds, vst_use->num_idx_pub, &Pi, vst_use->idx_hid_used);
      }
      vcpu = cpu_ms() - vc0;
      verify = now_ms() - v0;
      if(valid != 1) throw std::runtime_error("honest aligned proof rejected");

      if(i == -w) {
        nonce[0] ^= 1;
        long bad = 0;
        {
          zz_pPush push(q2_hat);
          bad = Verify_ISIS(nonce, s->seed, s->crs[0], ipk,
                            vst_use->mul_P, vst_use->mul_C, vst_use->coeffs_m_idx, vst_use->mul_Bf,
                            vst_use->Bounds, vst_use->num_idx_pub, &Pi, vst_use->idx_hid_used);
        }
        nonce[0] ^= 1;
        if(bad == 1) throw std::runtime_error("altered nonce accepted in aligned mode");
        // Rebuild only public inputs after changing a disclosed attribute.
        const string saved_attr=s->attrs[0];
        s->attrs[0][0]^=1;
        CachedState wrong_public;
        build_presentation_state(wrong_public,*s,ipk,pub,padded_mode,false);
        s->attrs[0]=saved_attr;
        {
          zz_pPush push(q2_hat);
          bad=Verify_ISIS(nonce,s->seed,s->crs[0],ipk,
                          wrong_public.mul_P,wrong_public.mul_C,wrong_public.coeffs_m_idx,wrong_public.mul_Bf,
                          wrong_public.Bounds,wrong_public.num_idx_pub,&Pi,wrong_public.idx_hid_used);
        }
        if(bad==1)throw std::runtime_error("altered disclosed attribute accepted");
        Pi[size/2]^=1;
        {
          zz_pPush push(q2_hat);
          bad=Verify_ISIS(nonce,s->seed,s->crs[0],ipk,
                          vst_use->mul_P,vst_use->mul_C,vst_use->coeffs_m_idx,vst_use->mul_Bf,
                          vst_use->Bounds,vst_use->num_idx_pub,&Pi,vst_use->idx_hid_used);
        }
        Pi[size/2]^=1;
        if(bad==1)throw std::runtime_error("altered serialized proof accepted");
      }
      proof_hash=proof_fingerprint(Pi,size);
      delete[] Pi;
    }

    struct rusage ru;
    if(getrusage(RUSAGE_SELF, &ru)) throw std::runtime_error("rusage");
    cout << std::setprecision(15) << "REVJSON {\"index\":" << i
         << ",\"warmup\":" << (i < 0 ? "true" : "false")
         << ",\"status\":\"ACCEPTED\",\"variant\":\"" << variant
         << "\",\"lifecycle\":\"" << life
         << "\",\"prove_ms\":" << prove
         << ",\"verify_ms\":" << verify
         << ",\"show_ms\":" << prove + verify
         << ",\"prove_cpu_ms\":" << pcpu
         << ",\"verify_cpu_ms\":" << vcpu
         << ",\"proof_bytes\":" << size
         << ",\"proof_sha\":\"" << proof_hash << "\",\"proof_hash_kind\":\"SHAKE128-256bit\""
         << ",\"K\":" << attempts
         << ",\"rss_kib\":" << ru.ru_maxrss
         << ",\"k\":3,\"D\":[0,4,5],\"attribute_count\":8,\"input_attribute_bytes\":8"
         << ",\"verification_mode\":\"external_native\",\"proof_size_kind\":\"actual_serialized\",\"declared_security_target\":null"
         << ",\"security_equivalence_established\":false}" << endl;
    if(life == "fresh") delete s;
  }
  delete cached_st;
  delete cached_verifier_st;
  delete persistent;
  delete[] ipk;
  return 0;
 } catch(const std::exception& e) {
  cerr << "REVISION FAILED: " << e.what() << endl;
  return 2;
 }
}
