"""Default-off Skill producer transaction composition, never effect admission.

Returned dispatch metadata does not authorize a Provider call. The original
Owner, Source, signature, budget and approval gates remain separate. Mutations
are never retried; a failed commit or close requires read-only reconciliation.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import re
from typing import Literal

from psycopg.pq import TransactionStatus
from psycopg.rows import dict_row

from aos_api.aip_eval_execution_authority import EvalExecutionRejected
from aos_api.aip_eval_authority_store import AipEvalAuthorityStore
from aos_api.aip_eval_contracts import EvalRunEvent, EvalRunStatus
from aos_api.aip_eval_writer_reconcile import reconcile_signed_skill_eval_intent
from aos_api.aip_signed_skill_eval_intent_store import SignedSkillEvalIntentStore, SkillEvalIntentConflict
from aos_api.aip_skill_eval_atomic_finisher import finish_signed_skill_eval_with_connection, _bounded_finisher
from aos_api.aip_skill_eval_producer_connection import configured_skill_producer_connection
from aos_api.aip_skill_eval_producer_identity import require_skill_producer_identity
from aos_api.db import connect_read_only
from aos_api.tenant_scope import TenantScope


def _identifier(value):
    if (type(value) is not str or not 1 <= len(value) <= 200
            or value != value.strip() or not value.isprintable()
            or any(ch.isspace() for ch in value)):
        raise ValueError('exact Skill producer identifier required')


def _hash(value):
    if type(value) is not str or re.fullmatch('[0-9a-f]{64}', value) is None:
        raise ValueError('original canonical Skill hash required')


def _version(value):
    if type(value) is not int or value < 1:
        raise ValueError('positive exact version required')


def _scope(value):
    if type(value) is not TenantScope:
        raise TypeError('exact tenant scope required')
    TenantScope(value.org_id, value.project_id)


class SkillProducerOutcomeUnknown(RuntimeError):
    """No returned mutation result is durable; never automatically retry."""


@dataclass(frozen=True)
class SkillDispatchRequest:
    intent_id: str
    run_id: str
    request_hash: str
    expected_intent_version: int
    case_id: str
    purpose: Literal['target', 'judge']
    input_hash: str

    def __post_init__(self):
        for value in (self.intent_id, self.run_id, self.case_id):
            _identifier(value)
        _hash(self.request_hash)
        _hash(self.input_hash)
        _version(self.expected_intent_version)
        if self.purpose not in ('target', 'judge'):
            raise ValueError('original target or judge purpose required')


@dataclass(frozen=True)
class SkillDispatchRecord:
    state: Literal['COMMITTED', 'RECORDED', 'UNKNOWN']
    dispatch_id: str | None = None
    intent_version: int | None = None
    claim_committed: bool = False
    observations: tuple = ()


def _request(value):
    if type(value) is not SkillDispatchRequest:
        raise TypeError('exact Skill dispatch request required')
    value.__post_init__()


def _bound_intent(store, conn, scope, request, *, missing_ok=False):
    intent = store.get(conn, scope, request.intent_id)
    if intent is None and missing_ok:
        return None
    if (intent is None or intent['run_id'] != request.run_id
            or intent['request_hash'] != request.request_hash):
        raise ValueError('original Skill intent binding differs')
    _version(intent['version'])
    return intent


def _dispatch(conn, scope, request):
    row = conn.execute('''SELECT dispatch_id,case_id,purpose,input_hash
        FROM aip_skill_eval_dispatch WHERE org_id=%s AND project_id=%s
        AND intent_id=%s AND case_id=%s AND purpose=%s''',
        (*scope.key, request.intent_id, request.case_id, request.purpose)).fetchone()
    if row is not None:
        _identifier(row['dispatch_id'])
        if (row['case_id'], row['purpose'], row['input_hash']) != (
                request.case_id, request.purpose, request.input_hash):
            raise ValueError('original Skill dispatch binding differs')
    return row


def _readonly(conn, scope, expected_database):
    row = conn.execute('''SELECT current_user AS role,current_database() AS database_name,
        current_setting('aos.org_id',true) AS org_id,
        current_setting('aos.project_id',true) AS project_id,
        current_setting('transaction_isolation') AS isolation,
        current_setting('transaction_read_only') AS readonly''').fetchone()
    if (row is None or row['role'] != 'aos_runtime' or row['database_name'] != expected_database
            or (row['org_id'], row['project_id']) != scope.key
            or row['isolation'] not in ('repeatable read', 'serializable')
            or row['readonly'] != 'on'):
        raise ValueError('scoped Skill read-only snapshot required')


class SkillEvalProducerTransactions:
    def __init__(self, *, expected_database: str):
        _identifier(expected_database)
        self.expected_database = expected_database

    @contextmanager
    def _write(self, scope, *, writer=True):
        _scope(scope)
        connector = configured_skill_producer_connection()
        if connector is None:
            raise RuntimeError('independent Skill producer identity is unavailable')
        try:
            with connector(expected_database=self.expected_database) as conn:
                if (conn.autocommit is not False or conn.row_factory is not dict_row
                        or conn.info.transaction_status != TransactionStatus.IDLE):
                    raise ValueError('idle caller-owned producer connection required')
                with conn.transaction():
                    conn.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
                    require_skill_producer_identity(conn, expected_database=self.expected_database)
                    conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)", scope.key)
                    if writer:
                        conn.execute('SET LOCAL ROLE aos_aip_eval_writer')
                    yield conn
        except (ValueError, TypeError, SkillEvalIntentConflict, EvalExecutionRejected):
            raise
        except Exception:
            raise SkillProducerOutcomeUnknown('Skill mutation outcome unknown; read-only reconciliation required') from None

    def create_intent(self, scope, *, run_id, idempotency_key, request_hash):
        _identifier(run_id)
        _identifier(idempotency_key)
        _hash(request_hash)
        with self._write(scope) as conn:
            result = dict(SignedSkillEvalIntentStore().create(conn, scope, run_id=run_id,
                idempotency_key=idempotency_key, request_hash=request_hash))
        return result

    @staticmethod
    def _start_context(scope, intent_id, request_hash, expected_intent_version, event):
        _scope(scope)
        _identifier(intent_id)
        _hash(request_hash)
        _version(expected_intent_version)
        if (expected_intent_version != 1 or type(event) is not EvalRunEvent
                or (event.tenant.org_id, event.tenant.project_id) != scope.key
                or event.sequence != 2 or event.event_type != 'status_changed'
                or event.from_status is not EvalRunStatus.QUEUED
                or event.to_status is not EvalRunStatus.RUNNING
                or event.payload_hash != hashlib.sha256(
                    b'{"from":"queued","to":"running"}').hexdigest()
                or event.created_at.utcoffset() is None):
            raise ValueError('exact new Skill start event required')

    def start_run(self, scope, *, intent_id, request_hash, expected_intent_version, event):
        """Commit original queued-to-running metadata, never effect admission."""
        self._start_context(scope, intent_id, request_hash, expected_intent_version, event)
        with self._write(scope, writer=False) as conn:
            _bounded_finisher(conn)
            conn.execute('SET LOCAL ROLE aos_aip_eval_writer')
            intent = SignedSkillEvalIntentStore().get(conn, scope, intent_id)
            if (intent is None or intent['run_id'] != event.run_id
                    or intent['request_hash'] != request_hash
                    or intent['version'] != expected_intent_version):
                raise ValueError('original new Skill start intent differs')
            context = conn.execute(
                'SELECT session_user AS login,clock_timestamp() AS checked_at').fetchone()
            conn.execute('SET LOCAL ROLE aos_skill_eval_finisher')
            authority = AipEvalAuthorityStore()
            row = authority._run_row(conn, scope, event.run_id, for_update=True)
            if (row is None or row['target_ref'].get('assetType') != 'skill_template'
                    or row['version'] != 1 or row['status'] != 'queued'
                    or event.actor != context['login']
                    or not row['created_at'] <= event.created_at <= context['checked_at']):
                raise ValueError('original queued Skill Run or start actor/clock differs')
            result = authority._transition_eval_run_with_connection(
                conn, scope, event, expected_version=1)
        return result

    def reconcile_start_run(self, scope, *, intent_id, request_hash,
                            expected_intent_version, event):
        """Read exact original start evidence; absence never authorizes resend."""
        self._start_context(scope, intent_id, request_hash, expected_intent_version, event)
        with connect_read_only(scope=scope, inherit_scope=False) as conn:
            _readonly(conn, scope, self.expected_database)
            intent = SignedSkillEvalIntentStore().get(conn, scope, intent_id)
            if intent is None:
                return None
            if (intent['run_id'] != event.run_id or intent['request_hash'] != request_hash
                    or type(intent['version']) is not int or intent['version'] < expected_intent_version):
                raise ValueError('original Skill start reconciliation intent differs')
            authority = AipEvalAuthorityStore()
            stored = authority._run_event_by_sequence(conn, scope, event.run_id, 2)
            if stored is None:
                return None
            if stored != event:
                raise ValueError('original Skill start event differs')
            row = authority._run_row(conn, scope, event.run_id)
            if (row is None or row['target_ref'].get('assetType') != 'skill_template'
                    or row['version'] < 2 or row['status'] == 'queued'
                    or row['started_at'] != event.created_at):
                raise ValueError('original Skill start Run differs')
            return authority._run_from_row(row)

    def claim_dispatch(self, scope, request):
        _request(request)
        with self._write(scope) as conn:
            store = SignedSkillEvalIntentStore()
            _bound_intent(store, conn, scope, request)
            identity = store.claim(conn, scope, intent_id=request.intent_id,
                expected_version=request.expected_intent_version, case_id=request.case_id,
                purpose=request.purpose, input_hash=request.input_hash)
            claimed = identity is not None
            if not claimed:
                row = _dispatch(conn, scope, request)
                if row is None:
                    raise ValueError('recorded Skill dispatch unavailable')
                identity = row['dispatch_id']
            _identifier(identity)
            current = _bound_intent(store, conn, scope, request)
            record = SkillDispatchRecord('COMMITTED' if claimed else 'RECORDED', identity,
                                         current['version'], claimed)
        return record

    def observe_dispatch(self, scope, request, *, dispatch_id, state, result_hash):
        _request(request)
        _identifier(dispatch_id)
        if state not in ('unknown', 'result_observed'):
            raise ValueError('original Skill observation state required')
        if state == 'unknown':
            if result_hash is not None:
                raise ValueError('unknown observation cannot claim a result')
        else:
            _hash(result_hash)
        with self._write(scope) as conn:
            store = SignedSkillEvalIntentStore()
            _bound_intent(store, conn, scope, request)
            row = _dispatch(conn, scope, request)
            if row is None or row['dispatch_id'] != dispatch_id:
                raise ValueError('observation belongs to another dispatch')
            store.observe(conn, scope, dispatch_id=dispatch_id, state=state, result_hash=result_hash)

    def finish(self, scope, **arguments):
        self._finish_context(scope, arguments)
        with self._write(scope, writer=False) as conn:
            proof = finish_signed_skill_eval_with_connection(conn,
                expected_database=self.expected_database, scope=scope, **arguments)
        return proof

    @staticmethod
    def _finish_context(scope, arguments):
        _scope(scope)
        _identifier(arguments['intent_id'])
        _hash(arguments['request_hash'])
        _version(arguments['expected_intent_version'])
        _version(arguments['expected_run_version'])
        for item in (arguments['report'], arguments['event']):
            if (item.tenant.org_id, item.tenant.project_id) != scope.key:
                raise ValueError('Skill ending tenant differs')

    def reconcile_dispatch(self, scope, request):
        _scope(scope)
        _request(request)
        with connect_read_only(scope=scope, inherit_scope=False) as conn:
            _readonly(conn, scope, self.expected_database)
            store = SignedSkillEvalIntentStore()
            intent = _bound_intent(store, conn, scope, request, missing_ok=True)
            if intent is None:
                return SkillDispatchRecord('UNKNOWN')
            row = _dispatch(conn, scope, request)
            if row is None:
                return SkillDispatchRecord('UNKNOWN', intent_version=intent['version'])
            observations = tuple(dict(x) for x in store.observations(conn, scope, row['dispatch_id']))
            return SkillDispatchRecord('RECORDED', row['dispatch_id'], intent['version'], False, observations)

    def reconcile_finish(self, scope, **arguments):
        """Accept the same PRE-finish versions; query their exact +1 results."""
        self._finish_context(scope, arguments)
        with connect_read_only(scope=scope, inherit_scope=False) as conn:
            _readonly(conn, scope, self.expected_database)
            return reconcile_signed_skill_eval_intent(conn, report=arguments['report'],
                expected_input_hashes=arguments['expected_input_hashes'], presented=arguments['presented'],
                intent_id=arguments['intent_id'], expected_request_hash=arguments['request_hash'],
                expected_intent_version=arguments['expected_intent_version'] + 1,
                expected_run_version=arguments['expected_run_version'] + 1)
