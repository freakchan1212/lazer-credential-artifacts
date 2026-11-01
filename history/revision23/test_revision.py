import tempfile, unittest
from pathlib import Path
from revision_common import check_rows, dump
from run_revision import plan
from summarize_revision import block_effects

class RevisionTests(unittest.TestCase):
 def test_fixed_design(self):
  jobs=plan('full',True)
  self.assertEqual(sum(x['sessions'] for x in jobs),4200)
  self.assertEqual(sum(x['sessions'] for x in jobs if x['variant']!='PQZK_BLNS'),3600)
  self.assertEqual(jobs,plan('full',True))
  self.assertEqual(len({x['id'] for x in jobs}),len(jobs))
 def test_reject_bad_worker(self):
  j=dict(sessions=1,warmup=0,variant='B1',lifecycle='steady')
  r=dict(index=0,warmup=False,status='ACCEPTED',prove_ms=2.,verify_ms=1.,show_ms=3.,proof_bytes=100,rss_kib=10,variant='B1',lifecycle='steady')
  check_rows([r],j)
  for change in [dict(status='REJECTED'),dict(show_ms=4),dict(prove_ms=float('nan')),dict(index=1),dict(proof_bytes=0)]:
   with self.assertRaises(ValueError):check_rows([dict(r,**change)],j)
 def test_block_statistics_keep_regressions(self):
  data=[]
  for rnd in [1,2,3]:
   for block in [1,2]:
    for v,t in [('G3',10),('C3',9 if block==1 else 12)]:
     for _ in range(2):data.append(dict(compiler='gcc',lifecycle='steady',variant=v,round=rnd,block=block,show_ms=t,prove_ms=t-1,verify_ms=1,K=3))
  s,b=block_effects(data,'gcc','steady','G3','C3',reps=500)
  self.assertEqual(s['improved_blocks'],3)
  self.assertAlmostEqual(s['reduction_pct'],-5)
  self.assertEqual(len(b),6)
if __name__=='__main__':unittest.main()
