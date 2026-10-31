"""Read child provenance on the original native admission transaction.

This module does not open connections, create holds, approve requests, commit,
or retry. Independent deployment pins and the original parent verifier remain
mandatory. Configuration is private startup input, never a request field.
"""
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from types import MappingProxyType

import psycopg
from psycopg import IsolationLevel
from psycopg.pq import TransactionStatus
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from aos_api.aip_budget_policy_window_catalog import (
    WindowCatalogBlocked, verify_window_catalog, verify_functions,
)
from aos_api.aip_budget_reservation_contracts import BudgetExactRef
from aos_api.tenant_scope import TenantScope

CONFIG_ENV = 'AOS_POLICY_WINDOW_RUNTIME_CONFIG'
ENTRY = 'public.aip_policy_window_risk_fact_v1(jsonb,jsonb)'
RUNTIME_LOGIN = 'aos_a0v_runtime_20260912'
RUNTIME_ROLE = 'aos_runtime'
EVALUATOR_LOGIN = 'aos_aip_binding_evaluator'
_HASH = re.compile('[0-9a-f]{64}')
_PRICE = re.compile('window-price-([0-9a-f]{64})')


class WindowRiskBlocked(ValueError):
    pass


@dataclass(frozen=True)
class WindowRuntimeConfig:
    expected_database: str
    native_manifest_sha256: str
    legacy_manifest_sha256: str
    runtime_manifest_sha256: str
    fingerprint: str


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate key')
        result[key] = value
    return result


def _file_stat(value):
    return (value.st_dev, value.st_ino, value.st_mode, value.st_uid, value.st_nlink,
            value.st_size, value.st_mtime_ns, value.st_ctime_ns)


def load_runtime_config(path):
    """Read exactly one stable private file; no DSN or credential is accepted."""
    try:
        path = Path(path)
        if not path.is_absolute() or path.resolve(strict=True) != path:
            raise ValueError()
        parent = path.parent.lstat()
        if (not stat.S_ISDIR(parent.st_mode) or parent.st_uid != os.geteuid()
                or stat.S_IMODE(parent.st_mode) != 0o700):
            raise ValueError()
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            opened_parent = os.fstat(directory)
            if (opened_parent.st_dev, opened_parent.st_ino) != (parent.st_dev, parent.st_ino):
                raise ValueError()
            fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                         dir_fd=directory)
            with os.fdopen(fd, 'rb') as stream:
                before = os.fstat(stream.fileno())
                if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.geteuid()
                        or stat.S_IMODE(before.st_mode) != 0o600 or before.st_nlink != 1
                        or not 0 < before.st_size <= 16384):
                    raise ValueError()
                raw = stream.read(16385)
                after = os.fstat(stream.fileno())
            if (_file_stat(before) != _file_stat(after) or len(raw) != before.st_size
                    or _file_stat(path.lstat()) != _file_stat(before)
                    or path.resolve(strict=True) != path):
                raise ValueError()
        finally:
            os.close(directory)
        body = json.loads(raw, object_pairs_hook=_unique)
        fields = {'schemaVersion', 'enabled', 'expectedDatabase', 'runtimeLogin', 'runtimeRole',
                  'evaluatorLogin', 'nativeManifestSha256', 'legacyManifestSha256', 'runtimeManifestSha256'}
        if (type(body) is not dict or set(body) != fields
                or body['schemaVersion'] != 'aos.policy-window.runtime-private/v1'
                or body['enabled'] is not True
                or (body['runtimeLogin'], body['runtimeRole'], body['evaluatorLogin']) != (
                    RUNTIME_LOGIN, RUNTIME_ROLE, EVALUATOR_LOGIN)
                or type(body['expectedDatabase']) is not str
                or not 1 <= len(body['expectedDatabase']) <= 63
                or body['expectedDatabase'] != body['expectedDatabase'].strip()
                or not body['expectedDatabase'].isprintable()
                or any(type(body[key]) is not str or not _HASH.fullmatch(body[key]) for key in (
                    'nativeManifestSha256', 'legacyManifestSha256', 'runtimeManifestSha256'))):
            raise ValueError()
        return WindowRuntimeConfig(body['expectedDatabase'], body['nativeManifestSha256'],
            body['legacyManifestSha256'], body['runtimeManifestSha256'], hashlib.sha256(raw).hexdigest())
    except (OSError, TypeError, ValueError):
        raise WindowRiskBlocked('POLICY_WINDOW_RUNTIME_PRIVATE_CONFIG_REQUIRED') from None


