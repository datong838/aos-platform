"""Adapter boundary tests; native acceptance is in the dedicated PG module."""
import pytest
from aos_api.auth import Principal


@pytest.mark.parametrize('fake', [None, {}, object(), Principal(
    subject='constructed', org_id='org-org', project_id='dev-project', token_kind='oidc')])
def test_store_requires_real_idle_owned_connection(fake):
    from aos_api.aip_budget_policy_window_store import WindowAuthorityStore, WindowStoreBlocked
    with pytest.raises(WindowStoreBlocked, match='REAL_IDLE_DATABASE_CONNECTION_REQUIRED'):
        WindowAuthorityStore(fake, manifest_sha256='a'*64, legacy_manifest_sha256='b'*64)


@pytest.mark.parametrize('result', [None, {}, {'status': 'observed', 'activationEligible': True}])
def test_reconcile_result_cannot_grant_activation(result):
    from aos_api.aip_budget_policy_window_store import WindowAuthorityStore, WindowStoreBlocked
    from aos_api.aip_budget_policy_window_commands import WindowConsumeCommand
    command = WindowConsumeCommand(schemaVersion=1, orgId='org-org', projectId='dev-project',
        idempotencyKey='proof', proposalId='p', proposalHash='a'*64, targetPairHash='b'*64,
        decisionId='d', decisionHash='c'*64)
    with pytest.raises(WindowStoreBlocked, match='NATIVE_RESULT_CONTRACT_REQUIRED'):
        WindowAuthorityStore.validate_result(result, command, reconcile=True)


@pytest.mark.parametrize('raw', [None, '{}', '{"schema":1,"schema":2}', '[]'])
def test_catalog_observation_rejects_unpinned_or_incomplete_seal(raw):
    from aos_api.aip_budget_policy_window_catalog import verify_window_catalog, WindowCatalogBlocked

    class Cursor:
        def execute(self, query, parameters=None):
            assert 'obj_description' in query
            return self

        def fetchone(self):
            return {'seal': raw}

    import hashlib
    pin = hashlib.sha256(raw.encode()).hexdigest() if isinstance(raw, str) else 'a'*64
    with pytest.raises(WindowCatalogBlocked, match='PINNED_MANIFEST_REQUIRED'):
        verify_window_catalog(Cursor(), manifest_sha256=pin, legacy_manifest_sha256='b'*64)


def test_store_preserves_catalog_rejection_as_original_public_error(monkeypatch):
    from aos_api.aip_budget_policy_window_catalog import WindowCatalogBlocked
    import aos_api.aip_budget_policy_window_store as module

    def reject(*args, **kwargs):
        raise WindowCatalogBlocked('POLICY_WINDOW_FUNCTION_SEAL_DRIFT')

    monkeypatch.setattr(module, 'verify_window_catalog', reject)
    # Exercise error translation only, not connection/identity admission.
    store = object.__new__(module.WindowAuthorityStore)
    store._manifest_sha256, store._legacy_manifest_sha256 = 'a'*64, 'b'*64
    with pytest.raises(module.WindowStoreBlocked, match='FUNCTION_SEAL_DRIFT'):
        store.verify_native_manifest(object())


def test_protected_package_pins_shared_catalog_source():
    from aos_api.aip_budget_policy_window_service import PACKAGE_FILES
    assert 'services/aos-api/aos_api/aip_budget_policy_window_catalog.py' in PACKAGE_FILES
