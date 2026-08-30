"""AIP-6 AgentRun authority bound to canonical TaskRun and exact assets."""
from __future__ import annotations

from datetime import datetime
from typing import Protocol

from aos_api.aip_agent_registry_contracts import (
    AgentRun,
    AgentRunStatus,
    CancelAgentRunRequest,
    CreateAgentRunRequest,
    RegistryReceipt,
    VersionedAssetRef,
)
from aos_api.aip_agent_registry_store import (
    AipAgentRegistryConflict,
    AipAgentRegistryNotFound,
    AipAgentRegistryPersistenceError,
    AipAgentRegistryStore,
    AipAgentRegistryTransitionBlocked,
)
from aos_api.aip_contracts import ResourceRef, TenantContext
from aos_api.aip_model_runtime_contracts import ModelRouteResolution, ModelRuntimeReadiness
from aos_api.aip_model_runtime_resolver import AipModelRuntimeResolver
from aos_api.aip_model_runtime_store import ModelRuntimeStoreError
from aos_api.tenant_scope import TenantScope
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.aip-agent-run")


class CapacityReservationGate(Protocol):
    def reserve(self, scope: TenantScope, resolution: ModelRouteResolution, agent_run_id: str) -> str: ...
    def release(self, scope: TenantScope, reservation_id: str) -> None: ...
    def release_for_run(self, scope: TenantScope, agent_run_id: str) -> None: ...


class UnavailableCapacityReservationGate:
    def reserve(self, scope: TenantScope, resolution: ModelRouteResolution, agent_run_id: str) -> str:
        raise AipAgentRegistryTransitionBlocked("capacity_reservation_authority_unavailable")

    def release(self, scope: TenantScope, reservation_id: str) -> None:
        return None

    def release_for_run(self, scope: TenantScope, agent_run_id: str) -> None:
        return None


