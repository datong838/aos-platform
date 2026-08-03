"""M2-B composition control service with receipt-first idempotency."""

from __future__ import annotations

from collections.abc import Callable, Collection
from copy import deepcopy
from datetime import datetime
from typing import Any, Protocol

from pydantic import ValidationError

from aos_api.asset_registry.composition_contracts import (
    CompositionLockPayload,
    CompositionRequest,
    RegistrySnapshot,
    StoredCompositionLock,
)
from aos_api.asset_registry.control_policy import (
    RESOLVE_OPERATION,
    require_control_read_role,
    require_control_role,
    require_target_markings,
    validate_idempotency_key,
)
from aos_api.asset_registry.control_protocols import (
    ActiveBaselineReader,
    IdempotentCommandStore,
)
from aos_api.asset_registry.errors import (
    CurrentInstallationStaleError,
    LockIntegrityCorruptError,
)
from aos_api.asset_registry.installation_store import (
    CommandReceipt,
    CommandResult,
    command_request_hash,
)
from aos_api.asset_registry.resolver import resolve


class SnapshotReader(Protocol):
    def read(self) -> RegistrySnapshot: ...


class CompositionPersistence(Protocol):
    def create_or_get_in_transaction(
        self,
        conn: Any,
        *,
        org_id: str,
        project_id: str,
        request: CompositionRequest,
        snapshot: RegistrySnapshot,
        payload: CompositionLockPayload,
        created_by: str,
    ) -> StoredCompositionLock: ...

    def get_lock(
        self,
        *,
        org_id: str,
        project_id: str,
        composition_id: str,
        revision: int = 1,
    ) -> StoredCompositionLock: ...


Resolver = Callable[
    [CompositionRequest, RegistrySnapshot, CompositionLockPayload | None],
    CompositionLockPayload,
]


class CompositionService:
    """Resolve immutable locks and authorize every first/replayed response."""

    def __init__(
        self,
        *,
        snapshot_reader: SnapshotReader,
        composition_store: CompositionPersistence,
        command_store: IdempotentCommandStore,
        baseline_reader: ActiveBaselineReader,
        resolver: Resolver = resolve,
    ) -> None:
        self._snapshot_reader = snapshot_reader
        self._composition_store = composition_store
        self._command_store = command_store
        self._baseline_reader = baseline_reader
        self._resolver = resolver

    def resolve(
        self,
        *,
        request: CompositionRequest,
        org_id: str,
        project_id: str,
        actor: str,
        roles: Collection[str],
        markings: Collection[str],
        idempotency_key: str | None,
    ) -> CommandReceipt:
        request = CompositionRequest.model_validate(request)
        require_control_role(roles=roles, operation=RESOLVE_OPERATION)
        key = validate_idempotency_key(idempotency_key)
        request_hash = command_request_hash(
            subject=actor,
            path_params={},
            body=request.model_dump(mode="json", by_alias=True, exclude_none=False),
            if_match=None,
        )

        def handler(conn: Any) -> CommandResult:
            baseline_payload: CompositionLockPayload | None = None
            effective_request = request
            if request.current_installation_ref is not None:
                baseline = self._baseline_reader.load_active_baseline_in_transaction(
                    conn,
                    org_id=org_id,
                    project_id=project_id,
                    requested_ref=request.current_installation_ref,
                )
                if baseline.lock.payload.request.environment != request.environment:
                    raise CurrentInstallationStaleError(
                        "current installation baseline environment is stale"
                    )
                baseline_payload = baseline.lock.payload
                effective_payload = request.model_dump(
                    mode="python", by_alias=True, exclude_none=False
                )
                effective_payload["currentInstallationRef"] = (
                    baseline.server_ref.model_dump(
                        mode="python", by_alias=True, exclude_none=False
                    )
                )
                effective_request = CompositionRequest.model_validate(effective_payload)

            snapshot = self._snapshot_reader.read()
            payload = self._resolver(
                effective_request,
                snapshot,
                baseline_payload,
            )
            _require_lock_markings(payload, markings=markings, conceal=False)
            stored = self._composition_store.create_or_get_in_transaction(
                conn,
                org_id=org_id,
                project_id=project_id,
                request=effective_request,
                snapshot=snapshot,
                payload=payload,
                created_by=actor,
            )
            return CommandResult(
                status_code=201,
                response_json=stored.model_dump(
                    mode="json", by_alias=True, exclude_none=False
                ),
            )

        receipt = self._command_store.execute_idempotent(
            org_id=org_id,
            project_id=project_id,
            operation=RESOLVE_OPERATION,
            idempotency_key=key,
            subject=actor,
            request_hash=request_hash,
            handler=handler,
        )
        stored = _stored_lock_from_receipt(receipt)
        _require_lock_markings(stored.payload, markings=markings, conceal=False)
        return receipt

    def get_lock(
        self,
        *,
        org_id: str,
        project_id: str,
        composition_id: str,
        revision: int,
        roles: Collection[str],
        markings: Collection[str],
    ) -> StoredCompositionLock:
        require_control_read_role(roles=roles)
        stored = self._composition_store.get_lock(
            org_id=org_id,
            project_id=project_id,
            composition_id=composition_id,
            revision=revision,
        )
        _require_lock_markings(stored.payload, markings=markings, conceal=True)
        return stored


def _stored_lock_from_receipt(receipt: CommandReceipt) -> StoredCompositionLock:
    if receipt.status_code != 201 or receipt.response_etag is not None:
        raise LockIntegrityCorruptError()
    try:
        payload = deepcopy(receipt.response_json)
        created_at = payload.get("createdAt")
        if isinstance(created_at, str):
            payload["createdAt"] = datetime.fromisoformat(created_at)
        return StoredCompositionLock.model_validate(payload)
    except (TypeError, ValueError, ValidationError) as exc:
        raise LockIntegrityCorruptError() from exc


def _require_lock_markings(
    payload: CompositionLockPayload,
    *,
    markings: Collection[str],
    conceal: bool,
) -> None:
    try:
        require_target_markings(
            principal_markings=markings,
            target_markings=payload.permission_diff.target.markings,
            conceal=conceal,
        )
    except (TypeError, ValueError) as exc:
        raise LockIntegrityCorruptError() from exc
