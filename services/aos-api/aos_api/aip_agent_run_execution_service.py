"""PostgreSQL authority for idempotent AgentRun execution attempts."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from aos_api.aip_agent_registry_store import (
    AipAgentRegistryConflict,
    AipAgentRegistryNotFound,
    AipAgentRegistryPersistenceError,
    AipAgentRegistryStore,
    AipAgentRegistryTransitionBlocked,
)
from aos_api.aip_agent_run_execution_contracts import (
    AgentRunExecutionAttempt,
    AgentRunExecutionStatus,
    CreateAgentRunExecutionAttemptRequest,
    TransitionAgentRunExecutionAttemptRequest,
)
from aos_api.aip_contracts import TenantContext
from aos_api.tenant_scope import TenantScope


_TRANSITIONS = {
    AgentRunExecutionStatus.PREPARED: {
        AgentRunExecutionStatus.INVOKING,
        AgentRunExecutionStatus.FAILED,
    },
    AgentRunExecutionStatus.INVOKING: {
        AgentRunExecutionStatus.SUCCEEDED,
        AgentRunExecutionStatus.FAILED,
        AgentRunExecutionStatus.UNKNOWN,
    },
}


class AipAgentRunExecutionService(AipAgentRegistryStore):
    def create(
        self,
        scope: TenantScope,
        request: CreateAgentRunExecutionAttemptRequest,
        *,
        idempotency_key: str,
        actor: str,
        occurred_at: datetime,
    ):
        self._validate_command(scope, idempotency_key, actor)
        operation = "agent_run_execution_attempt.create"
        request_hash = self._command_hash(request, actor)
        try:
            with self._connect_factory(scope) as conn:
                self._lock(conn, scope, operation, idempotency_key)
                replay = self._receipt_row(conn, scope, operation, idempotency_key)
                if replay:
                    self._require_replay_hash(replay, request_hash)
                    return (
                        self._from_row(scope, self._row(conn, scope, replay["result_ref"]["resourceId"])),
                        self._receipt_from_row(scope, replay),
                    )
                run = conn.execute(
                    """SELECT status,version,model_route_ref,policy_ref
                    FROM aip_agent_run WHERE org_id=%s AND project_id=%s
                    AND agent_run_id=%s FOR UPDATE""",
                    (*scope.key, request.agent_run_ref.resource_id),
                ).fetchone()
                if run is None:
                    raise AipAgentRegistryNotFound("agent run not found")
                if str(run["version"]) != request.agent_run_ref.revision:
                    raise AipAgentRegistryConflict("agent run exact revision drifted")
                if run["status"] != "running":
                    raise AipAgentRegistryTransitionBlocked("agent run is not running")
                if run["model_route_ref"] != request.route_ref.model_dump(mode="json", by_alias=True):
                    raise AipAgentRegistryConflict("execution route differs from agent run")
                if run["policy_ref"] != request.policy_ref.model_dump(mode="json", by_alias=True):
                    raise AipAgentRegistryConflict("execution policy differs from agent run")
                reservation = conn.execute(
                    """SELECT r.reservation_id,r.status,r.expires_at,
                    p.route_ref,p.model_ref,p.provider_ref
                    FROM aip_model_capacity_reservation r
                    JOIN aip_model_capacity_pool_revision p
                      ON p.org_id=r.org_id AND p.project_id=r.project_id
                     AND p.pool_id=r.pool_id AND p.revision=r.pool_revision
                    WHERE r.org_id=%s AND r.project_id=%s AND r.reservation_id=%s
                    AND r.agent_run_id=%s""",
                    (*scope.key, request.capacity_reservation_ref.resource_id,
                     request.agent_run_ref.resource_id),
                ).fetchone()
                if reservation is None or reservation["status"] != "reserved":
                    raise AipAgentRegistryTransitionBlocked("active capacity reservation required")
                if reservation["expires_at"] <= occurred_at:
                    raise AipAgentRegistryTransitionBlocked("capacity reservation expired")
                exact_capacity_refs = (
                    (reservation["route_ref"], request.route_ref),
                    (reservation["model_ref"], request.model_ref),
                    (reservation["provider_ref"], request.provider_ref),
                )
                if any(
                    actual != expected.model_dump(mode="json", by_alias=True)
                    for actual, expected in exact_capacity_refs
                ):
                    raise AipAgentRegistryConflict("capacity reservation exact runtime refs drifted")
                price = conn.execute(
                    """SELECT lifecycle,content_hash FROM aip_model_price_snapshot_revision
                    WHERE org_id=%s AND project_id=%s
                    AND model_price_snapshot_id=%s AND revision=%s""",
                    (*scope.key, request.price_snapshot_ref.asset_id,
                     request.price_snapshot_ref.revision),
                ).fetchone()
                if (
                    price is None
                    or price["lifecycle"] != "active"
                    or price["content_hash"] != request.price_snapshot_ref.content_hash
                ):
                    raise AipAgentRegistryTransitionBlocked("active exact price snapshot required")
                budget = conn.execute(
                    """SELECT lifecycle,content_hash,effective_from,effective_until
                    FROM aip_budget_revision WHERE org_id=%s AND project_id=%s
                    AND budget_id=%s AND revision=%s""",
                    (*scope.key, request.budget_ref.asset_id, request.budget_ref.revision),
                ).fetchone()
                if (
                    budget is None
                    or budget["lifecycle"] != "active"
                    or budget["content_hash"] != request.budget_ref.content_hash
                    or budget["effective_from"] > occurred_at
                    or (budget["effective_until"] and budget["effective_until"] <= occurred_at)
                ):
                    raise AipAgentRegistryTransitionBlocked("active exact budget revision required")
                row = conn.execute(
                    """INSERT INTO aip_agent_run_execution_attempt(
                    org_id,project_id,attempt_id,agent_run_id,agent_run_version,attempt_no,
                    idempotency_key,request_hash,route_ref,policy_ref,model_ref,provider_ref,
                    price_snapshot_ref,budget_ref,capacity_reservation_ref,data_classification,
                    lineage_id,status,prepared_at,created_by,updated_at)
                    VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,
                    %s::jsonb,%s::jsonb,%s::jsonb,%s,%s,'prepared',%s,%s,%s) RETURNING *""",
                    (
                        *scope.key,
                        request.attempt_id,
                        request.agent_run_ref.resource_id,
                        int(request.agent_run_ref.revision),
                        request.attempt_no,
                        idempotency_key,
                        request.request_hash,
                        self._json(request.route_ref),
                        self._json(request.policy_ref),
                        self._json(request.model_ref),
                        self._json(request.provider_ref),
                        self._json(request.price_snapshot_ref),
                        self._json(request.budget_ref),
                        self._json(request.capacity_reservation_ref),
                        request.data_classification,
                        request.lineage_id,
                        occurred_at,
                        actor.strip(),
                        occurred_at,
                    ),
                ).fetchone()
                receipt = self._insert_receipt(
                    conn, scope, operation, idempotency_key, request_hash,
                    "AgentRun", request.agent_run_ref.resource_id,
                    "AgentRunExecutionAttempt", request.attempt_id, actor, occurred_at,
                )
                conn.commit()
                return self._from_row(scope, row), receipt
        except (
            AipAgentRegistryConflict,
            AipAgentRegistryNotFound,
            AipAgentRegistryTransitionBlocked,
        ):
            raise
        except Exception as exc:
            raise AipAgentRegistryPersistenceError("agent run execution attempt persistence failed") from exc

    def transition(
        self,
        scope: TenantScope,
        attempt_id: str,
        request: TransitionAgentRunExecutionAttemptRequest,
        *,
        idempotency_key: str,
        actor: str,
        occurred_at: datetime,
    ):
        self._validate_command(scope, idempotency_key, actor)
        if request.to_status not in _TRANSITIONS.get(request.from_status, set()):
            raise AipAgentRegistryTransitionBlocked("execution attempt transition is not allowed")
        operation = f"agent_run_execution_attempt.{request.to_status.value}"
        request_hash = self._hash(
            {
                "actor": actor.strip(),
                "attemptId": attempt_id,
                "request": request.model_dump(mode="json", by_alias=True),
            }
        )
        try:
            with self._connect_factory(scope) as conn:
                self._lock(conn, scope, operation, idempotency_key)
                replay = self._receipt_row(conn, scope, operation, idempotency_key)
                if replay:
                    self._require_replay_hash(replay, request_hash)
                    return (
                        self._from_row(
                            scope,
                            self._row(conn, scope, replay["result_ref"]["resourceId"]),
                        ),
                        self._receipt_from_row(scope, replay),
                    )
                values: dict[str, Any] = {
                    "provider_receipt_id": request.provider_receipt_id,
                    "usage_receipt_ids": self._json(request.usage_receipt_ids),
                    "output_artifact_ref": self._json(request.output_artifact_ref)
                    if request.output_artifact_ref else None,
                    "reason_code": request.reason_code,
                    "invoking_at": occurred_at
                    if request.to_status is AgentRunExecutionStatus.INVOKING else None,
                    "completed_at": occurred_at
                    if request.to_status in {
                        AgentRunExecutionStatus.SUCCEEDED,
                        AgentRunExecutionStatus.FAILED,
                        AgentRunExecutionStatus.UNKNOWN,
                    } else None,
                }
                row = conn.execute(
                    """UPDATE aip_agent_run_execution_attempt SET status=%s,
                    provider_receipt_id=%s,usage_receipt_ids=%s::jsonb,
                    output_artifact_ref=%s::jsonb,reason_code=%s,
                    invoking_at=COALESCE(%s,invoking_at),completed_at=%s,
                    version=version+1,updated_at=%s
                    WHERE org_id=%s AND project_id=%s AND attempt_id=%s
                    AND version=%s AND status=%s RETURNING *""",
                    (
                        request.to_status.value,
                        values["provider_receipt_id"],
                        values["usage_receipt_ids"],
                        values["output_artifact_ref"],
                        values["reason_code"],
                        values["invoking_at"],
                        values["completed_at"],
                        occurred_at,
                        *scope.key,
                        attempt_id,
                        request.expected_version,
                        request.from_status.value,
                    ),
                ).fetchone()
                if row is None:
                    if self._row(conn, scope, attempt_id) is None:
                        raise AipAgentRegistryNotFound("execution attempt not found")
                    raise AipAgentRegistryConflict("execution attempt version or status changed")
                receipt = self._insert_receipt(
                    conn, scope, operation, idempotency_key, request_hash,
                    "AgentRunExecutionAttempt", attempt_id,
                    "AgentRunExecutionAttempt", attempt_id, actor, occurred_at,
                )
                conn.commit()
                return self._from_row(scope, row), receipt
        except (
            AipAgentRegistryConflict,
            AipAgentRegistryNotFound,
            AipAgentRegistryTransitionBlocked,
        ):
            raise
        except Exception as exc:
            raise AipAgentRegistryPersistenceError("agent run execution transition failed") from exc

    def get(self, scope: TenantScope, attempt_id: str) -> AgentRunExecutionAttempt:
        with self._connect_factory(scope) as conn:
            row = self._row(conn, scope, attempt_id)
        if row is None:
            raise AipAgentRegistryNotFound("execution attempt not found")
        return self._from_row(scope, row)

    def list(self, scope: TenantScope, *, agent_run_id: str | None, limit: int) -> list[AgentRunExecutionAttempt]:
        if limit < 1 or limit > 200:
            raise ValueError("list limit must be between 1 and 200")
        with self._connect_factory(scope) as conn:
            rows = conn.execute(
                """SELECT * FROM aip_agent_run_execution_attempt
                WHERE org_id=%s AND project_id=%s
                AND (%s::text IS NULL OR agent_run_id=%s)
                ORDER BY prepared_at DESC,attempt_id DESC LIMIT %s""",
                (*scope.key, agent_run_id, agent_run_id, limit),
            ).fetchall()
        return [self._from_row(scope, row) for row in rows]

    @staticmethod
    def _row(conn: Any, scope: TenantScope, attempt_id: str):
        return conn.execute(
            """SELECT * FROM aip_agent_run_execution_attempt
            WHERE org_id=%s AND project_id=%s AND attempt_id=%s""",
            (*scope.key, attempt_id),
        ).fetchone()

    @staticmethod
    def _from_row(scope: TenantScope, row: Any) -> AgentRunExecutionAttempt:
        if row is None:
            raise AipAgentRegistryNotFound("execution attempt not found")
        return AgentRunExecutionAttempt(
            tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
            attempt_id=row["attempt_id"], agent_run_id=row["agent_run_id"],
            agent_run_version=row["agent_run_version"], attempt_no=row["attempt_no"],
            route_ref=row["route_ref"], policy_ref=row["policy_ref"],
            model_ref=row["model_ref"], provider_ref=row["provider_ref"],
            price_snapshot_ref=row["price_snapshot_ref"], budget_ref=row["budget_ref"],
            capacity_reservation_ref=row["capacity_reservation_ref"],
            data_classification=row["data_classification"], lineage_id=row["lineage_id"],
            request_hash=row["request_hash"], status=row["status"],
            provider_receipt_id=row["provider_receipt_id"],
            usage_receipt_ids=row["usage_receipt_ids"],
            output_artifact_ref=row["output_artifact_ref"], reason_code=row["reason_code"],
            version=row["version"], prepared_at=row["prepared_at"],
            invoking_at=row["invoking_at"], completed_at=row["completed_at"],
            created_by=row["created_by"], updated_at=row["updated_at"],
        )
