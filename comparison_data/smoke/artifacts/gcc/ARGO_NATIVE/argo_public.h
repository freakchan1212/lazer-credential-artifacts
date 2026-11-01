/* Reconstruct verifier statement from issuer public key and disclosed input.
 * No signature, holder secret, or hidden attribute is read here.
 */
#ifndef REVIEWED_ARGO_PUBLIC_H
#define REVIEWED_ARGO_PUBLIC_H
#include "poly_q_sampling.h"
typedef struct {
  poly_qshow_mat_k_k A[PARAM_D][PARAM_D],B[PARAM_D][PARAM_D*PARAM_K],A3[PARAM_D][PARAM_K];
  poly_qshow_mat_k_k Ds[PARAM_D][2*PARAM_D],D[PARAM_D][PARAM_M_SHOW_HID];
  poly_qshow_vec_k u[PARAM_D];
} public_statement_t;
static void public_init(public_statement_t *v) {
 for(size_t i=0;i<PARAM_D;i++){
  poly_qshow_vec_k_init(v->u[i]);
  for(size_t j=0;j<PARAM_D;j++)poly_qshow_mat_k_k_init(v->A[i][j]);
  for(size_t j=0;j<PARAM_D*PARAM_K;j++)poly_qshow_mat_k_k_init(v->B[i][j]);
  for(size_t j=0;j<PARAM_K;j++)poly_qshow_mat_k_k_init(v->A3[i][j]);
  for(size_t j=0;j<2*PARAM_D;j++)poly_qshow_mat_k_k_init(v->Ds[i][j]);
  for(size_t j=0;j<PARAM_M_SHOW_HID;j++)poly_qshow_mat_k_k_init(v->D[i][j]);
 }
}
static void public_clear(public_statement_t *v) {
 for(size_t i=0;i<PARAM_D;i++){
  poly_qshow_vec_k_clear(v->u[i]);
  for(size_t j=0;j<PARAM_D;j++)poly_qshow_mat_k_k_clear(v->A[i][j]);
  for(size_t j=0;j<PARAM_D*PARAM_K;j++)poly_qshow_mat_k_k_clear(v->B[i][j]);
  for(size_t j=0;j<PARAM_K;j++)poly_qshow_mat_k_k_clear(v->A3[i][j]);
  for(size_t j=0;j<2*PARAM_D;j++)poly_qshow_mat_k_k_clear(v->Ds[i][j]);
  for(size_t j=0;j<PARAM_M_SHOW_HID;j++)poly_qshow_mat_k_k_clear(v->D[i][j]);
 }
}
static void public_prepare(public_statement_t *v,const sep_pk_t *pk,const uint8_t msg[PARAM_M*PARAM_N/8]) {
 poly_q_mat_d_d A,Ds[2];poly_q_mat_d_k A3;poly_q_mat_d_m D;
 poly_q_vec_d u;poly_q m,tmp;
 poly_q_mat_d_d_init(A);poly_q_mat_d_d_init(Ds[0]);poly_q_mat_d_d_init(Ds[1]);
 poly_q_mat_d_k_init(A3);poly_q_mat_d_m_init(D);poly_q_vec_d_init(u);poly_q_init(m);poly_q_init(tmp);
 poly_q_mat_d_d_uniform(A,pk->seed,DOMAIN_SEPARATOR_A,0);
 poly_q_mat_d_k_uniform(A3,pk->seed,DOMAIN_SEPARATOR_A3);
 poly_q_mat_d_d_uniform(Ds[0],pk->seed,DOMAIN_SEPARATOR_DS,0);
 poly_q_mat_d_d_uniform(Ds[1],pk->seed,DOMAIN_SEPARATOR_DS,PARAM_D);
 poly_q_mat_d_m_uniform(D,pk->seed,DOMAIN_SEPARATOR_D);
 poly_q_vec_d_uniform(u,pk->seed,DOMAIN_SEPARATOR_U);
#if PARAM_M==8
 const size_t disc[3]={0,4,5};
 for(size_t j=0;j<3;j++){
  poly_q_from_bits(m,&msg[disc[j]*(PARAM_N/8)]);
  for(size_t i=0;i<PARAM_D;i++){
   poly_q_mul(tmp,D->rows[i]->entries[disc[j]],m);
   poly_q_add(u->entries[i],u->entries[i],tmp);
  }
 }
#endif
 for(size_t i=0;i<PARAM_D;i++){
  poly_qshow_subring_embed_vec_k(v->u[i],u->entries[i],PARAM_Q1_SHOW);
  for(size_t j=0;j<PARAM_D;j++){
   poly_qshow_subring_embed_mat_k_k(v->A[i][j],A->rows[i]->entries[j],PARAM_Q1_SHOW);
   poly_qshow_subring_embed_mat_k_k(v->Ds[i][j],Ds[0]->rows[i]->entries[j],PARAM_Q1_SHOW);
   poly_qshow_subring_embed_mat_k_k(v->Ds[i][j+PARAM_D],Ds[1]->rows[i]->entries[j],PARAM_Q1_SHOW);
  }
  for(size_t j=0;j<PARAM_D*PARAM_K;j++)poly_qshow_subring_embed_mat_k_k(v->B[i][j],pk->B[j/PARAM_D]->rows[i]->entries[j%PARAM_D],PARAM_Q1_SHOW);
  for(size_t j=0;j<PARAM_K;j++)poly_qshow_subring_embed_mat_k_k(v->A3[i][j],A3->rows[i]->entries[j],PARAM_Q1_SHOW);
#if PARAM_M==10
  for(size_t j=0;j<PARAM_M;j++)poly_qshow_subring_embed_mat_k_k(v->D[i][j],D->rows[i]->entries[j],PARAM_Q1_SHOW);
#elif PARAM_M_SHOW_HID==8
  for(size_t j=0;j<PARAM_M;j++){
   if(j==0||j==4||j==5)poly_qshow_mat_k_k_zero(v->D[i][j]);
   else poly_qshow_subring_embed_mat_k_k(v->D[i][j],D->rows[i]->entries[j],PARAM_Q1_SHOW);
  }
#else
  const size_t hid[5]={1,2,3,6,7};
  for(size_t j=0;j<5;j++)poly_qshow_subring_embed_mat_k_k(v->D[i][j],D->rows[i]->entries[hid[j]],PARAM_Q1_SHOW);
#endif
 }
 poly_q_clear(m);poly_q_clear(tmp);poly_q_vec_d_clear(u);poly_q_mat_d_m_clear(D);
 poly_q_mat_d_k_clear(A3);poly_q_mat_d_d_clear(A);poly_q_mat_d_d_clear(Ds[0]);poly_q_mat_d_d_clear(Ds[1]);
}
static int public_verify(const public_statement_t *v,const show_proof_t *p,const uint8_t *crs,const uint8_t *seed){
 return show_verify(p,v->A,v->B,v->A3,v->Ds,v->D,v->u,crs,seed);
}
#endif
