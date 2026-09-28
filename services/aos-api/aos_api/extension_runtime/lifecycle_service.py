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
