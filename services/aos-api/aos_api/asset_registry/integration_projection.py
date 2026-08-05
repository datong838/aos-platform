"""Database-clock expiry projection for M4 Integration Cases.

The projector owns only freshness maintenance.  Canonical Evidence selection,
stage evaluation, snapshots, events, metrics, and PostgreSQL invariants remain
owned by :mod:`integration_store` and the frozen stage policy.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import psycopg
from psycopg import errors

from aos_api.asset_registry.errors import (
    AssetNotFoundError,
    EvidenceIntegrityCorruptError,
    EvidenceReferenceInvalidError,
    RevisionConflictError,
)
from aos_api.asset_registry.integration_contracts import IntegrationStage
from aos_api.asset_registry.integration_store import (
    ConnectFactory,
    IntegrationPersistenceError,
    PostgresIntegrationStore,
)
from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
from aos_api.db import connect

_EXPIRY_CAUSE = "evidence_expired"
_MAX_BATCH_SIZE = 1000


@dataclass(frozen=True, slots=True)
class ProjectionRefreshResult:
    """Outcome of one freshness check at one database-controlled cutoff."""

    case_id: str
    cutoff_at: datetime
    projected: bool
    stage_changed: bool
    snapshot_revision: int
    etag_version: int
    computed_stage: IntegrationStage


@dataclass(frozen=True, slots=True)
class ProjectionFailure:
    """Safe, auditable identity for one isolated poison-pill failure."""

    case_ref: str
    code: str


@dataclass(frozen=True, slots=True)
class ExpiryProjectionBatchResult:
    """Auditable result for one bounded ``SKIP LOCKED`` expiry batch."""

    cutoff_at: datetime
    selected_case_ids: tuple[str, ...]
    selected_case_refs: tuple[str, ...]
    results: tuple[ProjectionRefreshResult, ...]
    failures: tuple[ProjectionFailure, ...]

    @property
    def selected_count(self) -> int:
        return len(self.selected_case_ids)

    @property
    def projected_count(self) -> int:
        return sum(item.projected for item in self.results)

    @property
    def processed_case_refs(self) -> tuple[str, ...]:
        return self.selected_case_refs

    @property
    def failed_case_refs(self) -> tuple[str, ...]:
        return tuple(item.case_ref for item in self.failures)


class IntegrationExpiryProjector:
    """Refresh due current Cases without ever serving an expired projection.

    Every operation obtains one PostgreSQL cutoff and injects that same value
    into the Store transaction.  A failure is deliberately raised to the
    caller: read paths must fail closed instead of returning a stale high stage.
    """

    def __init__(self, connect_factory: ConnectFactory = connect) -> None:
        self._connect_factory = connect_factory

    def refresh_case_if_due(
        self,
        *,
        org_id: str,
        project_id: str,
        case_id: str,
    ) -> ProjectionRefreshResult:
        """Lock one Case and refresh it iff its projection is due at read time."""

        org_id = _normalized_text(org_id, "org_id")
        project_id = _normalized_text(project_id, "project_id")
        case_uuid = _case_uuid(case_id)
        try:
            with self._connect_factory() as conn:
                apply_asset_transaction_scope(conn, org_id=org_id, project_id=project_id)
                case = conn.execute(
                    """
                    SELECT c.org_id,c.project_id,c.case_pk,c.case_id,c.scope,
                           i.instance_pk,i.current_revision,i.etag_version,
                           p.snapshot_revision,p.computed_stage,
                           p.next_projection_at
                      FROM integration_case AS c
                      JOIN integration_instance AS i
                        ON i.org_id=c.org_id AND i.project_id=c.project_id
                       AND i.case_pk=c.case_pk
                      JOIN integration_case_projection AS p
                        ON p.org_id=c.org_id AND p.project_id=c.project_id
                       AND p.case_pk=c.case_pk
                     WHERE c.org_id=%s AND c.project_id=%s AND c.case_id=%s
                     FOR UPDATE OF c,i,p
                    """,
                    (org_id, project_id, case_uuid),
                ).fetchone()
                if case is None:
                    raise AssetNotFoundError("integration case not found")
                cutoff_at = _database_cutoff(conn)
                if case["scope"] != "current" or not _is_due(case, cutoff_at):
                    result = _unchanged_result(case, cutoff_at)
                else:
                    result = _project_locked_case(conn, case, cutoff_at)
                conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
                conn.commit()
                return result
        except _PASSTHROUGH_ERRORS:
            raise
        except (
            errors.CheckViolation,
            errors.ForeignKeyViolation,
            errors.UniqueViolation,
        ) as exc:
            raise EvidenceReferenceInvalidError(
                "expiry projection violates canonical persistence constraints"
            ) from exc
        except psycopg.Error as exc:
            raise IntegrationPersistenceError() from exc

    def project_expired_batch(
        self,
        *,
        org_id: str | None = None,
        project_id: str | None = None,
        batch_size: int = 100,
    ) -> ExpiryProjectionBatchResult:
        """Project one bounded due batch using ``SKIP LOCKED``.

        All selected Cases share the exact same cutoff.  Each Case receives an
        independent transaction so a poison pill rolls back completely and is
        reported without blocking later healthy Cases in the same batch.
        """

        if (
            isinstance(batch_size, bool)
            or not isinstance(batch_size, int)
            or not 1 <= batch_size <= _MAX_BATCH_SIZE
        ):
            raise ValueError("batch_size must be an integer between 1 and 1000")
        if (org_id is None) != (project_id is None):
            raise ValueError("org_id and project_id must be supplied together")
        if org_id is None or project_id is None:
            raise ValueError("tenant scope is required for expiry projection")
        org_id = _normalized_text(org_id, "org_id")
        project_id = _normalized_text(project_id, "project_id")
        try:
            with self._connect_factory() as conn:
                apply_asset_transaction_scope(conn, org_id=org_id, project_id=project_id)
                cutoff_at = _database_cutoff(conn)
                conn.commit()
        except psycopg.Error as exc:
            raise IntegrationPersistenceError() from exc

        attempted_pks: list[uuid.UUID] = []
        selected_case_ids: list[str] = []
        selected_case_refs: list[str] = []
        results: list[ProjectionRefreshResult] = []
        failures: list[ProjectionFailure] = []
        while len(selected_case_ids) < batch_size:
            case_id: str | None = None
            case_ref: str | None = None
            try:
                with self._connect_factory() as conn:
                    apply_asset_transaction_scope(conn, org_id=org_id, project_id=project_id)
                    case = conn.execute(
                        """
                        SELECT c.org_id,c.project_id,c.case_pk,c.case_id,c.scope,
                               i.instance_pk,i.current_revision,i.etag_version,
                               p.snapshot_revision,p.computed_stage,
                               p.next_projection_at
                          FROM integration_case AS c
                          JOIN integration_instance AS i
                            ON i.org_id=c.org_id AND i.project_id=c.project_id
                           AND i.case_pk=c.case_pk
                          JOIN integration_case_projection AS p
                            ON p.org_id=c.org_id AND p.project_id=c.project_id
                           AND p.case_pk=c.case_pk
                         WHERE c.scope='current'
                           AND (%s::TEXT IS NULL OR c.org_id=%s)
                           AND (%s::TEXT IS NULL OR c.project_id=%s)
                           AND p.next_projection_at IS NOT NULL
                           AND p.next_projection_at<=%s
                           AND NOT (c.case_pk=ANY(%s::UUID[]))
                         ORDER BY p.next_projection_at,c.org_id,c.project_id,c.case_pk
                         LIMIT 1
                         FOR UPDATE OF c,i,p SKIP LOCKED
                        """,
                        (
                            org_id,
                            org_id,
                            project_id,
                            project_id,
                            cutoff_at,
                            attempted_pks,
                        ),
                    ).fetchone()
                    if case is None:
                        conn.commit()
                        break
                    attempted_pks.append(case["case_pk"])
                    case_id = str(case["case_id"])
                    case_ref = _case_ref(case)
                    selected_case_ids.append(case_id)
                    selected_case_refs.append(case_ref)
                    results.append(_project_locked_case(conn, case, cutoff_at))
                    conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
                    conn.commit()
            except EvidenceIntegrityCorruptError:
                failures.append(
                    ProjectionFailure(
                        case_ref=_required_case_ref(case_ref),
                        code="evidence_integrity_corrupt",
                    )
                )
            except EvidenceReferenceInvalidError:
                failures.append(
                    ProjectionFailure(
                        case_ref=_required_case_ref(case_ref),
                        code="evidence_reference_invalid",
                    )
                )
            except RevisionConflictError:
                failures.append(
                    ProjectionFailure(
                        case_ref=_required_case_ref(case_ref),
                        code="revision_conflict",
                    )
                )
            except (
                errors.CheckViolation,
                errors.ForeignKeyViolation,
                errors.UniqueViolation,
            ):
                failures.append(
                    ProjectionFailure(
                        case_ref=_required_case_ref(case_ref),
                        code="persistence_constraint_failed",
                    )
                )
            except psycopg.Error:
                if case_id is None:
                    raise IntegrationPersistenceError() from None
                failures.append(
                    ProjectionFailure(
                        case_ref=_required_case_ref(case_ref),
                        code="persistence_failed",
                    )
                )
        return ExpiryProjectionBatchResult(
            cutoff_at=cutoff_at,
            selected_case_ids=tuple(selected_case_ids),
            selected_case_refs=tuple(selected_case_refs),
            results=tuple(results),
            failures=tuple(failures),
        )


_PASSTHROUGH_ERRORS = (
    AssetNotFoundError,
    RevisionConflictError,
    EvidenceReferenceInvalidError,
    EvidenceIntegrityCorruptError,
)


def _database_cutoff(conn: Any) -> datetime:
    row = conn.execute("SELECT clock_timestamp() AS cutoff_at").fetchone()
    if row is None or not isinstance(row["cutoff_at"], datetime):
        raise EvidenceIntegrityCorruptError()
    value = row["cutoff_at"]
    if value.tzinfo is None or value.utcoffset() is None:
        raise EvidenceIntegrityCorruptError()
    return value.astimezone(UTC)


def _is_due(case: Any, cutoff_at: datetime) -> bool:
    next_projection_at = case["next_projection_at"]
    if next_projection_at is None:
        return False
    if (
        not isinstance(next_projection_at, datetime)
        or next_projection_at.tzinfo is None
        or next_projection_at.utcoffset() is None
    ):
        raise EvidenceIntegrityCorruptError()
    return next_projection_at <= cutoff_at


def _project_locked_case(
    conn: Any, case: Any, cutoff_at: datetime
) -> ProjectionRefreshResult:
    store = PostgresIntegrationStore(clock=lambda: cutoff_at)
    projected = store.project_case_in_transaction(
        conn,
        org_id=case["org_id"],
        project_id=case["project_id"],
        case=case,
        if_match_etag=case["etag_version"],
        cause=_EXPIRY_CAUSE,
    )
    response = projected.response
    if response.cutoff_at != cutoff_at:
        raise EvidenceIntegrityCorruptError()
    return ProjectionRefreshResult(
        case_id=str(case["case_id"]),
        cutoff_at=cutoff_at,
        projected=True,
        stage_changed=projected.stage_event is not None,
        snapshot_revision=response.snapshot_revision,
        etag_version=response.etag_version,
        computed_stage=response.computed_stage,
    )


def _unchanged_result(case: Any, cutoff_at: datetime) -> ProjectionRefreshResult:
    try:
        stage = IntegrationStage(case["computed_stage"])
    except (KeyError, TypeError, ValueError) as exc:
        raise EvidenceIntegrityCorruptError() from exc
    return ProjectionRefreshResult(
        case_id=str(case["case_id"]),
        cutoff_at=cutoff_at,
        projected=False,
        stage_changed=False,
        snapshot_revision=case["snapshot_revision"],
        etag_version=case["etag_version"],
        computed_stage=stage,
    )


def _case_uuid(value: str) -> uuid.UUID:
    try:
        parsed = uuid.UUID(value)
    except (AttributeError, TypeError, ValueError) as exc:
        raise AssetNotFoundError("integration case not found") from exc
    if str(parsed) != value:
        raise AssetNotFoundError("integration case not found")
    return parsed


def _normalized_text(value: str, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or any(ord(char) < 32 for char in value)
    ):
        raise ValueError(f"{label} must be normalized text")
    return value


def _required_case_ref(value: str | None) -> str:
    if value is None:
        raise IntegrationPersistenceError()
    return value


def _case_ref(case: Any) -> str:
    return "/".join(
        (str(case["org_id"]), str(case["project_id"]), str(case["case_id"]))
    )
