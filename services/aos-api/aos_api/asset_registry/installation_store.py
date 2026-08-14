"""PostgreSQL draft installation and command persistence primitives."""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable, Collection
from contextlib import AbstractContextManager
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import psycopg
from psycopg import errors
from psycopg.types.json import Jsonb
from pydantic import ValidationError

from aos_api.asset_registry.canonical_json import canonical_json, canonical_sha256
from aos_api.asset_registry.composition_contracts import (
    ApproveInstallationRequest,
    CreateInstallationRequest,
    CurrentInstallationRef,
    InstallationEventEvidence,
    InstallationListQuery,
    InstallationListResponse,
    InstallationRecord,
)
from aos_api.asset_registry.composition_store import load_stored_lock
from aos_api.asset_registry.control_protocols import ActiveInstallationBaseline
from aos_api.asset_registry.errors import (
    ApprovalStaleError,
    AssetNotFoundError,
    AssetRegistryError,
    CurrentInstallationStaleError,
    DutySeparationRequiredError,
    IdempotencyConflictError,
    InstallationStateConflictError,
    LockIntegrityCorruptError,
    RevisionConflictError,
)
from aos_api.asset_registry.installation_evidence import verify_event_evidence
from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
from aos_api.db import connect

JsonObject = dict[str, Any]
ConnectFactory = Callable[[], AbstractContextManager[Any]]
UuidFactory = Callable[[], uuid.UUID]
CommandHandler = Callable[[Any], "CommandResult"]
_STRONG_ETAG = re.compile(r'^"[1-9][0-9]*"$')


class InstallationPersistenceError(RuntimeError):
    """Safe failure used when PostgreSQL details must not cross the Store."""

    def __init__(self) -> None:
        super().__init__("installation persistence failed")


@dataclass(frozen=True, slots=True)
class CommandResult:
    status_code: int
    response_json: JsonObject
    response_etag: str | None = None


@dataclass(frozen=True, slots=True)
class CommandReceipt(CommandResult):
    replayed: bool = False


@dataclass(frozen=True, slots=True)
class LockedInstallation:
    org_id: str
    project_id: str
    installation_pk: uuid.UUID
    record: InstallationRecord


