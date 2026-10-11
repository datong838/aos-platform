import hashlib,json,subprocess
from datetime import datetime,timezone
from pathlib import Path
from uuid import UUID
from aos_api.extension_runtime.configuration_store import _decode
ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
INSTALL='97aeb2e7-59ba-40f6-89a3-fb0293bc0497'
GEN='3a445eee-aa28-4459-9e5a-f12a806a94b1'
def lit(value):
    assert isinstance(value,str) and '\x00' not in value
    return "'"+value.replace("'","''")+"'"
def read(sql):
    r=subprocess.run(['docker','--context','colima-aos-extension','exec','aos-a0v-recovery-pg','psql','-X','-qAt','-v','ON_ERROR_STOP=1','-U','aos_app','-d','aos_meta_head','-c','BEGIN ISOLATION LEVEL SERIALIZABLE READ ONLY; '+sql+'; COMMIT;'],capture_output=True,text=True,check=True,timeout=30)
    return json.loads(r.stdout)
identity=read("SELECT json_build_object('database',current_database(),'migration',(SELECT version_num FROM alembic_version),'cluster',(SELECT system_identifier::text FROM pg_control_system()),'readOnly',current_setting('transaction_read_only'))")
assert identity['cluster']=='7683855731447750695' and identity['readOnly']=='on'
rows=read(f"SELECT coalesce(json_agg(row_to_json(x)),'[]'::json) FROM (SELECT configuration_id,revision,payload,content_hash,previous_hash,actor FROM extension_runtime_configuration WHERE org_id='org-org' AND project_id='dev-project' AND installation_id='{INSTALL}' AND generation='{GEN}') x")
assert len(rows)==1
ref,document=_decode(('org-org','dev-project',UUID(INSTALL),UUID(GEN)),rows[0])
mapping={'aip.responsibility_plan_revision':('aip_responsibility_plan','plan_id'),
         'aip.runtime_policy_revision':('aip_runtime_policy','runtime_policy_id'),
         'aip.budget_revision':('aip_budget','budget_id')}
summaries=[]
for purpose,refs in [('role',document.roleRefs),('data',document.dataRefs),('budget',(document.budgetRef,)),('policy',(document.policyRef,))]:
    for source in refs:
        entry={'purpose':purpose,'ref':source.model_dump(mode='json')}
        if source.authority in mapping:
            base,key=mapping[source.authority]
            row=read(f"SELECT row_to_json(x) FROM (SELECT h.current_revision,r.revision,r.content_hash,r.lifecycle FROM {base}_head h JOIN {base}_revision r ON r.org_id=h.org_id AND r.project_id=h.project_id AND r.{key}=h.{key} AND r.revision=h.current_revision WHERE h.org_id='org-org' AND h.project_id='dev-project' AND h.{key}={lit(source.id)}) x")
            entry['head']=row
            entry['headRefExact']=bool(row and row['revision']==source.revision and 'sha256:'+row['content_hash']==source.hash)
        elif source.authority=='aip.data_classification_policy_revision':
            row=read(f"SELECT row_to_json(x) FROM (SELECT h.current_revision,r.revision,r.content_hash,r.lifecycle,r.effective_from,r.effective_until,(r.effective_from<=clock_timestamp() AND r.effective_until>clock_timestamp()) AS effective_now FROM aip_runtime_guard_policy_head h JOIN aip_runtime_guard_policy_revision r ON r.org_id=h.org_id AND r.project_id=h.project_id AND r.policy_kind=h.policy_kind AND r.policy_id=h.policy_id AND r.revision=h.current_revision WHERE h.org_id='org-org' AND h.project_id='dev-project' AND h.policy_kind='data_classification' AND h.policy_id={lit(source.id)}) x")
            entry['head']=row
            entry['headRefExact']=bool(row and row['revision']==source.revision and 'sha256:'+row['content_hash']==source.hash)
        else:
            entry['headRefExact']='not_checked_by_this_collector'
        summaries.append(entry)
policy=read(f"SELECT row_to_json(x) FROM (SELECT payload->'budgetPolicyRef' AS budget_ref_camel,payload->'budget_policy_ref' AS budget_ref_snake FROM aip_runtime_policy_revision WHERE org_id='org-org' AND project_id='dev-project' AND runtime_policy_id={lit(document.policyRef.id)} AND revision={document.policyRef.revision}) x")
budget_ref=policy['budget_ref_camel']
budget_policy=read(f"SELECT json_build_object('headRevision',(SELECT current_revision FROM aip_model_governance_policy_head WHERE org_id='org-org' AND project_id='dev-project' AND policy_kind='budget' AND policy_id={lit(budget_ref['assetId'])}),'revisions',(SELECT json_agg(json_build_object('revision',r.revision,'contentHash',r.content_hash,'lifecycle',r.lifecycle,'effectiveFrom',r.effective_from,'effectiveUntil',r.effective_until,'effectiveNow',r.effective_from<=clock_timestamp() AND r.effective_until>clock_timestamp())) FROM aip_model_governance_policy_revision r WHERE r.org_id='org-org' AND r.project_id='dev-project' AND r.policy_kind='budget' AND r.policy_id={lit(budget_ref['assetId'])} AND (r.revision={int(budget_ref['revision'])} OR r.revision=(SELECT current_revision FROM aip_model_governance_policy_head WHERE org_id='org-org' AND project_id='dev-project' AND policy_kind='budget' AND policy_id={lit(budget_ref['assetId'])}))))")
result={'observedAt':datetime.now(timezone.utc).isoformat(),'identity':identity,'configurationRef':ref.model_dump(mode='json'),'currentDecoderHashVerified':True,'sourceChecks':summaries,'runtimePolicyBudgetRef':policy,'budgetPolicyReadback':budget_policy,'effects':'READ ONLY; configuration decoding is offline, no current permission or full source payload authorization','sourceSha256':{str(p.relative_to(REPO)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [REPO/'services/aos-api/aos_api/extension_runtime/configuration_store.py',REPO/'services/aos-api/aos_api/extension_runtime/configuration_contracts.py']}}
(ROOT/'readback.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False))
