"""Planning-only extension of agency/Stefan. No execution of generated plans.

Trusted local operator adapter: tenant is supplied by the authenticated caller,
never accepted from an untrusted request. SQLite is isolated from product DBs.
"""
from __future__ import annotations
import copy
import hashlib
import json
import os
import re
import sqlite3
import time
import urllib.request
import urllib.parse
from pathlib import Path

REQUIRED = ('goal', 'owner', 'systems', 'acceptance', 'budget')
STEP_FIELDS = ('id', 'trigger', 'inputs', 'preconditions', 'system', 'owner',
               'processing', 'mapping', 'output', 'permissions', 'failure',
               'retry', 'deduplication', 'audit', 'recovery', 'test', 'depends_on')

def dump(v):
    return json.dumps(v, ensure_ascii=False, sort_keys=True)

def digest(v):
    return hashlib.sha256(dump(v).encode()).hexdigest()

def valid_id(v):
    return isinstance(v, str) and bool(re.fullmatch(r'[A-Za-z0-9_-]{1,80}', v))

class PlanningError(Exception):
    pass

class Architect:
    def __init__(self, db_path, config, model=None):
        self.config, self.model = config, model
        self.db = sqlite3.connect(str(db_path), timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS pa_jobs (
            tenant TEXT, id TEXT, revision INTEGER, payload TEXT, status TEXT,
            attempts INTEGER DEFAULT 0, source_hash TEXT DEFAULT '', detail TEXT DEFAULT '{}',
            next_at REAL DEFAULT 0, PRIMARY KEY(tenant,id));
          CREATE TABLE IF NOT EXISTS pa_events (
            tenant TEXT, id TEXT, hash TEXT, PRIMARY KEY(tenant,id));
          CREATE TABLE IF NOT EXISTS pa_plans (
            tenant TEXT, job TEXT, version INTEGER, revision INTEGER, body TEXT,
            created REAL, PRIMARY KEY(tenant,job,version));
          CREATE TABLE IF NOT EXISTS pa_log (
            seq INTEGER PRIMARY KEY, tenant TEXT, job TEXT, state TEXT, detail TEXT, at REAL);
        ''')
        self.db.commit()

    def log(self, tenant, job, state, detail):
        self.db.execute('INSERT INTO pa_log(tenant,job,state,detail,at) VALUES(?,?,?,?,?)',
                        (tenant, job, state, dump(detail), time.time()))

    def job(self, tenant, jid):
        row = self.db.execute('SELECT * FROM pa_jobs WHERE tenant=? AND id=?', (tenant,jid)).fetchone()
        return dict(row) if row else None

    def submit(self, tenant, event):
        """Atomic admission. A replay is harmless, a changed replay is rejected."""
        if tenant not in self.config['tenants'] or not valid_id(event.get('event_id')) or not valid_id(event.get('job_id')):
            raise PlanningError('INVALID_ID_OR_TENANT')
        if 'tenant' in event and event['tenant'] != tenant:
            raise PlanningError('TENANT_MISMATCH')
        if len(dump(event)) > 32000:
            raise PlanningError('INPUT_TOO_LARGE')
        if event.get('kind') not in ('intake','answer','revise'):
            raise PlanningError('INVALID_KIND')
        payload = event.get('data', {})
        if not isinstance(payload, dict) or set(payload) - set(REQUIRED + ('process','notes','source_ids')):
            raise PlanningError('INVALID_FIELDS')
        for key in ('goal','owner','budget','process','notes'):
            if key in payload and (not isinstance(payload[key],str) or len(payload[key])>6000):
                raise PlanningError('INVALID_FIELD_TYPE')
        for key in ('systems','acceptance','source_ids'):
            if key in payload and (not isinstance(payload[key],list) or len(payload[key])>40
                    or any(not isinstance(x,str) or not x.strip() or len(x)>2000 for x in payload[key])):
                raise PlanningError('INVALID_FIELD_TYPE')
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            prior = self.db.execute('SELECT hash FROM pa_events WHERE tenant=? AND id=?',
                                    (tenant,event['event_id'])).fetchone()
            if prior:
                if prior['hash'] != digest(event):
                    raise PlanningError('EVENT_ID_CONFLICT')
                return 'DUPLICATE'
            old = self.job(tenant, event['job_id'])
            if event['kind'] == 'intake':
                if old:
                    raise PlanningError('JOB_EXISTS')
                revision = 1
            else:
                if not old or event.get('expected_revision') != old['revision']:
                    raise PlanningError('REVISION_CONFLICT')
                if old['status'] == 'RUNNING':
                    raise PlanningError('JOB_BUSY')
                previous = json.loads(old['payload'])
                previous.update(payload)
                payload, revision = previous, old['revision'] + 1
            self.db.execute('INSERT INTO pa_events VALUES(?,?,?)', (tenant,event['event_id'],digest(event)))
            self.db.execute('INSERT OR REPLACE INTO pa_jobs(tenant,id,revision,payload,status,attempts) VALUES(?,?,?,?,?,0)',
                            (tenant,event['job_id'],revision,dump(payload),'QUEUED'))
            self.log(tenant,event['job_id'],'QUEUED',{'revision':revision,'event_id':event['event_id']})
        return 'QUEUED'

    def sources(self, tenant, payload):
        policy = self.config['tenants'][tenant]
        allowed = policy['source_ids']
        requested = payload.get('source_ids', allowed)
        if not isinstance(requested, list) or any(s not in allowed for s in requested):
            raise PlanningError('SOURCE_ACCESS_DENIED')
        # Mandatory global and process sources cannot be removed by the brief.
        ids = sorted(set(requested + policy.get('mandatory_source_ids', [])))
        result = []
        total = 0
        for sid in ids:
            source = self.config['sources'].get(sid)
            if not source or source['scope'] not in ('global',tenant):
                raise PlanningError('SOURCE_ACCESS_DENIED')
            if source['scope'] == 'global' and source.get('classification') != 'sanitized':
                raise PlanningError('GLOBAL_SOURCE_NOT_SANITIZED')
            if source.get('transport','file') == 'github':
                # Catalog is operator-owned. No URL from customer/model is fetched.
                repo = source.get('repository','')
                ref = source['version']
                repo_path = source.get('repository_path','')
                if not re.fullmatch(r'Webschmiede-5389/[A-Za-z0-9_.-]+',repo) or not re.fullmatch(r'[a-f0-9]{40}',ref):
                    raise PlanningError('SOURCE_BOUNDARY')
                if not repo_path or '..' in repo_path.split('/') or repo_path.startswith('/'):
                    raise PlanningError('SOURCE_BOUNDARY')
                token = os.environ.get('PA_GITHUB_READ_TOKEN','')
                if not token:
                    raise PlanningError('SOURCE_CREDENTIAL_MISSING')
                url = 'https://api.github.com/repos/'+repo+'/contents/'+urllib.parse.quote(repo_path,safe='/')+'?ref='+ref
                req = urllib.request.Request(url,headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github.raw+json'})
                # Reject redirects rather than forwarding a credential to another host.
                class NoRedirect(urllib.request.HTTPRedirectHandler):
                    def redirect_request(self,*args,**kwargs):
                        return None
                with urllib.request.build_opener(NoRedirect).open(req,timeout=10) as response:
                    data=response.read(120001)
                if len(data)>120000:
                    raise PlanningError('CONTEXT_BUDGET')
                raw=data.decode('utf-8')
            else:
                path = Path(source['path']).resolve()
                root = Path(self.config['source_root']).resolve()
                if not path.is_relative_to(root) or path.stat().st_size > 120000:
                    raise PlanningError('SOURCE_BOUNDARY')
                raw = path.read_text(encoding='utf-8')
            total += len(raw)
            if total > 120000:
                raise PlanningError('CONTEXT_BUDGET')
            sha = hashlib.sha256(raw.encode()).hexdigest()
            if source.get('sha256') and sha != source['sha256']:
                raise PlanningError('SOURCE_CHANGED_REVIEW_REQUIRED')
            result.append({'id':sid,'sha256':sha,'version':source['version'],
                           'url':source['url'],'scope':source['scope'],'text':raw})
        if not result:
            raise PlanningError('SOURCES_MISSING')
        return result

    def context(self, tenant, payload):
        sources = self.sources(tenant,payload)
        values = copy.deepcopy(payload)
        conflicts = []
        origins = {k:'intake' for k in values}
        for s in sources:
            if self.config['sources'][s['id']].get('format') != 'facts':
                continue
            facts = json.loads(s['text']).get('facts',{})
            for key, val in facts.items():
                if key not in REQUIRED:
                    continue
                if key in values and values[key] not in (None,'',val):
                    conflicts.append(key)
                elif key not in values or values[key] in (None,''):
                    values[key] = val
                    origins[key] = s['id']
        gaps = [k for k in REQUIRED if not values.get(k) or values[k] == 'UNKNOWN']
        return values, sources, sorted(set(gaps)), sorted(set(conflicts)), origins

    def set_state(self, tenant, jid, state, detail, **fields):
        with self.db:
            self.db.execute('UPDATE pa_jobs SET status=?,detail=? WHERE tenant=? AND id=?',
                            (state,dump(detail),tenant,jid))
            for key,value in fields.items():
                if key not in ('source_hash','next_at'):
                    raise PlanningError('INTERNAL_FIELD')
                self.db.execute(f'UPDATE pa_jobs SET {key}=? WHERE tenant=? AND id=?',(value,tenant,jid))
            self.log(tenant,jid,state,detail)

    def process(self, tenant, jid):
        job = self.job(tenant,jid)
        payload = json.loads(job['payload'])
        try:
            values,sources,gaps,conflicts,origins = self.context(tenant,payload)
        except (PlanningError,OSError,ValueError) as exc:
            self.set_state(tenant,jid,'BLOCKED',{'code':str(exc) if isinstance(exc,PlanningError) else type(exc).__name__})
            return
        source_hash = digest([(s['id'],s['sha256']) for s in sources])
        if gaps or conflicts:
            self.set_state(tenant,jid,'WAITING_INPUT',{'questions':[
                {'field':k,'status':'UNKNOWN','owner':values.get('owner') or 'Christian',
                 'check':'Quellwiderspruch durch berechtigten Operator in Quelle korrigieren' if k in conflicts
                         else 'Wert in autorisierter Quelle oder Antwort ergänzen'}
                for k in sorted(set(gaps+conflicts))]},source_hash=source_hash)
            return
        if job['attempts'] >= 3:
            self.set_state(tenant,jid,'BLOCKED',{'code':'ATTEMPT_BUDGET_EXHAUSTED'})
            return
        with self.db:
            self.db.execute('UPDATE pa_jobs SET attempts=attempts+1, source_hash=? WHERE tenant=? AND id=?',
                            (source_hash,tenant,jid))
            self.log(tenant,jid,'CONTEXT_READY',{'sources':[s['id'] for s in sources],'origins':origins})
        try:
            if payload.get('process') == 'customer-intake-v1':
                plan = self.template_plan(values,sources)
                mode = 'DETERMINISTIC_REFERENCE'
            else:
                if self.model is None:
                    raise PlanningError('MODEL_NOT_CONFIGURED')
                plan = self.model(values,sources,json.loads(job['detail']))
                mode = 'LLM_DRAFT'
            errors = validate(plan, sources)
            if mode=='LLM_DRAFT' and plan.get('machine_review',{}).get('verdict')!='PASS':
                errors.append('MACHINE_REVIEW_FAILED')
                errors.extend(str(f)[:500] for f in plan.get('machine_review',{}).get('findings',[])[:10])
            if errors:
                self.set_state(tenant,jid,'RETRY',{'code':'PLAN_VALIDATION','findings':errors}, next_at=time.time()+1)
                return
            if mode == 'LLM_DRAFT':
                review = plan.get('machine_review',{})
                state = 'PLAN_READY' if review.get('verdict')=='PASS' and not any(
                    g.get('blocking',True) for g in plan.get('unknowns',[])) else 'REVIEW_REQUIRED' 
            else:
                state = 'PLAN_READY'
            plan.update({'tenant':tenant,'job_id':jid,'input_revision':job['revision'],
                         'mode':mode,'status':state,'execution_authorized':False,
                         'provenance':[{k:v for k,v in s.items() if k != 'text'} for s in sources],
                         'input_origins':origins})
            with self.db:
                version = self.db.execute('SELECT COALESCE(MAX(version),0)+1 FROM pa_plans WHERE tenant=? AND job=?',
                                          (tenant,jid)).fetchone()[0]
                plan['version'] = version
                self.db.execute('INSERT INTO pa_plans VALUES(?,?,?,?,?,?)',
                                (tenant,jid,version,job['revision'],dump(plan),time.time()))
                self.db.execute('UPDATE pa_jobs SET status=?,detail=? WHERE tenant=? AND id=?',
                                (state,dump({'version':version,'validation':'STRUCTURE_PASS'}),tenant,jid))
                self.log(tenant,jid,state,{'version':version,'mode':mode})
        except PlanningError as exc:
            self.set_state(tenant,jid,'BLOCKED',{'code':str(exc)})
        except Exception as exc:
            self.set_state(tenant,jid,'RETRY',{'code':'PROVIDER_OR_RUNTIME_ERROR','type':type(exc).__name__},next_at=time.time()+1)

    def template_plan(self, values, sources):
        template_source = next((s for s in sources if s['id']=='intake-template'),None)
        if not template_source:
            raise PlanningError('TEMPLATE_MISSING')
        plan = json.loads(template_source['text'])
        plan['goal'] = values['goal']
        plan['owner'] = values['owner']
        plan['systems'] = values['systems']
        plan['acceptance'] = values['acceptance']
        plan['budget'] = values['budget']
        # Only a narrowly specified standard process qualifies for template readiness.
        if values['systems'] != ['Projektregister','Google Drive'] or values['goal'] != plan['supported_goal']:
            raise PlanningError('OUTSIDE_REFERENCE_SCOPE')
        if values.get('notes'):
            raise PlanningError('REFERENCE_REQUIRES_FREEFORM_REVIEW')
        return plan

    def tick(self):
        """One bounded worker pass; source changes invalidate old readiness."""
        for row in self.db.execute("SELECT * FROM pa_jobs WHERE status IN ('PLAN_READY','WAITING_INPUT','REVIEW_REQUIRED')").fetchall():
            try:
                ss = self.sources(row['tenant'],json.loads(row['payload']))
                changed = digest([(s['id'],s['sha256']) for s in ss]) != row['source_hash']
            except Exception:
                changed = True
            if changed:
                self.set_state(row['tenant'],row['id'],'QUEUED',{'reason':'SOURCE_CHANGE'})
        rows = self.db.execute("SELECT tenant,id FROM pa_jobs WHERE status IN ('QUEUED','RETRY') AND next_at<=? LIMIT 10",(time.time(),)).fetchall()
        for row in rows:
            with self.db:
                cur = self.db.execute("UPDATE pa_jobs SET status='RUNNING' WHERE tenant=? AND id=? AND status IN ('QUEUED','RETRY')",tuple(row))
            if cur.rowcount:
                self.process(row['tenant'],row['id'])

    def recover(self):
        # Called only under exclusive worker lock, never by a concurrent submitter.
        with self.db:
            rows = self.db.execute("SELECT tenant,id FROM pa_jobs WHERE status='RUNNING'").fetchall()
            for row in rows:
                self.db.execute("UPDATE pa_jobs SET status='RETRY',next_at=0 WHERE tenant=? AND id=?",tuple(row))
                self.log(row['tenant'],row['id'],'RETRY',{'reason':'WORKER_RESTART'})

    def export(self, tenant, jid, directory):
        if tenant not in self.config['tenants'] or not valid_id(jid):
            raise PlanningError('ACCESS_DENIED')
        out = Path(directory)
        out.mkdir(parents=True,exist_ok=True)
        for row in self.db.execute('SELECT * FROM pa_plans WHERE tenant=? AND job=?',(tenant,jid)):
            # Immutable version file. Existing bytes must agree, never overwrite approval.
            path = out / f'{tenant}-{jid}-v{row["version"]}.json'
            text = json.dumps(json.loads(row['body']),ensure_ascii=False,indent=2)+'\n'
            if path.exists():
                if path.read_text()!=text:
                    raise PlanningError('EXPORT_CONFLICT')
            else:
                with path.open('x') as f:
                    f.write(text)
        state = {'job':self.job(tenant,jid),'log':[dict(r) for r in self.db.execute(
            'SELECT * FROM pa_log WHERE tenant=? AND job=? ORDER BY seq',(tenant,jid))]}
        # The DB is canonical; current-status export is replaceable and contains no secret.
        tmp = out / f'.{tenant}-{jid}-status.tmp'
        tmp.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')
        os.replace(tmp,out/f'{tenant}-{jid}-status.json')

def validate(plan, sources):
    errors = []
    if not isinstance(plan,dict):
        return ['PLAN_NOT_OBJECT']
    for key in ('goal','scope','exclusions','acceptance','steps','known_failures','handoff','unknowns'):
        if key not in plan:
            errors.append('MISSING_'+key)
    ids = {s['id'] for s in sources}
    if not plan.get('source_ids') or not set(plan['source_ids']).issubset(ids):
        errors.append('SOURCE_CITATION_INVALID')
    seen = set()
    steps = plan.get('steps',[])
    if not isinstance(steps,list) or not steps:
        return errors+['STEPS_MISSING']
    for step in steps:
        if not isinstance(step,dict):
            errors.append('STEP_NOT_OBJECT')
            continue
        for key in STEP_FIELDS:
            if key not in step or (key!='depends_on' and not step[key]):
                errors.append('STEP_MISSING_'+key)
        if step.get('id') in seen:
            errors.append('STEP_ID_DUPLICATE')
        deps=step.get('depends_on',[])
        if not isinstance(deps,list) or any(d not in seen for d in deps):
            errors.append('DEPENDENCY_ORDER_INVALID')
        seen.add(step.get('id'))
    for gap in plan.get('unknowns',[]):
        if not isinstance(gap,dict) or not all(gap.get(k) for k in ('field','owner','check','status')):
            errors.append('UNKNOWN_WITHOUT_CHECK')
    if plan.get('execution_authorized') is True:
        errors.append('EXECUTION_NOT_AUTHORIZED')
    return errors
