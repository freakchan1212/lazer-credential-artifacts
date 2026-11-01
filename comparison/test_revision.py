import tempfile,unittest
from pathlib import Path
from revision_common import check_rows,check_proof_reuse
from run_revision import plan
from summarize_revision import block_effects
import audit_two_baselines

class RevisionTests(unittest.TestCase):
 def test_legacy_subset_plan(self):
  self.assertEqual(sum(x['sessions'] for x in plan('full',True)),4200)
 def test_two_baseline_plan(self):
  jobs=plan('full',True,True,True)
  self.assertEqual(len(jobs),390)
  self.assertEqual(sum(x['sessions'] for x in jobs),7800)
  self.assertEqual(jobs,plan('full',True,True,True))
  self.assertEqual(len({x['id'] for x in jobs}),390)
  allowed={'B1','G3','C3','ARGO_NATIVE','ARGO_PADDED','ARGO_COMPACT','ARGO_PADDED_NOCACHE','PQZK_BLNS','PQZK_BLNS_PADDED','PQZK_BLNS_COMPACT','PQZK_BLNS_PADDED_NOCACHE'}
  self.assertEqual({x['variant'] for x in jobs},allowed)
  self.assertTrue(all(x['compiler']=='gcc' for x in jobs if x['variant'].startswith(('ARGO_','PQZK_'))))
  self.assertTrue(all(x['lifecycle']=='steady' for x in jobs if x['variant'].endswith('_NOCACHE')))
 def test_complete_source_audit(self):
  with tempfile.TemporaryDirectory() as td:
   result=audit_two_baselines.run(Path(td)/'audit.json')
   self.assertEqual(result['selected'],['argo','pqzk-blns'])
   self.assertEqual(result['status'],'SOURCE_COMPLETE_RUNNABLE')
   self.assertFalse(result['common_parameter_security_equivalence'])
 def test_reject_bad_worker(self):
  j=dict(sessions=1,warmup=0,variant='B1',lifecycle='steady')
  r=dict(index=0,warmup=False,status='ACCEPTED',prove_ms=2.,verify_ms=1.,show_ms=3.,proof_bytes=100,rss_kib=10,variant='B1',lifecycle='steady')
  check_rows([r],j)
  for change in [dict(status='REJECTED'),dict(show_ms=4),dict(prove_ms=float('nan')),dict(index=1),dict(proof_bytes=0),dict(formal=False)]:
   with self.assertRaises(ValueError):check_rows([dict(r,**change)],j)
 def test_crossblock_reuse(self):
  j=dict(compiler='gcc',variant='ARGO_PADDED',lifecycle='steady');r=dict(warmup=False,proof_sha='b'*64);seen=set()
  check_proof_reuse([r],j,seen)
  with self.assertRaises(ValueError):check_proof_reuse([r],j,seen)
 def test_keep_regression_blocks(self):
  data=[]
  for rnd in [1,2,3]:
   for block in [1,2]:
    for v,t in [('G3',10),('C3',9 if block==1 else 12)]:
     for _ in range(2):data.append(dict(compiler='gcc',lifecycle='steady',variant=v,round=rnd,block=block,show_ms=t,prove_ms=t-1,verify_ms=1,K=3))
  summary,blocks=block_effects(data,'gcc','steady','G3','C3',reps=500)
  self.assertEqual(summary['improved_blocks'],3)
  self.assertAlmostEqual(summary['reduction_pct'],-5)
  self.assertEqual(len(blocks),6)
if __name__=='__main__':unittest.main()
