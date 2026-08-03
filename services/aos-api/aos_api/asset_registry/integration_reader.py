"""Authorized PostgreSQL read models for M4 Integration Cases."""

from __future__ import annotations

import json
import uuid
from collections.abc import Collection, Sequence
from datetime import datetime
from typing import Any

import psycopg

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.asset_registry.errors import (
    AssetNotFoundError,
    EvidenceIntegrityCorruptError,
)
from aos_api.asset_registry.integration_contracts import (
    INTEGRATION_CASE_DETAIL_ADAPTER,
    INTEGRATION_EVIDENCE_ADAPTER,
    CurrentIntegrationCaseListItem,
    EvidenceType,
    IntegrationBlocker,
    IntegrationCaseListResponse,
    IntegrationCaseScope,
    IntegrationCaseStats,
    IntegrationCaseTimelineResponse,
    IntegrationMetric,
    IntegrationStage,
    IntegrationStageEvent,
    LatestEvidenceSummary,
    ReferenceIntegrationCaseListItem,
)
from aos_api.asset_registry.integration_store import IntegrationPersistenceError
from aos_api.db import connect

_VISIBLE = """
NOT EXISTS (
  SELECT 1
    FROM jsonb_array_elements_text(c.required_markings) AS required(marking)
   WHERE NOT (required.marking = ANY(%s))
)
"""