def _freeze(value):
    if type(value) is dict:
        if any(type(key) is not str for key in value):
            raise WindowRiskBlocked('POLICY_WINDOW_RUNTIME_FACT_REQUIRED')
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if type(value) is list:
        return tuple(_freeze(item) for item in value)
    if value is None or type(value) in (str, bool, int):
        return value
    raise WindowRiskBlocked('POLICY_WINDOW_RUNTIME_FACT_REQUIRED')


def _thaw(value):
    if isinstance(value, MappingProxyType):
        return {key: _thaw(item) for key, item in value.items()}
    if type(value) is tuple:
        return [_thaw(item) for item in value]
    return value


@dataclass(frozen=True)
class WindowRiskFact:
    payload: MappingProxyType
    effective_until: datetime

    @property
    def parent(self):
        return self.payload['parent']

    @property
    def decision_id(self):
        return self.payload['decisionId']

    @property
    def policy_ref(self):
        return self.payload['policyRef']

    def to_payload(self):
        return _thaw(self.payload)


def _wire_ref(ref, kind):
    if (type(ref) is not BudgetExactRef or ref.resource_type != kind
            or type(ref.revision) is not int or not 1 <= ref.revision <= 9007199254740991
            or type(ref.resource_id) is not str or ref.resource_id != ref.resource_id.strip()
            or not 1 <= len(ref.resource_id) <= 200
            or type(ref.content_hash) is not str or not ref.content_hash.startswith('sha256:')
            or not _HASH.fullmatch(ref.content_hash[7:])):
        raise WindowRiskBlocked('POLICY_WINDOW_RUNTIME_EXACT_REFERENCE_REQUIRED')
    return dict(assetType=kind, assetId=ref.resource_id, revision=ref.revision, contentHash=ref.content_hash[7:])


def _require_native(conn, scope):
    if (type(conn) is not psycopg.Connection or conn.closed or conn.autocommit or conn.read_only
            or conn.isolation_level != IsolationLevel.SERIALIZABLE or conn.row_factory is not dict_row
            or conn.info.transaction_status != TransactionStatus.INTRANS
            or not conn.pgconn.used_password
            or conn.info.get_parameters().get('require_auth') != 'scram-sha-256'):
        raise WindowRiskBlocked('POLICY_WINDOW_RUNTIME_NATIVE_DATABASE_CONNECTION_REQUIRED')
    if type(scope) is not TenantScope or scope.key != ('org-org', 'dev-project'):
        raise WindowRiskBlocked('POLICY_WINDOW_RUNTIME_TENANT_REQUIRED')


