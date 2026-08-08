"""M2-B installation control service with transactional revalidation."""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Collection
from typing import Any

from pydantic import ValidationError

from aos_api.asset_registry.composition_contracts import (
    ApproveInstallationRequest,
    CreateInstallationRequest,
    EmptyInstallationActionRequest,
    InstallationListQuery,
    InstallationListResponse,
    InstallationRecord,
    InstallationResponse,
    RejectInstallationRequest,
    RollbackInstallationRequest,
    StoredCompositionLock,
    UninstallInstallationRequest,
)
from aos_api.asset_registry.composition_store import load_stored_lock
from aos_api.asset_registry.control_policy import (
    APPLY_INSTALLATION_OPERATION,
    APPROVE_INSTALLATION_OPERATION,
    CREATE_INSTALLATION_OPERATION,
    REJECT_INSTALLATION_OPERATION,
    ROLLBACK_INSTALLATION_OPERATION,
    SUBMIT_INSTALLATION_OPERATION,
    UNINSTALL_INSTALLATION_OPERATION,
    VERIFY_INSTALLATION_OPERATION,
    parse_strong_if_match,
    require_control_read_role,
    require_control_role,
    require_target_markings,
    strong_etag,
    validate_idempotency_key,
)
from aos_api.asset_registry.errors import LockIntegrityCorruptError
from aos_api.asset_registry.installation_evidence import build_event_evidence
from aos_api.asset_registry.installation_revalidation import InstallationRevalidator
from aos_api.asset_registry.installation_store import (
    CommandReceipt,
    CommandResult,
    LockedInstallation,
    PostgresInstallationStore,
    command_request_hash,
)


