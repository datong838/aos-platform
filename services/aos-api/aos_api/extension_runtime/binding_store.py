"""Subordinate fence primitive. Authorization belongs to the lifecycle service."""
from uuid import UUID

from aos_api.extension_runtime.lifecycle_store import (
    RuntimeOperationStore, RuntimeRevisionConflict, _require_transaction, _values,
)


class RuntimeBindingStore:
    def fence(self, conn, *, org_id, project_id, installation_id, generation,
              operation_id, expected_operation_revision, expected_binding_revision):
        _require_transaction(conn)
        installation_id=UUID(str(installation_id))
        operation_id=UUID(str(operation_id))
        generation=UUID(str(generation))
        target=(org_id,project_id,installation_id)
        if conn.execute("""SELECT installation_id FROM bundle_installation
            WHERE org_id=%s AND project_id=%s AND installation_id=%s FOR UPDATE""",target).fetchone() is None:
            raise LookupError("installation not found")
        operation=conn.execute("""SELECT kind FROM extension_runtime_operation
            WHERE org_id=%s AND project_id=%s AND installation_id=%s AND operation_id=%s FOR UPDATE""",
            (*target,operation_id)).fetchone()
        if operation is None:
            raise LookupError("operation not found for installation")
        if _values(operation,('kind',))[0] == 'configure':
            from .configuration_request import load_configure_target
            target_request = load_configure_target(conn,org_id=org_id,project_id=project_id,operation_id=operation_id)
            if (str(generation) != target_request.generation or type(expected_binding_revision) is not int
                    or expected_binding_revision != target_request.bindingRevision):
                raise RuntimeRevisionConflict('configuration fence target differs from accepted request')
        binding=conn.execute("""SELECT revision FROM extension_runtime_binding
            WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s FOR UPDATE""",
            (*target,generation)).fetchone()
        if binding is None:
            raise LookupError("binding not found")
        if type(expected_binding_revision) is not int or _values(binding,("revision",))[0]!=expected_binding_revision:
            raise RuntimeRevisionConflict("binding version changed")
        result=RuntimeOperationStore().advance(conn,org_id=org_id,project_id=project_id,
            operation_id=operation_id,expected_revision=expected_operation_revision,phase="fencing")
        conn.execute("""UPDATE extension_runtime_binding SET enabled=false,operation_fence=true,
            execution_epoch=execution_epoch+1,revision=revision+1,observed_state='draining'
            WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s""",(*target,generation))
        return result
