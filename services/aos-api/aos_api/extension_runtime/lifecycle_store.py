"""Transactional subordinate operations; caller owns trusted tenant transaction."""
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from uuid import UUID, uuid4
from collections.abc import Mapping

from psycopg.pq import TransactionStatus
from psycopg.types.json import Jsonb

from aos_api.extension_runtime.lifecycle import next_phase


class RuntimeConflict(ValueError):
    pass


class RuntimeRevisionConflict(RuntimeConflict):
    pass


@dataclass(frozen=True)
class OperationResult:
    operation_id: UUID
    phase: str
    status: str
    revision: int
    replayed: bool = False


def _digest(value):
    raw=json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()
    return "sha256:"+hashlib.sha256(raw).hexdigest()


def _values(row, names):
    return tuple(row[name] for name in names) if isinstance(row,Mapping) else row


def _request_hash(*, kind, actor, etag, deadline, configuration_target=None):
    # PostgreSQL stores timestamptz as an instant. Only the new configuration
    # contract normalizes offsets; existing command hash semantics stay intact.
    if configuration_target is not None:
        deadline = deadline.astimezone(timezone.utc)
    request = {'kind':kind, 'actor':actor, 'expectedEtag':etag, 'deadline':deadline.isoformat()}
    if configuration_target is not None:
        request['configurationTarget'] = configuration_target
    return _digest(request)


def _require_transaction(conn):
    if conn.info.transaction_status != TransactionStatus.INTRANS:
        raise RuntimeError("runtime operation requires an explicit transaction")


def _deadline_valid(conn, deadline):
    # Call only after acquiring the operation lock; SELECT target expressions
    # in the locking statement may have been evaluated before a lock wait.
    row=conn.execute("SELECT %s > clock_timestamp() AS valid",(deadline,)).fetchone()
    return _values(row,("valid",))[0] is True


