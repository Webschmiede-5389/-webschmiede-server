#!/usr/bin/env python3
"""Local trusted spool adapter. No public listener, no customer communications."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'app/backend'))
from process_architect import Architect, PlanningError

def load_config(path):
    path=Path(path).resolve()
    config=json.loads(path.read_text())
    root=(path.parent/config['source_root']).resolve()
    config['source_root']=str(root)
    for s in config['sources'].values():
        if s.get('transport','file') == 'file':
            s['path']=str(root/s['path'])
    return config

def model_adapter(values,sources,findings):
    if os.environ.get('PA_LLM_APPROVED')!='1':
        raise PlanningError('MODEL_NOT_APPROVED')
    request={'values':values,'sources':sources,'findings':findings}
    if len(json.dumps(request))>130000:
        raise PlanningError('MODEL_INPUT_BUDGET')
    # Hard wall-clock bound across the existing client's HTTP call.
    result=subprocess.run([sys.executable,str(ROOT/'scripts/process_architect_model.py')],
                          input=json.dumps(request),text=True,capture_output=True,timeout=50)
    if result.returncode:
        raise RuntimeError('MODEL_CALL_FAILED')
    return json.loads(result.stdout)

def run(config_path,state,seconds=None,interval=1):
    os.umask(0o077)
    state=Path(state).resolve()
    state.mkdir(parents=True,exist_ok=True)
    lock=(state/'worker.lock').open('a')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    config=load_config(config_path)
    engine=Architect(state/'planning.sqlite',config,model_adapter)
    engine.recover()
    started=time.monotonic()
    for tenant in config['tenants']:
        for sub in ('inbox','processed','rejected','output'):
            (state/tenant/sub).mkdir(parents=True,exist_ok=True)
    try:
        while seconds is None or time.monotonic()-started<seconds:
            for tenant in config['tenants']:
                for path in sorted((state/tenant/'inbox').glob('*.json')):
                    try:
                        if path.is_symlink() or path.stat().st_size>32000:
                            raise PlanningError('INPUT_BOUNDARY')
                        event=json.loads(path.read_text())
                        result=engine.submit(tenant,event)
                        dest=state/tenant/'processed'/path.name
                    except (PlanningError,ValueError,TypeError,AttributeError) as exc:
                        result=str(exc) if isinstance(exc,PlanningError) else 'INVALID_JSON_EVENT'
                        dest=state/tenant/'rejected'/path.name
                    # No overwrite of a previously processed file. Content-address suffix.
                    if dest.exists():
                        dest=dest.with_name(dest.stem+'-'+str(time.time_ns())+'.json')
                    path.rename(dest)
                    dest.with_suffix('.receipt').write_text(result+'\n')
            engine.tick()
            for row in engine.db.execute('SELECT tenant,id FROM pa_jobs').fetchall():
                engine.export(row['tenant'],row['id'],state/row['tenant']/'output')
            (state/'heartbeat.json').write_text(json.dumps({'at':time.time(),'mode':'planning-only'}))
            time.sleep(interval)
    finally:
        engine.db.close()
        lock.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--config',required=True)
    parser.add_argument('--state',required=True)
    parser.add_argument('--seconds',type=float)
    parser.add_argument('--interval',type=float,default=1)
    a=parser.parse_args()
    run(a.config,a.state,a.seconds,max(a.interval,0.05))
