"""Purpose-only native window adapter with independent pinned-catalog checks.

No DSN, role provisioning, retries, or runtime admission. The protected caller
supplies the deployed manifest fingerprint independently of the current catalog.
"""
import re

import psycopg
from psycopg.pq import TransactionStatus
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic import SecretStr

from aos_api.aip_budget_store import canonical_hash
from aos_api.aip_budget_policy_window_catalog import (
    WindowCatalogBlocked, verify_window_catalog, verify_functions,
    FUNCTIONS, TABLES, RELATIONS, _RELATION_METADATA,
)
from aos_api.aip_budget_policy_renewal_store import (
    _SEALED_FUNCTIONS as LEGACY_FUNCTIONS, _SEALED_RELATIONS as LEGACY_RELATIONS,
)
from aos_api.aip_budget_policy_window_commands import (
    WindowProposeCommand, WindowDecisionCommand, WindowRevocationCommand, WindowConsumeCommand,
)
from aos_api.aip_budget_policy_window_identity import (
    CALLERS, CheckerBinding, WindowIdentityBlocked, database_identity, authenticate_checker,
)


class WindowStoreBlocked(ValueError):
    pass


class WindowStoreUnknown(RuntimeError):
    """Retain the original command for readonly reconciliation; never resend."""
    def __init__(self, *, operation, key, request_hash):
        super().__init__('POLICY_WINDOW_ATTEMPT_UNKNOWN_READ_ONLY_RECONCILE_REQUIRED')
        self.operation = operation
        self.idempotency_key = key
        self.request_hash = request_hash


ENTRIES = {WindowProposeCommand: ('propose', 'maker'), WindowDecisionCommand: ('decide', 'issuer'),
           WindowRevocationCommand: ('revoke', 'issuer'), WindowConsumeCommand: ('consume', 'consumer')}
_HASH = re.compile('[0-9a-f]{64}')
_CHECKER = '6f31cfdc-a26c-4f1f-ad6b-95a8559cc657'
_MACHINE = 'postgres-service:aos_budget_renewal_maker_call'


