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
