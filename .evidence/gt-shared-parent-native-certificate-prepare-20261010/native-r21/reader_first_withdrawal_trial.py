"""One scoped test withdrawal actor waits on actual v3 risk; no second code writer."""
import json,hashlib,queue,threading,time
from pathlib import Path
from uuid import uuid4
import psycopg,pytest
from psycopg.rows import dict_row
from psycopg.conninfo import conninfo_to_dict
from aos_api.db import get_dsn
from aos_api.aip_contracts import TenantContext
from aos_api import aip_model_eval_execution_reader as reader
STATE=None

def owner(params):
 c=psycopg.connect(**params,row_factory=dict_row);c.isolation_level=psycopg.IsolationLevel.SERIALIZABLE
 c.execute("SET LOCAL TimeZone='UTC'");c.execute('SET LOCAL ROLE aos_model_eval_issuer_owner');c.execute("SET LOCAL aos.org_id='org-org'");c.execute("SET LOCAL aos.project_id='dev-project'");return c

def start_waiting_withdrawal(conn,description,published,metadata,evidence_dir):
 global STATE
 assert STATE is None
 params=conninfo_to_dict(get_dsn());assert params['dbname']==conn.info.dbname and params['dbname'].startswith('aos_test_')
 identity=conn.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone();assert (identity['xid'],identity['pid'])==(description.immutable.caller_xid,description.immutable.caller_pid)
 assert metadata['callerXid']==identity['xid'] and metadata['callerPid']==identity['pid']
 event=dict(schemaVersion='aos.model-eval-identity-withdrawal/v1',tenant=dict(orgId='org-org',projectId='dev-project'),identityId='target-identity',eventId='isolated-reader-first-'+str(uuid4()));raw=json.dumps(event,sort_keys=True,separators=(',',':')).encode();ready=queue.Queue();terminal=queue.Queue();B=Path(evidence_dir)
 def withdraw():
  try:
   with owner(params) as writer:
    writer.execute("SET LOCAL statement_timeout='20s'");wid=writer.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone();ready.put(dict(wid))
    writer.execute('INSERT INTO aos_model_eval_issuer_private.identity_withdrawal(org_id,project_id,event_id,identity_id,content_hash,body) VALUES (%s,%s,%s,%s,%s,%s)',('org-org','dev-project',event['eventId'],event['identityId'],hashlib.sha256(raw).hexdigest(),raw))
    writer.commit();result=dict(writer=dict(wid),commit_returned=True)
   (B/'withdrawal-writer-terminal.json').open('x').write(json.dumps(result,indent=2)+'\n');terminal.put(result)
  except Exception as exc:
   result=dict(error_type=type(exc).__name__,sqlstate=getattr(exc,'sqlstate',None),commit_returned=False)
   (B/'withdrawal-writer-terminal.json').open('x').write(json.dumps(result,indent=2)+'\n');terminal.put(result)
 thread=threading.Thread(target=withdraw,name='isolated-identity-withdrawal');STATE=dict(params=params,published=published,identity=dict(identity),event=event,raw=raw,thread=thread,terminal=terminal,metadata=metadata)
 (B/'withdrawal-writer-intent.json').open('x').write(json.dumps(dict(risk_caller=dict(identity),published=published,event=event,event_hash=hashlib.sha256(raw).hexdigest(),execution_allowed=False),indent=2)+'\n');thread.start();wid=ready.get(timeout=5)
 blocked=False;blockers=[]
 with psycopg.connect(**params,row_factory=dict_row,autocommit=True) as monitor:
  until=time.monotonic()+5
  while time.monotonic()<until:
   blockers=monitor.execute('SELECT pg_blocking_pids(%s) AS p',(wid['pid'],)).fetchone()['p']
   if identity['pid'] in blockers:blocked=True;break
   time.sleep(.02)
 assert blocked and thread.is_alive() and terminal.empty()
 again=conn.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone();assert dict(again)==dict(identity)
 record=dict(actual_blocking=True,blockers=blockers,reader=dict(identity),writer=wid,writer_live_observed=True,same_risk_caller_unchanged=True,certificate_count=len(metadata['certificates']),execution_allowed=False)
 STATE['blocking']=record;(B/'reader-first-blocking-proof.json').open('x').write(json.dumps(record,indent=2)+'\n')

def finish_waiting_withdrawal(risk_xid,evidence_dir):
 assert STATE is not None and STATE['identity']['xid']==risk_xid
 thread=STATE['thread'];thread.join(timeout=25);assert not thread.is_alive()
 outcome=STATE['terminal'].get(timeout=1);assert outcome['commit_returned']
 p=STATE['published'];params=STATE['params']
 with owner(params) as fresh:
  with pytest.raises(reader.ModelExecutionPlanRejected,match='current Model identity revoked or binding drifted'):
   reader.validate_persisted_model_identity(fresh,expected_identity_epoch=1,expected_tenant=TenantContext(orgId='org-org',projectId='dev-project'),execution_id=p['execution_id'],manifest_hash=p['manifest_hash'],certificate_hash=p['certificate_hash'],root_hash=p['root_hash'],expected_root_epoch=1,expected_certificate_epoch=1)
  fresh.rollback()
 with owner(params) as inspect:
  head=dict(inspect.execute("SELECT epoch,version,active FROM aos_model_eval_issuer_private.identity_epoch WHERE identity_id='target-identity'").fetchone());assert head==dict(epoch=2,version=2,active=False)
  states={name:inspect.execute('SELECT pg_xact_status(%s::xid8) AS s',(xid,)).fetchone()['s'] for name,xid in dict(risk=risk_xid,writer=outcome['writer']['xid']).items()};assert states==dict(risk='aborted',writer='committed');inspect.rollback()
 record=dict(blocking=STATE['blocking'],writer=outcome,event=STATE['event'],event_hash=hashlib.sha256(STATE['raw']).hexdigest(),statuses=states,head=head,fresh_private_original_identity_rejected=True,fresh_full_v3_risk_attempted=False,risk_commit_rejected=True,execution_allowed=False,root_provenance_verified=False,full_task_delivered=False)
 (Path(evidence_dir)/'reader-first-withdrawal-proof.json').open('x').write(json.dumps(record,indent=2)+'\n')