class WindowAuthorityStore:
    def __init__(self, conn, *, manifest_sha256, legacy_manifest_sha256, checker_binding=None):
        self._conn = conn
        self._binding = checker_binding
        self._idle()
        if type(manifest_sha256) is not str or not _HASH.fullmatch(manifest_sha256):
            raise WindowStoreBlocked('POLICY_WINDOW_PINNED_MANIFEST_REQUIRED')
        if type(legacy_manifest_sha256) is not str or not _HASH.fullmatch(legacy_manifest_sha256):
            raise WindowStoreBlocked('POLICY_WINDOW_PINNED_LEGACY_MANIFEST_REQUIRED')
        self._manifest_sha256 = manifest_sha256
        self._legacy_manifest_sha256 = legacy_manifest_sha256

    def _idle(self):
        c = self._conn
        if (type(c) is not psycopg.Connection or c.closed or c.autocommit
                or c.info.transaction_status != TransactionStatus.IDLE or c.info.user not in CALLERS.values()):
            raise WindowStoreBlocked('POLICY_WINDOW_REAL_IDLE_DATABASE_CONNECTION_REQUIRED')

    def verify_native_manifest(self, cursor):
        try:
            verify_window_catalog(cursor, manifest_sha256=self._manifest_sha256,
                                  legacy_manifest_sha256=self._legacy_manifest_sha256)
        except WindowCatalogBlocked as error:
            raise WindowStoreBlocked(str(error)) from None

    @staticmethod
    def _verify_functions(cursor, entries):
        try:
            verify_functions(cursor, entries)
        except WindowCatalogBlocked as error:
            raise WindowStoreBlocked(str(error)) from None

    def propose(self, command):
        return self._call(command, expected=WindowProposeCommand)

    def decide(self, command, *, token):
        return self._call(command, expected=WindowDecisionCommand, token=token)

    def revoke(self, command, *, token):
        return self._call(command, expected=WindowRevocationCommand, token=token)

    def consume(self, command):
        return self._call(command, expected=WindowConsumeCommand)

    def reconcile(self, command, *, token=None):
        return self._call(command, expected=type(command), token=token, reconcile=True)

    def _call(self, command, *, expected, token=None, reconcile=False):
        self._idle()
        if expected not in ENTRIES or type(command) is not expected:
            raise WindowStoreBlocked('POLICY_WINDOW_EXACT_COMMAND_REQUIRED')
        try:
            payload = command.canonical_payload()
            command = expected.model_validate(payload)
            digest = command.request_hash
        except Exception:
            raise WindowStoreBlocked('POLICY_WINDOW_EXACT_COMMAND_REQUIRED') from None
        operation, purpose = ENTRIES[expected]
        if self._conn.info.user != CALLERS[purpose]:
            raise WindowStoreBlocked('POLICY_WINDOW_OPERATION_LOGIN_REQUIRED')
        if purpose != 'issuer' and token is not None:
            raise WindowStoreBlocked('POLICY_WINDOW_MACHINE_TOKEN_FORBIDDEN')
        if purpose == 'issuer' and (type(token) is not SecretStr or type(self._binding) is not CheckerBinding):
            raise WindowStoreBlocked('POLICY_WINDOW_PROTECTED_HUMAN_GATEWAY_REQUIRED')
        try:
            with self._conn.transaction():
                with self._conn.cursor(row_factory=dict_row) as cur:
                    cur.execute('SET TRANSACTION ISOLATION LEVEL READ COMMITTED, '+
                                ('READ ONLY' if reconcile else 'READ WRITE'))
                    cur.execute("SELECT set_config('aos.org_id','org-org',true),"
                                "set_config('aos.project_id','dev-project',true),"
                                "set_config('search_path','pg_catalog',true),"
                                "set_config('statement_timeout','5000',true),set_config('lock_timeout','1000',true)")
                    database_identity(self._conn, purpose, read_only=reconcile)
                    self.verify_native_manifest(cur)
                    actor = _MACHINE
                    if purpose == 'issuer':
                        actor = authenticate_checker(token, binding=self._binding, conn=self._conn,
                                                     read_only=reconcile).subject
                    if reconcile:
                        row = cur.execute('SELECT public.aip_policy_window_reconcile_v1(%s,%s,%s) AS result',
                                          (Jsonb(payload), operation, actor)).fetchone()
                    else:
                        # Names derive only from exact command-type whitelist.
                        name = 'public.aip_policy_window_'+operation+'_v1'
                        if purpose == 'issuer':
                            row = cur.execute('SELECT '+name+'(%s,%s) AS result', (Jsonb(payload), actor)).fetchone()
                        else:
                            row = cur.execute('SELECT '+name+'(%s) AS result', (Jsonb(payload),)).fetchone()
                    result = row['result'] if row else None
                    self.validate_result(result, command, reconcile=reconcile)
            # Only return after COMMIT, including deferred output constraints.
            return result
        except (WindowStoreBlocked, WindowIdentityBlocked):
            raise
        except psycopg.Error as error:
            if (error.sqlstate is not None and not error.sqlstate.startswith(('08', '57P'))
                    and not self._conn.closed and self._conn.info.transaction_status == TransactionStatus.IDLE):
                raise WindowStoreBlocked('POLICY_WINDOW_NATIVE_TRANSACTION_REJECTED:'+error.sqlstate) from None
            raise WindowStoreUnknown(operation=operation, key=command.idempotency_key, request_hash=digest) from None
        except Exception:
            raise WindowStoreUnknown(operation=operation, key=command.idempotency_key, request_hash=digest) from None

    @staticmethod
    def validate_result(result, command, *, reconcile):
        try:
            if type(result) is not dict or result.get('activationEligible') is not False:
                raise ValueError()
            if reconcile:
                if result == {'status': 'unresolved', 'activationEligible': False}: return
                if set(result) != {'status', 'receipt', 'activationEligible'} or result['status'] != 'observed':
                    raise ValueError()
                WindowAuthorityStore.validate_result(result['receipt'], command, reconcile=False)
                return
            op = command.operation
            actor = _CHECKER if op in {'decide', 'revoke'} else _MACHINE
            receipt_id = 'window-'+op+'-'+canonical_hash(dict(domain='aos.policy-window-receipt-id/v1',
                operation=op, actor=actor, tenant=dict(orgId='org-org', projectId='dev-project'), key=command.idempotency_key))
            if (result.get('operation') != op or result.get('requestHash') != command.request_hash
                    or result.get('command') != command.canonical_payload() or result.get('receiptId') != receipt_id
                    or result.get('status') != ('prepared' if op == 'propose' else 'observed')):
                raise ValueError()
            if op == 'propose':
                p = result['proposal']
                ident = canonical_hash(dict(domain='aos.window-proposal-id/v1',
                    tenant=dict(orgId='org-org', projectId='dev-project'), maker=_MACHINE, key=command.idempotency_key))
                if (p['request'] != command.canonical_payload() or p['requestHash'] != command.request_hash
                        or p['makerSubject'] != _MACHINE or p['checkerSubject'] != _CHECKER
                        or p['approvalSlot'] != 'window-approval-'+ident
                        or result['proposalId'] != 'window-proposal-'+ident
                        or result['proposalHash'] != canonical_hash(dict(domain='aos.budget-policy-window.proposal/v1', proposal=p))
                        or p['targetPairHash'] != canonical_hash(dict(domain='aos.budget-policy-window.targets/v1', targets=p['targets']))
                        or result['targetPairHash'] != p['targetPairHash']):
                    raise ValueError()
            else:
                if result['proposalId'] != command.proposal_id or result['proposalHash'] != command.proposal_hash:
                    raise ValueError()
                if type(result['decisionHash']) is not str or not _HASH.fullmatch(result['decisionHash']):
                    raise ValueError()
                if op == 'decide' and result['decision'] != command.decision: raise ValueError()
                if op == 'revoke' and (result['decision'] != 'revoked' or result['decisionId'] != receipt_id):
                    raise ValueError()
                if op == 'consume':
                    if (result['decisionId'] != command.decision_id or result['decisionHash'] != command.decision_hash
                            or result['targetPairHash'] != command.target_pair_hash
                            or not _HASH.fullmatch(result['bindingHash'])): raise ValueError()
                    for field, kind, prefix in [('policyRef', 'BudgetPolicyRevision', 'window-policy-'),
                                                ('priceRef', 'ModelPriceSnapshotRevision', 'window-price-')]:
                        ref = result[field]
                        if (set(ref) != {'assetType', 'assetId', 'revision', 'contentHash'}
                                or ref['assetType'] != kind or not ref['assetId'].startswith(prefix)
                                or type(ref['revision']) is not int or ref['revision'] != 1
                                or not _HASH.fullmatch(ref['contentHash'])): raise ValueError()
        except (KeyError, ValueError, TypeError, AttributeError):
            raise WindowStoreBlocked('POLICY_WINDOW_NATIVE_RESULT_CONTRACT_REQUIRED') from None
