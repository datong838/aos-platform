"""Tenant-scoped, read-only Task Cockpit core projection."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from functools import partial
from typing import Any
from urllib.parse import urlencode

import psycopg

from aos_api.aip_contracts import ResourceRef, StepRunStatus, TaskRunStatus
from aos_api.db import connect
from aos_api.aip_production_contracts import ExactRevisionRef
from aos_api.ecommerce_workshop_task_cockpit_contracts import (
    TASK_COCKPIT_SCHEMA_VERSION,
    TaskCockpitBlocker,
    TaskCockpitBlockerSeverity,
    TaskCockpitCheckpointPageEnvelope,
    TaskCockpitCheckpointSummary,
    TaskCockpitCoreEnvelope,
    TaskCockpitActionApproval,
    TaskCockpitApprovalDecision,
    TaskCockpitApprovalNavigationTarget,
    TaskCockpitApprovalReviewEnvelope,
    TaskCockpitActionExecution,
    TaskCockpitActionReceipt,
    TaskCockpitActionReceiptEnvelope,
    TaskCockpitAssigneeResolutionReceipt,
    TaskCockpitPageInfo,
    TaskCockpitPlanApproval,
    TaskCockpitProductionContextEnvelope,
    TaskCockpitResponsibilityHandoffEnvelope,
    TaskCockpitResponsibilitySlot,
    TaskCockpitStructuralAssignee,
    TaskCockpitHandoffDecision,
    TaskCockpitHandoffSummary,
    TaskCockpitReadiness,
    TaskCockpitReviewIssue,
    TaskCockpitReviewIssueEvent,
    TaskCockpitReviewReturnLineage,
    TaskCockpitRunSummary,
    TaskCockpitSkillContribution,
    TaskCockpitSkillContributionEnvelope,
    TaskCockpitSkillContributionReadiness,
    TaskCockpitSkillRunProjection,
    TaskCockpitStateConsistency,
    TaskCockpitStepPageEnvelope,
    TaskCockpitStageCompilationItem,
    TaskCockpitStepSummary,
    TaskCockpitTaskSummary,
)
from aos_api.errors import ApiError
from aos_api.public_contracts import TaskStatus
from aos_api.tenant_scope import TenantScope, apply_transaction_scope

ConnectFactory = Callable[[], AbstractContextManager[Any]]
Clock = Callable[[], datetime]

_CURSOR_VERSION = 1
_BUSINESS_TASK_SQL = "t.task_type NOT LIKE 'aip.%%' AND t.task_type <> 'logic_graph_run'"
_BLOCKERS = (
    TaskCockpitBlocker(
        code="TASK_COCKPIT_STAGE_MAPPING_RUN_SCOPED",
        severity=TaskCockpitBlockerSeverity.WARNING,
        dependency="aip.production.stage-compilation",
        requiredAction=(
            "展开具备 canonical productionContract 的 Run 读取 exact Stage mapping；"
            "缺失或漂移时保持失败关闭"
        ),
    ),
    TaskCockpitBlocker(
        code="TASK_COCKPIT_BUSINESS_CONTEXT_INDEPENDENT_SNAPSHOT",
        severity=TaskCockpitBlockerSeverity.WARNING,
        dependency="business-context:ecommerce.source-readiness",
        requiredAction=(
            "由 Shell 单次读取 canonical SourceReadinessEnvelope 并按其独立 cutoff 展示；"
            "禁止与 Task cutoff 混算"
        ),
    ),
)


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _checksum(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _format_time(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _parse_time(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("cursor timestamp must be a string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() is None:
        raise ValueError("cursor timestamp requires a timezone")
    return parsed.astimezone(UTC)


def _encode_cursor(
    *,
    scope: TenantScope,
    status: TaskStatus | None,
    cutoff: datetime,
    snapshot_hash: str,
    last_created_at: datetime,
    last_task_id: str,
) -> str:
    body = {
        "v": _CURSOR_VERSION,
        "orgId": scope.org_id,
        "projectId": scope.project_id,
        "status": status.value if status is not None else None,
        "cutoff": _format_time(cutoff),
        "snapshotHash": snapshot_hash,
        "lastCreatedAt": _format_time(last_created_at),
        "lastTaskId": last_task_id,
    }
    payload = {**body, "checksum": _checksum(body)}
    return base64.urlsafe_b64encode(_canonical_json(payload).encode("utf-8")).decode(
        "ascii"
    ).rstrip("=")


def _decode_cursor(
    value: str,
    *,
    scope: TenantScope,
    status: TaskStatus | None,
) -> tuple[datetime, str, datetime, str]:
    invalid = ApiError(
        code="TASK_COCKPIT_CURSOR_INVALID",
        message="Task Cockpit cursor is invalid or does not match this query",
        status_code=400,
    )
    try:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("cursor body must be an object")
        checksum = payload.pop("checksum")
        expected_keys = {
            "v",
            "orgId",
            "projectId",
            "status",
            "cutoff",
            "snapshotHash",
            "lastCreatedAt",
            "lastTaskId",
        }
        valid = (
            set(payload) == expected_keys
            and payload["v"] == _CURSOR_VERSION
            and payload["orgId"] == scope.org_id
            and payload["projectId"] == scope.project_id
            and payload["status"] == (status.value if status is not None else None)
            and isinstance(payload["snapshotHash"], str)
            and len(payload["snapshotHash"]) == 32
            and isinstance(payload["lastTaskId"], str)
            and bool(payload["lastTaskId"])
            and checksum == _checksum(payload)
        )
        if not valid:
            raise ValueError("cursor identity or checksum mismatch")
        cutoff = _parse_time(payload["cutoff"])
        last_created_at = _parse_time(payload["lastCreatedAt"])
        if last_created_at > cutoff:
            raise ValueError("cursor boundary exceeds cutoff")
        return cutoff, payload["snapshotHash"], last_created_at, payload["lastTaskId"]
    except (
        binascii.Error,
        ValueError,
        TypeError,
        KeyError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ):
        raise invalid from None


def _encode_step_cursor(
    *,
    scope: TenantScope,
    run_id: str,
    cutoff: datetime,
    snapshot_hash: str,
    last_created_at: datetime,
    last_step_run_id: str,
) -> str:
    body = {
        "v": _CURSOR_VERSION,
        "kind": "step",
        "orgId": scope.org_id,
        "projectId": scope.project_id,
        "runId": run_id,
        "cutoff": _format_time(cutoff),
        "snapshotHash": snapshot_hash,
        "lastCreatedAt": _format_time(last_created_at),
        "lastId": last_step_run_id,
    }
    payload = {**body, "checksum": _checksum(body)}
    return base64.urlsafe_b64encode(_canonical_json(payload).encode("utf-8")).decode(
        "ascii"
    ).rstrip("=")


def _encode_checkpoint_cursor(
    *,
    scope: TenantScope,
    run_id: str,
    cutoff: datetime,
    snapshot_hash: str,
    last_sequence: int,
    last_checkpoint_id: str,
) -> str:
    body = {
        "v": _CURSOR_VERSION,
        "kind": "checkpoint",
        "orgId": scope.org_id,
        "projectId": scope.project_id,
        "runId": run_id,
        "cutoff": _format_time(cutoff),
        "snapshotHash": snapshot_hash,
        "lastSequence": last_sequence,
        "lastId": last_checkpoint_id,
    }
    payload = {**body, "checksum": _checksum(body)}
    return base64.urlsafe_b64encode(_canonical_json(payload).encode("utf-8")).decode(
        "ascii"
    ).rstrip("=")


def _decode_detail_cursor(
    value: str,
    *,
    scope: TenantScope,
    run_id: str,
    kind: str,
) -> dict[str, Any]:
    invalid = ApiError(
        code="TASK_COCKPIT_CURSOR_INVALID",
        message="Task Cockpit cursor is invalid or does not match this query",
        status_code=400,
    )
    try:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("cursor body must be an object")
        checksum = payload.pop("checksum")
        common = {
            "v",
            "kind",
            "orgId",
            "projectId",
            "runId",
            "cutoff",
            "lastId",
        }
        expected = common | (
            {"snapshotHash", "lastCreatedAt"}
            if kind == "step"
            else {"snapshotHash", "lastSequence"}
        )
        valid = (
            kind in {"step", "checkpoint"}
            and set(payload) == expected
            and payload["v"] == _CURSOR_VERSION
            and payload["kind"] == kind
            and payload["orgId"] == scope.org_id
            and payload["projectId"] == scope.project_id
            and payload["runId"] == run_id
            and isinstance(payload["lastId"], str)
            and bool(payload["lastId"])
            and checksum == _checksum(payload)
        )
        if not valid:
            raise ValueError("cursor identity or checksum mismatch")
        payload["cutoff"] = _parse_time(payload["cutoff"])
        if kind == "step":
            if not isinstance(payload["snapshotHash"], str) or len(
                payload["snapshotHash"]
            ) != 32:
                raise ValueError("step snapshot hash is invalid")
            payload["lastCreatedAt"] = _parse_time(payload["lastCreatedAt"])
            if payload["lastCreatedAt"] > payload["cutoff"]:
                raise ValueError("cursor boundary exceeds cutoff")
        else:
            if not isinstance(payload["snapshotHash"], str) or len(
                payload["snapshotHash"]
            ) != 32:
                raise ValueError("checkpoint snapshot hash is invalid")
            if not isinstance(payload["lastSequence"], int) or payload[
                "lastSequence"
            ] < 1:
                raise ValueError("checkpoint sequence is invalid")
        return payload
    except (
        binascii.Error,
        ValueError,
        TypeError,
        KeyError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ):
        raise invalid from None


class TaskCockpitPersistenceError(RuntimeError):
    pass


class EcommerceWorkshopTaskCockpit:
    """Read canonical AIP Task/Run rows without creating a second authority."""

    def __init__(
        self,
        *,
        connect_factory: ConnectFactory | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._connect_factory = connect_factory or partial(connect, inherit_scope=False)
        self._clock = clock or (lambda: datetime.now(UTC))

    def read_core(
        self,
        *,
        org_id: str,
        project_id: str,
        status: TaskStatus | None,
        limit: int,
        cursor: str | None,
    ) -> TaskCockpitCoreEnvelope:
        scope = TenantScope(org_id, project_id)
        if not 1 <= limit <= 100:
            raise ApiError(
                code="VALIDATION",
                message="Task Cockpit limit must be between 1 and 100",
                status_code=400,
            )
        evaluated_at = self._aware_now()
        if cursor is None:
            cutoff = evaluated_at
            expected_snapshot_hash = None
            boundary: tuple[datetime, str] | None = None
        else:
            cutoff, expected_snapshot_hash, last_created_at, last_task_id = (
                _decode_cursor(cursor, scope=scope, status=status)
            )
            boundary = (last_created_at, last_task_id)

        try:
            with self._connect_factory() as conn:
                conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                apply_transaction_scope(conn, scope)
                snapshot_hash = self._read_core_snapshot_hash(
                    conn, scope=scope, status=status, cutoff=cutoff
                )
                self._require_current_snapshot(
                    expected=expected_snapshot_hash, actual=snapshot_hash
                )
                rows = self._read_rows(
                    conn,
                    scope=scope,
                    status=status,
                    cutoff=cutoff,
                    boundary=boundary,
                    limit=limit,
                )
        except ApiError:
            raise
        except (psycopg.Error, KeyError, TypeError, ValueError) as exc:
            raise TaskCockpitPersistenceError(
                "failed to read Task Cockpit core projection"
            ) from exc

        has_more = len(rows) > limit
        visible = rows[:limit]
        items = [self._task_summary(row) for row in visible]
        next_cursor = None
        if has_more and visible:
            last = visible[-1]
            next_cursor = _encode_cursor(
                scope=scope,
                status=status,
                cutoff=cutoff,
                snapshot_hash=snapshot_hash,
                last_created_at=last["task_created_at"],
                last_task_id=str(last["task_id"]),
            )
        return TaskCockpitCoreEnvelope(
            schemaVersion=TASK_COCKPIT_SCHEMA_VERSION,
            tenant={"orgId": scope.org_id, "projectId": scope.project_id},
            evaluatedAt=evaluated_at,
            taskCutoff=cutoff,
            stateConsistency=TaskCockpitStateConsistency.CURRENT_STATE_PER_PAGE,
            readiness=TaskCockpitReadiness.DEGRADED,
            blockers=list(_BLOCKERS),
            items=items,
            page=TaskCockpitPageInfo(
                limit=limit,
                count=len(items),
                hasMore=has_more,
                nextCursor=next_cursor,
            ),
        )

    def read_steps(
        self,
        *,
        org_id: str,
        project_id: str,
        run_id: str,
        limit: int,
        cursor: str | None,
    ) -> TaskCockpitStepPageEnvelope:
        scope = TenantScope(org_id, project_id)
        self._validate_detail_request(run_id=run_id, limit=limit)
        evaluated_at = self._aware_now()
        if cursor is None:
            cutoff = evaluated_at
            expected_snapshot_hash = None
            boundary: tuple[datetime, str] | None = None
        else:
            decoded = _decode_detail_cursor(
                cursor, scope=scope, run_id=run_id, kind="step"
            )
            cutoff = decoded["cutoff"]
            expected_snapshot_hash = decoded["snapshotHash"]
            boundary = (decoded["lastCreatedAt"], decoded["lastId"])

        try:
            with self._connect_factory() as conn:
                conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                apply_transaction_scope(conn, scope)
                self._require_run(conn, scope=scope, run_id=run_id)
                snapshot_hash = self._read_step_snapshot_hash(
                    conn, scope=scope, run_id=run_id, cutoff=cutoff
                )
                self._require_current_snapshot(
                    expected=expected_snapshot_hash, actual=snapshot_hash
                )
                rows = self._read_step_rows(
                    conn,
                    scope=scope,
                    run_id=run_id,
                    cutoff=cutoff,
                    boundary=boundary,
                    limit=limit,
                )
        except ApiError:
            raise
        except (psycopg.Error, KeyError, TypeError, ValueError) as exc:
            raise TaskCockpitPersistenceError(
                "failed to read Task Cockpit StepRun projection"
            ) from exc

        has_more = len(rows) > limit
        visible = rows[:limit]
        items = [self._step_summary(row) for row in visible]
        next_cursor = None
        if has_more and visible:
            last = visible[-1]
            next_cursor = _encode_step_cursor(
                scope=scope,
                run_id=run_id,
                cutoff=cutoff,
                snapshot_hash=snapshot_hash,
                last_created_at=last["created_at"],
                last_step_run_id=str(last["step_run_id"]),
            )
        return TaskCockpitStepPageEnvelope(
            tenant={"orgId": scope.org_id, "projectId": scope.project_id},
            runId=run_id,
            evaluatedAt=evaluated_at,
            membershipCutoff=cutoff,
            stateConsistency=TaskCockpitStateConsistency.CURRENT_STATE_PER_PAGE,
            items=items,
            page=TaskCockpitPageInfo(
                limit=limit,
                count=len(items),
                hasMore=has_more,
                nextCursor=next_cursor,
            ),
        )

    def read_checkpoints(
        self,
        *,
        org_id: str,
        project_id: str,
        run_id: str,
        limit: int,
        cursor: str | None,
    ) -> TaskCockpitCheckpointPageEnvelope:
        scope = TenantScope(org_id, project_id)
        self._validate_detail_request(run_id=run_id, limit=limit)
        evaluated_at = self._aware_now()
        if cursor is None:
            cutoff = evaluated_at
            expected_snapshot_hash = None
            boundary: tuple[int, str] | None = None
        else:
            decoded = _decode_detail_cursor(
                cursor, scope=scope, run_id=run_id, kind="checkpoint"
            )
            cutoff = decoded["cutoff"]
            expected_snapshot_hash = decoded["snapshotHash"]
            boundary = (decoded["lastSequence"], decoded["lastId"])

        try:
            with self._connect_factory() as conn:
                conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                apply_transaction_scope(conn, scope)
                self._require_run(conn, scope=scope, run_id=run_id)
                snapshot_hash = self._read_checkpoint_snapshot_hash(
                    conn, scope=scope, run_id=run_id, cutoff=cutoff
                )
                self._require_current_snapshot(
                    expected=expected_snapshot_hash, actual=snapshot_hash
                )
                rows = self._read_checkpoint_rows(
                    conn,
                    scope=scope,
                    run_id=run_id,
                    cutoff=cutoff,
                    boundary=boundary,
                    limit=limit,
                )
        except ApiError:
            raise
        except (psycopg.Error, KeyError, TypeError, ValueError) as exc:
            raise TaskCockpitPersistenceError(
                "failed to read Task Cockpit Checkpoint projection"
            ) from exc

        has_more = len(rows) > limit
        visible = rows[:limit]
        items = [self._checkpoint_summary(row) for row in visible]
        next_cursor = None
        if has_more and visible:
            last = visible[-1]
            next_cursor = _encode_checkpoint_cursor(
                scope=scope,
                run_id=run_id,
                cutoff=cutoff,
                snapshot_hash=snapshot_hash,
                last_sequence=int(last["sequence"]),
                last_checkpoint_id=str(last["checkpoint_id"]),
            )
        return TaskCockpitCheckpointPageEnvelope(
            tenant={"orgId": scope.org_id, "projectId": scope.project_id},
            runId=run_id,
            evaluatedAt=evaluated_at,
            membershipCutoff=cutoff,
            stateConsistency=TaskCockpitStateConsistency.CURRENT_STATE_PER_PAGE,
            items=items,
            page=TaskCockpitPageInfo(
                limit=limit,
                count=len(items),
                hasMore=has_more,
                nextCursor=next_cursor,
            ),
        )

    def read_production_context(
        self,
        *,
        org_id: str,
        project_id: str,
        run_id: str,
    ) -> TaskCockpitProductionContextEnvelope:
        scope = TenantScope(org_id, project_id)
        self._validate_detail_request(run_id=run_id, limit=1)
        evaluated_at = self._aware_now()
        try:
            with self._connect_factory() as conn:
                conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                apply_transaction_scope(conn, scope)
                row = conn.execute(
                    """SELECT run.task_id,run.run_id,run.plan_revision_id,
                              plan.revision AS plan_revision,plan.content_hash AS plan_content_hash,
                              plan.steps,plan.risk
                         FROM aip_task_run run
                         JOIN aip_plan_revision plan
                           ON plan.org_id=run.org_id AND plan.project_id=run.project_id
                          AND plan.plan_revision_id=run.plan_revision_id
                        WHERE run.org_id=%s AND run.project_id=%s AND run.run_id=%s""",
                    (scope.org_id, scope.project_id, run_id),
                ).fetchone()
            if row is None:
                raise ApiError(
                    code="TASK_COCKPIT_RUN_NOT_FOUND",
                    message="Task Cockpit Run was not found",
                    status_code=404,
                )
            return self._production_context(scope=scope, row=row, evaluated_at=evaluated_at)
        except ApiError:
            raise
        except (psycopg.Error, KeyError, TypeError, ValueError) as exc:
            raise TaskCockpitPersistenceError(
                "failed to read Task Cockpit production context"
            ) from exc

    def read_skill_contributions(
        self,
        *,
        org_id: str,
        project_id: str,
        run_id: str,
    ) -> TaskCockpitSkillContributionEnvelope:
        scope = TenantScope(org_id, project_id)
        self._validate_detail_request(run_id=run_id, limit=1)
        evaluated_at = self._aware_now()
        try:
            with self._connect_factory() as conn:
                conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                apply_transaction_scope(conn, scope)
                run_row = self._require_run(conn, scope=scope, run_id=run_id)
                rows = conn.execute(
                    """SELECT agent.agent_run_id,agent.task_id,agent.task_run_id,
                              agent.task_run_ref,agent.instance_id,agent.instance_version,
                              agent.instance_ref,agent.skill_binding_id,agent.skill_ref,
                              agent.logic_ref,agent.input_refs,agent.status AS run_status,
                              agent.version AS run_version,
                              agent.created_at AS run_created_at,
                              agent.updated_at AS run_updated_at,
                              binding.skill_id,binding.skill_revision,
                              binding.status AS binding_status,binding.version AS binding_version,
                              binding.readiness,binding.readiness_reasons,
                              binding.last_evaluated_at,binding.readiness_expires_at,
                              skill.content_hash AS skill_content_hash,
                              skill.canonical_logic_id,skill.logic_revision_ref,
                              instance.template_id,instance.template_revision,
                              template.content_hash AS template_content_hash,
                              template.display_name AS role_display_name,
                              template.role_key
                         FROM aip_agent_run agent
                         LEFT JOIN aip_skill_binding binding
                           ON binding.org_id=agent.org_id
                          AND binding.project_id=agent.project_id
                          AND binding.binding_id=agent.skill_binding_id
                         LEFT JOIN aip_skill_template_revision skill
                           ON skill.skill_id=binding.skill_id
                          AND skill.revision=binding.skill_revision
                         LEFT JOIN aip_agent_instance instance
                           ON instance.org_id=agent.org_id
                          AND instance.project_id=agent.project_id
                          AND instance.instance_id=agent.instance_id
                         LEFT JOIN aip_agent_template_revision template
                           ON template.template_id=instance.template_id
                          AND template.revision=instance.template_revision
                        WHERE agent.org_id=%s AND agent.project_id=%s
                          AND agent.task_run_id=%s
                        ORDER BY agent.created_at ASC,agent.agent_run_id ASC""",
                    (*scope.key, run_id),
                ).fetchall()
                agent_run_ids = [str(row["agent_run_id"]) for row in rows]
                attempt_rows = (
                    conn.execute(
                        """SELECT agent_run_id,output_artifact_ref
                             FROM aip_agent_run_execution_attempt
                            WHERE org_id=%s AND project_id=%s
                              AND agent_run_id=ANY(%s)
                              AND output_artifact_ref IS NOT NULL
                            ORDER BY agent_run_id ASC,attempt ASC""",
                        (*scope.key, agent_run_ids),
                    ).fetchall()
                    if agent_run_ids
                    else []
                )
            outputs: dict[str, list[ResourceRef]] = {}
            for row in attempt_rows:
                outputs.setdefault(str(row["agent_run_id"]), []).append(
                    ResourceRef.model_validate(row["output_artifact_ref"])
                )
            items = [
                self._skill_contribution(
                    row=row,
                    evaluated_at=evaluated_at,
                    outputs=outputs.pop(str(row["agent_run_id"]), []),
                )
                for row in rows
            ]
            if outputs:
                raise self._skill_contribution_drift(
                    "output Artifact references an unknown AgentRun"
                )
            return TaskCockpitSkillContributionEnvelope(
                tenant={"orgId": scope.org_id, "projectId": scope.project_id},
                runId=run_id,
                taskId=str(run_row["task_id"]),
                evaluatedAt=evaluated_at,
                projectionStatus="ready" if items else "blocked",
                blockerCodes=(
                    [] if items else ["NO_CANONICAL_AGENT_RUN_CONTRIBUTION"]
                ),
                items=items,
            )
        except ApiError:
            raise
        except (psycopg.Error, KeyError, TypeError, ValueError) as exc:
            raise TaskCockpitPersistenceError(
                "failed to read Task Cockpit Skill contribution projection"
            ) from exc

    def read_responsibility_handoffs(
        self,
        *,
        org_id: str,
        project_id: str,
        run_id: str,
    ) -> TaskCockpitResponsibilityHandoffEnvelope:
        scope = TenantScope(org_id, project_id)
        self._validate_detail_request(run_id=run_id, limit=1)
        evaluated_at = self._aware_now()
        try:
            with self._connect_factory() as conn:
                conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                apply_transaction_scope(conn, scope)
                run_row = conn.execute(
                    """SELECT run.task_id,run.run_id,run.plan_revision_id,
                              plan.revision AS plan_revision,plan.content_hash AS plan_content_hash,
                              plan.steps,plan.risk
                         FROM aip_task_run run
                         JOIN aip_plan_revision plan
                           ON plan.org_id=run.org_id AND plan.project_id=run.project_id
                          AND plan.plan_revision_id=run.plan_revision_id
                        WHERE run.org_id=%s AND run.project_id=%s AND run.run_id=%s""",
                    (scope.org_id, scope.project_id, run_id),
                ).fetchone()
                if run_row is None:
                    raise ApiError(
                        code="TASK_COCKPIT_RUN_NOT_FOUND",
                        message="Task Cockpit Run was not found",
                        status_code=404,
                    )
                production = self._production_context(
                    scope=scope, row=run_row, evaluated_at=evaluated_at
                )
                responsibility_row = conn.execute(
                    """SELECT plan_id,revision,profile,slots,content_hash,lifecycle
                         FROM aip_responsibility_plan_revision
                        WHERE org_id=%s AND project_id=%s AND plan_id=%s AND revision=%s""",
                    (
                        scope.org_id,
                        scope.project_id,
                        production.responsibility_plan_ref.resource_id,
                        production.responsibility_plan_ref.revision,
                    ),
                ).fetchone()
                raw_slots = (
                    responsibility_row.get("slots", [])
                    if isinstance(responsibility_row, dict)
                    else responsibility_row["slots"] if responsibility_row is not None else []
                )
                subject_ids = [
                    (
                        f"responsibility-plan:{production.responsibility_plan_ref.resource_id}"
                        f"@{production.responsibility_plan_ref.revision}/slot:{item.get('slotId')}"
                    )
                    for item in raw_slots
                    if isinstance(item, dict) and isinstance(item.get("slotId"), str)
                ]
                resolution_rows = (
                    conn.execute(
                        """SELECT receipt_id,subject_id,kind,resource_id,version,status,
                                  blocker_codes,content_hash,selected_assignee,
                                  required_capability_refs,binding_refs,snapshot_hash,
                                  expires_at,created_at
                             FROM aip_assignee_resolution_receipt
                            WHERE org_id=%s AND project_id=%s AND subject_id=ANY(%s)
                            ORDER BY subject_id ASC,created_at ASC,receipt_id ASC""",
                        (scope.org_id, scope.project_id, subject_ids),
                    ).fetchall()
                    if subject_ids
                    else []
                )
                handoff_rows = conn.execute(
                    """SELECT handoff_id,task_ref,task_run_ref,sender_instance_ref,
                              receiver_instance_ref,status,version,expires_at,consumed_at,created_at
                         FROM aip_handoff_envelope
                        WHERE org_id=%s AND project_id=%s AND task_run_id=%s
                        ORDER BY created_at ASC,handoff_id ASC""",
                    (scope.org_id, scope.project_id, run_id),
                ).fetchall()
                decision_rows = conn.execute(
                    """SELECT decision.decision_id,decision.handoff_id,decision.revision,
                              decision.decision,decision.reason_code,decision.gap_codes,
                              decision.content_hash,decision.created_at
                         FROM aip_handoff_decision_revision decision
                         JOIN aip_handoff_envelope envelope
                           ON envelope.org_id=decision.org_id
                          AND envelope.project_id=decision.project_id
                          AND envelope.handoff_id=decision.handoff_id
                        WHERE decision.org_id=%s AND decision.project_id=%s
                          AND envelope.task_run_id=%s
                        ORDER BY decision.handoff_id ASC,decision.revision ASC""",
                    (scope.org_id, scope.project_id, run_id),
                ).fetchall()
            return self._responsibility_handoff_context(
                scope=scope,
                production=production,
                responsibility_row=responsibility_row,
                resolution_rows=resolution_rows,
                handoff_rows=handoff_rows,
                decision_rows=decision_rows,
                evaluated_at=evaluated_at,
            )
        except ApiError:
            raise
        except (psycopg.Error, KeyError, TypeError, ValueError) as exc:
            raise TaskCockpitPersistenceError(
                "failed to read Task Cockpit responsibility and handoffs"
            ) from exc

    def read_approval_review_issues(
        self,
        *,
        org_id: str,
        project_id: str,
        run_id: str,
    ) -> TaskCockpitApprovalReviewEnvelope:
        scope = TenantScope(org_id, project_id)
        self._validate_detail_request(run_id=run_id, limit=1)
        evaluated_at = self._aware_now()
        try:
            with self._connect_factory() as conn:
                conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                apply_transaction_scope(conn, scope)
                run_row = conn.execute(
                    """SELECT run.run_id,run.task_id,run.plan_revision_id,
                              plan.revision AS plan_revision,plan.content_hash AS plan_content_hash,
                              plan.approval_status,plan.approved_by,plan.approved_at
                         FROM aip_task_run run
                         JOIN aip_plan_revision plan
                           ON plan.org_id=run.org_id AND plan.project_id=run.project_id
                          AND plan.plan_revision_id=run.plan_revision_id
                        WHERE run.org_id=%s AND run.project_id=%s AND run.run_id=%s""",
                    (*scope.key, run_id),
                ).fetchone()
                if run_row is None:
                    raise ApiError(
                        code="TASK_COCKPIT_RUN_NOT_FOUND",
                        message="Task Cockpit Run was not found",
                        status_code=404,
                    )
                proposal_rows = conn.execute(
                    """SELECT proposal_id,action_type_id,status,expires_at,version,
                              proposal_hash,created_at
                         FROM aip_action_proposal
                        WHERE org_id=%s AND project_id=%s AND run_id=%s
                        ORDER BY created_at ASC,proposal_id ASC""",
                    (*scope.key, run_id),
                ).fetchall()
                approval_rows = conn.execute(
                    """SELECT approval.approval_event_id,approval.proposal_id,
                              approval.proposal_version,approval.proposal_hash,
                              approval.decision,approval.actor_id,approval.expires_at,
                              approval.created_at
                         FROM aip_action_approval_event approval
                         JOIN aip_action_proposal proposal
                           ON proposal.org_id=approval.org_id
                          AND proposal.project_id=approval.project_id
                          AND proposal.proposal_id=approval.proposal_id
                        WHERE approval.org_id=%s AND approval.project_id=%s
                          AND proposal.run_id=%s
                        ORDER BY approval.proposal_id ASC,approval.created_at ASC,
                                 approval.approval_event_id ASC""",
                    (*scope.key, run_id),
                ).fetchall()
                issue_rows = conn.execute(
                    """SELECT issue.issue_id,issue.rule_ref,issue.severity,
                              issue.artifact_id,issue.artifact_hash,
                              artifact.content_hash AS canonical_artifact_hash,
                              issue.eval_report_id,issue.eval_report_revision,
                              issue.eval_report_hash,issue.evidence_refs,
                              issue.return_stage,issue.status,issue.version,
                              issue.created_at
                         FROM aip_review_issue issue
                         JOIN aip_artifact artifact
                           ON artifact.org_id=issue.org_id
                          AND artifact.project_id=issue.project_id
                          AND artifact.artifact_id=issue.artifact_id
                        WHERE issue.org_id=%s AND issue.project_id=%s
                          AND artifact.run_id=%s
                        ORDER BY issue.created_at ASC,issue.issue_id ASC""",
                    (*scope.key, run_id),
                ).fetchall()
                issue_event_rows = conn.execute(
                    """SELECT event.event_id,event.issue_id,event.sequence,event.event_type,
                              event.issue_version,event.payload_hash,event.payload,
                              event.actor,event.created_at
                         FROM aip_review_issue_event event
                         JOIN aip_review_issue issue
                           ON issue.org_id=event.org_id AND issue.project_id=event.project_id
                          AND issue.issue_id=event.issue_id
                         JOIN aip_artifact artifact
                           ON artifact.org_id=issue.org_id
                          AND artifact.project_id=issue.project_id
                          AND artifact.artifact_id=issue.artifact_id
                        WHERE event.org_id=%s AND event.project_id=%s
                          AND artifact.run_id=%s
                        ORDER BY event.issue_id ASC,event.sequence ASC""",
                    (*scope.key, run_id),
                ).fetchall()
                return_rows = conn.execute(
                    """SELECT decision.decision_id,decision.issue_id,decision.issue_version,
                              decision.run_id,decision.step_key,decision.step_run_id,
                              decision.attempt,decision.decision_hash,
                              decision.impact_decisions,decision.created_at,
                              step.run_id AS step_run_run_id,step.step_key AS step_run_step_key,
                              step.attempt AS step_run_attempt
                         FROM aip_return_decision decision
                         JOIN aip_review_issue issue
                           ON issue.org_id=decision.org_id
                          AND issue.project_id=decision.project_id
                          AND issue.issue_id=decision.issue_id
                         JOIN aip_artifact artifact
                           ON artifact.org_id=issue.org_id
                          AND artifact.project_id=issue.project_id
                          AND artifact.artifact_id=issue.artifact_id
                         JOIN aip_step_run step
                           ON step.org_id=decision.org_id
                          AND step.project_id=decision.project_id
                          AND step.step_run_id=decision.step_run_id
                        WHERE decision.org_id=%s AND decision.project_id=%s
                          AND artifact.run_id=%s
                        ORDER BY decision.issue_id ASC,decision.created_at ASC""",
                    (*scope.key, run_id),
                ).fetchall()
            return self._approval_review_context(
                scope=scope,
                run_row=run_row,
                proposal_rows=proposal_rows,
                approval_rows=approval_rows,
                issue_rows=issue_rows,
                issue_event_rows=issue_event_rows,
                return_rows=return_rows,
                evaluated_at=evaluated_at,
            )
        except ApiError:
            raise
        except (psycopg.Error, KeyError, TypeError, ValueError) as exc:
            raise TaskCockpitPersistenceError(
                "failed to read Task Cockpit approvals and review issues"
            ) from exc

    def read_action_receipts(
        self,
        *,
        org_id: str,
        project_id: str,
        run_id: str,
    ) -> TaskCockpitActionReceiptEnvelope:
        scope = TenantScope(org_id, project_id)
        self._validate_detail_request(run_id=run_id, limit=1)
        evaluated_at = self._aware_now()
        try:
            with self._connect_factory() as conn:
                conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                apply_transaction_scope(conn, scope)
                run_row = conn.execute(
                    """SELECT run_id,task_id FROM aip_task_run
                        WHERE org_id=%s AND project_id=%s AND run_id=%s""",
                    (*scope.key, run_id),
                ).fetchone()
                if run_row is None:
                    raise ApiError(
                        code="TASK_COCKPIT_RUN_NOT_FOUND",
                        message="Task Cockpit Run was not found",
                        status_code=404,
                    )
                proposal_rows = conn.execute(
                    """SELECT proposal_id,task_id,run_id,action_type_id,status,version,
                              proposal_hash,created_at
                         FROM aip_action_proposal
                        WHERE org_id=%s AND project_id=%s AND run_id=%s
                        ORDER BY created_at ASC,proposal_id ASC""",
                    (*scope.key, run_id),
                ).fetchall()
                lease_rows = conn.execute(
                    """SELECT lease.lease_id,lease.proposal_id,lease.proposal_hash,
                              lease.attempt,lease.created_at
                         FROM aip_action_execution_lease lease
                         JOIN aip_action_proposal proposal
                           ON proposal.org_id=lease.org_id
                          AND proposal.project_id=lease.project_id
                          AND proposal.proposal_id=lease.proposal_id
                        WHERE lease.org_id=%s AND lease.project_id=%s
                          AND proposal.run_id=%s
                        ORDER BY lease.proposal_id ASC,lease.attempt ASC""",
                    (*scope.key, run_id),
                ).fetchall()
                receipt_rows = conn.execute(
                    """SELECT receipt.receipt_id,receipt.proposal_id,receipt.lease_id,
                              receipt.status,receipt.provider_request_id,
                              receipt.request_fingerprint,receipt.evidence_refs,
                              receipt.payload,receipt.receipt_kind,
                              receipt.supersedes_receipt_id,receipt.created_at
                         FROM aip_action_receipt receipt
                         JOIN aip_action_proposal proposal
                           ON proposal.org_id=receipt.org_id
                          AND proposal.project_id=receipt.project_id
                          AND proposal.proposal_id=receipt.proposal_id
                        WHERE receipt.org_id=%s AND receipt.project_id=%s
                          AND proposal.run_id=%s
                        ORDER BY receipt.proposal_id ASC,receipt.created_at ASC,
                                 receipt.receipt_id ASC""",
                    (*scope.key, run_id),
                ).fetchall()
            return self._action_receipt_context(
                scope=scope,
                run_row=run_row,
                proposal_rows=proposal_rows,
                lease_rows=lease_rows,
                receipt_rows=receipt_rows,
                evaluated_at=evaluated_at,
            )
        except ApiError:
            raise
        except (psycopg.Error, KeyError, TypeError, ValueError) as exc:
            raise TaskCockpitPersistenceError(
                "failed to read Task Cockpit Action receipts"
            ) from exc

    @staticmethod
    def _validate_detail_request(*, run_id: str, limit: int) -> None:
        if not run_id or run_id != run_id.strip() or len(run_id) > 200:
            raise ApiError(
                code="VALIDATION",
                message="Task Cockpit runId is invalid",
                status_code=400,
            )
        if not 1 <= limit <= 100:
            raise ApiError(
                code="VALIDATION",
                message="Task Cockpit limit must be between 1 and 100",
                status_code=400,
            )

    @staticmethod
    def _require_current_snapshot(*, expected: str | None, actual: str) -> None:
        if expected is not None and expected != actual:
            raise ApiError(
                code="TASK_COCKPIT_CURSOR_STALE",
                message="Task Cockpit data changed; restart pagination",
                status_code=409,
            )

    @staticmethod
    def _read_core_snapshot_hash(
        conn: Any,
        *,
        scope: TenantScope,
        status: TaskStatus | None,
        cutoff: datetime,
    ) -> str:
        status_clause = ""
        params: list[Any] = [cutoff, scope.org_id, scope.project_id, cutoff]
        if status is not None:
            status_clause = "AND t.status=%s"
            params.append(status.value)
        row = conn.execute(
            f"""SELECT md5(COALESCE(string_agg(
                         concat_ws(':',t.task_id,t.version,t.status,
                           COALESCE(run.run_id,''),
                           COALESCE(run.version::text,''),
                           COALESCE(run.status,'')),
                         '|' ORDER BY t.task_id),'EMPTY')) AS snapshot_hash
                  FROM aip_task t
                  LEFT JOIN LATERAL (
                    SELECT r.run_id,r.version,r.status
                      FROM aip_task_run r
                     WHERE r.org_id=t.org_id AND r.project_id=t.project_id
                       AND r.task_id=t.task_id AND r.created_at<=%s
                     ORDER BY r.created_at DESC,r.run_id DESC LIMIT 1
                  ) run ON TRUE
                 WHERE t.org_id=%s AND t.project_id=%s AND t.created_at<=%s
                       AND {_BUSINESS_TASK_SQL}
                       {status_clause}""",
            tuple(params),
        ).fetchone()
        if row is None or not isinstance(row["snapshot_hash"], str):
            raise ValueError("Task Cockpit snapshot hash is unavailable")
        return row["snapshot_hash"]

    @staticmethod
    def _require_run(conn: Any, *, scope: TenantScope, run_id: str) -> Any:
        row = conn.execute(
            """SELECT 1 FROM aip_task_run
                WHERE org_id=%s AND project_id=%s AND run_id=%s""",
            (scope.org_id, scope.project_id, run_id),
        ).fetchone()
        if row is None:
            raise ApiError(
                code="TASK_COCKPIT_RUN_NOT_FOUND",
                message="Task Cockpit Run was not found",
                status_code=404,
            )
        return row

    @staticmethod
    def _read_step_snapshot_hash(
        conn: Any,
        *,
        scope: TenantScope,
        run_id: str,
        cutoff: datetime,
    ) -> str:
        row = conn.execute(
            """SELECT md5(COALESCE(string_agg(
                         concat_ws(':',step_run_id,attempt,status,token_count,cost_amount::text,
                           COALESCE(fence::text,''),COALESCE(assignment_lease_id,''),
                           safe_point::text,reconcile_required::text,updated_at::text),
                         '|' ORDER BY step_run_id),'EMPTY')) AS snapshot_hash
                  FROM aip_step_run
                 WHERE org_id=%s AND project_id=%s AND run_id=%s
                   AND created_at<=%s""",
            (scope.org_id, scope.project_id, run_id, cutoff),
        ).fetchone()
        if row is None or not isinstance(row["snapshot_hash"], str):
            raise ValueError("Task Cockpit StepRun snapshot hash is unavailable")
        return row["snapshot_hash"]

    @staticmethod
    def _read_step_rows(
        conn: Any,
        *,
        scope: TenantScope,
        run_id: str,
        cutoff: datetime,
        boundary: tuple[datetime, str] | None,
        limit: int,
    ) -> list[Any]:
        clauses = [
            "org_id=%s",
            "project_id=%s",
            "run_id=%s",
            "created_at<=%s",
        ]
        params: list[Any] = [scope.org_id, scope.project_id, run_id, cutoff]
        if boundary is not None:
            clauses.append("(created_at,step_run_id)>(%s,%s)")
            params.extend(boundary)
        params.append(limit + 1)
        return conn.execute(
            f"""SELECT step_run_id,step_key,attempt,status,token_count,
                       cost_amount,lease_owner,lease_expires_at,fence,assignment_lease_id,
                       input_hash,provider_request_fingerprint,safe_point,reconcile_required,
                       created_at,updated_at,
                       jsonb_array_length(input_refs)>0 AS has_input_refs,
                       jsonb_array_length(output_refs)>0 AS has_output_refs,
                       COALESCE(jsonb_typeof(error)<>'null',false) AS has_error
                  FROM aip_step_run
                 WHERE {' AND '.join(clauses)}
                 ORDER BY created_at ASC,step_run_id ASC
                 LIMIT %s""",
            tuple(params),
        ).fetchall()

    @staticmethod
    def _read_checkpoint_snapshot_hash(
        conn: Any,
        *,
        scope: TenantScope,
        run_id: str,
        cutoff: datetime,
    ) -> str:
        row = conn.execute(
            """SELECT md5(COALESCE(string_agg(
                         concat_ws(':',checkpoint_id,sequence,schema_version,
                           COALESCE(step_key,''),state_hash,artifact_refs::text,
                           COALESCE(attempt::text,''),COALESCE(input_hash,''),
                           COALESCE(dependency_snapshot_hash,''),
                           created_at::text),
                         '|' ORDER BY checkpoint_id),'EMPTY')) AS snapshot_hash
                  FROM aip_checkpoint
                 WHERE org_id=%s AND project_id=%s AND run_id=%s
                   AND created_at<=%s""",
            (scope.org_id, scope.project_id, run_id, cutoff),
        ).fetchone()
        if row is None or not isinstance(row["snapshot_hash"], str):
            raise ValueError("Task Cockpit Checkpoint snapshot hash is unavailable")
        return row["snapshot_hash"]

    @staticmethod
    def _read_checkpoint_rows(
        conn: Any,
        *,
        scope: TenantScope,
        run_id: str,
        cutoff: datetime,
        boundary: tuple[int, str] | None,
        limit: int,
    ) -> list[Any]:
        clauses = [
            "org_id=%s",
            "project_id=%s",
            "run_id=%s",
            "created_at<=%s",
        ]
        params: list[Any] = [scope.org_id, scope.project_id, run_id, cutoff]
        if boundary is not None:
            clauses.append("(sequence,checkpoint_id)>(%s,%s)")
            params.extend(boundary)
        params.append(limit + 1)
        return conn.execute(
            f"""SELECT checkpoint_id,sequence,schema_version,step_key,state_hash,attempt,
                       plan_revision_id,input_hash,provider_request_fingerprint,
                       dependency_snapshot_hash,
                       jsonb_array_length(artifact_refs) AS artifact_count,created_at
                  FROM aip_checkpoint
                 WHERE {' AND '.join(clauses)}
                 ORDER BY sequence ASC,checkpoint_id ASC
                 LIMIT %s""",
            tuple(params),
        ).fetchall()

    @staticmethod
    def _step_summary(row: Any) -> TaskCockpitStepSummary:
        return TaskCockpitStepSummary(
            stepRunId=str(row["step_run_id"]),
            stepKey=str(row["step_key"]),
            attempt=int(row["attempt"]),
            status=StepRunStatus(str(row["status"])),
            tokenCount=int(row["token_count"]),
            costAmount=row["cost_amount"],
            hasInputRefs=bool(row["has_input_refs"]),
            hasOutputRefs=bool(row["has_output_refs"]),
            hasError=bool(row["has_error"]),
            leaseOwner=row.get("lease_owner"),
            leaseExpiresAt=row.get("lease_expires_at"),
            fence=None if row.get("fence") is None else int(row["fence"]),
            assignmentLeaseId=row.get("assignment_lease_id"),
            inputHash=row.get("input_hash"),
            providerRequestFingerprint=row.get("provider_request_fingerprint"),
            safePoint=bool(row.get("safe_point", False)),
            reconcileRequired=bool(row.get("reconcile_required", False)),
            createdAt=row["created_at"],
            updatedAt=row["updated_at"],
        )

    @staticmethod
    def _checkpoint_summary(row: Any) -> TaskCockpitCheckpointSummary:
        return TaskCockpitCheckpointSummary(
            checkpointId=str(row["checkpoint_id"]),
            sequence=int(row["sequence"]),
            schemaVersion=int(row["schema_version"]),
            stepKey=row["step_key"],
            stateHash=str(row["state_hash"]),
            artifactCount=int(row["artifact_count"]),
            attempt=None if row.get("attempt") is None else int(row["attempt"]),
            planRevisionId=row.get("plan_revision_id"),
            inputHash=row.get("input_hash"),
            providerRequestFingerprint=row.get("provider_request_fingerprint"),
            dependencySnapshotHash=row.get("dependency_snapshot_hash"),
            resumeReadiness=(
                "checkpoint_exact"
                if all(
                    row.get(name) is not None
                    for name in (
                        "attempt",
                        "plan_revision_id",
                        "input_hash",
                        "provider_request_fingerprint",
                        "dependency_snapshot_hash",
                    )
                )
                else "legacy_unverified"
            ),
            createdAt=row["created_at"],
        )

    @staticmethod
    def _skill_contribution_drift(reason: str) -> ApiError:
        return ApiError(
            code="TASK_COCKPIT_SKILL_CONTRIBUTION_DRIFTED",
            message=f"Task Cockpit Skill contribution drifted: {reason}",
            status_code=409,
        )

    @classmethod
    def _skill_contribution(
        cls,
        *,
        row: Any,
        evaluated_at: datetime,
        outputs: list[ResourceRef],
    ) -> TaskCockpitSkillContribution:
        def exact_asset(value: object, expected_type: str) -> ExactRevisionRef:
            if not isinstance(value, dict) or set(value) != {
                "assetType",
                "assetId",
                "revision",
                "contentHash",
            }:
                raise cls._skill_contribution_drift(
                    f"{expected_type} exact reference shape is invalid"
                )
            if value["assetType"] != expected_type:
                raise cls._skill_contribution_drift(
                    f"{expected_type} exact reference kind changed"
                )
            return ExactRevisionRef(
                resourceType=value["assetType"],
                resourceId=value["assetId"],
                revision=value["revision"],
                contentHash=value["contentHash"],
            )

        required = {
            "skill_id",
            "skill_revision",
            "binding_status",
            "binding_version",
            "readiness",
            "readiness_reasons",
            "skill_content_hash",
            "canonical_logic_id",
            "logic_revision_ref",
            "template_id",
            "template_revision",
            "template_content_hash",
            "role_display_name",
            "role_key",
        }
        if any(row.get(key) is None for key in required):
            raise cls._skill_contribution_drift(
                "AgentRun dependency join is incomplete"
            )
        task_run_ref = ResourceRef.model_validate(row["task_run_ref"])
        if (
            task_run_ref.resource_type != "TaskRun"
            or task_run_ref.resource_id != str(row["task_run_id"])
        ):
            raise cls._skill_contribution_drift("TaskRun exact identity changed")
        skill_ref = exact_asset(row["skill_ref"], "SkillTemplate")
        logic_ref = exact_asset(row["logic_ref"], "LogicRevision")
        instance_ref = exact_asset(row["instance_ref"], "AgentInstance")
        canonical_logic_ref = exact_asset(
            row["logic_revision_ref"], "LogicRevision"
        )
        if (
            skill_ref.resource_id != str(row["skill_id"])
            or skill_ref.revision != int(row["skill_revision"])
            or skill_ref.content_hash != str(row["skill_content_hash"])
            or logic_ref != canonical_logic_ref
            or logic_ref.resource_id != str(row["canonical_logic_id"])
            or instance_ref.resource_id != str(row["instance_id"])
            or instance_ref.revision != int(row["instance_version"])
        ):
            raise cls._skill_contribution_drift(
                "AgentRun, Binding, Skill, Logic or AgentInstance exact reference drifted"
            )
        role_ref = ExactRevisionRef(
            resourceType="AgentTemplate",
            resourceId=str(row["template_id"]),
            revision=int(row["template_revision"]),
            contentHash=str(row["template_content_hash"]),
        )
        try:
            input_refs = [ResourceRef.model_validate(value) for value in row["input_refs"]]
            reason_codes = [str(value) for value in row["readiness_reasons"]]
        except (TypeError, ValueError) as exc:
            raise cls._skill_contribution_drift(
                "AgentRun input or Binding readiness shape is invalid"
            ) from exc
        last_verified_at = row["last_evaluated_at"]
        expires_at = row["readiness_expires_at"]
        if last_verified_at is None or expires_at is None:
            freshness = "unverified"
            status = "unknown"
            reason_codes.append("SKILL_BINDING_FRESHNESS_UNVERIFIED")
        elif expires_at <= evaluated_at:
            freshness = "stale"
            status = "stale"
            reason_codes.append("SKILL_BINDING_READINESS_STALE")
        else:
            freshness = "fresh"
            status = str(row["readiness"])
        if row["binding_status"] != "active":
            status = "blocked" if status != "stale" else status
            reason_codes.append("SKILL_BINDING_NOT_ACTIVE")
        reason_codes = list(dict.fromkeys(reason_codes))
        waiting_for = [] if status == "available" else reason_codes
        uncertainties = (
            []
            if freshness == "fresh"
            else ["运行就绪证据缺少新鲜有效期"]
        )
        return TaskCockpitSkillContribution(
            contributionId=str(row["agent_run_id"]),
            taskRunRef=task_run_ref,
            agentRunRef=ResourceRef(
                resourceType="AgentRun",
                resourceId=str(row["agent_run_id"]),
                revision=str(row.get("run_version", 1)),
                authority="aip-agent-run",
            ),
            roleRef=role_ref,
            assigneeRef=instance_ref,
            skillRevisionRef=skill_ref,
            bindingRef=ResourceRef(
                resourceType="SkillBinding",
                resourceId=str(row["skill_binding_id"]),
                revision=str(row["binding_version"]),
                authority="aip-skill-registry",
            ),
            logicRevisionRef=logic_ref,
            displayName=f"{row['role_display_name']} · 专业贡献",
            purpose=f"使用 {skill_ref.resource_id} 完成受控专业步骤",
            responsibility=str(row["role_key"]),
            readiness=TaskCockpitSkillContributionReadiness(
                status=status,
                freshness=freshness,
                reasonCodes=reason_codes,
                bindingStatus=row["binding_status"],
                lastVerifiedAt=last_verified_at,
                expiresAt=expires_at,
            ),
            runProjection=TaskCockpitSkillRunProjection(
                status=row["run_status"],
                startedAt=None,
                updatedAt=row["run_updated_at"],
                waitingFor=waiting_for,
            ),
            inputRefs=input_refs,
            outputArtifactRefs=outputs,
            assumptions=[],
            uncertainties=uncertainties,
            conflicts=[],
            missingInputs=[],
            allowedCommands=[],
        )

    @staticmethod
    def _production_context(
        *,
        scope: TenantScope,
        row: Any,
        evaluated_at: datetime,
    ) -> TaskCockpitProductionContextEnvelope:
        def drift(reason: str) -> ApiError:
            return ApiError(
                code="TASK_COCKPIT_PRODUCTION_CONTEXT_DRIFTED",
                message=f"Task Cockpit production context drifted: {reason}",
                status_code=409,
            )

        risk = row["risk"]
        steps = row["steps"]
        if not isinstance(risk, dict) or set(risk) != {"productionContract"}:
            raise drift("productionContract is unavailable")
        production = risk["productionContract"]
        expected_production_keys = {
            "compilerVersion",
            "stageTemplateRef",
            "responsibilityPlanRef",
            "stageCompilation",
            "productionStartGateRequired",
            "productionStartGateRef",
        }
        if not isinstance(production, dict) or set(production) != expected_production_keys:
            raise drift("productionContract shape is invalid")
        if (
            production["compilerVersion"] != "w2c.v1"
            or production["productionStartGateRequired"] is not True
        ):
            raise drift("compiler or start gate semantics changed")
        if not isinstance(steps, list) or not steps:
            raise drift("canonical Plan steps are unavailable")
        raw_stages = production["stageCompilation"]
        if not isinstance(raw_stages, list) or not raw_stages:
            raise drift("stage compilation is unavailable")
        expected_stage_keys = {
            "stageId",
            "title",
            "dependsOn",
            "applicability",
            "requiredSlotIds",
            "inputSchemaRef",
            "outputSchemaRef",
            "gateRefs",
            "checkpointPolicy",
            "retryPolicy",
            "compensationPolicy",
            "applicabilityResult",
            "evaluatedProfile",
        }
        expected_step_keys = {"stepKey", "title", "inputRefs"}
        if any(not isinstance(item, dict) or set(item) != expected_stage_keys for item in raw_stages):
            raise drift("stage compilation item shape is invalid")
        if any(not isinstance(item, dict) or set(item) != expected_step_keys for item in steps):
            raise drift("canonical Plan step shape is invalid")
        stage_ids = [item["stageId"] for item in raw_stages]
        step_ids = [item["stepKey"] for item in steps]
        if stage_ids != step_ids or any(
            stage["title"] != step["title"]
            for stage, step in zip(raw_stages, steps, strict=True)
        ):
            raise drift("Stage compilation and Plan steps do not match")
        try:
            template_ref = ExactRevisionRef.model_validate(production["stageTemplateRef"])
            responsibility_ref = ExactRevisionRef.model_validate(
                production["responsibilityPlanRef"]
            )
            stages = [
                TaskCockpitStageCompilationItem(
                    stageId=item["stageId"],
                    title=item["title"],
                    dependsOn=item["dependsOn"],
                    requiredSlotIds=item["requiredSlotIds"],
                    applicabilityResult=item["applicabilityResult"],
                    evaluatedProfile=item["evaluatedProfile"],
                )
                for item in raw_stages
            ]
        except (TypeError, ValueError) as exc:
            raise drift("exact refs or stage values are invalid") from exc
        applicable = [item.stage_id for item in stages if item.applicability_result == "applicable"]
        not_applicable = [
            item.stage_id for item in stages if item.applicability_result == "not_applicable"
        ]
        try:
            return TaskCockpitProductionContextEnvelope(
                tenant={"orgId": scope.org_id, "projectId": scope.project_id},
                runId=str(row["run_id"]),
                taskId=str(row["task_id"]),
                evaluatedAt=evaluated_at,
                planRef={
                    "resourceType": "PlanRevision",
                    "resourceId": str(row["plan_revision_id"]),
                    "revision": int(row["plan_revision"]),
                    "contentHash": str(row["plan_content_hash"]),
                },
                stageTemplateRef=template_ref,
                responsibilityPlanRef=responsibility_ref,
                compilerVersion="w2c.v1",
                stages=stages,
                applicableStageIds=applicable,
                notApplicableStageIds=not_applicable,
            )
        except (TypeError, ValueError) as exc:
            raise drift("production context envelope is invalid") from exc

    @staticmethod
    def _responsibility_handoff_context(
        *,
        scope: TenantScope,
        production: TaskCockpitProductionContextEnvelope,
        responsibility_row: Any,
        resolution_rows: list[Any],
        handoff_rows: list[Any],
        decision_rows: list[Any],
        evaluated_at: datetime,
    ) -> TaskCockpitResponsibilityHandoffEnvelope:
        def drift(reason: str) -> ApiError:
            return ApiError(
                code="TASK_COCKPIT_RESPONSIBILITY_HANDOFF_DRIFTED",
                message=f"Task Cockpit responsibility or handoff drifted: {reason}",
                status_code=409,
            )

        ref = production.responsibility_plan_ref
        if responsibility_row is None:
            raise drift("responsibility plan is unavailable")
        if (
            str(responsibility_row["plan_id"]) != ref.resource_id
            or int(responsibility_row["revision"]) != ref.revision
            or str(responsibility_row["content_hash"]) != ref.content_hash
            or responsibility_row["lifecycle"] != "frozen"
        ):
            raise drift("responsibility plan exact revision is not frozen")
        raw_slots = responsibility_row["slots"]
        expected_slot_keys = {
            "slotId",
            "responsibilityType",
            "requiredCapabilityIds",
            "inputSchemaRef",
            "outputSchemaRef",
            "gateRefs",
            "returnStage",
            "assignee",
        }
        expected_assignee_keys = {"kind", "resourceId", "version"}
        if not isinstance(raw_slots, list) or not raw_slots:
            raise drift("responsibility slots are unavailable")
        if any(
            not isinstance(item, dict)
            or set(item) != expected_slot_keys
            or not isinstance(item.get("assignee"), dict)
            or set(item["assignee"]) != expected_assignee_keys
            for item in raw_slots
        ):
            raise drift("responsibility slot shape is invalid")
        required_slot_ids = list(
            dict.fromkeys(
                slot_id
                for stage in production.stages
                for slot_id in stage.required_slot_ids
            )
        )
        try:
            receipts_by_subject: dict[str, list[TaskCockpitAssigneeResolutionReceipt]] = {}
            for row in resolution_rows:
                selected_assignee = row.get("selected_assignee")
                required_capability_refs = row.get("required_capability_refs") or []
                binding_refs = row.get("binding_refs") or []
                snapshot_hash = row.get("snapshot_hash")
                expires_at = row.get("expires_at")
                exact_selected_assignee = (
                    isinstance(selected_assignee, dict)
                    and selected_assignee.get("kind") == row["kind"]
                    and selected_assignee.get("resourceId") == row["resource_id"]
                    and selected_assignee.get("version") == row["version"]
                )
                snapshot_status = (
                    "blocked"
                    if row["status"] == "blocked" or not exact_selected_assignee
                    else "legacy_unverified"
                    if snapshot_hash is None or expires_at is None
                    else "stale"
                    if expires_at <= evaluated_at
                    else "exact_fresh"
                )
                receipt = TaskCockpitAssigneeResolutionReceipt(
                    receiptId=row["receipt_id"],
                    subjectId=row["subject_id"],
                    kind=row["kind"],
                    resourceId=row["resource_id"],
                    version=row["version"],
                    status=row["status"],
                    blockerCodes=row["blocker_codes"],
                    contentHash=row["content_hash"],
                    snapshotHash=snapshot_hash,
                    expiresAt=expires_at,
                    requiredCapabilityCount=len(required_capability_refs),
                    bindingCount=len(binding_refs),
                    snapshotStatus=snapshot_status,
                    createdAt=row["created_at"],
                )
                receipts_by_subject.setdefault(receipt.subject_id, []).append(receipt)
            slots = [
                TaskCockpitResponsibilitySlot(
                    slotId=item["slotId"],
                    responsibilityType=item["responsibilityType"],
                    requiredCapabilityIds=item["requiredCapabilityIds"],
                    returnStage=item["returnStage"],
                    assignee=TaskCockpitStructuralAssignee(
                        kind=item["assignee"]["kind"],
                        resourceId=item["assignee"]["resourceId"],
                        version=item["assignee"]["version"],
                        operationalReadiness=(
                            "resolved_at_observation"
                            if receipts_by_subject.get(
                                f"responsibility-plan:{ref.resource_id}@{ref.revision}/slot:{item['slotId']}"
                            )
                            and receipts_by_subject[
                                f"responsibility-plan:{ref.resource_id}@{ref.revision}/slot:{item['slotId']}"
                            ][-1].snapshot_status == "exact_fresh"
                            else "blocked_at_observation"
                            if receipts_by_subject.get(
                                f"responsibility-plan:{ref.resource_id}@{ref.revision}/slot:{item['slotId']}"
                            )
                            else "unverified"
                        ),
                        resolutionReceipts=receipts_by_subject.pop(
                            f"responsibility-plan:{ref.resource_id}@{ref.revision}/slot:{item['slotId']}",
                            [],
                        ),
                    ),
                )
                for item in raw_slots
            ]
        except (TypeError, ValueError) as exc:
            raise drift("responsibility slot values are invalid") from exc
        if receipts_by_subject:
            raise drift("assignee resolution references an unknown responsibility slot")

        decisions_by_handoff: dict[str, list[TaskCockpitHandoffDecision]] = {}
        try:
            for row in decision_rows:
                handoff_id = str(row["handoff_id"])
                decisions_by_handoff.setdefault(handoff_id, []).append(
                    TaskCockpitHandoffDecision(
                        decisionId=row["decision_id"],
                        revision=row["revision"],
                        decision=row["decision"],
                        reasonCode=row["reason_code"],
                        gapCodes=row["gap_codes"],
                        contentHash=row["content_hash"],
                        createdAt=row["created_at"],
                    )
                )
            handoffs: list[TaskCockpitHandoffSummary] = []
            for row in handoff_rows:
                task_ref = row["task_ref"]
                run_ref = row["task_run_ref"]
                if (
                    not isinstance(task_ref, dict)
                    or task_ref.get("resourceType") != "Task"
                    or task_ref.get("resourceId") != production.task_id
                    or not isinstance(run_ref, dict)
                    or run_ref.get("resourceType") != "TaskRun"
                    or run_ref.get("resourceId") != production.run_id
                ):
                    raise drift("handoff task or run exact reference changed")
                sender = row["sender_instance_ref"]
                receiver = row["receiver_instance_ref"]
                if not isinstance(sender, dict) or not isinstance(receiver, dict):
                    raise drift("handoff instance exact reference is unavailable")
                handoff_id = str(row["handoff_id"])
                handoffs.append(
                    TaskCockpitHandoffSummary(
                        handoffId=handoff_id,
                        status=row["status"],
                        version=row["version"],
                        senderInstanceRef={
                            "resourceType": sender.get("assetType"),
                            "resourceId": sender.get("assetId"),
                            "revision": sender.get("revision"),
                            "contentHash": sender.get("contentHash"),
                        },
                        receiverInstanceRef={
                            "resourceType": receiver.get("assetType"),
                            "resourceId": receiver.get("assetId"),
                            "revision": receiver.get("revision"),
                            "contentHash": receiver.get("contentHash"),
                        },
                        expiresAt=row["expires_at"],
                        consumedAt=row["consumed_at"],
                        createdAt=row["created_at"],
                        decisions=decisions_by_handoff.pop(handoff_id, []),
                    )
                )
        except ApiError:
            raise
        except (TypeError, ValueError) as exc:
            raise drift("handoff or decision values are invalid") from exc
        if decisions_by_handoff:
            raise drift("handoff decision references an unknown envelope")
        try:
            return TaskCockpitResponsibilityHandoffEnvelope(
                tenant={"orgId": scope.org_id, "projectId": scope.project_id},
                runId=production.run_id,
                taskId=production.task_id,
                evaluatedAt=evaluated_at,
                responsibilityPlanRef=ref,
                profile=responsibility_row["profile"],
                lifecycle=responsibility_row["lifecycle"],
                compilationReadiness="ready_at_compile",
                compiledRequiredSlotIds=required_slot_ids,
                slots=slots,
                handoffs=handoffs,
            )
        except (TypeError, ValueError) as exc:
            raise drift("responsibility or handoff envelope is invalid") from exc

    @staticmethod
    def _approval_review_context(
        *,
        scope: TenantScope,
        run_row: Any,
        proposal_rows: list[Any],
        approval_rows: list[Any],
        issue_rows: list[Any],
        issue_event_rows: list[Any],
        return_rows: list[Any],
        evaluated_at: datetime,
    ) -> TaskCockpitApprovalReviewEnvelope:
        def drift(reason: str) -> ApiError:
            return ApiError(
                code="TASK_COCKPIT_APPROVAL_REVIEW_DRIFTED",
                message=f"Task Cockpit approval or ReviewIssue drifted: {reason}",
                status_code=409,
            )

        task_id = str(run_row["task_id"])
        run_id = str(run_row["run_id"])
        plan_ref = ExactRevisionRef(
            resourceType="PlanRevision",
            resourceId=str(run_row["plan_revision_id"]),
            revision=int(run_row["plan_revision"]),
            contentHash=str(run_row["plan_content_hash"]),
        )

        def navigation(
            *, route_identity: str, route_path: str, target_ref: ExactRevisionRef,
            readiness: str, permission: str, blockers: list[str],
        ) -> TaskCockpitApprovalNavigationTarget:
            token = _checksum({
                "orgId": scope.org_id,
                "projectId": scope.project_id,
                "runId": run_id,
                "routeIdentity": route_identity,
                "target": target_ref.model_dump(mode="json", by_alias=True),
            })
            return TaskCockpitApprovalNavigationTarget(
                routeIdentity=route_identity,
                routePath=route_path,
                targetRef=target_ref,
                commandReadiness=readiness,
                requiredPermission=permission,
                blockerCodes=blockers,
                returnFocusToken=token,
            )

        try:
            plan_approval = TaskCockpitPlanApproval(
                planRef=plan_ref,
                approvalStatus=run_row["approval_status"],
                approvedBy=run_row["approved_by"],
                approvedAt=run_row["approved_at"],
                navigation=navigation(
                    route_identity="aip.task-plan",
                    route_path="/aip/studio?" + urlencode(
                        {"taskId": task_id, "runId": run_id}
                    ),
                    target_ref=plan_ref,
                    readiness="read_only_fact",
                    permission="aip.task.plan.read",
                    blockers=["RUN_ALREADY_MATERIALIZED_NO_APPROVAL_COMMAND"],
                ),
            )
        except (TypeError, ValueError) as exc:
            raise drift("Plan approval exact reference is invalid") from exc

        approvals_by_proposal: dict[str, list[TaskCockpitApprovalDecision]] = {}
        try:
            for row in approval_rows:
                approvals_by_proposal.setdefault(str(row["proposal_id"]), []).append(
                    TaskCockpitApprovalDecision(
                        approvalEventId=row["approval_event_id"],
                        proposalVersion=row["proposal_version"],
                        proposalHash=row["proposal_hash"],
                        decision=row["decision"],
                        actorId=row["actor_id"],
                        expiresAt=row["expires_at"],
                        createdAt=row["created_at"],
                    )
                )
            action_approvals: list[TaskCockpitActionApproval] = []
            for row in proposal_rows:
                proposal_id = str(row["proposal_id"])
                proposal_ref = ExactRevisionRef(
                    resourceType="ActionProposalRevision",
                    resourceId=proposal_id,
                    revision=int(row["version"]),
                    contentHash=str(row["proposal_hash"]),
                )
                action_approvals.append(
                    TaskCockpitActionApproval(
                        proposalRef=proposal_ref,
                        actionTypeId=row["action_type_id"],
                        status=row["status"],
                        expiresAt=row["expires_at"],
                        decisions=approvals_by_proposal.pop(proposal_id, []),
                        navigation=navigation(
                            route_identity="aip.action-drafts",
                            route_path="/aip/drafts?" + urlencode(
                                {
                                    "taskId": task_id,
                                    "runId": run_id,
                                    "proposalId": proposal_id,
                                }
                            ),
                            target_ref=proposal_ref,
                            readiness="destination_reauthorization_required",
                            permission="aip.action.approval.decide",
                            blockers=["DESTINATION_REAUTHORIZATION_REQUIRED"],
                        ),
                    )
                )
        except (TypeError, ValueError) as exc:
            raise drift("Action approval exact timeline is invalid") from exc
        if approvals_by_proposal:
            raise drift("ApprovalEvent references an unknown run-scoped Proposal")

        events_by_issue: dict[str, list[TaskCockpitReviewIssueEvent]] = {}
        returns_by_issue: dict[str, TaskCockpitReviewReturnLineage] = {}
        try:
            for row in issue_event_rows:
                issue_id = str(row["issue_id"])
                payload = row.get("payload")
                if payload is not None:
                    payload_hash = hashlib.sha256(
                        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
                    ).hexdigest()
                    if payload_hash != row["payload_hash"]:
                        raise drift("ReviewIssue event payload hash changed")
                events_by_issue.setdefault(issue_id, []).append(
                    TaskCockpitReviewIssueEvent(
                        eventId=row["event_id"], sequence=row["sequence"],
                        eventType=row["event_type"], issueVersion=row["issue_version"],
                        payloadHash=row["payload_hash"], payload=payload,
                        payloadReadiness=("exact" if payload is not None else "legacy_unavailable"),
                        actor=row["actor"],
                        createdAt=row["created_at"],
                    )
                )
            for row in return_rows:
                issue_id = str(row["issue_id"])
                if issue_id in returns_by_issue:
                    raise drift("ReviewIssue has more than one ReturnDecision")
                if (
                    str(row["run_id"]) != run_id
                    or str(row["step_run_run_id"]) != run_id
                    or str(row["step_key"]) != str(row["step_run_step_key"])
                    or int(row["attempt"]) != int(row["step_run_attempt"])
                ):
                    raise drift("ReturnDecision StepRun exact lineage changed")
                returns_by_issue[issue_id] = TaskCockpitReviewReturnLineage(
                    decisionId=row["decision_id"], issueVersion=row["issue_version"],
                    runId=row["run_id"], stepKey=row["step_key"],
                    stepRunId=row["step_run_id"], attempt=row["attempt"],
                    decisionHash=row["decision_hash"],
                    impactDecisions=row.get("impact_decisions") or [],
                    impactReadiness=("exact" if row.get("impact_decisions") else "legacy_unavailable"),
                    createdAt=row["created_at"],
                )
            review_issues: list[TaskCockpitReviewIssue] = []
            for row in issue_rows:
                issue_id = str(row["issue_id"])
                if row["artifact_hash"] != row["canonical_artifact_hash"]:
                    raise drift("ReviewIssue Artifact hash changed")
                lineage = returns_by_issue.pop(issue_id, None)
                evidence_refs = row["evidence_refs"]
                if not isinstance(evidence_refs, list):
                    raise drift("ReviewIssue evidenceRefs shape changed")
                review_issues.append(
                    TaskCockpitReviewIssue(
                        issueId=issue_id, version=row["version"], status=row["status"],
                        severity=row["severity"], ruleRef=row["rule_ref"],
                        artifactId=row["artifact_id"], artifactHash=row["artifact_hash"],
                        evalReportRef={
                            "resourceType": "EvalReportRevision",
                            "resourceId": row["eval_report_id"],
                            "revision": row["eval_report_revision"],
                            "contentHash": row["eval_report_hash"],
                        },
                        returnStage=row["return_stage"], evidenceCount=len(evidence_refs),
                        lineageReadiness=("attempt_exact" if lineage else "attempt_unresolved"),
                        returnLineage=lineage,
                        events=events_by_issue.pop(issue_id, []),
                    )
                )
        except ApiError:
            raise
        except (TypeError, ValueError) as exc:
            raise drift("ReviewIssue exact timeline is invalid") from exc
        if events_by_issue or returns_by_issue:
            raise drift("ReviewIssue event or ReturnDecision references an unknown issue")
        try:
            return TaskCockpitApprovalReviewEnvelope(
                tenant={"orgId": scope.org_id, "projectId": scope.project_id},
                runId=run_id, taskId=task_id, evaluatedAt=evaluated_at,
                planApproval=plan_approval, actionApprovals=action_approvals,
                reviewIssues=review_issues,
                actionApprovalCount=len(action_approvals),
                reviewIssueCount=len(review_issues),
                unresolvedAttemptCount=sum(
                    item.lineage_readiness == "attempt_unresolved" for item in review_issues
                ),
            )
        except (TypeError, ValueError) as exc:
            raise drift("approval and ReviewIssue envelope is invalid") from exc

    @staticmethod
    def _action_receipt_context(
        *,
        scope: TenantScope,
        run_row: Any,
        proposal_rows: list[Any],
        lease_rows: list[Any],
        receipt_rows: list[Any],
        evaluated_at: datetime,
    ) -> TaskCockpitActionReceiptEnvelope:
        def drift(reason: str) -> ApiError:
            return ApiError(
                code="TASK_COCKPIT_ACTION_RECEIPT_DRIFTED",
                message=f"Task Cockpit Action receipt drifted: {reason}",
                status_code=409,
            )

        run_id = str(run_row["run_id"])
        task_id = str(run_row["task_id"])
        proposals = {str(row["proposal_id"]): row for row in proposal_rows}
        if len(proposals) != len(proposal_rows):
            raise drift("duplicate ActionProposal identity")
        if any(
            str(row["run_id"]) != run_id or str(row["task_id"]) != task_id
            for row in proposal_rows
        ):
            raise drift("ActionProposal Task or Run scope changed")

        leases: dict[str, Any] = {}
        for row in lease_rows:
            proposal_id = str(row["proposal_id"])
            proposal = proposals.get(proposal_id)
            if proposal is None:
                raise drift("ExecutionLease references an unknown run-scoped Proposal")
            if proposal_id in leases or int(row["attempt"]) != 1:
                raise drift("ActionProposal has a non-canonical execution attempt")
            if str(row["proposal_hash"]) != str(proposal["proposal_hash"]):
                raise drift("ExecutionLease proposal hash changed")
            leases[proposal_id] = row

        receipts_by_proposal: dict[str, list[Any]] = {}
        for row in receipt_rows:
            proposal_id = str(row["proposal_id"])
            lease = leases.get(proposal_id)
            if lease is None or str(row["lease_id"]) != str(lease["lease_id"]):
                raise drift("ActionReceipt lease or Proposal reference changed")
            evidence_refs = row["evidence_refs"]
            if not isinstance(evidence_refs, list):
                raise drift("ActionReceipt evidenceRefs shape changed")
            receipts_by_proposal.setdefault(proposal_id, []).append(row)

        executions: list[TaskCockpitActionExecution] = []
        try:
            for proposal_id, proposal in proposals.items():
                lease = leases.get(proposal_id)
                raw_receipts = receipts_by_proposal.pop(proposal_id, [])
                initial = [row for row in raw_receipts if row["receipt_kind"] == "initial"]
                reconciles = [row for row in raw_receipts if row["receipt_kind"] == "reconcile"]
                if len(initial) > 1 or len(reconciles) > 1:
                    raise drift("ActionReceipt chain cardinality changed")
                if reconciles:
                    first = initial[0] if initial else None
                    latest = reconciles[0]
                    if (
                        first is None
                        or first["status"] != "unknown"
                        or latest["supersedes_receipt_id"] != first["receipt_id"]
                        or latest["lease_id"] != first["lease_id"]
                        or latest["request_fingerprint"] != first["request_fingerprint"]
                        or latest["provider_request_id"] != first["provider_request_id"]
                    ):
                        raise drift("Action reconcile chain changed")
                mapped_receipts: list[TaskCockpitActionReceipt] = []
                for row in raw_receipts:
                    payload = row["payload"]
                    if not isinstance(payload, dict):
                        raise drift("ActionReceipt payload shape changed")
                    resolved_status = (
                        payload.get("resolvedStatus")
                        if row["receipt_kind"] == "reconcile"
                        else None
                    )
                    mapped_receipts.append(TaskCockpitActionReceipt(
                        receiptId=row["receipt_id"], receiptKind=row["receipt_kind"],
                        status=row["status"], leaseId=row["lease_id"],
                        requestFingerprint=row["request_fingerprint"],
                        providerRequestPresent=row["provider_request_id"] is not None,
                        evidenceCount=len(row["evidence_refs"]),
                        supersedesReceiptId=row["supersedes_receipt_id"],
                        resolvedStatus=resolved_status, createdAt=row["created_at"],
                    ))
                reconciliation_state = "not_started"
                if initial:
                    reconciliation_state = (
                        "not_required" if initial[0]["status"] != "unknown"
                        else "resolved" if reconciles else "required"
                    )
                executions.append(TaskCockpitActionExecution(
                    proposalRef={
                        "resourceType": "ActionProposalRevision",
                        "resourceId": proposal_id,
                        "revision": proposal["version"],
                        "contentHash": proposal["proposal_hash"],
                    },
                    actionTypeId=proposal["action_type_id"],
                    proposalStatus=proposal["status"],
                    leaseId=None if lease is None else lease["lease_id"],
                    attempt=None if lease is None else lease["attempt"],
                    receipts=mapped_receipts,
                    reconciliationState=reconciliation_state,
                ))
        except ApiError:
            raise
        except (TypeError, ValueError) as exc:
            raise drift("Action receipt envelope values are invalid") from exc
        if receipts_by_proposal:
            raise drift("ActionReceipt references an unknown run-scoped Proposal")
        receipts = [receipt for item in executions for receipt in item.receipts]
        try:
            return TaskCockpitActionReceiptEnvelope(
                tenant={"orgId": scope.org_id, "projectId": scope.project_id},
                runId=run_id, taskId=task_id, evaluatedAt=evaluated_at,
                executions=executions, proposalCount=len(executions),
                receiptCount=len(receipts),
                unknownReceiptCount=sum(
                    item.receipt_kind == "initial" and item.status == "unknown"
                    for item in receipts
                ),
                reconcileRequiredCount=sum(
                    item.reconciliation_state == "required" for item in executions
                ),
                reconciledReceiptCount=sum(
                    item.receipt_kind == "reconcile" for item in receipts
                ),
            )
        except (TypeError, ValueError) as exc:
            raise drift("Action receipt envelope is invalid") from exc

    @staticmethod
    def _read_rows(
        conn: Any,
        *,
        scope: TenantScope,
        status: TaskStatus | None,
        cutoff: datetime,
        boundary: tuple[datetime, str] | None,
        limit: int,
    ) -> list[Any]:
        clauses = [
            "t.org_id=%s",
            "t.project_id=%s",
            "t.created_at<=%s",
            _BUSINESS_TASK_SQL,
        ]
        params: list[Any] = [cutoff, scope.org_id, scope.project_id, cutoff]
        if status is not None:
            clauses.append("t.status=%s")
            params.append(status.value)
        if boundary is not None:
            clauses.append("(t.created_at,t.task_id)<(%s,%s)")
            params.extend(boundary)
        params.append(limit + 1)
        return conn.execute(
            f"""SELECT t.task_id,t.task_type,t.title,t.status AS task_status,
                       t.priority,t.version AS task_version,
                       t.current_plan_revision_id,t.created_at AS task_created_at,
                       t.updated_at AS task_updated_at,
                       run.run_id,run.plan_revision_id,run.status AS run_status,
                       run.version AS run_version,run.started_at,run.finished_at,
                       run.created_at AS run_created_at,
                       run.updated_at AS run_updated_at
                  FROM aip_task t
                  LEFT JOIN LATERAL (
                    SELECT r.run_id,r.plan_revision_id,r.status,r.version,
                           r.started_at,r.finished_at,r.created_at,r.updated_at
                      FROM aip_task_run r
                     WHERE r.org_id=t.org_id AND r.project_id=t.project_id
                       AND r.task_id=t.task_id
                       AND r.created_at<=%s
                     ORDER BY r.created_at DESC,r.run_id DESC
                     LIMIT 1
                  ) run ON TRUE
                 WHERE {' AND '.join(clauses)}
                 ORDER BY t.created_at DESC,t.task_id DESC
                 LIMIT %s""",
            tuple(params),
        ).fetchall()

    @staticmethod
    def _task_summary(row: Any) -> TaskCockpitTaskSummary:
        run = None
        if row["run_id"] is not None:
            run = TaskCockpitRunSummary(
                runId=str(row["run_id"]),
                planRevisionId=str(row["plan_revision_id"]),
                status=TaskRunStatus(str(row["run_status"])),
                version=int(row["run_version"]),
                startedAt=row["started_at"],
                finishedAt=row["finished_at"],
                createdAt=row["run_created_at"],
                updatedAt=row["run_updated_at"],
            )
        return TaskCockpitTaskSummary(
            taskId=str(row["task_id"]),
            taskType=str(row["task_type"]),
            title=str(row["title"]),
            status=TaskStatus(str(row["task_status"])),
            priority=int(row["priority"]),
            version=int(row["task_version"]),
            currentPlanRevisionId=row["current_plan_revision_id"],
            createdAt=row["task_created_at"],
            updatedAt=row["task_updated_at"],
            run=run,
        )

    def _aware_now(self) -> datetime:
        value = self._clock()
        if not isinstance(value, datetime) or value.utcoffset() is None:
            raise TaskCockpitPersistenceError("Task Cockpit clock must be timezone aware")
        return value.astimezone(UTC)


__all__ = [
    "EcommerceWorkshopTaskCockpit",
    "TaskCockpitPersistenceError",
    "_decode_cursor",
    "_encode_cursor",
]
