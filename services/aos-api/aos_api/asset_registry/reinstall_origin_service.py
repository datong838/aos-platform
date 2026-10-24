"""Unwired reinstall orchestration; concrete origin authority is mandatory."""
from __future__ import annotations

import asyncio
import inspect
from collections.abc import Collection
from typing import Any, Protocol

from aos_api.asset_registry.composition_contracts import (
    CreateInstallationRequest, InstallationRecord, StoredCompositionLock,
)
from aos_api.asset_registry.composition_store import load_stored_lock
from aos_api.asset_registry.control_policy import (
    REINSTALL_INSTALLATION_OPERATION, parse_strong_if_match,
    require_control_role, validate_idempotency_key,
)
from aos_api.asset_registry.errors import (
    InstallationStateConflictError, LockIntegrityCorruptError, RevisionConflictError,
)
from aos_api.asset_registry.installation_service import (
    InstallationService, _canonical_installation_id, _command_result,
    _load_current_lock, _require_lock_markings,
)
from aos_api.asset_registry.installation_evidence import verify_event_evidence
from aos_api.asset_registry.installation_store import (
    CommandReceipt, CommandResult, LockedInstallation,
    PostgresInstallationStore, command_request_hash,
)
from aos_api.asset_registry.reinstall_contracts import (
    ReinstallInstallationRequest, ReinstallSourceRef,
)
from aos_api.tenant_scope import TenantScope


class ReinstallOriginPort(Protocol):
    """Trusted same-transaction authority/append port, never client input.

    check_current must hold current source/target permission and revocation
    barriers, verify native terminal authority for every supported branch,
    and reject missing/unknown obligations. It must NOT call a write-type
    uninstall command. Runtime receipts refer to terminal_revision minus one.
    append_origin must append the immutable exact same-tenant source/draft
    relation on conn; neither method may commit, reconnect or mutate inputs.
    A structural implementation is NOT production qualification. No App
    wiring is permitted without independently qualified concrete persistence.
    """

    def check_current(
        self, conn: Any, *, org_id: str, project_id: str, actor: str,
        markings: Collection[str], source: ReinstallSourceRef,
        locked_source: LockedInstallation, source_lock: StoredCompositionLock,
        target: CreateInstallationRequest, target_lock: StoredCompositionLock,
    ) -> bool: ...

    def append_origin(
        self, conn: Any, *, org_id: str, project_id: str, actor: str,
        source: ReinstallSourceRef, locked_source: LockedInstallation,
        target_record: InstallationRecord,
    ) -> None: ...


