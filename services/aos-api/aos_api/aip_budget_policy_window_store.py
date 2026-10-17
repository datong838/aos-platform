"""Purpose-only native window adapter with independent pinned-catalog checks.

No DSN, role provisioning, retries, or runtime admission. The protected caller
supplies the deployed manifest fingerprint independently of the current catalog.
"""
import hashlib
import json
import re

import psycopg
from psycopg.pq import TransactionStatus
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic import SecretStr

from aos_api.aip_budget_store import canonical_hash
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
_NATIVE = ('command(jsonb,text)', 'relation_shape(oid)', 'profile(text)', 'parent(jsonb,boolean)',
           'expected(jsonb,text)', 'history(jsonb,text,text)', 'proposal_fact(text,text,boolean)',
           'propose(jsonb)', 'decide(jsonb,text)', 'revoke(jsonb,text)', 'consume(jsonb)',
           'reconcile(jsonb,text,text)', 'guard_journal()', 'guard_fence()', 'complete_consume()')
FUNCTIONS = {'public.aip_policy_window_'+s.split('(', 1)[0]+'_v1('+s.split('(', 1)[1] for s in _NATIVE} | {
    'public.aip_budget_cost_hash_a0v_126(jsonb)', 'public.canonical_asset_registry_jsonb(jsonb)',
    'public.guard_aip4_append_only()',
    'public.aip_budget_consumption_fact_a0v_128(text,text,text,text,text,text)',
    'public.aip_budget_cost_actor_a0v_127(text,text,text,text,text)',
    'public.aip_cost_configuration_write_guard_a0v_128()', 'public.aip_renewal_profile_a0v_162(text)'}
TABLES = {'aip_budget_policy_window_'+s for s in ('proposal', 'decision', 'receipt', 'binding', 'fence')}
RELATIONS = TABLES | {'aip_budget_cost_proposal', 'aip_budget_cost_decision', 'aip_budget_cost_revocation',
    'aip_budget_receipt', 'aip_budget_cost_runtime_fence', 'aip_budget_head', 'aip_budget_revision',
    'aip_provider_instance_head', 'aip_provider_instance_revision', 'meta_membership',
    'aip_model_governance_policy_head', 'aip_model_governance_policy_revision',
    'aip_model_price_snapshot_head', 'aip_model_price_snapshot_revision'}
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
        row = cursor.execute("SELECT pg_catalog.obj_description('public.aip_budget_policy_window_proposal'"
                             "::regclass,'pg_class') AS seal").fetchone()
        try:
            raw = row['seal']
            if type(raw) is not str or hashlib.sha256(raw.encode()).hexdigest() != self._manifest_sha256:
                raise ValueError()
            def unique(pairs):
                result = {}
                for key, value in pairs:
                    if key in result: raise ValueError()
                    result[key] = value
                return result
            seal = json.loads(raw, object_pairs_hook=unique)
            if (set(seal) != {'schema', 'functions', 'relations'}
                    or seal['schema'] != 'aos-policy-window-native-seal/v1'
                    or type(seal['functions']) is not list or len(seal['functions']) != len(FUNCTIONS)
                    or {f['signature'] for f in seal['functions']} != FUNCTIONS
                    or type(seal['relations']) is not list or len(seal['relations']) != len(RELATIONS)
                    or {r['name'] for r in seal['relations']} != RELATIONS):
                raise ValueError()
        except (KeyError, ValueError, TypeError):
            raise WindowStoreBlocked('POLICY_WINDOW_PINNED_MANIFEST_REQUIRED') from None
        self._verify_functions(cursor, seal['functions'])
        for expected in seal['relations']:
            row = cursor.execute(_RELATION_METADATA, ('public.'+expected['name'],)).fetchone()
            if not row or row['metadata'] != expected:
                raise WindowStoreBlocked('POLICY_WINDOW_RELATION_SEAL_DRIFT')
        # The checker-member dependency is in the independently pinned old seal.
        row = cursor.execute("SELECT pg_catalog.obj_description('public.aip_budget_policy_renewal_proposal'"
                             "::regclass,'pg_class') AS seal").fetchone()
        try:
            raw = row['seal']
            if type(raw) is not str or hashlib.sha256(raw.encode()).hexdigest() != self._legacy_manifest_sha256:
                raise ValueError()
            legacy = json.loads(raw, object_pairs_hook=unique)
            if (set(legacy) != {'schema', 'functions', 'relations'}
                    or legacy['schema'] != 'aos-renewal-schema-seal/v1'
                    or type(legacy['functions']) is not list or len(legacy['functions']) != len(LEGACY_FUNCTIONS)
                    or {f['signature'] for f in legacy['functions']} != LEGACY_FUNCTIONS
                    or type(legacy['relations']) is not list or len(legacy['relations']) != len(LEGACY_RELATIONS)
                    or {r['name'] for r in legacy['relations']} != LEGACY_RELATIONS):
                raise ValueError()
        except (KeyError, ValueError, TypeError):
            raise WindowStoreBlocked('POLICY_WINDOW_PINNED_LEGACY_MANIFEST_REQUIRED') from None
        self._verify_functions(cursor, legacy['functions'])
        legacy_fields = {'name', 'owner', 'rls', 'forceRls', 'acl', 'columns', 'policies'}
        for expected in legacy['relations']:
            row = cursor.execute(_RELATION_METADATA, ('public.'+expected['name'],)).fetchone()
            if (set(expected) != legacy_fields or not row
                    or {k: row['metadata'][k] for k in legacy_fields} != expected):
                raise WindowStoreBlocked('POLICY_WINDOW_LEGACY_RELATION_SEAL_DRIFT')

    @staticmethod
    def _verify_functions(cursor, entries):
        for expected in entries:
            row = cursor.execute("""SELECT jsonb_build_object('signature',%s::text,
                'owner',pg_get_userbyid(p.proowner),'definer',p.prosecdef,'config',to_jsonb(p.proconfig),
                'acl',p.proacl::text,'definition',pg_get_functiondef(p.oid)) AS metadata
                FROM pg_catalog.pg_proc p WHERE p.oid=pg_catalog.to_regprocedure(%s)""",
                (expected['signature'], expected['signature'])).fetchone()
            actual = row['metadata'] if row else None
            if actual is not None:
                actual['bodySha256'] = hashlib.sha256(actual.pop('definition').encode()).hexdigest()
            if actual != expected:
                raise WindowStoreBlocked('POLICY_WINDOW_FUNCTION_SEAL_DRIFT')

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


