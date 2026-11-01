/*
 * Unified benchmark worker for Argo (Argo et al. [3], ACM CCS 2024).
 * Supports three variants compiled from the same worker source via ARGO_VARIANT_NAME:
 *   - ARGO_NATIVE  : Upstream 10 attributes (PARAM_M=10, PARAM_M_SHOW_HID=10, PARAM_M1_SHOW=211), 0 disclosed
 *   - ARGO_PADDED  : Task-adapted 8 attributes, disclosing D={0,4,5} via public-target folding + witness zero-padding
 *                    (PARAM_M=8, PARAM_M_SHOW_HID=8, PARAM_M1_SHOW=203; Argo counterpart of LaZer B1/G3)
 *   - ARGO_COMPACT : Task-adapted 8 attributes, disclosing D={0,4,5} via public-target folding + witness column compaction
 *                    (PARAM_M=8, PARAM_M_SHOW_HID=5, PARAM_M1_SHOW=191; Argo counterpart of LaZer C3)
 * Lifecycles:
 *   - steady: caches credential-fixed subring embedding (`show_user_embed`) across repeated presentations
 *   - fresh : executes full `show_user_embed` + `show_user_prove` + wire serialization/deserialization + `show_verify`
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <time.h>
#include <math.h>
#include <sys/resource.h>

#include "arith.h"
#include "randombytes.h"
#include "random.h"
#include "sep.h"
#include "osig.h"
#include "show.h"
#include "fips202.h"

#ifndef ARGO_VARIANT_NAME
#define ARGO_VARIANT_NAME "ARGO_COMPACT"
#endif

extern long argo_last_attempts;

static double now_ms(void) {
  struct timespec ts;
  clock_gettime(CLOCK_MONOTONIC, &ts);
  return (double)ts.tv_sec * 1000.0 + (double)ts.tv_nsec / 1e6;
}

static double cpu_ms(void) {
  struct timespec ts;
  clock_gettime(CLOCK_PROCESS_CPUTIME_ID, &ts);
  return (double)ts.tv_sec * 1000.0 + (double)ts.tv_nsec / 1e6;
}

#include "argo_wire.h"
#include "argo_public.h"
#define ARGO_RAW_PROOF_BYTES REVIEWED_WIRE_BYTES

typedef struct {
  sep_sk_t sk;
  sep_pk_t pk;
  user_sk_t usk;
  user_pk_t upk;
  sep_sig_t sig;
  poly_q_vec_d r[2];
  poly_q_vec_d cmt;
  poly_qshow_vec_m1 s1;
  poly_qshow_vec_k u_embed[PARAM_D];
  poly_qshow_mat_k_k A_embed[PARAM_D][PARAM_D];
  poly_qshow_mat_k_k B_embed[PARAM_D][PARAM_D * PARAM_K];
  poly_qshow_mat_k_k A3_embed[PARAM_D][PARAM_K];
  poly_qshow_mat_k_k Ds_embed[PARAM_D][2 * PARAM_D];
  poly_qshow_mat_k_k D_embed[PARAM_D][PARAM_M_SHOW_HID];
  uint8_t state[STATE_BYTES];
  uint8_t msg[PARAM_M * PARAM_N / 8];
  uint8_t crs_seed[CRS_SEED_BYTES];
} argo_session_t;

static void session_init(argo_session_t *s) {
  int i, j;
  sep_keys_init(&s->pk, &s->sk);
  user_keys_init(&s->upk, &s->usk);
  sep_sig_init(&s->sig);
  poly_q_vec_d_init(s->r[0]);
  poly_q_vec_d_init(s->r[1]);
  poly_q_vec_d_init(s->cmt);
  poly_qshow_vec_m1_init(s->s1);
  for (i = 0; i < PARAM_D; i++) {
    poly_qshow_vec_k_init(s->u_embed[i]);
    for (j = 0; j < PARAM_D; j++) {
      poly_qshow_mat_k_k_init(s->A_embed[i][j]);
      poly_qshow_mat_k_k_init(s->Ds_embed[i][j]);
      poly_qshow_mat_k_k_init(s->Ds_embed[i][j + PARAM_D]);
    }
    for (j = 0; j < PARAM_D * PARAM_K; j++) {
      poly_qshow_mat_k_k_init(s->B_embed[i][j]);
    }
    for (j = 0; j < PARAM_K; j++) {
      poly_qshow_mat_k_k_init(s->A3_embed[i][j]);
    }
    for (j = 0; j < PARAM_M_SHOW_HID; j++) {
      poly_qshow_mat_k_k_init(s->D_embed[i][j]);
    }
  }
}

static void session_clear(argo_session_t *s) {
  int i, j;
  sep_keys_clear(&s->pk, &s->sk);
  user_keys_clear(&s->upk, &s->usk);
  sep_sig_clear(&s->sig);
  poly_q_vec_d_clear(s->r[0]);
  poly_q_vec_d_clear(s->r[1]);
  poly_q_vec_d_clear(s->cmt);
  poly_qshow_vec_m1_clear(s->s1);
  for (i = 0; i < PARAM_D; i++) {
    poly_qshow_vec_k_clear(s->u_embed[i]);
    for (j = 0; j < PARAM_D; j++) {
      poly_qshow_mat_k_k_clear(s->A_embed[i][j]);
      poly_qshow_mat_k_k_clear(s->Ds_embed[i][j]);
      poly_qshow_mat_k_k_clear(s->Ds_embed[i][j + PARAM_D]);
    }
    for (j = 0; j < PARAM_D * PARAM_K; j++) {
      poly_qshow_mat_k_k_clear(s->B_embed[i][j]);
    }
    for (j = 0; j < PARAM_K; j++) {
      poly_qshow_mat_k_k_clear(s->A3_embed[i][j]);
    }
    for (j = 0; j < PARAM_M_SHOW_HID; j++) {
      poly_qshow_mat_k_k_clear(s->D_embed[i][j]);
    }
  }
}

static void session_issue(argo_session_t *s, const sep_pk_t *issuer_pk, const sep_sk_t *issuer_sk) {
  int i;
  randombytes(s->state, STATE_BYTES);
  randombytes(s->crs_seed, CRS_SEED_BYTES);
  memset(s->msg, 0, sizeof(s->msg));
#if PARAM_M == 10
  randombytes(s->msg, sizeof(s->msg));
#else
  for (i = 0; i < PARAM_M; i++) randombytes(&s->msg[i * (PARAM_N / 8)], 8);
#endif
  osig_user_keygen(&s->upk, &s->usk, issuer_pk->seed);
  osig_user_commit(s->r, s->cmt, s->msg, &s->upk);
  osig_signer_sign_commitment(&s->sig, s->state, issuer_sk, issuer_pk, s->cmt);
  osig_user_sig_complete(&s->sig, s->r);
}

int main(int argc, char **argv) {
  if (argc != 4 && argc != 5) {
    fprintf(stderr, "usage: %s sessions warmup steady|fresh\n", argv[0]);
    return 2;
  }
  const int no_cache = argc == 5 && strcmp(argv[4], "no-cache") == 0;
  if(argc==5 && !no_cache)return 2;
  const char *reported_variant = no_cache ? ARGO_VARIANT_NAME "_NOCACHE" : ARGO_VARIANT_NAME;
  const int n = atoi(argv[1]);
  const int w = atoi(argv[2]);
  const char *life = argv[3];
  const int is_steady = (strcmp(life, "steady") == 0);
  const int is_fresh = (strcmp(life, "fresh") == 0);
  if (n <= 0 || w < 0 || (!is_steady && !is_fresh)) {
    fprintf(stderr, "invalid arguments\n");
    return 2;
  }

  arith_setup();
  random_init();

  sep_pk_t issuer_pk;
  sep_sk_t issuer_sk;
  sep_keys_init(&issuer_pk, &issuer_sk);
  sep_keygen(&issuer_pk, &issuer_sk);

  argo_session_t persistent;
  public_statement_t public_cache;
  if (is_steady) {
    session_init(&persistent);
    session_issue(&persistent, &issuer_pk, &issuer_sk);
  if(!no_cache) {
    show_user_embed(persistent.A_embed, persistent.B_embed, persistent.A3_embed,
                    persistent.Ds_embed, persistent.D_embed, persistent.u_embed,
                    persistent.s1, &persistent.upk, &persistent.usk,
                    &issuer_pk, &persistent.sig, persistent.msg);
    public_init(&public_cache);public_prepare(&public_cache,&issuer_pk,persistent.msg);
  }
  }

  const size_t wire_proof_bytes = REVIEWED_WIRE_BYTES;
  uint8_t *wire_buf = (uint8_t *)malloc(ARGO_RAW_PROOF_BYTES);
  if (!wire_buf) {
    fprintf(stderr, "malloc failed\n");
    return 2;
  }

  for (int i = -w; i < n; i++) {
    argo_session_t fresh_sess;
    argo_session_t *s = &persistent;
    if (is_fresh) {
      session_init(&fresh_sess);
      session_issue(&fresh_sess, &issuer_pk, &issuer_sk);
      s = &fresh_sess;
    }

    show_proof_t proof;
    show_proof_init(&proof);
    show_proof_t decoded;show_proof_init(&decoded);
    randombytes(s->crs_seed, CRS_SEED_BYTES);

    const double p0 = now_ms(), pc0 = cpu_ms();
    if (is_fresh || no_cache) {
      show_user_embed(s->A_embed, s->B_embed, s->A3_embed,
                      s->Ds_embed, s->D_embed, s->u_embed,
                      s->s1, &s->upk, &s->usk,
                      &issuer_pk, &s->sig, s->msg);
    }
    show_user_prove(&proof, s->A_embed, s->B_embed, s->A3_embed,
                    s->Ds_embed, s->D_embed, s->s1,
                    s->crs_seed, s->upk.seed);
    if(serialize_show_proof(wire_buf, &proof)!=wire_proof_bytes)return 2;
    const double pcpu = cpu_ms() - pc0;
    const double prove = now_ms() - p0;
    const long attempts = argo_last_attempts;

    const double v0 = now_ms(), vc0 = cpu_ms();
    public_statement_t fresh_public;
    public_statement_t *pub = &public_cache;
    if(is_fresh || no_cache) {
      public_init(&fresh_public);public_prepare(&fresh_public,&issuer_pk,s->msg);pub=&fresh_public;
    }
    int valid = deserialize_show_proof(&decoded,wire_buf,wire_proof_bytes)
                && public_verify(pub,&decoded,s->crs_seed,s->upk.seed);
    const double vcpu = cpu_ms() - vc0;
    const double verify = now_ms() - v0;

    if (!valid) {
      fprintf(stderr, "REVISION FAILED: honest Argo proof rejected\n");
      return 2;
    }

    if (i == -w) {
      if(deserialize_show_proof(&decoded,wire_buf,wire_proof_bytes+1) ||
         deserialize_show_proof(&decoded,wire_buf,wire_proof_bytes-1)) {
        fprintf(stderr,"invalid wire length accepted\n");return 2;
      }
      uint8_t saved[8];memcpy(saved,wire_buf,8);put64(wire_buf,(uint64_t)PARAM_Q_SHOW);
      if(deserialize_show_proof(&decoded,wire_buf,wire_proof_bytes)) {fprintf(stderr,"noncanonical coefficient accepted\n");return 2;}
      memcpy(wire_buf,saved,8);
      if(!deserialize_show_proof(&decoded,wire_buf,wire_proof_bytes))return 2;
      s->crs_seed[0]^=1;
      int bad_crs=public_verify(pub,&decoded,s->crs_seed,s->upk.seed);s->crs_seed[0]^=1;
      coeff_qshow c0=poly_qshow_get_coeff(decoded.c,0);
      poly_qshow_set_coeff(decoded.c,0,c0+1);
      int bad_c=public_verify(pub,&decoded,s->crs_seed,s->upk.seed);
      poly_qshow_set_coeff(decoded.c,0,c0);
      coeff_qshow u0=poly_qshow_get_coeff(pub->u[0]->entries[0],0);
      poly_qshow_set_coeff(pub->u[0]->entries[0],0,u0+1);
      int bad_statement=public_verify(pub,&decoded,s->crs_seed,s->upk.seed);
      poly_qshow_set_coeff(pub->u[0]->entries[0],0,u0);
      int bad_disclosure=0;
#if PARAM_M == 8
      uint8_t changed[PARAM_M*PARAM_N/8];memcpy(changed,s->msg,sizeof(changed));changed[0]^=1;
      public_statement_t changed_public;public_init(&changed_public);
      public_prepare(&changed_public,&issuer_pk,changed);
      bad_disclosure=public_verify(&changed_public,&decoded,s->crs_seed,s->upk.seed);
      public_clear(&changed_public);
#endif
      if(bad_crs || bad_c || bad_statement || bad_disclosure) {
        fprintf(stderr,"tampered Argo proof/public input accepted\n");return 2;
      }
    }

    uint8_t sha_out[32];
    shake256(sha_out, 32, wire_buf, ARGO_RAW_PROOF_BYTES);
    char sha_hex[65];
    for (int b = 0; b < 32; b++) sprintf(sha_hex + 2 * b, "%02x", sha_out[b]);
    sha_hex[64] = '\0';

    struct rusage ru;
    getrusage(RUSAGE_SELF, &ru);
    printf("REVJSON {\"index\":%d,\"warmup\":%s,\"status\":\"ACCEPTED\",\"variant\":\"%s\","
           "\"lifecycle\":\"%s\",\"prove_ms\":%.9f,\"verify_ms\":%.9f,\"show_ms\":%.9f,"
           "\"prove_cpu_ms\":%.9f,\"verify_cpu_ms\":%.9f,\"proof_bytes\":%zu,"
           "\"raw_packed_bytes\":%zu,\"K\":%ld,\"rss_kib\":%ld,\"m1\":%d,"
           "\"k\":%d,\"D\":%s,\"attribute_count\":%d,\"input_attribute_bytes\":%d,"
           "\"proof_sha\":\"%s\",\"verification_mode\":\"argo_native\","
           "\"proof_size_kind\":\"actual_fixed_width_wire\",\"verifier_input\":\"public_only\","
           "\"declared_security_target\":null,\"security_equivalence_established\":false}\n",
           i, (i < 0 ? "true" : "false"), reported_variant,
           life, prove, verify, prove + verify,
           pcpu, vcpu, wire_proof_bytes,
           (size_t)ARGO_RAW_PROOF_BYTES, attempts, ru.ru_maxrss, (int)PARAM_M1_SHOW,
           (PARAM_M==10?0:3), (PARAM_M==10?"[]":"[0,4,5]"), (int)PARAM_M, (PARAM_M==10?32:8), sha_hex);
    fflush(stdout);

    show_proof_clear(&decoded);
    if(is_fresh || no_cache)public_clear(&fresh_public);
    show_proof_clear(&proof);
    if (is_fresh) {
      session_clear(&fresh_sess);
    }
  }

  free(wire_buf);
  if (is_steady) {
    if(!no_cache)public_clear(&public_cache);
    session_clear(&persistent);
  }
  sep_keys_clear(&issuer_pk, &issuer_sk);
  arith_teardown();
  return 0;
}
