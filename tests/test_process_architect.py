import json,sys,tempfile,time,subprocess,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'app/backend'),str(ROOT/'scripts')]
from process_architect import Architect,PlanningError,validate
from process_architect_worker import load_config
ASSETS=ROOT/'docs/agency/process-architect'
class PlanningTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)
  self.config=load_config(ASSETS/'pilot-config.json');self.e=Architect(self.path/'state.sqlite',self.config)
  self.ev=json.loads((ASSETS/'intake-complete.json').read_text())
 def tearDown(self):self.e.db.close();self.tmp.cleanup()
 def start(self):self.e.submit('TEST_A',self.ev);self.e.tick();return self.e.job('TEST_A',self.ev['job_id'])
 def test_complete_and_persistence(self):
  self.assertEqual(self.start()['status'],'PLAN_READY')
  plan=json.loads(self.e.db.execute('SELECT body FROM pa_plans').fetchone()[0])
  self.assertEqual(plan['input_origins']['owner'],'pilot-facts');self.assertEqual(len(plan['steps']),7)
  self.assertFalse(plan['execution_authorized']);self.assertEqual(plan['known_failures'][0]['id'],'PA-L01')
  self.e.db.close();self.e=Architect(self.path/'state.sqlite',self.config)
  self.assertEqual(self.e.db.execute('SELECT count(*) FROM pa_plans').fetchone()[0],1)
 def test_missing_answer_and_stale_answer(self):
  self.ev=json.loads((ASSETS/'intake-missing.json').read_text());j=self.start()
  self.assertEqual(j['status'],'WAITING_INPUT');self.assertEqual(json.loads(j['detail'])['questions'][0]['field'],'budget')
  ans=json.loads((ASSETS/'answer.json').read_text());self.e.submit('TEST_A',ans);self.e.tick()
  self.assertEqual(self.e.job('TEST_A','pilot-missing')['status'],'PLAN_READY');ans['event_id']='stale'
  with self.assertRaisesRegex(PlanningError,'REVISION_CONFLICT'):self.e.submit('TEST_A',ans)
 def test_duplicate_and_conflict(self):
  self.e.submit('TEST_A',self.ev);self.assertEqual(self.e.submit('TEST_A',self.ev),'DUPLICATE')
  self.ev['data']['budget']='changed'
  with self.assertRaisesRegex(PlanningError,'EVENT_ID_CONFLICT'):self.e.submit('TEST_A',self.ev)
  self.e.tick();self.assertEqual(self.e.db.execute('SELECT count(*) FROM pa_plans').fetchone()[0],1)
 def test_cross_tenant_source_denied(self):
  self.ev['data']['source_ids']=['pilot-facts'];self.e.submit('TEST_B',self.ev);self.e.tick()
  self.assertIn('SOURCE_ACCESS_DENIED',self.e.job('TEST_B','pilot-complete')['detail'])
  self.assertEqual(self.e.db.execute('SELECT count(*) FROM pa_plans').fetchone()[0],0)
 def test_tenant_spoof(self):
  self.ev['tenant']='TEST_B'
  with self.assertRaisesRegex(PlanningError,'TENANT_MISMATCH'):self.e.submit('TEST_A',self.ev)
  self.assertIsNone(self.e.job('TEST_A','pilot-complete'))
 def test_source_contradiction(self):
  self.ev['data']['owner']='different';self.assertEqual(self.start()['status'],'WAITING_INPUT')
 def test_schema_citations(self):
  p=json.loads((ASSETS/'intake-template.json').read_text());del p['steps'][0]['recovery'];p['source_ids']=['invented']
  errors=validate(p,self.e.sources('TEST_A',{}));self.assertIn('STEP_MISSING_recovery',errors);self.assertIn('SOURCE_CITATION_INVALID',errors)
 def test_bounded_provider_failure(self):
  def fail(*args):raise TimeoutError()
  self.e.model=fail;self.ev['data']['process']='freeform';self.e.submit('TEST_A',self.ev)
  for _ in range(4):
   self.e.tick()
   with self.e.db:self.e.db.execute('UPDATE pa_jobs SET next_at=0')
  j=self.e.job('TEST_A','pilot-complete');self.assertEqual(j['attempts'],3);self.assertEqual(j['status'],'BLOCKED')
 def test_model_repair_feedback_fixture(self):
  calls=[]
  def model(values,sources,findings):
   calls.append(findings);p=json.loads((ASSETS/'intake-template.json').read_text())
   if len(calls)==1:del p['steps'][0]['recovery']
   p['machine_review']={'verdict':'PASS','findings':[]};return p
  self.e.model=model;self.ev['data']['process']='freeform';self.start()
  with self.e.db:self.e.db.execute('UPDATE pa_jobs SET next_at=0')
  self.e.tick();self.assertIn('STEP_MISSING_recovery',calls[1]['findings']);self.assertEqual(self.e.job('TEST_A','pilot-complete')['status'],'PLAN_READY')
 def test_unconfigured_model_never_passes(self):
  self.ev['data']['process']='freeform';self.assertEqual(self.start()['status'],'BLOCKED')
 def test_recovery_retains_attempts(self):
  self.e.submit('TEST_A',self.ev)
  with self.e.db:self.e.db.execute("UPDATE pa_jobs SET status='RUNNING',attempts=2")
  self.e.recover();self.e.tick();j=self.e.job('TEST_A','pilot-complete');self.assertEqual(j['attempts'],3);self.assertEqual(j['status'],'PLAN_READY')
 def test_source_change_preserves_old_version(self):
  src=self.path/'facts.json';src.write_text((ASSETS/'pilot-facts.json').read_text());self.config['source_root']='/'
  self.config['sources']['pilot-facts']['path']=str(src);self.start()
  first=self.e.db.execute('SELECT body FROM pa_plans').fetchone()[0]
  f=json.loads(src.read_text());f['facts']['owner']='TEST new owner';src.write_text(json.dumps(f));self.e.tick()
  self.assertEqual(self.e.db.execute('SELECT count(*) FROM pa_plans').fetchone()[0],2)
  self.assertEqual(self.e.db.execute('SELECT body FROM pa_plans WHERE version=1').fetchone()[0],first)
 def test_source_pin_blocks(self):
  self.config['sources']['rules']['sha256']='wrong';self.assertIn('SOURCE_CHANGED_REVIEW_REQUIRED',self.start()['detail'])
 def test_path_and_type_rejected(self):
  self.ev['data']['source_path']='/etc/passwd'
  with self.assertRaisesRegex(PlanningError,'INVALID_FIELDS'):self.e.submit('TEST_A',self.ev)
  del self.ev['data']['source_path'];self.ev['data']['source_ids']='pilot-facts'
  with self.assertRaisesRegex(PlanningError,'INVALID_FIELD_TYPE'):self.e.submit('TEST_A',self.ev)
