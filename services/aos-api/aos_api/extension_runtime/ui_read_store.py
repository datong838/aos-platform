"""Internal delivery storage; callers still owe signed UI admission before enqueue."""
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict, _require_transaction, _values
from aos_api.extension_runtime.ui_current_principal import read_current_ui_principal
from aos_api.extension_runtime.ui_read_contracts import UiReadRequest
from aos_api.tenant_scope import TenantScope


@dataclass(frozen=True, slots=True)
class UiReadDelivery:
    request_id: UUID
    request_hash: str
    state: str
    revision: int
    deadline: datetime


def enqueue_ui_read(*, conn, scope: TenantScope, subject: str, idempotency_key: str,
                    request: UiReadRequest) -> UiReadDelivery:
    """Store once in caller's transaction. This function grants no execution rights."""
    _require_transaction(conn)
    if (type(request) is not UiReadRequest or type(idempotency_key) is not str
            or not 1 <= len(idempotency_key) <= 240 or not idempotency_key.isprintable()
            or idempotency_key != idempotency_key.strip()):
        raise RuntimeConflict('exact UI read request and key required')
    isolation = conn.execute('SHOW transaction_isolation').fetchone()
    if _values(isolation, ('transaction_isolation',))[0] != 'read committed':
        raise RuntimeConflict('UI admission requires read committed serialization')
    # The lock remains held until the caller commits or rolls back. READ COMMITTED
    # ensures a waiter sees its predecessor's inserts when it resumes.
    read_current_ui_principal(conn=conn, scope=scope, subject=subject, required_markings=())
    lock_key = canonical_sha256({'kind': 'runtime-ui-read-admission', 'scope': list(scope.key)})
    conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', (lock_key,))
    digest = canonical_sha256({'tenant': {'orgId': scope.org_id, 'projectId': scope.project_id},
                               'subject': subject, 'request': request.model_dump(mode='json')})
    row = conn.execute('''SELECT request_id,request_hash,state,revision,deadline
        FROM extension_runtime_ui_read_request
        WHERE org_id=%s AND project_id=%s AND subject=%s AND idempotency_key=%s''',
        (*scope.key, subject, idempotency_key)).fetchone()
    if row is not None:
        values = _values(row, ('request_id', 'request_hash', 'state', 'revision', 'deadline'))
        if values[1] != digest:
            raise RuntimeConflict('UI read idempotency key conflicts')
        return UiReadDelivery(*values)
    counts = conn.execute('''SELECT count(*) AS tenant_count,
        count(*) FILTER(WHERE subject=%s) AS subject_count
        FROM extension_runtime_ui_read_request WHERE org_id=%s AND project_id=%s
        AND state IN ('requested','claimed') AND deadline>clock_timestamp()''',
        (subject, *scope.key)).fetchone()
    tenant_count, subject_count = _values(counts, ('tenant_count', 'subject_count'))
    if tenant_count >= 64 or subject_count >= 8:
        raise RuntimeConflict('UI read pending capacity reached')
    target = request.target
    row = conn.execute('''INSERT INTO extension_runtime_ui_read_request
        (org_id,project_id,request_id,subject,idempotency_key,request_hash,
         installation_id,generation,execution_epoch,operation_id,module_id,target_json,
         case_limit,run_limit,state,deadline)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'requested',clock_timestamp()+interval '60 seconds')
        RETURNING request_id,request_hash,state,revision,deadline''',
        (*scope.key, uuid4(), subject, idempotency_key, digest, UUID(target.installationId),
         UUID(target.generation), target.executionEpoch, request.operationId, request.moduleId,
         Jsonb(target.model_dump(mode='json')), request.caseLimit, request.runLimit)).fetchone()
    return UiReadDelivery(*_values(row, ('request_id', 'request_hash', 'state', 'revision', 'deadline')))
