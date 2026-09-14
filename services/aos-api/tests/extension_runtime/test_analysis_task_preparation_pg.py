import pytest
from tests.test_ecommerce_analysis_compilation_binding import fixture
from aos_api.db import connect
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_business_investigation_profile_catalog import INITIAL_STORE_PROFILE
from aos_api.tenant_scope import TenantScope


def test_actual_task_brief_preparation_is_atomic_and_idempotent():
    from aos_api.ecommerce_analysis_task_preparation import prepare_analysis_task
    _,case,run=fixture()
    scope=TenantScope('org-org','dev-project')
    with connect(scope) as conn:
        def prepare():return prepare_analysis_task(HostTransaction(conn),scope=scope,actor='fixture-analysis',
            case=case,run=run,domain_profile=INITIAL_STORE_PROFILE)
        before=conn.execute('SELECT count(*) AS n FROM aip_task WHERE org_id=%s AND project_id=%s',scope.key).fetchone()['n']
        first=prepare();second=prepare()
        assert first==second
        assert first['taskBriefRef']['revision']==2
        assert first['task']['goal']==first['taskBriefSpec']
        assert first['taskBriefSpec']['domainProfileRef']['resourceId']==INITIAL_STORE_PROFILE.profile_id
        assert conn.execute('SELECT count(*) AS n FROM aip_task_brief_revision WHERE org_id=%s AND project_id=%s AND brief_id=%s',(*scope.key,first['taskBriefRef']['resourceId'])).fetchone()['n']==2
        assert conn.execute("SELECT count(*) AS n FROM aip_production_contract_receipt WHERE org_id=%s AND project_id=%s AND result_ref->>'resourceId'=%s",(*scope.key,first['taskBriefRef']['resourceId'])).fetchone()['n']==2
        conn.rollback()
        assert conn.execute('SELECT count(*) AS n FROM aip_task WHERE org_id=%s AND project_id=%s',scope.key).fetchone()['n']==before


@pytest.mark.parametrize('fault',['tenant','case','run'])
def test_task_preparation_rejects_invalid_lineage_before_storage(fault):
    from aos_api.ecommerce_analysis_task_preparation import prepare_analysis_task
    _,case,run=fixture();scope=TenantScope('org-org','dev-project')
    if fault=='tenant':scope=TenantScope('dev-org','dev-project')
    elif fault=='case':case.content_hash='sha256:'+'f'*64
    else:run.authority.content_hash='sha256:'+'f'*64
    with pytest.raises(ValueError):prepare_analysis_task(HostTransaction(object()),scope=scope,actor='fixture',
        case=case,run=run,domain_profile=INITIAL_STORE_PROFILE)
