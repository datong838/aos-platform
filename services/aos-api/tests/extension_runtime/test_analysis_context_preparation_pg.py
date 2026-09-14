"""Actual task/evidence/Eval/Context; installed selection and configured roles are fixtures."""
from uuid import uuid4
import pytest
from psycopg.types.json import Jsonb
from tests.aip.test_aip_skill_publication_service import published_skill_runtime
from test_analysis_startup_evidence_pg import (
    startup_case, analysis_case, consumer_case, host_case, control_governed, governed,
    service_case, stored, pair, body,
)
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.aip_production_contract_store import canonical_hash
from aos_api.ecommerce_business_investigation_profile_catalog import INITIAL_STORE_PROFILE
from aos_api.ecommerce_business_investigation_aip_authority import build_responsibility_plan_request
from aos_api.ecommerce_analysis_compilation_selection import AnalysisCompilationSelectionReader
from aos_api.ecommerce_analysis_compilation_roles import AnalysisCompilationRoleReader
from aos_api.pipeline_source_selection_owner import PipelineSourceSelectionOwner
from test_ecommerce_analysis_start_operation import _package
from test_ecommerce_analysis_compilation_blueprint import request


@pytest.fixture(scope='module')
def context_publication():
    suffix=uuid4().hex[:8]
    runtime=published_skill_runtime(skill_id='ecommerce.skill.D01.ctx.'+suffix,
        canonical_logic_id='ecommerce.logic.D01.ctx.'+suffix,scope=TenantScope('org-org','dev-project'))
    with connect(runtime.scope) as conn:
        wait=conn.execute('SELECT EXTRACT(EPOCH FROM (occurred_at-clock_timestamp())) AS seconds FROM aip_publication_event WHERE org_id=%s AND project_id=%s AND event_id=%s',
            (*runtime.scope.key,runtime.published.publication_ref.resource_id)).fetchone()['seconds']
        assert wait<1
        if wait>0:conn.execute('SELECT pg_sleep(%s)',(float(wait)+0.02,))
    return runtime


@pytest.fixture
def context_case(context_publication,startup_case,monkeypatch):
    conn,analysis,claimed,run_ref=startup_case
    scope=analysis.scope
    analysis.source.control._owner._source=object.__new__(PipelineSourceSelectionOwner)
    roles=build_responsibility_plan_request({name:1 for name in (
        'ecommerce.data_advisor.default','ecommerce.customer_service.default','ecommerce.content_officer.default',
        'ecommerce.private_domain_manager.default','ecommerce.campaign_planner.default','ecommerce.shopping_advisor.default')})
    raw=roles.model_dump(mode='json',by_alias=True)
    plan_id='fixture-context-roles-'+uuid4().hex[:12]
    digest=canonical_hash(raw)
    # Frozen role metadata is a named configuration fixture; capabilities are
    # tested by the real selection reader's own suite, not claimed here.
    conn.execute('''INSERT INTO aip_responsibility_plan_head(org_id,project_id,plan_id,current_revision,version)
        VALUES(%s,%s,%s,1,1)''',(*scope.key,plan_id))
    conn.execute('''INSERT INTO aip_responsibility_plan_revision
        (org_id,project_id,plan_id,revision,profile,template_ref,slots,merge_decisions,content_hash,lifecycle,created_by)
        VALUES(%s,%s,%s,1,%s,%s,%s,'[]',%s,'frozen','fixture')''',
        (*scope.key,plan_id,roles.profile,Jsonb(raw['templateRef']),Jsonb(raw['slots']),digest))
    plan=dict(raw,tenant=dict(orgId=scope.org_id,projectId=scope.project_id),planId=plan_id,
        revision=1,contentHash=digest,lifecycle='frozen',readiness='ready',coverage='complete',blockers=[])
    def selected(self,connection,**kw):
        return kw['execute'](dict(responsibilityPlan=plan,
            skills=[context_publication.published.model_dump(mode='json',by_alias=True)]))
    monkeypatch.setattr(AnalysisCompilationSelectionReader,'run_current',selected)
    monkeypatch.setattr(AnalysisCompilationRoleReader,'run_current',
        lambda self,connection,**kw:kw['execute']({'responsibilityPlan':plan}))
    blueprint=_package().handle('ecommerce_growth_analysis_advance',request(),object())
    blueprint['stageSkills'][0]['skillId']=context_publication.published.skill_id
    blueprint['stageSkills'][0]['canonicalLogicId']=context_publication.published.canonical_logic_id
    blueprint['contentHash']=canonical_sha256({k:v for k,v in blueprint.items() if k!='contentHash'})
    return conn,analysis,claimed,run_ref,blueprint


