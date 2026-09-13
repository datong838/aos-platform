from copy import deepcopy
import pytest
from test_ecommerce_analysis_start_operation import _package
from aos_api.ecommerce_analysis_compilation_roles import AnalysisCompilationRoleReader
from aos_api.ecommerce_business_investigation_profile_catalog import INITIAL_STORE_PROFILE
from aos_api.tenant_scope import TenantScope
from aos_api.db import connect


@pytest.fixture
def preparation(monkeypatch):
    from aos_api.ecommerce_analysis_template_preparation import AnalysisTemplatePreparation
    roles=object.__new__(AnalysisCompilationRoleReader)
    monkeypatch.setattr(AnalysisCompilationRoleReader,'run_current',lambda self,conn,**kw:kw['execute']({}))
    blueprint=_package().handle('ecommerce_growth_analysis_advance',dict(kind='build_analysis_compilation_blueprint',
        profileRef=INITIAL_STORE_PROFILE.exact_ref.model_dump(mode='json',by_alias=True,exclude_none=True)),object())
    return AnalysisTemplatePreparation(roles),blueprint


def test_template_prepare_actual_revisions_receipts_and_rollback(preparation):
    service,blueprint=preparation
    scope=TenantScope('org-org','dev-project')
    with connect(scope) as conn:
        before=conn.execute('SELECT count(*) AS n FROM aip_stage_template_revision WHERE org_id=%s AND project_id=%s',scope.key).fetchone()['n']
        def run():return service.run_current(conn,scope=scope,selection_ref={},actor='fixture-preparation',
            domain_profile=INITIAL_STORE_PROFILE,blueprint=deepcopy(blueprint),execute=lambda result:result)
        receipts_before=conn.execute('SELECT count(*) AS n FROM aip_production_contract_receipt WHERE org_id=%s AND project_id=%s',scope.key).fetchone()['n']
        first=run();second=run()
        assert first==second
        assert first['stageTemplateRef']['revision']==2
        count=conn.execute('SELECT count(*) AS n FROM aip_stage_template_revision WHERE org_id=%s AND project_id=%s',scope.key).fetchone()['n']
        assert count==before+2
        assert conn.execute('SELECT count(*) AS n FROM aip_production_contract_receipt WHERE org_id=%s AND project_id=%s',scope.key).fetchone()['n']==receipts_before+2
        conn.rollback()
        assert conn.execute('SELECT count(*) AS n FROM aip_stage_template_revision WHERE org_id=%s AND project_id=%s',scope.key).fetchone()['n']==before

        def fail(result):raise RuntimeError('downstream failed')
        with pytest.raises(RuntimeError),conn.transaction():
            service.run_current(conn,scope=scope,selection_ref={},actor='fixture-preparation',
                domain_profile=INITIAL_STORE_PROFILE,blueprint=blueprint,execute=fail)
        assert conn.execute('SELECT count(*) AS n FROM aip_stage_template_revision WHERE org_id=%s AND project_id=%s',scope.key).fetchone()['n']==before
        assert conn.execute('SELECT count(*) AS n FROM aip_production_contract_receipt WHERE org_id=%s AND project_id=%s',scope.key).fetchone()['n']==receipts_before
        committed=run();conn.commit()
        assert run()==committed
        assert conn.execute('SELECT count(*) AS n FROM aip_production_contract_receipt WHERE org_id=%s AND project_id=%s',scope.key).fetchone()['n']==receipts_before+2
