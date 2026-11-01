// Measurement adapter for pqzk-blns, upstream Apache-2.0 implementation.
// Protocol sources unchanged except task parameters and proof-length observation.
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
extern long idx_Com, idx_ISIS;
extern size_t revision_last_proof_bytes;
static double now_ms() {
  return std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now().time_since_epoch()).count();
}
static double cpu_ms() {
  struct timespec ts; if(clock_gettime(CLOCK_PROCESS_CPUTIME_ID,&ts)) throw std::runtime_error("CPU clock");
  return ts.tv_sec*1000.0+ts.tv_nsec/1e6;
}
struct Session {
  CRS2_t crs; mat_zz_p bf; CRED_t cred; Vec<string> attrs;
  uint8_t seed[SEED_LEN];
};
static void issue(Session& s,const uint8_t* ipk,const ISK_t& isk,const vec_UL& pub) {
  H_Init(s.crs,s.bf,s.seed,s.attrs,l0-pub.length());
  // Eight input attributes of eight random bytes each. Upstream hashes each string;
  // this is task alignment, NOT identical encoding to LaZer's binary witness.
  for(long j=0;j<l0;j++) { unsigned char a[8]; GenRandBytes(a,8);s.attrs[j]=string((char*)a,8); }
  STATE_t state; RHO1_t r1{}; uint8_t* r2=nullptr;
  H_VerCred1(r1,state,s.seed,s.crs,ipk,s.attrs,pub);
  Vec<string> visible=s.attrs; auto hidden=Compute_idx_hid(pub);
  for(auto &i:hidden) visible[i]="0";
  I_VerCred(&r2,s.seed,s.crs,s.bf,ipk,isk,visible,pub,r1);
  if(!r2) throw std::runtime_error("issuance returned no signature");
  H_VerCred2(s.cred,ipk,s.bf,&r2,state);
  if(!s.cred.valid) throw std::runtime_error("invalid issued credential");
}
int main(int argc,char**argv) {
 try {
  if(argc!=4) throw std::runtime_error("usage: worker sessions warmup steady|fresh");
  const int n=std::stoi(argv[1]),w=std::stoi(argv[2]); const string life=argv[3];
  if(n<=0||w<0||(life!="steady"&&life!="fresh")) throw std::runtime_error("bad arguments");
  // Explicit OS entropy, no deterministic seed in performance runs.
  unsigned char entropy[32];std::ifstream ur("/dev/urandom",std::ios::binary);
  ur.read((char*)entropy,32); if(ur.gcount()!=32)throw std::runtime_error("OS entropy unavailable");
  SetSeed(ZZFromBytes(entropy,32));
  zz_p::init(q0); vec_UL pub=conv<vec_UL>("[0 4 5]");
  ISK_t isk;uint8_t* ipk=nullptr;I_KeyGen(&ipk,isk);
  Session* persistent=nullptr;
  if(life=="steady") { persistent=new Session;issue(*persistent,ipk,isk,pub); }
  for(int i=-w;i<n;i++) {
   Session* s=persistent;
   if(life=="fresh") {s=new Session;issue(*s,ipk,isk,pub);}
   uint8_t nonce[NONCE_LEN];GenRandBytes(nonce,NONCE_LEN); VP_t vp{};
   const double p0=now_ms(),pc0=cpu_ms();
   H_VerPres(vp,s->cred,nonce,s->seed,s->crs,ipk,s->bf,s->attrs,pub);
   const double pcpu=cpu_ms()-pc0,prove=now_ms()-p0;
   const size_t size=revision_last_proof_bytes;const long attempts=idx_ISIS;
   if(!vp.valid||!vp.Pi||!size)throw std::runtime_error("invalid proof");
   const double v0=now_ms(),vc0=cpu_ms();
   const long valid=V_Verify(vp,nonce,s->seed,s->crs,s->bf,pub);
   const double vcpu=cpu_ms()-vc0,verify=now_ms()-v0;
   if(valid!=1)throw std::runtime_error("honest proof rejected");
   // Out-of-timing regression on the FIRST warm-up (or first sample if no warm-up).
   if(i==-w) {
    nonce[0]^=1;const long bad=V_Verify(vp,nonce,s->seed,s->crs,s->bf,pub);nonce[0]^=1;
    if(bad==1)throw std::runtime_error("altered nonce accepted");
   }
   struct rusage ru;if(getrusage(RUSAGE_SELF,&ru))throw std::runtime_error("rusage");
   cout<<std::setprecision(15)<<"REVJSON {\"index\":"<<i<<",\"warmup\":"<<(i<0?"true":"false")
       <<",\"status\":\"ACCEPTED\",\"variant\":\"PQZK_BLNS\",\"lifecycle\":\""<<life
       <<"\",\"prove_ms\":"<<prove<<",\"verify_ms\":"<<verify<<",\"show_ms\":"<<prove+verify
       <<",\"prove_cpu_ms\":"<<pcpu<<",\"verify_cpu_ms\":"<<vcpu<<",\"proof_bytes\":"<<size
       <<",\"K\":"<<attempts<<",\"rss_kib\":"<<ru.ru_maxrss
       <<",\"k\":3,\"D\":[0,4,5],\"attribute_count\":8,\"input_attribute_bytes\":8"
       <<",\"verification_mode\":\"external_native\",\"declared_security_target\":128"
       <<",\"security_equivalence_established\":false}"<<endl;
   delete[] vp.Pi;if(life=="fresh")delete s;
  }
  delete persistent;delete[]ipk;
  return 0;
 } catch(const std::exception&e) {cerr<<"REVISION FAILED: "<<e.what()<<endl;return 2;}
}
