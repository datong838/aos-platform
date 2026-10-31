"""Runtime configuration/connection negatives; no mock may grant admission."""
import hashlib
import json
import os

import pytest


@pytest.fixture
def runtime_config(tmp_path):
    tmp_path.chmod(0o700)
    path = tmp_path / 'runtime.json'
    body = dict(schemaVersion='aos.policy-window.runtime-private/v1', enabled=True,
        expectedDatabase='isolated_candidate', runtimeLogin='aos_a0v_runtime_20260912',
        runtimeRole='aos_runtime', evaluatorLogin='aos_aip_binding_evaluator',
        nativeManifestSha256='a'*64, legacyManifestSha256='b'*64, runtimeManifestSha256='c'*64)
    path.touch(mode=0o600)
    path.write_text(json.dumps(body))
    return path, body


def test_private_runtime_config_preserves_independent_pins(runtime_config):
    from aos_api.aip_budget_policy_window_risk_authority import load_runtime_config
    path, body = runtime_config
    result = load_runtime_config(path)
    assert result.expected_database == body['expectedDatabase']
    assert result.native_manifest_sha256 == 'a'*64
    assert result.legacy_manifest_sha256 == 'b'*64
    assert result.runtime_manifest_sha256 == 'c'*64
    assert result.fingerprint == hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize('field,value', [
    ('enabled', False), ('enabled', 1), ('expectedDatabase', True),
    ('runtimeLogin', 'qyh_restored_api_login'), ('runtimeRole', 'public'),
    ('evaluatorLogin', 'aos_runtime'), ('nativeManifestSha256', 'bad'),
    ('runtimeManifestSha256', None), ('approved', True), ('dsn', 'forbidden'),
])
def test_runtime_config_rejects_disabled_drift_and_request_fields(runtime_config, field, value):
    from aos_api.aip_budget_policy_window_risk_authority import load_runtime_config, WindowRiskBlocked
    path, body = runtime_config
    body[field] = value
    path.write_text(json.dumps(body))
    with pytest.raises(WindowRiskBlocked, match='PRIVATE_CONFIG_REQUIRED'):
        load_runtime_config(path)


def test_runtime_config_rejects_duplicate_keys(runtime_config):
    from aos_api.aip_budget_policy_window_risk_authority import load_runtime_config, WindowRiskBlocked
    path, _ = runtime_config
    path.write_text(path.read_text()[:-1] + ',"enabled":true}')
    with pytest.raises(WindowRiskBlocked, match='PRIVATE_CONFIG_REQUIRED'):
        load_runtime_config(path)


@pytest.mark.parametrize('kind', ['symlink', 'hardlink', 'public_file', 'public_directory'])
def test_runtime_config_requires_one_private_unlinked_file(runtime_config, kind):
    from aos_api.aip_budget_policy_window_risk_authority import load_runtime_config, WindowRiskBlocked
    path, _ = runtime_config
    if kind == 'symlink':
        target = path.with_name('link.json')
        target.symlink_to(path)
    elif kind == 'hardlink':
        target = path.with_name('link.json')
        os.link(path, target)
    else:
        target = path
        if kind == 'public_file': path.chmod(0o644)
        else: path.parent.chmod(0o755)
    with pytest.raises(WindowRiskBlocked, match='PRIVATE_CONFIG_REQUIRED'):
        load_runtime_config(target)


@pytest.mark.parametrize('fake', [None, {}, object()])
def test_constructed_objects_cannot_become_native_risk_authority(fake, monkeypatch):
    from aos_api.aip_budget_policy_window_risk_authority import read_window_risk_fact, WindowRiskBlocked
    from aos_api.tenant_scope import TenantScope
    monkeypatch.delenv('AOS_POLICY_WINDOW_RUNTIME_CONFIG', raising=False)
    with pytest.raises(WindowRiskBlocked, match='NATIVE_DATABASE_CONNECTION_REQUIRED'):
        read_window_risk_fact(fake, scope=TenantScope('org-org', 'dev-project'),
                             budget_ref=None, price_ref=None)


def test_host_wrapper_cannot_turn_a_fake_connection_into_authority(monkeypatch):
    from aos_api.aip_budget_policy_window_risk_authority import read_window_risk_fact, WindowRiskBlocked
    from aos_api.ecommerce_growth_host_ports import HostTransaction
    from aos_api.tenant_scope import TenantScope
    monkeypatch.delenv('AOS_POLICY_WINDOW_RUNTIME_CONFIG', raising=False)
    with pytest.raises(WindowRiskBlocked, match='NATIVE_DATABASE_CONNECTION_REQUIRED'):
        read_window_risk_fact(HostTransaction(object()), scope=TenantScope('org-org', 'dev-project'),
                             budget_ref=None, price_ref=None)


def test_child_price_cannot_fall_back_through_a_non_cost_budget():
    from aos_api.aip_budget_cost_runtime import require_cost_risk, BudgetCostRuntimeBlocked
    from aos_api.aip_budget_reservation_contracts import BudgetExactRef
    from aos_api.tenant_scope import TenantScope

    class NoActivation:
        def execute(self, query, parameters):
            assert 'aip_budget_receipt' in query
            return self

        def fetchall(self):
            return []

    def ref(kind, identity):
        return BudgetExactRef(resourceType=kind, resourceId=identity, revision=1, contentHash='sha256:' + 'a'*64)
    with pytest.raises(BudgetCostRuntimeBlocked):
        require_cost_risk(NoActivation(), TenantScope('org-org', 'dev-project'),
            ref('BudgetRevision', 'non-cost'), ref('ModelPriceSnapshotRevision', 'window-price-' + 'b'*64), 10)


@pytest.mark.parametrize('policy', [None, {}, 'invalid',
    dict(assetType='BudgetRevision', assetId='wrong-family', revision=1, contentHash='a'*64)])
def test_formal_child_policy_input_denial_precedes_database_queries(policy, monkeypatch):
    from aos_api import aip_binding_evaluator_connection as connection
    from aos_api.aip_budget_cost_runtime import read_formal_budget_fact, BudgetCostRuntimeBlocked
    from aos_api.tenant_scope import TenantScope

    # This bypass tests only input rejection; it cannot establish native authority.
    monkeypatch.setattr(connection, 'require_binding_evaluator_transaction', lambda *args: None)

    class NoQueries:
        def execute(self, *args, **kwargs):
            pytest.fail('invalid child policy must be rejected before reading authority')

    def ref(kind, identity):
        return dict(assetType=kind, assetId=identity, revision=1, contentHash='a'*64)

    with pytest.raises(BudgetCostRuntimeBlocked, match='FORMAL_BUDGET_CHILD_POLICY_BINDING_REQUIRED'):
        read_formal_budget_fact(conn=NoQueries(), scope=TenantScope('org-org', 'dev-project'),
            budget_ref=ref('BudgetRevision', 'parent'),
            price_ref=ref('ModelPriceSnapshotRevision', 'window-price-' + 'b'*64),
            provider_ref=ref('ProviderInstanceRevision', 'provider'), budget_policy_ref=policy)
