"""Window identity denies constructed identities and ambiguous purposes."""
import pytest
from pydantic import SecretStr

from aos_api.auth import Principal


@pytest.mark.parametrize('purpose', ['maker', 'issuer', 'consumer'])
@pytest.mark.parametrize('fake', [None, {}, object(), Principal(
    subject='constructed', org_id='org-org', project_id='dev-project', token_kind='oidc')])
def test_database_identity_requires_real_connection(purpose, fake):
    from aos_api.aip_budget_policy_window_identity import database_identity, WindowIdentityBlocked
    with pytest.raises(WindowIdentityBlocked, match='REAL_DATABASE_SESSION_REQUIRED'):
        database_identity(fake, purpose, read_only=False)


@pytest.mark.parametrize('purpose', [None, 'runtime', 'Consumer', True, []])
def test_unknown_purpose_is_rejected_before_database(purpose):
    from aos_api.aip_budget_policy_window_identity import database_identity, WindowIdentityBlocked
    with pytest.raises(WindowIdentityBlocked, match='EXACT_PURPOSE_REQUIRED'):
        database_identity(None, purpose, read_only=False)


@pytest.mark.parametrize('read_only', [None, 0, 1, 'off', {}])
def test_transaction_mode_cannot_be_coerced(read_only):
    from aos_api.aip_budget_policy_window_identity import database_identity, WindowIdentityBlocked
    with pytest.raises(WindowIdentityBlocked, match='EXACT_PURPOSE_REQUIRED'):
        database_identity(None, 'consumer', read_only=read_only)


def test_checker_does_not_accept_public_subject_or_principal():
    from aos_api.aip_budget_policy_window_identity import authenticate_checker, WindowIdentityBlocked
    principal = Principal(subject='constructed', org_id='org-org', project_id='dev-project', token_kind='oidc')
    with pytest.raises(WindowIdentityBlocked):
        authenticate_checker(principal, binding=None, conn=None, read_only=False)
    with pytest.raises(WindowIdentityBlocked):
        authenticate_checker(SecretStr('synthetic-not-a-jwt'), binding=None, conn=None, read_only=False)
