"""Canonical SourceReadiness owner over Data/Adapter facts.

The PostgreSQL reader uses one tenant-scoped, repeatable-read, read-only
transaction.  It never reads source ``props`` or secret payloads.  Missing
exact policy/capability/config revisions remain explicit blockers.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

from aos_api.db import connect
from aos_api.qyh_cron_scheduler import next_run_at
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
_POLICY_ROOT = _MAPPING_ROOT.parent / "policies"
_FRESHNESS_POLICY_PATH = _POLICY_ROOT / "source-freshness.v1.json"
_QUALITY_POLICY_PATH = _POLICY_ROOT / "source-quality.v1.json"
_RECONCILIATION_POLICY_PATH = _POLICY_ROOT / "source-reconciliation.v1.json"
_QUERY_BINDING_ID = "ecommerce.data_advisor.strategy.plan.r2"


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class ObservedSourceFacts:
    pipeline_id: str
    object_type: str
    pipeline_present: bool
    source_present: bool
    source_id: str | None
    target: str | None
    schedule_id: str | None
    cron: str | None
    schedule_enabled: bool
    ingest_kind: str | None
    ingest_pipeline_id: str | None
    ingest_source_id: str | None
    latest_run: LatestRunObservation
    source_event_at: datetime | None
    counts: SourceCounts


@dataclass(frozen=True, slots=True)
class AtomicSourceFacts:
    checked_at: datetime
    sources: tuple[ObservedSourceFacts, ...]
    query_capability: "ObservedQueryCapability | None"


@dataclass(frozen=True, slots=True)
class ObservedQueryCapability:
    binding_id: str
    capability_id: str | None
    version: int
    status: str
    dependency_snapshot_hash: str | None


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
                SELECT p.id AS pipeline_id, p.object_type_hint, p.target,
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
                SELECT s.pipeline_id, s.id AS schedule_id, s.cron,
                       s.enabled AS schedule_enabled,
                       s.ingest->>'kind' AS ingest_kind,
                       s.ingest->>'pipelineId' AS ingest_pipeline_id,
                       s.ingest->>'sourceId' AS ingest_source_id,
                       r.id, r.status, r.scheduled_for,
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
            query_capability_row = conn.execute(
                """
                SELECT binding_id, capability_ref->>'assetId' AS capability_id,
                       version, status, dependency_snapshot_hash
                  FROM aip_capability_binding
                 WHERE org_id=%s AND project_id=%s AND binding_id=%s
                """,
                (org_id, project_id, _QUERY_BINDING_ID),
            ).fetchone()

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
                    source_id=pipeline.get("source_id") if pipeline else None,
                    target=pipeline.get("target") if pipeline else None,
                    schedule_id=run.get("schedule_id") if run else None,
                    cron=run.get("cron") if run else None,
                    schedule_enabled=bool(run and run.get("schedule_enabled")),
                    ingest_kind=run.get("ingest_kind") if run else None,
                    ingest_pipeline_id=run.get("ingest_pipeline_id") if run else None,
                    ingest_source_id=run.get("ingest_source_id") if run else None,
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
        query_capability = None
        if query_capability_row:
            query_capability = ObservedQueryCapability(
                binding_id=str(query_capability_row["binding_id"]),
                capability_id=query_capability_row.get("capability_id"),
                version=int(query_capability_row["version"]),
                status=str(query_capability_row["status"]),
                dependency_snapshot_hash=query_capability_row.get(
                    "dependency_snapshot_hash"
                ),
            )
        return AtomicSourceFacts(
            checked_at=checked_at,
            sources=tuple(observed),
            query_capability=query_capability,
        )

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
        freshness_policy_ref = _file_ref("FreshnessPolicy", _FRESHNESS_POLICY_PATH)
        quality_policy_ref = _file_ref("QualityPolicy", _QUALITY_POLICY_PATH)
        reconciliation_policy_ref = _file_ref(
            "ReconciliationPolicy", _RECONCILIATION_POLICY_PATH
        )
        freshness_policy = _json_file(_FRESHNESS_POLICY_PATH)
        query_capability_ref = _query_capability_ref(facts.query_capability)
        items: list[SourceReadinessItem] = []
        by_pipeline = {item.pipeline_id: item for item in facts.sources}
        for canonical in CANONICAL_QYH_SOURCES:
            observed = by_pipeline[canonical.pipeline_id]
            mapping_ref = _file_ref("Mapping", _MAPPING_ROOT / canonical.mapping_file)
            source_config_ref = _source_config_ref(
                tenant=tenant,
                observed=observed,
            )
            blockers: list[str] = []
            reasons: list[str] = []
            expected_cron = _expected_cron(freshness_policy, canonical.pipeline_id)
            if source_config_ref is None:
                blockers.append("SOURCE_CONFIG_EXACT_REF_MISSING")
            if freshness_policy_ref is None or expected_cron is None:
                blockers.append("FRESHNESS_POLICY_REF_MISSING")
            if quality_policy_ref is None:
                blockers.append("QUALITY_POLICY_REF_MISSING")
            if reconciliation_policy_ref is None:
                blockers.append("RECONCILIATION_POLICY_REF_MISSING")
            if query_capability_ref is None:
                blockers.append("QUERY_CAPABILITY_REF_MISSING")
            if not observed.pipeline_present:
                blockers.append("PIPELINE_NOT_FOUND")
            if not observed.source_present:
                blockers.append("SOURCE_NOT_FOUND")
            if not observed.schedule_id:
                blockers.append("SCHEDULE_NOT_FOUND")
            elif not observed.schedule_enabled:
                blockers.append("SCHEDULE_DISABLED")
            if expected_cron and observed.cron != expected_cron:
                blockers.append("SCHEDULE_CRON_POLICY_MISMATCH")
            if observed.ingest_kind != "pipeline-live-v1":
                blockers.append("SCHEDULE_INGEST_KIND_MISMATCH")
            if observed.ingest_pipeline_id != canonical.pipeline_id:
                blockers.append("SCHEDULE_PIPELINE_REF_MISMATCH")
            if observed.ingest_source_id != "niushop-qyh":
                blockers.append("SCHEDULE_SOURCE_REF_MISMATCH")
            if mapping_ref is None:
                blockers.append("MAPPING_EXACT_REF_MISSING")
            if schema_ref is None:
                blockers.append("SCHEMA_EXACT_REF_MISSING")
            if masking_ref is None:
                blockers.append("MASKING_POLICY_EXACT_REF_MISSING")

            quality = _quality_observation(
                observed=observed,
                rule_ref=quality_policy_ref,
                mapping_ref=mapping_ref,
                schema_ref=schema_ref,
                masking_ref=masking_ref,
            )
            reconciliation = _reconciliation_observation(
                observed=observed,
                rule_ref=reconciliation_policy_ref,
            )
            freshness_expires_at = _freshness_expiry(
                observed=observed,
                expected_cron=expected_cron,
                policy=freshness_policy,
            )
            status = _readiness_status(
                checked_at=facts.checked_at,
                observed=observed,
                blockers=blockers,
                freshness_expires_at=freshness_expires_at,
                quality=quality,
                reconciliation=reconciliation,
            )
            if observed.latest_run.status != ObservationStatus.SUCCEEDED:
                reasons.append("LATEST_RUN_NOT_SUCCEEDED")
            if quality.status == PolicyCheckStatus.FAIL:
                reasons.append("SOURCE_QUALITY_FAILED")
            if reconciliation.status == PolicyCheckStatus.FAIL:
                reasons.append("SOURCE_RECONCILIATION_FAILED")
            if (
                freshness_expires_at is not None
                and facts.checked_at > freshness_expires_at
            ):
                reasons.append("SOURCE_DATA_STALE")
            if status == SourceReadinessStatus.EMPTY:
                reasons.append("SOURCE_EMPTY")
            blockers = sorted(set(blockers))
            reasons = sorted(set([*reasons, *blockers]))
            items.append(
                SourceReadinessItem(
                    tenant=tenant,
                    sourceId="niushop-qyh",
                    pipelineId=canonical.pipeline_id,
                    objectType=canonical.object_type,
                    status=status,
                    checkedAt=facts.checked_at,
                    observedAt=observed.latest_run.finished_at,
                    sourceEventAt=observed.source_event_at,
                    dataCutoff=observed.latest_run.finished_at,
                    freshnessExpiresAt=freshness_expires_at,
                    sourceConfigRef=source_config_ref,
                    mappingRef=mapping_ref,
                    schemaRef=schema_ref,
                    maskingPolicyRef=masking_ref,
                    freshnessPolicyRef=freshness_policy_ref,
                    qualityPolicyRef=quality_policy_ref,
                    reconciliationPolicyRef=reconciliation_policy_ref,
                    queryCapabilityRef=query_capability_ref,
                    latestRun=observed.latest_run,
                    counts=observed.counts,
                    quality=quality,
                    reconciliation=reconciliation,
                    reasons=reasons,
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


def _json_file(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _canonical_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _source_config_ref(
    *, tenant: dict[str, str], observed: ObservedSourceFacts
) -> ExactResourceRef | None:
    if not observed.pipeline_present or not observed.schedule_id:
        return None
    payload = {
        "schemaVersion": "aos.source-readiness.source-config/v1",
        "tenant": tenant,
        "pipelineId": observed.pipeline_id,
        "objectType": observed.object_type,
        "sourceId": observed.source_id,
        "target": observed.target,
        "schedule": {
            "id": observed.schedule_id,
            "cron": observed.cron,
            "enabled": observed.schedule_enabled,
            "ingestKind": observed.ingest_kind,
            "pipelineId": observed.ingest_pipeline_id,
            "sourceId": observed.ingest_source_id,
        },
    }
    digest = _canonical_hash(payload)
    return ExactResourceRef(
        resourceType="SourceConfig",
        resourceId=f"{tenant['orgId']}/{tenant['projectId']}/{observed.pipeline_id}",
        revision=digest,
        contentHash=digest,
        authority="postgres:meta_pipeline+meta_schedule",
    )


def _query_capability_ref(
    observed: ObservedQueryCapability | None,
) -> ExactResourceRef | None:
    if (
        observed is None
        or observed.binding_id != _QUERY_BINDING_ID
        or observed.capability_id != "strategy.plan"
        or observed.status != "active"
        or not observed.dependency_snapshot_hash
        or len(observed.dependency_snapshot_hash) != 64
    ):
        return None
    return ExactResourceRef(
        resourceType="CapabilityBinding",
        resourceId=observed.binding_id,
        revision=str(observed.version),
        contentHash=observed.dependency_snapshot_hash,
        authority="postgres:aip_capability_binding",
    )


def _expected_cron(policy: dict[str, Any] | None, pipeline_id: str) -> str | None:
    if not policy or policy.get("schemaVersion") != (
        "aos.source-readiness.freshness-policy/v1"
    ):
        return None
    cron_by_pipeline = policy.get("expectedCronByPipeline")
    if not isinstance(cron_by_pipeline, dict):
        return None
    cron = cron_by_pipeline.get(pipeline_id)
    return cron if isinstance(cron, str) and cron.strip() else None


def _freshness_expiry(
    *,
    observed: ObservedSourceFacts,
    expected_cron: str | None,
    policy: dict[str, Any] | None,
) -> datetime | None:
    if not observed.latest_run.finished_at or not expected_cron or not policy:
        return None
    grace = policy.get("graceMinutes")
    if not isinstance(grace, int) or grace < 0:
        return None
    next_expected = next_run_at(expected_cron, observed.latest_run.finished_at)
    return next_expected + timedelta(minutes=grace) if next_expected else None


def _quality_observation(
    *,
    observed: ObservedSourceFacts,
    rule_ref: ExactResourceRef | None,
    mapping_ref: ExactResourceRef | None,
    schema_ref: ExactResourceRef | None,
    masking_ref: ExactResourceRef | None,
) -> PolicyObservation:
    if rule_ref is None:
        return PolicyObservation(
            status=PolicyCheckStatus.UNKNOWN,
            summary="quality policy exact revision is unavailable",
        )
    checks = (
        observed.pipeline_present,
        observed.source_present,
        observed.latest_run.status == ObservationStatus.SUCCEEDED,
        observed.latest_run.rows_written is not None,
        mapping_ref is not None,
        schema_ref is not None,
        masking_ref is not None,
    )
    passed = all(checks)
    return PolicyObservation(
        status=PolicyCheckStatus.PASS if passed else PolicyCheckStatus.FAIL,
        ruleRef=rule_ref,
        summary=(
            "metadata quality checks passed; no row-level metric was inferred"
            if passed
            else "one or more observable metadata quality checks failed"
        ),
    )


def _reconciliation_observation(
    *, observed: ObservedSourceFacts, rule_ref: ExactResourceRef | None
) -> PolicyObservation:
    if rule_ref is None:
        return PolicyObservation(
            status=PolicyCheckStatus.UNKNOWN,
            summary="reconciliation policy exact revision is unavailable",
        )
    counts = observed.counts
    passed = (
        counts.source_total is not None
        and counts.projection_total is not None
        and counts.unexplained_delta == 0
        and counts.source_total == counts.projection_total
    )
    return PolicyObservation(
        status=PolicyCheckStatus.PASS if passed else PolicyCheckStatus.FAIL,
        ruleRef=rule_ref,
        summary=(
            "source and projection counts reconcile in the same snapshot"
            if passed
            else "source and projection counts do not reconcile"
        ),
    )


def _readiness_status(
    *,
    checked_at: datetime,
    observed: ObservedSourceFacts,
    blockers: list[str],
    freshness_expires_at: datetime | None,
    quality: PolicyObservation,
    reconciliation: PolicyObservation,
) -> SourceReadinessStatus:
    if blockers:
        return SourceReadinessStatus.BLOCKED
    if observed.latest_run.status == ObservationStatus.FAILED:
        return SourceReadinessStatus.FAILED
    if observed.latest_run.status != ObservationStatus.SUCCEEDED:
        return SourceReadinessStatus.UNKNOWN
    if (
        quality.status == PolicyCheckStatus.FAIL
        or reconciliation.status == PolicyCheckStatus.FAIL
    ):
        return SourceReadinessStatus.FAILED
    if (
        quality.status != PolicyCheckStatus.PASS
        or reconciliation.status != PolicyCheckStatus.PASS
        or freshness_expires_at is None
    ):
        return SourceReadinessStatus.UNKNOWN
    if checked_at > freshness_expires_at:
        return SourceReadinessStatus.STALE
    if observed.counts.source_total == 0 and observed.counts.projection_total == 0:
        return SourceReadinessStatus.EMPTY
    return SourceReadinessStatus.READY


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
