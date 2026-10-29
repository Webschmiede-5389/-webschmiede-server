"""Reproducible offline end-to-end evidence; no LLM or external account calls."""
import json,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];ASSETS=ROOT/'docs/agency/process-architect'
state=Path(sys.argv[1]).resolve();state.mkdir(parents=True,exist_ok=True)
if (state/'planning.sqlite').exists():raise SystemExit('Use a new empty evidence directory')
cmd=[sys.executable,str(ROOT/'scripts/process_architect_worker.py'),'--config',str(ASSETS/'pilot-config.json'),'--state',str(state),'--interval','.05']
p=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
def wait(job,status):
 f=state/'TEST_A/output'/f'TEST_A-{job}-status.json';end=time.monotonic()+10
 while time.monotonic()<end:
  if f.exists() and json.loads(f.read_text())['job']['status']==status:return
  if p.poll() is not None:raise RuntimeError(p.communicate()[1].decode())
  time.sleep(.05)
 raise TimeoutError(job)
def put(name):
 f=state/'TEST_A/inbox'/name;t=f.with_suffix('.tmp');t.write_text((ASSETS/name).read_text());t.rename(f)
try:
 end=time.monotonic()+10
 while not (state/'TEST_A/inbox').exists():
  if time.monotonic()>end:raise TimeoutError('worker start')
  time.sleep(.05)
 put('intake-complete.json');put('intake-missing.json')
 wait('pilot-complete','PLAN_READY');wait('pilot-missing','WAITING_INPUT')
 waiting=json.loads((state/'TEST_A/output/TEST_A-pilot-missing-status.json').read_text())
 (state/'waiting-checkpoint.json').write_text(json.dumps(waiting,ensure_ascii=False,indent=2))
 p.terminate();p.communicate(timeout=3)
 p=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 put('answer.json');wait('pilot-missing','PLAN_READY')
 print(json.dumps({'mode':'OFFLINE_DETERMINISTIC_REFERENCE','complete':'PLAN_READY','missing_before':'WAITING_INPUT','missing_after_restart_and_answer':'PLAN_READY','live_llm':'NOT_TESTED','external_connectors':'NOT_TESTED','activated':False},indent=2))
finally:p.terminate();p.communicate(timeout=3)
