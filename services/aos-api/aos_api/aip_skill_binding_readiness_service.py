"""Fail-closed tenant SkillBinding readiness aggregation for BIND-3."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from aos_api.aip_agent_registry_contracts import (
    CapabilityReadiness,
    OperationalBindingReadiness,
    SkillBinding,
)
from aos_api.aip_agent_registry_store import (
    AipAgentRegistryStore,
    AipAgentRegistryTransitionBlocked,
)
from aos_api.aip_model_runtime_store import AipModelRuntimeStore, ModelRuntimeStoreError
from aos_api.aip_skill_publication_service import (
    PostgresSkillPublicationRouteAuthority,
    SkillPublicationRouteAuthority,
)
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope


class AipSkillBindingReadinessService:
    def __init__(
        self,
        connect_factory=None,
        *,
        route_authority: SkillPublicationRouteAuthority | None = None,
        model_store: AipModelRuntimeStore | None = None,
        ttl: timedelta = timedelta(minutes=15),
    ) -> None:
        if ttl <= timedelta(0):
            raise ValueError("skill binding readiness ttl must be positive")
        self._connect_factory = connect_factory or db_connect
        self._route_authority = (
            route_authority or PostgresSkillPublicationRouteAuthority()
        )
        self._model_store = model_store or AipModelRuntimeStore()
        self._ttl = ttl

    def evaluate(
        self,
        scope: TenantScope,
        binding: SkillBinding,
        *,
        evaluated_at: datetime,
    ) -> OperationalBindingReadiness:
        reasons: list[str] = []
        dependencies = binding.dependencies
        with self._connect_factory(scope) as conn:
            skill = conn.execute(
                """SELECT * FROM aip_skill_template_revision
                   WHERE skill_id=%s AND revision=%s AND content_hash=%s""",
                (
                    binding.skill.asset_id,
                    binding.skill.revision,
                    binding.skill.content_hash,
                ),
            ).fetchone()
            if skill is None or skill["lifecycle"] != "published":
                reasons.append("SKILL_REVISION_NOT_PUBLISHED")
            else:
                tenant = skill["publication_tenant"] or {}
                if (
                    tenant.get("orgId") != scope.org_id
                    or tenant.get("projectId") != scope.project_id
                ):
                    reasons.append("SKILL_PUBLICATION_TENANT_MISMATCH")
                if (
                    dependencies.eval_gate_ref is None
                    or skill["release_gate_ref"]
                    != dependencies.eval_gate_ref.model_dump(mode="json", by_alias=True)
                ):
                    reasons.append("SKILL_EVAL_GATE_BLOCKED")
                if (
                    dependencies.model_route_ref is None
                    or skill["model_route_ref"]
                    != dependencies.model_route_ref.model_dump(mode="json", by_alias=True)
                    or dependencies.runtime_policy_ref is None
                    or skill["runtime_policy_ref"]
                    != dependencies.runtime_policy_ref.model_dump(
                        mode="json", by_alias=True
                    )
                ):
                    reasons.append("MODEL_ROUTE_BLOCKED")
                self._verify_publication(conn, scope, skill, reasons)
                self._verify_gate(conn, scope, dependencies.eval_gate_ref, reasons)

            instance = conn.execute(
                """SELECT status FROM aip_agent_instance
                   WHERE org_id=%s AND project_id=%s AND instance_id=%s""",
                (*scope.key, binding.instance_id),
            ).fetchone()
            if instance is None or instance["status"] != "active":
                reasons.append("INSTANCE_NOT_ACTIVE")

            capability_rows = self._capability_rows(
                conn, scope, binding.capability_binding_ids
            )
            if len(capability_rows) != len(set(binding.capability_binding_ids)):
                reasons.append("CAPABILITY_BINDING_MISSING")
            required = set(skill["required_capabilities"] if skill else [])
            provided = {
                row["capability_ref"].get("assetId") for row in capability_rows
            }
            if not required.issubset(provided):
                reasons.append("CAPABILITY_COVERAGE_INCOMPLETE")
            for row in capability_rows:
                if row["status"] != "active":
                    reasons.append("CAPABILITY_BINDING_NOT_ACTIVE")
                usable = row["operational_readiness"] == "available" or (
                    row["operational_readiness"] == "degraded"
                    and bool(row["allow_degraded"])
                )
                if not usable:
                    reasons.append("CAPABILITY_BINDING_NOT_ACTIVE")
                if (
                    row["dependency_snapshot_hash"] is None
                    or row["readiness_expires_at"] is None
                    or row["readiness_expires_at"] <= evaluated_at
                ):
                    reasons.append("CAPABILITY_HEALTH_STALE")

        if dependencies.model_route_ref is None:
            reasons.append("MODEL_ROUTE_BLOCKED")
        elif dependencies.runtime_policy_ref is None:
            reasons.append("RUNTIME_POLICY_REF_MISSING")
        else:
            try:
                self._route_authority.require_ready(
                    scope,
                    dependencies.model_route_ref,
                    dependencies.runtime_policy_ref,
                    evaluated_at=evaluated_at,
                )
            except AipAgentRegistryTransitionBlocked:
                reasons.append("MODEL_ROUTE_BLOCKED")

        if dependencies.budget_policy_ref is None:
            reasons.append("BUDGET_POLICY_MISSING")
        elif dependencies.runtime_policy_ref is not None:
            try:
                policy = self._model_store.get_policy(
                    scope,
                    dependencies.runtime_policy_ref.asset_id,
                    dependencies.runtime_policy_ref.revision,
                )
            except ModelRuntimeStoreError:
                reasons.append("BUDGET_POLICY_MISSING")
            else:
                if (
                    policy.content_hash != dependencies.runtime_policy_ref.content_hash
                    or policy.budget_policy_ref != dependencies.budget_policy_ref
                    or dependencies.budget_policy_ref != binding.budget_policy_ref
                ):
                    reasons.append("BUDGET_POLICY_MISSING")

        reasons = sorted(set(reasons))
        return OperationalBindingReadiness(
            readiness=(
                CapabilityReadiness.BLOCKED
                if reasons
                else CapabilityReadiness.AVAILABLE
            ),
            reasons=reasons,
            dependencies=dependencies,
            dependency_snapshot_hash=self.snapshot_hash(
                binding, capability_rows if "capability_rows" in locals() else []
            ),
            evaluated_at=evaluated_at,
            expires_at=evaluated_at + self._ttl,
        )

    @staticmethod
    def snapshot_hash(binding: SkillBinding, capability_rows: list[Any]) -> str:
        capability_snapshots = sorted(
            (
                {
                    "bindingId": row["binding_id"],
                    "capabilityRef": row["capability_ref"],
                    "dependencySnapshotHash": row["dependency_snapshot_hash"],
                    "readinessExpiresAt": row["readiness_expires_at"],
                    "status": row["status"],
                }
                for row in capability_rows
            ),
            key=lambda item: item["bindingId"],
        )
        return AipAgentRegistryStore._hash(
            {
                "skill": binding.skill,
                "instanceId": binding.instance_id,
                "capabilityBindings": capability_snapshots,
                "budgetPolicyRef": binding.budget_policy_ref,
                "dependencies": binding.dependencies,
            }
        )

    @staticmethod
    def _capability_rows(conn, scope: TenantScope, ids: list[str]):
        if not ids:
            return []
        return conn.execute(
            """SELECT * FROM aip_capability_binding
               WHERE org_id=%s AND project_id=%s AND binding_id=ANY(%s)
               ORDER BY binding_id""",
            (*scope.key, ids),
        ).fetchall()

    @staticmethod
    def _verify_gate(conn, scope, gate_ref, reasons: list[str]) -> None:
        if gate_ref is None:
            reasons.append("SKILL_EVAL_GATE_BLOCKED")
            return
        row = conn.execute(
            """SELECT status,decision_hash FROM aip_release_gate_decision
               WHERE org_id=%s AND project_id=%s AND decision_id=%s""",
            (*scope.key, gate_ref.asset_id),
        ).fetchone()
        if (
            row is None
            or row["status"] != "passed"
            or row["decision_hash"] != gate_ref.content_hash
        ):
            reasons.append("SKILL_EVAL_GATE_BLOCKED")

    @staticmethod
    def _verify_publication(conn, scope, skill, reasons: list[str]) -> None:
        publication = skill["publication_ref"] or {}
        row = conn.execute(
            """SELECT event_type,target_ref FROM aip_publication_event
               WHERE org_id=%s AND project_id=%s AND publication_id=%s
               ORDER BY occurred_at DESC,event_id DESC LIMIT 1""",
            (*scope.key, publication.get("revision")),
        ).fetchone()
        parent = skill["parent_ref"] or {}
        if (
            row is None
            or row["event_type"] != "published"
            or row["target_ref"].get("assetId") != parent.get("assetId")
            or row["target_ref"].get("revision") != str(parent.get("revision"))
            or row["target_ref"].get("contentHash") != parent.get("contentHash")
        ):
            reasons.append("SKILL_PUBLICATION_REVOKED")
