"""Persisted ownership journal. OCI side effects must occur after its transaction commits."""
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4
import re

from aos_api.extension_runtime.lifecycle_store import _require_transaction, _values, _deadline_valid, _digest, RuntimeConflict, RuntimeOperationStore
from aos_api.extension_runtime.supervisor import ResourceIdentity


@dataclass(frozen=True)
class ResourceIntent:
    resource_id: UUID
    identity: ResourceIdentity
    engine_context: str
    replayed: bool = False


class ResourceJournal:
    def record_registered(self,conn,*,org_id,project_id,resource_id,declared):
        """Trusted signed supervisor only; persists comparison, not readiness."""
        from .contracts import RegistrationDescription
        _require_transaction(conn)
        description=RegistrationDescription.model_validate(declared)
        claims_hash=_digest(description.model_dump(mode='json',by_alias=True))
        target=(org_id,project_id,UUID(str(resource_id)))
        row=conn.execute("""SELECT owner_token_ref,engine_context,container_id
            FROM extension_runtime_resource_lease WHERE org_id=%s AND project_id=%s AND resource_id=%s""",target).fetchone()
        if row is None:raise LookupError('resource not found')
        owner,context,container_id=_values(row,('owner_token_ref','engine_context','container_id'))
        if container_id is None:raise RuntimeConflict('resource not created')
        # Reuse exact lock order and the live/claimed identity guard. Since the
        # ID already exists this never creates an additional creation event.
        self.record_created(conn,org_id=org_id,project_id=project_id,
            intent=ResourceIntent(target[2],ResourceIdentity(owner),context),container_id=container_id)
        row=conn.execute("""SELECT operation_id,package_hash FROM extension_runtime_resource_lease
            WHERE org_id=%s AND project_id=%s AND resource_id=%s""",target).fetchone()
        operation_id,package_hash=_values(row,('operation_id','package_hash'))
        payload={'resourceId':str(target[2]),'containerId':container_id,'packageHash':package_hash,'claimsHash':claims_hash}
        prior=conn.execute("""SELECT payload FROM extension_runtime_event WHERE org_id=%s AND project_id=%s
            AND operation_id=%s AND type='resource_registered' AND payload->>'resourceId'=%s""",
            (org_id,project_id,operation_id,str(target[2]))).fetchone()
        if prior is not None:
            if _values(prior,('payload',))[0]!=payload:raise RuntimeConflict('registration observation changed')
            return
        row=conn.execute("""UPDATE extension_runtime_operation SET revision=revision+1
            WHERE org_id=%s AND project_id=%s AND operation_id=%s RETURNING revision""",
            (org_id,project_id,operation_id)).fetchone()
        RuntimeOperationStore._event(conn,org_id,project_id,operation_id,_values(row,('revision',))[0],
            'resource_registered',payload)

    def record_created(self,conn,*,org_id,project_id,intent,container_id):
        """Record a trusted OCI observation; never assert registration/readiness."""
        _require_transaction(conn)
        if not isinstance(intent,ResourceIntent) or not isinstance(container_id,str) or not re.fullmatch(r"[0-9a-f]{64}",container_id):
            raise ValueError("invalid container observation")
        target=(org_id,project_id,intent.resource_id)
        head=conn.execute("""SELECT o.installation_id,o.operation_id FROM extension_runtime_resource_lease r
            JOIN extension_runtime_operation o USING(org_id,project_id,operation_id)
            WHERE r.org_id=%s AND r.project_id=%s AND r.resource_id=%s""",target).fetchone()
        if head is None:raise LookupError("resource not found")
        installation_id,operation_id=_values(head,("installation_id","operation_id"))
        conn.execute("""SELECT installation_id FROM bundle_installation
            WHERE org_id=%s AND project_id=%s AND installation_id=%s FOR UPDATE""",
            (org_id,project_id,installation_id)).fetchone()
        operation=conn.execute("""SELECT revision FROM extension_runtime_operation
            WHERE org_id=%s AND project_id=%s AND operation_id=%s FOR UPDATE""",
            (org_id,project_id,operation_id)).fetchone()
        row=conn.execute("""SELECT owner_token_ref,engine_context,container_id,create_claimed_at,observed_release
            FROM extension_runtime_resource_lease WHERE org_id=%s AND project_id=%s AND resource_id=%s FOR UPDATE""",target).fetchone()
        owner,context,existing,claimed,released=_values(row,("owner_token_ref","engine_context","container_id","create_claimed_at","observed_release"))
        if (owner,context)!=(intent.identity.owner,intent.engine_context) or claimed is None or released:
            raise RuntimeConflict("resource cannot accept creation observation")
        if existing is not None:
            if existing!=container_id:raise RuntimeConflict("container identity changed")
            return
        conn.execute("""UPDATE extension_runtime_resource_lease SET container_id=%s
            WHERE org_id=%s AND project_id=%s AND resource_id=%s""",(container_id,*target))
        revision=_values(operation,("revision",))[0]+1
        conn.execute("""UPDATE extension_runtime_operation SET revision=%s
            WHERE org_id=%s AND project_id=%s AND operation_id=%s""",(revision,org_id,project_id,operation_id))
        RuntimeOperationStore._event(conn,org_id,project_id,operation_id,revision,"resource_created",
            {"resourceId":str(intent.resource_id),"containerId":container_id})

    def record_cleanup(self, conn, *, org_id, project_id, intent, removed):
        """Trusted supervisor observation; absence/unknown never means released."""
        _require_transaction(conn)
        if type(removed) is not bool or not isinstance(intent,ResourceIntent):
            raise ValueError("invalid cleanup observation")
        target=(org_id,project_id,intent.resource_id)
        row=conn.execute("""SELECT operation_id,generation FROM extension_runtime_resource_lease
            WHERE org_id=%s AND project_id=%s AND resource_id=%s""",target).fetchone()
        if row is None:
            raise LookupError("resource not found")
        operation_id,generation=_values(row,("operation_id","generation"))
        head=conn.execute("""SELECT installation_id FROM extension_runtime_operation
            WHERE org_id=%s AND project_id=%s AND operation_id=%s""",
            (org_id,project_id,operation_id)).fetchone()
        if head is None:
            raise LookupError("operation not found")
        installation_id=_values(head,("installation_id",))[0]
        binding_target=(org_id,project_id,installation_id,generation)
        conn.execute("""SELECT installation_id FROM bundle_installation
            WHERE org_id=%s AND project_id=%s AND installation_id=%s FOR UPDATE""",
            binding_target[:3]).fetchone()
        operation=conn.execute("""SELECT revision FROM extension_runtime_operation
            WHERE org_id=%s AND project_id=%s AND operation_id=%s FOR UPDATE""",
            (org_id,project_id,operation_id)).fetchone()
        if operation is None:
            raise LookupError("operation not found")
        conn.execute("""SELECT generation FROM extension_runtime_binding
            WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s FOR UPDATE""",
            binding_target).fetchone()
        resource=conn.execute("""SELECT owner_token_ref,engine_context,cleanup_state
            FROM extension_runtime_resource_lease WHERE org_id=%s AND project_id=%s AND resource_id=%s FOR UPDATE""",target).fetchone()
        owner,context,state=_values(resource,("owner_token_ref","engine_context","cleanup_state"))
        if (owner,context)!=(intent.identity.owner,intent.engine_context):
            raise RuntimeConflict("cleanup resource identity mismatch")
        requested="released" if removed else "uncertain"
        if state==requested or state=="released":
            return state
        # A single missing child invalidates admission, but cannot prove the
        # whole generation stopped. Lifecycle aggregation owns that decision.
        conn.execute("""UPDATE extension_runtime_binding SET enabled=false,operation_fence=true,
            execution_epoch=execution_epoch+CASE WHEN enabled OR NOT operation_fence THEN 1 ELSE 0 END,
            revision=revision+1,observed_state='unknown'
            WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s
            AND (enabled OR NOT operation_fence OR observed_state<>'unknown')""",binding_target)
        conn.execute("""UPDATE extension_runtime_resource_lease SET cleanup_state=%s,observed_release=%s
            WHERE org_id=%s AND project_id=%s AND resource_id=%s""",(requested,removed,*target))
        revision=_values(operation,("revision",))[0]+1
        conn.execute("""UPDATE extension_runtime_operation SET revision=%s,
            status=CASE WHEN %s THEN status ELSE 'needs_attention' END,
            failure_code=CASE WHEN %s THEN failure_code ELSE 'RESOURCE_CLEANUP_UNCERTAIN' END
            WHERE org_id=%s AND project_id=%s AND operation_id=%s""",
            (revision,removed,removed,org_id,project_id,operation_id))
        RuntimeOperationStore._event(conn,org_id,project_id,operation_id,revision,"resource_"+requested,
            {"resourceId":str(intent.resource_id)})
        return requested

    def claim_create(self, conn, *, org_id, project_id, resource_id):
        """One-shot intent claim. Commit before OCI; crashes never reissue it."""
        _require_transaction(conn)
        target=(org_id,project_id,UUID(str(resource_id)))
        identity=conn.execute("""SELECT operation_id FROM extension_runtime_resource_lease
          WHERE org_id=%s AND project_id=%s AND resource_id=%s""",target).fetchone()
        if identity is None:
            raise LookupError("resource intent not found")
        operation_id=_values(identity,("operation_id",))[0]
        operation=conn.execute("""SELECT status,deadline
          FROM extension_runtime_operation WHERE org_id=%s AND project_id=%s
          AND operation_id=%s FOR UPDATE""",(org_id,project_id,operation_id)).fetchone()
        if operation is None:
            raise LookupError("operation not found")
        status,deadline=_values(operation,("status","deadline"))
        if status not in {"accepted","running"} or not _deadline_valid(conn,deadline):
            raise RuntimeConflict("operation cannot create resources")
        row=conn.execute("""UPDATE extension_runtime_resource_lease
          SET create_claimed_at=clock_timestamp()
          WHERE org_id=%s AND project_id=%s AND resource_id=%s
          AND create_claimed_at IS NULL AND NOT observed_release
          AND expires_at > clock_timestamp()
          RETURNING resource_id,owner_token_ref,engine_context""",target).fetchone()
        if row is None:
            raise RuntimeConflict("resource creation claim unavailable; reconcile only")
        resource,owner,context=_values(row,("resource_id","owner_token_ref","engine_context"))
        return ResourceIntent(resource,ResourceIdentity(owner),context)

    def prepare(self, conn, *, org_id, project_id, operation_id, generation,
                package_id, package_hash, engine_context, expires_at):
        _require_transaction(conn)
        if not re.fullmatch(r"sha256:[0-9a-f]{64}",package_hash):
            raise ValueError("invalid package digest")
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,79}",engine_context):
            raise ValueError("invalid trusted engine context")
        if not isinstance(expires_at,datetime) or expires_at.utcoffset() is None:
            raise ValueError("invalid resource expiry")
        target=(org_id,project_id,UUID(str(operation_id)))
        head=conn.execute("""SELECT installation_id FROM extension_runtime_operation
          WHERE org_id=%s AND project_id=%s AND operation_id=%s""",target).fetchone()
        if head is None:
            raise LookupError("operation not found")
        installation_id=_values(head,("installation_id",))[0]
        conn.execute("""SELECT installation_id FROM bundle_installation
          WHERE org_id=%s AND project_id=%s AND installation_id=%s FOR UPDATE""",
          (org_id,project_id,installation_id))
        operation=conn.execute("""SELECT status,deadline FROM extension_runtime_operation
          WHERE org_id=%s AND project_id=%s AND operation_id=%s FOR UPDATE""",target).fetchone()
        if operation is None:
            raise LookupError("operation not found")
        if _values(operation,("status",))[0] not in {"accepted","running"}:
            raise RuntimeConflict("operation no longer accepts resources")
        if not _deadline_valid(conn,_values(operation,("status","deadline"))[1]):
            raise RuntimeConflict("operation deadline expired")
        generation=UUID(str(generation))
        existing=conn.execute("""SELECT resource_id,owner_token_ref,engine_context FROM extension_runtime_resource_lease
          WHERE org_id=%s AND project_id=%s AND operation_id=%s AND generation=%s AND package_id=%s AND package_hash=%s""",
          (*target,generation,package_id,package_hash)).fetchone()
        if existing:
            resource_id,owner,context=_values(existing,("resource_id","owner_token_ref","engine_context"))
            if context!=engine_context:
                raise RuntimeConflict("resource intent engine changed")
            # A replay is for reconciliation only, never permission to create again.
            return ResourceIntent(resource_id,ResourceIdentity(owner),context,True)
        resource_id=uuid4(); identity=ResourceIdentity(uuid4().hex)
        conn.execute("""INSERT INTO extension_runtime_resource_lease
          (org_id,project_id,resource_id,operation_id,owner_token_ref,generation,package_id,package_hash,
           engine_context,resource_name,expires_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
          (org_id,project_id,resource_id,target[2],identity.owner,generation,package_id,package_hash,
           engine_context,identity.name,expires_at))
        return ResourceIntent(resource_id,identity,engine_context)

    def unresolved(self, conn, *, org_id, project_id):
        rows=conn.execute("""SELECT resource_id,owner_token_ref,engine_context FROM extension_runtime_resource_lease
          WHERE org_id=%s AND project_id=%s AND NOT observed_release ORDER BY resource_id""",
          (org_id,project_id)).fetchall()
        return [ResourceIntent(values[0],ResourceIdentity(values[1]),values[2],True)
                for row in rows if (values:=_values(row,("resource_id","owner_token_ref","engine_context")))]
