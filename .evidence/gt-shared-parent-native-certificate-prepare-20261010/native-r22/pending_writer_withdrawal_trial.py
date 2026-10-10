"""Pending immutable withdrawal commits only after real stale-reader blocking."""
import json,hashlib,queue,threading,time
from pathlib import Path
from uuid import uuid4
import psycopg,pytest
from psycopg.rows import dict_row
from psycopg.conninfo import conninfo_to_dict
from psycopg.types.json import Jsonb
from aos_api.db import get_dsn
from aos_api.aip_model_eval_execution_contracts import ModelSharedParentRiskSignedCertificateEnvelope
from aos_api.aip_provider_capacity_source_consumer import _consumption_packet
from reader_first_withdrawal_trial import owner
from aos_api.aip_contracts import TenantContext
from aos_api import aip_model_eval_execution_reader as reader
STATE=None

def start_pending_then_consume(conn,command,manifest,description,published,proof,evidence_dir):
 global STATE
 assert STATE is None
 params=conninfo_to_dict(get_dsn());assert params['dbname']==conn.info.dbname and params['dbname'].startswith('aos_test_')
 identity=conn.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone();assert (identity['xid'],identity['pid'])==(description.immutable.caller_xid,description.immutable.caller_pid)
 event=dict(schemaVersion='aos.model-eval-identity-withdrawal/v1',tenant=dict(orgId='org-org',projectId='dev-project'),identityId='target-identity',eventId='isolated-pending-writer-'+str(uuid4()));raw=json.dumps(event,sort_keys=True,separators=(',',':')).encode();ready=queue.Queue();terminal=queue.Queue();B=Path(evidence_dir)
 def withdraw():
  try:
   with owner(params) as writer:
    writer.execute("SET LOCAL statement_timeout='20s'");wid=writer.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone()
    writer.execute('INSERT INTO aos_model_eval_issuer_private.identity_withdrawal(org_id,project_id,event_id,identity_id,content_hash,body) VALUES (%s,%s,%s,%s,%s,%s)',('org-org','dev-project',event['eventId'],event['identityId'],hashlib.sha256(raw).hexdigest(),raw));ready.put(dict(wid))
    blocked=False;blockers=[]
    with psycopg.connect(**params,row_factory=dict_row,autocommit=True) as monitor:
     until=time.monotonic()+5
     while time.monotonic()<until:
      blockers=monitor.execute('SELECT pg_blocking_pids(%s) AS p',(identity['pid'],)).fetchone()['p']
      if wid['pid'] in blockers:blocked=True;break
      time.sleep(.02)
    assert blocked
    writer.commit();result=dict(writer=dict(wid),commit_returned=True,actual_blocking=True,blockers=blockers,reader=dict(identity))
   (B/'pending-writer-terminal.json').open('x').write(json.dumps(result,indent=2)+'\n');terminal.put(result)
  except Exception as exc:
   result=dict(error_type=type(exc).__name__,sqlstate=getattr(exc,'sqlstate',None),commit_returned=False)
   (B/'pending-writer-terminal.json').open('x').write(json.dumps(result,indent=2)+'\n');terminal.put(result)
 thread=threading.Thread(target=withdraw,name='isolated-pending-identity-withdrawal');STATE=dict(params=params,published=published,identity=dict(identity),event=event,raw=raw,thread=thread,terminal=terminal)
 (B/'pending-writer-intent.json').open('x').write(json.dumps(dict(risk_caller=dict(identity),published=published,event=event,event_hash=hashlib.sha256(raw).hexdigest(),execution_allowed=False),indent=2)+'\n');thread.start();wid=ready.get(timeout=5)
 certificates=[ModelSharedParentRiskSignedCertificateEnvelope.model_validate(x).model_dump(mode='json',by_alias=True) for x in proof['certificates']];packet=json.dumps(certificates,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
 with pytest.raises(psycopg.errors.SerializationFailure) as exc:
  with conn.transaction():
   conn.execute("SET LOCAL statement_timeout='20s'")
   conn.execute('SELECT public.prepare_model_shared_parent_certificate_set(%s,%s::jsonb,%s::uuid,%s,%s)',(_consumption_packet(command),Jsonb(command.source_ref.model_dump(mode='json',by_alias=True)),description.plan_id,description.content_hash,packet))
 assert exc.value.sqlstate=='40001'
 thread.join(timeout=25);assert not thread.is_alive();outcome=terminal.get(timeout=1);assert outcome['commit_returned'] and outcome['actual_blocking'] and wid['pid'] in outcome['blockers']
 after=conn.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone();assert dict(after)==dict(identity) and conn.info.transaction_status==psycopg.pq.TransactionStatus.INTRANS
 with pytest.raises(psycopg.errors.CheckViolation,match='SHARED_EXECUTOR_MANIFEST_REQUIRED'):
  with conn.transaction():conn.execute('SELECT public.read_model_shared_parent_executor_set_facts(%s,%s,%s,%s)',(manifest['executionId'],description.immutable.manifest_hash,description.content_hash,description.immutable.original_risk_hash))
 STATE['outcome']=outcome
 (B/'pending-writer-serialization-proof.json').open('x').write(json.dumps(dict(writer=outcome,sqlstate='40001',same_risk_caller_unchanged=True,manifest_absent_after_savepoint=True,outer_transaction_live=True,execution_allowed=False),indent=2)+'\n')

def finish_pending_withdrawal(risk_xid,evidence_dir):
 assert STATE is not None and STATE['identity']['xid']==risk_xid and not STATE['thread'].is_alive()
 p=STATE['published'];params=STATE['params'];outcome=STATE['outcome']
 with owner(params) as fresh:
  with pytest.raises(reader.ModelExecutionPlanRejected,match='current Model identity revoked or binding drifted'):
   reader.validate_persisted_model_identity(fresh,expected_identity_epoch=1,expected_tenant=TenantContext(orgId='org-org',projectId='dev-project'),execution_id=p['execution_id'],manifest_hash=p['manifest_hash'],certificate_hash=p['certificate_hash'],root_hash=p['root_hash'],expected_root_epoch=1,expected_certificate_epoch=1)
  fresh.rollback()
 with owner(params) as inspect:
  head=dict(inspect.execute("SELECT epoch,version,active FROM aos_model_eval_issuer_private.identity_epoch WHERE identity_id='target-identity'").fetchone());assert head==dict(epoch=2,version=2,active=False)
  states={name:inspect.execute('SELECT pg_xact_status(%s::xid8) AS s',(xid,)).fetchone()['s'] for name,xid in dict(risk=risk_xid,writer=outcome['writer']['xid']).items()};assert states==dict(risk='aborted',writer='committed');inspect.rollback()
 record=dict(writer=outcome,event=STATE['event'],event_hash=hashlib.sha256(STATE['raw']).hexdigest(),statuses=states,head=head,fresh_private_original_identity_rejected=True,fresh_full_v3_risk_attempted=False,stale_v3_sqlstate='40001',risk_commit_rejected=True,execution_allowed=False,root_provenance_verified=False,full_task_delivered=False)
 (Path(evidence_dir)/'pending-writer-withdrawal-proof.json').open('x').write(json.dumps(record,indent=2)+'\n')
