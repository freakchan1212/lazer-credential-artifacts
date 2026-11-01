/* Audited explicit fixed-width proof transport; not an entropy-size estimate. */
#ifndef REVIEWED_ARGO_WIRE_H
#define REVIEWED_ARGO_WIRE_H
static void put64(uint8_t *p, uint64_t x) {
  for (size_t i=0;i<8;i++) p[i]=(uint8_t)(x>>(8*i));
}
static uint64_t get64(const uint8_t *p) {
  uint64_t x=0; for(size_t i=0;i<8;i++) x|=(uint64_t)p[i]<<(8*i); return x;
}
static void wire_poly(uint8_t *p, const poly_qshow x) {
  for(size_t i=0;i<PARAM_N_SHOW;i++) put64(p+8*i,(uint64_t)poly_qshow_get_coeff(x,i));
}
static int read_poly(poly_qshow x,const uint8_t *p) {
  poly_qshow_zero(x);
  for(size_t i=0;i<PARAM_N_SHOW;i++) {
    uint64_t v=get64(p+8*i); if(v>=(uint64_t)PARAM_Q_SHOW) return 0;
    poly_qshow_set_coeff(x,i,(coeff_qshow)v);
  }
  return 1;
}
#define REVIEWED_WIRE_BYTES ((PARAM_D_SHOW+PARAM_ARP_DIV_N_L_SHOW+PARAM_L_SHOW+2+PARAM_M1_SHOW+PARAM_M2_SHOW)*PARAM_N_SHOW*8+PARAM_ARP_SHOW*8+4)
static size_t serialize_show_proof(uint8_t *buf, const show_proof_t *p) {
  size_t o=0;
#define WRITE_POLY(x) do {wire_poly(buf+o,(x));o+=PARAM_N_SHOW*8;} while(0)
  for(size_t i=0;i<PARAM_D_SHOW;i++) WRITE_POLY(p->tA->entries[i]);
  for(size_t i=0;i<PARAM_ARP_DIV_N_L_SHOW;i++) WRITE_POLY(p->tB->entries[i]);
  for(size_t i=0;i<PARAM_ARP_SHOW;i++){put64(buf+o,(uint64_t)p->z3[i]);o+=8;}
  for(size_t i=0;i<PARAM_L_SHOW;i++) WRITE_POLY(p->h->entries[i]);
  WRITE_POLY(p->t1); WRITE_POLY(p->c);
  for(size_t i=0;i<4;i++)buf[o++]=(uint8_t)(p->ctr_c>>(8*i));
  for(size_t i=0;i<PARAM_M1_SHOW;i++)WRITE_POLY(p->z1->entries[i]);
  for(size_t i=0;i<PARAM_M2_SHOW;i++)WRITE_POLY(p->z2->entries[i]);
#undef WRITE_POLY
  return o;
}
static int deserialize_show_proof(show_proof_t *p,const uint8_t *buf,size_t len) {
  if(len!=REVIEWED_WIRE_BYTES)return 0;
  size_t o=0;
#define READ_POLY(x) do {if(!read_poly((x),buf+o))return 0;o+=PARAM_N_SHOW*8;}while(0)
  for(size_t i=0;i<PARAM_D_SHOW;i++)READ_POLY(p->tA->entries[i]);
  for(size_t i=0;i<PARAM_ARP_DIV_N_L_SHOW;i++)READ_POLY(p->tB->entries[i]);
  for(size_t i=0;i<PARAM_ARP_SHOW;i++){
    uint64_t v=get64(buf+o);o+=8;
    p->z3[i]=(v>>63)?-(int64_t)(~v)-1:(int64_t)v;
  }
  for(size_t i=0;i<PARAM_L_SHOW;i++)READ_POLY(p->h->entries[i]);
  READ_POLY(p->t1);READ_POLY(p->c);
  p->ctr_c=0;for(size_t i=0;i<4;i++)p->ctr_c|=(uint32_t)buf[o++]<<(8*i);
  for(size_t i=0;i<PARAM_M1_SHOW;i++)READ_POLY(p->z1->entries[i]);
  for(size_t i=0;i<PARAM_M2_SHOW;i++)READ_POLY(p->z2->entries[i]);
#undef READ_POLY
  return o==len;
}
#endif
