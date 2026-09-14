"""Real Eval/publication/contract PG; current selection and route/Logic are named doubles."""
import pytest
from tests.aip.test_aip_skill_publication_service import published_skill_runtime
from aos_api.db import connect
from aos_api.ecommerce_analysis_compilation_selection import AnalysisCompilationSelectionReader
from aos_api.ecommerce_business_investigation_profile_catalog import INITIAL_STORE_PROFILE
from test_ecommerce_analysis_start_operation import _package
from test_ecommerce_analysis_compilation_blueprint import request


@pytest.fixture(scope='module')
def published():
    runtime=published_skill_runtime(skill_id='ecommerce.skill.D01',canonical_logic_id='ecommerce.logic.D01')
    # Publication uses the host clock; allow the known VM clock skew to elapse
    # before evaluating a just-created fixture against the database clock.
    with connect(runtime.scope) as conn:
        wait=conn.execute('''SELECT EXTRACT(EPOCH FROM (occurred_at-clock_timestamp())) AS seconds
            FROM aip_publication_event WHERE org_id=%s AND project_id=%s AND event_id=%s''',
            (*runtime.scope.key,runtime.published.publication_ref.resource_id)).fetchone()['seconds']
        assert wait < 1, 'fixture host/database clock skew exceeds one second'
        if wait>0:conn.execute('SELECT pg_sleep(%s)',(float(wait)+0.02,))
    return runtime


def prepare(conn,published,monkeypatch,execute=lambda value:value):
    from aos_api.ecommerce_analysis_startup_eval import AnalysisStartupEvalPreparation
    selection=object.__new__(AnalysisCompilationSelectionReader)
    def current(self,connection,**kw):
        return kw['execute'](dict(skills=[published.published.model_dump(mode='json',by_alias=True)]))
    monkeypatch.setattr(AnalysisCompilationSelectionReader,'run_current',current)
    return AnalysisStartupEvalPreparation(selection).run_current(conn,scope=published.scope,selection_ref={},
        actor='fixture-startup-eval',domain_profile=INITIAL_STORE_PROFILE,
        blueprint=_package().handle('ecommerce_growth_analysis_advance',request(),object()),execute=execute)


def test_actual_startup_eval_freeze_replay_and_outer_rollback(published,monkeypatch):
    with connect(published.scope) as conn:
        first=prepare(conn,published,monkeypatch)
        assert prepare(conn,published,monkeypatch)==first
        assert first['startupEval']['lifecycle']=='frozen'
        assert first['startupEval']['readiness']=='ready'
        assert first['startupEval']['gatePolicy']['evidenceKind']=='isolated_skill_contract'
        identity=first['startupEvalRef']['resourceId']
        assert conn.execute('SELECT count(*) AS n FROM aip_eval_contract_revision WHERE org_id=%s AND project_id=%s AND contract_id=%s',
            (*published.scope.key,identity)).fetchone()['n']==2
        conn.rollback()
        assert conn.execute('SELECT count(*) AS n FROM aip_eval_contract_head WHERE org_id=%s AND project_id=%s AND contract_id=%s',
            (*published.scope.key,identity)).fetchone()['n']==0


@pytest.mark.parametrize('fault',['expired','publication','callback','duplicate'])
def test_current_eval_dependency_failure_leaves_no_contract(published,monkeypatch,fault):
    from datetime import timedelta
    from aos_api.aip_release_publication_models import RevokePublicationRequest
    from aos_api.aip_release_publication_service import AipReleasePublicationService
    from aos_api.ecommerce_growth_host_ports import HostTransaction
    from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
    with connect(published.scope) as conn:
        before=conn.execute('SELECT count(*) AS n FROM aip_eval_contract_head WHERE org_id=%s AND project_id=%s',published.scope.key).fetchone()['n']
        if fault=='expired':
            # Read wrapper reports expiry; no immutable gate row is rewritten.
            original=AipReleasePublicationService._gate_from_row
            def expired(scope,row):
                gate=original(scope,row)
                return gate.model_copy(update={'expires_at':gate.decided_at-timedelta(seconds=1)})
            monkeypatch.setattr(AipReleasePublicationService,'_gate_from_row',staticmethod(expired))
        def consume(value):
            if fault=='callback':raise RuntimeError('downstream failure')
            if fault=='duplicate':
                from aos_api.aip_production_contracts import CreateEvalContractRequest,EvalContractRevision
                from aos_api.aip_production_contract_store import AipProductionContractStore
                contract=EvalContractRevision.model_validate(value['startupEval'])
                body=CreateEvalContractRequest(**{k:getattr(contract,k) for k in CreateEvalContractRequest.model_fields})
                store=AipProductionContractStore(TransactionBoundConnectFactory(HostTransaction(conn),published.scope))
                duplicate=store.create_eval_contract(published.scope,'fixture','duplicate-create',body)
                store.freeze_eval_contract(published.scope,'fixture',duplicate.contract_id,duplicate.version,'duplicate-freeze')
            if fault=='publication':
                AipReleasePublicationService(TransactionBoundConnectFactory(HostTransaction(conn),published.scope)).revoke(
                    published.scope,actor='fixture-startup-eval',publication_id=published.published.publication_ref.revision,
                    request=RevokePublicationRequest(
                        reason_hash='a'*64,idempotency_key='startup-revoke'))
            return value
        message={'callback':'downstream failure','duplicate':'dependencies changed'}.get(fault,'lineage invalid or expired')
        with pytest.raises((ValueError,RuntimeError),match=message),conn.transaction():
            prepare(conn,published,monkeypatch,execute=consume)
        assert conn.execute('SELECT count(*) AS n FROM aip_eval_contract_head WHERE org_id=%s AND project_id=%s',published.scope.key).fetchone()['n']==before
