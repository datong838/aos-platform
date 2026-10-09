import json
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
B=Path(__file__).resolve().parent;result=json.loads((B/'native-normalization-r2-result.json').read_text());assert result['pytest_exit']==0;lab=json.loads((B/'lab.json').read_text())
with psycopg.connect(host='127.0.0.1',port=5437,user='aos_app',dbname=result['database'],passfile=lab['passfile'],row_factory=dict_row) as c:
 c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY');assert c.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']==lab['cluster']
 rows=c.execute("""SELECT r.receipt_id,r.idempotency_key,r.result_ref,e.event_id,e.reason,e.actor,
    e.bundle_id,e.revision,e.content_hash,p.epoch,
    r.xmin::text AS receipt_xid,e.xmin::text AS revoke_xid,p.xmin::text AS epoch_xid,
    pg_xact_status(r.xmin::text::xid8) AS receipt_state,pg_xact_status(e.xmin::text::xid8) AS revoke_state,
    pg_xact_status(p.xmin::text::xid8) AS epoch_state
    FROM public.aip_production_contract_receipt r
    JOIN public.aip_evidence_bundle_revoke_event e ON
    (e.org_id,e.project_id,e.bundle_id,e.revision,e.content_hash)=
    (r.org_id,r.project_id,r.result_ref->>'resourceId',(r.result_ref->>'revision')::bigint,r.result_ref->>'contentHash')
    JOIN public.aip_capacity_evidence_epoch p ON (p.org_id,p.project_id,p.bundle_id)=(e.org_id,e.project_id,e.bundle_id)
    WHERE r.org_id='org-org' AND r.project_id='dev-project' AND r.operation='evidence_bundle.revoke'
    AND r.idempotency_key LIKE 'native-three-revoke-%' ORDER BY e.bundle_id""").fetchall()
 assert len(rows)==3 and len({x['bundle_id'] for x in rows})==3
 for x in rows:
  assert x['reason']=='isolated genuine original origin revoke' and x['epoch']==1
  assert x['receipt_xid']==x['revoke_xid']==x['epoch_xid']
  assert x['receipt_state']==x['revoke_state']==x['epoch_state']=='committed'
 assert c.execute("SELECT count(*) AS n FROM public.aip_production_contract_receipt WHERE org_id='dev-org' AND idempotency_key LIKE 'native-three-revoke-%'").fetchone()['n']==0
 assert c.execute('SELECT count(*) AS n FROM aos_capacity_publication_private.source_publication').fetchone()['n']==0
proof=dict(schema='aos-original-three-origin-genuine-revokes-independent-readback/v1',database=result['database'],cluster=lab['cluster'],receipts_revokes_epochs=rows,same_caller_actual_committed=True,canary_zero=True,sources_zero=True,effects_replayed=False,formal_business_execution=False)
(B/'actual-original-revokes-independent.json').write_text(json.dumps(proof,indent=2));print('Three exact original revoke receipts/events/neutralepochs share actual committed xid each; epoch1, canary0, Source0; no replay')
