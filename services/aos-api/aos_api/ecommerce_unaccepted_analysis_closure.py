"""Restricted recovery service; closure is never a business acceptance Receipt."""
from contextlib import contextmanager
from typing import Literal
from uuid import UUID

from psycopg import IsolationLevel
from psycopg.pq import TransactionStatus
from psycopg.types.json import Jsonb
from pydantic import ConfigDict, Field, field_validator

from aos_api.aip_contracts import AipContractModel
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.extension_runtime.consumer_connection import consumer_connection
from aos_api.extension_runtime.storage_ports import require_runtime_role
from aos_api.tenant_scope import TenantScope


class UnacceptedAnalysisClosureRequest(AipContractModel):
    model_config = ConfigDict(strict=True, extra='forbid', frozen=True, hide_input_in_errors=True)
    schema_version: Literal['aos.ecommerce.unaccepted-analysis-closure/v1']
    occurrence_id: str
    fence_receipt_id: str
    fence_content_hash: str = Field(pattern=r'^sha256:[0-9a-f]{64}$')
    idempotency_key: str = Field(min_length=1, max_length=160)

    @field_validator('occurrence_id', 'fence_receipt_id')
    @classmethod
    def canonical_uuid(cls, value):
        if str(UUID(value)) != value:
            raise ValueError('canonical closure UUID required')
        return value

    @field_validator('idempotency_key')
    @classmethod
    def canonical_key(cls, value):
        if value != value.strip() or not value.isprintable():
            raise ValueError('canonical closure key required')
        return value


class UnacceptedAnalysisClosureService:
    def __init__(self, *, connect):
        if not callable(connect):
            raise TypeError('current recovery connection required')
        self._connect = connect

    @contextmanager
    def _transaction(self):
        with self._connect() as conn:
            if conn.info.transaction_status != TransactionStatus.IDLE:
                raise ValueError('idle recovery connection required')
            previous = conn.isolation_level
            conn.isolation_level = IsolationLevel.SERIALIZABLE
            try:
                yield conn
            finally:
                conn.isolation_level = previous

    def close(self, *, scope, request, actor):
        if type(scope) is not TenantScope or type(request) is not UnacceptedAnalysisClosureRequest:
            raise TypeError('exact trusted tenant and closure request required')
        request = UnacceptedAnalysisClosureRequest.model_validate(request.model_dump(by_alias=True))
        if type(actor) is not str or not actor or actor != actor.strip() or not actor.isprintable():
            raise ValueError('canonical current recovery actor required')
        wire = request.model_dump(mode='json', by_alias=True)
        with consumer_connection(self._transaction, dict(org_id=scope.org_id, project_id=scope.project_id)) as conn:
            require_runtime_role(conn, org_id=scope.org_id, project_id=scope.project_id,
                protected_tables=('public.ecommerce_unaccepted_analysis_closure_receipt',))
            conn.execute('SET LOCAL ROLE aos_extension_maintainer')
            response = conn.execute('SELECT public.ecommerce_unaccepted_analysis_close_a0v_060(%s,%s) AS receipt',
                                    (Jsonb(wire), actor)).fetchone()['receipt']
            conn.execute('SET LOCAL ROLE aos_runtime')
            row = conn.execute('''SELECT authority_data,content_hash,request_hash,actor
                FROM public.ecommerce_unaccepted_analysis_closure_receipt
                WHERE org_id=%s AND project_id=%s AND idempotency_key=%s''',
                (*scope.key, request.idempotency_key)).fetchone()
            if (row is None or row['actor'] != actor or row['request_hash'] != canonical_sha256(wire)
                    or row['content_hash'] != canonical_sha256(row['authority_data'])
                    or dict(row['authority_data'], contentHash=row['content_hash']) !=
                       {k:v for k,v in response.items() if k != 'replayed'}
                    or response['businessAccepted'] is not False):
                raise ValueError('closure receipt readback differs')
            return response


class UnacceptedScheduleAnalysisClosureRequest(AipContractModel):
    model_config = ConfigDict(strict=True, extra='forbid', frozen=True, hide_input_in_errors=True)
    schema_version: Literal['aos.ecommerce.unaccepted-schedule-analysis-closure/v1']
    occurrence_id: str
    schedule_control_receipt_id: str
    schedule_control_content_hash: str = Field(pattern=r'^sha256:[0-9a-f]{64}$')
    idempotency_key: str = Field(min_length=1, max_length=160)

    @field_validator('occurrence_id', 'schedule_control_receipt_id')
    @classmethod
    def canonical_uuid(cls, value):
        if str(UUID(value)) != value:
            raise ValueError('canonical schedule closure UUID required')
        return value

    @field_validator('idempotency_key')
    @classmethod
    def canonical_key(cls, value):
        if value != value.strip() or not value.isprintable():
            raise ValueError('canonical schedule closure key required')
        return value


class UnacceptedScheduleAnalysisClosureService(UnacceptedAnalysisClosureService):
    def close(self, *, scope, request, actor):
        if type(scope) is not TenantScope or type(request) is not UnacceptedScheduleAnalysisClosureRequest:
            raise TypeError('exact trusted tenant and schedule closure request required')
        request = UnacceptedScheduleAnalysisClosureRequest.model_validate(
            request.model_dump(by_alias=True)
        )
        if type(actor) is not str or not actor or actor != actor.strip() or not actor.isprintable():
            raise ValueError('canonical current recovery actor required')
        wire = request.model_dump(mode='json', by_alias=True)
        with consumer_connection(
            self._transaction, dict(org_id=scope.org_id, project_id=scope.project_id)
        ) as conn:
            require_runtime_role(
                conn, org_id=scope.org_id, project_id=scope.project_id,
                protected_tables=('public.ecommerce_unaccepted_analysis_closure_receipt',),
            )
            conn.execute('SET LOCAL ROLE aos_extension_maintainer')
            response = conn.execute(
                'SELECT public.ecommerce_unaccepted_schedule_analysis_close_a0v_082(%s,%s) AS receipt',
                (Jsonb(wire), actor),
            ).fetchone()['receipt']
            conn.execute('SET LOCAL ROLE aos_runtime')
            row = conn.execute('''SELECT authority_data,content_hash,request_hash,actor
                FROM public.ecommerce_unaccepted_analysis_closure_receipt
                WHERE org_id=%s AND project_id=%s AND idempotency_key=%s''',
                (*scope.key, request.idempotency_key),
            ).fetchone()
            if (
                row is None or row['actor'] != actor
                or row['request_hash'] != canonical_sha256(wire)
                or row['content_hash'] != canonical_sha256(row['authority_data'])
                or dict(row['authority_data'], contentHash=row['content_hash'])
                   != {key: value for key, value in response.items() if key != 'replayed'}
                or response['businessAccepted'] is not False
            ):
                raise ValueError('schedule closure receipt readback differs')
            return response
