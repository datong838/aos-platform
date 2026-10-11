"""Original historical ImpactPreview drafts through isolated fixed Source LOGIN."""
import hashlib,json
from pathlib import Path
from datetime import datetime,timedelta,timezone
from contextlib import contextmanager
import psycopg
from psycopg import sql
from psycopg.rows import dict_row
import real_contract as C
from aos_api.aip_bi_plan_issuer_connection import BIIssuerDatabaseConfig
from aos_api.aip_source_issuer_connection import SourceIssuerDatabaseConfig,connect_source_issuer_write
from aos_api.aip_production_contract_store import AipProductionContractStore,ProductionContractDependencyBlocked,ProductionContractConflict,ProductionContractNotFound,ProductionContractIdempotencyConflict
from aos_api.aip_production_contracts import CreateImpactPreviewRequest,ReviseImpactPreviewRequest
from aos_api.tenant_scope import TenantScope
R=C.R
PREFIX='impact-preview'
TABLES={t:'SELECT' for t in ['aip_task','aip_plan_revision','aip_task_brief_revision','aip_evidence_bundle_revision','aip_evidence_bundle_revoke_event','aip_eval_contract_revision','aip_responsibility_plan_revision','aip_stage_template_revision','aip_production_context_revision','aip_eval_suite_revision','aip_publication_event','aip_release_gate_decision']}
TABLES.update(aip_impact_preview_head='SELECT,INSERT,UPDATE',aip_impact_preview_revision='SELECT,INSERT',aip_production_contract_receipt='SELECT,INSERT')
def record(name,value):
 with (R/(PREFIX+'-'+name+'.json')).open('x') as f:json.dump(value,f,indent=2,default=str);f.write('\n')
def counts(c):
 return {t:c.execute(sql.SQL('SELECT count(*) AS n FROM {}').format(sql.Identifier(t))).fetchone()['n'] for t in ['aip_impact_preview_head','aip_impact_preview_revision','aip_production_contract_receipt','aip_task_run','aip_step_run']}
