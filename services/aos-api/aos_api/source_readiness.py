"""Canonical SourceReadiness owner over Data/Adapter facts.

The PostgreSQL reader uses one tenant-scoped, repeatable-read, read-only
transaction.  It never reads source ``props`` or secret payloads.  Missing
exact policy/capability/config revisions remain explicit blockers.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from aos_api.db import connect
from aos_api.source_readiness_contracts import (
    CANONICAL_QYH_SOURCES,
    ExactResourceRef,
    LatestRunObservation,
    ObservationStatus,
    PolicyCheckStatus,
    PolicyObservation,
    SourceCounts,
    SourceReadinessEnvelope,
    SourceReadinessItem,
    SourceReadinessStatus,
    aggregate_source_readiness_status,
)
from aos_api.tenant_scope import (
    ORG_GUC,
    PROJECT_GUC,
    TenantScope,
    apply_transaction_scope,
)


ConnectFactory = Callable[[], AbstractContextManager[Any]]
Clock = Callable[[], datetime]
_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_MAPPING_ROOT = (
    _REPOSITORY_ROOT
    / "bundles"
    / "platforms"
    / "ecommerce-niushop"
    / "content"
    / "mappings"
)
_SCHEMA_PATH = (
    _REPOSITORY_ROOT
    / "bundles"
    / "platforms"
    / "ecommerce-niushop"
    / "content"
    / "schemas"
    / "niushop-schema-fingerprint.json"
)
_MASKING_PATH = _MAPPING_ROOT / "_pii-exclusion.yaml"


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class ObservedSourceFacts:
    pipeline_id: str
    object_type: str
    pipeline_present: bool
    source_present: bool
    latest_run: LatestRunObservation
    source_event_at: datetime | None
    counts: SourceCounts


@dataclass(frozen=True, slots=True)
class AtomicSourceFacts:
    checked_at: datetime
    sources: tuple[ObservedSourceFacts, ...]


class SourceReadinessFactSource(Protocol):
    def read_atomic(self, *, org_id: str, project_id: str) -> AtomicSourceFacts: ...


class PostgresSourceReadinessFactSource:
    """Read only aggregate metadata; source payload and secrets are excluded."""

    def __init__(
        self,
        connect_factory: ConnectFactory = connect,
        clock: Clock = _utc_now,
    ) -> None:
        self._connect_factory = connect_factory
        self._clock = clock

    def read_atomic(self, *, org_id: str, project_id: str) -> AtomicSourceFacts:
        scope = TenantScope(org_id=org_id, project_id=project_id)
        checked_at = self._clock()
        pipeline_ids = [item.pipeline_id for item in CANONICAL_QYH_SOURCES]
        object_types = [item.object_type for item in CANONICAL_QYH_SOURCES]
        with self._connect_factory() as conn:
            conn.rollback()
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            apply_transaction_scope(conn, scope)
            self._assert_scope(conn, scope)
            pipeline_rows = conn.execute(
                """
                SELECT p.id AS pipeline_id, p.object_type_hint,
                       s.id AS source_id
                  FROM meta_pipeline p
                  LEFT JOIN meta_source s
                    ON s.id=p.source_id
                   AND s.org_id=p.org_id AND s.project_id=p.project_id
                 WHERE p.org_id=%s AND p.project_id=%s
                   AND p.id=ANY(%s)
                 ORDER BY p.id
                """,
                (org_id, project_id, pipeline_ids),
            ).fetchall()
            latest_rows = conn.execute(
                """
                WITH ranked AS (
                  SELECT r.*,
                         row_number() OVER (
                           PARTITION BY schedule_id
                           ORDER BY started_at DESC, id DESC
                         ) AS rn
                    FROM meta_schedule_run r
                   WHERE org_id=%s AND project_id=%s
                )
                SELECT s.pipeline_id, r.id, r.status, r.scheduled_for,
                       r.started_at, r.finished_at, r.rows_written,
                       NULLIF(r.error_code, '') AS error_code
                  FROM meta_schedule s
                  LEFT JOIN ranked r ON r.schedule_id=s.id AND r.rn=1
                 WHERE s.org_id=%s AND s.project_id=%s
                   AND s.pipeline_id=ANY(%s)
                 ORDER BY s.pipeline_id
                """,
                (org_id, project_id, org_id, project_id, pipeline_ids),
            ).fetchall()
            source_rows = conn.execute(
                """
                SELECT object_type,
                       count(*) AS source_total,
                       count(*) FILTER (WHERE deleted_at IS NULL) AS source_active,
                       count(*) FILTER (WHERE deleted_at IS NOT NULL) AS source_deleted,
                       max(source_updated_at) AS source_event_at
                  FROM ecom_object
                 WHERE org_id=%s AND workspace_id=%s
                   AND object_type=ANY(%s)
                 GROUP BY object_type
                """,
                (org_id, project_id, object_types),
            ).fetchall()
            projection_rows = conn.execute(
                """
                SELECT object_type, count(*) AS projection_total
                  FROM obj_instance
                 WHERE org_id=%s AND project_id=%s
                   AND object_type=ANY(%s)
                 GROUP BY object_type
                """,
                (org_id, project_id, object_types),
            ).fetchall()

        pipelines = {row["pipeline_id"]: row for row in pipeline_rows}
        latest = {row["pipeline_id"]: row for row in latest_rows}
        source_counts = {row["object_type"]: row for row in source_rows}
        projection_counts = {row["object_type"]: row for row in projection_rows}
        observed: list[ObservedSourceFacts] = []
        for canonical in CANONICAL_QYH_SOURCES:
            pipeline = pipelines.get(canonical.pipeline_id)
            run = latest.get(canonical.pipeline_id)
            source = source_counts.get(canonical.object_type, {})
            projection = projection_counts.get(canonical.object_type, {})
            source_total = int(source.get("source_total") or 0)
            projection_total = int(projection.get("projection_total") or 0)
            observed.append(
                ObservedSourceFacts(
                    pipeline_id=canonical.pipeline_id,
                    object_type=canonical.object_type,
                    pipeline_present=pipeline is not None,
                    source_present=bool(pipeline and pipeline.get("source_id")),
                    latest_run=_latest_run(run),
                    source_event_at=source.get("source_event_at"),
                    counts=SourceCounts(
                        sourceTotal=source_total,
                        sourceActive=int(source.get("source_active") or 0),
                        sourceDeleted=int(source.get("source_deleted") or 0),
                        projectionTotal=projection_total,
                        unexplainedDelta=projection_total - source_total,
                    ),
                )
            )
        return AtomicSourceFacts(checked_at=checked_at, sources=tuple(observed))

    @staticmethod
    def _assert_scope(conn: Any, scope: TenantScope) -> None:
        row = conn.execute(
            f"""
            SELECT current_setting('{ORG_GUC}', true) AS org_id,
                   current_setting('{PROJECT_GUC}', true) AS project_id
            """
        ).fetchone()
        if row is None or (row["org_id"], row["project_id"]) != scope.key:
            raise RuntimeError("SOURCE_READINESS_TENANT_SCOPE_MISMATCH")


class SourceReadinessService:
    def __init__(self, source: SourceReadinessFactSource) -> None:
        self._source = source

    def read(self, *, org_id: str, project_id: str) -> SourceReadinessEnvelope:
        facts = self._source.read_atomic(org_id=org_id, project_id=project_id)
        tenant = {"orgId": org_id, "projectId": project_id}
        schema_ref = _file_ref("SchemaFingerprint", _SCHEMA_PATH)
        masking_ref = _file_ref("MaskingPolicy", _MASKING_PATH)
        items: list[SourceReadinessItem] = []
        by_pipeline = {item.pipeline_id: item for item in facts.sources}
        for canonical in CANONICAL_QYH_SOURCES:
            observed = by_pipeline[canonical.pipeline_id]
            mapping_ref = _file_ref("Mapping", _MAPPING_ROOT / canonical.mapping_file)
            blockers = [
                "SOURCE_CONFIG_EXACT_REF_MISSING",
                "FRESHNESS_POLICY_REF_MISSING",
                "QUALITY_POLICY_REF_MISSING",
                "RECONCILIATION_POLICY_REF_MISSING",
                "QUERY_CAPABILITY_REF_MISSING",
            ]
            if not observed.pipeline_present:
                blockers.append("PIPELINE_NOT_FOUND")
            if not observed.source_present:
                blockers.append("SOURCE_NOT_FOUND")
            if observed.latest_run.status != ObservationStatus.SUCCEEDED:
                blockers.append("LATEST_RUN_NOT_SUCCEEDED")
            if mapping_ref is None:
                blockers.append("MAPPING_EXACT_REF_MISSING")
            if schema_ref is None:
                blockers.append("SCHEMA_EXACT_REF_MISSING")
            if masking_ref is None:
                blockers.append("MASKING_POLICY_EXACT_REF_MISSING")
            blockers = sorted(set(blockers))
            items.append(
                SourceReadinessItem(
                    tenant=tenant,
                    sourceId="niushop-qyh",
                    pipelineId=canonical.pipeline_id,
                    objectType=canonical.object_type,
                    status=SourceReadinessStatus.BLOCKED,
                    checkedAt=facts.checked_at,
                    observedAt=observed.latest_run.finished_at,
                    sourceEventAt=observed.source_event_at,
                    dataCutoff=observed.source_event_at,
                    mappingRef=mapping_ref,
                    schemaRef=schema_ref,
                    maskingPolicyRef=masking_ref,
                    latestRun=observed.latest_run,
                    counts=observed.counts,
                    quality=PolicyObservation(
                        status=PolicyCheckStatus.UNKNOWN,
                        summary="quality policy revision is not available",
                    ),
                    reconciliation=PolicyObservation(
                        status=PolicyCheckStatus.UNKNOWN,
                        summary="counts are observed; no exact reconciliation policy is available",
                    ),
                    reasons=blockers,
                    blockers=blockers,
                )
            )
        status = aggregate_source_readiness_status([item.status for item in items])
        return SourceReadinessEnvelope(
            tenant=tenant,
            checkedAt=facts.checked_at,
            cutoffAt=facts.checked_at,
            status=status,
            sources=items,
        )


def build_source_readiness_service() -> SourceReadinessService:
    return SourceReadinessService(PostgresSourceReadinessFactSource())


def _file_ref(resource_type: str, path: Path) -> ExactResourceRef | None:
    try:
        payload = path.read_bytes()
    except FileNotFoundError:
        return None
    digest = hashlib.sha256(payload).hexdigest()
    return ExactResourceRef(
        resourceType=resource_type,
        resourceId=str(path.relative_to(_REPOSITORY_ROOT)),
        revision=digest,
        contentHash=digest,
        authority="git:file",
    )


def _latest_run(row: Any | None) -> LatestRunObservation:
    if not row or not row.get("id"):
        return LatestRunObservation()
    raw_status = str(row.get("status") or "unknown").strip().lower()
    try:
        status = ObservationStatus(raw_status)
    except ValueError:
        status = ObservationStatus.UNKNOWN
    return LatestRunObservation(
        runId=str(row["id"]),
        status=status,
        scheduledFor=row.get("scheduled_for"),
        startedAt=row.get("started_at"),
        finishedAt=row.get("finished_at"),
        rowsWritten=row.get("rows_written"),
        errorCode=row.get("error_code"),
    )