class RuntimeOperationStore:
    def fail_uncommitted_preparation(self,conn,*,org_id,project_id,operation_id,expected_revision,failure_code):
        """Trusted worker terminal failure, only before preparation was committed."""
        _require_transaction(conn)
        if failure_code not in {'PREPARATION_VALIDATION_FAILED','PREPARATION_EXECUTION_FAILED',
                                'PREPARATION_STOPPED','PREPARATION_EXPIRED'}:
            raise ValueError('invalid preparation failure code')
        target=(org_id,project_id,UUID(str(operation_id)))
        head=conn.execute('''SELECT installation_id FROM extension_runtime_operation
            WHERE org_id=%s AND project_id=%s AND operation_id=%s''',target).fetchone()
        if head is None:raise LookupError('operation not found')
        conn.execute('''SELECT installation_id FROM bundle_installation
            WHERE org_id=%s AND project_id=%s AND installation_id=%s FOR UPDATE''',
            (org_id,project_id,_values(head,('installation_id',))[0])).fetchone()
        row=conn.execute('''SELECT kind,phase,status,revision,failure_code FROM extension_runtime_operation
            WHERE org_id=%s AND project_id=%s AND operation_id=%s FOR UPDATE''',target).fetchone()
        kind,phase,status,revision,existing_code=_values(row,('kind','phase','status','revision','failure_code'))
        if type(expected_revision) is not int or expected_revision!=revision:
            raise RuntimeRevisionConflict('operation version changed')
        if kind!='runtime-apply' or phase not in {'accepted','validating','preparing','registered'}:
            raise RuntimeConflict('operation is not an uncommitted preparation')
        if status=='failed' and existing_code==failure_code:
            return OperationResult(target[2],phase,status,revision,replayed=True)
        if status not in {'accepted','running','needs_attention'}:
            raise RuntimeConflict('operation cannot settle failure')
        resources=conn.execute('''SELECT observed_release,cleanup_state FROM extension_runtime_resource_lease
            WHERE org_id=%s AND project_id=%s AND operation_id=%s ORDER BY resource_id FOR UPDATE''',target).fetchall()
        if any(_values(row,('observed_release','cleanup_state'))!=(True,'released') for row in resources):
            raise RuntimeConflict('preparation resources remain unresolved')
        revision+=1
        conn.execute('''UPDATE extension_runtime_operation SET status='failed',revision=%s,failure_code=%s
            WHERE org_id=%s AND project_id=%s AND operation_id=%s''',(revision,failure_code,*target))
        self._event(conn,*target,revision,'preparation_failed',{'phase':phase,'failureCode':failure_code})
        return OperationResult(target[2],phase,'failed',revision)

    def settle_failed_preparation(self,conn,*,org_id,project_id,operation_id,expected_revision):
        """Close confirmed failed preparation, never resume or activate it."""
        _require_transaction(conn)
        target=(org_id,project_id,UUID(str(operation_id)))
        identity=conn.execute("""SELECT installation_id FROM extension_runtime_operation
            WHERE org_id=%s AND project_id=%s AND operation_id=%s""",target).fetchone()
        if identity is None:
            raise LookupError("operation not found")
        conn.execute("""SELECT installation_id FROM bundle_installation
            WHERE org_id=%s AND project_id=%s AND installation_id=%s FOR UPDATE""",
            (org_id,project_id,_values(identity,("installation_id",))[0]))
        row=conn.execute("""SELECT kind,status,phase,revision,failure_code FROM extension_runtime_operation
            WHERE org_id=%s AND project_id=%s AND operation_id=%s FOR UPDATE""",target).fetchone()
        kind,status,phase,revision,reason=_values(row,("kind","status","phase","revision","failure_code"))
        if type(expected_revision) is not int or revision!=expected_revision:
            raise RuntimeRevisionConflict("operation version changed")
        if kind!="runtime-apply" or status!="needs_attention" or reason!="RESOURCE_CLEANUP_UNCERTAIN":
            raise RuntimeConflict("operation is not a failed preparation cleanup")
        resources=conn.execute("""SELECT observed_release FROM extension_runtime_resource_lease
            WHERE org_id=%s AND project_id=%s AND operation_id=%s FOR UPDATE""",target).fetchall()
        if not resources or not all(_values(item,("observed_release",))[0] for item in resources):
            raise RuntimeConflict("preparation resources are not confirmed released")
        revision+=1
        conn.execute("""UPDATE extension_runtime_operation SET status='failed',revision=%s
            WHERE org_id=%s AND project_id=%s AND operation_id=%s""",(revision,*target))
        self._event(conn,*target,revision,"failed_preparation_settled",{"phase":phase})
        return OperationResult(target[2],phase,"failed",revision)

    def accept(self, conn, *, org_id, project_id, installation_id, kind,
               idempotency_key, requested_by, expected_installation_etag, deadline,
               configuration_target=None):
        _require_transaction(conn)
        from aos_api.extension_runtime.lifecycle import _PATHS
        if kind not in _PATHS or not isinstance(deadline,datetime) or deadline.utcoffset() is None:
            raise ValueError("invalid operation or deadline")
        if type(expected_installation_etag) is not int or expected_installation_etag < 1:
            raise ValueError("invalid expected installation revision")
        if not isinstance(idempotency_key,str) or not 1 <= len(idempotency_key) <= 240:
            raise ValueError("invalid idempotency key")
        snapshot = None
        if kind == 'configure' or (kind == 'enable' and configuration_target is not None):
            from .configuration_contracts import ConfigureTarget
            snapshot = ConfigureTarget.model_validate(configuration_target).model_dump(mode='json')
            scope = conn.execute("SELECT current_setting('aos.org_id',true) AS org_id,current_setting('aos.project_id',true) AS project_id").fetchone()
            if not org_id or not project_id or _values(scope,('org_id','project_id')) != (org_id,project_id):
                raise PermissionError('configuration tenant scope mismatch')
        elif configuration_target is not None:
            raise ValueError('configuration target only belongs to configure or enable')
        installation_id=UUID(str(installation_id))
        target=(org_id,project_id,installation_id)
        # Serialize by the existing installation head. Replay precedes CAS validation.
        head=conn.execute("""SELECT etag_version FROM bundle_installation
            WHERE org_id=%s AND project_id=%s AND installation_id=%s FOR UPDATE""",target).fetchone()
        if head is None:
            raise LookupError("installation not found")
        head=_values(head,("etag_version",))
        request_hash=_request_hash(kind=kind,actor=requested_by,etag=expected_installation_etag,
                                  deadline=deadline,configuration_target=snapshot)
        existing=conn.execute("""SELECT operation_id,phase,status,revision,request_hash
            FROM extension_runtime_operation WHERE org_id=%s AND project_id=%s AND installation_id=%s
            AND kind=%s AND idempotency_key=%s""",(*target,kind,idempotency_key)).fetchone()
        if existing:
            existing=_values(existing,("operation_id","phase","status","revision","request_hash"))
            if existing[4]!=request_hash:
                raise RuntimeConflict("idempotency key has another request")
            return OperationResult(*existing[:4],replayed=True)
        if head[0]!=expected_installation_etag:
            raise RuntimeRevisionConflict("installation version changed")
        binding_revision = None
        if snapshot is not None:
            binding = conn.execute('''SELECT revision FROM extension_runtime_binding
                WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s FOR UPDATE''',
                (*target, UUID(snapshot['generation']))).fetchone()
            if binding is None:
                raise LookupError('configuration binding not found')
            binding_revision = snapshot['bindingRevision']
            if _values(binding,('revision',))[0] != binding_revision:
                raise RuntimeRevisionConflict('configuration binding version changed')
            if not _deadline_valid(conn,deadline):
                raise RuntimeConflict('configuration request deadline expired')
        operation_id=uuid4()
        conn.execute("""INSERT INTO extension_runtime_operation
            (org_id,project_id,operation_id,installation_id,kind,idempotency_key,request_hash,
             requested_by,expected_installation_etag,expected_binding_revision,status,phase,deadline)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'accepted','accepted',%s)""",
            (org_id,project_id,operation_id,installation_id,kind,idempotency_key,request_hash,
             requested_by,expected_installation_etag,binding_revision,deadline))
        payload={"kind":kind}
        if snapshot is not None:
            payload['configurationTarget']=snapshot
        self._event(conn,org_id,project_id,operation_id,1,"accepted",payload)
        return OperationResult(operation_id,"accepted","accepted",1)

    def advance(self, conn, *, org_id, project_id, operation_id, expected_revision, phase):
        _require_transaction(conn)
        target=(org_id,project_id,UUID(str(operation_id)))
        identity=conn.execute("""SELECT installation_id FROM extension_runtime_operation
            WHERE org_id=%s AND project_id=%s AND operation_id=%s""",target).fetchone()
        if identity is None:
            raise LookupError("operation not found")
        identity=_values(identity,("installation_id",))
        conn.execute("""SELECT installation_id FROM bundle_installation
            WHERE org_id=%s AND project_id=%s AND installation_id=%s FOR UPDATE""",
            (org_id,project_id,identity[0]))
        row=conn.execute("""SELECT kind,phase,status,revision,deadline FROM extension_runtime_operation
            WHERE org_id=%s AND project_id=%s AND operation_id=%s FOR UPDATE""",target).fetchone()
        row=_values(row,("kind","phase","status","revision","deadline"))
        if type(expected_revision) is not int or row[3]!=expected_revision:
            raise RuntimeRevisionConflict("operation version changed")
        if row[2] not in {"accepted","running"}:
            raise RuntimeConflict("operation does not accept progress")
        if row[0] in {"runtime-apply","runtime-verify","configure","enable"} and not _deadline_valid(conn,row[4]):
            raise RuntimeConflict("operation deadline expired")
        next_phase(row[0],row[1],phase)
        status=phase if phase in {"succeeded","cancelled"} else "running"
        revision=row[3]+1
        conn.execute("""UPDATE extension_runtime_operation SET phase=%s,status=%s,revision=%s
            WHERE org_id=%s AND project_id=%s AND operation_id=%s""",(phase,status,revision,*target))
        self._event(conn,*target,revision,phase,{"previousPhase":row[1]})
        return OperationResult(target[2],phase,status,revision)

    @staticmethod
    def _event(conn,org_id,project_id,operation_id,sequence,event_type,payload):
        event_id=uuid4()
        conn.execute("""INSERT INTO extension_runtime_event
            (org_id,project_id,operation_id,sequence,event_id,type,payload,payload_hash)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s)""",
            (org_id,project_id,operation_id,sequence,event_id,event_type,Jsonb(payload),_digest(payload)))
        conn.execute("""INSERT INTO extension_runtime_outbox(org_id,project_id,event_id,consumer_id)
            VALUES(%s,%s,%s,'runtime-reconciler')""",(org_id,project_id,event_id))
