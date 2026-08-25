"""AIP-4 E1B runner with exact-reference drift checks and hash-only reports."""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from aos_api.aip_contracts import ArtifactRef, TenantContext
from aos_api.aip_eval_authority_store import (
    AipEvalAuthorityConflict,
    AipEvalAuthorityNotFound,
    AipEvalAuthorityPersistenceError,
    AipEvalAuthorityStore,
)
from aos_api.aip_eval_contracts import (
    AssetRevisionRef,
    AssetType,
    EvalCaseResultEvidence,
    EvalContractRevisionRef,
    EvalGatePolicyRef,
    EvalReportRevision,
    EvalRunAuthorityRecord,
    EvalRunEvent,
    EvalRunStatus,
    EvalStageAttemptRef,
    EvalSubjectArtifactRef,
    JudgeRevisionRef,
)
from aos_api.aip_eval_pack_registry import AipEvalPackRegistry
from aos_api.aip_production_contract_store import (
    AipProductionContractStore,
    ProductionContractError,
)
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope

ConnectFactory = Callable[..., AbstractContextManager[Any]]


@dataclass(frozen=True)
class ResolvedArtifact:
    reference: ArtifactRef
    value: Any


@dataclass(frozen=True)
class TargetExecution:
    target: AssetRevisionRef
    value: Any


@dataclass(frozen=True)
class JudgeExecution:
    judge: JudgeRevisionRef
    passed: bool
    detail_code: str


ArtifactResolver = Callable[[ArtifactRef], ResolvedArtifact]
TargetExecutor = Callable[[AssetRevisionRef, Any], TargetExecution]
JudgeExecutor = Callable[[JudgeRevisionRef, Any, Any], JudgeExecution]


def _hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compute_eval_report_hash(report: EvalReportRevision) -> str:
    payload = report.model_dump(mode="json", by_alias=True, exclude={"content_hash"})
    return _hash(payload)