class AipAgentRunService(AipAgentRegistryStore):
    def __init__(self, connect_factory=None, *, model_resolver=None, capacity_gate=None) -> None:
        super().__init__(connect_factory)
        self._model_resolver = model_resolver or AipModelRuntimeResolver()
        if capacity_gate is None:
            from aos_api.aip_model_capacity_reservation import AipModelCapacityReservationGate

            capacity_gate = AipModelCapacityReservationGate(self._connect_factory)
        self._capacity_gate = capacity_gate

    def create(self, scope: TenantScope, request: CreateAgentRunRequest, *, idempotency_key: str, actor: str, occurred_at: datetime) -> tuple[AgentRun, RegistryReceipt]:
        self._validate_command(scope, idempotency_key, actor)
        operation = "agent_run.create"
        request_hash = self._command_hash(request, actor)
        run = request.run
        try:
            with self._connect_factory(scope) as conn:
                self._lock(conn, scope, operation, idempotency_key)
                replay = self._receipt_row(conn, scope, operation, idempotency_key)
                if replay:
                    self._require_replay_hash(replay, request_hash)
                    return self._from_row(scope, self._row(conn, scope, request.agent_run_id)), self._receipt_from_row(scope, replay)
                if self._row(conn, scope, request.agent_run_id):
                    raise AipAgentRegistryConflict("agent run id already exists")
                task_id, task_run_id = self._require_task_run(
                    conn, scope, run.task_ref, request.task_run_ref, run.plan_ref
                )
                instance = self._instance_row(conn, scope, run.agent_instance.asset_id)
                if instance is None:
                    raise AipAgentRegistryNotFound("exact agent instance revision not found")
                snapshot = self._instance_snapshot(instance)
                exact_instance = self._instance_from_row(scope, instance).instance_ref
                if exact_instance != run.agent_instance:
                    raise AipAgentRegistryNotFound("exact agent instance revision not found")
                if instance["status"] != "active":
                    raise AipAgentRegistryTransitionBlocked("agent instance is not active")
                binding = conn.execute(
                    """SELECT b.*,s.content_hash,s.canonical_logic_id,s.logic_revision_ref
                       FROM aip_skill_binding b
                       JOIN aip_skill_template_revision s ON s.skill_id=b.skill_id
                        AND s.revision=b.skill_revision
                       WHERE b.org_id=%s AND b.project_id=%s AND b.binding_id=%s""",
                    (*scope.key, request.skill_binding_id),
                ).fetchone()
                if binding is None or binding["status"] != "active":
                    raise AipAgentRegistryTransitionBlocked("skill binding is not active")
                if binding["instance_id"] != instance["instance_id"]:
                    raise AipAgentRegistryConflict("skill binding belongs to a different agent instance")
                if (binding["skill_id"], int(binding["skill_revision"]), binding["content_hash"]) != (
                    run.skill.asset_id, run.skill.revision, run.skill.content_hash
                ):
                    raise AipAgentRegistryConflict("skill binding exact revision drifted")
                if (
                    binding["canonical_logic_id"] != run.logic.asset_id
                    or not binding["logic_revision_ref"]
                    or VersionedAssetRef.model_validate(binding["logic_revision_ref"])
                    != run.logic
                ):
                    raise AipAgentRegistryConflict(
                        "agent run logic differs from the Skill's exact published LogicRevision"
                    )
                self._require_healthy_capabilities(conn, scope, binding["capability_refs"])
                self._require_logic(conn, scope, run.logic)
                row = conn.execute(
                    """INSERT INTO aip_agent_run
                       (org_id,project_id,agent_run_id,task_id,task_run_id,plan_ref,
                        task_ref,task_run_ref,instance_id,instance_version,instance_ref,instance_snapshot,
                        skill_binding_id,skill_ref,logic_ref,
                        model_route_ref,policy_ref,input_refs,status,version,created_at,updated_at)
                       VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s,%s::jsonb,%s::jsonb,%s,%s::jsonb,%s::jsonb,
                        %s::jsonb,%s::jsonb,%s::jsonb,'queued',1,%s,%s) RETURNING *""",
                    (*scope.key, request.agent_run_id, task_id, task_run_id,
                     self._json(run.plan_ref), self._json(run.task_ref),
                     self._json(request.task_run_ref), instance["instance_id"], instance["version"],
                     self._json(run.agent_instance), self._json(snapshot),
                     request.skill_binding_id, self._json(run.skill), self._json(run.logic),
                     self._json(run.model_route), self._json(run.policy),
                     self._json(run.input_refs), occurred_at, occurred_at),
                ).fetchone()
                receipt = self._insert_receipt(conn, scope, operation, idempotency_key,
                    request_hash, "TaskRun", task_run_id, "AgentRun", request.agent_run_id,
                    actor, occurred_at)
                conn.commit()
                return self._from_row(scope, row), receipt
        except (AipAgentRegistryConflict, AipAgentRegistryNotFound, AipAgentRegistryTransitionBlocked):
            raise
        except Exception as exc:
            raise AipAgentRegistryPersistenceError("agent run persistence failed") from exc

    def transition(self, scope: TenantScope, agent_run_id: str, *, expected_version: int, from_status: AgentRunStatus, to_status: AgentRunStatus, actor: str, occurred_at: datetime) -> AgentRun:
        allowed = {
            AgentRunStatus.QUEUED: {AgentRunStatus.RUNNING, AgentRunStatus.CANCELLED},
            AgentRunStatus.RUNNING: {AgentRunStatus.PAUSED, AgentRunStatus.SUCCEEDED, AgentRunStatus.FAILED, AgentRunStatus.CANCELLED, AgentRunStatus.UNKNOWN},
            AgentRunStatus.PAUSED: {AgentRunStatus.RUNNING, AgentRunStatus.CANCELLED},
        }
        if to_status not in allowed.get(from_status, set()):
            raise AipAgentRegistryTransitionBlocked("agent run transition is not allowed")
        with self._connect_factory(scope) as conn:
            current = self._row(conn, scope, agent_run_id)
            if current is None:
                raise AipAgentRegistryNotFound("agent run not found")
            if to_status is AgentRunStatus.RUNNING:
                resolution = self._resolve_start(scope, current)
                reservation_id = self._capacity_gate.reserve(scope, resolution, agent_run_id)
            else:
                reservation_id = None
            row = conn.execute("""UPDATE aip_agent_run SET status=%s,version=version+1,updated_at=%s
                WHERE org_id=%s AND project_id=%s AND agent_run_id=%s AND version=%s AND status=%s RETURNING *""",
                (to_status.value, occurred_at, *scope.key, agent_run_id, expected_version, from_status.value)).fetchone()
            if row is None:
                if reservation_id:
                    self._capacity_gate.release(scope, reservation_id)
                raise AipAgentRegistryConflict("agent run version or status changed")
            try:
                conn.commit()
            except Exception:
                if reservation_id:
                    self._capacity_gate.release(scope, reservation_id)
                raise
            if from_status in {AgentRunStatus.RUNNING, AgentRunStatus.PAUSED} and to_status is not AgentRunStatus.RUNNING:
                try:
                    self._capacity_gate.release_for_run(scope, agent_run_id)
                except Exception:
                    # AgentRun CAS is already committed. The reservation authority has
                    # a bounded TTL, so report the recovery path without implying rollback.
                    log.warning(
                        "capacity_release_deferred agent_run_id=%s target_status=%s",
                        agent_run_id,
                        to_status.value,
                        exc_info=True,
                    )
            return self._from_row(scope, row)

    def cancel_queued(
        self,
        scope: TenantScope,
        agent_run_id: str,
        request: CancelAgentRunRequest,
        *,
        idempotency_key: str,
        actor: str,
        occurred_at: datetime,
    ) -> tuple[AgentRun, RegistryReceipt]:
        """Cancel a never-started AgentRun without resolving Provider or secrets."""
        self._validate_command(scope, idempotency_key, actor)
        operation = "agent_run.cancel_queued"
        request_hash = self._command_hash(request, actor)
        try:
            with self._connect_factory(scope) as conn:
                self._lock(conn, scope, operation, idempotency_key)
                replay = self._receipt_row(conn, scope, operation, idempotency_key)
                if replay:
                    self._require_replay_hash(replay, request_hash)
                    return self._from_row(scope, self._row(conn, scope, agent_run_id)), self._receipt_from_row(scope, replay)
                row = conn.execute(
                    """UPDATE aip_agent_run SET status='cancelled',version=version+1,updated_at=%s
                       WHERE org_id=%s AND project_id=%s AND agent_run_id=%s
                        AND version=%s AND status='queued' RETURNING *""",
                    (occurred_at, *scope.key, agent_run_id, request.expected_version),
                ).fetchone()
                if row is None:
                    current = self._row(conn, scope, agent_run_id)
                    if current is None:
                        raise AipAgentRegistryNotFound("agent run not found")
                    raise AipAgentRegistryConflict("queued agent run version or status changed")
                receipt = self._insert_receipt(
                    conn,
                    scope,
                    operation,
                    idempotency_key,
                    request_hash,
                    "AgentRun",
                    agent_run_id,
                    "AgentRun",
                    agent_run_id,
                    actor,
                    occurred_at,
                )
                conn.commit()
                return self._from_row(scope, row), receipt
        except (AipAgentRegistryConflict, AipAgentRegistryNotFound, AipAgentRegistryTransitionBlocked):
            raise
        except Exception as exc:
            raise AipAgentRegistryPersistenceError("agent run cancellation persistence failed") from exc

    def _resolve_start(self, scope: TenantScope, current) -> ModelRouteResolution:
        route_ref = current["model_route_ref"]
        policy_ref = current["policy_ref"]
        if route_ref.get("assetType") != "ModelRouteRevision":
            raise AipAgentRegistryTransitionBlocked("agent_run_model_route_kind_invalid")
        if policy_ref.get("assetType") != "RuntimePolicyRevision":
            raise AipAgentRegistryTransitionBlocked("agent_run_runtime_policy_revision_required")
        try:
            resolution = self._model_resolver.resolve(scope, route_ref["assetId"])
        except ModelRuntimeStoreError as exc:
            raise AipAgentRegistryTransitionBlocked("model_runtime_authority_unavailable") from exc
        if resolution.readiness is not ModelRuntimeReadiness.READY:
            blockers = ",".join(resolution.blocker_codes) or "model_runtime_not_ready"
            raise AipAgentRegistryTransitionBlocked(blockers)
        requested_route = (
            route_ref.get("assetId"), route_ref.get("revision"), route_ref.get("contentHash")
        )
        exact_route = (
            resolution.route.asset_id, resolution.route.revision, resolution.route.content_hash
        )
        requested_policy = (
            policy_ref.get("assetId"), policy_ref.get("revision"), policy_ref.get("contentHash")
        )
        exact_policy = (
            resolution.policy.asset_id, resolution.policy.revision, resolution.policy.content_hash
        )
        if requested_route != exact_route:
            raise AipAgentRegistryTransitionBlocked("agent_run_model_route_exact_ref_drifted")
        if requested_policy != exact_policy:
            raise AipAgentRegistryTransitionBlocked("agent_run_runtime_policy_exact_ref_drifted")
        return resolution

    def get(self, scope: TenantScope, agent_run_id: str) -> AgentRun:
        with self._connect_factory(scope) as conn:
            row = self._row(conn, scope, agent_run_id)
        if row is None:
            raise AipAgentRegistryNotFound("agent run not found")
        return self._from_row(scope, row)

    def list(self, scope: TenantScope, *, instance_id: str | None = None, limit: int = 20) -> list[AgentRun]:
        with self._connect_factory(scope) as conn:
            if instance_id is None:
                rows = conn.execute(
                    """SELECT * FROM aip_agent_run
                       WHERE org_id=%s AND project_id=%s
                       ORDER BY updated_at DESC,agent_run_id DESC LIMIT %s""",
                    (*scope.key, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT * FROM aip_agent_run
                       WHERE org_id=%s AND project_id=%s AND instance_id=%s
                       ORDER BY updated_at DESC,agent_run_id DESC LIMIT %s""",
                    (*scope.key, instance_id, limit),
                ).fetchall()
        return [self._from_row(scope, row) for row in rows]

    @staticmethod
    def _row(conn, scope: TenantScope, agent_run_id: str):
        return conn.execute("""SELECT * FROM aip_agent_run
            WHERE org_id=%s AND project_id=%s AND agent_run_id=%s""",
            (*scope.key, agent_run_id)).fetchone()

    @staticmethod
    def _require_task_run(conn, scope: TenantScope, task_ref: ResourceRef, task_run_ref: ResourceRef, plan_ref: ResourceRef) -> tuple[str, str]:
        if task_ref.resource_type != "Task" or task_run_ref.resource_type != "TaskRun" or plan_ref.resource_type != "PlanRevision":
            raise AipAgentRegistryConflict("task, task run and plan refs have invalid kinds")
        row = conn.execute("""SELECT r.task_id,r.run_id,r.plan_revision_id,
                r.version AS run_version,t.version AS task_version,p.revision AS plan_revision
            FROM aip_task_run r
            JOIN aip_task t ON t.org_id=r.org_id AND t.project_id=r.project_id
             AND t.task_id=r.task_id
            JOIN aip_plan_revision p ON p.org_id=r.org_id AND p.project_id=r.project_id
             AND p.plan_revision_id=r.plan_revision_id
            WHERE r.org_id=%s AND r.project_id=%s AND r.run_id=%s""",
            (*scope.key, task_run_ref.resource_id)).fetchone()
        if row is None:
            raise AipAgentRegistryNotFound("canonical task run not found")
        if row["task_id"] != task_ref.resource_id:
            raise AipAgentRegistryConflict("task run belongs to another task")
        if row["plan_revision_id"] != plan_ref.resource_id:
            raise AipAgentRegistryConflict("task run belongs to another plan revision")
        exact = (
            (task_ref.revision, str(row["task_version"])),
            (task_run_ref.revision, str(row["run_version"])),
            (plan_ref.revision, str(row["plan_revision"])),
        )
        if any(actual != expected for actual, expected in exact):
            raise AipAgentRegistryConflict("task, task run or plan exact revision drifted")
        return row["task_id"], row["run_id"]

    @staticmethod
    def _require_healthy_capabilities(conn, scope: TenantScope, ids: list[str]) -> None:
        if not ids:
            return
        rows = conn.execute("""SELECT binding_id FROM aip_capability_binding
            WHERE org_id=%s AND project_id=%s AND binding_id=ANY(%s)
             AND status='active' AND health='healthy'""", (*scope.key, ids)).fetchall()
        if {row["binding_id"] for row in rows} != set(ids):
            raise AipAgentRegistryTransitionBlocked("required capability binding is not active and healthy")

    @staticmethod
    def _require_logic(conn, scope: TenantScope, ref) -> None:
        row = conn.execute("""SELECT r.graph_hash FROM aip_logic_graph_revision r
            JOIN aip_logic_publication p ON p.org_id=r.org_id AND p.project_id=r.project_id
             AND p.graph_id=r.graph_id AND p.graph_revision=r.revision
             AND p.graph_hash=r.graph_hash
            WHERE r.org_id=%s AND r.project_id=%s AND r.graph_id=%s AND r.revision=%s
             AND r.graph_hash=%s LIMIT 1""",
            (*scope.key, ref.asset_id, ref.revision, ref.content_hash)).fetchone()
        if row is None:
            raise AipAgentRegistryNotFound("published exact LogicRevision not found")

    @staticmethod
    def _from_row(scope: TenantScope, row) -> AgentRun:
        if row is None:
            raise AipAgentRegistryNotFound("agent run not found")
        request = {
            "taskRef": row["task_ref"],
            "planRef": row["plan_ref"], "agentInstance": row["instance_ref"],
            "skill": row["skill_ref"], "logic": row["logic_ref"], "modelRoute": row["model_route_ref"],
            "policy": row["policy_ref"], "inputRefs": row["input_refs"],
        }
        return AgentRun(tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
            agent_run_id=row["agent_run_id"], task_id=row["task_id"], task_run_id=row["task_run_id"],
            instance_id=row["instance_id"], instance_version=row["instance_version"],
            skill_binding_id=row["skill_binding_id"], request=request, status=row["status"],
            version=row["version"], created_at=row["created_at"], updated_at=row["updated_at"])
