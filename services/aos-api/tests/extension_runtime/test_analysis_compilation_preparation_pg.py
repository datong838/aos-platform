"""Real Plan/Saga/Context/publication stores; selection and Eval source are fixtures."""
from uuid import uuid4
import pytest
from psycopg.types.json import Jsonb
from test_analysis_context_preparation_pg import (
    context_case,startup_case,analysis_case,consumer_case,host_case,control_governed,
    governed,service_case,stored,pair,body,
)
from tests.aip.test_aip_skill_publication_service import published_skill_runtime
from tests.test_aip_logic_publication_store import _create_graph,_succeed_dry_run,_request,_evidence,FakeEvidenceReader
from tests.test_ecommerce_analysis_skill_set import data
from aos_api.aip_logic_graph_store import LogicGraphStore
from aos_api.aip_logic_run_store import LogicRunStore
from aos_api.aip_logic_publication_store import LogicPublicationStore
from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.ecommerce_analysis_compilation_selection import AnalysisCompilationSelectionReader
from aos_api.ecommerce_analysis_skill_set import AnalysisSkillBindingSet
from aos_api.ecommerce_business_investigation_profile_catalog import INITIAL_STORE_PROFILE
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
from aos_api.aip_production_contract_store import AipProductionContractStore
from aos_api.aip_stage_template_authority import resolve_stage_template_source


@pytest.fixture(scope='module')
def publications():
    scope=TenantScope('org-org','dev-project')
    # Bootstrap scope via the same shared publication helper first.
    initial=published_skill_runtime(scope=scope)
    result=[]
    for n in range(3):
        graph=_create_graph(LogicGraphStore(),*scope.key)
        _succeed_dry_run(LogicRunStore(),graph,*scope.key,run_id='compile-'+uuid4().hex)
        report_id='compile-report-'+uuid4().hex
        LogicPublicationStore().publish(*scope.key,'fixture',graph.id,
            _request(graph,key='compile-publication-'+uuid4().hex,report_id=report_id),
            FakeEvidenceReader(_evidence(graph,report_id=report_id)))
        runtime=published_skill_runtime(scope=scope,skill_id='ecommerce.skill.compile.'+uuid4().hex,
            canonical_logic_id=graph.id,logic_revision_ref=VersionedAssetRef(assetType='LogicRevision',
                assetId=graph.id,revision=graph.revision,contentHash=graph.graph_hash))
        result.append(runtime)
    return result


@pytest.fixture(scope='module')
def context_publication(publications):
    runtime=publications[0]
    with connect(runtime.scope) as conn:
        wait=conn.execute('SELECT EXTRACT(EPOCH FROM (occurred_at-clock_timestamp())) AS seconds FROM aip_publication_event WHERE event_id=%s',
            (runtime.published.publication_ref.resource_id,)).fetchone()['seconds']
        assert wait<1
        if wait>0:conn.execute('SELECT pg_sleep(%s)',(float(wait)+0.02,))
    return runtime


