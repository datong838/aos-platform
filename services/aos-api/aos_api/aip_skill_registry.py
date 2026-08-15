"""PostgreSQL authority for immutable AIP-6 skills and tenant bindings."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from aos_api.aip_agent_registry_contracts import (
    CreateSkillBindingRequest,
    EvaluateOperationalBindingRequest,
    OperationalBindingDependencies,
    OperationalBindingReadiness,
    PublishSkillTemplateRequest,
    RegistryReceipt,
    SkillBinding,
    SkillTemplateRevision,
    TemplateLifecycle,
    UpdateSkillBindingRequest,
    VersionedAssetRef,
)
from aos_api.aip_agent_registry_store import (
    AipAgentRegistryConflict,
    AipAgentRegistryNotFound,
    AipAgentRegistryPersistenceError,
    AipAgentRegistryStore,
    AipAgentRegistryTransitionBlocked,
)
from aos_api.aip_contracts import TenantContext
from aos_api.tenant_scope import TenantScope

_TRANSITIONS = {
    "provisioning": {"active", "revoked"},
    "active": {"suspended", "revoked"},
    "suspended": {"active", "revoked"},
    "revoked": set(),
}


class AipSkillRegistry(AipAgentRegistryStore):
    def __init__(self, connect_factory=None, *, readiness_service=None) -> None:
        super().__init__(connect_factory)
        if readiness_service is None:
            from aos_api.aip_skill_binding_readiness_service import (
                AipSkillBindingReadinessService,
            )

            readiness_service = AipSkillBindingReadinessService(
                connect_factory=connect_factory
            )
        self._readiness_service = readiness_service

    def publish_skill(self, request: PublishSkillTemplateRequest, *, actor: str) -> SkillTemplateRevision:
        if not actor.strip():
            raise ValueError("actor is required")
        if request.lifecycle is TemplateLifecycle.PUBLISHED:
            raise AipAgentRegistryTransitionBlocked(
                "published skills require the governed Eval publication service"
            )
        try:
            with self._connect_factory() as conn:
                row = conn.execute(
                    """INSERT INTO aip_skill_template_revision
                       (skill_id,revision,canonical_logic_id,lifecycle,input_schema,
                        output_schema,tool_allowlist,required_capabilities,risk_level,
                        eval_pack_ref,memory_policy_ref,handoff_policy_ref,source_ref,
                        source_license,parent_ref,publication_tenant,release_gate_ref,
                        publication_ref,model_route_ref,runtime_policy_ref,content_hash,
                        created_by)
                       VALUES (%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,
                        %s,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s::jsonb,
                        %s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s)
                       ON CONFLICT (skill_id,revision) DO NOTHING RETURNING *""",
                    (request.skill_id, request.revision, request.canonical_logic_id,
                     request.lifecycle.value, self._json(request.input_schema),
                     self._json(request.output_schema), self._json(request.tool_allowlist),
                     self._json(request.required_capabilities), request.risk_level,
                     self._json(request.eval_pack_ref) if request.eval_pack_ref else None,
                     self._json(request.memory_policy_ref), self._json(request.handoff_policy_ref),
                     self._json(request.source_ref), request.source_license,
                     self._json(request.parent_ref) if request.parent_ref else None,
                     self._json(request.publication_tenant) if request.publication_tenant else None,
                     self._json(request.release_gate_ref) if request.release_gate_ref else None,
                     self._json(request.publication_ref) if request.publication_ref else None,
                     self._json(request.model_route_ref) if request.model_route_ref else None,
                     self._json(request.runtime_policy_ref) if request.runtime_policy_ref else None,
                     request.content_hash, actor.strip()),
                ).fetchone()
                if row is None:
                    row = self._skill_row(conn, request.skill_id, request.revision)
                    if row is None or self._skill_content(row) != request.model_dump(mode="json"):
                        raise AipAgentRegistryConflict("skill revision already has different content")
                conn.commit()
                return self._skill_from_row(row)
        except (
            AipAgentRegistryConflict,
            AipAgentRegistryNotFound,
            AipAgentRegistryTransitionBlocked,
        ):
            raise
        except Exception as exc:
            raise AipAgentRegistryPersistenceError("skill template persistence failed") from exc

    def get_skill(self, skill_id: str, revision: int) -> SkillTemplateRevision:
        try:
            with self._connect_factory() as conn:
                row = self._skill_row(conn, skill_id, revision)
                if row is None:
                    raise AipAgentRegistryNotFound("skill template revision not found")
                return self._skill_from_row(row)
        except (AipAgentRegistryNotFound, AipAgentRegistryConflict):
            raise
        except Exception as exc:
            raise AipAgentRegistryPersistenceError("skill template read failed") from exc

    def list_skills(
        self,
        *,
        source_resource_id: str | None = None,
        source_revision: str | None = None,
        lifecycle: TemplateLifecycle | None = None,
        limit: int = 100,
    ) -> list[SkillTemplateRevision]:
        if limit < 1 or limit > 200:
            raise ValueError("list limit must be between 1 and 200")
        try:
            with self._connect_factory() as conn:
                rows = conn.execute(
                    """SELECT * FROM aip_skill_template_revision
                       WHERE (%s::text IS NULL OR source_ref->>'resourceId'=%s)
                         AND (%s::text IS NULL OR source_ref->>'revision'=%s)
                         AND (%s::text IS NULL OR lifecycle=%s)
                       ORDER BY skill_id,revision DESC LIMIT %s""",
                    (
                        source_resource_id,
                        source_resource_id,
                        source_revision,
                        source_revision,
                        lifecycle.value if lifecycle else None,
                        lifecycle.value if lifecycle else None,
                        limit,
                    ),
                ).fetchall()
            return [self._skill_from_row(row) for row in rows]
        except Exception as exc:
            raise AipAgentRegistryPersistenceError("skill template list failed") from exc

    def create_binding(self, scope: TenantScope, request: CreateSkillBindingRequest, *, idempotency_key: str, actor: str, occurred_at: datetime) -> tuple[SkillBinding, RegistryReceipt]:
        self._validate_command(scope, idempotency_key, actor)
        request_hash = self._command_hash(request, actor)
        operation = "skill_binding.create"
        try:
            with self._connect_factory(scope) as conn:
                self._lock(conn, scope, operation, idempotency_key)
                replay = self._receipt_row(conn, scope, operation, idempotency_key)
                if replay is not None:
                    self._require_replay_hash(replay, request_hash)
                    row = self._binding_row(conn, scope, replay["result_ref"]["resourceId"])
                    return self._binding_from_row(scope, row), self._receipt_from_row(scope, replay)
                skill = conn.execute(
                    """SELECT * FROM aip_skill_template_revision
                       WHERE skill_id=%s AND revision=%s AND content_hash=%s""",
                    (request.skill.asset_id, request.skill.revision, request.skill.content_hash),
                ).fetchone()
                if skill is None:
                    raise AipAgentRegistryNotFound("exact skill revision not found")
                if TemplateLifecycle(skill["lifecycle"]) is not TemplateLifecycle.PUBLISHED:
                    raise AipAgentRegistryTransitionBlocked("only published skills can be bound")
                latest = conn.execute(
                    """SELECT lifecycle FROM aip_skill_template_revision
                       WHERE skill_id=%s ORDER BY revision DESC LIMIT 1""",
                    (request.skill.asset_id,),
                ).fetchone()
                if latest is None or TemplateLifecycle(latest["lifecycle"]) is not TemplateLifecycle.PUBLISHED:
                    raise AipAgentRegistryTransitionBlocked(
                        "deprecated or revoked skill families cannot create bindings"
                    )
                publication_tenant = skill.get("publication_tenant") or {}
                if (
                    publication_tenant.get("orgId") != scope.org_id
                    or publication_tenant.get("projectId") != scope.project_id
                ):
                    raise AipAgentRegistryTransitionBlocked(
                        "published skill belongs to another tenant publication"
                    )
                if self._instance_row(conn, scope, request.instance_id) is None:
                    raise AipAgentRegistryNotFound("agent instance not found")
                if self._binding_row(conn, scope, request.binding_id) is not None:
                    raise AipAgentRegistryConflict("skill binding id already exists")
                self._require_capability_refs(conn, scope, request.capability_binding_ids)
                capability_rows = self._capability_rows(
                    conn, scope, request.capability_binding_ids
                )
                provided = {
                    row["capability_ref"].get("assetId") for row in capability_rows
                }
                if not set(skill["required_capabilities"]).issubset(provided):
                    raise AipAgentRegistryTransitionBlocked(
                        "skill required capabilities are not fully covered"
                    )
                row = conn.execute(
                    """INSERT INTO aip_skill_binding
                       (org_id,project_id,binding_id,instance_id,skill_id,skill_revision,
                        capability_refs,budget_policy_ref,status,version,created_at,updated_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,1,%s,%s)
                       RETURNING *""",
                    (*scope.key, request.binding_id, request.instance_id,
                     request.skill.asset_id, request.skill.revision,
                     self._json(request.capability_binding_ids),
                     self._json(request.budget_policy_ref), request.initial_status,
                     occurred_at, occurred_at),
                ).fetchone()
                receipt = self._insert_receipt(conn, scope, operation, idempotency_key,
                    request_hash, "SkillTemplate", request.skill.asset_id,
                    "SkillBinding", request.binding_id, actor, occurred_at)
                row = self._binding_row(conn, scope, request.binding_id)
                conn.commit()
                return self._binding_from_row(scope, row), receipt
        except (AipAgentRegistryConflict, AipAgentRegistryNotFound, AipAgentRegistryTransitionBlocked):
            raise
        except Exception as exc:
            raise AipAgentRegistryPersistenceError("skill binding persistence failed") from exc

    def get_binding(self, scope: TenantScope, binding_id: str) -> SkillBinding:
        try:
            with self._connect_factory(scope) as conn:
                row = self._binding_row(conn, scope, binding_id)
                if row is None:
                    raise AipAgentRegistryNotFound("skill binding not found")
                return self._binding_from_row(scope, row)
        except AipAgentRegistryNotFound:
            raise
        except Exception as exc:
            raise AipAgentRegistryPersistenceError("skill binding read failed") from exc

    def list_bindings(self, scope: TenantScope, *, instance_id: str | None = None, limit: int = 100) -> list[SkillBinding]:
        if limit < 1 or limit > 200:
            raise ValueError("list limit must be between 1 and 200")
        try:
            with self._connect_factory(scope) as conn:
                rows = conn.execute(
                    """SELECT b.*,s.content_hash FROM aip_skill_binding b
                       JOIN aip_skill_template_revision s ON s.skill_id=b.skill_id
                        AND s.revision=b.skill_revision
                       WHERE b.org_id=%s AND b.project_id=%s
                        AND (%s::text IS NULL OR b.instance_id=%s)
                       ORDER BY b.updated_at DESC,b.binding_id LIMIT %s""",
                    (*scope.key, instance_id, instance_id, limit),
                ).fetchall()
                return [self._binding_from_row(scope, row) for row in rows]
        except Exception as exc:
            raise AipAgentRegistryPersistenceError("skill binding list failed") from exc

    def update_binding(self, scope: TenantScope, binding_id: str, request: UpdateSkillBindingRequest, *, idempotency_key: str, actor: str, occurred_at: datetime) -> tuple[SkillBinding, RegistryReceipt]:
        self._validate_command(scope, idempotency_key, actor)
        request_hash = self._command_hash(request, actor)
        operation = "skill_binding.update"
        if request.to_status not in _TRANSITIONS[request.from_status]:
            raise AipAgentRegistryTransitionBlocked("skill binding transition is not allowed")
        try:
            with self._connect_factory(scope) as conn:
                self._lock(conn, scope, operation, idempotency_key)
                replay = self._receipt_row(conn, scope, operation, idempotency_key)
                if replay is not None:
                    self._require_replay_hash(replay, request_hash)
                    return self._binding_from_row(scope, self._binding_row(conn, scope, binding_id)), self._receipt_from_row(scope, replay)
                if request.to_status == "active":
                    current_row = self._binding_row(conn, scope, binding_id)
                    if current_row is None:
                        raise AipAgentRegistryNotFound("skill binding not found")
                    decision_at = datetime.now(UTC)
                    if (
                        current_row["readiness"] != "available"
                        or current_row["dependency_snapshot_hash"] is None
                        or current_row["readiness_expires_at"] is None
                        or current_row["readiness_expires_at"] <= decision_at
                    ):
                        raise AipAgentRegistryTransitionBlocked(
                            "fresh skill binding readiness does not allow activation"
                        )
                    recomputed = self._readiness_service.evaluate(
                        scope,
                        self._binding_from_row(scope, current_row),
                        evaluated_at=decision_at,
                    )
                    if (
                        recomputed.readiness.value != "available"
                        or recomputed.dependency_snapshot_hash
                        != current_row["dependency_snapshot_hash"]
                    ):
                        raise AipAgentRegistryTransitionBlocked(
                            "skill binding dependency snapshot drifted before activation"
                        )
                row = conn.execute(
                    """UPDATE aip_skill_binding SET status=%s,version=version+1,updated_at=%s
                       WHERE org_id=%s AND project_id=%s AND binding_id=%s
                        AND version=%s AND status=%s RETURNING *""",
                    (request.to_status, occurred_at, *scope.key, binding_id,
                     request.expected_version, request.from_status),
                ).fetchone()
                if row is None:
                    if self._binding_row(conn, scope, binding_id) is None:
                        raise AipAgentRegistryNotFound("skill binding not found")
                    raise AipAgentRegistryConflict("skill binding version or status changed")
                receipt = self._insert_receipt(conn, scope, operation, idempotency_key,
                    request_hash, "SkillBinding", binding_id, "SkillBinding", binding_id,
                    actor, occurred_at)
                row = self._binding_row(conn, scope, binding_id)
                conn.commit()
                return self._binding_from_row(scope, row), receipt
        except (AipAgentRegistryConflict, AipAgentRegistryNotFound, AipAgentRegistryTransitionBlocked):
            raise
        except Exception as exc:
            raise AipAgentRegistryPersistenceError("skill binding update failed") from exc

    def evaluate_binding(
        self,
        scope: TenantScope,
        binding_id: str,
        request: EvaluateOperationalBindingRequest,
        *,
        idempotency_key: str,
        actor: str,
        evaluated_at: datetime,
    ) -> tuple[SkillBinding, OperationalBindingReadiness, RegistryReceipt]:
        self._validate_command(scope, idempotency_key, actor)
        self._require_skill_dependency_shape(request.dependencies)
        current = self.get_binding(scope, binding_id)
        if request.dependencies.budget_policy_ref != current.budget_policy_ref:
            raise AipAgentRegistryTransitionBlocked(
                "skill binding budget policy is immutable and must match evaluation"
            )
        candidate = current.model_copy(update={"dependencies": request.dependencies})
        result = self._readiness_service.evaluate(
            scope, candidate, evaluated_at=evaluated_at
        )
        if (
            request.expected_dependency_snapshot_hash is not None
            and request.expected_dependency_snapshot_hash
            != result.dependency_snapshot_hash
        ):
            raise AipAgentRegistryConflict("dependency snapshot hash changed")
        operation = "skill_binding.evaluate"
        request_hash = self._command_hash(request, actor)
        dependencies = result.dependencies
        try:
            with self._connect_factory(scope) as conn:
                self._lock(conn, scope, operation, idempotency_key)
                replay = self._receipt_row(conn, scope, operation, idempotency_key)
                if replay is not None:
                    self._require_replay_hash(replay, request_hash)
                    row = self._binding_row(conn, scope, binding_id)
                    return (
                        self._binding_from_row(scope, row),
                        self._readiness_from_row(row),
                        self._receipt_from_row(scope, replay),
                    )
                row = conn.execute(
                    """UPDATE aip_skill_binding SET
                       model_route_ref=%s::jsonb,runtime_policy_ref=%s::jsonb,
                       eval_gate_ref=%s::jsonb,dependency_snapshot_hash=%s,
                       readiness=%s,readiness_reasons=%s::jsonb,
                       last_evaluated_at=%s,readiness_expires_at=%s,
                       version=version+1,updated_at=%s
                       WHERE org_id=%s AND project_id=%s AND binding_id=%s
                         AND version=%s AND status IN ('provisioning','suspended')
                       RETURNING *""",
                    (
                        self._json(dependencies.model_route_ref),
                        self._json(dependencies.runtime_policy_ref),
                        self._json(dependencies.eval_gate_ref),
                        result.dependency_snapshot_hash,
                        result.readiness.value,
                        self._json(result.reasons),
                        result.evaluated_at,
                        result.expires_at,
                        result.evaluated_at,
                        *scope.key,
                        binding_id,
                        request.expected_version,
                    ),
                ).fetchone()
                if row is None:
                    if self._binding_row(conn, scope, binding_id) is None:
                        raise AipAgentRegistryNotFound("skill binding not found")
                    raise AipAgentRegistryConflict(
                        "skill binding version or lifecycle changed"
                    )
                receipt = self._insert_receipt(
                    conn,
                    scope,
                    operation,
                    idempotency_key,
                    request_hash,
                    "SkillBinding",
                    binding_id,
                    "SkillBindingReadiness",
                    binding_id,
                    actor,
                    evaluated_at,
                )
                row = self._binding_row(conn, scope, binding_id)
                conn.commit()
                return self._binding_from_row(scope, row), result, receipt
        except (
            AipAgentRegistryConflict,
            AipAgentRegistryNotFound,
            AipAgentRegistryTransitionBlocked,
        ):
            raise
        except Exception as exc:
            raise AipAgentRegistryPersistenceError(
                "skill binding evaluation failed"
            ) from exc

    @staticmethod
    def _skill_row(conn: Any, skill_id: str, revision: int):
        return conn.execute("SELECT * FROM aip_skill_template_revision WHERE skill_id=%s AND revision=%s", (skill_id, revision)).fetchone()

    @staticmethod
    def _binding_row(conn: Any, scope: TenantScope, binding_id: str):
        return conn.execute(
            """SELECT b.*,s.content_hash FROM aip_skill_binding b
               JOIN aip_skill_template_revision s ON s.skill_id=b.skill_id
                AND s.revision=b.skill_revision
               WHERE b.org_id=%s AND b.project_id=%s AND b.binding_id=%s""",
            (*scope.key, binding_id),
        ).fetchone()

    @staticmethod
    def _require_capability_refs(conn: Any, scope: TenantScope, ids: list[str]) -> None:
        if not ids:
            return
        rows = conn.execute("""SELECT binding_id FROM aip_capability_binding
            WHERE org_id=%s AND project_id=%s AND binding_id=ANY(%s)""", (*scope.key, ids)).fetchall()
        if {row["binding_id"] for row in rows} != set(ids):
            raise AipAgentRegistryNotFound("capability binding reference not found")

    @staticmethod
    def _capability_rows(conn: Any, scope: TenantScope, ids: list[str]):
        if not ids:
            return []
        return conn.execute(
            """SELECT binding_id,capability_ref FROM aip_capability_binding
               WHERE org_id=%s AND project_id=%s AND binding_id=ANY(%s)""",
            (*scope.key, ids),
        ).fetchall()

    @staticmethod
    def _require_skill_dependency_shape(
        dependencies: OperationalBindingDependencies,
    ) -> None:
        if (
            dependencies.provider_ref is not None
            or dependencies.eval_contract_ref is not None
            or dependencies.license_evidence_refs
            or dependencies.data_dependency_refs
            or dependencies.tool_dependency_refs
            or dependencies.allow_degraded
        ):
            raise ValueError(
                "skill binding dependencies only accept route, policy, gate and budget refs"
            )

    @staticmethod
    def _skill_from_row(row: Any) -> SkillTemplateRevision:
        return SkillTemplateRevision(skill_id=row["skill_id"], revision=row["revision"],
            canonical_logic_id=row["canonical_logic_id"], lifecycle=row["lifecycle"],
            input_schema=row["input_schema"], output_schema=row["output_schema"],
            tool_allowlist=row["tool_allowlist"], required_capabilities=row["required_capabilities"],
            risk_level=row["risk_level"], eval_pack_ref=row["eval_pack_ref"],
            memory_policy_ref=row["memory_policy_ref"], handoff_policy_ref=row["handoff_policy_ref"],
            source_ref=row["source_ref"], source_license=row["source_license"],
            parent_ref=row.get("parent_ref"), publication_tenant=row.get("publication_tenant"),
            release_gate_ref=row.get("release_gate_ref"), publication_ref=row.get("publication_ref"),
            model_route_ref=row.get("model_route_ref"), runtime_policy_ref=row.get("runtime_policy_ref"),
            content_hash=row["content_hash"], created_by=row["created_by"], created_at=row["created_at"])

    @staticmethod
    def _skill_content(row: Any) -> dict[str, Any]:
        return AipSkillRegistry._skill_from_row(row).model_dump(mode="json", exclude={"created_by", "created_at"})

    @staticmethod
    def _binding_from_row(scope: TenantScope, row: Any) -> SkillBinding:
        if row is None:
            raise AipAgentRegistryNotFound("skill binding not found")
        return SkillBinding(tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
            binding_id=row["binding_id"], instance_id=row["instance_id"],
            skill=VersionedAssetRef(asset_type="SkillTemplate", asset_id=row["skill_id"],
                revision=row["skill_revision"], content_hash=row["content_hash"]),
            capability_binding_ids=row["capability_refs"], budget_policy_ref=row["budget_policy_ref"],
            dependencies=AipSkillRegistry._dependencies_from_row(row),
            readiness=row["readiness"], readiness_reasons=row["readiness_reasons"],
            dependency_snapshot_hash=row["dependency_snapshot_hash"],
            last_evaluated_at=row["last_evaluated_at"],
            readiness_expires_at=row["readiness_expires_at"],
            status=row["status"], version=row["version"], created_at=row["created_at"], updated_at=row["updated_at"])

    @staticmethod
    def _dependencies_from_row(row: Any) -> OperationalBindingDependencies:
        return OperationalBindingDependencies(
            model_route_ref=row["model_route_ref"],
            runtime_policy_ref=row["runtime_policy_ref"],
            eval_gate_ref=row["eval_gate_ref"],
            budget_policy_ref=row["budget_policy_ref"],
        )

    @staticmethod
    def _readiness_from_row(row: Any) -> OperationalBindingReadiness:
        if row is None or row["dependency_snapshot_hash"] is None:
            raise AipAgentRegistryTransitionBlocked(
                "skill binding has not been evaluated"
            )
        return OperationalBindingReadiness(
            readiness=row["readiness"],
            reasons=row["readiness_reasons"],
            dependencies=AipSkillRegistry._dependencies_from_row(row),
            dependency_snapshot_hash=row["dependency_snapshot_hash"],
            evaluated_at=row["last_evaluated_at"],
            expires_at=row["readiness_expires_at"],
        )