class InstallationService:
    """Authorize, revalidate, and persist the frozen installation lifecycle."""

    def __init__(
        self,
        *,
        store: PostgresInstallationStore,
        composition_store: Any,
        revalidator: InstallationRevalidator,
    ) -> None:
        self._store = store
        self._composition_store = composition_store
        self._revalidator = revalidator

    def create(
        self,
        *,
        request: CreateInstallationRequest,
        org_id: str,
        project_id: str,
        actor: str,
        roles: Collection[str],
        markings: Collection[str],
        idempotency_key: str | None,
    ) -> CommandReceipt:
        request = CreateInstallationRequest.model_validate(request)
        require_control_role(roles=roles, operation=CREATE_INSTALLATION_OPERATION)
        key = validate_idempotency_key(idempotency_key)

        def handler(conn: Any) -> CommandResult:
            _, lock = load_stored_lock(
                conn,
                org_id=org_id,
                project_id=project_id,
                composition_id=request.composition_id,
                revision=request.lock_revision,
            )
            _require_lock_markings(lock, markings=markings, conceal=False)
            record = self._store.create_draft_in_transaction(
                conn,
                org_id=org_id,
                project_id=project_id,
                request=request,
                requested_by=actor,
            )
            return _command_result(record, status_code=201)

        receipt = self._execute(
            operation=CREATE_INSTALLATION_OPERATION,
            org_id=org_id,
            project_id=project_id,
            actor=actor,
            idempotency_key=key,
            path_params={},
            body=request.model_dump(mode="json", by_alias=True),
            if_match=None,
            handler=handler,
        )
        self._authorize_receipt(
            receipt,
            org_id=org_id,
            project_id=project_id,
            markings=markings,
        )
        return receipt

    def list(
        self,
        *,
        query: InstallationListQuery,
        org_id: str,
        project_id: str,
        roles: Collection[str],
        markings: Collection[str],
    ) -> InstallationListResponse:
        require_control_read_role(roles=roles)
        return self._store.list_visible_installations(
            org_id=org_id,
            project_id=project_id,
            query=InstallationListQuery.model_validate(query),
            allowed_markings=markings,
        )

    def get(
        self,
        *,
        installation_id: str,
        org_id: str,
        project_id: str,
        roles: Collection[str],
        markings: Collection[str],
    ) -> InstallationResponse:
        require_control_read_role(roles=roles)
        record = self._store.get_installation(
            org_id=org_id,
            project_id=project_id,
            installation_id=_canonical_installation_id(installation_id),
        )
        response = _response_from_record(record)
        self._authorize_response(
            response,
            org_id=org_id,
            project_id=project_id,
            markings=markings,
            conceal=True,
        )
        return response

    def submit(
        self,
        *,
        installation_id: str,
        request: EmptyInstallationActionRequest,
        org_id: str,
        project_id: str,
        actor: str,
        roles: Collection[str],
        markings: Collection[str],
        idempotency_key: str | None,
        if_match: str | None,
    ) -> CommandReceipt:
        return self._transition(
            operation=SUBMIT_INSTALLATION_OPERATION,
            request_type=EmptyInstallationActionRequest,
            mutate=lambda conn, locked, request, actor, lock: (
                self._store.append_submit_in_transaction(
                    conn, locked=locked, actor=actor
                )
            ),
            revalidate=True,
            installation_id=installation_id,
            request=request,
            org_id=org_id,
            project_id=project_id,
            actor=actor,
            roles=roles,
            markings=markings,
            idempotency_key=idempotency_key,
            if_match=if_match,
        )

    def approve(
        self,
        *,
        installation_id: str,
        request: ApproveInstallationRequest,
        org_id: str,
        project_id: str,
        actor: str,
        roles: Collection[str],
        markings: Collection[str],
        idempotency_key: str | None,
        if_match: str | None,
    ) -> CommandReceipt:
        return self._transition(
            operation=APPROVE_INSTALLATION_OPERATION,
            request_type=ApproveInstallationRequest,
            mutate=lambda conn, locked, request, actor, lock: (
                self._store.append_approval_in_transaction(
                    conn, locked=locked, actor=actor, request=request
                )
            ),
            revalidate=True,
            installation_id=installation_id,
            request=request,
            org_id=org_id,
            project_id=project_id,
            actor=actor,
            roles=roles,
            markings=markings,
            idempotency_key=idempotency_key,
            if_match=if_match,
        )

    def reject(
        self,
        *,
        installation_id: str,
        request: RejectInstallationRequest,
        org_id: str,
        project_id: str,
        actor: str,
        roles: Collection[str],
        markings: Collection[str],
        idempotency_key: str | None,
        if_match: str | None,
    ) -> CommandReceipt:
        return self._transition(
            operation=REJECT_INSTALLATION_OPERATION,
            request_type=RejectInstallationRequest,
            mutate=lambda conn, locked, request, actor, lock: (
                self._store.append_rejection_in_transaction(
                    conn, locked=locked, actor=actor, reason=request.reason
                )
            ),
            revalidate=False,
            installation_id=installation_id,
            request=request,
            org_id=org_id,
            project_id=project_id,
            actor=actor,
            roles=roles,
            markings=markings,
            idempotency_key=idempotency_key,
            if_match=if_match,
        )

    def apply(
        self,
        *,
        installation_id: str,
        request: EmptyInstallationActionRequest,
        org_id: str,
        project_id: str,
        actor: str,
        roles: Collection[str],
        markings: Collection[str],
        idempotency_key: str | None,
        if_match: str | None,
    ) -> CommandReceipt:
        return self._transition(
            operation=APPLY_INSTALLATION_OPERATION,
            request_type=EmptyInstallationActionRequest,
            mutate=self._append_apply,
            revalidate=False,
            installation_id=installation_id,
            request=request,
            org_id=org_id,
            project_id=project_id,
            actor=actor,
            roles=roles,
            markings=markings,
            idempotency_key=idempotency_key,
            if_match=if_match,
        )

    def verify(
        self,
        *,
        installation_id: str,
        request: EmptyInstallationActionRequest,
        org_id: str,
        project_id: str,
        actor: str,
        roles: Collection[str],
        markings: Collection[str],
        idempotency_key: str | None,
        if_match: str | None,
    ) -> CommandReceipt:
        return self._transition(
            operation=VERIFY_INSTALLATION_OPERATION,
            request_type=EmptyInstallationActionRequest,
            mutate=self._append_verify,
            revalidate=False,
            installation_id=installation_id,
            request=request,
            org_id=org_id,
            project_id=project_id,
            actor=actor,
            roles=roles,
            markings=markings,
            idempotency_key=idempotency_key,
            if_match=if_match,
        )

    def rollback(
        self,
        *,
        installation_id: str,
        request: RollbackInstallationRequest,
        org_id: str,
        project_id: str,
        actor: str,
        roles: Collection[str],
        markings: Collection[str],
        idempotency_key: str | None,
        if_match: str | None,
    ) -> CommandReceipt:
        return self._transition(
            operation=ROLLBACK_INSTALLATION_OPERATION,
            request_type=RollbackInstallationRequest,
            mutate=self._append_rollback,
            revalidate=False,
            installation_id=installation_id,
            request=request,
            org_id=org_id,
            project_id=project_id,
            actor=actor,
            roles=roles,
            markings=markings,
            idempotency_key=idempotency_key,
            if_match=if_match,
        )

    def uninstall(
        self,
        *,
        installation_id: str,
        request: UninstallInstallationRequest,
        org_id: str,
        project_id: str,
        actor: str,
        roles: Collection[str],
        markings: Collection[str],
        idempotency_key: str | None,
        if_match: str | None,
    ) -> CommandReceipt:
        return self._transition(
            operation=UNINSTALL_INSTALLATION_OPERATION,
            request_type=UninstallInstallationRequest,
            mutate=self._append_uninstall,
            revalidate=False,
            installation_id=installation_id,
            request=request,
            org_id=org_id,
            project_id=project_id,
            actor=actor,
            roles=roles,
            markings=markings,
            idempotency_key=idempotency_key,
            if_match=if_match,
        )

    def _transition(
        self,
        *,
        operation: str,
        request_type: type,
        mutate: Callable[
            [Any, LockedInstallation, Any, str, StoredCompositionLock],
            InstallationRecord,
        ],
        revalidate: bool,
        installation_id: str,
        request: Any,
        org_id: str,
        project_id: str,
        actor: str,
        roles: Collection[str],
        markings: Collection[str],
        idempotency_key: str | None,
        if_match: str | None,
    ) -> CommandReceipt:
        installation_id = _canonical_installation_id(installation_id)
        request = request_type.model_validate(request)
        require_control_role(roles=roles, operation=operation)
        key = validate_idempotency_key(idempotency_key)
        matched_etag, expected_version = parse_strong_if_match(if_match)

        def handler(conn: Any) -> CommandResult:
            locked = self._store.lock_for_transition_in_transaction(
                conn,
                org_id=org_id,
                project_id=project_id,
                installation_id=installation_id,
                expected_etag_version=expected_version,
            )
            lock = _load_current_lock(
                conn, locked=locked, org_id=org_id, project_id=project_id
            )
            _require_lock_markings(lock, markings=markings, conceal=False)
            if revalidate:
                self._revalidator.revalidate_in_transaction(conn, lock=lock)
            record = mutate(conn, locked, request, actor, lock)
            return _command_result(record, status_code=200)

        receipt = self._execute(
            operation=operation,
            org_id=org_id,
            project_id=project_id,
            actor=actor,
            idempotency_key=key,
            path_params={"installationId": installation_id},
            body=request.model_dump(mode="json", by_alias=True),
            if_match=matched_etag,
            handler=handler,
        )
        self._authorize_receipt(
            receipt,
            org_id=org_id,
            project_id=project_id,
            markings=markings,
        )
        return receipt

    def _execute(
        self,
        *,
        operation: str,
        org_id: str,
        project_id: str,
        actor: str,
        idempotency_key: str,
        path_params: dict[str, object],
        body: dict[str, object],
        if_match: str | None,
        handler: Callable[[Any], CommandResult],
    ) -> CommandReceipt:
        return self._store.execute_idempotent(
            org_id=org_id,
            project_id=project_id,
            operation=operation,
            idempotency_key=idempotency_key,
            subject=actor,
            request_hash=command_request_hash(
                subject=actor,
                path_params=path_params,
                body=body,
                if_match=if_match,
            ),
            handler=handler,
        )

    def _authorize_receipt(
        self,
        receipt: CommandReceipt,
        *,
        org_id: str,
        project_id: str,
        markings: Collection[str],
    ) -> InstallationResponse:
        try:
            response = InstallationResponse.model_validate_json(
                json.dumps(receipt.response_json)
            )
        except (TypeError, ValueError, ValidationError) as exc:
            raise LockIntegrityCorruptError() from exc
        if receipt.response_etag != strong_etag(response.etag_version):
            raise LockIntegrityCorruptError()
        self._authorize_response(
            response,
            org_id=org_id,
            project_id=project_id,
            markings=markings,
            conceal=False,
        )
        return response

    def _authorize_response(
        self,
        response: InstallationResponse,
        *,
        org_id: str,
        project_id: str,
        markings: Collection[str],
        conceal: bool,
    ) -> None:
        lock = self._composition_store.get_lock(
            org_id=org_id,
            project_id=project_id,
            composition_id=response.current.composition_id,
            revision=response.current.lock_revision,
        )
        _require_lock_markings(lock, markings=markings, conceal=conceal)

    def _append_apply(
        self,
        conn: Any,
        locked: LockedInstallation,
        request: EmptyInstallationActionRequest,
        actor: str,
        lock: StoredCompositionLock,
    ) -> InstallationRecord:
        checked_at = self._revalidator.revalidate_in_transaction(
            conn, lock=lock
        ).checked_at
        return self._store.append_apply_in_transaction(
            conn,
            locked=locked,
            actor=actor,
            evidence=_evidence("dry_apply", locked, checked_at),
        )

    def _append_verify(
        self,
        conn: Any,
        locked: LockedInstallation,
        request: EmptyInstallationActionRequest,
        actor: str,
        lock: StoredCompositionLock,
    ) -> InstallationRecord:
        checked_at = self._revalidator.revalidate_in_transaction(
            conn, lock=lock
        ).checked_at
        return self._store.append_verify_in_transaction(
            conn,
            locked=locked,
            actor=actor,
            evidence=_evidence("verification", locked, checked_at),
        )

    def _append_rollback(
        self,
        conn: Any,
        locked: LockedInstallation,
        request: RollbackInstallationRequest,
        actor: str,
        lock: StoredCompositionLock,
    ) -> InstallationRecord:
        checked_at = self._store.read_control_clock_in_transaction(conn)
        return self._store.append_rollback_in_transaction(
            conn,
            locked=locked,
            actor=actor,
            reason=request.reason,
            evidence=_evidence("rollback", locked, checked_at),
        )

    def _append_uninstall(
        self,
        conn: Any,
        locked: LockedInstallation,
        request: UninstallInstallationRequest,
        actor: str,
        lock: StoredCompositionLock,
    ) -> InstallationRecord:
        checked_at = self._store.read_control_clock_in_transaction(conn)
        return self._store.append_uninstall_in_transaction(
            conn,
            locked=locked,
            actor=actor,
            reason=request.reason,
            evidence=_evidence("uninstall", locked, checked_at),
        )