@pytest.fixture
def compilation_case(context_case,publications,monkeypatch):
    conn,analysis,claimed,run_ref,blueprint=context_case
    for entry,runtime in zip(blueprint['stageSkills'],publications):
        entry.update(skillId=runtime.published.skill_id,canonicalLogicId=runtime.published.canonical_logic_id)
    blueprint['contentHash']=canonical_sha256({k:v for k,v in blueprint.items() if k!='contentHash'})
    # Named readiness fixtures in the disposable DB, not live capability calls.
    role_rows=conn.execute('SELECT slots FROM aip_responsibility_plan_revision WHERE org_id=%s AND project_id=%s',analysis.scope.key).fetchall()
    template='fixture-compile-agent-'+uuid4().hex
    conn.execute("""INSERT INTO aip_agent_template_revision
        (template_id,revision,display_name,role_key,lifecycle,source_ref,source_license,manifest,content_hash,created_by)
        VALUES(%s,1,'fixture','fixture','draft','{}','fixture','{}',%s,'fixture')""",(template,'a'*64))
    assigned={}
    for row in role_rows:
        for slot in row['slots']:
            assigned.setdefault(slot['assignee']['resourceId'],set()).update(slot['requiredCapabilityIds'])
    for instance,capabilities in assigned.items():
        conn.execute("""INSERT INTO aip_agent_instance
            (org_id,project_id,instance_id,template_id,template_revision,status,overlay,created_by)
            VALUES(%s,%s,%s,%s,1,'active','{}','fixture') ON CONFLICT DO NOTHING""",(*analysis.scope.key,instance,template))
        cap_refs=[]
        for cap in sorted(capabilities):
            cap_id='fixture-cap-'+uuid4().hex
            conn.execute("""INSERT INTO aip_capability_binding
                (org_id,project_id,binding_id,capability_ref,secret_ref,health,network_policy_revision,quota_policy_revision,
                 timeout_ms,max_concurrency,status,operational_readiness,dependency_snapshot_hash,readiness_expires_at,last_evaluated_at)
                VALUES(%s,%s,%s,%s,'secret://fixture-not-real','healthy','fixture','fixture',1000,1,'active',
                    'available',%s,clock_timestamp()+interval '1 hour',clock_timestamp())""",
                (*analysis.scope.key,cap_id,Jsonb(dict(resourceType='Capability',resourceId=cap)), 'f'*64))
            cap_refs.append(cap_id)
        skill=publications[0].published
        conn.execute("""INSERT INTO aip_skill_binding
            (org_id,project_id,binding_id,instance_id,skill_id,skill_revision,capability_refs,budget_policy_ref,status)
            VALUES(%s,%s,%s,%s,%s,%s,%s,'{}','active') ON CONFLICT DO NOTHING""",
            (*analysis.scope.key,'fixture-role-skill-'+uuid4().hex,instance,skill.skill_id,skill.revision,Jsonb(cap_refs)))
    before=AnalysisCompilationSelectionReader.run_current
    def selected(self,connection,**kw):
        old=before(self,connection,**{**kw,'execute':lambda value:value})
        store=AipProductionContractStore(TransactionBoundConnectFactory(HostTransaction(conn),analysis.scope),
            stage_template_source_resolver=resolve_stage_template_source)
        role=store.get_responsibility_plan(analysis.scope,old['responsibilityPlan']['planId'],conn=conn)
        row=conn.execute('SELECT template_id FROM aip_stage_template_revision WHERE org_id=%s AND project_id=%s AND content_hash=%s',
            (*analysis.scope.key,canonical_sha256(blueprint['stageTemplateRequest']).removeprefix('sha256:'))).fetchone()
        stage=store.get_stage_template(analysis.scope,row['template_id'],conn=conn)
        _,sample,raw=data()
        bindings=[]
        for i,runtime in enumerate(publications):
            skill=runtime.published
            b=sample.model_dump(mode='json',by_alias=True)
            b.update(bindingId='fixture-binding-'+str(i),skill=dict(assetType='SkillTemplate',assetId=skill.skill_id,
                revision=skill.revision,contentHash=skill.content_hash))
            bindings.append(b)
        role_ref=dict(resourceType='ResponsibilityPlanRevision',resourceId=role.plan_id,revision=role.revision,contentHash=role.content_hash)
        raw.update(schemaVersion='aos.ecommerce.analysis-skill-binding-set/v1',bindings=bindings,responsibilityPlanRef=role_ref)
        raw['contentHash']=canonical_sha256(raw)
        skillset=AnalysisSkillBindingSet.model_validate(raw)
        return kw['execute'](dict(compilationBlueprint=blueprint,
            currentInstallation={k:raw[k] for k in ('installationId','generation','executionEpoch')},
            responsibilityPlan=role.model_dump(mode='json',by_alias=True),stageTemplate=stage.model_dump(mode='json',by_alias=True),
            skills=[r.published.model_dump(mode='json',by_alias=True) for r in publications],skillBindingSet=raw,
            skillBindingSetRef=skillset.exact_ref.model_dump(mode='json',by_alias=True)))
    monkeypatch.setattr(AnalysisCompilationSelectionReader,'run_current',selected)
    return context_case


