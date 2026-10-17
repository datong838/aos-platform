"""Private serial window service: pinned provenance, SCRAM, durable no-resend.

No routes, shared DSN, provisioning, or runtime activation. OIDC environment is
scoped to this serial private executor; embedding in a concurrent API requires a
separate process boundary. Human tokens never enter files, hashes, or results.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
from threading import RLock
from typing import Literal

import psycopg
from psycopg.rows import dict_row
from pydantic import ConfigDict, SecretStr, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel
from aos_api.aip_budget_policy_renewal_connection import (
    ROOT, PACKAGE_FILES as LEGACY_PACKAGE_FILES, _private_bytes, _unique,
    _original_oidc_loader, _FORBIDDEN_ENV,
)
from aos_api.aip_budget_policy_window_commands import (
    WindowProposeCommand, WindowDecisionCommand, WindowRevocationCommand, WindowConsumeCommand,
)
from aos_api.aip_budget_policy_window_identity import CALLERS, CheckerBinding, database_identity, authenticate_checker
from aos_api.aip_budget_policy_window_store import WindowAuthorityStore, WindowStoreBlocked
from aos_api.aip_network_issuer_attempt import (
    AttemptReceipt, AttemptAlreadyRecorded, AttemptConflict, AttemptUnknown, AttemptBlocked, _reserve_attempt_receipt,
)

PACKAGE_FILES = tuple(sorted(set(LEGACY_PACKAGE_FILES) | {
    'services/aos-api/aos_api/aip_budget_policy_window_'+name for name in
    ('commands.py', 'identity.py', 'store.py', 'catalog.py', 'service.py', 'authority.sql')
} | {'services/aos-api/alembic/versions/a0v_163_budget_policy_window.py'} | {
    'services/aos-api/aos_api/'+name for name in (
        'auth.py', 'oidc.py', 'tenant_scope.py', 'env_load.py', 'aip_network_issuer_attempt.py',
        'aip_contracts.py', 'aip_budget_store.py', 'aip_agent_registry_contracts.py')
}))
_HASH = re.compile('[0-9a-f]{64}')
COMMANDS = {'propose': WindowProposeCommand, 'decide': WindowDecisionCommand,
            'revoke': WindowRevocationCommand, 'consume': WindowConsumeCommand}
PURPOSES = {'propose': 'maker', 'decide': 'issuer', 'revoke': 'issuer', 'consume': 'consumer'}
_SERIAL = RLock()


class WindowServiceBlocked(ValueError):
    pass


@dataclass(frozen=True)
class WindowProfile:
    purpose: str
    host: str
    port: int
    database: str
    user: str
    passfile: Path
    passfile_sha256: str


@dataclass(frozen=True)
class ProtectedWindowConfig:
    path: Path
    content_sha256: str
    enabled: bool
    binding: CheckerBinding
    profiles: tuple[WindowProfile, ...]
    native_manifest_sha256: str
    legacy_manifest_sha256: str
    package_sources: tuple[tuple[str, str], ...]

    def profile(self, purpose):
        matches = [p for p in self.profiles if p.purpose == purpose]
        if len(matches) != 1:
            raise WindowServiceBlocked('POLICY_WINDOW_EXACT_PURPOSE_REQUIRED')
        return matches[0]


def load_protected_config(path):
    try:
        raw = _private_bytes(path)
        value = json.loads(raw, object_pairs_hook=_unique,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        fields = {'schemaVersion', 'orgId', 'projectId', 'enabled', 'identityConfigPath',
                  'identityConfigSha256', 'profiles', 'packageSources', 'nativeManifestSha256', 'legacyManifestSha256'}
        if (type(value) is not dict or set(value) != fields
                or value['schemaVersion'] != 'aos.budget-policy-window.private/v1'
                or value['orgId'] != 'org-org' or value['projectId'] != 'dev-project'
                or type(value['enabled']) is not bool
                or any(type(value[k]) is not str or not _HASH.fullmatch(value[k])
                       for k in ('nativeManifestSha256', 'legacyManifestSha256', 'identityConfigSha256'))
                or type(value['packageSources']) is not dict
                or set(value['packageSources']) != set(PACKAGE_FILES)):
            raise ValueError()
        for relative, digest in value['packageSources'].items():
            source = ROOT/relative
            if (type(digest) is not str or not _HASH.fullmatch(digest) or source.is_symlink()
                    or not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != digest):
                raise ValueError()
        identity_path = Path(value['identityConfigPath'])
        identity_raw = _private_bytes(identity_path, maximum=16384)
        digest = hashlib.sha256(identity_raw).hexdigest()
        if digest != value['identityConfigSha256']: raise ValueError()
        environment = _original_oidc_loader()(identity_path)
        if hashlib.sha256(_private_bytes(identity_path, maximum=16384)).hexdigest() != digest:
            raise ValueError()
        binding = CheckerBinding('6f31cfdc-a26c-4f1f-ad6b-95a8559cc657', digest, tuple(sorted(environment.items())))
        if type(value['profiles']) is not dict or set(value['profiles']) != set(CALLERS): raise ValueError()
        profiles = []
        for purpose, item in value['profiles'].items():
            if (type(item) is not dict or set(item) !=
                    {'host', 'port', 'database', 'user', 'passfile', 'passfileSha256'}
                    or item['host'] not in {'127.0.0.1', 'localhost', '::1'}
                    or type(item['port']) is not int or not 1 <= item['port'] <= 65535
                    or type(item['database']) is not str or not re.fullmatch('[A-Za-z0-9_]{1,63}', item['database'])
                    or item['user'] != CALLERS[purpose]
                    or type(item['passfileSha256']) is not str or not _HASH.fullmatch(item['passfileSha256'])):
                raise ValueError()
            passfile = Path(item['passfile'])
            credential = _private_bytes(passfile, maximum=16384)
            escaped_host = item['host'].replace('\\', '\\\\').replace(':', '\\:')
            prefix = f"{escaped_host}:{item['port']}:{item['database']}:{item['user']}:".encode()
            if (hashlib.sha256(credential).hexdigest() != item['passfileSha256']
                    or not credential.startswith(prefix) or b'\n' in credential.rstrip(b'\n')
                    or not credential[len(prefix):].strip()): raise ValueError()
            profiles.append(WindowProfile(purpose, item['host'], item['port'], item['database'],
                item['user'], passfile, item['passfileSha256']))
        if len({(p.host, p.port, p.database) for p in profiles}) != 1: raise ValueError()
        return ProtectedWindowConfig(Path(path), hashlib.sha256(raw).hexdigest(), value['enabled'], binding,
            tuple(sorted(profiles, key=lambda p: p.purpose)), value['nativeManifestSha256'],
            value['legacyManifestSha256'], tuple(sorted(value['packageSources'].items())))
    except Exception:
        raise WindowServiceBlocked('POLICY_WINDOW_PRIVATE_CONFIG_REQUIRED') from None


def _store(conn, config):
    return WindowAuthorityStore(conn, manifest_sha256=config.native_manifest_sha256,
        legacy_manifest_sha256=config.legacy_manifest_sha256, checker_binding=config.binding)


@contextmanager
def open_purpose_connection(config, purpose, read_only):
    if (type(config) is not ProtectedWindowConfig or type(purpose) is not str
            or purpose not in CALLERS or type(read_only) is not bool):
        raise WindowServiceBlocked('POLICY_WINDOW_PROTECTED_CONNECTION_REQUIRED')
    # Serialize this executor's environment/auth boundary; other API threads must
    # use a separate process, not share mutable OIDC globals with this service.
    with _SERIAL:
        fresh = load_protected_config(config.path)
        if (fresh != config or not fresh.enabled or any(os.environ.get(k) for k in _FORBIDDEN_ENV)
                or os.environ.get('PGREQUIREAUTH')):
            raise WindowServiceBlocked('POLICY_WINDOW_CONFIG_CLOSED_OR_DRIFTED')
        profile = fresh.profile(purpose)
        previous = {k: os.environ.get(k) for k, _ in fresh.binding.validated_oidc_environment}
        conn = None
        try:
            os.environ.update(dict(fresh.binding.validated_oidc_environment))
            try:
                conn = psycopg.connect(host=profile.host, port=profile.port, dbname=profile.database,
                    user=profile.user, passfile=str(profile.passfile), require_auth='scram-sha-256',
                    connect_timeout=5, options='-c statement_timeout=5000 -c lock_timeout=1000')
                store = _store(conn, fresh)
                with conn.transaction():
                    conn.execute('SET TRANSACTION ISOLATION LEVEL READ COMMITTED, READ ONLY')
                    conn.execute("SELECT set_config('aos.org_id','org-org',true),"
                                 "set_config('aos.project_id','dev-project',true),set_config('search_path','pg_catalog',true)")
                    database_identity(conn, purpose, read_only=True)
                    with conn.cursor(row_factory=dict_row) as cursor: store.verify_native_manifest(cursor)
            except Exception:
                raise WindowServiceBlocked('POLICY_WINDOW_PURPOSE_CONNECTION_UNAVAILABLE') from None
            conn.read_only = read_only
            # Do not recategorize operation or COMMIT exceptions as connect errors.
            yield conn
        finally:
            if conn is not None: conn.close()
            for k, value in previous.items():
                if value is None: os.environ.pop(k, None)
                else: os.environ[k] = value


class WindowRequest(AipContractModel):
    model_config = ConfigDict(frozen=True, hide_input_in_errors=True)
    schema_version: Literal[1]
    mode: Literal['execute', 'reconcile']
    operation: Literal['propose', 'decide', 'revoke', 'consume']
    command: WindowProposeCommand | WindowDecisionCommand | WindowRevocationCommand | WindowConsumeCommand
    bearer_token: SecretStr | None = None

    @model_validator(mode='before')
    @classmethod
    def no_machine_token_field(cls, value):
        if (type(value) is dict and value.get('operation') not in {'decide', 'revoke'}
                and any(k in value for k in ('bearerToken', 'bearer_token'))):
            raise ValueError('machine token field forbidden')
        return value

    @field_validator('schema_version', mode='before')
    @classmethod
    def exact_version(cls, value):
        if type(value) is not int: raise ValueError('integer version required')
        return value

    @field_validator('command', mode='before')
    @classmethod
    def exact_command(cls, value, info):
        expected = COMMANDS.get(info.data.get('operation'))
        if expected is None: raise ValueError('operation required')
        if type(value) is expected: value = value.model_dump(mode='python', by_alias=True)
        if type(value) is not dict: raise ValueError('exact command required')
        return expected.model_validate(value)

    @field_validator('bearer_token', mode='before')
    @classmethod
    def secret_token(cls, value):
        if type(value) is SecretStr: value = value.get_secret_value()
        if value is None: return None
        if type(value) is not str or not 0 < len(value) <= 16384: raise ValueError('bounded secret token required')
        return SecretStr(value)

    @model_validator(mode='after')
    def correct_kind(self):
        if type(self.command) is not COMMANDS[self.operation]: raise ValueError('command operation differs')
        if (self.operation in {'decide', 'revoke'}) != (self.bearer_token is not None):
            raise ValueError('issuer secret required; machine secret forbidden')
        return self

    def revalidated(self):
        return type(self).model_validate(self.model_dump(mode='python', by_alias=True,
            exclude={'bearer_token'} if self.bearer_token is None else set()))


class WindowService:
    def __init__(self, config, attempt_directory):
        if type(config) is not ProtectedWindowConfig or not Path(attempt_directory).is_absolute():
            raise WindowServiceBlocked('POLICY_WINDOW_PRIVATE_SERVICE_REQUIRED')
        self.config = config
        self.attempt_directory = Path(attempt_directory)

    def reconcile(self, request):
        if type(request) is not WindowRequest: raise WindowServiceBlocked('POLICY_WINDOW_EXACT_PRIVATE_REQUEST_REQUIRED')
        request = request.revalidated()
        with open_purpose_connection(self.config, PURPOSES[request.operation], True) as conn:
            return _store(conn, self.config).reconcile(request.command, token=request.bearer_token)

    def execute(self, request):
        if type(request) is not WindowRequest: raise WindowServiceBlocked('POLICY_WINDOW_EXACT_PRIVATE_REQUEST_REQUIRED')
        request = request.revalidated()
        if request.mode == 'reconcile': return self.reconcile(request)
        purpose = PURPOSES[request.operation]
        # Real current authentication and both pins precede durable reservation.
        with open_purpose_connection(self.config, purpose, True) as conn:
            with conn.transaction():
                conn.execute('SET TRANSACTION ISOLATION LEVEL READ COMMITTED, READ ONLY')
                conn.execute("SELECT set_config('aos.org_id','org-org',true),set_config('aos.project_id','dev-project',true)")
                database_identity(conn, purpose, read_only=True)
                subject = 'postgres-service:aos_budget_renewal_maker_call'
                if purpose == 'issuer':
                    subject = authenticate_checker(request.bearer_token, binding=self.config.binding,
                                                   conn=conn, read_only=True).subject
        command = request.command
        source = command.parent_cost_proposal_id if request.operation == 'propose' else command.proposal_id
        marker = AttemptReceipt(command.org_id, command.project_id, source, command.idempotency_key,
                                command.request_hash, subject)
        try:
            _reserve_attempt_receipt(self.attempt_directory, marker, namespace='budget-policy-window/v1/'+request.operation)
        except AttemptAlreadyRecorded:
            return self.reconcile(request)
        except AttemptConflict:
            return self._status(request, 'conflict')
        except AttemptUnknown:
            return self._try_reconcile(request, 'unresolved')
        except AttemptBlocked:
            raise WindowServiceBlocked('POLICY_WINDOW_PRIVATE_ATTEMPT_REQUIRED') from None
        try:
            with open_purpose_connection(self.config, purpose, False) as conn:
                store = _store(conn, self.config)
                if purpose == 'issuer': return getattr(store, request.operation)(command, token=request.bearer_token)
                return getattr(store, request.operation)(command)
        except WindowStoreBlocked:
            return self._status(request, 'blocked')
        except Exception:
            return self._try_reconcile(request, 'unresolved')

    def _try_reconcile(self, request, fallback):
        try: return self.reconcile(request)
        except Exception: return self._status(request, fallback)

    @staticmethod
    def _status(request, status):
        return dict(operation=request.operation, requestHash=request.command.request_hash,
                    status=status, activationEligible=False)