def _catalog(conn, config):
    previous = conn.execute("SELECT current_setting('search_path') AS path").fetchone()['path']
    conn.execute("SELECT set_config('search_path','pg_catalog',true)")
    try:
        with conn.cursor(row_factory=dict_row) as cursor:
            verify_window_catalog(cursor, manifest_sha256=config.native_manifest_sha256,
                                  legacy_manifest_sha256=config.legacy_manifest_sha256)
            row = cursor.execute("SELECT pg_catalog.obj_description(pg_catalog.to_regprocedure(%s),'pg_proc') AS raw",
                                 (ENTRY,)).fetchone()
            raw = row['raw'] if row else None
            if type(raw) is not str or hashlib.sha256(raw.encode()).hexdigest() != config.runtime_manifest_sha256:
                raise WindowRiskBlocked('POLICY_WINDOW_RUNTIME_INDEPENDENT_SEAL_REQUIRED')
            seal = json.loads(raw, object_pairs_hook=_unique)
            if (type(seal) is not dict or set(seal) != {
                    'schema', 'function', 'dependencies', 'runtimeLogin', 'runtimeRole', 'evaluatorLogin'}
                    or seal['schema'] != 'aos-policy-window-runtime-seal/v1'
                    or (seal['runtimeLogin'], seal['runtimeRole'], seal['evaluatorLogin']) != (
                        RUNTIME_LOGIN, RUNTIME_ROLE, EVALUATOR_LOGIN)
                    or seal['dependencies'] != {
                        'aip_budget_policy_window_proposal': config.native_manifest_sha256,
                        'aip_budget_policy_renewal_proposal': config.legacy_manifest_sha256}
                    or seal['function']['signature'] != ENTRY
                    or seal['function']['owner'] != 'aos_budget_consumer_owner'
                    or seal['function']['definer'] is not True
                    or seal['function']['config'] != ['search_path=pg_catalog']):
                raise WindowRiskBlocked('POLICY_WINDOW_RUNTIME_INDEPENDENT_SEAL_REQUIRED')
            verify_functions(cursor, [seal['function']])
    except WindowCatalogBlocked as error:
        raise WindowRiskBlocked(str(error)) from None
    except (KeyError, TypeError, ValueError) as error:
        if isinstance(error, WindowRiskBlocked):
            raise
        raise WindowRiskBlocked('POLICY_WINDOW_RUNTIME_INDEPENDENT_SEAL_REQUIRED') from None
    finally:
        # An aborted native transaction must retain its original SQLSTATE.
        if not conn.closed and conn.info.transaction_status == TransactionStatus.INTRANS:
            conn.execute("SELECT set_config('search_path',%s,true)", (previous,))


def _fact(raw, budget, price, now):
    fields = {'schema', 'factOnly', 'activationEligible', 'parent', 'policyRef', 'priceRef',
              'proposalId', 'proposalHash', 'decisionId', 'decisionHash', 'receiptId',
              'bindingId', 'bindingHash', 'fenceVersion', 'effectiveFrom', 'effectiveUntil'}
    try:
        suffix = _PRICE.fullmatch(price['assetId']).group(1)
        if (type(raw) is not dict or set(raw) != fields or raw['schema'] != 'aos-policy-window-risk-fact/v1'
                or raw['factOnly'] is not True or raw['activationEligible'] is not False
                or type(raw['parent']) is not dict or raw['parent']['budgetRef'] != budget
                or raw['priceRef'] != price or raw['proposalId'] != 'window-proposal-' + suffix
                or raw['decisionId'] != 'window-approval-' + suffix
                or type(raw['fenceVersion']) is not int or raw['fenceVersion'] != 2):
            raise ValueError()
        policy = raw['policyRef']
        if (type(policy) is not dict or set(policy) != {'assetType', 'assetId', 'revision', 'contentHash'}
                or policy['assetType'] != 'BudgetPolicyRevision' or policy['assetId'] != 'window-policy-' + suffix
                or type(policy['revision']) is not int or policy['revision'] != 1):
            raise ValueError()
        for digest in (raw['proposalHash'], raw['decisionHash'], raw['bindingHash'], policy['contentHash']):
            if type(digest) is not str or not _HASH.fullmatch(digest):
                raise ValueError()
        for key, prefix in [('receiptId', 'window-consume-'), ('bindingId', 'window-binding-')]:
            if type(raw[key]) is not str or not raw[key].startswith(prefix) or not _HASH.fullmatch(raw[key][len(prefix):]):
                raise ValueError()
        start = datetime.fromisoformat(raw['effectiveFrom'].replace('Z', '+00:00'))
        until = datetime.fromisoformat(raw['effectiveUntil'].replace('Z', '+00:00'))
        if start.utcoffset() is None or until.utcoffset() is None or not start <= now < until:
            raise ValueError()
        return WindowRiskFact(_freeze(raw), until)
    except (KeyError, TypeError, ValueError, AttributeError):
        raise WindowRiskBlocked('POLICY_WINDOW_RUNTIME_FACT_REQUIRED') from None


