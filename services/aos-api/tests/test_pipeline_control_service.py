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