class PostgresInstallationStore:
    """Create draft installations and expose no state-transition operation."""

    def __init__(
        self,
        connect_factory: ConnectFactory = connect,
        *,
        uuid_factory: UuidFactory = uuid.uuid4,
    ) -> None:
        self._connect_factory = connect_factory
        self._uuid_factory = uuid_factory

    def create_draft(
        self,
        *,
        org_id: str,
        project_id: str,
        request: CreateInstallationRequest,
        requested_by: str,
    ) -> InstallationRecord:
        values = _validated_create_inputs(
            org_id=org_id,
            project_id=project_id,
            request=request,
            requested_by=requested_by,
        )
        try:
            with self._connect_factory() as conn:
                apply_asset_transaction_scope(conn, org_id=org_id, project_id=project_id)
                record = self.create_draft_in_transaction(conn, **values)
                conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
                conn.commit()
                return record
        except (AssetRegistryError, LockIntegrityCorruptError):
            raise
        except errors.UniqueViolation as exc:
            raise RevisionConflictError("installation identity already exists") from exc
        except psycopg.Error as exc:
            raise InstallationPersistenceError() from exc

    def create_draft_in_transaction(
        self,
        conn: Any,
        *,
        org_id: str,
        project_id: str,
        request: CreateInstallationRequest,
        requested_by: str,
    ) -> InstallationRecord:
        """Create a draft using a caller-owned transaction for M2-B commands."""

        org_id = _normalized_text(org_id, "org_id")
        project_id = _normalized_text(project_id, "project_id")
        requested_by = _normalized_text(requested_by, "requested_by")
        request = CreateInstallationRequest.model_validate(request)
        composition_pk, lock = load_stored_lock(
            conn,
            org_id=org_id,
            project_id=project_id,
            composition_id=request.composition_id,
            revision=request.lock_revision,
        )
        if lock.payload.current_installation_ref is not None:
            self.load_active_baseline_in_transaction(
                conn,
                org_id=org_id,
                project_id=project_id,
                requested_ref=lock.payload.current_installation_ref,
            )
        installation_pk = self._uuid_factory()
        installation_id = self._uuid_factory()
        conn.execute(
            """
            INSERT INTO bundle_installation (
              org_id, project_id, installation_pk, installation_id,
              display_name, current_revision, active_revision,
              previous_active_revision, etag_version, created_by
            ) VALUES (%s, %s, %s, %s, %s, 1, NULL, NULL, 1, %s)
            """,
            (
                org_id,
                project_id,
                installation_pk,
                installation_id,
                request.display_name,
                requested_by,
            ),
        )
        conn.execute(
            """
            INSERT INTO bundle_installation_revision (
              org_id, project_id, installation_pk, revision, parent_revision,
              state, composition_pk, lock_revision, lock_hash,
              permission_diff_hash, migration_plan_hash,
              contribution_diff_hash, overlay_revision, requested_by,
              decision_id
            ) VALUES (
              %s, %s, %s, 1, NULL, 'draft', %s, %s, %s, %s, %s, %s,
              %s, %s, NULL
            )
            """,
            (
                org_id,
                project_id,
                installation_pk,
                composition_pk,
                lock.revision,
                lock.lock_hash,
                lock.permission_diff_hash,
                lock.migration_plan_hash,
                lock.contribution_diff_hash,
                request.overlay_revision,
                requested_by,
            ),
        )
        conn.execute(
            """
            INSERT INTO bundle_installation_event (
              org_id, project_id, installation_pk, sequence,
              from_revision, to_revision, from_state, to_state,
              actor, reason, evidence_json, evidence_hash
            ) VALUES (%s, %s, %s, 1, NULL, 1, NULL, 'draft', %s,
                      NULL, NULL, NULL)
            """,
            (org_id, project_id, installation_pk, requested_by),
        )
        return _load_record_by_pk(
            conn,
            org_id=org_id,
            project_id=project_id,
            installation_pk=installation_pk,
        )

    def get_installation(
        self,
        *,
        org_id: str,
        project_id: str,
        installation_id: str,
    ) -> InstallationRecord:
        org_id = _normalized_text(org_id, "org_id")
        project_id = _normalized_text(project_id, "project_id")
        installation_uuid = _resource_uuid(installation_id)
        try:
            with self._connect_factory() as conn:
                apply_asset_transaction_scope(conn, org_id=org_id, project_id=project_id)
                row = conn.execute(
                    """
                    SELECT installation_pk
                      FROM bundle_installation
                     WHERE org_id = %s AND project_id = %s
                       AND installation_id = %s
                    """,
                    (org_id, project_id, installation_uuid),
                ).fetchone()
                if row is None:
                    raise AssetNotFoundError("bundle installation not found")
                return _load_record_by_pk(
                    conn,
                    org_id=org_id,
                    project_id=project_id,
                    installation_pk=row["installation_pk"],
                )
        except (AssetNotFoundError, LockIntegrityCorruptError):
            raise
        except psycopg.Error as exc:
            raise InstallationPersistenceError() from exc

    def list_installations(
        self,
        *,
        org_id: str,
        project_id: str,
        query: InstallationListQuery,
    ) -> InstallationListResponse:
        org_id = _normalized_text(org_id, "org_id")
        project_id = _normalized_text(project_id, "project_id")
        query = InstallationListQuery.model_validate(query)
        state_clause = " AND r.state = %s" if query.state is not None else ""
        state_params: tuple[object, ...] = (
            (query.state,) if query.state is not None else ()
        )
        try:
            with self._connect_factory() as conn:
                apply_asset_transaction_scope(conn, org_id=org_id, project_id=project_id)
                rows = conn.execute(
                    """
                    WITH filtered AS MATERIALIZED (
                      SELECT i.installation_id, i.display_name, r.state,
                             i.current_revision, i.active_revision,
                             i.previous_active_revision, i.etag_version,
                             i.created_at, i.updated_at
                        FROM bundle_installation i
                        JOIN bundle_installation_revision r
                          ON r.org_id = i.org_id
                         AND r.project_id = i.project_id
                         AND r.installation_pk = i.installation_pk
                         AND r.revision = i.current_revision
                       WHERE i.org_id = %s AND i.project_id = %s
                    """
                    + state_clause
                    + """
                    ), page AS (
                      SELECT *
                        FROM filtered
                       ORDER BY created_at DESC, installation_id ASC
                       LIMIT %s OFFSET %s
                    )
                    SELECT page.*, totals.total
                      FROM (SELECT COUNT(*) AS total FROM filtered) totals
                      LEFT JOIN page ON TRUE
                      ORDER BY page.created_at DESC NULLS LAST,
                               page.installation_id ASC NULLS LAST
                    """,
                    (
                        org_id,
                        project_id,
                        *state_params,
                        query.limit,
                        query.offset,
                    ),
                ).fetchall()
                assert rows
                total = rows[0]["total"]
                page_rows = [row for row in rows if row["installation_id"] is not None]
                return InstallationListResponse.model_validate(
                    {
                        "items": [_list_item_json(row) for row in page_rows],
                        "total": total,
                        "limit": query.limit,
                        "offset": query.offset,
                    }
                )
        except LockIntegrityCorruptError:
            raise
        except (ValidationError, ValueError, TypeError, KeyError) as exc:
            raise LockIntegrityCorruptError() from exc
        except psycopg.Error as exc:
            raise InstallationPersistenceError() from exc

    def list_visible_installations(
        self,
        *,
        org_id: str,
        project_id: str,
        query: InstallationListQuery,
        allowed_markings: Collection[str],
    ) -> InstallationListResponse:
        org_id = _normalized_text(org_id, "org_id")
        project_id = _normalized_text(project_id, "project_id")
        query = InstallationListQuery.model_validate(query)
        markings = sorted(
            {_normalized_text(item, "marking") for item in allowed_markings}
        )
        state_clause = " AND r.state = %s" if query.state is not None else ""
        state_params: tuple[object, ...] = (query.state,) if query.state else ()
        try:
            with self._connect_factory() as conn:
                apply_asset_transaction_scope(conn, org_id=org_id, project_id=project_id)
                corrupt = conn.execute(
                    """
                    SELECT EXISTS (
                      SELECT 1
                        FROM bundle_installation i
                        JOIN bundle_installation_revision r
                          ON r.org_id=i.org_id AND r.project_id=i.project_id
                         AND r.installation_pk=i.installation_pk
                         AND r.revision=i.current_revision
                        JOIN bundle_composition_lock l
                          ON l.org_id=r.org_id AND l.project_id=r.project_id
                         AND l.composition_pk=r.composition_pk
                         AND l.revision=r.lock_revision
                       WHERE i.org_id=%s AND i.project_id=%s
                         AND (jsonb_typeof(l.permission_diff_json->'target'->'markings') <> 'array'
                              OR canonical_bundle_control_sha256(l.permission_diff_json) <> l.permission_diff_hash)
                    ) AS corrupt
                    """,
                    (org_id, project_id),
                ).fetchone()
                if corrupt is None or corrupt["corrupt"]:
                    raise LockIntegrityCorruptError()
                rows = conn.execute(
                    """
                    WITH visible AS MATERIALIZED (
                      SELECT i.installation_id, i.display_name, r.state,
                             i.current_revision, i.active_revision,
                             i.previous_active_revision, i.etag_version,
                             i.created_at, i.updated_at
                        FROM bundle_installation i
                        JOIN bundle_installation_revision r
                          ON r.org_id=i.org_id AND r.project_id=i.project_id
                         AND r.installation_pk=i.installation_pk
                         AND r.revision=i.current_revision
                        JOIN bundle_composition_lock l
                          ON l.org_id=r.org_id AND l.project_id=r.project_id
                         AND l.composition_pk=r.composition_pk
                         AND l.revision=r.lock_revision
                       WHERE i.org_id=%s AND i.project_id=%s
                         AND (l.permission_diff_json->'target'->'markings') <@ %s::jsonb
                    """
                    + state_clause
                    + """
                    ), page AS (
                      SELECT * FROM visible
                       ORDER BY created_at DESC, installation_id ASC
                       LIMIT %s OFFSET %s
                    )
                    SELECT page.*, totals.total
                      FROM (SELECT COUNT(*) AS total FROM visible) totals
                      LEFT JOIN page ON TRUE
                      ORDER BY page.created_at DESC NULLS LAST,
                               page.installation_id ASC NULLS LAST
                    """,
                    (
                        org_id,
                        project_id,
                        Jsonb(markings),
                        *state_params,
                        query.limit,
                        query.offset,
                    ),
                ).fetchall()
                assert rows
                return InstallationListResponse.model_validate(
                    {
                        "items": [
                            _list_item_json(row)
                            for row in rows
                            if row["installation_id"] is not None
                        ],
                        "total": rows[0]["total"],
                        "limit": query.limit,
                        "offset": query.offset,
                    }
                )
        except LockIntegrityCorruptError:
            raise
        except (ValidationError, ValueError, TypeError, KeyError) as exc:
            raise LockIntegrityCorruptError() from exc
        except psycopg.Error as exc:
            raise InstallationPersistenceError() from exc

    def execute_idempotent(
        self,
        *,
        org_id: str,
        project_id: str,
        operation: str,
        idempotency_key: str,
        subject: str,
        request_hash: str,
        handler: CommandHandler,
    ) -> CommandReceipt:
        org_id = _normalized_text(org_id, "org_id")
        project_id = _normalized_text(project_id, "project_id")
        operation = _normalized_text(operation, "operation")
        idempotency_key = _idempotency_key(idempotency_key)
        subject = _normalized_text(subject, "subject")
        if re.fullmatch(r"sha256:[0-9a-f]{64}", request_hash) is None:
            raise ValueError("request_hash must be a canonical SHA-256 value")
        try:
            with self._connect_factory() as conn:
                apply_asset_transaction_scope(conn, org_id=org_id, project_id=project_id)
                lock_identity = (
                    f"{org_id}\x1f{project_id}\x1f{operation}\x1f{idempotency_key}"
                )
                conn.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                    (lock_identity,),
                )
                row = conn.execute(
                    """
                    SELECT subject, request_hash, status_code,
                           response_json, response_etag
                      FROM bundle_installation_command
                     WHERE org_id = %s AND project_id = %s
                       AND operation = %s AND idempotency_key = %s
                    """,
                    (org_id, project_id, operation, idempotency_key),
                ).fetchone()
                if row is not None:
                    if row["request_hash"] != request_hash:
                        raise IdempotencyConflictError(
                            "idempotency key was used for a different request"
                        )
                    if row["subject"] != subject:
                        raise LockIntegrityCorruptError()
                    receipt = _receipt_from_row(row, replayed=True)
                    conn.commit()
                    return receipt

                result = _validated_command_result(handler(conn))
                conn.execute(
                    """
                    INSERT INTO bundle_installation_command (
                      org_id, project_id, operation, idempotency_key,
                      subject, request_hash, status_code,
                      response_json, response_etag
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        org_id,
                        project_id,
                        operation,
                        idempotency_key,
                        subject,
                        request_hash,
                        result.status_code,
                        Jsonb(result.response_json),
                        result.response_etag,
                    ),
                )
                conn.commit()
                return CommandReceipt(
                    status_code=result.status_code,
                    response_json=result.response_json,
                    response_etag=result.response_etag,
                    replayed=False,
                )
        except (AssetRegistryError, LockIntegrityCorruptError):
            raise
        except psycopg.Error as exc:
            raise InstallationPersistenceError() from exc

    def lock_for_cas(
        self,
        conn: Any,
        *,
        org_id: str,
        project_id: str,
        installation_id: str,
        expected_etag_version: int,
    ) -> InstallationRecord:
        """Lock one installation row and verify its current ETag without mutation."""

        org_id = _normalized_text(org_id, "org_id")
        project_id = _normalized_text(project_id, "project_id")
        if (
            isinstance(expected_etag_version, bool)
            or not isinstance(expected_etag_version, int)
            or expected_etag_version < 1
        ):
            raise RevisionConflictError("installation revision does not match")
        row = conn.execute(
            """
            SELECT installation_pk, etag_version
              FROM bundle_installation
             WHERE org_id = %s AND project_id = %s
               AND installation_id = %s
             FOR UPDATE
            """,
            (org_id, project_id, _resource_uuid(installation_id)),
        ).fetchone()
        if row is None:
            raise AssetNotFoundError("bundle installation not found")
        if row["etag_version"] != expected_etag_version:
            raise RevisionConflictError("installation revision does not match")
        return _load_record_by_pk(
            conn,
            org_id=org_id,
            project_id=project_id,
            installation_pk=row["installation_pk"],
        )

    def lock_for_transition_in_transaction(
        self,
        conn: Any,
        *,
        org_id: str,
        project_id: str,
        installation_id: str,
        expected_etag_version: int,
    ) -> LockedInstallation:
        record = self.lock_for_cas(
            conn,
            org_id=org_id,
            project_id=project_id,
            installation_id=installation_id,
            expected_etag_version=expected_etag_version,
        )
        row = conn.execute(
            """
            SELECT installation_pk
              FROM bundle_installation
             WHERE org_id = %s AND project_id = %s
               AND installation_id = %s
             FOR UPDATE
            """,
            (org_id, project_id, _resource_uuid(installation_id)),
        ).fetchone()
        if row is None:
            raise AssetNotFoundError("bundle installation not found")
        return LockedInstallation(
            org_id=org_id,
            project_id=project_id,
            installation_pk=uuid.UUID(str(row["installation_pk"])),
            record=record,
        )

    def load_active_baseline_in_transaction(
        self,
        conn: Any,
        *,
        org_id: str,
        project_id: str,
        requested_ref: CurrentInstallationRef,
    ) -> ActiveInstallationBaseline:
        requested_ref = CurrentInstallationRef.model_validate(requested_ref)
        row = conn.execute(
            """
            SELECT installation_pk, active_revision
              FROM bundle_installation
             WHERE org_id = %s AND project_id = %s
               AND installation_id = %s
             FOR SHARE
            """,
            (
                org_id,
                project_id,
                _resource_uuid(requested_ref.installation_id),
            ),
        ).fetchone()
        if row is None:
            raise AssetNotFoundError("bundle installation not found")
        if row["active_revision"] is None:
            raise CurrentInstallationStaleError(
                "current installation has no active baseline"
            )
        revision = conn.execute(
            """
            SELECT c.composition_id, r.lock_revision, r.lock_hash,
                   r.permission_diff_hash, r.migration_plan_hash,
                   r.contribution_diff_hash, r.overlay_revision
              FROM bundle_installation_revision r
              JOIN bundle_composition c
                ON c.org_id = r.org_id AND c.project_id = r.project_id
               AND c.composition_pk = r.composition_pk
             WHERE r.org_id = %s AND r.project_id = %s
               AND r.installation_pk = %s AND r.revision = %s
            """,
            (org_id, project_id, row["installation_pk"], row["active_revision"]),
        ).fetchone()
        if revision is None:
            raise LockIntegrityCorruptError()
        try:
            _, lock = load_stored_lock(
                conn,
                org_id=org_id,
                project_id=project_id,
                composition_id=str(revision["composition_id"]),
                revision=revision["lock_revision"],
            )
            server_ref = CurrentInstallationRef.model_validate(
                {
                    "installationId": requested_ref.installation_id,
                    "revision": row["active_revision"],
                    "lockHash": revision["lock_hash"],
                    "overlayRevision": revision["overlay_revision"],
                }
            )
        except (AssetRegistryError, ValidationError, TypeError, ValueError) as exc:
            raise LockIntegrityCorruptError() from exc
        persisted_hashes = (
            revision["lock_hash"],
            revision["permission_diff_hash"],
            revision["migration_plan_hash"],
            revision["contribution_diff_hash"],
        )
        lock_hashes = (
            lock.lock_hash,
            lock.permission_diff_hash,
            lock.migration_plan_hash,
            lock.contribution_diff_hash,
        )
        if persisted_hashes != lock_hashes:
            raise LockIntegrityCorruptError()
        if server_ref != requested_ref:
            raise CurrentInstallationStaleError(
                "current installation baseline is stale"
            )
        return ActiveInstallationBaseline(server_ref=server_ref, lock=lock)

    def read_control_clock_in_transaction(self, conn: Any) -> datetime:
        row = conn.execute("SELECT clock_timestamp() AS checked_at").fetchone()
        if row is None or not isinstance(row["checked_at"], datetime):
            raise InstallationPersistenceError()
        return row["checked_at"]

    def guard_replacement_activation_in_transaction(
        self,
        conn: Any,
        *,
        locked: LockedInstallation,
        requested_ref: CurrentInstallationRef | None,
    ) -> None:
        """Serialize siblings and require the exact predecessor to remain active."""

        if requested_ref is None:
            return
        predecessor = conn.execute(
            """
            SELECT installation_pk
              FROM bundle_installation
             WHERE org_id=%s AND project_id=%s AND installation_id=%s
             FOR UPDATE
            """,
            (
                locked.org_id,
                locked.project_id,
                _resource_uuid(requested_ref.installation_id),
            ),
        ).fetchone()
        if predecessor is None:
            raise CurrentInstallationStaleError(
                "replacement predecessor is unavailable"
            )
        self.load_active_baseline_in_transaction(
            conn,
            org_id=locked.org_id,
            project_id=locked.project_id,
            requested_ref=requested_ref,
        )
        active_child = self._find_active_replacement_in_transaction(
            conn,
            org_id=locked.org_id,
            project_id=locked.project_id,
            predecessor_installation_id=requested_ref.installation_id,
            excluded_installation_pk=locked.installation_pk,
        )
        if active_child is not None:
            raise InstallationStateConflictError(
                "replacement predecessor already has an active replacement"
            )

    def guard_no_active_replacement_in_transaction(
        self,
        conn: Any,
        *,
        locked: LockedInstallation,
    ) -> None:
        """Require leaf-first rollback/uninstall for replacement lineages."""

        active_child = self._find_active_replacement_in_transaction(
            conn,
            org_id=locked.org_id,
            project_id=locked.project_id,
            predecessor_installation_id=locked.record.installation_id,
            excluded_installation_pk=locked.installation_pk,
        )
        if active_child is not None:
            raise InstallationStateConflictError(
                "installation has an active replacement and must be restored leaf-first"
            )

    def _find_active_replacement_in_transaction(
        self,
        conn: Any,
        *,
        org_id: str,
        project_id: str,
        predecessor_installation_id: str,
        excluded_installation_pk: uuid.UUID,
    ) -> str | None:
        row = conn.execute(
            """
            SELECT child.installation_id
              FROM bundle_installation child
              JOIN bundle_installation_revision active
                ON active.org_id=child.org_id
               AND active.project_id=child.project_id
               AND active.installation_pk=child.installation_pk
               AND active.revision=child.active_revision
              JOIN bundle_composition_lock lock
                ON lock.org_id=active.org_id
               AND lock.project_id=active.project_id
               AND lock.composition_pk=active.composition_pk
               AND lock.revision=active.lock_revision
             WHERE child.org_id=%s AND child.project_id=%s
               AND child.active_revision IS NOT NULL
               AND child.installation_pk<>%s
               AND lock.lock_payload->'currentInstallationRef'
                   ->>'installationId'=%s
             ORDER BY child.installation_id
             LIMIT 1
            """,
            (
                org_id,
                project_id,
                excluded_installation_pk,
                predecessor_installation_id,
            ),
        ).fetchone()
        return str(row["installation_id"]) if row is not None else None

    def append_submit_in_transaction(
        self, conn: Any, *, locked: LockedInstallation, actor: str
    ) -> InstallationRecord:
        return self._append_transition(
            conn, locked=locked, actor=actor, to_state="submitted"
        )

    def append_approval_in_transaction(
        self,
        conn: Any,
        *,
        locked: LockedInstallation,
        actor: str,
        request: ApproveInstallationRequest,
    ) -> InstallationRecord:
        request = ApproveInstallationRequest.model_validate(request)
        current = locked.record.current
        if actor == current.requested_by:
            raise DutySeparationRequiredError(
                "installation requester cannot approve the same plan"
            )
        expected = (
            current.lock_hash,
            current.permission_diff_hash,
            current.migration_plan_hash,
            current.contribution_diff_hash,
        )
        supplied = (
            request.lock_hash,
            request.permission_diff_hash,
            request.migration_plan_hash,
            request.contribution_diff_hash,
        )
        if supplied != expected:
            raise ApprovalStaleError("installation approval hashes are stale")
        return self._append_transition(
            conn,
            locked=locked,
            actor=actor,
            to_state="approved",
            decision="approved",
        )

    def append_rejection_in_transaction(
        self,
        conn: Any,
        *,
        locked: LockedInstallation,
        actor: str,
        reason: str,
    ) -> InstallationRecord:
        if actor == locked.record.current.requested_by:
            raise DutySeparationRequiredError(
                "installation requester cannot reject the same plan"
            )
        return self._append_transition(
            conn,
            locked=locked,
            actor=actor,
            to_state="rejected",
            decision="rejected",
            reason=_normalized_text(reason, "reason"),
        )

    def append_apply_in_transaction(
        self,
        conn: Any,
        *,
        locked: LockedInstallation,
        actor: str,
        evidence: InstallationEventEvidence,
    ) -> InstallationRecord:
        return self._append_transition(
            conn, locked=locked, actor=actor, to_state="applied", evidence=evidence
        )

    def append_verify_in_transaction(
        self,
        conn: Any,
        *,
        locked: LockedInstallation,
        actor: str,
        evidence: InstallationEventEvidence,
    ) -> InstallationRecord:
        return self._append_transition(
            conn, locked=locked, actor=actor, to_state="active", evidence=evidence
        )

    def append_rollback_in_transaction(
        self,
        conn: Any,
        *,
        locked: LockedInstallation,
        actor: str,
        reason: str,
        evidence: InstallationEventEvidence,
    ) -> InstallationRecord:
        return self._append_transition(
            conn,
            locked=locked,
            actor=actor,
            to_state="rolled_back",
            reason=_normalized_text(reason, "reason"),
            evidence=evidence,
        )

    def append_uninstall_in_transaction(
        self,
        conn: Any,
        *,
        locked: LockedInstallation,
        actor: str,
        reason: str,
        evidence: InstallationEventEvidence,
    ) -> InstallationRecord:
        return self._append_transition(
            conn,
            locked=locked,
            actor=actor,
            to_state="uninstalled",
            reason=_normalized_text(reason, "reason"),
            evidence=evidence,
        )

    def _append_transition(
        self,
        conn: Any,
        *,
        locked: LockedInstallation,
        actor: str,
        to_state: str,
        decision: str | None = None,
        reason: str | None = None,
        evidence: InstallationEventEvidence | None = None,
    ) -> InstallationRecord:
        actor = _normalized_text(actor, "actor")
        current = locked.record.current
        allowed = {
            "submitted": ("draft", None),
            "approved": ("submitted", None),
            "rejected": ("submitted", None),
            "applied": ("approved", "dry_apply"),
            "active": ("applied", "verification"),
            "rolled_back": ("active", "rollback"),
            "uninstalled": ("active", "uninstall"),
        }
        expected_from, evidence_type = allowed[to_state]
        if current.state != expected_from:
            raise InstallationStateConflictError(
                "installation state transition is not allowed"
            )
        if (evidence is None) != (evidence_type is None):
            raise InstallationStateConflictError(
                "installation transition evidence is inconsistent"
            )
        if evidence is not None and evidence.type != evidence_type:
            raise InstallationStateConflictError(
                "installation transition evidence type is inconsistent"
            )
        if to_state in {"rejected", "rolled_back", "uninstalled"}:
            if reason is None:
                raise InstallationStateConflictError(
                    "installation transition requires a reason"
                )
        elif reason is not None:
            raise InstallationStateConflictError(
                "installation transition does not accept a reason"
            )

        timestamp = (
            evidence.observed_at
            if evidence is not None
            else self.read_control_clock_in_transaction(conn)
        )
        next_revision = current.revision + 1
        decision_id = current.decision_id
        if decision is not None:
            decision_uuid = self._uuid_factory()
            decision_id = str(decision_uuid)
            conn.execute(
                """
                INSERT INTO bundle_installation_decision (
                  org_id, project_id, decision_id, installation_pk,
                  submitted_revision, decision, actor, lock_hash,
                  permission_diff_hash, migration_plan_hash,
                  contribution_diff_hash, reason, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    locked.org_id,
                    locked.project_id,
                    decision_uuid,
                    locked.installation_pk,
                    current.revision,
                    decision,
                    actor,
                    current.lock_hash,
                    current.permission_diff_hash,
                    current.migration_plan_hash,
                    current.contribution_diff_hash,
                    reason,
                    timestamp,
                ),
            )
        if to_state in {"applied", "active", "rolled_back", "uninstalled"} and decision_id is None:
            raise LockIntegrityCorruptError()

        composition_pk, _ = load_stored_lock(
            conn,
            org_id=locked.org_id,
            project_id=locked.project_id,
            composition_id=current.composition_id,
            revision=current.lock_revision,
        )
        conn.execute(
            """
            INSERT INTO bundle_installation_revision (
              org_id, project_id, installation_pk, revision, parent_revision,
              state, composition_pk, lock_revision, lock_hash,
              permission_diff_hash, migration_plan_hash, contribution_diff_hash,
              overlay_revision, requested_by, decision_id, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                locked.org_id,
                locked.project_id,
                locked.installation_pk,
                next_revision,
                current.revision,
                to_state,
                composition_pk,
                current.lock_revision,
                current.lock_hash,
                current.permission_diff_hash,
                current.migration_plan_hash,
                current.contribution_diff_hash,
                current.overlay_revision,
                current.requested_by,
                uuid.UUID(decision_id) if decision_id is not None else None,
                timestamp,
            ),
        )
        evidence_json = (
            evidence.model_dump(mode="json", by_alias=True, exclude_none=False)
            if evidence is not None
            else None
        )
        conn.execute(
            """
            INSERT INTO bundle_installation_event (
              org_id, project_id, installation_pk, sequence,
              from_revision, to_revision, from_state, to_state,
              actor, reason, evidence_json, evidence_hash, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                locked.org_id,
                locked.project_id,
                locked.installation_pk,
                next_revision,
                current.revision,
                next_revision,
                current.state,
                to_state,
                actor,
                reason,
                Jsonb(evidence_json) if evidence_json is not None else None,
                canonical_sha256(evidence_json) if evidence_json is not None else None,
                timestamp,
            ),
        )
        if to_state == "active":
            pointer_sql = (
                ", previous_active_revision = active_revision, active_revision = %s"
            )
            pointer_params: tuple[object, ...] = (next_revision,)
        elif to_state == "rolled_back":
            pointer_sql = ", active_revision = previous_active_revision"
            pointer_params = ()
        elif to_state == "uninstalled":
            pointer_sql = ", active_revision = previous_active_revision"
            pointer_params = ()
        else:
            pointer_sql = ""
            pointer_params = ()
        conn.execute(
            """
            UPDATE bundle_installation
               SET current_revision = %s, etag_version = %s, updated_at = %s
            """
            + pointer_sql
            + " WHERE org_id = %s AND project_id = %s AND installation_pk = %s",
            (
                next_revision,
                next_revision,
                timestamp,
                *pointer_params,
                locked.org_id,
                locked.project_id,
                locked.installation_pk,
            ),
        )
        conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
        return _load_record_by_pk(
            conn,
            org_id=locked.org_id,
            project_id=locked.project_id,
            installation_pk=locked.installation_pk,
        )