def read_native_window_risk_fact(conn, *, scope, budget_ref, price_ref):
    """Fixed native entry; it never accepts a wrapper, supplied config or callback."""
    _require_native(conn, scope)
    budget = _wire_ref(budget_ref, 'BudgetRevision')
    price = _wire_ref(price_ref, 'ModelPriceSnapshotRevision')
    matched = _PRICE.fullmatch(price['assetId'])
    if matched is None or price['revision'] != 1:
        raise WindowRiskBlocked('POLICY_WINDOW_RUNTIME_EXACT_REFERENCE_REQUIRED')
    path = os.environ.get(CONFIG_ENV)
    config = load_runtime_config(path)
    if conn.info.dbname != config.expected_database:
        raise WindowRiskBlocked('POLICY_WINDOW_RUNTIME_DATABASE_REQUIRED')
    identity = conn.execute("SELECT session_user AS login,current_user AS role,"
        "current_setting('aos.org_id',true) AS org,current_setting('aos.project_id',true) AS project").fetchone()
    if (identity is None or (identity['org'], identity['project']) != scope.key
            or (identity['login'], identity['role']) not in {
                (RUNTIME_LOGIN, RUNTIME_ROLE), (EVALUATOR_LOGIN, EVALUATOR_LOGIN)}):
        raise WindowRiskBlocked('POLICY_WINDOW_RUNTIME_ACTUAL_CALLER_REQUIRED')
    _catalog(conn, config)
    # These original caller grants supply head locks; the child definer receives
    # no new UPDATE privilege on either old sealed relation.
    head = conn.execute('SELECT current_revision FROM public.aip_model_price_snapshot_head '
        'WHERE org_id=%s AND project_id=%s AND model_price_snapshot_id=%s FOR SHARE',
        (*scope.key, price['assetId'])).fetchone()
    policy_head = conn.execute("SELECT current_revision FROM public.aip_model_governance_policy_head "
        "WHERE org_id=%s AND project_id=%s AND policy_kind='budget' AND policy_id=%s FOR SHARE",
        (*scope.key, 'window-policy-' + matched.group(1))).fetchone()
    if not head or not policy_head or head['current_revision'] != 1 or policy_head['current_revision'] != 1:
        raise WindowRiskBlocked('POLICY_WINDOW_RUNTIME_CURRENT_HEAD_REQUIRED')
    raw = conn.execute('SELECT public.aip_policy_window_risk_fact_v1(%s,%s) AS fact',
                       (Jsonb(budget), Jsonb(price))).fetchone()['fact']
    now = conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
    fact = _fact(raw, budget, price, now)
    if os.environ.get(CONFIG_ENV) != path or load_runtime_config(path).fingerprint != config.fingerprint:
        raise WindowRiskBlocked('POLICY_WINDOW_RUNTIME_PRIVATE_CONFIG_DRIFT')
    return fact


def read_window_risk_fact(conn, *, scope, budget_ref, price_ref):
    if type(conn) is psycopg.Connection:
        return read_native_window_risk_fact(conn, scope=scope, budget_ref=budget_ref, price_ref=price_ref)
    from aos_api.ecommerce_growth_host_ports import HostTransaction
    if type(conn) is HostTransaction:
        return conn.read_window_risk_fact(scope=scope, budget_ref=budget_ref, price_ref=price_ref)
    raise WindowRiskBlocked('POLICY_WINDOW_RUNTIME_NATIVE_DATABASE_CONNECTION_REQUIRED')
