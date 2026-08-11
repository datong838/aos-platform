"""Tenant-scoped PostgreSQL authority for AIP-4 eval and evidence facts."""

from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

from aos_api.aip_contracts import TenantContext
from aos_api.aip_eval_contracts import (
    AssetRevisionRef,
    AssetType,
    DatasetRevisionRef,
    EvalRunAuthorityRecord,
    EvalRunEvent,
    EvalRunStatus,
    LineageEvent,
    MetricDefinitionRevision,
    PublicationEvent,
    ReleaseGateDecision,
    TelemetrySpan,
    UsageAdjustment,
    UsageReceipt,
)
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope

ConnectFactory = Callable[..., AbstractContextManager[Any]]


class AipEvalAuthorityError(RuntimeError):
    code = "AIP_EVAL_AUTHORITY_ERROR"


class AipEvalAuthorityNotFound(AipEvalAuthorityError):
    code = "AIP_EVAL_AUTHORITY_NOT_FOUND"


class AipEvalAuthorityConflict(AipEvalAuthorityError):
    code = "AIP_EVAL_AUTHORITY_CONFLICT"


class AipEvalAuthorityTransitionBlocked(AipEvalAuthorityError):
    code = "AIP_EVAL_AUTHORITY_TRANSITION_BLOCKED"


class AipEvalAuthorityPersistenceError(AipEvalAuthorityError):
    code = "AIP_EVAL_AUTHORITY_PERSISTENCE_ERROR"


_ALLOWED_TRANSITIONS: dict[EvalRunStatus, frozenset[EvalRunStatus]] = {
    EvalRunStatus.QUEUED: frozenset({EvalRunStatus.RUNNING, EvalRunStatus.CANCELLED}),
    EvalRunStatus.RUNNING: frozenset(
        {
            EvalRunStatus.SUCCEEDED,
            EvalRunStatus.FAILED,
            EvalRunStatus.CANCELLED,
            EvalRunStatus.UNKNOWN,
        }
    ),
    EvalRunStatus.UNKNOWN: frozenset(
        {EvalRunStatus.SUCCEEDED, EvalRunStatus.FAILED, EvalRunStatus.CANCELLED}
    ),
}