class ReinstallOriginService:
    """Reuse the original executor; no default origin store or runtime wiring."""

    def __init__(
        self, *, store: PostgresInstallationStore,
        installation_service: InstallationService, origin_store: ReinstallOriginPort,
    ) -> None:
        if (type(store) is not PostgresInstallationStore
                or type(installation_service) is not InstallationService
                or installation_service._store is not store):
            raise ValueError("original installation command graph required")
        for name in ("check_current", "append_origin"):
            method = getattr(origin_store, name, None)
            if (not callable(method) or inspect.iscoroutinefunction(method)
                    or inspect.isgeneratorfunction(method)
                    or inspect.isasyncgenfunction(method)):
                raise ValueError("synchronous trusted origin persistence required")
        self._store = store
        self._installation_service = installation_service
        self._origin_store = origin_store

    def reinstall(
        self, *, installation_id: str,
        request: ReinstallInstallationRequest | dict[str, Any],
        org_id: str, project_id: str, actor: str,
        roles: Collection[str], markings: Collection[str],
        idempotency_key: str | None, if_match: str | None,
    ) -> CommandReceipt:
        TenantScope(org_id, project_id)
        if type(request) not in (ReinstallInstallationRequest, dict):
            raise ValueError("exact reinstall request required")
        request = ReinstallInstallationRequest.model_validate(request)
        installation_id = _canonical_installation_id(installation_id)
        matched_header, expected_version = parse_strong_if_match(if_match)
        if (installation_id != request.source.installation_id
                or expected_version != request.source.terminal_revision):
            raise RevisionConflictError("reinstall source precondition differs")
        roles, markings = tuple(roles), tuple(markings)
        require_control_role(roles=roles, operation=REINSTALL_INSTALLATION_OPERATION)
        key = validate_idempotency_key(idempotency_key)
        digest = command_request_hash(
            subject=actor, path_params={"installationId": installation_id},
            body=request.model_dump(mode="json", by_alias=True), if_match=matched_header,
        )
        checked_source: LockedInstallation | None = None

        def current_check(conn: Any) -> bool:
            nonlocal checked_source
            locked = self._store.lock_for_transition_in_transaction(
                conn, org_id=org_id, project_id=project_id,
                installation_id=installation_id, expected_etag_version=expected_version,
            )
            record = locked.record
            if record.state != "uninstalled":
                raise InstallationStateConflictError("terminal uninstall source required")
            if (record.installation_id != installation_id
                    or record.current_revision != expected_version
                    or record.etag_version != expected_version
                    or record.current.lock_hash != request.source.lock_hash):
                raise LockIntegrityCorruptError()
            source_lock = _load_current_lock(
                conn, locked=locked, org_id=org_id, project_id=project_id,
            )
            tail = record.events[-1]
            if (tail.evidence is None or tail.evidence.type != "uninstall"
                    or record.decision is None):
                raise LockIntegrityCorruptError()
            try:
                verify_event_evidence(
                    tail.evidence, installation_id=installation_id,
                    from_revision=tail.from_revision, to_revision=tail.to_revision,
                    lock_hash=record.current.lock_hash,
                    permission_diff_hash=record.current.permission_diff_hash,
                    migration_plan_hash=record.current.migration_plan_hash,
                    contribution_diff_hash=record.current.contribution_diff_hash,
                    decision_id=record.decision.decision_id,
                    observed_at=tail.evidence.observed_at, from_state=tail.from_state,
                )
            except (TypeError, ValueError) as exc:
                raise LockIntegrityCorruptError() from exc
            _require_lock_markings(source_lock, markings=markings, conceal=False)
            _, target_lock = load_stored_lock(
                conn, org_id=org_id, project_id=project_id,
                composition_id=request.target.composition_id,
                revision=request.target.lock_revision,
            )
            _require_lock_markings(target_lock, markings=markings, conceal=False)
            checked_source = locked
            return self._origin_store.check_current(
                conn, org_id=org_id, project_id=project_id, actor=actor,
                markings=markings, source=request.source, locked_source=locked,
                source_lock=source_lock, target=request.target, target_lock=target_lock,
            )

        def handler(conn: Any) -> CommandResult:
            if checked_source is None:
                raise LockIntegrityCorruptError()
            record = self._store.create_draft_in_transaction(
                conn, org_id=org_id, project_id=project_id,
                request=request.target, requested_by=actor,
            )
            appended = self._origin_store.append_origin(
                conn, org_id=org_id, project_id=project_id, actor=actor,
                source=request.source, locked_source=checked_source, target_record=record,
            )
            if appended is not None:
                if isinstance(appended, asyncio.Future):
                    appended.cancel()
                if inspect.iscoroutine(appended) or inspect.isgenerator(appended):
                    appended.close()
                raise ValueError("origin append must complete synchronously with None")
            return _command_result(record, status_code=201)

        receipt = self._store.execute_idempotent(
            org_id=org_id, project_id=project_id,
            operation=REINSTALL_INSTALLATION_OPERATION, idempotency_key=key,
            subject=actor, request_hash=digest, current_check=current_check, handler=handler,
        )
        self._installation_service._authorize_receipt(
            receipt, org_id=org_id, project_id=project_id, markings=markings,
        )
        return receipt
