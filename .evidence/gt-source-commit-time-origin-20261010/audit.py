"""Native read-only Source commit-time candidate, never an issuance operation."""
import hashlib
import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
import psycopg
from psycopg.rows import dict_row

B=Path(__file__).resolve().parent
R=B.parents[1]
sys.path.insert(0,str(R/'services/aos-api'))
from aos_api.aip_provider_capacity_publication_transaction import require_source_transaction_functions
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
s=importlib.util.spec_from_file_location('mc',R/'scripts/memory/memoryctl.py')
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
a=m.load_authority();assert a['project_revision']=='AOS-001657'
task=json.loads((B/'task.json').read_text())
assert next(x for x in m.load_leases(m.DEFAULT_PATHS)['leases'] if x['task_id']==B.name)==task
assert task['status']=='ACTIVE' and task['owner']=='codex-01a107a2-e9e4-7670-bc44-1144fa9b27e2'
assert datetime.now(timezone.utc)<datetime.fromisoformat(task['lease_expires_at'])
up=R/'.evidence/gt-source-final-commit-boundary-20261009/upstream-xact.c'
old=R/'.evidence/gt-source-final-commit-boundary-20261009/boundary-audit.json'
assert sha(up)==json.loads(old.read_text())['upstream_sha256']
text=up.read_text()
start=text.index('\nRecordTransactionCommit(void)')
end=text.index('\nRecordTransactionAbort',start)
section=text[start:end]
anchors=['XactLogCommitRecord(GetCurrentTransactionStopTimestamp()',
         'TransactionTreeSetCommitTsData(xid, nchildren, children,',
         'XLogFlush(XactLastRecEnd);','TransactionIdCommitTree(xid',
         'SyncRepWaitForLSN(XactLastRecEnd, true)']
positions=[section.index(x) for x in anchors]
assert positions==sorted(positions) and len(set(positions))==len(positions)
ordering=[{'anchor':x,'line':text[:start+p].count('\n')+1} for x,p in zip(anchors,positions)]
assert 'xactStopTimestamp is the time at which we log a commit / abort WAL record' in text
assert 'replorigin_session_origin_timestamp = GetCurrentTransactionStopTimestamp();' in section
full=R/'.evidence/gt-source-desktop-shm-lab-20261009'
lab=json.loads((full/'lab.json').read_text())
proof=json.loads((full/'independent-whole-final-verification.json').read_text())
db=next(x['database'] for x in proof['databases'] if x['sources'])
container=json.loads(subprocess.check_output(['docker','--context',lab['context'],'inspect',lab['name']],text=True))[0]
assert container['Id']==lab['container_id'] and container['RestartCount']==0
product=R/'services/aos-api/aos_api/aip_provider_capacity_publication_transaction.py'
product_hash=sha(product)
late=R/'.evidence/gt-source-body-expiry-commit-native-20261009/independent-verification.json'
late_hash=sha(late)
rows=[]
with psycopg.connect(host='127.0.0.1',port=lab['port'],dbname=db,user='aos_app',passfile=lab['passfile'],
                     options='-c default_transaction_read_only=on',row_factory=dict_row) as c:
    c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
    settings=c.execute("SELECT name,setting,context,source FROM pg_settings WHERE name IN ('track_commit_timestamp','server_version','synchronous_commit','fsync','full_page_writes') ORDER BY name").fetchall()
    by_name={x['name']:x['setting'] for x in settings}
    assert by_name['server_version'].startswith('16.14')
    assert all(by_name[x]=='on' for x in ('fsync','full_page_writes','synchronous_commit'))
    assert c.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']==lab['cluster']
    require_source_transaction_functions(c)
    rows=c.execute("""SELECT p.asset_id,p.content_hash,p.content_hash=encode(sha256(p.source_raw),'hex') AS hash_ok,
       aos_ed25519.verify(p.signature,p.source_raw,decode(s.signed_facts->>'sourceSignerPublicKey','base64')) AS signature_ok,
       s.finalized,v.native_xid::text AS xid,v.native_session,
       v.native_xid=s.native_xid AND v.native_pid=s.native_pid AND v.original_signed_facts=s.signed_facts AS provenance_ok
       FROM aos_capacity_publication_private.source_publication p JOIN aos_capacity_publication_private.source_pending s ON s.attempt_id=p.attempt_id
       JOIN aos_capacity_publication_private.source_provenance v ON (v.org_id,v.project_id,v.asset_id)=(p.org_id,p.project_id,p.asset_id)""").fetchall()
    assert rows
    for row in rows:
        assert all(row[x] for x in ('hash_ok','signature_ok','finalized','provenance_ok'))
        row['xid_status']=c.execute('SELECT pg_xact_status(%s::xid8) AS state',(row['xid'],)).fetchone()['state']
        assert row['xid_status']=='committed'
        try:
            with c.transaction():
                value=c.execute('SELECT pg_xact_commit_timestamp(%s::xid) AS recorded_at',(row['xid'],)).fetchone()['recorded_at']
            assert by_name['track_commit_timestamp']=='on'
            row['commit_time_query']={'recorded_at':value.isoformat() if value else None,'is_actual_end':False}
        except psycopg.errors.ObjectNotInPrerequisiteState as error:
            assert by_name['track_commit_timestamp']=='off' and error.sqlstate=='55000'
            row['commit_time_query']={'recorded_at':None,'sqlstate':error.sqlstate,'is_actual_end':False}
    assert c.execute('SHOW transaction_read_only').fetchone()['transaction_read_only']=='on'
    c.rollback()
assert sha(product)==product_hash and sha(late)==late_hash
out={'observed_at':datetime.now(timezone.utc).isoformat(),
     'result':'COMMIT_TIMESTAMP_IS_NOT_ACTUAL_END','head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),
     'authority_revision':a['project_revision'],'task':task['task_id'],'database':db,'cluster':lab['cluster'],
     'container_id':container['Id'],'container_started_at':container['State']['StartedAt'],'settings':settings,
     'retained_signed_sources':rows,'upstream_url':'https://raw.githubusercontent.com/postgres/postgres/REL_16_14/src/backend/access/transam/xact.c',
     'upstream_sha256':sha(up),'commit_time_before_durability_pipeline':ordering,
     'late_source_evidence_sha256':late_hash,'original_product_sha256':product_hash,
     'read_only':True,'track_parameter_changed':False,'source_attempt_replayed':False,
     'strict_actual_end_gate':'RED_UNPROVEN','execution_allowed':False,
     'limitation':'Source timestamp ordering is not a new measured WAL-delay attack; live tracking is off. Enabling tracking alone cannot turn the stored pre-flush timestamp into actual completion.'}
with (B/'audit-result.json').open('x') as f:json.dump(out,f,ensure_ascii=False,indent=2)
print(json.dumps({'result':out['result'],'signed_sources':len(rows),'track_commit_timestamp':by_name['track_commit_timestamp'],
                  'native_query_errors':[x['commit_time_query'].get('sqlstate') for x in rows],'read_only':True}))