def main():
 assert not (R/(PREFIX+'-intent.json')).exists(),'Existing effect: reconcile only'
 restored=json.loads((C.ROOT/'.evidence/qyh-source-boundary-clone-20261011/restore-verified.json').read_text())
 item=json.loads(C.S.run(['inspect','--format','{"Id":{{json .Id}},"Mounts":{{json .Mounts}},"Ports":{{json .NetworkSettings.Ports}}}',C.TARGET]))
 assert item['Id']==restored['container']['Id'] and item['Mounts']==[] and item['Ports']=={'5432/tcp':[{'HostIp':'127.0.0.1','HostPort':'18431'}]}
 before=C.S.P.M.fingerprint(C.TARGET);metadata=C.S.D.metadata(C.TARGET)
 assert before==C.S.P.M.fingerprint('qyh-restored-pg-20261011')
 config=SourceIssuerDatabaseConfig('contract',BIIssuerDatabaseConfig('127.0.0.1',18431,C.DB,(R/'private/contract-identity/contract.pgpass').resolve()))
 connections=[];cases=[]
 @contextmanager
 def contract(scope):
  with connect_source_issuer_write(config,scope) as c:
   identity=c.execute('SELECT session_user AS login,current_user AS role,current_database() AS db').fetchone()
   assert identity=={'login':C.ROLE,'role':C.ROLE,'db':C.DB};connections.append(identity);yield c
 def no_plan(scope):raise AssertionError('Impact used Plan writer')
 store=AipProductionContractStore(lambda scope:C.runtime(scope,read_only=True),contract_connect_factory=contract,plan_connect_factory=no_plan)
 role=False;trigger=False
 with psycopg.connect(host='127.0.0.1',port=18431,dbname=C.DB,user='aos_app',autocommit=True,row_factory=dict_row) as admin:
  assert admin.execute('SELECT system_identifier::text AS cluster FROM pg_control_system()').fetchone()['cluster']==restored['cloneIdentity']['cluster']
  assert not admin.execute('SELECT 1 FROM pg_roles WHERE rolname=%s',(C.ROLE,)).fetchone()
  context=admin.execute('SELECT * FROM aip_production_context_revision WHERE context_id=%s AND org_id=%s AND project_id=%s',('ctx-daeec3f5a06049a08783',*C.SCOPE.key)).fetchone()
  plan=admin.execute('SELECT * FROM aip_plan_revision WHERE plan_revision_id=%s AND org_id=%s AND project_id=%s',('plan-bf6514bf8d7f49f2871e',*C.SCOPE.key)).fetchone()
  task=admin.execute('SELECT version,status FROM aip_task WHERE task_id=%s AND org_id=%s AND project_id=%s',(context['task_id'],*C.SCOPE.key)).fetchone();assert task['status']=='cancelled'
  stage=admin.execute('SELECT * FROM aip_stage_template_revision WHERE template_id=%s AND revision=2 AND org_id=%s AND project_id=%s',('stage-template-9a16f2cf2f6f410aa555',*C.SCOPE.key)).fetchone();assert stage
  impact={k:{'quality':'unknown'} for k in ['objectScope','channelScope','cost','budget','risks','reversibility','approvalChain','rateCapacityKill']}
  body=CreateImpactPreviewRequest(task_id=context['task_id'],plan_ref={'resourceType':'PlanRevision','resourceId':plan['plan_revision_id'],'revision':plan['revision'],'contentHash':plan['content_hash']},production_context_ref=plan['risk']['productionContract']['productionContextRef'],brief_ref=context['brief_ref'],evidence_bundle_ref=context['evidence_bundle_ref'],eval_contract_ref=context['eval_contract_ref'],responsibility_plan_ref=context['responsibility_plan_ref'],stage_template_ref={'resourceType':'StageTemplateRevision','resourceId':stage['template_id'],'revision':stage['revision'],'contentHash':stage['content_hash']},impact=impact,expires_at=datetime.now(timezone.utc)+timedelta(hours=1))
  initial=counts(admin);record('intent',{'database':C.DB,'cluster':restored['cloneIdentity']['cluster'],'containerId':item['Id'],'initialCounts':initial,'currentDatabaseTouched':False,'scriptHash':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
  try:
   admin.execute(sql.SQL('CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEROLE NOCREATEDB NOREPLICATION').format(sql.Identifier(C.ROLE)));role=True
   admin.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO {}').format(sql.Identifier(C.DB),sql.Identifier(C.ROLE)))
   admin.execute(sql.SQL('GRANT USAGE ON SCHEMA public TO {}').format(sql.Identifier(C.ROLE)))
   for t,p in TABLES.items():
    admin.execute(sql.SQL('GRANT {} ON {} TO {}').format(sql.SQL(p),sql.Identifier(t),sql.Identifier(C.ROLE)))
    admin.execute(sql.SQL("CREATE POLICY {} ON {} TO {} USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true)) WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))").format(sql.Identifier('qyh_impact_'+t),sql.Identifier(t),sql.Identifier(C.ROLE)))
   assert not admin.execute('SELECT 1 FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname=%s)',(C.ROLE,)).fetchone()
   made=store.create_impact_preview(C.SCOPE,'clone:test','qyh-impact-create',body);assert made.lifecycle.value=='draft' and made.readiness.value!='ready' and made.blockers
   assert store.create_impact_preview(C.SCOPE,'clone:test','qyh-impact-create',body).model_dump()==made.model_dump();cases.append('original-create-and-idempotency')
   revised_body=ReviseImpactPreviewRequest.model_validate({**body.model_dump(),'expected_version':1})
   cases.append(C.expect_error(ProductionContractNotFound,lambda:store.revise_impact_preview(TenantScope('dev-org','dev-project'),'clone:test',made.preview_id,'qyh-impact-canary',revised_body)))
   admin.execute("CREATE FUNCTION qyh_impact_rollback() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.idempotency_key='qyh-impact-rollback' THEN RAISE EXCEPTION 'QYH_IMPACT_RECEIPT_ROLLBACK'; END IF; RETURN NEW; END $$")
   admin.execute('CREATE TRIGGER qyh_impact_rollback BEFORE INSERT ON aip_production_contract_receipt FOR EACH ROW EXECUTE FUNCTION qyh_impact_rollback()');trigger=True
   saved=counts(admin)
   cases.append(C.expect_error(psycopg.Error,lambda:store.revise_impact_preview(C.SCOPE,'clone:test',made.preview_id,'qyh-impact-rollback',revised_body),state='P0001'));assert counts(admin)==saved
   revised=store.revise_impact_preview(C.SCOPE,'clone:test',made.preview_id,'qyh-impact-revise',revised_body);assert revised.version==2 and revised.revision==2 and revised.readiness.value!='ready'
   assert store.revise_impact_preview(C.SCOPE,'clone:test',made.preview_id,'qyh-impact-revise',revised_body).model_dump()==revised.model_dump();cases.append('original-revise-and-idempotency')
   cases.append(C.expect_error(ProductionContractConflict,lambda:store.revise_impact_preview(C.SCOPE,'clone:test',made.preview_id,'qyh-impact-stale',revised_body)))
   cases.append(C.expect_error(ProductionContractIdempotencyConflict,lambda:store.create_impact_preview(C.SCOPE,'clone:test','qyh-impact-create',body.model_copy(update={'expires_at':body.expires_at+timedelta(minutes=1)}))))
   saved=counts(admin);cases.append(C.expect_error(ProductionContractDependencyBlocked,lambda:store.freeze_impact_preview(C.SCOPE,'clone:test',made.preview_id,2,'qyh-impact-freeze-denied')));assert counts(admin)==saved
   cases.append(C.expect_error(psycopg.Error,forge_runtime,state='42501'))
   final=counts(admin);assert final==dict(initial,aip_impact_preview_head=initial['aip_impact_preview_head']+1,aip_impact_preview_revision=initial['aip_impact_preview_revision']+2,aip_production_contract_receipt=initial['aip_production_contract_receipt']+2)
   assert admin.execute('SELECT version,status FROM aip_task WHERE task_id=%s AND org_id=%s AND project_id=%s',(context['task_id'],*C.SCOPE.key)).fetchone()==task
   assert admin.execute('SELECT * FROM aip_plan_revision WHERE plan_revision_id=%s AND org_id=%s AND project_id=%s',(plan['plan_revision_id'],*C.SCOPE.key)).fetchone()==plan
   record('business-result',{'cases':cases,'connections':connections,'created':made.model_dump(mode='json',by_alias=True),'revised':revised.model_dump(mode='json',by_alias=True),'initialCounts':initial,'finalCounts':final,'oldTaskAndPlanUnchanged':True,'noNewRunOrStep':True,'historicalMetadataOnly':True,'formalLoginConnected':False,'formalPublisherConnected':False,'fullRestorationAccepted':False})
  except Exception as error:
   record('failure',{'errorType':type(error).__name__,'sqlstate':getattr(error,'sqlstate',None),'completedCases':cases,'observedCounts':counts(admin),'unknownEffectReplayAllowed':False});raise
  finally:
   if trigger:admin.execute('DROP TRIGGER qyh_impact_rollback ON aip_production_contract_receipt')
   admin.execute('DROP FUNCTION IF EXISTS qyh_impact_rollback()')
   if role:
    for t in TABLES:admin.execute(sql.SQL('DROP POLICY IF EXISTS {} ON {}').format(sql.Identifier('qyh_impact_'+t),sql.Identifier(t)))
    admin.execute(sql.SQL('DROP OWNED BY {}').format(sql.Identifier(C.ROLE)));admin.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(C.ROLE)))
 assert C.S.P.M.fingerprint(C.TARGET)==before==C.S.P.M.fingerprint('qyh-restored-pg-20261011')
 assert C.S.D.metadata(C.TARGET)==metadata==C.S.D.metadata('qyh-restored-pg-20261011')
 record('verified',{'originalAndCurrent647DataExact':True,'allOriginalMetadataExact':True,'temporaryRoleAndPoliciesRemoved':True,'noNewRunOrStep':True,'currentDatabaseTouched':False,'wholeTaskAccepted':False});print(json.dumps({'cases':len(cases),'positiveOriginalOperations':2,'noNewRunOrStep':True}))
def forge_runtime():
 with C.runtime(C.SCOPE,read_only=False) as c:
  c.execute("INSERT INTO aip_production_contract_receipt(org_id,project_id,receipt_id,operation,idempotency_key,request_hash,result_ref,created_by) VALUES('org-org','dev-project','qyh-impact-forged','impact_preview.create','qyh-impact-forged',%s,'{}','clone:test')",('a'*64,))
if __name__=='__main__':main()
