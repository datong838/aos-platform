from pathlib import Path
import pytest
from aos_api.asset_registry.installation_store import PostgresInstallationStore
from aos_api.asset_registry.release_policy import ReleasePolicy
from aos_api.pipeline_control_service import PipelineControlServiceFactory
from aos_api.pipeline_runtime_control_contracts import PipelineSourceSelectionDraft
from aos_api.tenant_scope import TenantScope
from tests.test_pipeline_runtime_control_contracts import payload


def factory(tmp_path):
    return PipelineControlServiceFactory(installation_store=PostgresInstallationStore(),
        policy=ReleasePolicy(trust_roots=None),allowlist_roots={'fixture':tmp_path})


def test_factory_composes_same_current_dependencies_without_connection(tmp_path,monkeypatch):
    import aos_api.pipeline_control_service as module
    monkeypatch.setattr(module,'runtime_worker_connection',lambda:pytest.fail('constructor connected'))
    f=factory(tmp_path);service=f.build(TenantScope('org-org','dev-project'))
    assert service.claims._controls is service.controls
    assert service.controls._selections is service.selections
    assert service.selections._store is f.installation_store
    assert service.selections._release_policy is f.policy
    assert service.selections._artifacts.loader.trust_roots is f.policy._trust_roots


def test_cross_tenant_request_is_rejected_before_connect(tmp_path,monkeypatch):
    import aos_api.pipeline_control_service as module
    service=factory(tmp_path).build(TenantScope('org-org','dev-project'))
    monkeypatch.setattr(module,'runtime_worker_connection',lambda:pytest.fail('cross scope connected'))
    body=payload();body.pop('sourceSelectionRef')
    with pytest.raises(PermissionError):service.approve_selection(draft=PipelineSourceSelectionDraft.model_validate(body),actor='actor',idempotency_key='first')


def test_bad_asset_root_is_lazy_and_does_not_construct_service(tmp_path):
    f=PipelineControlServiceFactory(installation_store=PostgresInstallationStore(),policy=ReleasePolicy(trust_roots=None),
        allowlist_roots={'missing':tmp_path/'missing'})
    with pytest.raises(ValueError):f.build(TenantScope('org-org','dev-project'))


def test_factory_rejects_arbitrary_authority_dependencies(tmp_path):
    with pytest.raises(TypeError):PipelineControlServiceFactory(installation_store=object(),policy=ReleasePolicy(trust_roots=None),allowlist_roots={})


def test_snapshot_stop_mode_does_not_require_available_asset_directory(tmp_path):
    f=PipelineControlServiceFactory(installation_store=PostgresInstallationStore(),policy=ReleasePolicy(trust_roots=None),
        allowlist_roots={'missing':tmp_path/'unavailable'})
    scope=TenantScope('org-org','dev-project')
    stopped=f.build_snapshot_schedule(scope,source_controls=False)
    assert stopped._owner._groups is None
    with pytest.raises(ValueError):f.build_snapshot_schedule(scope,source_controls=True)
    with pytest.raises(PermissionError,match='stop-only'):
        stopped._owner.transition(None,scope=scope,definition_id='unused',actor='actor',intent='enable',
            expected_ref=None,idempotency_key='denied')


def test_snapshot_worker_factory_shares_original_authority_without_connecting(tmp_path,monkeypatch):
    from sqlalchemy import create_engine
    from aos_api.ecom_consistency_store import EcomConsistencyStore
    import aos_api.pipeline_control_service as module
    import aos_api.phase5_pipeline_engine as pipeline
    monkeypatch.setattr(module,'runtime_worker_connection',lambda:pytest.fail('constructor connected'))
    named_engine=object()
    monkeypatch.setattr(pipeline,'get_engine',lambda:named_engine)
    engine=create_engine('postgresql+psycopg://unused@127.0.0.1:1/unused')
    try:
        store=EcomConsistencyStore(engine)
        worker=factory(tmp_path).build_snapshot_worker(TenantScope('org-org','dev-project'),store=store)
        assert worker._runtime._claims._groups._controls is worker._recovery._controls
        assert worker._runtime._completion._store is worker._recovery._store is store
        assert worker._runtime._connect is worker._recovery._connect is module.runtime_worker_connection
        assert worker._recovery._eng is named_engine
        assert worker._runtime._host_lease is worker._recovery._host_lease is None
        with pytest.raises(TypeError):factory(tmp_path).build_snapshot_worker(worker.scope,store=object())
    finally:engine.dispose()


def test_snapshot_worker_factory_only_passes_exact_same_scope_opt_in_lease(tmp_path,monkeypatch):
    from sqlalchemy import create_engine
    from aos_api.ecom_consistency_store import EcomConsistencyStore
    from aos_api.extension_runtime.host_lease import OptInHostLease
    import aos_api.pipeline_control_service as module

    monkeypatch.setattr(module,'runtime_worker_connection',lambda:pytest.fail('constructor connected'))
    scope=TenantScope('org-org','dev-project')
    lease=OptInHostLease(connect=lambda:pytest.fail('lease acquired'),scope=scope)
    wrong=OptInHostLease(connect=lambda:pytest.fail('lease acquired'),
                         scope=TenantScope('dev-org','dev-project'))
    engine=create_engine('postgresql+psycopg://unused@127.0.0.1:1/unused')
    try:
        store=EcomConsistencyStore(engine)
        worker=factory(tmp_path).build_snapshot_worker(scope,store=store,host_lease=lease)
        assert worker._runtime._host_lease is worker._recovery._host_lease is lease
        with pytest.raises(TypeError,match='Host lease'):
            factory(tmp_path).build_snapshot_worker(scope,store=store,host_lease=object())
        with pytest.raises(PermissionError,match='tenant'):
            factory(tmp_path).build_snapshot_worker(scope,store=store,host_lease=wrong)
    finally:engine.dispose()