# Catalog-only observation: never execute the sealed relation helper.
_RELATION_METADATA = """ SELECT jsonb_build_object('name',c.relname,'owner',pg_get_userbyid(c.relowner),
  'rls',c.relrowsecurity,'forceRls',c.relforcerowsecurity,'acl',c.relacl::text,
  'columns',(SELECT jsonb_agg(jsonb_build_object('name',a.attname,'acl',a.attacl::text) ORDER BY a.attnum)
   FROM pg_attribute a WHERE a.attrelid=c.oid AND a.attnum>0 AND NOT a.attisdropped),
  'policies',COALESCE((SELECT jsonb_agg(jsonb_build_object('name',p.polname,'roles',to_jsonb(p.polroles),
   'permissive',p.polpermissive,'command',p.polcmd,'using',pg_get_expr(p.polqual,p.polrelid),
   'check',pg_get_expr(p.polwithcheck,p.polrelid)) ORDER BY p.polname)
   FROM pg_policy p WHERE p.polrelid=c.oid),'[]'::jsonb),
  'triggers',COALESCE((SELECT jsonb_agg(jsonb_build_object('name',t.tgname,'enabled',t.tgenabled,
    'definition',pg_get_triggerdef(t.oid)) ORDER BY t.tgname)
   FROM pg_trigger t WHERE t.tgrelid=c.oid AND NOT t.tgisinternal),'[]'::jsonb),
  'indexes',COALESCE((SELECT jsonb_agg(jsonb_build_object('name',ic.relname,
    'definition',pg_get_indexdef(i.indexrelid),'valid',i.indisvalid,'ready',i.indisready)
    ORDER BY ic.relname) FROM pg_index i JOIN pg_class ic ON ic.oid=i.indexrelid
    WHERE i.indrelid=c.oid),'[]'::jsonb),
  'constraints',COALESCE((SELECT jsonb_agg(jsonb_build_object('name',co.conname,
    'type',co.contype,'deferrable',co.condeferrable,'deferred',co.condeferred,
    'definition',pg_get_constraintdef(co.oid)) ORDER BY co.conname)
    FROM pg_constraint co WHERE co.conrelid=c.oid),'[]'::jsonb)) AS metadata
 FROM pg_class c WHERE c.oid=pg_catalog.to_regclass(%s) AND c.relnamespace='public'::regnamespace"""
