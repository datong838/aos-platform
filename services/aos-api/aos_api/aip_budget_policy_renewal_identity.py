"""Private renewal identity boundary, not a reusable execution permit.

Only the future protected gateway constructs CheckerBinding from the original
validated management configuration. Public commands never accept this binding.
The gateway and its private database credentials remain trusted components.
"""
from dataclasses import dataclass
import os
import re

import psycopg
from psycopg.rows import dict_row
from pydantic import SecretStr

from aos_api.auth import Principal, resolve_principal


class RenewalIdentityBlocked(ValueError):
    pass


_SCOPE = ('org-org', 'dev-project')
_HUMAN = '6f31cfdc-a26c-4f1f-ad6b-95a8559cc657'
_ISSUER = 'http://127.0.0.1:18448/realms/qyh-local'
_ROLES = {'maker': 'aos_budget_renewal_maker_call', 'issuer': 'aos_budget_renewal_issuer_call',
          'consumer': 'aos_budget_renewal_consumer_call'}


@dataclass(frozen=True)
class MachineMakerIdentity:
    subject: str
    session_user: str
    org_id: str = _SCOPE[0]
    project_id: str = _SCOPE[1]
    activation_eligible: bool = False


@dataclass(frozen=True)
class CheckerBinding:
    subject: str
    identity_config_sha256: str
    validated_oidc_environment: tuple[tuple[str, str], ...]

    def __post_init__(self):
        if (self.subject != _HUMAN or type(self.identity_config_sha256) is not str
                or re.fullmatch('[0-9a-f]{64}', self.identity_config_sha256) is None
                or type(self.validated_oidc_environment) is not tuple
                or any(type(x) is not tuple or len(x) != 2
                       or any(type(v) is not str for v in x)
                       for x in self.validated_oidc_environment)):
            raise RenewalIdentityBlocked('RENEWAL_PROTECTED_CHECKER_BINDING_REQUIRED')
        expected = {
            'AOS_AUTH_ALLOW_DEV': '0', 'AOS_AUTH_EXTERNAL_ONLY': '1',
            'AOS_OIDC_ISSUER': _ISSUER, 'AOS_OIDC_AUDIENCE': 'aos-api',
            'AOS_OIDC_CLIENT_ID': 'aos-api',
            'AOS_OIDC_JWKS_URL': _ISSUER + '/protocol/openid-connect/certs',
            'AOS_OIDC_ISSUERS': '', 'AOS_OIDC_JWKS_URLS': '',
            'AOS_OIDC_TOKEN_URL': _ISSUER + '/protocol/openid-connect/token',
            'AOS_OIDC_TOKEN_ALG': 'RS256',
        }
        env = dict(self.validated_oidc_environment)
        if (len(env) != len(self.validated_oidc_environment)
                or set(env) != set(expected) | {'AOS_OIDC_LEEWAY_SECONDS'}
                or any(env[k] != v for k, v in expected.items())
                or env['AOS_OIDC_LEEWAY_SECONDS'] not in {'0', '1', '2', '3', '4', '5'}):
            raise RenewalIdentityBlocked('RENEWAL_PROTECTED_CHECKER_BINDING_REQUIRED')


def _database_identity(conn, purpose):
    if type(conn) is not psycopg.Connection or conn.closed:
        raise RenewalIdentityBlocked('RENEWAL_REAL_DATABASE_SESSION_REQUIRED')
    try:
        with conn.cursor(row_factory=dict_row) as cursor:
            row = cursor.execute("""SELECT session_user AS login,current_user AS role,
                current_setting('aos.org_id',true) AS org_id,
                current_setting('aos.project_id',true) AS project_id,
                current_schemas(true) AS schemas,
                r.rolcanlogin,r.rolsuper,r.rolbypassrls,r.rolinherit,
                r.rolcreatedb,r.rolcreaterole,r.rolreplication,
                EXISTS(SELECT 1 FROM pg_auth_members
                       WHERE roleid=r.oid OR member=r.oid) AS membership
                FROM pg_roles r WHERE r.rolname=session_user""").fetchone()
        if (not row or row['login'] != _ROLES[purpose] or row['role'] != row['login']
                or (row['org_id'], row['project_id']) != _SCOPE
                or row['rolcanlogin'] is not True
                or any(row[k] is not False for k in (
                    'rolsuper', 'rolbypassrls', 'rolinherit', 'rolcreatedb',
                    'rolcreaterole', 'rolreplication', 'membership'))
                or not row['schemas']
                or not set(row['schemas']) <= {'pg_catalog', 'public'}):
            raise RenewalIdentityBlocked('RENEWAL_DATABASE_IDENTITY_PROFILE_REQUIRED')
        return row['login']
    except RenewalIdentityBlocked:
        raise
    except Exception:
        raise RenewalIdentityBlocked('RENEWAL_DATABASE_IDENTITY_UNAVAILABLE') from None


def authenticate_machine_maker(conn):
    login = _database_identity(conn, 'maker')
    return MachineMakerIdentity(subject='postgres-service:' + login, session_user=login)


def authenticate_checker(token, *, binding, conn):
    if type(token) is not SecretStr or type(binding) is not CheckerBinding:
        raise RenewalIdentityBlocked('RENEWAL_SECRET_JWT_AND_BINDING_REQUIRED')
    # Reparse even internally constructed/copy-mutated binding metadata.
    CheckerBinding(binding.subject, binding.identity_config_sha256, binding.validated_oidc_environment)
    if any(os.environ.get(k) != v for k, v in binding.validated_oidc_environment):
        raise RenewalIdentityBlocked('RENEWAL_APPROVED_IDENTITY_CONFIGURATION_DRIFT')
    _database_identity(conn, 'issuer')
    try:
        principal = resolve_principal(token=token.get_secret_value(),
                                      header_org=_SCOPE[0], header_project=_SCOPE[1])
        if (type(principal) is not Principal or principal.token_kind != 'oidc'
                or principal.subject != binding.subject
                or (principal.org_id, principal.project_id) != _SCOPE):
            raise ValueError('identity differs')
        with conn.cursor(row_factory=dict_row) as cursor:
            row = cursor.execute(
                'SELECT public.aip_renewal_checker_member_a0v_162() AS allowed').fetchone()
        if not row or row['allowed'] is not True:
            raise ValueError('current membership differs')
        return principal
    except Exception:
        raise RenewalIdentityBlocked('RENEWAL_ORIGINAL_HUMAN_IDENTITY_REQUIRED') from None
