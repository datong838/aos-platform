"""Single-claim delivery persistence using the existing signed-read Attempt ledger."""
from dataclasses import dataclass, field
import secrets
from uuid import UUID

from psycopg.types.json import Jsonb

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.extension_runtime.generation_attempts import PostgresRuntimeAttemptStore, _scope, _token_hash, _HASH
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict, _require_transaction, _values
from aos_api.extension_runtime.ui_read_contracts import UiReadRequest
from aos_api.tenant_scope import TenantScope


@dataclass(frozen=True, slots=True)
class UiReadClaim:
    request_id: UUID
    request: UiReadRequest
    subject: str
    attempt_id: UUID
    owner_token: str = field(repr=False)


def _current(conn,scope,target):
    row=conn.execute('''SELECT installation_revision,execution_epoch,revision,enabled,operation_fence,
        desired_state,observed_state FROM extension_runtime_binding
        WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s FOR SHARE''',
        (*scope.key,UUID(target.installationId),UUID(target.generation))).fetchone()
    return row is not None and _values(row,('installation_revision','execution_epoch','revision','enabled',
        'operation_fence','desired_state','observed_state')) == (target.installationRevision,target.executionEpoch,
        target.bindingRevision,True,False,'enabled','ready')


def claim_ui_read(*,conn,scope:TenantScope,request_id:UUID,snapshot_hash:str):
    _require_transaction(conn)
    if type(scope) is not TenantScope or type(request_id) is not UUID or type(snapshot_hash) is not str or not _HASH.fullmatch(snapshot_hash):
        raise RuntimeConflict('exact UI read claim required')
    _scope(conn,*scope.key)
    row=conn.execute('''SELECT subject,request_hash,target_json,case_limit,run_limit,state,revision,deadline,
        deadline>clock_timestamp() AS current FROM extension_runtime_ui_read_request
        WHERE org_id=%s AND project_id=%s AND request_id=%s FOR UPDATE''',(*scope.key,request_id)).fetchone()
    if row is None:return None
    subject,digest,target,case_limit,run_limit,state,revision,deadline,current=_values(row,
        ('subject','request_hash','target_json','case_limit','run_limit','state','revision','deadline','current'))
    if state!='requested':return None
    if revision!=1 or not current:raise RuntimeConflict('UI read request no longer claimable')
    request=UiReadRequest.model_validate(dict(schemaVersion='aos.runtime-ui-read-request/v1',
        operationId='analyst_workspace_view_v1',moduleId='ecommerce.analyst',target=target,caseLimit=case_limit,runLimit=run_limit))
    expected=canonical_sha256(dict(tenant=dict(orgId=scope.org_id,projectId=scope.project_id),subject=subject,
                                   request=request.model_dump(mode='json')))
    if digest!=expected or not _current(conn,scope,request.target):raise RuntimeConflict('UI read target differs')
    token=secrets.token_urlsafe(48)
    attempt_hash=canonical_sha256(dict(requestHash=digest,snapshotHash=snapshot_hash))
    lease=PostgresRuntimeAttemptStore().begin(conn,org_id=scope.org_id,project_id=scope.project_id,
        installation_id=request.target.installationId,generation=request.target.generation,
        execution_epoch=request.target.executionEpoch,operation_kind='signed_read',operation_key='ui-read:'+str(request_id),
        idempotency_key='ui-read:'+str(request_id),request_hash=attempt_hash,owner_token=token,lease_until=deadline)
    if not lease.execute_once:raise RuntimeConflict('UI read attempt cannot be replayed')
    conn.execute('''UPDATE extension_runtime_ui_read_request SET state='claimed',revision=2,claimed_at=clock_timestamp(),
        attempt_id=%s,owner_token_hash=%s,snapshot_hash=%s,attempt_request_hash=%s
        WHERE org_id=%s AND project_id=%s AND request_id=%s''',
        (lease.attempt_id,_token_hash(token),snapshot_hash,attempt_hash,*scope.key,request_id))
    return UiReadClaim(request_id,request,subject,lease.attempt_id,token)


def complete_ui_read(*,conn,scope:TenantScope,claim:UiReadClaim,result=None,failure_code=None):
    _require_transaction(conn)
    if type(scope) is not TenantScope or type(claim) is not UiReadClaim:
        raise RuntimeConflict('exact UI read completion required')
    if (result is None)==(failure_code is None) or (result is not None and type(result) is not dict):
        raise RuntimeConflict('one UI read result or failure required')
    if failure_code is not None and failure_code not in {'READ_ACCESS_REVOKED','READ_FAILED','READ_RESULT_INVALID','READ_OUTCOME_UNKNOWN'}:
        raise RuntimeConflict('fixed UI read failure required')
    _scope(conn,*scope.key)
    row=conn.execute('''SELECT state,revision,attempt_id,owner_token_hash,deadline<=clock_timestamp() AS expired,target_json
        FROM extension_runtime_ui_read_request WHERE org_id=%s AND project_id=%s AND request_id=%s FOR UPDATE''',
        (*scope.key,claim.request_id)).fetchone()
    if row is None:raise RuntimeConflict('UI read claim unavailable')
    state,revision,attempt,owner,expired,target=_values(row,('state','revision','attempt_id','owner_token_hash','expired','target_json'))
    if (state,revision,attempt,owner)!=('claimed',2,claim.attempt_id,_token_hash(claim.owner_token)) or target!=claim.request.target.model_dump(mode='json'):
        raise RuntimeConflict('UI read claim changed')
    if expired:failure_code='READ_DEADLINE_EXPIRED'
    elif result is not None and not _current(conn,scope,claim.request.target):failure_code='READ_RUNTIME_CHANGED'
    state='expired' if expired else ('failed' if failure_code else 'succeeded')
    stored_result=None if failure_code else result
    result_hash=canonical_sha256(stored_result) if stored_result is not None else None
    PostgresRuntimeAttemptStore().settle(conn,org_id=scope.org_id,project_id=scope.project_id,
        attempt_id=claim.attempt_id,expected_revision=1,owner_token=claim.owner_token,
        state='succeeded' if state=='succeeded' else 'failed')
    conn.execute('''UPDATE extension_runtime_ui_read_request SET state=%s,revision=3,completed_at=clock_timestamp(),
        result_json=%s,result_hash=%s,failure_code=%s WHERE org_id=%s AND project_id=%s AND request_id=%s''',
        (state,Jsonb(stored_result) if stored_result is not None else None,result_hash,failure_code,*scope.key,claim.request_id))
    return state
