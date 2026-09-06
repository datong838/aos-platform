"""Receipt-first configuration/enable acceptance, never inline execution."""
from datetime import timedelta
from uuid import UUID

from aos_api.asset_registry.control_policy import (CONFIGURE_RUNTIME_OPERATION,ENABLE_RUNTIME_OPERATION,APPLY_INSTALLATION_OPERATION,
    require_control_role,validate_idempotency_key,parse_strong_if_match,strong_etag)
from aos_api.asset_registry.installation_service import _load_current_lock,_require_lock_markings
from aos_api.asset_registry.installation_store import CommandResult,command_request_hash
from .configuration_contracts import ConfigureTarget
from .configuration_store import read_configuration
from .lifecycle_store import RuntimeOperationStore,RuntimeConflict,_values


class RuntimeConfigurationService:
    def __init__(self, *, installation_store, installation_reader, revalidator, authorize):
        if not callable(authorize):raise ValueError('current configuration authority required')
        self._store=installation_store
        self._reader=installation_reader
        self._revalidator=revalidator
        self._authorize=authorize

    def request(self, *, installation_id, kind, org_id, project_id, actor, roles, markings,
                idempotency_key, if_match, target):
        operations={'configure':CONFIGURE_RUNTIME_OPERATION,'enable':ENABLE_RUNTIME_OPERATION}
        if kind not in operations:raise ValueError('unsupported configuration command')
        # Reuse the frozen installation-maintenance role contract; runtime
        # receipt namespaces do not expand legacy control command operations.
        require_control_role(roles=roles,operation=APPLY_INSTALLATION_OPERATION)
        key=validate_idempotency_key(idempotency_key)
        etag,revision=parse_strong_if_match(if_match)
        installation_id=str(UUID(str(installation_id)))
        target=ConfigureTarget.model_validate(target)
        scope=dict(org_id=org_id,project_id=project_id)
        self._reader.get(installation_id=installation_id,**scope,roles=roles,markings=markings)

        def current_check(conn):
            # Serialize the authority readers after the installation lock, also
            # on replay; do not impose the old request's CAS on cached receipts.
            row=conn.execute('''SELECT installation_id FROM bundle_installation
                WHERE org_id=%s AND project_id=%s AND installation_id=%s FOR UPDATE''',
                (org_id,project_id,UUID(installation_id))).fetchone()
            if row is None:raise LookupError('configuration installation not found')
            read_configuration(conn,**scope,installation_id=installation_id,generation=target.generation,
                actor=actor,ref=target.configRef,authorize=self._authorize)
            return True

        def handler(conn):
            locked=self._store.lock_for_transition_in_transaction(conn,**scope,installation_id=installation_id,
                expected_etag_version=revision)
            lock=_load_current_lock(conn,locked=locked,**scope)
            _require_lock_markings(lock,markings=markings,conceal=False)
            if locked.record.state!='active':raise RuntimeConflict('configuration requires active installation')
            if conn.execute('''SELECT operation_id FROM extension_runtime_operation
                WHERE org_id=%s AND project_id=%s AND installation_id=%s
                AND status NOT IN ('succeeded','failed','cancelled') LIMIT 1''',
                (org_id,project_id,UUID(installation_id))).fetchone() is not None:
                raise RuntimeConflict('installation already has unresolved operation')
            checked=self._revalidator.revalidate_in_transaction(conn,lock=lock)
            if not checked.runtime_members:raise RuntimeConflict('pure content uses existing workflow')
            if kind=='enable':
                row=conn.execute('''SELECT config_ref FROM extension_runtime_binding
                    WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s FOR UPDATE''',
                    (org_id,project_id,UUID(installation_id),UUID(target.generation))).fetchone()
                if row is None or _values(row,('config_ref',))[0]!=target.configRef.model_dump(mode='json'):
                    raise RuntimeConflict('enable target is not the committed configuration')
            result=RuntimeOperationStore().accept(conn,**scope,installation_id=installation_id,kind=kind,
                idempotency_key=key,requested_by=actor,expected_installation_etag=revision,
                deadline=checked.checked_at+timedelta(minutes=5),configuration_target=target.model_dump(mode='json'))
            return CommandResult(status_code=202,response_json=dict(installationId=installation_id,
                operationId=str(result.operation_id),phase=result.phase,status=result.status,revision=result.revision),
                response_etag=strong_etag(result.revision))

        return self._store.execute_idempotent(**scope,operation=operations[kind],idempotency_key=key,subject=actor,
            request_hash=command_request_hash(subject=actor,path_params={'installationId':installation_id},
                body={'kind':kind,'target':target.model_dump(mode='json')},if_match=etag),
            current_check=current_check,handler=handler)
