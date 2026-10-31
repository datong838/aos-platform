"""Default-off immutable Route Eval command/result evidence, never a dispatcher."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import hashlib
import json
import re
from typing import Literal

from pydantic import Field,field_validator,model_validator

from aos_api.aip_budget_reservation_contracts import (
    BudgetExactRef,ReserveBudgetRequest,exact_ref_payload,
)
from aos_api.aip_budget_reservation_store import AipBudgetReservationStore
from aos_api.aip_contracts import AipContractModel,TenantContext
from aos_api.aip_model_route_eval_manifest import ROUTE_OPERATIONS
from aos_api.tenant_scope import TenantScope


SHA=r'^[0-9a-f]{64}$'
WIRE_LIMIT=1_048_576


class RouteEvalExecutionConflict(RuntimeError):
    """Safe fail-closed category for durable Route evidence."""


class RouteEvalExecutionCommand(AipContractModel):
    schema_version: Literal['aos.route-eval-execution-command/v1']='aos.route-eval-execution-command/v1'
    tenant: TenantContext
    execution_id: str=Field(min_length=1,max_length=200)
    manifest_hash: str=Field(pattern=SHA)
    context_binding_hash: str=Field(pattern=SHA)
    admission_hash: str=Field(pattern=SHA)
    call_key: str=Field(min_length=1,max_length=200)
    call_binding_hash: str=Field(pattern=SHA)
    case_id: str=Field(min_length=1,max_length=200)
    purpose: Literal['target','judge']
    target_call_key: str | None=Field(default=None,max_length=200)
    budget_request: ReserveBudgetRequest
    invocation_ref: BudgetExactRef
    reservation_ref: BudgetExactRef
    input_hash: str=Field(pattern=SHA)
    execution_allowed: Literal[False]=False

    @field_validator('execution_id','call_key','case_id','target_call_key')
    @classmethod
    def _identity(cls,value):
        if value is not None and value!=value.strip():
            raise ValueError('Route command identity must be canonical')
        return value

    @model_validator(mode='after')
    def _exact_call(self):
        request=self.budget_request
        if (request.operation_id!=ROUTE_OPERATIONS[self.purpose]
            or request.invocation_key!=self.call_key
            or self.invocation_ref.resource_type!='CapabilityInvocationRevision'
            or self.reservation_ref.resource_type!='BudgetReservationRevision'
            or self.invocation_ref.revision!=1 or self.reservation_ref.revision!=1
            or (self.purpose=='target' and self.target_call_key is not None)
            or (self.purpose=='judge' and
                (not self.target_call_key or self.target_call_key==self.call_key))):
            raise ValueError('exact Route command binding required')
        return self


class RouteEvalExecutionResult(AipContractModel):
    schema_version: Literal['aos.route-eval-execution-result/v1']='aos.route-eval-execution-result/v1'
    tenant: TenantContext
    execution_id: str=Field(min_length=1,max_length=200)
    call_key: str=Field(min_length=1,max_length=200)
    case_id: str=Field(min_length=1,max_length=200)
    purpose: Literal['target','judge']
    provider_request_ref: BudgetExactRef
    provider_result_id: str=Field(min_length=1,max_length=240)
    provider_id: str=Field(min_length=1,max_length=200)
    model_id: str=Field(min_length=1,max_length=240)
    output_hash: str=Field(pattern=SHA)
    prompt_tokens: int=Field(ge=0,le=9_007_199_254_740_991)
    completion_tokens: int=Field(ge=0,le=9_007_199_254_740_991)
    observed_at: datetime
    execution_allowed: Literal[False]=False

    @field_validator('execution_id','call_key','case_id','provider_result_id',
        'provider_id','model_id')
    @classmethod
    def _identity(cls,value):
        if value!=value.strip():raise ValueError('Route result identity must be canonical')
        return value

    @model_validator(mode='after')
    def _exact_result(self):
        if (self.provider_request_ref.resource_type!='CapabilityProviderRequestReceipt'
            or self.observed_at.utcoffset() is None):
            raise ValueError('exact Route Provider result required')
        return self


def _canonical(value) -> tuple[str,str]:
    payload=value.model_dump(mode='json',by_alias=True)
    text=json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=False,
        allow_nan=False)
    return text,hashlib.sha256(text.encode()).hexdigest()


def _load(model,value):
    if type(value) is str:value=json.loads(value)
    return model.model_validate(value)


class RouteEvalExecutionJournal:
    """Persist exact local evidence; caller owns transaction and external effects."""

    def __init__(self,*,storage_schema='public'):
        if re.fullmatch(r'[a-z_][a-z0-9_]*',storage_schema) is None:
            raise ValueError('invalid Route journal schema')
        self.schema=storage_schema

    def _reservation(self,conn,scope,reservation_id):
        row=conn.execute(f'''SELECT * FROM {self.schema}.aip_budget_reservation
            WHERE org_id=%s AND project_id=%s AND reservation_id=%s FOR UPDATE''',
            (*scope.key,reservation_id)).fetchone()
        if row is None:raise RouteEvalExecutionConflict('Route reservation unavailable')
        return row

    def _command_row(self,conn,scope,reservation_id):
        return conn.execute(f'''SELECT * FROM {self.schema}.aip_route_eval_execution_command
            WHERE org_id=%s AND project_id=%s AND reservation_id=%s''',
            (*scope.key,reservation_id)).fetchone()

    def _result_row(self,conn,scope,reservation_id):
        return conn.execute(f'''SELECT * FROM {self.schema}.aip_route_eval_execution_result
            WHERE org_id=%s AND project_id=%s AND reservation_id=%s''',
            (*scope.key,reservation_id)).fetchone()

    @staticmethod
    def _scope(scope,tenant):
        if (type(scope) is not TenantScope or scope.key!=('org-org','dev-project')
            or (tenant.org_id,tenant.project_id)!=scope.key):
            raise RouteEvalExecutionConflict('exact Route tenant scope required')

    def _read_command(self,row):
        try:
            command=_load(RouteEvalExecutionCommand,row['command_payload'])
            text,digest=_canonical(command);raw=bytes(row['input_bytes'])
            if (digest!=row['command_hash'] or json.loads(text)!=row['command_payload']
                or hashlib.sha256(raw).hexdigest()!=row['input_hash']
                or row['input_hash']!=command.input_hash
                or not 1<=len(raw)<=WIRE_LIMIT
                or (row['execution_id'],row['case_id'],row['purpose'],row['call_key'])
                   !=(command.execution_id,command.case_id,command.purpose,command.call_key)):
                raise ValueError
            return command,raw
        except (ValueError,TypeError,KeyError,AttributeError,json.JSONDecodeError):
            raise RouteEvalExecutionConflict('stored Route command drifted') from None

    def _read_result(self,row,command):
        try:
            result=_load(RouteEvalExecutionResult,row['result_payload'])
            text,digest=_canonical(result);raw=bytes(row['output_bytes'])
            if (digest!=row['result_hash'] or json.loads(text)!=row['result_payload']
                or hashlib.sha256(raw).hexdigest()!=row['output_hash']
                or row['output_hash']!=result.output_hash or len(raw)>WIRE_LIMIT
                or (result.tenant,result.execution_id,result.call_key,result.case_id,result.purpose)
                   !=(command.tenant,command.execution_id,command.call_key,
                      command.case_id,command.purpose)):
                raise ValueError
            return result,raw
        except (ValueError,TypeError,KeyError,AttributeError,json.JSONDecodeError):
            raise RouteEvalExecutionConflict('stored Route result drifted') from None

    def enqueue(self,conn,scope,reservation_id,*,command,input_bytes):
        if type(command) is not RouteEvalExecutionCommand or type(input_bytes) is not bytes:
            raise RouteEvalExecutionConflict('original Route command and bytes required')
        self._scope(scope,command.tenant)
        if (not 1<=len(input_bytes)<=WIRE_LIMIT
            or hashlib.sha256(input_bytes).hexdigest()!=command.input_hash):
            raise RouteEvalExecutionConflict('exact bounded Route input bytes required')
        row=self._reservation(conn,scope,reservation_id);request=command.budget_request
        invocation,reservation=AipBudgetReservationStore.initial_hold_refs(request,
            invocation_id=row['invocation_id'],reservation_id=row['reservation_id'])
        try:approval=BudgetExactRef.model_validate(row['approval_ref'])
        except (ValueError,TypeError):
            raise RouteEvalExecutionConflict('Route reservation approval drifted') from None
        if (row['state']!='held' or row['operation_id']!=request.operation_id
            or row['invocation_key']!=request.invocation_key
            or row['request_hash']!=request.request_hash()
            or approval!=request.approval_ref
            or invocation!=command.invocation_ref or reservation!=command.reservation_ref):
            raise RouteEvalExecutionConflict('exact HELD Route reservation required')
        if command.purpose=='judge':
            target=conn.execute(f'''SELECT c.call_key,r.output_bytes,r.output_hash
                FROM {self.schema}.aip_route_eval_execution_command c
                JOIN {self.schema}.aip_route_eval_execution_result r
                  USING(org_id,project_id,reservation_id)
                WHERE c.org_id=%s AND c.project_id=%s AND c.execution_id=%s
                  AND c.case_id=%s AND c.purpose='target' FOR SHARE OF c,r''',
                (*scope.key,command.execution_id,command.case_id)).fetchone()
            if (target is None or target['call_key']!=command.target_call_key
                or bytes(target['output_bytes'])!=input_bytes
                or target['output_hash']!=command.input_hash
                or hashlib.sha256(bytes(target['output_bytes'])).hexdigest()!=target['output_hash']):
                raise RouteEvalExecutionConflict(
                    'Judge input must be exact recorded Target output')
        text,digest=_canonical(command);existing=self._command_row(conn,scope,reservation_id)
        if existing is not None:
            original,raw=self._read_command(existing)
            if original!=command or raw!=input_bytes:
                raise RouteEvalExecutionConflict('Route command replay drifted')
            return original.model_copy(deep=True)
        conn.execute(f'''INSERT INTO {self.schema}.aip_route_eval_execution_command(
            org_id,project_id,reservation_id,execution_id,case_id,purpose,call_key,
            command_hash,command_payload,input_hash,input_bytes)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)''',
            (*scope.key,reservation_id,command.execution_id,command.case_id,
             command.purpose,command.call_key,digest,text,command.input_hash,input_bytes))
        return command.model_copy(deep=True)

    def record_result(self,conn,scope,reservation_id,*,result,output_bytes):
        if type(result) is not RouteEvalExecutionResult or type(output_bytes) is not bytes:
            raise RouteEvalExecutionConflict('original Route result and bytes required')
        self._scope(scope,result.tenant)
        if (len(output_bytes)>WIRE_LIMIT
            or hashlib.sha256(output_bytes).hexdigest()!=result.output_hash):
            raise RouteEvalExecutionConflict('exact bounded Route output bytes required')
        command_row=self._command_row(conn,scope,reservation_id)
        if command_row is None:raise RouteEvalExecutionConflict('Route command unavailable')
        command,_=self._read_command(command_row);row=self._reservation(conn,scope,reservation_id)
        try:provider=BudgetExactRef.model_validate(row['provider_request_receipt_ref'])
        except (ValueError,TypeError):
            raise RouteEvalExecutionConflict('Route provider request unavailable') from None
        if (row['state'] not in {'submitted','unknown'}
            or provider!=result.provider_request_ref
            or (result.execution_id,result.call_key,result.case_id,result.purpose)
               !=(command.execution_id,command.call_key,command.case_id,command.purpose)):
            raise RouteEvalExecutionConflict('submitted exact Route result required')
        text,digest=_canonical(result);existing=self._result_row(conn,scope,reservation_id)
        if existing is not None:
            original,raw=self._read_result(existing,command)
            if original!=result or raw!=output_bytes:
                raise RouteEvalExecutionConflict('Route result replay drifted')
            return original.model_copy(deep=True)
        conn.execute(f'''INSERT INTO {self.schema}.aip_route_eval_execution_result(
            org_id,project_id,reservation_id,provider_request_ref,result_hash,
            result_payload,output_hash,output_bytes)
            VALUES(%s,%s,%s,%s::jsonb,%s,%s::jsonb,%s,%s)''',
            (*scope.key,reservation_id,json.dumps(exact_ref_payload(
                result.provider_request_ref),sort_keys=True,separators=(',',':')),
             digest,text,result.output_hash,output_bytes))
        return result.model_copy(deep=True)

    def read(self,conn,scope,reservation_id):
        if type(scope) is not TenantScope or scope.key!=('org-org','dev-project'):
            raise RouteEvalExecutionConflict('exact Route tenant scope required')
        row=self._command_row(conn,scope,reservation_id)
        if row is None:return None
        command,input_bytes=self._read_command(row);result_row=self._result_row(
            conn,scope,reservation_id)
        result=output_bytes=None
        if result_row is not None:result,output_bytes=self._read_result(result_row,command)
        return {'command':command.model_copy(deep=True),'inputBytes':deepcopy(input_bytes),
            'result':None if result is None else result.model_copy(deep=True),
            'outputBytes':deepcopy(output_bytes)}
