"""Original caller post-expiry COMMIT probe in fresh retained owned fixture."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

base=Path(__file__).resolve().parent
repo=base.parents[1]
assert subprocess.check_output(['docker','--context','colima-aos-a0v-test-only','inspect','aos-capacity-publication-scram-20261006','--format','{{.Id}}'],text=True).strip()=='4be7e2967dfd98ad81a6d9e554c420024e9e4e90cdf5649e19355d940542aad2'
passfile=Path(tempfile.gettempdir())/'aos-capacity-publication-scram-20261006.pgpass'
assert passfile.stat().st_mode&0o077==0
for key in ('PGPASSWORD','PGPASSFILE','PGSERVICE','PGSERVICEFILE','PGOPTIONS'):
    os.environ.pop(key,None)
os.environ.update(AOS_DATABASE_URL='postgresql://aos_app@127.0.0.1:5434/aos_meta',
    AOS_EXTENSION_PG_TEST='1',AOS_EXTENSION_PG_HOST='127.0.0.1',AOS_EXTENSION_PG_PORT='5434',
    AOS_EXTENSION_PG_USER='aos_app',AOS_EXTENSION_PG_DATABASE='aos_meta',
    AOS_TEST_RETAIN_DATABASE='1',AOS_TEST_USE_SHARED_DATABASE='0',AOS_DOTENV_DISABLED='1')
sys.path.insert(0,str(repo/'services/aos-api'))
sys.path.insert(0,str(repo/'.evidence/gt-atomic-model-admission-20261008'))
sys.path.insert(0,str(repo/'services/aos-api/tests/extension_runtime'))
sys.path.insert(0,str(repo/'services/aos-api/tests'))
# The original issuer forbids global credential variables. Only the exact
# owned admin login receives its existing passfile as a connection parameter.
import psycopg
from psycopg.conninfo import conninfo_to_dict
original_connect=psycopg.connect
def owned_connect(*args,**kwargs):
    assert len(args)<=1
    parameters=conninfo_to_dict(args[0] if args else kwargs.get('conninfo',''))
    for key in ('user','host','port','dbname'):
        if key in kwargs:parameters[key]=kwargs[key]
    if parameters.get('user')=='aos_app':
        assert parameters.get('host')=='127.0.0.1' and str(parameters.get('port'))=='5434'
        assert parameters.get('dbname')=='aos_meta' or parameters.get('dbname','').startswith('aos_test_')
        kwargs['passfile']=str(passfile)
    return original_connect(*args,**kwargs)
psycopg.connect=owned_connect
import json,hashlib
from psycopg.rows import dict_row
from datetime import datetime
data=repo/'.evidence/gt-judge-call-authority-20261008'
evidence=repo/'.evidence/gt-atomic-model-admission-20261008'
proof=json.loads((data/'judge-dual-bucket-green-r3-native-proof.json').read_text())
result=json.loads((data/'judge-dual-bucket-green-r3-result.json').read_text())
affected={'test_model_eval_judge_authority_pg.py','test_model_eval_judge_action_boundary.py','test_model_eval_budget_reservation_pg.py','test_aip_budget_reservation_contracts.py','test_model_eval_budget_bucket_contract.py','test_aip_budget_reservation_pg.py'}
checked=[x for x in result['results'] if x['nodeid'].split('::')[0].split('/')[-1] in affected]
assert len(checked)==1 and all(x['outcome']=='passed' for x in checked)
assert result['pytest_exit']==0 and len(result['results'])==1
# Preserve broader historical fixed-id/private schema bootstrap failures; do not label that full run GREEN.
assert proof['database']==result['database']=='aos_test_379975a6f96d_ti4_test'
def digest(value):
 return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str).encode()).hexdigest()
def normalized(value):return json.loads(json.dumps(value,default=str))
b=proof['judge_budget'];hold=b['hold'];keys=tuple(k for k in hold if k!='content_hash')
with psycopg.connect('postgresql://aos_app@127.0.0.1:5434/'+proof['database'],row_factory=dict_row) as conn:
 conn.execute('SET TRANSACTION READ ONLY')
 assert conn.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']=='7693564235776004128'
 assert conn.execute('SELECT version_num FROM alembic_version').fetchone()['version_num']=='a0v_159'
 assert conn.execute('SELECT pg_xact_status(%s::xid8) AS s',(b['caller']['xid'],)).fetchone()['s']=='committed'
 assert conn.execute('SELECT pg_xact_status(%s::xid8) AS s',(b['rollback_caller']['xid'],)).fetchone()['s']=='aborted'
 assert conn.execute('SELECT pg_xact_status(%s::xid8) AS s',(b['expiry_wait']['caller']['xid'],)).fetchone()['s']=='aborted'
 lock=proof['shared_fee_lock_order']
 assert conn.execute('SELECT pg_xact_status(%s::xid8) AS s',(lock['caller']['xid'],)).fetchone()['s']=='aborted'
 for table in ('aip_model_judge_budget_reservation','aip_model_judge_budget_reservation_bucket'):
  acl=conn.execute("SELECT relrowsecurity,relforcerowsecurity,has_table_privilege('aos_runtime',oid,'SELECT') AS s,has_table_privilege('aos_runtime',oid,'INSERT') AS i,has_table_privilege('aos_runtime',oid,'UPDATE') AS u,has_table_privilege('aos_runtime',oid,'DELETE') AS d,has_table_privilege('aos_runtime',oid,'TRUNCATE') AS t FROM pg_class WHERE oid=%s::regclass",('public.'+table,)).fetchone()
  assert acl==dict(relrowsecurity=True,relforcerowsecurity=True,s=True,i=True,u=False,d=False,t=False)
 conn.execute('SET LOCAL ROLE aos_runtime')
 conn.execute("SELECT set_config('aos.org_id','org-org',true),set_config('aos.project_id','dev-project',true)")
 row=conn.execute('SELECT * FROM aip_model_judge_budget_reservation WHERE reservation_id=%s',(hold['reservation_id'],)).fetchone()
 immutable=normalized({k:row[k] for k in keys})
 assert immutable=={k:hold[k] for k in keys} and row['content_hash']==hold['content_hash']=='sha256:'+digest(immutable)
 assert row['purpose']=='model-judge-call' and row['upper_bound_minor']==10 and row['state']=='held'
 req=conn.execute('SELECT * FROM aip_model_eval_judge_request WHERE request_id=%s',(row['request_id'],)).fetchone()
 assert (req['org_id'],req['project_id'])==('org-org','dev-project')
 assert normalized({k:req[k] for k in b['pending']})==b['pending'] and digest(req['request_json'])==row['request_hash']==req['request_hash']
 assert req['request_json']['executionAllowed'] is False and req['request_json']['upperBoundMinor']==10
 event=conn.execute('SELECT * FROM aip_action_approval_event WHERE approval_event_id=%s',(row['approval_event_id'],)).fetchone()
 assert normalized(event)==b['approval']
 proposal=conn.execute('SELECT * FROM aip_action_proposal WHERE proposal_id=%s',(row['proposal_id'],)).fetchone()
 assert proposal['purpose']=='model-judge-call' and proposal['status']=='approved' and proposal['policy_snapshot']['executionAllowed'] is False
 assert event['actor_id']!=proposal['created_by']==req['created_by'] and event['proposal_hash']==row['proposal_hash']==proposal['proposal_hash']
 projection={key:event[key] for key in ('approval_event_id','proposal_id','proposal_version','proposal_hash','decision','actor_id','reason','expires_at','created_at','action_binding_hash')}
 assert row['approval_ref']==dict(resourceType='ActionApprovalEvent',resourceId=event['approval_event_id'],revision=event['proposal_version'],contentHash='sha256:'+digest(projection))
 assert row['created_at']<event['expires_at']<=req['expires_at']
 original=req['request_json']['judgeGovernanceApplication']['request']
 assert row['budget_policy_ref']==original['budgetPolicyRef']
 assert row['price_ref']==dict(resourceType=original['priceRef']['assetType'],resourceId=original['priceRef']['assetId'],revision=original['priceRef']['revision'],contentHash='sha256:'+original['priceRef']['contentHash'])
 for source in ('targetApplication','judgeGovernanceApplication'):
  leg=req['request_json'][source]
  stored=conn.execute('SELECT * FROM aip_model_eval_request WHERE request_id=%s',(leg['requestId'],)).fetchone()
  assert stored['request_json']==leg['request'] and digest(stored['request_json'])==leg['requestHash']==stored['request_hash']
  assert conn.execute('SELECT count(*) AS n FROM aip_model_eval_budget_reservation WHERE request_id=%s',(leg['requestId'],)).fetchone()['n']==0
 links=conn.execute("SELECT l.*,b.held_minor,b.period_end,b.limit_minor FROM aip_model_judge_budget_reservation_bucket l JOIN aip_budget_bucket b USING(org_id,project_id,bucket_kind,account_id,period_start,currency) WHERE l.org_id='org-org' AND l.project_id='dev-project' AND l.reservation_id=%s",(row['reservation_id'],)).fetchall()
 assert len(links)==3 and {x['bucket_kind'] for x in links}=={'task','daily','pilot'}
 for link in links:
  expected='model-judge/'+row['request_id'] if link['bucket_kind']=='task' else row['budget_revision_ref']['resourceId']+':'+link['bucket_kind']
  assert link['account_id']==expected and link['reserved_minor']==link['held_minor']==10 and link['currency']=='CNY'
 from aos_api.aip_budget_cost_runtime import shared_risk_totals
 assert shared_risk_totals(conn,__import__('aos_api.tenant_scope',fromlist=['TenantScope']).TenantScope('org-org','dev-project'),row['budget_revision_ref']['resourceId'])==(1,10)
 wait=b['expiry_wait'];pw=wait['prewait'];short=conn.execute('SELECT * FROM aip_action_approval_event WHERE approval_event_id=%s',(wait['approval']['approval_event_id'],)).fetchone()
 assert normalized(short)==wait['approval'] and datetime.fromisoformat(pw['checkedAt'])<short['expires_at']
 assert digest({k:v for k,v in pw.items() if k!='sourceFactsHash'})==pw['sourceFactsHash']
 assert wait['observed'][0]==wait['caller']['pid'] and wait['observed'][1]=='Lock' and wait['outcomes']==['JUDGE_CURRENT_APPROVAL_REQUIRED']
 assert wait['thread_terminal'] and wait['original_hold_retained']
 assert lock['observed'][0]==lock['caller']['pid'] and lock['observed'][1]=='Lock' and lock['shared_bucket_free_before_fee'] and lock['outcomes']==['rolled-back'] and lock['thread_terminal']
 reader=proof['judge_parent_reader']
 from aos_api.aip_model_eval_execution_contracts import ModelJudgeParentBudgetLimit
 parent=ModelJudgeParentBudgetLimit.model_validate(reader['declaration'])
 assert str(row['reservation_id'])==parent.parent_hold_ref.resource_id and row['content_hash']==parent.parent_hold_ref.content_hash
 assert row['request_id']==parent.request_id and row['request_hash']==parent.request_hash
 assert row['approval_ref']==parent.approval_ref.model_dump(mode='json',by_alias=True)
 assert set(reader['negative_cases'])=={'hold_hash','request_hash','approval','policy','price','amount','canary','nonSER'}
 for identity in (reader['positive_caller'],reader['wait_caller']):
  assert conn.execute('SELECT pg_xact_status(%s::xid8) AS s',(identity['xid'],)).fetchone()['s']=='aborted'
 assert reader['observed'][0]==reader['wait_caller']['pid'] and reader['observed'][1]=='Lock'
 assert reader['outcomes']==['JUDGE_CURRENT_APPROVAL_REQUIRED'] and reader['thread_terminal'] and reader['hold_unchanged']
 assert datetime.fromisoformat(reader['prewait']['checkedAt'])<event['expires_at']
 assert conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']>event['expires_at']
 assert digest({k:v for k,v in reader['prewait'].items() if k!='sourceFactsHash'})==reader['prewait']['sourceFactsHash']
 owner=proof['judge_owner_preparation']
 from aos_api.aip_model_eval_execution_owner import ModelJudgeApplicationPreparation
 prepared=ModelJudgeApplicationPreparation.model_validate(owner['preparation'])
 assert prepared.parent_limit==parent and prepared.request==req['request_json']
 assert prepared.request_id==row['request_id'] and prepared.request_hash==row['request_hash']
 assert (prepared.caller_xid,prepared.caller_pid)==(reader['positive_caller']['xid'],reader['positive_caller']['pid'])
 original_xmin=conn.execute('SELECT xmin::text AS xid FROM aip_model_judge_budget_reservation WHERE reservation_id=%s',(row['reservation_id'],)).fetchone()['xid']
 assert original_xmin==prepared.parent_row_xmin==str(int(b['caller']['xid'])%4294967296)
 assert prepared.checked_at<event['expires_at'] and prepared.execution_allowed is False
 assert set(owner['negative_cases'])=={'old-quality-request','wrong-new-approval','empty-request','empty-approval','non-native','nonSER','canary','admin'}
 assert owner['copied_preparation_rejected'] and owner['expiry_wait_via_owner']
 dual=proof['dual_fee_lock_order']
 assert len(dual['fee_keys'])==2 and dual['fee_keys']==sorted(dual['fee_keys'],key=lambda k:(k['budget_id'],k['revision']))
 assert dual['fee_keys'][0]['budget_id']!=dual['fee_keys'][1]['budget_id']
 assert conn.execute('SELECT pg_xact_status(%s::xid8) AS s',(dual['caller']['xid'],)).fetchone()['s']=='aborted'
 assert dual['observed'][0]==dual['caller']['pid'] and dual['observed'][1]=='Lock'
 assert dual['first_fee_locked'] and dual['judge_bucket_free_before_second_fee']
 assert dual['thread_terminal'] and dual['outcomes']==['rolled-back']
 actual_fee_keys=[]
 for purpose in ('targetApplication','judgeGovernanceApplication'):
  bref=req['request_json'][purpose]['request']['budgetPolicyRef']
  policy=conn.execute("SELECT payload FROM aip_model_governance_policy_revision WHERE org_id='org-org' AND project_id='dev-project' AND policy_kind='budget' AND policy_id=%s AND revision=%s",(bref['assetId'],bref['revision'])).fetchone()['payload']
  budget=policy['budgetRevisionRef']
  fence=conn.execute("SELECT budget_id,revision FROM aip_budget_cost_runtime_fence WHERE org_id='org-org' AND project_id='dev-project' AND budget_id=%s AND revision=%s",(budget['assetId'],budget['revision'])).fetchone()
  assert fence is not None;actual_fee_keys.append(dict(fence))
 assert sorted(actual_fee_keys,key=lambda k:(k['budget_id'],k['revision']))==dual['fee_keys']
 union=proof['dual_bucket_lock_order']
 assert len(union['buckets'])==6 and union['buckets']==sorted(union['buckets'],key=lambda x:(x['bucket_kind'],x['account_id'],x['period_start'],x['currency']))
 assert union['five_preceding_locked']==[x['account_id'] for x in union['buckets'][:-1]]
 assert union['two_fees_locked']==[x['budget_id'] for x in dual['fee_keys']]
 assert union['observed']['pid']==union['caller']['pid'] and union['observed']['wait_event_type']=='Lock'
 assert union['outcomes']==['rolled-back'] and union['thread_terminal'] and union['held_counters_unchanged'] and union['new_parent_not_created']
 assert union['row_limit_mutation_rejected_by_original_guard'] and union['physical_source_joint_not_proven']
 assert conn.execute('SELECT pg_xact_status(%s::xid8) AS s',(union['caller']['xid'],)).fetchone()['s']=='aborted'
 assert conn.execute('SELECT pg_xact_status(%s::xid8) AS s',(union['metadata_caller']['xid'],)).fetchone()['s']=='committed'
 for bucket in union['buckets']:
  stored=conn.execute('''SELECT bucket_kind,account_id,period_start,currency,period_end,limit_minor,held_minor FROM aip_budget_bucket
    WHERE org_id='org-org' AND project_id='dev-project' AND bucket_kind=%s AND account_id=%s AND period_start=%s AND currency=%s''',
    (bucket['bucket_kind'],bucket['account_id'],bucket['period_start'],bucket['currency'])).fetchone()
  assert normalized(stored)==bucket
 assert conn.execute("SELECT count(*) AS n FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid() AND state<>'idle'").fetchone()['n']==0
 caseproof=proof['judge_case_set']
 expected_cases=[dict(caseId=c['caseId'],inputHash=c['inputArtifact']['contentHash'],expectedHash=c['expectedArtifact']['contentHash'] if c.get('expectedArtifact') is not None else None) for c in req['request_json']['cases']]
 assert caseproof['cases']==expected_cases and len(expected_cases)==2
 assert caseproof['case_set_hash']==digest(expected_cases)
 assert (caseproof['target_request_id'],caseproof['target_request_hash'])==(req['request_json']['targetApplication']['requestId'],req['request_json']['targetApplication']['requestHash'])
 assert set(caseproof['negative_cases'])=={'cropped','duplicate','reordered','input','expected','extra-permit','list','empty','unchecked-copy','wrong-target','target-hash','case-hash'}
 assert caseproof['execution_allowed'] is False and caseproof['expiry_wait_via_case_set']
 conn.execute("SELECT set_config('aos.org_id','dev-org',true)")
 assert conn.execute('SELECT count(*) AS n FROM aip_model_judge_budget_reservation').fetchone()['n']==0
# Actual old158 fallback remains original ordinary+Eval totals; read-only.
with psycopg.connect('postgresql://aos_app@127.0.0.1:5434/aos_test_c3181df11c54_ti4_test',row_factory=dict_row) as old:
 old.execute('SET TRANSACTION READ ONLY')
 assert old.execute('SELECT version_num FROM alembic_version').fetchone()['version_num']=='a0v_158'
 assert old.execute("SELECT to_regclass('public.aip_model_judge_budget_reservation') AS r").fetchone()['r'] is None
 old.execute('SET LOCAL ROLE aos_runtime');old.execute("SELECT set_config('aos.org_id','org-org',true),set_config('aos.project_id','dev-project',true)")
 budget=old.execute("SELECT budget_id FROM aip_budget_revision WHERE org_id='org-org' AND project_id='dev-project' LIMIT 1").fetchone()['budget_id']
 expected=old.execute("SELECT count(*) AS n,coalesce(sum(upper_bound_minor),0) AS risk FROM (SELECT upper_bound_minor FROM aip_budget_reservation WHERE org_id='org-org' AND project_id='dev-project' AND policy_ref->>'resourceId'=%s UNION ALL SELECT upper_bound_minor FROM aip_model_eval_budget_reservation WHERE org_id='org-org' AND project_id='dev-project' AND budget_revision_ref->>'resourceId'=%s) x",(budget,budget)).fetchone()
 assert shared_risk_totals(old,__import__('aos_api.tenant_scope',fromlist=['TenantScope']).TenantScope('org-org','dev-project'),budget)==(expected['n'],expected['risk'])
from datetime import datetime
files=['services/aos-api/aos_api/aip_model_eval_execution_owner.py','services/aos-api/aos_api/aip_model_eval_execution_reader.py','services/aos-api/aos_api/aip_model_eval_execution_contracts.py','services/aos-api/aos_api/aip_model_eval_judge_budget.py','services/aos-api/aos_api/aip_model_eval_judge_budget_authority.py','services/aos-api/alembic/versions/a0v_159_model_judge_budget.py','services/aos-api/aos_api/aip_budget_reservation_store.py','services/aos-api/aos_api/aip_model_eval_budget_reservation.py','services/aos-api/aos_api/aip_budget_cost_runtime.py','services/aos-api/tests/aip/test_model_eval_judge_authority_pg.py']
report=dict(status='GREEN',authority_revision='AOS-001597',head='210ef3ec842c58b8e639922524cc582c0d73749d',database=proof['database'],migration_head='a0v_159',exact_hold=hold,known_commit=True,rollback_aborted=True,affected_tests=1,broad_cumulative={'exit':1,'passed':60,'failed_or_setup_errors':32,'status':'RED_RETAINED_FIXED_FIXTURE_COLLISIONS'},shared_fee_lock_order=lock,budget_expiry_wait=wait,judge_parent_reader=reader,judge_owner_preparation=owner,judge_case_set=caseproof,dual_fee_lock_order=dual,dual_bucket_lock_order=union,legacy158_fallback=True,files={f:hashlib.sha256((repo/f).read_bytes()).hexdigest() for f in files},execution_allowed=False,limitations=['retained full158 then isolated actual Alembic159; not fresh full bootstrap','hold and bucket backing only; original runtime INSERT ledger is not private joint certificate','physical account/parent allocation/unique Intent/trusted finalizer/known joint COMMIT still pending','formal Root/Subject/config/expected read/model quality/natural chain remain pending','broader cumulative60PASS31FAIL1ERROR: original fixed-id/private-empty bootstrap collisions; cannot claim full regression GREEN'])
(evidence/'judge-dual-bucket-independent-r3.json').write_text(json.dumps(report,ensure_ascii=False,default=str,indent=2)+'\n')
print('GREEN: unified6budget buckets/5priorNOWAIT+2fees/knownmetadataCOMMIT+waiterabort/original definitionguard. Original new-purpose hold/three buckets/actual committed xid/aborted rollback/current-approval expiry after bucket wait/common fee-before-bucket/ACL/RLS/legacy158 independent readback')
