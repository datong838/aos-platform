"""Identity checks never accept a constructed Principal as a service session."""
import pytest
from pydantic import SecretStr

from aos_api.auth import Principal


@pytest.mark.parametrize('fake', [None, {}, object(), Principal(
    subject='pretend-maker', org_id='org-org', project_id='dev-project', token_kind='oidc')])
def test_machine_requires_real_database_connection(fake):
    from aos_api.aip_budget_policy_renewal_identity import authenticate_machine_maker, RenewalIdentityBlocked
    with pytest.raises(RenewalIdentityBlocked):
        authenticate_machine_maker(fake)


def test_checker_never_accepts_a_principal_instead_of_secret_jwt():
    from aos_api.aip_budget_policy_renewal_identity import authenticate_checker, RenewalIdentityBlocked
    p = Principal(subject='pretend-checker', org_id='org-org', project_id='dev-project', token_kind='oidc')
    with pytest.raises(RenewalIdentityBlocked):
        authenticate_checker(p, binding=None, conn=None)


def test_checker_missing_protected_binding_stops_before_jwt_or_database():
    from aos_api.aip_budget_policy_renewal_identity import authenticate_checker, RenewalIdentityBlocked
    with pytest.raises(RenewalIdentityBlocked):
        authenticate_checker(SecretStr('not-a-jwt'), binding=None, conn=None)


def protected_environment():
    issuer = 'http://127.0.0.1:18448/realms/qyh-local'
    return dict(AOS_AUTH_ALLOW_DEV='0', AOS_AUTH_EXTERNAL_ONLY='1',
                AOS_OIDC_ISSUER=issuer, AOS_OIDC_AUDIENCE='aos-api', AOS_OIDC_CLIENT_ID='aos-api',
                AOS_OIDC_JWKS_URL=issuer + '/protocol/openid-connect/certs',
                AOS_OIDC_ISSUERS='', AOS_OIDC_JWKS_URLS='',
                AOS_OIDC_TOKEN_URL=issuer + '/protocol/openid-connect/token',
                AOS_OIDC_TOKEN_ALG='RS256', AOS_OIDC_LEEWAY_SECONDS='0')


@pytest.mark.parametrize('kind', ['subject', 'hash', 'audience', 'duplicate', 'skew'])
def test_protected_binding_rejects_substitution_or_ambiguous_configuration(kind):
    from aos_api.aip_budget_policy_renewal_identity import CheckerBinding, RenewalIdentityBlocked
    subject, digest = '6f31cfdc-a26c-4f1f-ad6b-95a8559cc657', 'a' * 64
    env = protected_environment()
    if kind == 'subject':
        subject = 'another-member'
    elif kind == 'hash':
        digest = 'not-exact'
    elif kind == 'audience':
        env['AOS_OIDC_AUDIENCE'] = 'other-app'
    elif kind == 'skew':
        env['AOS_OIDC_LEEWAY_SECONDS'] = '60'
    pairs = tuple(env.items())
    if kind == 'duplicate':
        pairs += (pairs[0],)
    with pytest.raises(RenewalIdentityBlocked):
        CheckerBinding(subject, digest, pairs)


def test_environment_drift_denied_before_token_or_database(monkeypatch):
    from aos_api.aip_budget_policy_renewal_identity import authenticate_checker, CheckerBinding, RenewalIdentityBlocked
    env = protected_environment()
    binding = CheckerBinding('6f31cfdc-a26c-4f1f-ad6b-95a8559cc657', 'a' * 64, tuple(env.items()))
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv('AOS_AUTH_ALLOW_DEV', '1')
    with pytest.raises(RenewalIdentityBlocked, match='CONFIGURATION_DRIFT'):
        authenticate_checker(SecretStr('not-a-jwt'), binding=binding, conn=None)


@pytest.mark.parametrize('fake', [None, {}, object(), Principal(
    subject='pretend-caller', org_id='org-org', project_id='dev-project', token_kind='oidc')])
def test_store_has_no_shared_connection_or_constructed_identity_fallback(fake):
    from aos_api.aip_budget_policy_renewal_store import RenewalAuthorityStore, RenewalStoreBlocked
    with pytest.raises(RenewalStoreBlocked, match='REAL_IDLE_DATABASE_CONNECTION'):
        RenewalAuthorityStore(fake)
