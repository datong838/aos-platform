"""Transaction-bound immutable execution evidence, never a Provider dispatcher."""
from datetime import datetime
import hashlib
import json
import re
from copy import deepcopy

from psycopg import sql


class ContentExecutionConflict(RuntimeError):
    pass


def _json_datetime(value):
    if isinstance(value, datetime) and value.utcoffset() is not None:
        return value.isoformat()
    raise TypeError('journal values must be JSON or timezone-aware datetime')


def _payload(value):
    if type(value) is not dict:
        raise ValueError('journal payload must be an object')
    text = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False, default=_json_datetime)
    return text, hashlib.sha256(text.encode()).hexdigest()


class ContentExecutionJournal:
    def __init__(self, *, storage_schema='public'):
        if not re.fullmatch(r'[a-z_][a-z0-9_]*', storage_schema):
            raise ValueError('invalid storage schema')
        self.schema = storage_schema

    def _table(self, name):
        return sql.Identifier(self.schema, name)

    def list_held(self, conn, scope, *, limit=32):
        """List only v2 pending intents; run_one still owns the submit lock."""
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('content selector limit is invalid')
        rows = conn.execute(sql.SQL('''SELECT c.reservation_id,c.command_payload,c.command_hash,
                   c.budget_request_hash,b.request_hash AS reservation_request_hash,
                   r.request_hash AS runtime_request_hash,r.response
              FROM {} c
              JOIN {} b USING(org_id,project_id,reservation_id)
              JOIN {} r ON r.org_id=c.org_id AND r.project_id=c.project_id
                  AND r.operation_id='ecommerce_growth_content_generate'
                  AND r.idempotency_key=c.command_payload->>'idempotencyKey'
              LEFT JOIN {} result ON result.org_id=c.org_id
                  AND result.project_id=c.project_id
                  AND result.reservation_id=c.reservation_id
             WHERE c.org_id=%s AND c.project_id=%s AND b.state='held'
               AND r.response->>'state'='PENDING' AND result.reservation_id IS NULL
             ORDER BY c.created_at,c.reservation_id LIMIT %s''').format(
                 self._table('ecommerce_content_execution_command'),
                 self._table('aip_budget_reservation'),
                 self._table('ecommerce_growth_runtime_command_receipt'),
                 self._table('ecommerce_content_execution_result')),
             (*scope.key, limit)).fetchall()
        from aos_api.aip_budget_reservation_store import AipBudgetReservationStore
        from aos_api.ecommerce_growth_host_ports import HostTransaction
        from aos_api.ecommerce_growth_runtime_adapters import (
            ContentGenerateHostService, TransactionBoundConnectFactory,
        )
        budget = AipBudgetReservationStore(
            TransactionBoundConnectFactory(HostTransaction(conn), scope),
            authority_schema=self.schema,
        )
        selected = []
        for row in rows:
            command = row['command_payload']
            response = row['response']
            if (
                _payload(command)[1] != row['command_hash']
                or ContentGenerateHostService._budget_request(command).request_hash()
                != row['budget_request_hash']
                or row['reservation_request_hash'] != row['budget_request_hash']
                or type(response) is not dict
                or response.get('requestHash') != command['requestHash']
                or row['runtime_request_hash'] != command['requestHash']
                or type(response.get('replayed')) is not bool
                or response != ContentGenerateHostService._pending_receipt(
                    command,
                    budget.get(scope, str(row['reservation_id'])),
                    ContentGenerateHostService._budget_request(command),
                    replayed=response['replayed'],
                )
            ):
                raise ContentExecutionConflict('content pending runtime Receipt drifted')
            selected.append(str(row['reservation_id']))
        return selected

    def list_recorded(self, conn, scope, *, limit=32):
        """Find immutable results needing accounting, with no send path."""
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('content result selector limit is invalid')
        rows=conn.execute(sql.SQL('''SELECT r.reservation_id,r.result_payload,r.result_hash,
                   r.provider_request_ref,b.provider_request_receipt_ref,
                   b.request_hash AS reservation_request_hash,
                   c.command_payload,c.command_hash,c.budget_request_hash
              FROM {} r
              JOIN {} b USING(org_id,project_id,reservation_id)
              JOIN {} c USING(org_id,project_id,reservation_id)
             WHERE r.org_id=%s AND r.project_id=%s
               AND b.state IN ('submitted','unknown')
             ORDER BY r.recorded_at,r.reservation_id LIMIT %s''').format(
                 self._table('ecommerce_content_execution_result'),
                 self._table('aip_budget_reservation'),
                 self._table('ecommerce_content_execution_command')),
            (*scope.key,limit)).fetchall()
        from aos_api.ecommerce_growth_runtime_adapters import ContentGenerateHostService
        selected=[]
        for row in rows:
            if (_payload(row['result_payload'])[1]!=row['result_hash']
                or _payload(row['command_payload'])[1]!=row['command_hash']
                or ContentGenerateHostService._budget_request(row['command_payload']).request_hash()
                    !=row['budget_request_hash']
                or row['reservation_request_hash']!=row['budget_request_hash']
                or row['provider_request_ref']!=row['provider_request_receipt_ref']):
                raise ContentExecutionConflict('recorded content result drifted')
            selected.append(str(row['reservation_id']))
        return selected

    def _reservation(self, conn, scope, reservation_id):
        row = conn.execute(sql.SQL('SELECT * FROM {} WHERE org_id=%s AND project_id=%s AND reservation_id=%s FOR UPDATE').format(
            self._table('aip_budget_reservation')), (*scope.key, reservation_id)).fetchone()
        if row is None or row['operation_id'] != 'ecommerce_growth_content_generate':
            raise ContentExecutionConflict('content reservation unavailable')
        return row

    def enqueue(self, conn, scope, reservation_id, *, budget_request_hash, command):
        text, digest = _payload(command)
        command = json.loads(text)
        reservation = self._reservation(conn, scope, reservation_id)
        row = conn.execute(sql.SQL('SELECT * FROM {} WHERE org_id=%s AND project_id=%s AND reservation_id=%s').format(
            self._table('ecommerce_content_execution_command')), (*scope.key, reservation_id)).fetchone()
        if row is not None:
            if row['command_hash'] != digest or row['command_payload'] != command or row['budget_request_hash'] != budget_request_hash:
                raise ContentExecutionConflict('content command replay drifted')
            return deepcopy(row['command_payload'])
        if reservation['state'] != 'held' or reservation['request_hash'] != budget_request_hash:
            raise ContentExecutionConflict('held exact content reservation required')
        conn.execute(sql.SQL('INSERT INTO {}(org_id,project_id,reservation_id,budget_request_hash,command_hash,command_payload) VALUES(%s,%s,%s,%s,%s,%s::jsonb)').format(
            self._table('ecommerce_content_execution_command')), (*scope.key, reservation_id, budget_request_hash, digest, text))
        return deepcopy(command)

    def record_result(self, conn, scope, reservation_id, *, provider_request_ref, result):
        text, digest = _payload(result)
        result = json.loads(text)
        request_text, _ = _payload(provider_request_ref)
        reservation = self._reservation(conn, scope, reservation_id)
        row = conn.execute(sql.SQL('SELECT * FROM {} WHERE org_id=%s AND project_id=%s AND reservation_id=%s').format(
            self._table('ecommerce_content_execution_result')), (*scope.key, reservation_id)).fetchone()
        if row is not None:
            if row['result_hash'] != digest or row['result_payload'] != result or row['provider_request_ref'] != provider_request_ref:
                raise ContentExecutionConflict('content result replay drifted')
            return deepcopy(row['result_payload'])
        if reservation['state'] not in {'submitted','unknown'} or reservation['provider_request_receipt_ref'] != provider_request_ref:
            raise ContentExecutionConflict('submitted exact provider request required')
        conn.execute(sql.SQL('INSERT INTO {}(org_id,project_id,reservation_id,provider_request_ref,result_hash,result_payload) VALUES(%s,%s,%s,%s::jsonb,%s,%s::jsonb)').format(
            self._table('ecommerce_content_execution_result')), (*scope.key, reservation_id, request_text, digest, text))
        return deepcopy(result)

    def read(self, conn, scope, reservation_id):
        row = conn.execute(sql.SQL('''SELECT c.command_payload,c.command_hash,r.result_payload,r.result_hash
            FROM {} c LEFT JOIN {} r USING(org_id,project_id,reservation_id)
            WHERE c.org_id=%s AND c.project_id=%s AND c.reservation_id=%s''').format(
                self._table('ecommerce_content_execution_command'), self._table('ecommerce_content_execution_result')),
                (*scope.key, reservation_id)).fetchone()
        if row is None:
            return None
        if _payload(row['command_payload'])[1] != row['command_hash'] or (
            row['result_payload'] is not None and _payload(row['result_payload'])[1] != row['result_hash']
        ):
            raise ContentExecutionConflict('stored content execution evidence drifted')
        return {'command': deepcopy(row['command_payload']), 'result': deepcopy(row['result_payload'])}