class WorkerAcceptance(unittest.TestCase):
 def test_one_start_then_answer_and_restart(self):
  with tempfile.TemporaryDirectory() as td:
   state=Path(td);cmd=[sys.executable,str(ROOT/'scripts/process_architect_worker.py'),'--config',str(ASSETS/'pilot-config.json'),'--state',td,'--interval','.05']
   process=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
   def wait_status(job,status):
    path=state/'TEST_A/output'/f'TEST_A-{job}-status.json';deadline=time.monotonic()+8
    while time.monotonic()<deadline:
     if path.exists() and json.loads(path.read_text())['job']['status']==status:return
     if process.poll() is not None:self.fail(process.communicate()[1].decode())
     time.sleep(.05)
    self.fail(f'timeout {job} {status}')
   try:
    inbox=state/'TEST_A/inbox';deadline=time.monotonic()+5
    while not inbox.exists() and time.monotonic()<deadline:time.sleep(.05)
    for f in ['intake-complete.json','intake-missing.json']:
     temp=inbox/(f+'.tmp');temp.write_text((ASSETS/f).read_text());temp.rename(inbox/f)
    wait_status('pilot-complete','PLAN_READY');wait_status('pilot-missing','WAITING_INPUT')
    process.terminate();process.communicate(timeout=3)
    process=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    temp=inbox/'answer.tmp';temp.write_text((ASSETS/'answer.json').read_text());temp.rename(inbox/'answer.json')
    wait_status('pilot-missing','PLAN_READY')
    p=json.loads((state/'TEST_A/output/TEST_A-pilot-missing-v1.json').read_text());self.assertEqual(p['input_revision'],2)
   finally:process.terminate();process.communicate(timeout=3)
if __name__=='__main__':unittest.main()
