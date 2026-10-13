"""Private three-actor adapter for bounded native renewal functions.

No shared DSN, request actor, retry, deployment or connection provisioning lives
here. The protected gateway supplies one owned connection and the original JWT.
Publication proof must come from SQL; a parsed command is never an approval.
"""
import hashlib
import json
import psycopg
from psycopg.pq import TransactionStatus
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic import SecretStr

from aos_api.aip_budget_policy_renewal_contracts import (
    RenewalProposalCommand, RenewalDecisionCommand, RenewalConsumeCommand,
    RenewalRevocationCommand,
)
from aos_api.aip_budget_policy_renewal_identity import (
    CheckerBinding, RenewalIdentityBlocked, _database_identity, authenticate_checker,
)


class RenewalStoreBlocked(ValueError):
    pass


class RenewalStoreUnknown(RuntimeError):
    """Original key/hash must be reconciled read-only; this does not permit resend."""
    def __init__(self, *, operation, key, request_hash):
        super().__init__('RENEWAL_ATTEMPT_UNKNOWN_READ_ONLY_RECONCILE_REQUIRED')
        self.operation, self.idempotency_key, self.request_hash = operation, key, request_hash


_ENTRIES = {
    RenewalProposalCommand: ('propose', 'maker'),
    RenewalDecisionCommand: ('decide', 'issuer'),
    RenewalRevocationCommand: ('revoke', 'issuer'),
    RenewalConsumeCommand: ('consume', 'consumer'),
}
_CALLERS = {'maker': 'aos_budget_renewal_maker_call',
            'issuer': 'aos_budget_renewal_issuer_call',
            'consumer': 'aos_budget_renewal_consumer_call'}
_SEALED_FUNCTIONS = {
    'public.aip_renewal_relation_shape_a0v_162(oid)',
    'public.aip_renewal_profile_a0v_162(text)',
    'public.aip_renewal_checker_member_a0v_162()',
    'public.aip_renewal_source_a0v_162(jsonb,text)',
    'public.aip_renewal_proposal_command_a0v_162(jsonb)',
    'public.aip_renewal_propose_a0v_162(jsonb)',
    'public.aip_renewal_reconcile_a0v_162(jsonb,text,text)',
    'public.aip_renewal_issuer_command_a0v_162(jsonb,text)',
    'public.aip_renewal_issuer_fact_a0v_162(jsonb,text,boolean)',
    'public.aip_renewal_issuer_write_a0v_162(jsonb,text,text)',
    'public.aip_renewal_decide_a0v_162(jsonb,text)',
    'public.aip_renewal_revoke_a0v_162(jsonb,text)',
    'public.aip_renewal_consume_command_a0v_162(jsonb)',
    'public.aip_renewal_consume_fact_a0v_162(jsonb,boolean)',
    'public.aip_renewal_consume_history_a0v_162(jsonb)',
    'public.aip_renewal_assert_insert_a0v_162(text,text,text,bigint,text,jsonb,text,timestamp with time zone,timestamp with time zone,timestamp with time zone)',
    'public.aip_renewal_complete_receipt_a0v_162()',
    'public.aip_renewal_consume_a0v_162(jsonb)',
    'public.aip_budget_cost_hash_a0v_126(jsonb)',
    'public.canonical_asset_registry_jsonb(jsonb)',
    'public.guard_aip4_append_only()',
    'public.aip_cost_configuration_write_guard_a0v_128()',
}
_SEALED_RELATIONS = {
    'aip_budget_policy_renewal_proposal', 'aip_budget_policy_renewal_decision',
    'aip_budget_policy_renewal_receipt', 'aip_model_governance_policy_head',
    'aip_model_governance_policy_revision', 'aip_budget_head', 'aip_budget_revision',
    'aip_provider_instance_head', 'aip_provider_instance_revision', 'meta_membership',
}