def prepare(data,execute=lambda value:value):
    from aos_api.ecommerce_analysis_context_preparation import AnalysisContextPreparation
    conn,analysis,claimed,run_ref,blueprint=data
    return AnalysisContextPreparation(analysis).run_current(conn,claimed=claimed,run_ref=run_ref,
        domain_profile=INITIAL_STORE_PROFILE,blueprint=blueprint,execute=execute)


def test_real_task_bound_context_is_idempotent_and_atomic(context_case):
    conn,analysis,_,_,_=context_case
    before=conn.execute('SELECT count(*) AS n FROM aip_task WHERE org_id=%s AND project_id=%s',analysis.scope.key).fetchone()['n']
    with pytest.raises(RuntimeError,match='outer rollback'),conn.transaction():
        first=prepare(context_case)
        assert prepare(context_case)==first
        context=first['productionContext']
        assert context['taskId']==first['task']['id']
        assert context['briefRef']==first['taskBriefRef']
        assert context['evidenceBundleRef']==first['startupBundleRef']
        assert context['evalContractRef']==first['startupEvalRef']
        assert context['lifecycle']=='frozen' and context['readiness']=='ready'
        assert first['startupBundle']['licenseSummary']['allowedPurposes']==['analysis-start']
        assert conn.execute('SELECT count(*) AS n FROM aip_production_context_revision WHERE org_id=%s AND project_id=%s AND task_id=%s',
            (*analysis.scope.key,first['task']['id'])).fetchone()['n']==1
        raise RuntimeError('outer rollback')
    assert conn.execute('SELECT count(*) AS n FROM aip_task WHERE org_id=%s AND project_id=%s',analysis.scope.key).fetchone()['n']==before


@pytest.mark.parametrize('fault',['downstream','bundle-revoked'])
def test_context_callback_failure_rolls_back(context_case,fault):
    from aos_api.aip_production_contract_store import AipProductionContractStore
    from aos_api.aip_production_contracts import RevokeEvidenceBundleRequest
    from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
    from aos_api.ecommerce_growth_host_ports import HostTransaction
    conn,analysis,_,_,_=context_case
    def fail(value):
        if fault=='downstream':raise RuntimeError('downstream failure')
        bundle=value['startupBundleRef']
        AipProductionContractStore(TransactionBoundConnectFactory(HostTransaction(conn),analysis.scope)).revoke_evidence_bundle(
            analysis.scope,'fixture',bundle['resourceId'],'fixture-revoke',RevokeEvidenceBundleRequest(
                expectedRevision=bundle['revision'],expectedContentHash=bundle['contentHash'],reason='fixture revoked'))
        return value
    message='downstream failure' if fault=='downstream' else 'dependencies changed'
    with pytest.raises((ValueError,RuntimeError),match=message),conn.transaction():prepare(context_case,execute=fail)
    assert conn.execute("SELECT count(*) AS n FROM aip_production_context_revision WHERE org_id=%s AND project_id=%s AND profile=%s",
        (*analysis.scope.key,INITIAL_STORE_PROFILE.responsibility_template_code)).fetchone()['n']==0