class AipEvalRunner:
    def __init__(
        self,
        connect_factory: ConnectFactory | None = None,
        *,
        production_contract_store: AipProductionContractStore | None = None,
    ) -> None:
        self._connect_factory = connect_factory or db_connect
        self._authority = AipEvalAuthorityStore(connect_factory=self._connect_factory)
        self._registry = AipEvalPackRegistry(connect_factory=self._connect_factory)
        self._contracts = production_contract_store or AipProductionContractStore(
            connect_factory=self._connect_factory
        )

    def run_by_contract(
        self,
        scope: TenantScope,
        *,
        contract_id: str,
        contract_revision: int,
        contract_content_hash: str,
        idempotency_key: str,
        actor: str,
        resolve_artifact: ArtifactResolver,
        execute_target: TargetExecutor,
        execute_judge: JudgeExecutor,
        subject_artifact_ref: EvalSubjectArtifactRef | None = None,
        stage_attempt_ref: EvalStageAttemptRef | None = None,
        gate_policy_ref: EvalGatePolicyRef | None = None,
        evidence_cutoff_at: datetime | None = None,
    ) -> EvalReportRevision:
        """Resolve the suite only from one frozen, ready exact EvalContract revision."""
        ref = EvalContractRevisionRef(
            resource_id=contract_id,
            revision=contract_revision,
            content_hash=contract_content_hash,
        )
        contract = self._resolve_contract(scope, ref)
        return self.run(
            scope,
            suite_id=contract.suite_ref.resource_id,
            suite_revision=contract.suite_ref.revision,
            idempotency_key=idempotency_key,
            actor=actor,
            resolve_artifact=resolve_artifact,
            execute_target=execute_target,
            execute_judge=execute_judge,
            eval_contract_ref=ref,
            subject_artifact_ref=subject_artifact_ref,
            stage_attempt_ref=stage_attempt_ref,
            gate_policy_ref=gate_policy_ref,
            evidence_cutoff_at=evidence_cutoff_at,
        )

    def run(
        self,
        scope: TenantScope,
        *,
        suite_id: str,
        suite_revision: int,
        idempotency_key: str,
        actor: str,
        resolve_artifact: ArtifactResolver,
        execute_target: TargetExecutor,
        execute_judge: JudgeExecutor,
        eval_contract_ref: EvalContractRevisionRef | None = None,
        subject_artifact_ref: EvalSubjectArtifactRef | None = None,
        stage_attempt_ref: EvalStageAttemptRef | None = None,
        gate_policy_ref: EvalGatePolicyRef | None = None,
        evidence_cutoff_at: datetime | None = None,
    ) -> EvalReportRevision:
        media_refs = (
            subject_artifact_ref,
            stage_attempt_ref,
            gate_policy_ref,
            evidence_cutoff_at,
        )
        if any(item is None for item in media_refs) and any(item is not None for item in media_refs):
            raise AipEvalAuthorityConflict(
                "media Artifact, Stage attempt, policy and cutoff must be bound together"
            )
        if subject_artifact_ref is not None:
            if eval_contract_ref is None:
                raise AipEvalAuthorityConflict("media subject eval requires exact contract")
            assert stage_attempt_ref is not None
            self._assert_media_subject(scope, subject_artifact_ref, stage_attempt_ref)
        suite = self._registry.get_suite_revision(scope, suite_id, suite_revision)
        if eval_contract_ref is not None:
            contract = self._resolve_contract(scope, eval_contract_ref)
            if (
                contract.suite_ref.resource_id != suite.suite_id
                or contract.suite_ref.revision != suite.revision
                or contract.suite_ref.content_hash != suite.content_hash
            ):
                raise AipEvalAuthorityConflict(
                    "eval contract suite exact reference does not match resolved suite"
                )
        self._assert_target_not_withdrawn(scope, suite.target)
        tenant = TenantContext(org_id=scope.org_id, project_id=scope.project_id)
        now = datetime.now(UTC)
        run_id = f"eval-run-{uuid.uuid4().hex}"
        suite_ref = AssetRevisionRef(
            asset_type=AssetType.EVAL_SUITE,
            asset_id=suite.suite_id,
            revision=str(suite.revision),
            content_hash=suite.content_hash,
        )
        run = EvalRunAuthorityRecord(
            tenant=tenant,
            run_id=run_id,
            suite_ref=suite_ref,
            eval_contract_ref=eval_contract_ref,
            subject_artifact_ref=subject_artifact_ref,
            stage_attempt_ref=stage_attempt_ref,
            gate_policy_ref=gate_policy_ref,
            evidence_cutoff_at=evidence_cutoff_at,
            target=suite.target,
            dataset=suite.dataset,
            judge=suite.judge,
            status=EvalRunStatus.QUEUED,
            idempotency_key=idempotency_key,
            created_by=actor,
            created_at=now,
            version=1,
        )
        initial = self._event(tenant, run_id, 1, None, EvalRunStatus.QUEUED, actor)
        run = self._authority.create_eval_run(scope, run, initial)
        if run.status is not EvalRunStatus.QUEUED:
            raise AipEvalAuthorityConflict("eval run idempotency replay is not queued")
        running = self._event(
            tenant, run_id, 2, EvalRunStatus.QUEUED, EvalRunStatus.RUNNING, actor
        )
        run = self._authority.transition_eval_run(scope, running, expected_version=1)
        try:
            results: list[EvalCaseResultEvidence] = []
            for case in suite.cases:
                started = time.monotonic()
                input_value = self._resolve_exact(resolve_artifact, case.input_artifact)
                expected_value = (
                    self._resolve_exact(resolve_artifact, case.expected_artifact)
                    if case.expected_artifact
                    else None
                )
                execution = execute_target(suite.target, input_value)
                if execution.target != suite.target:
                    raise AipEvalAuthorityConflict("target revision/hash drifted during eval")
                judged = execute_judge(suite.judge, execution.value, expected_value)
                if judged.judge != suite.judge:
                    raise AipEvalAuthorityConflict("judge revision/hash drifted during eval")
                results.append(
                    EvalCaseResultEvidence(
                        case_id=case.case_id,
                        passed=judged.passed,
                        actual_hash=_hash(execution.value),
                        expected_hash=_hash(expected_value) if case.expected_artifact else None,
                        detail_code=judged.detail_code,
                        duration_ms=max(0, int((time.monotonic() - started) * 1000)),
                    )
                )
            passed = sum(1 for result in results if result.passed)
            total = len(results)
            report = EvalReportRevision(
                tenant=tenant,
                report_id=f"eval-report-{uuid.uuid4().hex}",
                revision=1,
                content_hash="0" * 64,
                run_id=run_id,
                suite_ref=suite_ref,
                eval_contract_ref=eval_contract_ref,
                subject_artifact_ref=subject_artifact_ref,
                stage_attempt_ref=stage_attempt_ref,
                gate_policy_ref=gate_policy_ref,
                evidence_cutoff_at=evidence_cutoff_at,
                target=suite.target,
                dataset=suite.dataset,
                judge=suite.judge,
                results=results,
                passed=passed,
                failed=total - passed,
                total=total,
                pass_rate=round(passed / total, 6),
                gate_passed=(passed / total) >= suite.gate_threshold,
                created_at=datetime.now(UTC),
            )
            report = report.model_copy(update={"content_hash": compute_eval_report_hash(report)})
            self._append_report(scope, report)
            success = self._event(
                tenant, run_id, 3, EvalRunStatus.RUNNING, EvalRunStatus.SUCCEEDED, actor
            )
            self._authority.transition_eval_run(scope, success, expected_version=2)
            return report
        except Exception:
            failed = self._event(
                tenant, run_id, 3, EvalRunStatus.RUNNING, EvalRunStatus.FAILED, actor
            )
            try:
                self._authority.transition_eval_run(scope, failed, expected_version=2)
            except Exception:  # noqa: BLE001,S110 - preserve original failure
                pass
            raise

    def get_report(self, scope: TenantScope, report_id: str, revision: int = 1) -> EvalReportRevision:
        try:
            with self._connect(scope) as conn:
                row = conn.execute(
                    """SELECT * FROM aip_eval_report_revision
                       WHERE org_id=%s AND project_id=%s AND report_id=%s AND revision=%s""",
                    (scope.org_id, scope.project_id, report_id, revision),
                ).fetchone()
        except Exception as exc:
            raise AipEvalAuthorityPersistenceError("eval report read failed") from exc
        if row is None:
            raise AipEvalAuthorityNotFound("eval report revision not found")
        return self._report_from_row(scope, row)

    def _append_report(self, scope: TenantScope, report: EvalReportRevision) -> None:
        try:
            with self._connect(scope) as conn:
                base = (
                    scope.org_id, scope.project_id, report.report_id, report.revision,
                    report.content_hash, report.run_id,
                )
                tail = (
                    self._json(report.suite_ref), self._json(report.target),
                    self._json(report.dataset), self._json(report.judge),
                    self._json(report.results), report.passed, report.failed, report.total,
                    report.pass_rate, report.gate_passed, report.created_at,
                )
                if report.subject_artifact_ref is None:
                    if report.eval_contract_ref is None:
                        statement = """INSERT INTO aip_eval_report_revision (
                           org_id,project_id,report_id,revision,content_hash,run_id,
                           suite_ref,target_ref,dataset_ref,judge_ref,results,passed,
                           failed,total,pass_rate,gate_passed,created_at
                           ) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,
                                     %s::jsonb,%s::jsonb,%s,%s,%s,%s,%s,%s)
                           ON CONFLICT (org_id,project_id,run_id) DO NOTHING RETURNING report_id"""
                        params = (*base, *tail)
                    else:
                        statement = """INSERT INTO aip_eval_report_revision (
                           org_id,project_id,report_id,revision,content_hash,run_id,
                           eval_contract_ref,suite_ref,target_ref,dataset_ref,judge_ref,results,
                           passed,failed,total,pass_rate,gate_passed,created_at
                           ) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,
                                     %s::jsonb,%s::jsonb,%s::jsonb,%s,%s,%s,%s,%s,%s)
                           ON CONFLICT (org_id,project_id,run_id) DO NOTHING RETURNING report_id"""
                        params = (*base, self._json(report.eval_contract_ref), *tail)
                else:
                    statement = """INSERT INTO aip_eval_report_revision (
                       org_id,project_id,report_id,revision,content_hash,run_id,
                       eval_contract_ref,subject_artifact_ref,stage_attempt_ref,
                       gate_policy_ref,evidence_cutoff_at,suite_ref,target_ref,dataset_ref,judge_ref,results,
                       passed,failed,total,pass_rate,gate_passed,created_at
                       ) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,
                                 %s::jsonb,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,
                                 %s,%s,%s,%s,%s,%s)
                       ON CONFLICT (org_id,project_id,run_id) DO NOTHING RETURNING report_id"""
                    params = (
                        *base, self._json(report.eval_contract_ref),
                        self._json(report.subject_artifact_ref),
                        self._json(report.stage_attempt_ref),
                        self._json(report.gate_policy_ref), report.evidence_cutoff_at, *tail,
                    )
                row = conn.execute(statement, params).fetchone()
                if row is None:
                    raise AipEvalAuthorityConflict("eval run already has a report")
                conn.commit()
        except (AipEvalAuthorityConflict, AipEvalAuthorityNotFound):
            raise
        except Exception as exc:
            raise AipEvalAuthorityPersistenceError("eval report persistence failed") from exc

    def _assert_target_not_withdrawn(
        self, scope: TenantScope, target: AssetRevisionRef
    ) -> None:
        try:
            with self._connect(scope) as conn:
                row = conn.execute(
                    """SELECT event_type FROM aip_publication_event
                       WHERE org_id=%s AND project_id=%s
                         AND target_ref=%s::jsonb
                       ORDER BY occurred_at DESC,event_id DESC LIMIT 1""",
                    (*scope.key, self._json(target)),
                ).fetchone()
        except Exception as exc:
            raise AipEvalAuthorityPersistenceError(
                "publication state read failed before eval run"
            ) from exc
        if row is not None and row["event_type"] in {
            "revoked",
            "suspended",
            "deprecated",
        }:
            raise AipEvalAuthorityConflict(
                "eval target publication is withdrawn; a new revision is required"
            )

    def _assert_media_subject(
        self,
        scope: TenantScope,
        artifact_ref: EvalSubjectArtifactRef,
        attempt_ref: EvalStageAttemptRef,
    ) -> None:
        """Resolve media subject and require the canonical latest StepRun attempt."""
        try:
            with self._connect(scope) as conn:
                artifact = conn.execute(
                    """SELECT artifact_id,content_hash,run_id,family_role
                       FROM aip_artifact
                       WHERE org_id=%s AND project_id=%s AND artifact_id=%s""",
                    (*scope.key, artifact_ref.resource_id),
                ).fetchone()
                attempt = conn.execute(
                    """SELECT step_run_id,run_id,step_key,attempt,input_hash
                       FROM aip_step_run
                       WHERE org_id=%s AND project_id=%s AND step_run_id=%s""",
                    (*scope.key, attempt_ref.step_run_id),
                ).fetchone()
                latest = conn.execute(
                    """SELECT step_run_id,attempt FROM aip_step_run
                       WHERE org_id=%s AND project_id=%s AND run_id=%s AND step_key=%s
                       ORDER BY attempt DESC LIMIT 1""",
                    (*scope.key, attempt_ref.run_id, attempt_ref.step_key),
                ).fetchone()
        except Exception as exc:
            raise AipEvalAuthorityPersistenceError(
                "media eval subject resolution failed"
            ) from exc
        if (
            artifact is None
            or artifact["content_hash"] != artifact_ref.content_hash
            or artifact["family_role"] != "variant"
            or artifact["run_id"] != attempt_ref.run_id
        ):
            raise AipEvalAuthorityConflict("media eval Artifact is missing or drifted")
        if (
            attempt is None
            or attempt["run_id"] != attempt_ref.run_id
            or attempt["step_key"] != attempt_ref.step_key
            or int(attempt["attempt"]) != attempt_ref.attempt
            or attempt["input_hash"] != attempt_ref.input_hash
        ):
            raise AipEvalAuthorityConflict("media eval Stage attempt is missing or drifted")
        if (
            latest is None
            or latest["step_run_id"] != attempt_ref.step_run_id
            or int(latest["attempt"]) != attempt_ref.attempt
        ):
            raise AipEvalAuthorityConflict("media eval requires the latest Stage attempt")

    def _resolve_contract(
        self, scope: TenantScope, ref: EvalContractRevisionRef
    ):
        try:
            contract = self._contracts.get_eval_contract(
                scope, ref.resource_id, ref.revision
            )
        except ProductionContractError as exc:
            raise AipEvalAuthorityConflict(
                "eval contract exact reference is unavailable"
            ) from exc
        if contract.content_hash != ref.content_hash:
            raise AipEvalAuthorityConflict("eval contract exact content hash drifted")
        if contract.lifecycle.value != "frozen":
            raise AipEvalAuthorityConflict("eval contract is not frozen")
        if contract.readiness.value != "ready" or contract.blockers:
            codes = ",".join(blocker.code for blocker in contract.blockers)
            raise AipEvalAuthorityConflict(
                f"eval contract is not ready:{codes or 'UNKNOWN'}"
            )
        return contract

    @staticmethod
    def _resolve_exact(resolver: ArtifactResolver, ref: ArtifactRef | None) -> Any:
        if ref is None or not ref.revision or not ref.content_hash:
            raise AipEvalAuthorityConflict("eval artifact requires exact revision/hash")
        resolved = resolver(ref)
        if resolved.reference != ref:
            raise AipEvalAuthorityConflict("eval artifact revision/hash drifted")
        if _hash(resolved.value) != ref.content_hash:
            raise AipEvalAuthorityConflict("eval artifact content hash drifted")
        return resolved.value

    @staticmethod
    def _event(tenant: TenantContext, run_id: str, sequence: int, from_status: EvalRunStatus | None, to_status: EvalRunStatus, actor: str) -> EvalRunEvent:
        now = datetime.now(UTC)
        return EvalRunEvent(
            tenant=tenant,
            event_id=f"eval-event-{uuid.uuid4().hex}",
            run_id=run_id,
            sequence=sequence,
            event_type="status_changed" if from_status else "created",
            from_status=from_status,
            to_status=to_status,
            payload_hash=_hash({"from": from_status.value if from_status else None, "to": to_status.value}),
            actor=actor,
            created_at=now,
        )

    def _connect(self, scope: TenantScope) -> AbstractContextManager[Any]:
        if self._connect_factory is db_connect:
            return db_connect(scope)
        try:
            return self._connect_factory(scope)
        except TypeError:
            return self._connect_factory()

    @staticmethod
    def _json(value: Any) -> str:
        if hasattr(value, "model_dump"):
            value = value.model_dump(mode="json", by_alias=True)
        elif isinstance(value, list):
            value = [item.model_dump(mode="json", by_alias=True) for item in value]
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def _report_from_row(scope: TenantScope, row: Any) -> EvalReportRevision:
        return EvalReportRevision(
            tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
            report_id=row["report_id"], revision=row["revision"], content_hash=row["content_hash"],
            run_id=row["run_id"], suite_ref=row["suite_ref"], target=row["target_ref"],
            eval_contract_ref=(
                row["eval_contract_ref"]
                if "eval_contract_ref" in row.keys() and row["eval_contract_ref"] is not None
                else None
            ),
            subject_artifact_ref=(
                row["subject_artifact_ref"]
                if "subject_artifact_ref" in row.keys() and row["subject_artifact_ref"] is not None
                else None
            ),
            stage_attempt_ref=(
                row["stage_attempt_ref"]
                if "stage_attempt_ref" in row.keys() and row["stage_attempt_ref"] is not None
                else None
            ),
            gate_policy_ref=(
                row["gate_policy_ref"]
                if "gate_policy_ref" in row.keys() and row["gate_policy_ref"] is not None
                else None
            ),
            evidence_cutoff_at=(
                row["evidence_cutoff_at"] if "evidence_cutoff_at" in row.keys() else None
            ),
            dataset=row["dataset_ref"], judge=row["judge_ref"], results=row["results"],
            passed=row["passed"], failed=row["failed"], total=row["total"],
            pass_rate=row["pass_rate"], gate_passed=row["gate_passed"], created_at=row["created_at"],
        )


__all__ = [
    "AipEvalRunner", "JudgeExecution", "ResolvedArtifact", "TargetExecution",
    "compute_eval_report_hash",
]