def _command_result(record: InstallationRecord, *, status_code: int) -> CommandResult:
    response = _response_from_record(record)
    return CommandResult(
        status_code=status_code,
        response_json=response.model_dump(mode="json", by_alias=True),
        response_etag=strong_etag(response.etag_version),
    )


def _response_from_record(record: InstallationRecord) -> InstallationResponse:
    try:
        return InstallationResponse.model_validate(
            record.model_dump(mode="python", by_alias=True)
        )
    except (TypeError, ValueError, ValidationError) as exc:
        raise LockIntegrityCorruptError() from exc


def _load_current_lock(
    conn: Any,
    *,
    locked: LockedInstallation,
    org_id: str,
    project_id: str,
) -> StoredCompositionLock:
    _, lock = load_stored_lock(
        conn,
        org_id=org_id,
        project_id=project_id,
        composition_id=locked.record.current.composition_id,
        revision=locked.record.current.lock_revision,
    )
    current = locked.record.current
    if (
        current.lock_hash,
        current.permission_diff_hash,
        current.migration_plan_hash,
        current.contribution_diff_hash,
    ) != (
        lock.lock_hash,
        lock.permission_diff_hash,
        lock.migration_plan_hash,
        lock.contribution_diff_hash,
    ):
        raise LockIntegrityCorruptError()
    return lock