class RenewalAuthorityStore:
    def __init__(self, conn, *, checker_binding=None):
        self._conn = conn
        self._binding = checker_binding
        self._idle()

    def _idle(self):
        c = self._conn
        if (type(c) is not psycopg.Connection or c.closed or c.autocommit
                or c.info.transaction_status != TransactionStatus.IDLE
                or c.info.user not in _CALLERS.values()):
            raise RenewalStoreBlocked('RENEWAL_REAL_IDLE_DATABASE_CONNECTION_REQUIRED')

    def propose(self, command):
        return self._call(command, expected=RenewalProposalCommand)

    def decide(self, command, *, token):
        return self._call(command, expected=RenewalDecisionCommand, token=token)

    def revoke(self, command, *, token):
        return self._call(command, expected=RenewalRevocationCommand, token=token)

    def consume(self, command):
        return self._call(command, expected=RenewalConsumeCommand)

    def reconcile(self, original_command, *, token=None):
        return self._call(original_command, expected=type(original_command),
                          token=token, reconcile=True)

    def _verify_native_manifest(self, cur):
        # Independent catalog observation: do not execute the function whose
        # body/owner/ACL we are verifying, or grant callers table SELECT for it.
        row = cur.execute("SELECT obj_description('public.aip_budget_policy_renewal_proposal'"
                          "::regclass,'pg_class') AS seal").fetchone()
        try:
            value = json.loads(row['seal'])
            valid = (type(value) is dict and value.get('schema') == 'aos-renewal-schema-seal/v1'
                     and type(value.get('functions')) is list
                     and len(value['functions']) == len(_SEALED_FUNCTIONS)
                     and {v['signature'] for v in value['functions']} == _SEALED_FUNCTIONS
                     and type(value.get('relations')) is list
                     and len(value['relations']) == len(_SEALED_RELATIONS)
                     and {v['name'] for v in value['relations']} == _SEALED_RELATIONS)
        except (ValueError, TypeError, KeyError):
            valid = False
        if not valid:
            raise RenewalStoreBlocked('RENEWAL_SCHEMA_SEAL_REQUIRED')
        for expected in value['functions']:
            current = cur.execute("""SELECT jsonb_build_object('signature',%s::text,
                'owner',pg_get_userbyid(proowner),'definer',prosecdef,'config',to_jsonb(proconfig),
                'acl',proacl::text,'definition',pg_get_functiondef(oid)) AS metadata
                FROM pg_proc WHERE oid=%s::regprocedure""",
                (expected['signature'], expected['signature'])).fetchone()
            if not current:
                raise RenewalStoreBlocked('RENEWAL_SCHEMA_SEAL_DRIFT')
            metadata = current['metadata']
            metadata['bodySha256'] = hashlib.sha256(metadata.pop('definition').encode()).hexdigest()
            if metadata != expected:
                raise RenewalStoreBlocked('RENEWAL_SCHEMA_SEAL_DRIFT')
        for expected in value['relations']:
            current = cur.execute("""SELECT jsonb_build_object('name',c.relname,
                'owner',pg_get_userbyid(c.relowner),'rls',c.relrowsecurity,
                'forceRls',c.relforcerowsecurity,'acl',c.relacl::text,
                'columns',(SELECT jsonb_agg(jsonb_build_object('name',a.attname,'acl',a.attacl::text)
                  ORDER BY a.attnum) FROM pg_attribute a WHERE a.attrelid=c.oid
                    AND a.attnum>0 AND NOT a.attisdropped),
                'policies',COALESCE((SELECT jsonb_agg(jsonb_build_object('name',p.polname,
                  'permissive',p.polpermissive,'roles',to_jsonb(p.polroles),'command',p.polcmd,
                  'using',pg_get_expr(p.polqual,p.polrelid),'check',pg_get_expr(p.polwithcheck,p.polrelid))
                  ORDER BY p.polname) FROM pg_policy p WHERE p.polrelid=c.oid),'[]'::jsonb)) AS metadata
                FROM pg_class c WHERE c.oid=%s::regclass AND c.relnamespace='public'::regnamespace""",
                ('public.' + expected['name'],)).fetchone()
            if not current or current['metadata'] != expected:
                raise RenewalStoreBlocked('RENEWAL_SCHEMA_SEAL_DRIFT')

    def _call(self, command, *, expected, token=None, reconcile=False):
        self._idle()
        if expected not in _ENTRIES or type(command) is not expected:
            raise RenewalStoreBlocked('RENEWAL_EXACT_PUBLIC_COMMAND_REQUIRED')
        payload, digest = command.canonical_payload(), command.request_hash
        operation, purpose = _ENTRIES[expected]
        # Native protocol identity is checked before changing transaction mode;
        # the original management/API login cannot become a renewal writer.
        if self._conn.info.user != _CALLERS[purpose]:
            raise RenewalStoreBlocked('RENEWAL_OPERATION_LOGIN_REQUIRED')
        try:
            with self._conn.transaction():
                with self._conn.cursor(row_factory=dict_row) as cur:
                    cur.execute('SET TRANSACTION ISOLATION LEVEL READ COMMITTED, ' +
                                ('READ ONLY' if reconcile else 'READ WRITE'))
                    cur.execute("SELECT set_config('aos.org_id','org-org',true),"
                                "set_config('aos.project_id','dev-project',true),"
                                "set_config('statement_timeout','5000',true),"
                                "set_config('lock_timeout','1000',true)")
                    _database_identity(self._conn, purpose)
                    self._verify_native_manifest(cur)
                    actor = None
                    if purpose == 'issuer':
                        if type(token) is not SecretStr or type(self._binding) is not CheckerBinding:
                            raise RenewalStoreBlocked('RENEWAL_PROTECTED_HUMAN_GATEWAY_REQUIRED')
                        actor = authenticate_checker(token, binding=self._binding,
                                                     conn=self._conn).subject
                    if reconcile:
                        row = cur.execute(
                            'SELECT public.aip_renewal_reconcile_a0v_162(%s,%s,%s) AS result',
                            (Jsonb(payload), operation, actor)).fetchone()
                    elif purpose == 'issuer':
                        # Operation comes only from the exact type whitelist.
                        name = {'decide': 'aip_renewal_decide_a0v_162',
                                'revoke': 'aip_renewal_revoke_a0v_162'}[operation]
                        row = cur.execute('SELECT public.' + name + '(%s,%s) AS result',
                                          (Jsonb(payload), actor)).fetchone()
                    else:
                        name = {'propose': 'aip_renewal_propose_a0v_162',
                                'consume': 'aip_renewal_consume_a0v_162'}[operation]
                        row = cur.execute('SELECT public.' + name + '(%s) AS result',
                                          (Jsonb(payload),)).fetchone()
                    result = row['result'] if row else None
                    if (type(result) is not dict or result.get('activationEligible') is not False
                            or result.get('status') not in
                            ({'observed', 'unresolved', 'conflict'} if reconcile else
                             {dict(propose='prepared', decide='decided',
                                   revoke='revoked', consume='observed')[operation]})
                            or result.get('operation') != operation
                            or result.get('requestHash') != digest):
                        raise RenewalStoreBlocked('RENEWAL_NATIVE_RESULT_CONTRACT_REQUIRED')
                    if operation == 'propose' and result['status'] in {'prepared', 'observed'}:
                        self._validate_proposal(result, command)
                    if operation == 'consume' and result['status']=='observed':
                        self._validate_published_policy(result)
            # The outer transaction completed, including deferred native checks.
            return result
        except (RenewalStoreBlocked, RenewalIdentityBlocked):
            raise
        except psycopg.Error as error:
            known_rollback = (error.sqlstate is not None
                              and not error.sqlstate.startswith(('08', '57P'))
                              and not self._conn.closed
                              and self._conn.info.transaction_status == TransactionStatus.IDLE)
            if known_rollback:
                raise RenewalStoreBlocked('RENEWAL_NATIVE_TRANSACTION_REJECTED:' + error.sqlstate) from None
            raise RenewalStoreUnknown(operation=operation, key=command.idempotency_key,
                                      request_hash=digest) from None

    @staticmethod
    def _validate_proposal(result, command):
        # Reuse original typed contracts/hash before committing a prepared draft.
        from aos_api.aip_budget_policy_renewal_proposal import BudgetPolicyRenewalProposal
        from aos_api.aip_budget_contracts import BudgetRevision
        from aos_api.aip_model_runtime_contracts import ProviderInstanceRevision
        from aos_api.aip_model_governance_policy_store import canonical_hash
        from pydantic import ValidationError
        try:
            p = result['proposal']
            contract = BudgetPolicyRenewalProposal.model_validate(p['contract'])
            body = contract.canonical_payload()
            if (p['contract'] != body or p['contractHash'] != contract.proposal_hash
                    or canonical_hash(p) != result['proposalHash']
                    or p['request'] != command.canonical_payload()
                    or p['sourcePolicy'] != body['sourcePolicy']
                    or p['targetDraft'] != body['targetPolicy']
                    or result['targetDraft'] != body['targetPolicy']
                    or p['targetActive'] != {**body['targetPolicy'], 'lifecycle': 'active'}
                    or result['targetActiveHash'] != canonical_hash(p['targetActive'])):
                raise ValueError('prepared contract mismatch')
            for key, model, omit, ref in (
                ('sourceBudget', BudgetRevision,
                 {'tenant','contentHash','createdBy','createdAt'}, contract.source_policy.budget_revision_ref),
                ('sourceProvider', ProviderInstanceRevision,
                 {'tenant','revision','contentHash','createdBy','createdAt'},
                 contract.source_policy.development_cost_authorization.provider),
            ):
                value = model.model_validate(p[key])
                raw = value.model_dump(mode='json', by_alias=True)
                identifier = value.budget_id if key == 'sourceBudget' else value.provider_instance_id
                if (identifier != ref.asset_id or value.revision != ref.revision
                        or value.content_hash != ref.content_hash
                        or canonical_hash({k:v for k,v in raw.items() if k not in omit}) != ref.content_hash
                        or value.tenant != contract.tenant):
                    raise ValueError('prepared dependency snapshot mismatch')
        except (KeyError, ValueError, TypeError, ValidationError):
            raise RenewalStoreBlocked('RENEWAL_TYPED_PREPARED_SNAPSHOT_REQUIRED') from None

    @staticmethod
    def _validate_published_policy(result):
        from aos_api.aip_model_governance_policy_contracts import BudgetPolicyRevision
        from aos_api.aip_model_governance_policy_store import canonical_hash
        from pydantic import ValidationError
        try:
            value=BudgetPolicyRevision.model_validate(result['policy'])
            raw=value.model_dump(mode='json',by_alias=True)
            body={k:v for k,v in raw.items() if k not in {'tenant','contentHash','createdBy','createdAt'}}
            if (value.lifecycle.value!='active' or value.tenant.org_id!='org-org'
                    or value.tenant.project_id!='dev-project'
                    or value.created_by!='postgres-service:aos_budget_renewal_consumer_call'
                    or value.content_hash!=canonical_hash(body)
                    or result['ref']!={'assetType':'BudgetPolicyRevision','assetId':value.policy_id,
                                      'revision':value.revision,'contentHash':value.content_hash}):
                raise ValueError('canonical publication mismatch')
        except (KeyError,ValueError,TypeError,ValidationError):
            raise RenewalStoreBlocked('RENEWAL_TYPED_CANONICAL_PUBLICATION_REQUIRED') from None
