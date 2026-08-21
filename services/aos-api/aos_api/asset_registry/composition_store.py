"""Atomic PostgreSQL persistence for immutable composition locks."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager
from copy import deepcopy
from datetime import datetime
from typing import Any, Protocol

import psycopg
from psycopg import errors
from psycopg.types.json import Jsonb
from pydantic import ValidationError

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.asset_registry.composition_contracts import (
    CanonicalCompositionRequest,
    CompositionLockPayload,
    CompositionRequest,
    CurrentInstallationRef,
    RegistrySnapshot,
    RegistrySnapshotCandidate,
    StoredCompositionLock,
)
from aos_api.asset_registry.errors import (
    AssetNotFoundError,
    LockIntegrityCorruptError,
    LockIntegrityInvalidError,
    RegistrySnapshotStaleError,
    RevisionConflictError,
)
from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
from aos_api.db import connect

JsonObject = dict[str, Any]
ConnectFactory = Callable[[], AbstractContextManager[Any]]
UuidFactory = Callable[[], uuid.UUID]


class CompositionPersistenceError(RuntimeError):
    """Safe failure used when PostgreSQL details must not cross the Store."""

    def __init__(self) -> None:
        super().__init__("composition persistence failed")


class CompositionStore(Protocol):
    def create_or_get(
        self,
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


class PostgresCompositionStore:
    """Persist composition identity and revision-one lock in one transaction."""

    def __init__(
        self,
        connect_factory: ConnectFactory = connect,
        *,
        uuid_factory: UuidFactory = uuid.uuid4,
    ) -> None:
        self._connect_factory = connect_factory
        self._uuid_factory = uuid_factory

    def create_or_get(
        self,
        *,
        org_id: str,
        project_id: str,
        request: CompositionRequest,
        snapshot: RegistrySnapshot,
        payload: CompositionLockPayload,
        created_by: str,
    ) -> StoredCompositionLock:
        try:
            with self._connect_factory() as conn:
                apply_asset_transaction_scope(conn, org_id=org_id, project_id=project_id)
                result = self.create_or_get_in_transaction(
                    conn,
                    org_id=org_id,
                    project_id=project_id,
                    request=request,
                    snapshot=snapshot,
                    payload=payload,
                    created_by=created_by,
                )
                conn.commit()
                return result
        except (RevisionConflictError, LockIntegrityCorruptError):
            raise
        except (errors.CheckViolation, errors.ForeignKeyViolation) as exc:
            raise LockIntegrityInvalidError(
                "composition lock violates persistence constraints"
            ) from exc
        except psycopg.Error as exc:
            raise CompositionPersistenceError() from exc

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
    ) -> StoredCompositionLock:
        """Create or reuse one immutable lock without committing the caller transaction."""

        org_id = _normalized_text(org_id, "org_id")
        project_id = _normalized_text(project_id, "project_id")
        created_by = _normalized_text(created_by, "created_by")
        request = CompositionRequest.model_validate(request)
        snapshot = RegistrySnapshot.model_validate(snapshot)
        payload = CompositionLockPayload.model_validate(payload)
        _validate_payload_inputs(request=request, snapshot=snapshot, payload=payload)

        request_json = request.lock_request().model_dump(
            mode="json", by_alias=True, exclude_none=False
        )
        snapshot_json = snapshot.model_dump(
            mode="json", by_alias=True, exclude_none=False
        )
        current_ref_json = _optional_model_json(request.current_installation_ref)
        request_hash = canonical_sha256(request_json)
        current_ref_hash = (
            canonical_sha256(current_ref_json) if current_ref_json is not None else None
        )
        lock_json = payload.hash_payload_dump()
        permission_json = payload.permission_diff.model_dump(
            mode="json", by_alias=True, exclude_none=False
        )
        migration_json = payload.migration_plan.model_dump(
            mode="json", by_alias=True, exclude_none=False
        )
        contribution_json = payload.contribution_diff.model_dump(
            mode="json", by_alias=True, exclude_none=False
        )
        incoming_hashes = (
            canonical_sha256(lock_json),
            canonical_sha256(permission_json),
            canonical_sha256(migration_json),
            canonical_sha256(contribution_json),
        )

        existing = _select_equivalent(
            conn,
            org_id=org_id,
            project_id=project_id,
            request_hash=request_hash,
            snapshot_hash=snapshot.snapshot_hash,
            resolver_version=payload.resolver_version,
            current_ref_hash=current_ref_hash,
        )
        if existing is not None:
            result = _stored_lock_from_row(existing)
            _require_same_equivalent_lock(
                existing=result,
                incoming=payload,
                incoming_hashes=incoming_hashes,
            )
            return result

        composition_pk = self._uuid_factory()
        composition_id = self._uuid_factory()
        inserted = conn.execute(
            """
            INSERT INTO bundle_composition (
              org_id, project_id, composition_pk, composition_id,
              request_json, request_hash,
              registry_snapshot_json, registry_snapshot_hash,
              current_installation_ref_json,
              current_installation_ref_hash,
              resolver_version, created_by
            ) VALUES (
              %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT DO NOTHING
            RETURNING composition_pk
            """,
            (
                org_id,
                project_id,
                composition_pk,
                composition_id,
                Jsonb(request_json),
                request_hash,
                Jsonb(snapshot_json),
                snapshot.snapshot_hash,
                Jsonb(current_ref_json) if current_ref_json is not None else None,
                current_ref_hash,
                payload.resolver_version,
                created_by,
            ),
        ).fetchone()
        if inserted is None:
            existing = _select_equivalent(
                conn,
                org_id=org_id,
                project_id=project_id,
                request_hash=request_hash,
                snapshot_hash=snapshot.snapshot_hash,
                resolver_version=payload.resolver_version,
                current_ref_hash=current_ref_hash,
            )
            if existing is None:
                raise RevisionConflictError(
                    "composition identity conflicts with persisted data"
                )
            result = _stored_lock_from_row(existing)
            _require_same_equivalent_lock(
                existing=result,
                incoming=payload,
                incoming_hashes=incoming_hashes,
            )
            return result

        conn.execute(
            """
            INSERT INTO bundle_composition_lock (
              org_id, project_id, composition_pk, revision,
              lock_payload, lock_hash,
              permission_diff_json, permission_diff_hash,
              migration_plan_json, migration_plan_hash,
              contribution_diff_json, contribution_diff_hash,
              created_by
            ) VALUES (
              %s, %s, %s, 1, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            """,
            (
                org_id,
                project_id,
                composition_pk,
                Jsonb(lock_json),
                incoming_hashes[0],
                Jsonb(permission_json),
                incoming_hashes[1],
                Jsonb(migration_json),
                incoming_hashes[2],
                Jsonb(contribution_json),
                incoming_hashes[3],
                created_by,
            ),
        )
        row = _select_by_pk(
            conn,
            org_id=org_id,
            project_id=project_id,
            composition_pk=composition_pk,
            revision=1,
        )
        if row is None:
            raise LockIntegrityCorruptError()
        return _stored_lock_from_row(row)

    def get_lock(
        self,
        *,
        org_id: str,
        project_id: str,
        composition_id: str,
        revision: int = 1,
    ) -> StoredCompositionLock:
        org_id = _normalized_text(org_id, "org_id")
        project_id = _normalized_text(project_id, "project_id")
        composition_uuid = _resource_uuid(composition_id)
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
            raise AssetNotFoundError("composition lock not found")
        try:
            with self._connect_factory() as conn:
                apply_asset_transaction_scope(conn, org_id=org_id, project_id=project_id)
                row = _select_by_id(
                    conn,
                    org_id=org_id,
                    project_id=project_id,
                    composition_id=composition_uuid,
                    revision=revision,
                )
                if row is None:
                    raise AssetNotFoundError("composition lock not found")
                return _stored_lock_from_row(row)
        except (AssetNotFoundError, LockIntegrityCorruptError):
            raise
        except psycopg.Error as exc:
            raise CompositionPersistenceError() from exc


def load_stored_lock(
    conn: Any,
    *,
    org_id: str,
    project_id: str,
    composition_id: str,
    revision: int,
) -> tuple[uuid.UUID, StoredCompositionLock]:
    """Load and verify a lock through an existing caller-owned transaction."""

    composition_uuid = _resource_uuid(composition_id)
    row = _select_by_id(
        conn,
        org_id=org_id,
        project_id=project_id,
        composition_id=composition_uuid,
        revision=revision,
    )
    if row is None:
        raise AssetNotFoundError("composition lock not found")
    return uuid.UUID(str(row["composition_pk"])), _stored_lock_from_row(row)


def _validate_payload_inputs(
    *,
    request: CompositionRequest,
    snapshot: RegistrySnapshot,
    payload: CompositionLockPayload,
) -> None:
    if (
        request.registry_snapshot_hash is not None
        and request.registry_snapshot_hash != snapshot.snapshot_hash
    ):
        raise RegistrySnapshotStaleError(
            "registry snapshot precondition does not match the resolved snapshot"
        )
    if payload.request != request.lock_request():
        raise LockIntegrityInvalidError(
            "composition lock request does not match the resolved request"
        )
    if payload.registry_snapshot_hash != snapshot.snapshot_hash:
        raise LockIntegrityInvalidError(
            "composition lock snapshot does not match the resolved snapshot"
        )
    if payload.current_installation_ref != request.current_installation_ref:
        raise LockIntegrityInvalidError(
            "composition lock baseline does not match the resolved request"
        )


def _require_same_equivalent_lock(
    *,
    existing: StoredCompositionLock,
    incoming: CompositionLockPayload,
    incoming_hashes: tuple[str, str, str, str],
) -> None:
    existing_hashes = (
        existing.lock_hash,
        existing.permission_diff_hash,
        existing.migration_plan_hash,
        existing.contribution_diff_hash,
    )
    if existing.payload != incoming or existing_hashes != incoming_hashes:
        raise LockIntegrityInvalidError(
            "equivalent composition input produced a different lock"
        )


def _select_equivalent(
    conn: Any,
    *,
    org_id: str,
    project_id: str,
    request_hash: str,
    snapshot_hash: str,
    resolver_version: str,
    current_ref_hash: str | None,
) -> Any | None:
    return conn.execute(
        _LOCK_SELECT
        + """
         WHERE c.org_id = %s
           AND c.project_id = %s
           AND c.request_hash = %s
           AND c.registry_snapshot_hash = %s
           AND c.resolver_version = %s
           AND COALESCE(c.current_installation_ref_hash, '') = COALESCE(%s, '')
         ORDER BY l.revision ASC
         LIMIT 1
        """,
        (
            org_id,
            project_id,
            request_hash,
            snapshot_hash,
            resolver_version,
            current_ref_hash,
        ),
    ).fetchone()


def _select_by_id(
    conn: Any,
    *,
    org_id: str,
    project_id: str,
    composition_id: uuid.UUID,
    revision: int,
) -> Any | None:
    return conn.execute(
        _LOCK_SELECT
        + """
         WHERE c.org_id = %s
           AND c.project_id = %s
           AND c.composition_id = %s
           AND l.revision = %s
        """,
        (org_id, project_id, composition_id, revision),
    ).fetchone()


def _select_by_pk(
    conn: Any,
    *,
    org_id: str,
    project_id: str,
    composition_pk: uuid.UUID,
    revision: int,
) -> Any | None:
    return conn.execute(
        _LOCK_SELECT
        + """
         WHERE c.org_id = %s
           AND c.project_id = %s
           AND c.composition_pk = %s
           AND l.revision = %s
        """,
        (org_id, project_id, composition_pk, revision),
    ).fetchone()


_LOCK_SELECT = """
    SELECT c.composition_pk, c.composition_id,
           c.request_json, c.request_hash,
           c.registry_snapshot_json, c.registry_snapshot_hash,
           c.current_installation_ref_json,
           c.current_installation_ref_hash,
           c.resolver_version,
           l.revision, l.lock_payload, l.lock_hash,
           l.permission_diff_json, l.permission_diff_hash,
           l.migration_plan_json, l.migration_plan_hash,
           l.contribution_diff_json, l.contribution_diff_hash,
           l.created_at
      FROM bundle_composition c
      LEFT JOIN bundle_composition_lock l
        ON l.org_id = c.org_id
       AND l.project_id = c.project_id
       AND l.composition_pk = c.composition_pk
"""


def _stored_lock_from_row(row: Any) -> StoredCompositionLock:
    try:
        request = CanonicalCompositionRequest.model_validate(row["request_json"])
        if row["request_hash"] != canonical_sha256(
            request.model_dump(mode="json", by_alias=True, exclude_none=False)
        ):
            raise ValueError("request hash mismatch")

        snapshot = _snapshot_from_json(row["registry_snapshot_json"])
        if snapshot.snapshot_hash != row["registry_snapshot_hash"]:
            raise ValueError("snapshot hash mismatch")

        current_ref_json = row["current_installation_ref_json"]
        current_ref = (
            CurrentInstallationRef.model_validate(current_ref_json)
            if current_ref_json is not None
            else None
        )
        expected_current_ref_hash = (
            canonical_sha256(
                current_ref.model_dump(mode="json", by_alias=True, exclude_none=False)
            )
            if current_ref is not None
            else None
        )
        if expected_current_ref_hash != row["current_installation_ref_hash"]:
            raise ValueError("current installation ref hash mismatch")

        payload = CompositionLockPayload.model_validate(row["lock_payload"])
        if (
            payload.request != request
            or payload.registry_snapshot_hash != snapshot.snapshot_hash
            or payload.current_installation_ref != current_ref
            or payload.resolver_version != row["resolver_version"]
        ):
            raise ValueError("composition columns and lock payload disagree")

        permission_json = payload.permission_diff.model_dump(
            mode="json", by_alias=True, exclude_none=False
        )
        migration_json = payload.migration_plan.model_dump(
            mode="json", by_alias=True, exclude_none=False
        )
        contribution_json = payload.contribution_diff.model_dump(
            mode="json", by_alias=True, exclude_none=False
        )
        if (
            permission_json != row["permission_diff_json"]
            or migration_json != row["migration_plan_json"]
            or contribution_json != row["contribution_diff_json"]
        ):
            raise ValueError("composition lock diff columns disagree")

        return StoredCompositionLock.model_validate(
            {
                "compositionId": str(row["composition_id"]),
                "revision": row["revision"],
                "payload": payload,
                "lockHash": row["lock_hash"],
                "permissionDiffHash": row["permission_diff_hash"],
                "migrationPlanHash": row["migration_plan_hash"],
                "contributionDiffHash": row["contribution_diff_hash"],
                "createdAt": row["created_at"],
            }
        )
    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        raise LockIntegrityCorruptError() from exc


def _optional_model_json(value: CurrentInstallationRef | None) -> JsonObject | None:
    if value is None:
        return None
    return value.model_dump(mode="json", by_alias=True, exclude_none=False)


def _snapshot_from_json(value: Any) -> RegistrySnapshot:
    if not isinstance(value, dict):
        raise TypeError("registry snapshot must be an object")
    payload = deepcopy(value)
    stored_hash = payload.get("snapshotHash")
    raw_hash_payload = {
        "schemaVersion": payload.get("schemaVersion"),
        "candidates": payload.get("candidates"),
    }
    if not isinstance(stored_hash, str) or stored_hash != canonical_sha256(
        raw_hash_payload
    ):
        raise ValueError("snapshotHash does not match persisted snapshot payload")

    raw_candidates = payload.get("candidates")
    if not isinstance(raw_candidates, list):
        raise TypeError("registry snapshot candidates must be an array")
    candidates = [
        RegistrySnapshotCandidate.model_validate(item) for item in raw_candidates
    ]
    normalized_hash = canonical_sha256(
        {
            "schemaVersion": payload.get("schemaVersion"),
            "candidates": [
                item.model_dump(mode="json", by_alias=True, exclude_none=False)
                for item in candidates
            ],
        }
    )
    payload["candidates"] = candidates
    payload["snapshotHash"] = normalized_hash
    checked_at = payload.get("checkedAt")
    if isinstance(checked_at, str):
        payload["checkedAt"] = datetime.fromisoformat(checked_at)
    validated = RegistrySnapshot.model_validate(payload)
    return validated.model_copy(update={"snapshot_hash": stored_hash})


def _resource_uuid(value: str) -> uuid.UUID:
    try:
        parsed = uuid.UUID(value)
    except (AttributeError, TypeError, ValueError) as exc:
        raise AssetNotFoundError("composition lock not found") from exc
    if str(parsed) != value:
        raise AssetNotFoundError("composition lock not found")
    return parsed


def _normalized_text(value: str, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or "\x00" in value
    ):
        raise ValueError(f"{label} must be non-blank and normalized")
    return value
