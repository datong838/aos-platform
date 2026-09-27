import pytest
from tests.test_ecommerce_analysis_compilation_binding import fixture
from aos_api.db import connect
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_business_investigation_profile_catalog import INITIAL_STORE_PROFILE
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef
from aos_api.tenant_scope import TenantScope
from test_analysis_startup_evidence_pg import (
    startup_case, analysis_case, consumer_case, host_case, control_governed, governed,
    service_case, stored, pair, body,
)


def test_actual_task_brief_preparation_is_atomic_and_idempotent(startup_case):
    from aos_api.ecommerce_analysis_task_preparation import prepare_analysis_task
    from aos_api.ecommerce_business_investigation_case import BusinessInvestigationCaseRevision
    from aos_api.ecommerce_business_investigation_run import BusinessInvestigationRunStore
    from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
    conn,analysis,claimed,run_ref=startup_case
    scope=TenantScope('org-org','dev-project')
    snapshot,_=analysis._phase(conn,claimed,lambda snap,request,dispatch:(snap,request))
    selection=PipelineExactRef.model_validate(snapshot['source']['policy']['sourceSelectionRef'])
    case=BusinessInvestigationCaseRevision.model_validate(snapshot['source']['case'])
    run=BusinessInvestigationRunStore(TransactionBoundConnectFactory(HostTransaction(conn),scope)).get_verified(scope,run_ref.resource_id)
    before=conn.execute('SELECT count(*) AS n FROM aip_task WHERE org_id=%s AND project_id=%s',scope.key).fetchone()['n']
    with pytest.raises(RuntimeError,match='outer rollback'),conn.transaction():
        def prepare():return prepare_analysis_task(HostTransaction(conn),scope=scope,actor='fixture-analysis',
            case=case,run=run,domain_profile=INITIAL_STORE_PROFILE,selection_ref=selection)
        first=prepare();second=prepare()
        assert first==second
        assert first['taskBriefRef']['revision']==2
        assert first['task']['goal']==first['taskBriefSpec']
        assert first['task']['selectionRef']==dict(resourceType='SourceSelectionRevision',
            resourceId=selection.resource_id,revision=str(selection.revision),authority='postgresql')
        assert first['taskBriefSpec']['domainProfileRef']['resourceId']==INITIAL_STORE_PROFILE.profile_id
        assert conn.execute('SELECT count(*) AS n FROM aip_task_brief_revision WHERE org_id=%s AND project_id=%s AND brief_id=%s',(*scope.key,first['taskBriefRef']['resourceId'])).fetchone()['n']==2
        assert conn.execute("SELECT count(*) AS n FROM aip_production_contract_receipt WHERE org_id=%s AND project_id=%s AND result_ref->>'resourceId'=%s",(*scope.key,first['taskBriefRef']['resourceId'])).fetchone()['n']==2
        raise RuntimeError('outer rollback')
    assert conn.execute('SELECT count(*) AS n FROM aip_task WHERE org_id=%s AND project_id=%s',scope.key).fetchone()['n']==before


@pytest.mark.parametrize('fault',['tenant','case','run'])
def test_task_preparation_rejects_invalid_lineage_before_storage(fault):
    from aos_api.ecommerce_analysis_task_preparation import prepare_analysis_task
    _,case,run=fixture();scope=TenantScope('org-org','dev-project')
    if fault=='tenant':scope=TenantScope('dev-org','dev-project')
    elif fault=='case':case.content_hash='sha256:'+'f'*64
    else:run.authority.content_hash='sha256:'+'f'*64
    with pytest.raises(ValueError):prepare_analysis_task(HostTransaction(object()),scope=scope,actor='fixture',
        case=case,run=run,domain_profile=INITIAL_STORE_PROFILE,
        selection_ref=PipelineExactRef(resourceType='SourceSelectionRevision',resourceId='source-selection-1',
            revision=1,contentHash='sha256:'+'a'*64))


@pytest.mark.parametrize('selection', [None,
    PipelineExactRef(resourceType='OtherRevision',resourceId='other-1',revision=1,
        contentHash='sha256:'+'a'*64)])
def test_task_preparation_requires_original_source_selection_before_storage(selection):
    from aos_api.ecommerce_analysis_task_preparation import prepare_analysis_task
    _,case,run=fixture()
    with pytest.raises(ValueError,match='exact Host analysis preparation inputs'):
        prepare_analysis_task(HostTransaction(object()),scope=TenantScope('org-org','dev-project'),
            actor='fixture',case=case,run=run,domain_profile=INITIAL_STORE_PROFILE,
            selection_ref=selection)
