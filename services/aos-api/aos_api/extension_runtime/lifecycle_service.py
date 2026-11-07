"""Authorized preparation requests using the existing Installation receipt authority."""
from datetime import timedelta
from uuid import UUID

from aos_api.asset_registry.control_policy import (
    APPLY_INSTALLATION_OPERATION, VERIFY_INSTALLATION_OPERATION, require_control_role,
    validate_idempotency_key, parse_strong_if_match, strong_etag,
)
from aos_api.asset_registry.installation_service import _load_current_lock, _require_lock_markings
from aos_api.asset_registry.installation_store import CommandResult, command_request_hash
from aos_api.extension_runtime.lifecycle_store import RuntimeOperationStore, RuntimeConflict


class RuntimeLifecycleService:
    def __init__(self, *, installation_store, installation_reader, revalidator):
        self._store=installation_store
        self._reader=installation_reader
        self._revalidator=revalidator

    def request_recovery(self, *, installation_id, org_id, project_id, actor, roles,
                         markings, idempotency_key, if_match, recovery_admission):
        from aos_api.tenant_scope import TenantScope
        from aos_api.asset_registry.composition_contracts import CurrentInstallationRef
        from .recovery_contracts import ReleasedRecoveryTarget
        from .lifecycle_store import _values
        require_control_role(roles=roles,operation=APPLY_INSTALLATION_OPERATION)
        key=validate_idempotency_key(idempotency_key)
        etag,revision=parse_strong_if_match(if_match)
        installation_id=str(UUID(str(installation_id)))
        scope=TenantScope(org_id,project_id)
        self._reader.get(installation_id=installation_id,org_id=org_id,project_id=project_id,
                         roles=roles,markings=markings)

        def current_context():
            try:value=recovery_admission()
            except Exception:value=None
            if type(value) is not str or not value or value!=value.strip():
                raise RuntimeConflict('current runtime host recovery assignment unavailable')
            return value

        def handler(conn):
            locked=self._store.lock_for_transition_in_transaction(conn,org_id=org_id,project_id=project_id,
                installation_id=installation_id,expected_etag_version=revision)
            lock=_load_current_lock(conn,locked=locked,org_id=org_id,project_id=project_id)
            _require_lock_markings(lock,markings=markings,conceal=False)
            context=current_context()
            candidate=self.inspect_released_recovery_in_transaction(conn=conn,scope=scope,
                installation_id=installation_id,expected_etag=revision,actor=actor,engine_context=context)
            binding=conn.execute('''SELECT revision FROM extension_runtime_binding
                WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s FOR UPDATE''',
                (org_id,project_id,UUID(installation_id),candidate.source_generation)).fetchone()
            if binding is None:raise RuntimeConflict('current recovery binding unavailable')
            record=locked.record
            target=ReleasedRecoveryTarget(sourceRef=CurrentInstallationRef(installationId=installation_id,
                revision=record.current_revision,lockHash=record.current.lock_hash,
                overlayRevision=record.current.overlay_revision),generation=str(candidate.source_generation),
                bindingRevision=_values(binding,('revision',))[0],executionEpoch=candidate.source_execution_epoch,
                preparationOperationId=str(candidate.preparation_operation_id),
                verificationOperationId=str(candidate.verification_operation_id),
                resourceIds=[str(value) for value in candidate.resource_ids])
            if current_context()!=context:
                raise RuntimeConflict('runtime recovery assignment changed')
            result=RuntimeOperationStore().accept(conn,org_id=org_id,project_id=project_id,
                installation_id=installation_id,kind='runtime-recover',idempotency_key=key,requested_by=actor,
                expected_installation_etag=revision,
                deadline=self._store.read_control_clock_in_transaction(conn)+timedelta(minutes=5),
                recovery_target=target.model_dump(mode='json',by_alias=True))
            return CommandResult(status_code=202,response_json=dict(installationId=installation_id,
                operationId=str(result.operation_id),phase=result.phase,status=result.status,revision=result.revision),
                response_etag=strong_etag(result.revision))

        return self._store.execute_idempotent(org_id=org_id,project_id=project_id,
            operation='runtime_installations.runtime-recover',idempotency_key=key,subject=actor,
            request_hash=command_request_hash(subject=actor,path_params={'installationId':installation_id},
                body={'kind':'runtime-recover'},if_match=etag),handler=handler)

    def inspect_released_recovery_in_transaction(self, *, conn, scope, installation_id,
            expected_etag, actor, engine_context):
        from .released_preparation_recovery import inspect_released_preparation_recovery
        from .current_permission import CurrentControlPermission
        return inspect_released_preparation_recovery(conn=conn, installation_store=self._store,
            revalidator=self._revalidator,
            check_current_permission=CurrentControlPermission(operation=APPLY_INSTALLATION_OPERATION),
            scope=scope, installation_id=installation_id, expected_etag=expected_etag,
            actor=actor, engine_context=engine_context)

    def reset_preparation(self, *, installation_id, org_id, project_id, actor,
                          roles, markings, idempotency_key, if_match):
        from .preparation_reset import reset_preparation
        from .current_permission import CurrentControlPermission
        require_control_role(roles=roles, operation=APPLY_INSTALLATION_OPERATION)
        key = validate_idempotency_key(idempotency_key)
        etag, revision = parse_strong_if_match(if_match)
        installation_id = str(UUID(str(installation_id)))
        self._reader.get(installation_id=installation_id, org_id=org_id,
                         project_id=project_id, roles=roles, markings=markings)

        def handler(conn):
            record = reset_preparation(conn, installation_store=self._store,
                check_current_permission=CurrentControlPermission(operation=APPLY_INSTALLATION_OPERATION),
                org_id=org_id, project_id=project_id, installation_id=installation_id,
                expected_etag=revision, actor=actor)
            return CommandResult(status_code=200, response_json={
                "installationId": installation_id, "state": record.state,
                "revision": record.current_revision}, response_etag=strong_etag(record.etag_version))

        return self._store.execute_idempotent(org_id=org_id, project_id=project_id,
            operation="runtime_installations.preparation-reset", idempotency_key=key,
            subject=actor, request_hash=command_request_hash(subject=actor,
                path_params={"installationId": installation_id}, body={"kind": "preparation-reset"},
                if_match=etag), handler=handler)

    def request_preparation(self, *, installation_id, kind, org_id, project_id, actor,
                            roles, markings, idempotency_key, if_match,
                            preparation_admission):
        operations={"runtime-apply":(APPLY_INSTALLATION_OPERATION,"approved"),
                    "runtime-verify":(VERIFY_INSTALLATION_OPERATION,"applied")}
        if kind not in operations:
            raise ValueError("unsupported preparation operation")
        permission,required_state=operations[kind]
        require_control_role(roles=roles,operation=permission)
        key=validate_idempotency_key(idempotency_key)
        etag,revision=parse_strong_if_match(if_match)
        installation_id=str(UUID(str(installation_id)))
        # Replays must not disclose a receipt after the caller loses current access.
        self._reader.get(installation_id=installation_id,org_id=org_id,project_id=project_id,
                         roles=roles,markings=markings)

        def handler(conn):
            locked=self._store.lock_for_transition_in_transaction(conn,org_id=org_id,project_id=project_id,
                installation_id=installation_id,expected_etag_version=revision)
            lock=_load_current_lock(conn,locked=locked,org_id=org_id,project_id=project_id)
            _require_lock_markings(lock,markings=markings,conceal=False)
            if locked.record.state!=required_state:
                raise RuntimeConflict("installation state does not permit preparation")
            active=conn.execute("""SELECT operation_id FROM extension_runtime_operation
                WHERE org_id=%s AND project_id=%s AND installation_id=%s
                AND status NOT IN ('succeeded','failed','cancelled') LIMIT 1""",
                (org_id,project_id,UUID(installation_id))).fetchone()
            if active is not None:
                raise RuntimeConflict("installation already has an unresolved operation")
            checked=self._revalidator.revalidate_in_transaction(conn,lock=lock)
            if not checked.runtime_members:
                raise RuntimeConflict("pure content uses the existing installation workflow")
            try:
                admitted = preparation_admission() is True
            except Exception:
                admitted = False
            if not admitted:
                raise RuntimeConflict("current runtime host preparation assignment unavailable")
            result=RuntimeOperationStore().accept(conn,org_id=org_id,project_id=project_id,
                installation_id=installation_id,kind=kind,idempotency_key=key,requested_by=actor,
                expected_installation_etag=revision,deadline=checked.checked_at+timedelta(minutes=5))
            return CommandResult(status_code=202,response_json={"installationId":installation_id,
                "operationId":str(result.operation_id),"phase":result.phase,"status":result.status,
                "revision":result.revision},response_etag=strong_etag(result.revision))

        return self._store.execute_idempotent(org_id=org_id,project_id=project_id,
            operation="runtime_installations."+kind,idempotency_key=key,subject=actor,
            request_hash=command_request_hash(subject=actor,path_params={"installationId":installation_id},
                body={"kind":kind},if_match=etag),handler=handler)
