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