def _validated_create_inputs(
    *,
    org_id: str,
    project_id: str,
    request: CreateInstallationRequest,
    requested_by: str,
) -> JsonObject:
    return {
        "org_id": _normalized_text(org_id, "org_id"),
        "project_id": _normalized_text(project_id, "project_id"),
        "request": CreateInstallationRequest.model_validate(request),
        "requested_by": _normalized_text(requested_by, "requested_by"),
    }


def _load_record_by_pk(
    conn: Any,
    *,
    org_id: str,
    project_id: str,
    installation_pk: uuid.UUID,
) -> InstallationRecord:
    row = conn.execute(
        """
        SELECT i.installation_id, i.display_name,
               i.current_revision, i.active_revision,
               i.previous_active_revision, i.etag_version,
               i.created_at, i.updated_at,
               r.revision, r.parent_revision, r.state,
               c.composition_id, r.lock_revision, r.lock_hash,
               r.permission_diff_hash, r.migration_plan_hash,
               r.contribution_diff_hash, r.overlay_revision,
               r.requested_by, r.decision_id,
               r.created_at AS revision_created_at,
               d.submitted_revision, d.decision, d.actor AS decision_actor,
               d.lock_hash AS decision_lock_hash,
               d.permission_diff_hash AS decision_permission_diff_hash,
               d.migration_plan_hash AS decision_migration_plan_hash,
               d.contribution_diff_hash AS decision_contribution_diff_hash,
               d.reason AS decision_reason,
               d.created_at AS decision_created_at
          FROM bundle_installation i
          JOIN bundle_installation_revision r
            ON r.org_id = i.org_id
           AND r.project_id = i.project_id
           AND r.installation_pk = i.installation_pk
           AND r.revision = i.current_revision
          JOIN bundle_composition c
            ON c.org_id = r.org_id
           AND c.project_id = r.project_id
           AND c.composition_pk = r.composition_pk
          LEFT JOIN bundle_installation_decision d
            ON d.org_id = r.org_id
           AND d.project_id = r.project_id
           AND d.decision_id = r.decision_id
         WHERE i.org_id = %s AND i.project_id = %s
           AND i.installation_pk = %s
         FOR SHARE OF i
        """,
        (org_id, project_id, installation_pk),
    ).fetchone()
    if row is None:
        raise AssetNotFoundError("bundle installation not found")
    try:
        try:
            _, lock = load_stored_lock(
                conn,
                org_id=org_id,
                project_id=project_id,
                composition_id=str(row["composition_id"]),
                revision=int(row["lock_revision"]),
            )
        except AssetNotFoundError as exc:
            raise LockIntegrityCorruptError() from exc
        if (
            row["lock_hash"],
            row["permission_diff_hash"],
            row["migration_plan_hash"],
            row["contribution_diff_hash"],
        ) != (
            lock.lock_hash,
            lock.permission_diff_hash,
            lock.migration_plan_hash,
            lock.contribution_diff_hash,
        ):
            raise ValueError("installation revision lock hashes disagree")

        events = conn.execute(
            """
            SELECT sequence, from_revision, to_revision,
                   from_state, to_state, actor, reason,
                   evidence_json, evidence_hash, created_at
              FROM bundle_installation_event
             WHERE org_id = %s AND project_id = %s
               AND installation_pk = %s
             ORDER BY sequence ASC
            """,
            (org_id, project_id, installation_pk),
        ).fetchall()
        event_json = [_event_json(event) for event in events]
        decision_json = None
        if row["decision_id"] is not None:
            if row["decision"] is None:
                raise ValueError("installation decision row is missing")
            decision_json = {
                "decisionId": str(row["decision_id"]),
                "installationId": str(row["installation_id"]),
                "submittedRevision": row["submitted_revision"],
                "decision": row["decision"],
                "actor": row["decision_actor"],
                "lockHash": row["decision_lock_hash"],
                "permissionDiffHash": row["decision_permission_diff_hash"],
                "migrationPlanHash": row["decision_migration_plan_hash"],
                "contributionDiffHash": row["decision_contribution_diff_hash"],
                "reason": row["decision_reason"],
                "createdAt": row["decision_created_at"],
            }
        record = InstallationRecord.model_validate(
            {
                **_list_item_json(row),
                "current": {
                    "installationId": str(row["installation_id"]),
                    "revision": row["revision"],
                    "parentRevision": row["parent_revision"],
                    "state": row["state"],
                    "compositionId": str(row["composition_id"]),
                    "lockRevision": row["lock_revision"],
                    "lockHash": row["lock_hash"],
                    "permissionDiffHash": row["permission_diff_hash"],
                    "migrationPlanHash": row["migration_plan_hash"],
                    "contributionDiffHash": row["contribution_diff_hash"],
                    "overlayRevision": row["overlay_revision"],
                    "requestedBy": row["requested_by"],
                    "decisionId": (
                        str(row["decision_id"])
                        if row["decision_id"] is not None
                        else None
                    ),
                    "createdAt": row["revision_created_at"],
                },
                "decision": decision_json,
                "events": event_json,
            }
        )
        for event in record.events:
            if event.evidence is None:
                continue
            if record.decision is None:
                raise ValueError("evidence event requires an approved decision")
            verify_event_evidence(
                event.evidence,
                installation_id=record.installation_id,
                from_revision=event.from_revision,
                to_revision=event.to_revision,
                lock_hash=record.current.lock_hash,
                permission_diff_hash=record.current.permission_diff_hash,
                migration_plan_hash=record.current.migration_plan_hash,
                contribution_diff_hash=record.current.contribution_diff_hash,
                decision_id=record.decision.decision_id,
                observed_at=event.evidence.observed_at,
            )
        return record
    except (ValidationError, ValueError, TypeError, KeyError) as exc:
        raise LockIntegrityCorruptError() from exc