class AipEvalAuthorityStore:
    """Single persistence authority for E0B1; routes are added in E0B2."""

    def __init__(self, connect_factory: ConnectFactory | None = None) -> None:
        self._connect_factory = connect_factory or db_connect

    def create_dataset_revision(
        self,
        scope: TenantScope,
        ref: DatasetRevisionRef,
        *,
        manifest: dict[str, Any],
        actor: str,
    ) -> DatasetRevisionRef:
        self._require_scope(scope)
        if not actor.strip():
            raise ValueError("actor is required")
        try:
            with self._connect(scope) as conn:
                row = conn.execute(
                    """INSERT INTO aip_eval_dataset_revision (
                       org_id,project_id,dataset_id,revision,content_hash,source_hash,
                       redaction_policy_ref,manifest,actor,created_at
                       ) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,NOW())
                       ON CONFLICT (org_id,project_id,dataset_id,revision) DO NOTHING
                       RETURNING dataset_id,revision,content_hash,source_hash,
                                 redaction_policy_ref""",
                    (
                        scope.org_id,
                        scope.project_id,
                        ref.dataset_id,
                        ref.revision,
                        ref.content_hash,
                        ref.source_hash,
                        self._json(ref.redaction_policy),
                        self._json(manifest),
                        actor.strip(),
                    ),
                ).fetchone()
                if row is None:
                    row = self._dataset_row(conn, scope, ref.dataset_id, ref.revision)
                    if (
                        row is None
                        or self._dataset_from_row(row) != ref
                        or row["manifest"] != manifest
                    ):
                        raise AipEvalAuthorityConflict(
                            "dataset revision already exists with different content"
                        )
                conn.commit()
                return self._dataset_from_row(row)
        except AipEvalAuthorityError:
            raise
        except Exception as exc:
            raise AipEvalAuthorityPersistenceError(
                "dataset revision persistence failed"
            ) from exc

    def get_dataset_revision(
        self, scope: TenantScope, dataset_id: str, revision: int
    ) -> DatasetRevisionRef:
        self._require_scope(scope)
        try:
            with self._connect(scope) as conn:
                row = self._dataset_row(conn, scope, dataset_id, revision)
        except Exception as exc:
            raise AipEvalAuthorityPersistenceError(
                "dataset revision read failed"
            ) from exc
        if row is None:
            raise AipEvalAuthorityNotFound("dataset revision not found")
        return self._dataset_from_row(row)

    def create_eval_run(
        self,
        scope: TenantScope,
        record: EvalRunAuthorityRecord,
        initial_event: EvalRunEvent,
    ) -> EvalRunAuthorityRecord:
        self._require_tenant(scope, record.tenant)
        self._require_tenant(scope, initial_event.tenant)
        if record.status is not EvalRunStatus.QUEUED:
            raise ValueError("new eval run must start queued")
        if record.version != 1 or record.started_at or record.finished_at:
            raise ValueError("new eval run must start at version 1 without timestamps")
        try:
            if int(record.suite_ref.revision) < 1:
                raise ValueError
        except ValueError as exc:
            raise ValueError("eval suite revision must be a positive integer") from exc
        if (
            initial_event.run_id != record.run_id
            or initial_event.sequence != 1
            or initial_event.from_status is not None
            or initial_event.to_status is not EvalRunStatus.QUEUED
        ):
            raise ValueError("initial eval event must be sequence 1: null -> queued")
        try:
            with self._connect(scope) as conn:
                row = conn.execute(
                    """INSERT INTO aip_eval_run (
                       org_id,project_id,run_id,suite_id,suite_revision,suite_hash,
                       target_ref,dataset_ref,judge_ref,status,idempotency_key,version,
                       created_by,created_at,started_at,finished_at
                       ) VALUES (
                       %s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s,%s,
                       %s,%s,%s,%s)
                       ON CONFLICT (org_id,project_id,idempotency_key) DO NOTHING
                       RETURNING *""",
                    self._run_insert_params(scope, record),
                ).fetchone()
                if row is None:
                    row = self._run_by_idempotency(conn, scope, record.idempotency_key)
                    replay_event = self._run_event_by_sequence(
                        conn, scope, record.run_id, 1
                    )
                    if (
                        row is None
                        or self._run_from_row(row) != record
                        or replay_event != initial_event
                    ):
                        raise AipEvalAuthorityConflict(
                            "eval run idempotency key was reused"
                        )
                    return self._run_from_row(row)
                self._insert_run_event(conn, scope, initial_event)
                conn.commit()
                return self._run_from_row(row)
        except AipEvalAuthorityError:
            raise
        except Exception as exc:
            raise AipEvalAuthorityPersistenceError(
                "eval run persistence failed"
            ) from exc

    def get_eval_run(self, scope: TenantScope, run_id: str) -> EvalRunAuthorityRecord:
        self._require_scope(scope)
        try:
            with self._connect(scope) as conn:
                row = self._run_row(conn, scope, run_id)
        except Exception as exc:
            raise AipEvalAuthorityPersistenceError("eval run read failed") from exc
        if row is None:
            raise AipEvalAuthorityNotFound("eval run not found")
        return self._run_from_row(row)

    def transition_eval_run(
        self,
        scope: TenantScope,
        event: EvalRunEvent,
        *,
        expected_version: int,
    ) -> EvalRunAuthorityRecord:
        self._require_tenant(scope, event.tenant)
        try:
            with self._connect(scope) as conn:
                row = self._run_row(conn, scope, event.run_id, for_update=True)
                if row is None:
                    raise AipEvalAuthorityNotFound("eval run not found")
                current = EvalRunStatus(str(row["status"]))
                version = int(row["version"])
                if version != expected_version or event.from_status is not current:
                    raise AipEvalAuthorityConflict(
                        "eval run version or from_status changed"
                    )
                if event.to_status not in _ALLOWED_TRANSITIONS.get(
                    current, frozenset()
                ):
                    raise AipEvalAuthorityTransitionBlocked(
                        f"transition {current.value}->{event.to_status.value} is blocked"
                    )
                expected_sequence = self._next_run_sequence(conn, scope, event.run_id)
                if event.sequence != expected_sequence:
                    raise AipEvalAuthorityConflict("eval run event sequence changed")
                self._insert_run_event(conn, scope, event)
                terminal = event.to_status in {
                    EvalRunStatus.SUCCEEDED,
                    EvalRunStatus.FAILED,
                    EvalRunStatus.CANCELLED,
                }
                updated = conn.execute(
                    """UPDATE aip_eval_run
                       SET status=%s,version=version+1,
                           started_at=CASE
                             WHEN %s='running' THEN COALESCE(started_at,%s)
                             ELSE started_at END,
                           finished_at=CASE WHEN %s THEN %s ELSE NULL END
                       WHERE org_id=%s AND project_id=%s AND run_id=%s
                         AND version=%s
                       RETURNING *""",
                    (
                        event.to_status.value,
                        event.to_status.value,
                        event.created_at,
                        terminal,
                        event.created_at,
                        scope.org_id,
                        scope.project_id,
                        event.run_id,
                        expected_version,
                    ),
                ).fetchone()
                if updated is None:
                    raise AipEvalAuthorityConflict("eval run changed concurrently")
                conn.commit()
                return self._run_from_row(updated)
        except AipEvalAuthorityError:
            raise
        except Exception as exc:
            raise AipEvalAuthorityPersistenceError(
                "eval run transition failed"
            ) from exc

    def append_release_gate(
        self, scope: TenantScope, decision: ReleaseGateDecision
    ) -> ReleaseGateDecision:
        self._require_tenant(scope, decision.tenant)
        return self._append_contract(
            scope,
            table="aip_release_gate_decision",
            id_column="decision_id",
            identifier=decision.decision_id,
            columns=(
                "decision_id",
                "target_ref",
                "suite_ref",
                "eval_run_id",
                "eval_report_ref",
                "status",
                "decision_hash",
                "invalidated_by",
                "decided_by",
                "decided_at",
            ),
            values=(
                decision.decision_id,
                self._json(decision.target),
                self._json(decision.suite_ref),
                decision.eval_run_id,
                self._json(decision.eval_report),
                decision.status.value,
                decision.decision_hash,
                decision.invalidated_by,
                decision.decided_by,
                decision.decided_at,
            ),
            expected=decision,
            parser=lambda row: ReleaseGateDecision(
                tenant=self._tenant(scope),
                decision_id=row["decision_id"],
                target=row["target_ref"],
                suite_ref=row["suite_ref"],
                eval_run_id=row["eval_run_id"],
                eval_report=row["eval_report_ref"],
                status=row["status"],
                decision_hash=row["decision_hash"],
                invalidated_by=row["invalidated_by"],
                decided_by=row["decided_by"],
                decided_at=row["decided_at"],
            ),
        )

    def append_publication_event(
        self, scope: TenantScope, event: PublicationEvent
    ) -> PublicationEvent:
        self._require_tenant(scope, event.tenant)
        return self._append_contract(
            scope,
            table="aip_publication_event",
            id_column="event_id",
            identifier=event.event_id,
            columns=(
                "event_id",
                "publication_id",
                "target_ref",
                "event_type",
                "release_gate_decision_id",
                "reason_hash",
                "actor",
                "occurred_at",
            ),
            values=(
                event.event_id,
                event.publication_id,
                self._json(event.target),
                event.event_type.value,
                event.release_gate_decision_id,
                event.reason_hash,
                event.actor,
                event.occurred_at,
            ),
            expected=event,
            parser=lambda row: PublicationEvent(
                tenant=self._tenant(scope),
                event_id=row["event_id"],
                publication_id=row["publication_id"],
                target=row["target_ref"],
                event_type=row["event_type"],
                release_gate_decision_id=row["release_gate_decision_id"],
                reason_hash=row["reason_hash"],
                actor=row["actor"],
                occurred_at=row["occurred_at"],
            ),
        )

    def append_lineage_event(
        self, scope: TenantScope, event: LineageEvent
    ) -> LineageEvent:
        self._require_tenant(scope, event.tenant)
        return self._append_contract(
            scope,
            table="aip_lineage_event",
            id_column="event_id",
            identifier=event.event_id,
            columns=(
                "event_id",
                "lineage_id",
                "root_type",
                "root_id",
                "sequence",
                "event_type",
                "subject_ref",
                "artifact_ref",
                "payload_hash",
                "quality",
                "occurred_at",
                "observed_at",
                "source_kind",
                "source_id",
                "source_hash",
            ),
            values=(
                event.event_id,
                event.lineage_id,
                event.root_type.value,
                event.root_id,
                event.sequence,
                event.event_type.value,
                self._json(event.subject) if event.subject else None,
                self._json(event.artifact) if event.artifact else None,
                event.payload_hash,
                event.quality.value,
                event.occurred_at,
                event.observed_at,
                event.source_kind.value if event.source_kind else None,
                event.source_id,
                event.source_hash,
            ),
            expected=event,
            parser=lambda row: LineageEvent(
                tenant=self._tenant(scope),
                event_id=row["event_id"],
                lineage_id=row["lineage_id"],
                root_type=row["root_type"],
                root_id=row["root_id"],
                sequence=row["sequence"],
                event_type=row["event_type"],
                subject=row["subject_ref"],
                artifact=row["artifact_ref"],
                payload_hash=row["payload_hash"],
                quality=row["quality"],
                occurred_at=row["occurred_at"],
                observed_at=row["observed_at"],
                source_kind=row["source_kind"],
                source_id=row["source_id"],
                source_hash=row["source_hash"],
            ),
        )

    def append_usage_receipt(
        self, scope: TenantScope, receipt: UsageReceipt
    ) -> UsageReceipt:
        self._require_tenant(scope, receipt.tenant)
        try:
            with self._connect(scope) as conn:
                lineage = conn.execute(
                    """SELECT 1 FROM aip_lineage_event
                       WHERE org_id=%s AND project_id=%s AND lineage_id=%s LIMIT 1""",
                    (scope.org_id, scope.project_id, receipt.lineage_id),
                ).fetchone()
                if lineage is None:
                    raise AipEvalAuthorityNotFound(
                        "usage receipt lineage is not available in this scope"
                    )
                row = conn.execute(
                    """INSERT INTO aip_usage_receipt (
                         org_id,project_id,receipt_id,provider,provider_receipt_id,
                         lineage_id,usage_kind,quantity,unit,currency,quality,
                         source_hash,observed_at
                       ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT DO NOTHING RETURNING *""",
                    (
                        *scope.key,
                        receipt.receipt_id,
                        receipt.provider,
                        receipt.provider_receipt_id,
                        receipt.lineage_id,
                        receipt.usage_kind.value,
                        receipt.quantity,
                        receipt.unit,
                        receipt.currency,
                        receipt.quality.value,
                        receipt.source_hash,
                        receipt.observed_at,
                    ),
                ).fetchone()
                if row is None:
                    row = conn.execute(
                        """SELECT * FROM aip_usage_receipt
                           WHERE org_id=%s AND project_id=%s AND provider=%s
                             AND provider_receipt_id=%s""",
                        (*scope.key, receipt.provider, receipt.provider_receipt_id),
                    ).fetchone()
                if row is None or self._usage_from_row(scope, row) != receipt:
                    raise AipEvalAuthorityConflict(
                        "provider usage receipt was replayed with different content"
                    )
                conn.commit()
                return self._usage_from_row(scope, row)
        except AipEvalAuthorityError:
            raise
        except Exception as exc:
            raise AipEvalAuthorityPersistenceError(
                "usage receipt persistence failed"
            ) from exc

    def append_telemetry_span(
        self, scope: TenantScope, span: TelemetrySpan
    ) -> TelemetrySpan:
        self._require_tenant(scope, span.tenant)
        try:
            with self._connect(scope) as conn:
                lineage = conn.execute(
                    """SELECT 1 FROM aip_lineage_event
                       WHERE org_id=%s AND project_id=%s AND lineage_id=%s LIMIT 1""",
                    (*scope.key, span.lineage_id),
                ).fetchone()
                if lineage is None:
                    raise AipEvalAuthorityNotFound(
                        "telemetry span lineage is not available in this scope"
                    )
                row = conn.execute(
                    """INSERT INTO aip_telemetry_span (
                         org_id,project_id,span_record_id,provider,provider_receipt_id,
                         lineage_id,trace_id,span_id,parent_span_id,name,kind,status,
                         producer_started_at,producer_ended_at,observed_at,ingested_at,
                         attributes_hash,source_hash,quality
                       ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT DO NOTHING RETURNING *""",
                    (
                        *scope.key,
                        span.span_record_id,
                        span.provider,
                        span.provider_receipt_id,
                        span.lineage_id,
                        span.trace_id,
                        span.span_id,
                        span.parent_span_id,
                        span.name,
                        span.kind.value,
                        span.status.value,
                        span.producer_started_at,
                        span.producer_ended_at,
                        span.observed_at,
                        span.ingested_at,
                        span.attributes_hash,
                        span.source_hash,
                        span.quality.value,
                    ),
                ).fetchone()
                if row is None:
                    row = conn.execute(
                        """SELECT * FROM aip_telemetry_span
                           WHERE org_id=%s AND project_id=%s AND provider=%s
                             AND provider_receipt_id=%s""",
                        (*scope.key, span.provider, span.provider_receipt_id),
                    ).fetchone()
                if row is None:
                    raise AipEvalAuthorityConflict("telemetry span replay disappeared")
                stored = self._span_from_row(scope, row)
                if stored != span.model_copy(
                    update={"ingested_at": stored.ingested_at}
                ):
                    raise AipEvalAuthorityConflict(
                        "provider span receipt was replayed with different content"
                    )
                conn.commit()
                return stored
        except AipEvalAuthorityError:
            raise
        except Exception as exc:
            raise AipEvalAuthorityPersistenceError(
                "telemetry span persistence failed"
            ) from exc

    def append_usage_adjustment(
        self, scope: TenantScope, adjustment: UsageAdjustment
    ) -> UsageAdjustment:
        self._require_tenant(scope, adjustment.tenant)
        return self._append_contract(
            scope,
            table="aip_usage_adjustment",
            id_column="adjustment_id",
            identifier=adjustment.adjustment_id,
            columns=(
                "adjustment_id",
                "receipt_id",
                "delta",
                "reason_hash",
                "actor",
                "created_at",
            ),
            values=(
                adjustment.adjustment_id,
                adjustment.receipt_id,
                adjustment.delta,
                adjustment.reason_hash,
                adjustment.actor,
                adjustment.created_at,
            ),
            expected=adjustment,
            parser=lambda row: UsageAdjustment(
                tenant=self._tenant(scope),
                adjustment_id=row["adjustment_id"],
                receipt_id=row["receipt_id"],
                delta=row["delta"],
                reason_hash=row["reason_hash"],
                actor=row["actor"],
                created_at=row["created_at"],
            ),
        )

    def create_metric_definition(
        self,
        scope: TenantScope,
        definition: MetricDefinitionRevision,
        *,
        actor: str,
    ) -> MetricDefinitionRevision:
        self._require_scope(scope)
        if not actor.strip():
            raise ValueError("actor is required")
        return self._append_contract(
            scope,
            table="aip_metric_definition_revision",
            id_column="metric_id",
            identifier=definition.metric_id,
            columns=(
                "metric_id",
                "revision",
                "content_hash",
                "definition",
                "actor",
            ),
            values=(
                definition.metric_id,
                definition.revision,
                definition.content_hash,
                self._json(definition),
                actor.strip(),
            ),
            expected=definition,
            parser=lambda row: MetricDefinitionRevision.model_validate(
                row["definition"]
            ),
            extra_lookup=("revision", definition.revision),
        )

    def list_lineage_events(
        self, scope: TenantScope, lineage_id: str
    ) -> list[LineageEvent]:
        self._require_scope(scope)
        try:
            with self._connect(scope) as conn:
                rows = conn.execute(
                    """SELECT * FROM aip_lineage_event
                       WHERE org_id=%s AND project_id=%s AND lineage_id=%s
                       ORDER BY sequence,event_id""",
                    (scope.org_id, scope.project_id, lineage_id),
                ).fetchall()
        except Exception as exc:
            raise AipEvalAuthorityPersistenceError("lineage read failed") from exc
        return [
            LineageEvent(
                tenant=self._tenant(scope),
                event_id=row["event_id"],
                lineage_id=row["lineage_id"],
                root_type=row["root_type"],
                root_id=row["root_id"],
                sequence=row["sequence"],
                event_type=row["event_type"],
                subject=row["subject_ref"],
                artifact=row["artifact_ref"],
                payload_hash=row["payload_hash"],
                quality=row["quality"],
                occurred_at=row["occurred_at"],
                observed_at=row["observed_at"],
                source_kind=row["source_kind"],
                source_id=row["source_id"],
                source_hash=row["source_hash"],
            )
            for row in rows
        ]

    def list_telemetry_spans(
        self, scope: TenantScope, lineage_id: str
    ) -> list[TelemetrySpan]:
        self._require_scope(scope)
        try:
            with self._connect(scope) as conn:
                rows = conn.execute(
                    """SELECT * FROM aip_telemetry_span
                       WHERE org_id=%s AND project_id=%s AND lineage_id=%s
                       ORDER BY producer_started_at,span_record_id""",
                    (*scope.key, lineage_id),
                ).fetchall()
        except Exception as exc:
            raise AipEvalAuthorityPersistenceError(
                "telemetry span read failed"
            ) from exc
        return [self._span_from_row(scope, row) for row in rows]

    def list_usage_receipts(
        self, scope: TenantScope, lineage_id: str
    ) -> list[UsageReceipt]:
        self._require_scope(scope)
        try:
            with self._connect(scope) as conn:
                rows = conn.execute(
                    """SELECT * FROM aip_usage_receipt
                       WHERE org_id=%s AND project_id=%s AND lineage_id=%s
                       ORDER BY observed_at,receipt_id""",
                    (*scope.key, lineage_id),
                ).fetchall()
        except Exception as exc:
            raise AipEvalAuthorityPersistenceError("usage receipt read failed") from exc
        return [self._usage_from_row(scope, row) for row in rows]

    def list_usage_adjustments(
        self, scope: TenantScope, receipt_id: str
    ) -> list[UsageAdjustment]:
        self._require_scope(scope)
        try:
            with self._connect(scope) as conn:
                rows = conn.execute(
                    """SELECT * FROM aip_usage_adjustment
                       WHERE org_id=%s AND project_id=%s AND receipt_id=%s
                       ORDER BY created_at,adjustment_id""",
                    (*scope.key, receipt_id),
                ).fetchall()
        except Exception as exc:
            raise AipEvalAuthorityPersistenceError(
                "usage adjustment read failed"
            ) from exc
        return [
            UsageAdjustment(
                tenant=self._tenant(scope),
                adjustment_id=row["adjustment_id"],
                receipt_id=row["receipt_id"],
                delta=row["delta"],
                reason_hash=row["reason_hash"],
                actor=row["actor"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def _span_from_row(self, scope: TenantScope, row: Any) -> TelemetrySpan:
        return TelemetrySpan(
            tenant=self._tenant(scope),
            span_record_id=row["span_record_id"],
            provider=row["provider"],
            provider_receipt_id=row["provider_receipt_id"],
            lineage_id=row["lineage_id"],
            trace_id=row["trace_id"],
            span_id=row["span_id"],
            parent_span_id=row["parent_span_id"],
            name=row["name"],
            kind=row["kind"],
            status=row["status"],
            producer_started_at=row["producer_started_at"],
            producer_ended_at=row["producer_ended_at"],
            observed_at=row["observed_at"],
            ingested_at=row["ingested_at"],
            attributes_hash=row["attributes_hash"],
            source_hash=row["source_hash"],
            quality=row["quality"],
        )

    def _usage_from_row(self, scope: TenantScope, row: Any) -> UsageReceipt:
        return UsageReceipt(
            tenant=self._tenant(scope),
            receipt_id=row["receipt_id"],
            provider=row["provider"],
            provider_receipt_id=row["provider_receipt_id"],
            lineage_id=row["lineage_id"],
            usage_kind=row["usage_kind"],
            quantity=row["quantity"],
            unit=row["unit"],
            currency=row["currency"],
            quality=row["quality"],
            source_hash=row["source_hash"],
            observed_at=row["observed_at"],
        )

    def _append_contract(
        self,
        scope: TenantScope,
        *,
        table: str,
        id_column: str,
        identifier: str,
        columns: tuple[str, ...],
        values: tuple[Any, ...],
        expected: Any,
        parser: Callable[[Any], Any],
        extra_lookup: tuple[str, Any] | None = None,
    ):
        placeholders = ",".join(
            "%s::jsonb" if column.endswith("_ref") or column == "definition" else "%s"
            for column in columns
        )
        column_sql = ",".join(("org_id", "project_id", *columns))
        lookup_sql = f"{id_column}=%s"
        lookup_params: list[Any] = [scope.org_id, scope.project_id, identifier]
        if extra_lookup is not None:
            lookup_sql += f" AND {extra_lookup[0]}=%s"
            lookup_params.append(extra_lookup[1])
        try:
            with self._connect(scope) as conn:
                row = conn.execute(
                    f"""INSERT INTO {table} ({column_sql})
                        VALUES (%s,%s,{placeholders})
                        ON CONFLICT DO NOTHING RETURNING *""",
                    (scope.org_id, scope.project_id, *values),
                ).fetchone()
                if row is None:
                    row = conn.execute(
                        f"""SELECT * FROM {table}
                            WHERE org_id=%s AND project_id=%s AND {lookup_sql}""",
                        tuple(lookup_params),
                    ).fetchone()
                    if row is None or parser(row) != expected:
                        raise AipEvalAuthorityConflict(
                            f"{table} identifier was reused with different content"
                        )
                conn.commit()
                return parser(row)
        except AipEvalAuthorityError:
            raise
        except Exception as exc:
            raise AipEvalAuthorityPersistenceError(
                f"{table} persistence failed"
            ) from exc

    @staticmethod
    def _tenant(scope: TenantScope) -> TenantContext:
        return TenantContext(org_id=scope.org_id, project_id=scope.project_id)

    @staticmethod
    def _require_scope(scope: TenantScope) -> None:
        if not scope.org_id.strip() or not scope.project_id.strip():
            raise ValueError("org_id and project_id are required")

    def _require_tenant(self, scope: TenantScope, tenant: TenantContext) -> None:
        self._require_scope(scope)
        if tenant.org_id != scope.org_id or tenant.project_id != scope.project_id:
            raise ValueError("contract tenant must match authenticated scope")

    def _connect(self, scope: TenantScope):
        try:
            return self._connect_factory(scope)
        except TypeError:
            return self._connect_factory()

    @staticmethod
    def _json(value: Any) -> str:
        if hasattr(value, "model_dump"):
            value = value.model_dump(mode="json", by_alias=True)
        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    @staticmethod
    def _dataset_row(conn: Any, scope: TenantScope, dataset_id: str, revision: int):
        return conn.execute(
            """SELECT dataset_id,revision,content_hash,source_hash,
                      redaction_policy_ref,manifest
               FROM aip_eval_dataset_revision
               WHERE org_id=%s AND project_id=%s AND dataset_id=%s AND revision=%s""",
            (scope.org_id, scope.project_id, dataset_id, revision),
        ).fetchone()

    @staticmethod
    def _dataset_from_row(row: Any) -> DatasetRevisionRef:
        return DatasetRevisionRef(
            dataset_id=row["dataset_id"],
            revision=row["revision"],
            content_hash=row["content_hash"],
            source_hash=row["source_hash"],
            redaction_policy=row["redaction_policy_ref"],
        )

    @staticmethod
    def _run_row(
        conn: Any, scope: TenantScope, run_id: str, *, for_update: bool = False
    ):
        suffix = " FOR UPDATE" if for_update else ""
        return conn.execute(
            """SELECT * FROM aip_eval_run
               WHERE org_id=%s AND project_id=%s AND run_id=%s"""
            + suffix,
            (scope.org_id, scope.project_id, run_id),
        ).fetchone()

    @staticmethod
    def _run_by_idempotency(conn: Any, scope: TenantScope, key: str):
        return conn.execute(
            """SELECT * FROM aip_eval_run
               WHERE org_id=%s AND project_id=%s AND idempotency_key=%s""",
            (scope.org_id, scope.project_id, key),
        ).fetchone()

    def _run_from_row(self, row: Any) -> EvalRunAuthorityRecord:
        return EvalRunAuthorityRecord(
            tenant=TenantContext(org_id=row["org_id"], project_id=row["project_id"]),
            run_id=row["run_id"],
            suite_ref=AssetRevisionRef(
                asset_type=AssetType.EVAL_SUITE,
                asset_id=row["suite_id"],
                revision=str(row["suite_revision"]),
                content_hash=row["suite_hash"],
            ),
            target=row["target_ref"],
            dataset=row["dataset_ref"],
            judge=row["judge_ref"],
            status=row["status"],
            idempotency_key=row["idempotency_key"],
            created_by=row["created_by"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            version=row["version"],
        )

    def _run_insert_params(
        self, scope: TenantScope, record: EvalRunAuthorityRecord
    ) -> tuple[Any, ...]:
        return (
            scope.org_id,
            scope.project_id,
            record.run_id,
            record.suite_ref.asset_id,
            int(record.suite_ref.revision),
            record.suite_ref.content_hash,
            self._json(record.target),
            self._json(record.dataset),
            self._json(record.judge),
            record.status.value,
            record.idempotency_key,
            record.version,
            record.created_by,
            record.created_at,
            record.started_at,
            record.finished_at,
        )

    @staticmethod
    def _insert_run_event(conn: Any, scope: TenantScope, event: EvalRunEvent) -> None:
        row = conn.execute(
            """INSERT INTO aip_eval_run_event (
               org_id,project_id,event_id,run_id,sequence,event_type,from_status,
               to_status,payload_hash,actor,created_at
               ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (org_id,project_id,event_id) DO NOTHING
               RETURNING event_id""",
            (
                scope.org_id,
                scope.project_id,
                event.event_id,
                event.run_id,
                event.sequence,
                event.event_type,
                event.from_status.value if event.from_status else None,
                event.to_status.value,
                event.payload_hash,
                event.actor,
                event.created_at,
            ),
        ).fetchone()
        if row is None:
            existing = conn.execute(
                """SELECT run_id,sequence,event_type,from_status,to_status,
                          payload_hash,actor,created_at
                   FROM aip_eval_run_event
                   WHERE org_id=%s AND project_id=%s AND event_id=%s""",
                (scope.org_id, scope.project_id, event.event_id),
            ).fetchone()
            if existing is None:
                raise AipEvalAuthorityConflict("eval run event sequence conflicts")
            replay = EvalRunEvent(
                tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
                event_id=event.event_id,
                **existing,
            )
            if replay != event:
                raise AipEvalAuthorityConflict(
                    "eval run event id was reused with different content"
                )

    @staticmethod
    def _next_run_sequence(conn: Any, scope: TenantScope, run_id: str) -> int:
        row = conn.execute(
            """SELECT COALESCE(MAX(sequence),0)+1 AS next_sequence
               FROM aip_eval_run_event
               WHERE org_id=%s AND project_id=%s AND run_id=%s""",
            (scope.org_id, scope.project_id, run_id),
        ).fetchone()
        return int(row["next_sequence"])

    @staticmethod
    def _run_event_by_sequence(
        conn: Any, scope: TenantScope, run_id: str, sequence: int
    ) -> EvalRunEvent | None:
        row = conn.execute(
            """SELECT event_id,run_id,sequence,event_type,from_status,to_status,
                      payload_hash,actor,created_at
               FROM aip_eval_run_event
               WHERE org_id=%s AND project_id=%s AND run_id=%s AND sequence=%s""",
            (scope.org_id, scope.project_id, run_id, sequence),
        ).fetchone()
        if row is None:
            return None
        return EvalRunEvent(
            tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
            **row,
        )


__all__ = [
    "AipEvalAuthorityConflict",
    "AipEvalAuthorityError",
    "AipEvalAuthorityNotFound",
    "AipEvalAuthorityPersistenceError",
    "AipEvalAuthorityStore",
    "AipEvalAuthorityTransitionBlocked",
]