def compile(data,execute=lambda value:value):
    from aos_api.ecommerce_analysis_compilation_preparation import AnalysisCompilationPreparation
    from aos_api.ecommerce_analysis_context_preparation import AnalysisContextPreparation
    conn,analysis,claimed,run_ref,blueprint=data
    return AnalysisCompilationPreparation(AnalysisContextPreparation(analysis)).run_current(conn,
        claimed=claimed,run_ref=run_ref,domain_profile=INITIAL_STORE_PROFILE,blueprint=blueprint,execute=execute)


def test_real_saga_creates_plan_and_receipt_in_outer_transaction(compilation_case,monkeypatch):
    conn,analysis,_,_,_=compilation_case
    from aos_api.aip_business_investigation_compile_saga import BusinessInvestigationCompileSaga
    from aos_api.aip_business_investigation_compiler import BusinessInvestigationProfileCompiler
    from aos_api.aip_production_contracts import ExactRevisionRef
    original=BusinessInvestigationCompileSaga.execute
    original_compile=BusinessInvestigationProfileCompiler.compile
    def check_refs(self,scope,actor,key,request):
        assert not self._exact_ref_resolver(TenantScope('dev-org','dev-project'),request.case_ref)
        assert not self._exact_ref_resolver(scope,ExactRevisionRef(resourceType='Unknown',resourceId='unknown',revision=1,contentHash='a'*64))
        return original_compile(self,scope,actor,key,request)
    def replay(self,*args,**kwargs):
        first=original(self,*args,**kwargs)
        again=original(self,*args,**kwargs)
        assert again.replayed and again.authority==first.authority
        return first
    monkeypatch.setattr(BusinessInvestigationProfileCompiler,'compile',check_refs)
    monkeypatch.setattr(BusinessInvestigationCompileSaga,'execute',replay)
    with pytest.raises(RuntimeError,match='rollback after compilation'),conn.transaction():
        result=compile(compilation_case)
        receipt=result['compilationReceipt']
        assert receipt['runtimeAuthorized'] is False
        row=conn.execute('SELECT * FROM aip_plan_revision WHERE org_id=%s AND project_id=%s AND plan_revision_id=%s',
            (*analysis.scope.key,receipt['planRef']['resourceId'])).fetchone()
        assert row is not None
        assert conn.execute('SELECT count(*) AS n FROM aip_business_investigation_compile_receipt WHERE org_id=%s AND project_id=%s',
            analysis.scope.key).fetchone()['n']==1
        raise RuntimeError('rollback after compilation')
    assert conn.execute('SELECT count(*) AS n FROM aip_business_investigation_compile_receipt WHERE org_id=%s AND project_id=%s',analysis.scope.key).fetchone()['n']==0


def test_downstream_failure_leaves_no_compilation(compilation_case):
    conn,analysis,_,_,_=compilation_case
    def fail(value):
        assert value['compilationReceipt']['planRef']['resourceId']
        raise RuntimeError('downstream failed')
    with pytest.raises(RuntimeError,match='downstream failed'),conn.transaction():compile(compilation_case,execute=fail)
    assert conn.execute('SELECT count(*) AS n FROM aip_business_investigation_compile_receipt WHERE org_id=%s AND project_id=%s',analysis.scope.key).fetchone()['n']==0


def test_capability_revocation_after_compile_rolls_back(compilation_case):
    conn,analysis,_,_,_=compilation_case
    def revoke(value):
        conn.execute("UPDATE aip_capability_binding SET status='suspended' WHERE org_id=%s AND project_id=%s AND binding_id LIKE 'fixture-cap-%%'",analysis.scope.key)
        return value
    with pytest.raises(ValueError,match='compilation input changed'),conn.transaction():compile(compilation_case,execute=revoke)
    assert conn.execute('SELECT count(*) AS n FROM aip_business_investigation_compile_receipt WHERE org_id=%s AND project_id=%s',analysis.scope.key).fetchone()['n']==0