class PostgresIntegrationCaseReader:
    """Build strict public projections only after tenant and marking filtering."""

    def __init__(self, connect_factory=connect) -> None:
        self._connect_factory = connect_factory

    def list_cases(
        self,
        *,
        org_id: str,
        project_id: str,
        scope: str,
        allowed_markings: Collection[str],
        limit: int,
        offset: int,
    ) -> IntegrationCaseListResponse:
        markings = _markings(allowed_markings)
        try:
            with self._connect_factory() as conn:
                cutoff = conn.execute(
                    "SELECT statement_timestamp() AS cutoff"
                ).fetchone()["cutoff"]
                total = conn.execute(
                    f"""SELECT COUNT(*) AS total
                           FROM integration_case c
                          WHERE c.org_id=%s AND c.project_id=%s AND c.scope=%s
                            AND {_VISIBLE}""",
                    (org_id, project_id, scope, markings),
                ).fetchone()["total"]
                rows = conn.execute(
                    f"""SELECT c.*,i.etag_version,r.installation_pk,
                                  bi.installation_id,r.overlay_revision,
                                  p.snapshot_revision,p.computed_stage,p.cutoff_at,
                                  p.blocker_count,p.connector_count,p.pipeline_count,
                                  p.dataset_row_count,p.latency_ms,s.snapshot_json,
                                  s.snapshot_hash
                             FROM integration_case c
                             JOIN integration_instance i
                               ON i.org_id=c.org_id AND i.project_id=c.project_id
                              AND i.case_pk=c.case_pk
                             JOIN integration_instance_revision r
                               ON r.org_id=i.org_id AND r.project_id=i.project_id
                              AND r.instance_pk=i.instance_pk
                              AND r.revision=i.current_revision
                             JOIN integration_case_projection p
                               ON p.org_id=c.org_id AND p.project_id=c.project_id
                              AND p.case_pk=c.case_pk
                             JOIN integration_evidence_snapshot s
                               ON s.org_id=p.org_id AND s.project_id=p.project_id
                              AND s.case_pk=p.case_pk
                              AND s.snapshot_revision=p.snapshot_revision
                        LEFT JOIN bundle_installation bi
                               ON bi.org_id=r.org_id AND bi.project_id=r.project_id
                              AND bi.installation_pk=r.installation_pk
                            WHERE c.org_id=%s AND c.project_id=%s AND c.scope=%s
                              AND {_VISIBLE}
                         ORDER BY c.created_at,c.case_pk
                            LIMIT %s OFFSET %s""",
                    (org_id, project_id, scope, markings, limit, offset),
                ).fetchall()
                for row in rows:
                    _verify_snapshot(row)
                items = [_list_item(row) for row in rows]
                stats = (
                    self._current_stats(
                        conn,
                        org_id=org_id,
                        project_id=project_id,
                        markings=markings,
                        cutoff=cutoff,
                    )
                    if scope == IntegrationCaseScope.CURRENT.value
                    else None
                )
                return IntegrationCaseListResponse.model_validate(
                    {
                        "items": items,
                        "scope": scope,
                        "total": total,
                        "limit": limit,
                        "offset": offset,
                        "stats": stats,
                    }
                )
        except (AssetNotFoundError, EvidenceIntegrityCorruptError):
            raise
        except psycopg.Error as exc:
            raise IntegrationPersistenceError() from exc

    def get_case_detail(
        self,
        *,
        org_id: str,
        project_id: str,
        case_id: str,
        allowed_markings: Collection[str],
    ):
        markings = _markings(allowed_markings)
        try:
            case_uuid = uuid.UUID(case_id)
        except (TypeError, ValueError) as exc:
            raise AssetNotFoundError("integration case not found") from exc
        try:
            with self._connect_factory() as conn:
                row = conn.execute(
                    f"""SELECT c.*,i.current_revision,i.etag_version,
                                  r.installation_revision,r.lock_revision,r.lock_hash,
                                  r.overlay_revision,bi.installation_id,
                                  bc.composition_id,p.snapshot_revision,
                                  p.computed_stage,p.cutoff_at,p.next_projection_at,
                                  p.stage_gates_json,p.blockers_json,
                                  p.connector_count,p.pipeline_count,
                                  p.dataset_row_count,p.latency_ms,p.blocker_count,
                                  s.snapshot_json,s.snapshot_hash
                             FROM integration_case c
                             JOIN integration_instance i
                               ON i.org_id=c.org_id AND i.project_id=c.project_id
                              AND i.case_pk=c.case_pk
                             JOIN integration_instance_revision r
                               ON r.org_id=i.org_id AND r.project_id=i.project_id
                              AND r.instance_pk=i.instance_pk
                              AND r.revision=i.current_revision
                             JOIN integration_case_projection p
                               ON p.org_id=c.org_id AND p.project_id=c.project_id
                              AND p.case_pk=c.case_pk
                             JOIN integration_evidence_snapshot s
                               ON s.org_id=p.org_id AND s.project_id=p.project_id
                              AND s.case_pk=p.case_pk
                              AND s.snapshot_revision=p.snapshot_revision
                        LEFT JOIN bundle_installation bi
                               ON bi.org_id=r.org_id AND bi.project_id=r.project_id
                              AND bi.installation_pk=r.installation_pk
                        LEFT JOIN bundle_composition bc
                               ON bc.org_id=r.org_id AND bc.project_id=r.project_id
                              AND bc.composition_pk=r.composition_pk
                            WHERE c.org_id=%s AND c.project_id=%s AND c.case_id=%s
                              AND {_VISIBLE}""",
                    (org_id, project_id, case_uuid, markings),
                ).fetchone()
                if row is None:
                    raise AssetNotFoundError("integration case not found")
                snapshot = _verify_snapshot(row)
                evidence = [_evidence_summary(item) for item in snapshot["evidence"]]
                payload = {
                    **_list_payload(row),
                    "installationRevision": row["installation_revision"],
                    "compositionId": _uuid_text(row["composition_id"]),
                    "lockRevision": row["lock_revision"],
                    "lockHash": row["lock_hash"],
                    "stageGates": row["stage_gates_json"],
                    "latestEvidence": evidence,
                    "blockers": [
                        IntegrationBlocker.model_validate_json(json.dumps(item))
                        for item in row["blockers_json"]
                    ],
                    "nextProjectionAt": row["next_projection_at"],
                    "metrics": _detail_metrics(row),
                }
                return INTEGRATION_CASE_DETAIL_ADAPTER.validate_python(payload)
        except (AssetNotFoundError, EvidenceIntegrityCorruptError):
            raise
        except psycopg.Error as exc:
            raise IntegrationPersistenceError() from exc

    def list_case_timeline(
        self,
        *,
        org_id: str,
        project_id: str,
        case_id: str,
        allowed_markings: Collection[str],
        limit: int,
        offset: int,
    ) -> IntegrationCaseTimelineResponse:
        markings = _markings(allowed_markings)
        try:
            case_uuid = uuid.UUID(case_id)
        except (TypeError, ValueError) as exc:
            raise AssetNotFoundError("integration case not found") from exc
        try:
            with self._connect_factory() as conn:
                case = conn.execute(
                    f"""SELECT c.case_pk,c.scope
                           FROM integration_case c
                          WHERE c.org_id=%s AND c.project_id=%s AND c.case_id=%s
                            AND {_VISIBLE}""",
                    (org_id, project_id, case_uuid, markings),
                ).fetchone()
                if case is None:
                    raise AssetNotFoundError("integration case not found")
                total = conn.execute(
                    """SELECT COUNT(*) AS total FROM integration_stage_event
                        WHERE org_id=%s AND project_id=%s AND case_pk=%s""",
                    (org_id, project_id, case["case_pk"]),
                ).fetchone()["total"]
                rows = conn.execute(
                    """SELECT sequence,snapshot_revision,old_stage,new_stage,cause,
                              reason_refs,created_at
                         FROM integration_stage_event
                        WHERE org_id=%s AND project_id=%s AND case_pk=%s
                     ORDER BY sequence LIMIT %s OFFSET %s""",
                    (org_id, project_id, case["case_pk"], limit, offset),
                ).fetchall()
                items = [
                    IntegrationStageEvent.model_validate(
                        {
                            "sequence": row["sequence"],
                            "snapshotRevision": row["snapshot_revision"],
                            "oldStage": row["old_stage"],
                            "newStage": row["new_stage"],
                            "cause": row["cause"],
                            "reasonRefs": row["reason_refs"],
                            "createdAt": row["created_at"],
                        }
                    )
                    for row in rows
                ]
                return IntegrationCaseTimelineResponse.model_validate(
                    {
                        "caseId": case_id,
                        "scope": case["scope"],
                        "items": items,
                        "total": total,
                        "limit": limit,
                        "offset": offset,
                    }
                )
        except (AssetNotFoundError, EvidenceIntegrityCorruptError):
            raise
        except psycopg.Error as exc:
            raise IntegrationPersistenceError() from exc

    def _current_stats(
        self,
        conn: Any,
        *,
        org_id: str,
        project_id: str,
        markings: list[str],
        cutoff: datetime,
    ) -> IntegrationCaseStats:
        rows = conn.execute(
            f"""SELECT p.computed_stage,s.snapshot_json,s.snapshot_hash
                   FROM integration_case c
                   JOIN integration_case_projection p
                     ON p.org_id=c.org_id AND p.project_id=c.project_id
                    AND p.case_pk=c.case_pk
                   JOIN integration_evidence_snapshot s
                     ON s.org_id=p.org_id AND s.project_id=p.project_id
                    AND s.case_pk=p.case_pk
                    AND s.snapshot_revision=p.snapshot_revision
                  WHERE c.org_id=%s AND c.project_id=%s AND c.scope='current'
                    AND {_VISIBLE}""",
            (org_id, project_id, markings),
        ).fetchall()
        connectors: set[str] = set()
        pipelines: set[str] = set()
        datasets: dict[tuple[str, str], int | None] = {}
        latencies: list[int] = []
        measured = {"connector": set(), "pipeline": set(), "dataset": set(), "latency": set()}
        for index, row in enumerate(rows):
            snapshot = _verify_snapshot(row)
            for raw in snapshot["evidence"]:
                item = INTEGRATION_EVIDENCE_ADAPTER.validate_json(json.dumps(raw))
                if not _valid_at(item, cutoff):
                    continue
                kind = item.evidence_type
                if kind == EvidenceType.SOURCE_CONNECTION and item.claims.read_probe and item.claims.tenant_binding:
                    connectors.add(item.subject_ref)
                    measured["connector"].add(index)
                elif kind == EvidenceType.PIPELINE_RUN and item.claims.result == "succeeded":
                    pipelines.add(item.subject_ref)
                    measured["pipeline"].add(index)
                elif kind == EvidenceType.DATASET_REVISION and item.claims.row_count is not None:
                    datasets[(item.subject_ref, item.claims.revision)] = item.claims.row_count
                    measured["dataset"].add(index)
                elif kind == EvidenceType.RUNTIME_HEALTH and item.claims.healthy and item.claims.latency_ms is not None:
                    latencies.append(item.claims.latency_ms)
                    measured["latency"].add(index)
        eligible = len(rows)
        return IntegrationCaseStats(
            caseCount=_metric(eligible, "count", eligible, eligible, cutoff),
            productionActiveCount=_metric(
                sum(row["computed_stage"] == IntegrationStage.PRODUCTION_ACTIVE.value for row in rows),
                "count",
                eligible,
                eligible,
                cutoff,
            ),
            connectorCount=_metric(len(connectors) if measured["connector"] else None, "distinct_count", len(measured["connector"]), eligible, cutoff),
            pipelineCount=_metric(len(pipelines) if measured["pipeline"] else None, "distinct_count", len(measured["pipeline"]), eligible, cutoff),
            datasetRowCount=_metric(sum(value for value in datasets.values() if value is not None) if measured["dataset"] else None, "sum", len(measured["dataset"]), eligible, cutoff),
            latencyMs=_metric(max(latencies) if measured["latency"] else None, "max", len(measured["latency"]), eligible, cutoff),
        )