def _evidence(
    evidence_type: str,
    locked: LockedInstallation,
    observed_at: Any,
):
    current = locked.record.current
    if locked.record.decision is None:
        raise LockIntegrityCorruptError()
    return build_event_evidence(
        evidence_type=evidence_type,
        installation_id=locked.record.installation_id,
        from_revision=current.revision,
        to_revision=current.revision + 1,
        lock_hash=current.lock_hash,
        permission_diff_hash=current.permission_diff_hash,
        migration_plan_hash=current.migration_plan_hash,
        contribution_diff_hash=current.contribution_diff_hash,
        decision_id=locked.record.decision.decision_id,
        observed_at=observed_at,
    )


def _require_lock_markings(
    lock: StoredCompositionLock,
    *,
    markings: Collection[str],
    conceal: bool,
) -> None:
    try:
        require_target_markings(
            principal_markings=markings,
            target_markings=lock.payload.permission_diff.target.markings,
            conceal=conceal,
        )
    except (TypeError, ValueError) as exc:
        raise LockIntegrityCorruptError() from exc


def _canonical_installation_id(value: str) -> str:
    try:
        parsed = uuid.UUID(value)
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("installationId must be a UUID") from exc
    if str(parsed) != value:
        raise ValueError("installationId must use canonical lowercase UUID form")
    return value
