"""Independent native READ ONLY verification; never replay a fixture."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import psycopg
from psycopg.rows import dict_row
B=Path(__file__).resolve().parent;R=B.parents[1]
sys.path.insert(0,str(R/'services/aos-api'))
from aos_api.aip_budget_reservation_store import canonical_hash
from aos_api.aip_model_eval_authorization import ModelEvalRequestCreate
from aos_api.aip_model_runtime_contracts import RegisteredModelRevision
from aos_api.aip_model_governance_policy_contracts import QuotaPolicyRevision
lab=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
container=json.loads(subprocess.check_output(['docker','--context',lab['context'],'inspect',lab['name']],text=True))[0]
assert container['Id']==lab['container_id'] and container['RestartCount']==0
records=[]
for suffix in ('r2','r3'):
    prefix='model-owner-fixture-isolation-native-1651-'+suffix
    result=json.loads((B/(prefix+'-result.json')).read_text())
    assert result['pytest_exit']==0 and result['old_evidence_unchanged']
    assert all(x['phase']=='call' and x['outcome']=='passed' for x in result['results'])
    attempt=json.loads((B/(prefix+'-attempt.json')).read_text())
    assert container['State']['StartedAt']==attempt['started_at'] and attempt['free_bytes']>2500000000
    for path,digest in result['old_evidence_hashes_before'].items():
        assert hashlib.sha256((R/path).read_bytes()).hexdigest()==digest
    directory=B/prefix
    if suffix=='r2':
        proof=json.loads((directory/(prefix+'-owner-input.json')).read_text());apps=[proof['application']]
    else:
        proof=json.loads((directory/(prefix+'-whole-rollback-input.json')).read_text());apps=proof['applications']
    with psycopg.connect(host='127.0.0.1',port=5441,user='aos_app',dbname=result['database'],passfile=lab['passfile'],
                         options='-c default_transaction_read_only=on',row_factory=dict_row) as c:
        c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
        assert c.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']==lab['cluster']
        status=c.execute('SELECT pg_xact_status(%s::xid8) AS state',(proof['caller']['xid'],)).fetchone()['state']
        assert status==('committed' if suffix=='r2' else 'aborted')
        for app in apps:
            row=c.execute('SELECT request_json,request_hash FROM aip_model_eval_request WHERE org_id=%s AND project_id=%s AND request_id=%s',('org-org','dev-project',app['request_id'])).fetchone()
            assert canonical_hash(row['request_json'])==row['request_hash']==app['request_hash']
            req=ModelEvalRequestCreate.model_validate(row['request_json'])
            for table,key,ref,typ,exclusions in [
                ('aip_registered_model_revision','registered_model_id',req.source_ref,RegisteredModelRevision,{'tenant','contentHash','createdBy','createdAt','revision'}),
                ('aip_model_governance_policy_revision','policy_id',req.quota_policy_ref,QuotaPolicyRevision,{'tenant','contentHash','createdBy','createdAt'})]:
                sql='SELECT payload,content_hash FROM '+table+' WHERE org_id=%s AND project_id=%s AND '+key+'=%s AND revision=%s'
                if key=='policy_id':sql+=" AND policy_kind='quota'"
                rec=c.execute(sql,('org-org','dev-project',ref.asset_id,ref.revision)).fetchone();obj=typ.model_validate(rec['payload'])
                assert obj.content_hash==rec['content_hash']==ref.content_hash
                assert canonical_hash({k:v for k,v in obj.model_dump(mode='json',by_alias=True).items() if k not in exclusions})==ref.content_hash
            assert c.execute('SELECT count(*) AS n FROM aip_model_eval_budget_reservation WHERE request_id=%s',(app['request_id'],)).fetchone()['n']==(1 if suffix=='r2' else 0)
        counts={table:c.execute('SELECT count(*) AS n FROM '+table).fetchone()['n'] for table in (
            'aip_agent_run','aip_model_capacity_reservation','aos_model_eval_execution_private.case_result')}
        assert all(v==0 for v in counts.values())
        head=c.execute('SELECT version_num FROM alembic_version').fetchone()['version_num']
        readonly=c.execute('SHOW transaction_read_only').fetchone()['transaction_read_only'];assert readonly=='on';c.rollback()
    records.append({'database':result['database'],'head':head,'read_only':readonly,'caller_xid':proof['caller']['xid'],
        'caller_state':status,'original_applications_verified':len(apps),'legacy_fixture_hold_count':1 if suffix=='r2' else 0,
        'budget_holds_rolled_back':suffix=='r3','business_counts':counts})
library=subprocess.check_output(['docker','--context',lab['context'],'exec',lab['name'],'sha256sum','/usr/local/lib/postgresql/aos_ed25519.so'],text=True).split()[0]
assert library=='6054f5dd98337b2da957ba7984333f96e26c7141b0a8d8fbd4e3981d2bc4745e'
out={'result':'FRESH_ORIGINAL_OWNER_AND_WHOLE_PLAN_ROLLBACK_VERIFIED','databases':records,'old_evidence_unchanged':True,
    'source_verifier_sha256':library,'container_restarted':False,'execution_allowed':False,'full_model_admission':False,
    'failed_colima_attempt_retained':True,'limitations':'Original governance fixtures only, not Model-quality inputs, transport admission, tokenizer or formal Source completion.'}
with (B/'model-owner-fixture-isolation-independent-1651.json').open('x') as f:json.dump(out,f,indent=2)
print(json.dumps({'result':out['result'],'databases':len(records),'applications':sum(x['original_applications_verified'] for x in records),'business_counts_zero':True}))