class PrincipalMarkingResolver:
    """Freeze the verified principal marking set after confirming active binding."""

    def required_markings_for_create_in_transaction(
        self,
        conn: Any,
        *,
        org_id: str,
        project_id: str,
        installation_id: str,
        principal_markings: Collection[str],
    ) -> Sequence[str]:
        row = conn.execute(
            """SELECT 1
                 FROM bundle_installation i
                 JOIN bundle_installation_revision r
                   ON r.org_id=i.org_id AND r.project_id=i.project_id
                  AND r.installation_pk=i.installation_pk
                  AND r.revision=i.active_revision
                WHERE i.org_id=%s AND i.project_id=%s AND i.installation_id=%s
                  AND r.state='active'""",
            (org_id, project_id, uuid.UUID(installation_id)),
        ).fetchone()
        if row is None:
            raise AssetNotFoundError("active installation binding not found")
        return _markings(principal_markings)


def _verify_snapshot(row: Any) -> dict[str, Any]:
    try:
        payload = dict(row["snapshot_json"])
        embedded = payload.pop("snapshotHash")
        if embedded != row["snapshot_hash"] or embedded != canonical_sha256(payload):
            raise EvidenceIntegrityCorruptError()
        evidence = payload.get("evidence")
        if not isinstance(evidence, list):
            raise EvidenceIntegrityCorruptError()
        return {**payload, "snapshotHash": embedded}
    except (KeyError, TypeError, ValueError) as exc:
        raise EvidenceIntegrityCorruptError() from exc


