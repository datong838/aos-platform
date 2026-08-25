"""Project immutable AIP runtime facts into the canonical lineage ledger."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from aos_api.aip_contracts import ArtifactRef, TenantContext
from aos_api.aip_eval_contracts import (
    AssetRevisionRef,
    EvidenceQuality,
    LineageEvent,
    LineageEventType,
    LineageRootType,
    LineageSourceKind,
)
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope

ConnectFactory = Callable[..., AbstractContextManager[Any]]


class AipLineageError(RuntimeError):
    code = "AIP_LINEAGE_ERROR"


class AipLineageNotFound(AipLineageError):
    code = "AIP_LINEAGE_NOT_FOUND"


class AipLineageConflict(AipLineageError):
    code = "AIP_LINEAGE_SOURCE_CONFLICT"


class AipLineageUnsupportedRoot(AipLineageError):
    code = "AIP_LINEAGE_ROOT_UNSUPPORTED"


class AipLineagePersistenceError(AipLineageError):
    code = "AIP_LINEAGE_PERSISTENCE_ERROR"


@dataclass(frozen=True)
class _SourceFact:
    source_kind: LineageSourceKind
    source_id: str
    event_type: LineageEventType
    occurred_at: datetime
    fingerprint: dict[str, Any]
    quality: EvidenceQuality = EvidenceQuality.MEASURED
    subject: AssetRevisionRef | None = None
    artifact: ArtifactRef | None = None


class AipLineageService:
    """Derive lineage only from tenant-scoped PostgreSQL authority rows."""

    def __init__(self, connect_factory: ConnectFactory | None = None) -> None:
        self._connect_factory = connect_factory or db_connect

    def reconcile(
        self,
        scope: TenantScope,
        root_type: LineageRootType,
        root_id: str,
    ) -> list[LineageEvent]:
        self._require(scope, root_id)
        if root_type in {
            LineageRootType.RESEARCH_JOB,
            LineageRootType.LEGACY_DECISION,
        }:
            raise AipLineageUnsupportedRoot(
                f"{root_type.value} projection is not available in E3A"
            )
        try:
            with self._connect(scope) as conn:
                facts = self._facts(conn, scope, root_type, root_id)
                lineage_id = self.lineage_id(root_type, root_id)
                existing = conn.execute(
                    """SELECT * FROM aip_lineage_event
                       WHERE org_id=%s AND project_id=%s AND lineage_id=%s
                       ORDER BY sequence,event_id FOR UPDATE""",
                    (*scope.key, lineage_id),
                ).fetchall()
                by_source = {
                    (str(row["source_kind"]), str(row["source_id"])): row
                    for row in existing
                    if row["source_kind"] is not None
                }
                sequence = max((int(row["sequence"]) for row in existing), default=0)
                for fact in sorted(
                    facts,
                    key=lambda item: (
                        item.occurred_at,
                        item.source_kind.value,
                        item.source_id,
                    ),
                ):
                    source_hash = self._hash(fact.fingerprint)
                    key = (fact.source_kind.value, fact.source_id)
                    prior = by_source.get(key)
                    if prior is not None:
                        if str(prior["source_hash"]) != source_hash:
                            raise AipLineageConflict(
                                "authority source changed after lineage projection"
                            )
                        continue
                    sequence += 1
                    observed_at = max(datetime.now(timezone.utc), fact.occurred_at)
                    event = LineageEvent(
                        tenant=TenantContext(
                            org_id=scope.org_id,
                            project_id=scope.project_id,
                        ),
                        event_id=self._event_id(
                            scope, fact.source_kind, fact.source_id, source_hash
                        ),
                        lineage_id=lineage_id,
                        root_type=root_type,
                        root_id=root_id,
                        sequence=sequence,
                        event_type=fact.event_type,
                        subject=fact.subject,
                        artifact=fact.artifact,
                        payload_hash=source_hash,
                        quality=fact.quality,
                        occurred_at=fact.occurred_at,
                        observed_at=observed_at,
                        source_kind=fact.source_kind,
                        source_id=fact.source_id,
                        source_hash=source_hash,
                    )
                    row = conn.execute(
                        """INSERT INTO aip_lineage_event (
                             org_id,project_id,event_id,lineage_id,root_type,root_id,
                             sequence,event_type,subject_ref,artifact_ref,payload_hash,
                             quality,occurred_at,observed_at,source_kind,source_id,source_hash
                           ) VALUES (
                             %s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,
                             %s,%s,%s,%s,%s
                           )
                           ON CONFLICT DO NOTHING RETURNING *""",
                        (
                            *scope.key,
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
                            event.source_kind.value,
                            event.source_id,
                            event.source_hash,
                        ),
                    ).fetchone()
                    if row is None:
                        row = conn.execute(
                            """SELECT * FROM aip_lineage_event
                               WHERE org_id=%s AND project_id=%s
                                 AND source_kind=%s AND source_id=%s""",
                            (*scope.key, *key),
                        ).fetchone()
                        if row is None or str(row["source_hash"]) != source_hash:
                            raise AipLineageConflict(
                                "lineage source identifier was reused with different content"
                            )
                    by_source[key] = row
                conn.commit()
                return self._list_with_conn(conn, scope, lineage_id)
        except AipLineageError:
            raise
        except Exception as exc:
            raise AipLineagePersistenceError("lineage projection failed") from exc

    def list_events(
        self,
        scope: TenantScope,
        root_type: LineageRootType,
        root_id: str,
    ) -> list[LineageEvent]:
        self._require(scope, root_id)
        try:
            with self._connect(scope) as conn:
                return self._list_with_conn(
                    conn, scope, self.lineage_id(root_type, root_id)
                )
        except Exception as exc:
            raise AipLineagePersistenceError("lineage read failed") from exc

    @staticmethod
    def lineage_id(root_type: LineageRootType, root_id: str) -> str:
        digest = hashlib.sha256(f"{root_type.value}:{root_id}".encode()).hexdigest()[
            :24
        ]
        return f"lineage-{digest}"

    def _facts(
        self,
        conn: Any,
        scope: TenantScope,
        root_type: LineageRootType,
        root_id: str,
    ) -> list[_SourceFact]:
        if root_type is LineageRootType.TASK_RUN:
            return self._task_facts(conn, scope, root_id)
        if root_type is LineageRootType.ACTION:
            return self._action_facts(conn, scope, root_id)
        if root_type is LineageRootType.EVAL_RUN:
            return self._eval_facts(conn, scope, root_id)
        if root_type is LineageRootType.PUBLICATION:
            return self._publication_facts(conn, scope, root_id)
        raise AipLineageUnsupportedRoot(root_type.value)

    def _task_facts(
        self, conn: Any, scope: TenantScope, run_id: str
    ) -> list[_SourceFact]:
        run = conn.execute(
            """SELECT run_id,task_id,plan_revision_id,logic_graph_id,logic_revision,
                      status,request_hash,version,created_at,started_at,finished_at,updated_at
               FROM aip_task_run
               WHERE org_id=%s AND project_id=%s AND run_id=%s""",
            (*scope.key, run_id),
        ).fetchone()
        if run is None:
            raise AipLineageNotFound("task run not found in scope")
        facts = [
            _SourceFact(
                LineageSourceKind.TASK_RUN,
                f"{run_id}:v{run['version']}",
                self._run_event(str(run["status"])),
                run["updated_at"] or run["created_at"],
                dict(run),
                quality=(
                    EvidenceQuality.UNKNOWN
                    if run["status"] == "unknown"
                    else EvidenceQuality.MEASURED
                ),
            )
        ]
        steps = conn.execute(
            """SELECT step_run_id,step_key,attempt,status,input_refs,output_refs,
                      think_ref,action_ref,verify_ref,observe_ref,error,token_count,
                      cost_amount,created_at,updated_at
               FROM aip_step_run
               WHERE org_id=%s AND project_id=%s AND run_id=%s""",
            (*scope.key, run_id),
        ).fetchall()
        for row in steps:
            event_type = (
                LineageEventType.ERROR
                if row["status"] in {"failed", "unknown"}
                else LineageEventType.TOOL
                if row["action_ref"]
                else LineageEventType.MODEL
            )
            facts.append(
                _SourceFact(
                    LineageSourceKind.STEP_RUN,
                    f"{row['step_run_id']}:{self._time_key(row['updated_at'])}",
                    event_type,
                    row["updated_at"] or row["created_at"],
                    dict(row),
                    quality=(
                        EvidenceQuality.UNKNOWN
                        if row["status"] == "unknown"
                        else EvidenceQuality.MEASURED
                    ),
                )
            )
        for row in conn.execute(
            """SELECT checkpoint_id,sequence,schema_version,step_key,state_hash,
                      state_snapshot_ref,artifact_refs,resume_token_hash,created_at
               FROM aip_checkpoint
               WHERE org_id=%s AND project_id=%s AND run_id=%s""",
            (*scope.key, run_id),
        ).fetchall():
            facts.append(
                _SourceFact(
                    LineageSourceKind.CHECKPOINT,
                    str(row["checkpoint_id"]),
                    LineageEventType.RECEIPT,
                    row["created_at"],
                    dict(row),
                )
            )
        for row in conn.execute(
            """SELECT artifact_id,artifact_type,content_ref,schema_ref,source,
                      evidence_refs,marking,content_hash,metadata,created_at
               FROM aip_artifact
               WHERE org_id=%s AND project_id=%s AND run_id=%s""",
            (*scope.key, run_id),
        ).fetchall():
            source_hash = self._hash(dict(row))
            facts.append(
                _SourceFact(
                    LineageSourceKind.ARTIFACT,
                    str(row["artifact_id"]),
                    LineageEventType.ARTIFACT,
                    row["created_at"],
                    dict(row),
                    artifact=ArtifactRef(
                        artifact_id=row["artifact_id"],
                        artifact_type=row["artifact_type"],
                        content_hash=row["content_hash"] or source_hash,
                    ),
                )
            )
        for row in conn.execute(
            """SELECT evidence_id,evidence_type,subject_ref,source_type,source_ref,
                      observed_at,freshness_at,content_hash,redaction,created_at
               FROM aip_evidence
               WHERE org_id=%s AND project_id=%s AND run_id=%s""",
            (*scope.key, run_id),
        ).fetchall():
            facts.append(
                _SourceFact(
                    LineageSourceKind.EVIDENCE,
                    str(row["evidence_id"]),
                    LineageEventType.RECEIPT,
                    row["observed_at"] or row["created_at"],
                    dict(row),
                    artifact=ArtifactRef(
                        artifact_id=row["evidence_id"],
                        artifact_type=row["evidence_type"],
                        content_hash=row["content_hash"],
                    ),
                )
            )
        return facts

    def _action_facts(
        self, conn: Any, scope: TenantScope, proposal_id: str
    ) -> list[_SourceFact]:
        exists = conn.execute(
            """SELECT 1 FROM aip_action_proposal
               WHERE org_id=%s AND project_id=%s AND proposal_id=%s""",
            (*scope.key, proposal_id),
        ).fetchone()
        if exists is None:
            raise AipLineageNotFound("action proposal not found in scope")
        facts: list[_SourceFact] = []
        for row in conn.execute(
            """SELECT event_id,event_type,proposal_version,proposal_hash,created_at
               FROM aip_action_event
               WHERE org_id=%s AND project_id=%s AND proposal_id=%s""",
            (*scope.key, proposal_id),
        ).fetchall():
            event_type = (
                LineageEventType.APPROVAL
                if row["event_type"] in {"approved", "rejected"}
                else LineageEventType.ERROR
                if row["event_type"] in {"failed", "expired"}
                else LineageEventType.ACTION
            )
            facts.append(
                _SourceFact(
                    LineageSourceKind.ACTION_EVENT,
                    str(row["event_id"]),
                    event_type,
                    row["created_at"],
                    dict(row),
                )
            )
        for row in conn.execute(
            """SELECT receipt_id,lease_id,status,provider_request_id,
                      request_fingerprint,evidence_refs,payload,receipt_kind,
                      supersedes_receipt_id,attempt_id,action_binding_hash,
                      approval_set_hash,adapter_revision_ref,account_binding_ref,
                      capability_binding_ref,reservation_ref,response_artifact_ref,
                      response_hash,output_schema_ref,receipt_schema_ref,
                      usage_schema_ref,redaction_policy_ref,
                      usage_receipt_refs,lineage_source_ref,receipt_content_hash,
                      created_at
               FROM aip_action_receipt
               WHERE org_id=%s AND project_id=%s AND proposal_id=%s""",
            (*scope.key, proposal_id),
        ).fetchall():
            event_type = (
                LineageEventType.RECONCILE
                if row["receipt_kind"] == "reconcile"
                else LineageEventType.ERROR
                if row["status"] in {"failed", "unknown"}
                else LineageEventType.RECEIPT
            )
            source_hash = self._hash(dict(row))
            facts.append(
                _SourceFact(
                    LineageSourceKind.ACTION_RECEIPT,
                    str(row["receipt_id"]),
                    event_type,
                    row["created_at"],
                    dict(row),
                    quality=(
                        EvidenceQuality.UNKNOWN
                        if row["status"] == "unknown"
                        else EvidenceQuality.MEASURED
                    ),
                    artifact=ArtifactRef(
                        artifact_id=row["receipt_id"],
                        artifact_type="action_receipt",
                        revision=row["receipt_kind"],
                        content_hash=source_hash,
                    ),
                )
            )
        return facts

    def _eval_facts(
        self, conn: Any, scope: TenantScope, run_id: str
    ) -> list[_SourceFact]:
        run = conn.execute(
            """SELECT run_id,suite_id,suite_revision,suite_hash,target_ref,
                      dataset_ref,judge_ref,status,idempotency_key,version,
                      created_at,started_at,finished_at
               FROM aip_eval_run
               WHERE org_id=%s AND project_id=%s AND run_id=%s""",
            (*scope.key, run_id),
        ).fetchone()
        if run is None:
            raise AipLineageNotFound("eval run not found in scope")
        facts = [
            _SourceFact(
                LineageSourceKind.EVAL_RUN,
                f"{run_id}:v{run['version']}",
                self._eval_event(str(run["status"])),
                run["finished_at"] or run["started_at"] or run["created_at"],
                dict(run),
                quality=(
                    EvidenceQuality.UNKNOWN
                    if run["status"] == "unknown"
                    else EvidenceQuality.MEASURED
                ),
                subject=AssetRevisionRef.model_validate(run["target_ref"]),
            )
        ]
        for row in conn.execute(
            """SELECT event_id,sequence,event_type,from_status,to_status,
                      payload_hash,created_at
               FROM aip_eval_run_event
               WHERE org_id=%s AND project_id=%s AND run_id=%s""",
            (*scope.key, run_id),
        ).fetchall():
            facts.append(
                _SourceFact(
                    LineageSourceKind.EVAL_RUN_EVENT,
                    str(row["event_id"]),
                    self._eval_event(str(row["to_status"])),
                    row["created_at"],
                    dict(row),
                    quality=(
                        EvidenceQuality.UNKNOWN
                        if row["to_status"] == "unknown"
                        else EvidenceQuality.MEASURED
                    ),
                    subject=AssetRevisionRef.model_validate(run["target_ref"]),
                )
            )
        for row in conn.execute(
            """SELECT report_id,revision,content_hash,target_ref,gate_passed,created_at
               FROM aip_eval_report_revision
               WHERE org_id=%s AND project_id=%s AND run_id=%s""",
            (*scope.key, run_id),
        ).fetchall():
            facts.append(
                _SourceFact(
                    LineageSourceKind.EVAL_REPORT,
                    f"{row['report_id']}:r{row['revision']}",
                    LineageEventType.EVAL,
                    row["created_at"],
                    dict(row),
                    subject=AssetRevisionRef.model_validate(row["target_ref"]),
                    artifact=ArtifactRef(
                        artifact_id=row["report_id"],
                        artifact_type="eval_report",
                        revision=str(row["revision"]),
                        content_hash=row["content_hash"],
                    ),
                )
            )
        return facts

    def _publication_facts(
        self, conn: Any, scope: TenantScope, publication_id: str
    ) -> list[_SourceFact]:
        rows = conn.execute(
            """SELECT event_id,event_type,target_ref,release_gate_decision_id,
                      reason_hash,occurred_at
               FROM aip_publication_event
               WHERE org_id=%s AND project_id=%s AND publication_id=%s""",
            (*scope.key, publication_id),
        ).fetchall()
        if not rows:
            raise AipLineageNotFound("publication not found in scope")
        return [
            _SourceFact(
                LineageSourceKind.PUBLICATION_EVENT,
                str(row["event_id"]),
                LineageEventType.RECEIPT,
                row["occurred_at"],
                dict(row),
                subject=AssetRevisionRef.model_validate(row["target_ref"]),
            )
            for row in rows
        ]

    def _list_with_conn(
        self, conn: Any, scope: TenantScope, lineage_id: str
    ) -> list[LineageEvent]:
        rows = conn.execute(
            """SELECT * FROM aip_lineage_event
               WHERE org_id=%s AND project_id=%s AND lineage_id=%s
               ORDER BY sequence,event_id""",
            (*scope.key, lineage_id),
        ).fetchall()
        return [
            LineageEvent(
                tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
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

    @staticmethod
    def _run_event(status: str) -> LineageEventType:
        if status in {"failed", "cancelled", "unknown"}:
            return LineageEventType.ERROR
        if status == "succeeded":
            return LineageEventType.RECEIPT
        if status == "queued":
            return LineageEventType.INPUT
        return LineageEventType.ACTION

    @staticmethod
    def _eval_event(status: str) -> LineageEventType:
        return (
            LineageEventType.ERROR
            if status in {"failed", "cancelled", "unknown"}
            else LineageEventType.EVAL
        )

    @staticmethod
    def _event_id(
        scope: TenantScope,
        source_kind: LineageSourceKind,
        source_id: str,
        source_hash: str,
    ) -> str:
        digest = hashlib.sha256(
            f"{scope.org_id}:{scope.project_id}:{source_kind.value}:{source_id}:{source_hash}".encode()
        ).hexdigest()[:28]
        return f"lineage-event-{digest}"

    @classmethod
    def _hash(cls, value: Any) -> str:
        return hashlib.sha256(cls._json(value).encode("utf-8")).hexdigest()

    @staticmethod
    def _json(value: Any) -> str:
        if hasattr(value, "model_dump"):
            value = value.model_dump(mode="json", by_alias=True)

        def fallback(item: Any) -> str:
            if isinstance(item, datetime):
                return item.isoformat()
            if isinstance(item, Decimal):
                return format(item, "f")
            return str(item)

        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=fallback,
        )

    @staticmethod
    def _time_key(value: datetime) -> str:
        return value.astimezone(timezone.utc).isoformat()

    @staticmethod
    def _require(scope: TenantScope, root_id: str) -> None:
        if not scope.org_id.strip() or not scope.project_id.strip():
            raise ValueError("org_id and project_id are required")
        if not root_id.strip():
            raise ValueError("root_id is required")

    def _connect(self, scope: TenantScope):
        try:
            return self._connect_factory(scope)
        except TypeError:
            return self._connect_factory()


__all__ = [
    "AipLineageConflict",
    "AipLineageError",
    "AipLineageNotFound",
    "AipLineagePersistenceError",
    "AipLineageService",
    "AipLineageUnsupportedRoot",
]
