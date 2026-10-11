"""Exercise original compilation dependency gates without allowing any write."""
import hashlib
import json
from pathlib import Path
from contextlib import contextmanager
import real_contract as C
from aos_api.aip_production_contract_store import (AipProductionContractStore,
    ProductionContractDependencyBlocked, ProductionContractNotFound)
from aos_api.aip_production_contracts import CompileStageTemplateRequest, ExactRevisionRef
from aos_api.aip_responsibility_template_authority import resolve_responsibility_template
from aos_api.aip_stage_template_authority import resolve_stage_template_source
from aos_api.tenant_scope import TenantScope

out=C.R/'stage-compile-dependency-result.json'
assert not out.exists(), 'Existing result: read-only reconciliation required'
connections=[]
@contextmanager
def source_readonly(scope):
    with C.runtime(scope,read_only=True) as conn:
        row=conn.execute("SELECT current_database() AS db,current_user AS role,current_setting('transaction_read_only') AS readonly,system_identifier::text AS cluster FROM pg_control_system()").fetchone()
        frozen=json.loads((C.ROOT/'.evidence/qyh-source-boundary-clone-20261011/restore-verified.json').read_text())
        assert row['db']==C.DB and row['role']=='aos_runtime' and row['readonly']=='on'
        assert row['cluster']==frozen['cloneIdentity']['cluster']
        connections.append(row)
        yield conn
def never_plan(scope):
    raise AssertionError('Blocked compilation must not open a Plan writer')
store=AipProductionContractStore(lambda scope:C.runtime(scope,read_only=True),
    contract_connect_factory=source_readonly,plan_connect_factory=never_plan,
    responsibility_template_resolver=resolve_responsibility_template,
    stage_template_source_resolver=resolve_stage_template_source)
context=store.get_production_context(C.SCOPE,'ctx-daeec3f5a06049a08783')
template=store.get_stage_template(C.SCOPE,'stage-template-9a16f2cf2f6f410aa555',2)
responsibility=store.get_responsibility_plan(C.SCOPE,context.responsibility_plan_ref.resource_id,context.responsibility_plan_ref.revision)
assert context.readiness.value=='ready' and template.profile==context.profile and template.lifecycle.value=='frozen'
assert responsibility.readiness.value=='blocked' and len(responsibility.blockers)==6
assert {x.code for x in responsibility.blockers}=={'SKILL_BINDING_STALE'}
def count():
    with C.runtime(C.SCOPE,read_only=True) as conn:
        return {t:conn.execute('SELECT count(*) AS n FROM '+t).fetchone()['n']
            for t in ('aip_task','aip_plan_revision','aip_task_run','aip_step_run','aip_production_contract_receipt')}
with C.runtime(C.SCOPE,read_only=True) as conn:
    task=conn.execute('SELECT version,status FROM aip_task WHERE org_id=%s AND project_id=%s AND task_id=%s',(*C.SCOPE.key,context.task_id)).fetchone()
assert task['status']=='cancelled'
body=CompileStageTemplateRequest(task_id=context.task_id,expected_task_version=task['version'],
    template_revision=template.revision,template_content_hash=template.content_hash,
    responsibility_plan_ref=context.responsibility_plan_ref,
    production_context_ref=ExactRevisionRef(resource_type='ProductionContextRevision',resource_id=context.context_id,
        revision=context.revision,content_hash=context.content_hash),profile=context.profile)
before=count()
cases=[]
for scope,key,request,kind,code in (
    (C.SCOPE,'qyh-stage-compile-dependency-blocked',body,ProductionContractDependencyBlocked,'RESPONSIBILITY_PLAN_NOT_READY'),
    (C.SCOPE,'qyh-stage-compile-dependency-drift',body.model_copy(update={'template_content_hash':'0'*64}),ProductionContractDependencyBlocked,'STAGE_TEMPLATE_DRIFTED'),
    (TenantScope('dev-org','dev-project'),'qyh-stage-compile-dependency-canary',body,ProductionContractNotFound,None)):
    try:
        store.compile_stage_template(scope,'test-only:no-execution',template.template_id,key,request)
    except kind as error:
        if code is not None:assert str(error)==code
        cases.append({'scope':list(scope.key),'errorType':type(error).__name__,'code':code})
    else:raise AssertionError('Original compile rejection missing')
assert count()==before
fresh=store.get_responsibility_plan(C.SCOPE,responsibility.plan_id,responsibility.revision)
assert fresh.model_dump()==responsibility.model_dump()
with C.runtime(C.SCOPE,read_only=True) as conn:
    assert conn.execute('SELECT version,status FROM aip_task WHERE org_id=%s AND project_id=%s AND task_id=%s',(*C.SCOPE.key,context.task_id)).fetchone()==task
result={'task':'qyh-source-boundary-rehearsal-20261011','authority':'AOS-001896',
    'contextHistoricalReadyNotCurrentExecutionProof':True,'taskStatus':task['status'],
    'responsibilityCurrentBlockers':[x.code for x in fresh.blockers],
    'originalCompilationDenials':cases,'readonlySourceConnections':connections,
    'fiveTableCountsUnchanged':before,'originalTaskAndResponsibilityUnchanged':True,
    'databaseWrites':0,'currentAuthoritativeDatabaseConnected':False,
    'cancelledTaskOrOldRunReplayed':False,'fullRestorationAccepted':False,
    'scriptHash':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
with out.open('x') as stream:stream.write(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'originalCompileDenials':len(cases),'staleBindings':len(fresh.blockers),'taskStatus':task['status'],'databaseWrites':0}))