def _list_item(row: Any):
    model = CurrentIntegrationCaseListItem if row["scope"] == "current" else ReferenceIntegrationCaseListItem
    return model.model_validate(_list_payload(row))


def _list_payload(row: Any) -> dict[str, Any]:
    return {
        "caseId": str(row["case_id"]),
        "scope": row["scope"],
        "displayName": row["display_name"],
        "owner": row["owner"],
        "installationId": _uuid_text(row["installation_id"]),
        "overlayRevision": row["overlay_revision"],
        "computedStage": row["computed_stage"],
        "snapshotRevision": row["snapshot_revision"],
        "cutoffAt": row["cutoff_at"],
        "blockerCount": row["blocker_count"],
        "etagVersion": row["etag_version"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def _detail_metrics(row: Any):
    if row["scope"] == "reference":
        return None
    cutoff = row["cutoff_at"]
    return {
        "connectorCount": _metric(row["connector_count"], "distinct_count", int(row["connector_count"] is not None), 1, cutoff),
        "pipelineCount": _metric(row["pipeline_count"], "distinct_count", int(row["pipeline_count"] is not None), 1, cutoff),
        "datasetRowCount": _metric(row["dataset_row_count"], "sum", int(row["dataset_row_count"] is not None), 1, cutoff),
        "latencyMs": _metric(row["latency_ms"], "max", int(row["latency_ms"] is not None), 1, cutoff),
    }


def _metric(value: int | None, aggregation: str, measured: int, eligible: int, cutoff: datetime) -> IntegrationMetric:
    return IntegrationMetric.model_validate(
        {"value": value, "aggregation": aggregation, "measuredCaseCount": measured, "eligibleCaseCount": eligible, "cutoffAt": cutoff}
    )


def _evidence_summary(raw: dict[str, Any]) -> LatestEvidenceSummary:
    item = INTEGRATION_EVIDENCE_ADAPTER.validate_json(json.dumps(raw))
    return LatestEvidenceSummary.model_validate(
        {
            "evidenceId": item.evidence_id,
            "revision": item.revision,
            "evidenceType": item.evidence_type,
            "subjectRef": item.subject_ref,
            "outcome": item.outcome,
            "observedAt": item.observed_at,
            "expiresAt": item.expires_at,
            "revokedAt": item.revoked_at,
            "artifactHash": item.artifact_hash,
            "evidenceHash": item.evidence_hash,
            "recordedAt": item.recorded_at,
        }
    )


def _valid_at(item: Any, cutoff: datetime) -> bool:
    return (
        item.outcome.value == "valid"
        and item.observed_at <= cutoff
        and item.revoked_at is None
        and (item.expires_at is None or cutoff < item.expires_at)
    )


def _markings(values: Collection[str]) -> list[str]:
    result = sorted(values)
    if any(not isinstance(value, str) or not value or value != value.strip() for value in result) or len(result) != len(set(result)):
        raise ValueError("markings must be unique normalized strings")
    return result


def _uuid_text(value: Any) -> str | None:
    return str(value) if value is not None else None