def _list_item_json(row: Any) -> JsonObject:
    return {
        "installationId": str(row["installation_id"]),
        "displayName": row["display_name"],
        "state": row["state"],
        "currentRevision": row["current_revision"],
        "activeRevision": row["active_revision"],
        "previousActiveRevision": row["previous_active_revision"],
        "etagVersion": row["etag_version"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def _event_json(row: Any) -> JsonObject:
    evidence = row["evidence_json"]
    if evidence is None:
        if row["evidence_hash"] is not None:
            raise ValueError("installation event evidence columns disagree")
    else:
        if canonical_sha256(evidence) != row["evidence_hash"]:
            raise ValueError("installation event evidence hash mismatch")
        evidence = _event_evidence_from_json(evidence)
    return {
        "sequence": row["sequence"],
        "fromRevision": row["from_revision"],
        "toRevision": row["to_revision"],
        "fromState": row["from_state"],
        "toState": row["to_state"],
        "actor": row["actor"],
        "reason": row["reason"],
        "evidence": evidence,
        "createdAt": row["created_at"],
    }


def command_request_hash(
    *,
    subject: str,
    path_params: JsonObject,
    body: JsonObject,
    if_match: str | None,
) -> str:
    """Hash the exact frozen client command envelope used by receipts."""

    subject = _normalized_text(subject, "subject")
    if not isinstance(path_params, dict) or not isinstance(body, dict):
        raise TypeError("command pathParams and body must be JSON objects")
    envelope = {
        "subject": subject,
        "pathParams": deepcopy(path_params),
        "body": deepcopy(body),
        "ifMatch": if_match,
    }
    return canonical_sha256(envelope)


def _event_evidence_from_json(value: Any) -> JsonObject:
    if not isinstance(value, dict):
        raise TypeError("installation event evidence must be an object")
    payload = deepcopy(value)
    observed_at = payload.get("observedAt")
    if isinstance(observed_at, str):
        payload["observedAt"] = datetime.fromisoformat(observed_at)
    return payload


def _validated_command_result(value: CommandResult) -> CommandResult:
    if not isinstance(value, CommandResult):
        raise TypeError("idempotent command handler must return CommandResult")
    if (
        isinstance(value.status_code, bool)
        or not isinstance(value.status_code, int)
        or not 200 <= value.status_code <= 299
    ):
        raise ValueError("command status must be successful")
    if not isinstance(value.response_json, dict):
        raise TypeError("command response must be a JSON object")
    canonical_json(value.response_json)
    if (
        value.response_etag is not None
        and _STRONG_ETAG.fullmatch(value.response_etag) is None
    ):
        raise ValueError("command response ETag is invalid")
    return value


def _receipt_from_row(row: Any, *, replayed: bool) -> CommandReceipt:
    try:
        result = _validated_command_result(
            CommandResult(
                status_code=row["status_code"],
                response_json=row["response_json"],
                response_etag=row["response_etag"],
            )
        )
        return CommandReceipt(
            status_code=result.status_code,
            response_json=result.response_json,
            response_etag=result.response_etag,
            replayed=replayed,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise LockIntegrityCorruptError() from exc


def _resource_uuid(value: str) -> uuid.UUID:
    try:
        parsed = uuid.UUID(value)
    except (AttributeError, TypeError, ValueError) as exc:
        raise AssetNotFoundError("bundle installation not found") from exc
    if str(parsed) != value:
        raise AssetNotFoundError("bundle installation not found")
    return parsed


def _idempotency_key(value: str) -> str:
    value = _normalized_text(value, "idempotency_key")
    if len(value) > 160 or not value.isprintable():
        raise ValueError("idempotency_key violates the frozen contract")
    return value


def _normalized_text(value: str, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or "\x00" in value
    ):
        raise ValueError(f"{label} must be non-blank and normalized")
    return value
