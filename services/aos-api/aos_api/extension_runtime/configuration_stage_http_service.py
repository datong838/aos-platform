"""Fixed SQL transport, returning success only after the restricted transaction commits."""
import json
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from psycopg.types.json import Jsonb

from aos_api.asset_registry.control_policy import validate_idempotency_key
from .configuration_contracts import ConfigurationRef
from .configuration_stage_contracts import ConfigurationStageRequest
from .configuration_stage_connection import configuration_stage_connection
from .lifecycle_store import _values


class StageReceipt(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid', hide_input_in_errors=True)
    requestId: str
    requestHash: str = Field(pattern=r'^sha256:[0-9a-f]{64}$')
    state: Literal['requested','succeeded','rejected','expired']
    revision: int = Field(ge=1, le=2**63-1)
    deadline: datetime

    @field_validator('requestId')
    @classmethod
    def canonical_request_id(cls, value):
        if str(UUID(value)) != value: raise ValueError('canonical request identity required')
        return value

    @field_validator('deadline')
    @classmethod
    def aware_deadline(cls, value):
        if value.utcoffset() is None: raise ValueError('deadline timezone required')
        return value


class StageStatus(StageReceipt):
    result: ConfigurationRef | None
    failureCode: str | None = Field(pattern=r'^[A-Z][A-Z0-9_]{0,79}$')

    @model_validator(mode='after')
    def state_shape(self):
        if ((self.state == 'succeeded') != (self.result is not None)
                or (self.state in {'rejected','expired'}) != (self.failureCode is not None)):
            raise ValueError('configuration receipt state differs')
        return self


class ConfigurationStageHttpService:
    def __init__(self, *, connect=configuration_stage_connection):
        if not callable(connect): raise TypeError('trusted configuration connection required')
        self.connect = connect

    def enqueue(self, *, scope, subject, idempotency_key, request):
        key = validate_idempotency_key(idempotency_key)
        request = ConfigurationStageRequest.model_validate(request)
        with self.connect(scope=scope, subject=subject) as conn:
            row = conn.execute('SELECT public.extension_configuration_stage_enqueue_a0v_037(%s,%s,%s) AS receipt',
                (subject, key, Jsonb(request.model_dump(mode='json')))).fetchone()
            value = StageReceipt.model_validate_json(json.dumps(_values(row, ('receipt',))[0]))
        return self._response(scope, value)

    def get(self, *, scope, subject, request_id):
        identity = UUID(str(request_id))
        with self.connect(scope=scope, subject=subject) as conn:
            row = conn.execute('SELECT public.extension_configuration_stage_query_a0v_037(%s,%s::uuid) AS receipt',
                (subject, identity)).fetchone()
            result = _values(row, ('receipt',))[0]
            if result is None: raise LookupError('configuration request unavailable')
            value = StageStatus.model_validate_json(json.dumps(result))
            if UUID(value.requestId) != identity: raise ValueError('configuration receipt identity differs')
        return self._response(scope, value)

    @staticmethod
    def _response(scope, value):
        return dict(schemaVersion='aos.runtime-configuration-stage-status/v1',
                    tenant=dict(orgId=scope.org_id, projectId=scope.project_id),
                    **value.model_dump(mode='json'))
