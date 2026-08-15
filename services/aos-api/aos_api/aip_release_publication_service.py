"""AIP-4 E2 release gates and append-only publication events.

All evidence is re-read and checked inside the same tenant-scoped transaction.
The caller can select an exact report, but can never submit a GREEN status.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from typing import Any

from aos_api.aip_contracts import ArtifactRef, TenantContext
from aos_api.aip_eval_contracts import (
    AssetRevisionRef,
    AssetType,
    EvalReportRevision,
    EvalRunStatus,
    PublicationEvent,
    PublicationEventType,
    ReleaseGateDecision,
    ReleaseGateStatus,
)
from aos_api.aip_eval_pack_registry import compute_eval_suite_hash
from aos_api.aip_eval_runner import compute_eval_report_hash
from aos_api.aip_release_publication_models import (
    DeriveReleaseGateRequest,
    PublishReleaseRequest,
    RevokePublicationRequest,
)
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope

ConnectFactory = Callable[..., AbstractContextManager[Any]]


class AipReleasePublicationError(RuntimeError):
    code = "AIP_RELEASE_PUBLICATION_ERROR"


class AipReleasePublicationNotFound(AipReleasePublicationError):
    code = "AIP_RELEASE_PUBLICATION_NOT_FOUND"


class AipReleasePublicationConflict(AipReleasePublicationError):
    code = "AIP_RELEASE_PUBLICATION_CONFLICT"


class AipReleasePublicationIntegrityError(AipReleasePublicationError):
    code = "AIP_RELEASE_PUBLICATION_INTEGRITY_ERROR"


class AipReleaseGateRejected(AipReleasePublicationError):
    code = "AIP_RELEASE_GATE_REJECTED"


class AipReleaseAssetUnsupported(AipReleasePublicationError):
    code = "AIP_RELEASE_ASSET_UNSUPPORTED"


class AipPublicationAlreadyRevoked(AipReleasePublicationError):
    code = "AIP_PUBLICATION_ALREADY_REVOKED"


class AipReleasePublicationPersistenceError(AipReleasePublicationError):
    code = "AIP_RELEASE_PUBLICATION_PERSISTENCE_ERROR"


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(
        _jsonable(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", by_alias=True)
    if isinstance(value, dict):
        return {key: _jsonable(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(child) for child in value]
    return value


class AipReleasePublicationService:
    def __init__(self, connect_factory: ConnectFactory | None = None) -> None:
        self._connect_factory = connect_factory or db_connect

    def derive_gate(
        self,
        scope: TenantScope,
        *,
        actor: str,
        request: DeriveReleaseGateRequest,
    ) -> ReleaseGateDecision:
        actor = self._actor(actor)
        decision_id = self._stable_id("gate", scope, request.idempotency_key)
        try:
            with self._connect(scope) as conn:
                existing = self._gate_row(conn, scope, decision_id)
                if existing is not None:
                    gate = self._gate_from_row(scope, existing)
                    self._require_gate_replay(gate, actor=actor, request=request)
                    return gate

                report_row = conn.execute(
                    """SELECT * FROM aip_eval_report_revision
                       WHERE org_id=%s AND project_id=%s
                         AND report_id=%s AND revision=%s""",
                    (*scope.key, request.report_id, request.report_revision),
                ).fetchone()
                if report_row is None:
                    raise AipReleasePublicationNotFound("eval report revision not found")
                report = self._report_from_row(scope, report_row)
                if (
                    report.content_hash != request.report_hash
                    or compute_eval_report_hash(report) != request.report_hash
                ):
                    raise AipReleasePublicationIntegrityError(
                        "eval report revision/hash verification failed"
                    )

                run_row = conn.execute(
                    """SELECT * FROM aip_eval_run
                       WHERE org_id=%s AND project_id=%s AND run_id=%s""",
                    (*scope.key, report.run_id),
                ).fetchone()
                if run_row is None:
                    raise AipReleasePublicationIntegrityError("eval run is missing")
                self._verify_run(report, run_row)

                suite_revision = self._int_revision(report.suite_ref.revision)
                suite_row = conn.execute(
                    """SELECT * FROM aip_eval_suite_revision
                       WHERE org_id=%s AND project_id=%s
                         AND suite_id=%s AND revision=%s""",
                    (*scope.key, report.suite_ref.asset_id, suite_revision),
                ).fetchone()
                if suite_row is None:
                    raise AipReleasePublicationIntegrityError(
                        "eval suite revision is missing"
                    )
                suite = self._suite_from_row(suite_row)
                if (
                    suite.content_hash != report.suite_ref.content_hash
                    or compute_eval_suite_hash(suite) != suite.content_hash
                    or suite.target != report.target
                    or suite.dataset != report.dataset
                    or suite.judge != report.judge
                ):
                    raise AipReleasePublicationIntegrityError(
                        "eval suite/report exact references drifted"
                    )

                status = (
                    ReleaseGateStatus.PASSED
                    if report.gate_passed
                    and report.pass_rate >= suite.gate_threshold
                    else ReleaseGateStatus.FAILED
                )
                decided_at = datetime.now(UTC)
                report_ref = ArtifactRef(
                    artifact_id=report.report_id,
                    artifact_type=AssetType.EVAL_REPORT.value,
                    revision=str(report.revision),
                    content_hash=report.content_hash,
                )
                decision_hash = _canonical_hash(
                    {
                        "target": report.target,
                        "suiteRef": report.suite_ref,
                        "evalRunId": report.run_id,
                        "evalReport": report_ref,
                        "status": status.value,
                    }
                )
                gate = ReleaseGateDecision(
                    tenant=self._tenant(scope),
                    decision_id=decision_id,
                    target=report.target,
                    suite_ref=report.suite_ref,
                    eval_run_id=report.run_id,
                    eval_report=report_ref,
                    status=status,
                    decision_hash=decision_hash,
                    decided_by=actor,
                    decided_at=decided_at,
                )
                self._insert_gate(conn, scope, gate)
                conn.commit()
                return gate
        except AipReleasePublicationError:
            raise
        except Exception as exc:
            raise AipReleasePublicationPersistenceError(
                "release gate derivation failed"
            ) from exc

    def publish(
        self,
        scope: TenantScope,
        *,
        actor: str,
        request: PublishReleaseRequest,
    ) -> PublicationEvent:
        actor = self._actor(actor)
        publication_id = self._stable_id("publication", scope, request.idempotency_key)
        event_id = self._stable_id("published", scope, request.idempotency_key)
        try:
            with self._connect(scope) as conn:
                existing = self._event_row(conn, scope, event_id)
                if existing is not None:
                    event = self._event_from_row(scope, existing)
                    if (
                        event.publication_id != publication_id
                        or event.release_gate_decision_id
                        != request.release_gate_decision_id
                        or event.reason_hash != request.reason_hash
                        or event.actor != actor
                        or event.event_type is not PublicationEventType.PUBLISHED
                    ):
                        raise AipReleasePublicationConflict(
                            "idempotency key was reused with a different publication"
                        )
                    return event

                gate_row = self._gate_row(
                    conn, scope, request.release_gate_decision_id
                )
                if gate_row is None:
                    raise AipReleasePublicationNotFound(
                        "release gate decision not found"
                    )
                gate = self._gate_from_row(scope, gate_row)
                if gate.status is not ReleaseGateStatus.PASSED:
                    raise AipReleaseGateRejected("release gate is not passed")
                self._verify_gate_evidence(conn, scope, gate)
                self._verify_publishable_target(conn, scope, gate.target)
                event = PublicationEvent(
                    tenant=self._tenant(scope),
                    event_id=event_id,
                    publication_id=publication_id,
                    target=gate.target,
                    event_type=PublicationEventType.PUBLISHED,
                    release_gate_decision_id=gate.decision_id,
                    reason_hash=request.reason_hash,
                    actor=actor,
                    occurred_at=datetime.now(UTC),
                )
                self._insert_event(conn, scope, event)
                conn.commit()
                return event
        except AipReleasePublicationError:
            raise
        except Exception as exc:
            raise AipReleasePublicationPersistenceError("publication failed") from exc

    def revoke(
        self,
        scope: TenantScope,
        *,
        publication_id: str,
        actor: str,
        request: RevokePublicationRequest,
    ) -> PublicationEvent:
        actor = self._actor(actor)
        event_id = self._stable_id("revoked", scope, request.idempotency_key)
        try:
            with self._connect(scope) as conn:
                existing = self._event_row(conn, scope, event_id)
                if existing is not None:
                    event = self._event_from_row(scope, existing)
                    if (
                        event.publication_id != publication_id
                        or event.reason_hash != request.reason_hash
                        or event.actor != actor
                        or event.event_type is not PublicationEventType.REVOKED
                    ):
                        raise AipReleasePublicationConflict(
                            "idempotency key was reused with a different revocation"
                        )
                    return event

                published_row = conn.execute(
                    """SELECT * FROM aip_publication_event
                       WHERE org_id=%s AND project_id=%s AND publication_id=%s
                         AND event_type='published'
                       ORDER BY occurred_at,event_id LIMIT 1 FOR UPDATE""",
                    (*scope.key, publication_id),
                ).fetchone()
                if published_row is None:
                    raise AipReleasePublicationNotFound("publication not found")
                revoked = conn.execute(
                    """SELECT 1 FROM aip_publication_event
                       WHERE org_id=%s AND project_id=%s AND publication_id=%s
                         AND event_type='revoked' LIMIT 1""",
                    (*scope.key, publication_id),
                ).fetchone()
                if revoked is not None:
                    raise AipPublicationAlreadyRevoked(
                        "publication already has a revocation event"
                    )
                published = self._event_from_row(scope, published_row)
                event = PublicationEvent(
                    tenant=self._tenant(scope),
                    event_id=event_id,
                    publication_id=publication_id,
                    target=published.target,
                    event_type=PublicationEventType.REVOKED,
                    release_gate_decision_id=published.release_gate_decision_id,
                    reason_hash=request.reason_hash,
                    actor=actor,
                    occurred_at=datetime.now(UTC),
                )
                self._insert_event(conn, scope, event)
                conn.commit()
                return event
        except AipReleasePublicationError:
            raise
        except Exception as exc:
            raise AipReleasePublicationPersistenceError("revocation failed") from exc

    @staticmethod
    def _verify_gate_evidence(
        conn: Any, scope: TenantScope, gate: ReleaseGateDecision
    ) -> None:
        expected_hash = _canonical_hash(
            {
                "target": gate.target,
                "suiteRef": gate.suite_ref,
                "evalRunId": gate.eval_run_id,
                "evalReport": gate.eval_report,
                "status": gate.status.value,
            }
        )
        if gate.decision_hash != expected_hash:
            raise AipReleasePublicationIntegrityError(
                "release gate decision hash verification failed"
            )
        revision = AipReleasePublicationService._int_revision(
            gate.eval_report.revision or ""
        )
        row = conn.execute(
            """SELECT * FROM aip_eval_report_revision
               WHERE org_id=%s AND project_id=%s
                 AND report_id=%s AND revision=%s""",
            (*scope.key, gate.eval_report.artifact_id, revision),
        ).fetchone()
        if row is None:
            raise AipReleasePublicationIntegrityError(
                "release gate eval report is missing"
            )
        report = AipReleasePublicationService._report_from_row(scope, row)
        if (
            report.content_hash != gate.eval_report.content_hash
            or compute_eval_report_hash(report) != report.content_hash
            or report.target != gate.target
            or report.suite_ref != gate.suite_ref
            or report.run_id != gate.eval_run_id
        ):
            raise AipReleasePublicationIntegrityError(
                "release gate eval report exact references drifted"
            )

    @staticmethod
    def _verify_run(report: EvalReportRevision, row: Any) -> None:
        if (
            EvalRunStatus(str(row["status"])) is not EvalRunStatus.SUCCEEDED
            or row["suite_id"] != report.suite_ref.asset_id
            or int(row["suite_revision"])
            != AipReleasePublicationService._int_revision(
                report.suite_ref.revision
            )
            or row["suite_hash"] != report.suite_ref.content_hash
            or AssetRevisionRef.model_validate(row["target_ref"]) != report.target
            or row["dataset_ref"] != report.dataset.model_dump(
                mode="json", by_alias=True
            )
            or row["judge_ref"] != report.judge.model_dump(mode="json", by_alias=True)
        ):
            raise AipReleasePublicationIntegrityError(
                "eval run/report exact references drifted or run did not succeed"
            )

    @staticmethod
    def _verify_publishable_target(
        conn: Any, scope: TenantScope, target: AssetRevisionRef
    ) -> None:
        if target.asset_type is AssetType.SKILL_TEMPLATE:
            revision = AipReleasePublicationService._int_revision(target.revision)
            row = conn.execute(
                """SELECT lifecycle,content_hash
                   FROM aip_skill_template_revision
                   WHERE skill_id=%s AND revision=%s""",
                (target.asset_id, revision),
            ).fetchone()
            if row is None:
                raise AipReleasePublicationNotFound(
                    "skill template revision not found"
                )
            if (
                row["lifecycle"] != "evaluated"
                or row["content_hash"] != target.content_hash
            ):
                raise AipReleasePublicationIntegrityError(
                    "skill template revision/hash/lifecycle changed after evaluation"
                )
            return
        if target.asset_type is not AssetType.LOGIC_GRAPH:
            raise AipReleaseAssetUnsupported(
                "asset registry is not available for this target type"
            )
        revision = AipReleasePublicationService._int_revision(target.revision)
        row = conn.execute(
            """SELECT r.graph_hash,g.revision AS current_revision,
                      g.graph_hash AS current_hash,g.deleted_at
               FROM aip_logic_graph_revision r
               JOIN aip_logic_graph g
                 ON g.org_id=r.org_id AND g.project_id=r.project_id
                AND g.graph_id=r.graph_id
               WHERE r.org_id=%s AND r.project_id=%s
                 AND r.graph_id=%s AND r.revision=%s""",
            (*scope.key, target.asset_id, revision),
        ).fetchone()
        if row is None:
            raise AipReleasePublicationNotFound("logic graph revision not found")
        if (
            row["graph_hash"] != target.content_hash
            or int(row["current_revision"]) != revision
            or row["current_hash"] != target.content_hash
            or row["deleted_at"] is not None
        ):
            raise AipReleasePublicationIntegrityError(
                "logic graph revision/hash changed after evaluation"
            )

    @staticmethod
    def _require_gate_replay(
        gate: ReleaseGateDecision,
        *,
        actor: str,
        request: DeriveReleaseGateRequest,
    ) -> None:
        if (
            gate.eval_report.artifact_id != request.report_id
            or gate.eval_report.revision != str(request.report_revision)
            or gate.eval_report.content_hash != request.report_hash
            or gate.decided_by != actor
        ):
            raise AipReleasePublicationConflict(
                "idempotency key was reused with a different gate request"
            )

    @staticmethod
    def _insert_gate(
        conn: Any, scope: TenantScope, gate: ReleaseGateDecision
    ) -> None:
        conn.execute(
            """INSERT INTO aip_release_gate_decision (
               org_id,project_id,decision_id,target_ref,suite_ref,eval_run_id,
               eval_report_ref,status,decision_hash,invalidated_by,decided_by,decided_at
               ) VALUES (%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s::jsonb,%s,%s,%s,%s,%s)""",
            (
                *scope.key,
                gate.decision_id,
                AipReleasePublicationService._json(gate.target),
                AipReleasePublicationService._json(gate.suite_ref),
                gate.eval_run_id,
                AipReleasePublicationService._json(gate.eval_report),
                gate.status.value,
                gate.decision_hash,
                gate.invalidated_by,
                gate.decided_by,
                gate.decided_at,
            ),
        )

    @staticmethod
    def _insert_event(conn: Any, scope: TenantScope, event: PublicationEvent) -> None:
        conn.execute(
            """INSERT INTO aip_publication_event (
               org_id,project_id,event_id,publication_id,target_ref,event_type,
               release_gate_decision_id,reason_hash,actor,occurred_at
               ) VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s)""",
            (
                *scope.key,
                event.event_id,
                event.publication_id,
                AipReleasePublicationService._json(event.target),
                event.event_type.value,
                event.release_gate_decision_id,
                event.reason_hash,
                event.actor,
                event.occurred_at,
            ),
        )

    @staticmethod
    def _gate_row(conn: Any, scope: TenantScope, decision_id: str) -> Any | None:
        return conn.execute(
            """SELECT * FROM aip_release_gate_decision
               WHERE org_id=%s AND project_id=%s AND decision_id=%s""",
            (*scope.key, decision_id),
        ).fetchone()

    @staticmethod
    def _event_row(conn: Any, scope: TenantScope, event_id: str) -> Any | None:
        return conn.execute(
            """SELECT * FROM aip_publication_event
               WHERE org_id=%s AND project_id=%s AND event_id=%s""",
            (*scope.key, event_id),
        ).fetchone()

    @staticmethod
    def _gate_from_row(scope: TenantScope, row: Any) -> ReleaseGateDecision:
        return ReleaseGateDecision(
            tenant=AipReleasePublicationService._tenant(scope),
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
        )

    @staticmethod
    def _event_from_row(scope: TenantScope, row: Any) -> PublicationEvent:
        return PublicationEvent(
            tenant=AipReleasePublicationService._tenant(scope),
            event_id=row["event_id"],
            publication_id=row["publication_id"],
            target=row["target_ref"],
            event_type=row["event_type"],
            release_gate_decision_id=row["release_gate_decision_id"],
            reason_hash=row["reason_hash"],
            actor=row["actor"],
            occurred_at=row["occurred_at"],
        )

    @staticmethod
    def _report_from_row(scope: TenantScope, row: Any) -> EvalReportRevision:
        return EvalReportRevision(
            tenant=AipReleasePublicationService._tenant(scope),
            report_id=row["report_id"],
            revision=row["revision"],
            content_hash=row["content_hash"],
            run_id=row["run_id"],
            suite_ref=row["suite_ref"],
            target=row["target_ref"],
            dataset=row["dataset_ref"],
            judge=row["judge_ref"],
            results=row["results"],
            passed=row["passed"],
            failed=row["failed"],
            total=row["total"],
            pass_rate=row["pass_rate"],
            gate_passed=row["gate_passed"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _suite_from_row(row: Any):
        from aos_api.aip_eval_contracts import EvalSuiteRevision

        return EvalSuiteRevision(
            suite_id=row["suite_id"],
            revision=row["revision"],
            content_hash=row["content_hash"],
            target=row["target_ref"],
            dataset=row["dataset_ref"],
            judge=row["judge_ref"],
            cases=row["cases"],
            gate_threshold=row["gate_threshold"],
        )

    def _connect(self, scope: TenantScope) -> AbstractContextManager[Any]:
        if self._connect_factory is db_connect:
            return db_connect(scope)
        try:
            return self._connect_factory(scope)
        except TypeError:
            return self._connect_factory()

    @staticmethod
    def _stable_id(kind: str, scope: TenantScope, key: str) -> str:
        digest = _canonical_hash({"kind": kind, "scope": scope.key, "key": key})
        return f"{kind}-{digest[:32]}"

    @staticmethod
    def _int_revision(value: str) -> int:
        try:
            revision = int(value)
        except (TypeError, ValueError) as exc:
            raise AipReleasePublicationIntegrityError(
                "asset revision must be an integer for the current registry"
            ) from exc
        if revision < 1 or str(revision) != str(value):
            raise AipReleasePublicationIntegrityError("asset revision is not canonical")
        return revision

    @staticmethod
    def _actor(actor: str) -> str:
        actor = actor.strip()
        if not actor:
            raise ValueError("actor is required")
        return actor

    @staticmethod
    def _tenant(scope: TenantScope) -> TenantContext:
        return TenantContext(org_id=scope.org_id, project_id=scope.project_id)

    @staticmethod
    def _json(value: Any) -> str:
        if hasattr(value, "model_dump"):
            value = value.model_dump(mode="json", by_alias=True)
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


__all__ = [
    "AipPublicationAlreadyRevoked",
    "AipReleaseAssetUnsupported",
    "AipReleaseGateRejected",
    "AipReleasePublicationConflict",
    "AipReleasePublicationError",
    "AipReleasePublicationIntegrityError",
    "AipReleasePublicationNotFound",
    "AipReleasePublicationPersistenceError",
    "AipReleasePublicationService",
]
