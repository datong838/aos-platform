"""Read-only failed fixture diagnosis, no credential or raw claim output."""
import tempfile,json
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
from aos_api.aip_provider_capacity_action import ProviderCapacityActionGuard
from aos_api.aip_provider_capacity_source_action import ProviderCapacitySourceActionGuard
from aos_api.aip_action_policy import classify_action_risk
from aos_api.aip_action_store import canonical_hash
password=(Path(tempfile.gettempdir())/'aos-capacity-publication-scram-20261006.pgpass').read_text().strip().split(':')[-1]
with psycopg.connect(host='127.0.0.1',port=5434,user='aos_app',password=password,dbname='aos_test_f33dae69eb88_ti4_test',row_factory=dict_row) as c:
 c.read_only=True
 c.execute("SELECT set_config('aos.org_id','org-org',true),set_config('aos.project_id','dev-project',true)")
 c.execute('SET LOCAL ROLE aos_capacity_publication_owner')
 results=[]
 print(c.execute("SELECT bool_and(task_id IS NULL) AS task_null,bool_and(run_id IS NULL) AS run_null,bool_and(object_ref IS NULL) AS object_sql_null,bool_and(object_ref='null'::jsonb) AS object_json_null,bool_and(impact_preview_id IS NULL) AS impact_null,bool_and(client_risk_hint IS NULL) AS risk_hint_null FROM public.aip_action_proposal WHERE status='approved'").fetchone())
 for p in c.execute("SELECT * FROM public.aip_action_proposal WHERE status='approved'").fetchall():
  guard=ProviderCapacitySourceActionGuard if p['action_type_id']==ProviderCapacitySourceActionGuard.action_id else ProviderCapacityActionGuard
  if p['action_type_id']!=guard.action_id:continue
  risk=classify_action_risk(guard.action_id,guard.action_snapshot,{},None)
  policy=dict(floor=risk.floor.value,reasons=list(risk.reasons),**risk.approval_policy)
  d=c.execute('SELECT * FROM public.aip_action_draft WHERE proposal_id=%s',(p['proposal_id'],)).fetchone()
  e=c.execute('SELECT * FROM public.aip_action_approval_event WHERE proposal_id=%s',(p['proposal_id'],)).fetchone()
  obj=c.execute('SELECT id,name,description,published,properties,required_markings FROM public.meta_object_type WHERE id=%s',(guard.object_id,)).fetchone()
  act=c.execute("SELECT jsonb_build_object('id',id,'name',name,'objectType',object_type,'parameters',parameters,'requiredMarkings',required_markings,'submissionCriteria',submission_criteria) AS body FROM public.meta_action_type WHERE id=%s",(guard.action_id,)).fetchone()['body']
  hashes=c.execute("SELECT encode(sha256(convert_to(public.canonical_asset_registry_jsonb(%s::jsonb),'UTF8')),'hex') AS draft_hash",(json.dumps(d['snapshot']),)).fetchone()
  eligibility=canonical_hash(dict(tenant=dict(orgId=p['org_id'],projectId=p['project_id']),actorId=e['actor_id'],roles=['owner'],slotId='checker.1',approvalPolicyHash=p['approval_policy_hash']))
  results.append(dict(action=guard.action_id,object_equal=dict(obj)==guard.object_snapshot,metadata_equal=act==guard.action_snapshot,snapshot_equal=p['action_type_snapshot']=={**guard.action_snapshot,'revisionHash':canonical_hash(guard.action_snapshot)},policy_equal=p['policy_snapshot']==policy,policy_hash=canonical_hash(p['policy_snapshot'])==p['approval_policy_hash'],draft_status=d['status'],draft_hash_native=hashes['draft_hash']==p['proposal_hash'],draft_hash_python=canonical_hash(d['snapshot'])==p['proposal_hash'],draft_metadata=d['snapshot'].get('actionType')==p['action_type_snapshot'],draft_payload=d['snapshot'].get('payload')==p['payload'],draft_policy=d['snapshot'].get('policy')==p['policy_snapshot'],draft_binding=d['snapshot'].get('actionBindingHash')==p['action_binding_hash'],independent=e['actor_id']!=p['created_by'],eligibility=eligibility==e['eligibility_snapshot_hash']))
 print(json.dumps(results,indent=2))
