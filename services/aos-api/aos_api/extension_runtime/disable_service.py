"""Receipt-first conservative disable; invalid positive dependencies cannot veto it."""
from datetime import timedelta
from uuid import UUID

from aos_api.asset_registry.control_policy import (DISABLE_RUNTIME_OPERATION,APPLY_INSTALLATION_OPERATION,
    require_control_role,validate_idempotency_key,parse_strong_if_match,strong_etag)
from aos_api.asset_registry.installation_service import _load_current_lock,_require_lock_markings
from aos_api.asset_registry.installation_store import CommandResult,command_request_hash
from .disable_contracts import DisableTarget
from .lifecycle_store import RuntimeOperationStore,RuntimeConflict,_values
from .runtime_gate import _reject_deferred
from .configuration_request import load_configure_target,load_enable_target
from .disable_commit import begin_disable


class RuntimeDisableService:
    def __init__(self, *, installation_store, installation_reader, check_current_permission,
                 dependent=None):
        if not callable(check_current_permission):raise ValueError('current disable permission required')
        self._store=installation_store
        self._reader=installation_reader
        self._permission=check_current_permission
        self._dependent=dependent

    def request(self, *, installation_id, org_id, project_id, actor, roles, markings,
                idempotency_key, if_match, target):
        require_control_role(roles=roles,operation=APPLY_INSTALLATION_OPERATION)
        key=validate_idempotency_key(idempotency_key)
        etag,revision=parse_strong_if_match(if_match)
        installation_id=str(UUID(str(installation_id)))
        target=DisableTarget.model_validate(target)
        scope=dict(org_id=org_id,project_id=project_id)
        self._reader.get(installation_id=installation_id,**scope,roles=roles,markings=markings)

        def current_check(conn):
            row=conn.execute('''SELECT etag_version FROM bundle_installation
                WHERE org_id=%s AND project_id=%s AND installation_id=%s FOR UPDATE''',
                (org_id,project_id,UUID(installation_id))).fetchone()
            if row is None:raise LookupError('disable installation not found')
            locked=self._store.lock_for_transition_in_transaction(conn,**scope,installation_id=installation_id,
                expected_etag_version=_values(row,('etag_version',))[0])
            allowed=self._permission(conn=conn,locked=locked,actor=actor)
            _reject_deferred(allowed)
            if allowed is not True:raise PermissionError('current disable permission required')
            return True

        def handler(conn):
            locked=self._store.lock_for_transition_in_transaction(conn,**scope,installation_id=installation_id,
                expected_etag_version=revision)
            lock=_load_current_lock(conn,locked=locked,**scope)
            _require_lock_markings(lock,markings=markings,conceal=False)
            pending=conn.execute('''SELECT operation_id,kind,phase,status,revision FROM extension_runtime_operation
                WHERE org_id=%s AND project_id=%s AND installation_id=%s
                AND status NOT IN ('succeeded','failed','cancelled') ORDER BY operation_id FOR UPDATE''',
                (org_id,project_id,UUID(installation_id))).fetchall()
            # Only effect-free positive operations with this exact target can
            # be cancelled. Validate the full set before changing any record.
            for row in pending:
                op,kind,phase,status,prior_revision=_values(row,('operation_id','kind','phase','status','revision'))
                if kind not in ('configure','enable') or phase not in ('accepted','validating') or status not in ('accepted','running'):
                    raise RuntimeConflict('unresolved operation requires lifecycle reconciliation')
                reader=load_configure_target if kind=='configure' else load_enable_target
                previous=reader(conn,**scope,operation_id=op)
                if previous.generation!=target.generation or previous.bindingRevision!=target.bindingRevision:
                    raise RuntimeConflict('unresolved operation target differs from disable')
            clock=self._store.read_control_clock_in_transaction(conn)
            result=RuntimeOperationStore().accept(conn,**scope,installation_id=installation_id,kind='disable',
                idempotency_key=key,requested_by=actor,expected_installation_etag=revision,
                deadline=clock+timedelta(minutes=5),binding_target=target.model_dump(mode='json'))
            for row in pending:
                op,kind,phase,status,prior_revision=_values(row,('operation_id','kind','phase','status','revision'))
                conn.execute('''UPDATE extension_runtime_operation SET status='cancelled',revision=revision+1
                    WHERE org_id=%s AND project_id=%s AND operation_id=%s''',(org_id,project_id,op))
                RuntimeOperationStore()._event(conn,org_id,project_id,op,prior_revision+1,'cancelled_for_disable',
                    dict(previousPhase=phase,disableOperationId=str(result.operation_id),actor=actor))
            if pending:
                # Cancellation, disable receipt and fence are one commit; no
                # window where a cancelled positive operation leaves work open.
                result=begin_disable(conn,**scope,operation_id=result.operation_id,expected_revision=result.revision,
                    installation_store=self._store,check_current_permission=self._permission,
                    dependent=self._dependent)
            return CommandResult(status_code=202,response_json=dict(installationId=installation_id,
                operationId=str(result.operation_id),phase=result.phase,status=result.status,revision=result.revision),
                response_etag=strong_etag(result.revision))

        return self._store.execute_idempotent(**scope,operation=DISABLE_RUNTIME_OPERATION,idempotency_key=key,subject=actor,
            request_hash=command_request_hash(subject=actor,path_params={'installationId':installation_id},
                body={'target':target.model_dump(mode='json')},if_match=etag),current_check=current_check,handler=handler)
