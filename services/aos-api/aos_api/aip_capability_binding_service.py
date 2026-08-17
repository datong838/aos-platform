"""Tenant-scoped AIP-6 CapabilityBinding lifecycle; secrets remain opaque refs."""
from __future__ import annotations

from datetime import UTC, datetime

from aos_api.aip_agent_registry_contracts import (
    BindingHealth,
    CapabilityBinding,
    CapabilityReadiness,
    CreateCapabilityBindingRequest,
    EvaluateOperationalBindingRequest,
    OperationalBindingDependencies,
    OperationalBindingReadiness,
    RegistryReceipt,
    UpdateCapabilityBindingRequest,
)
from aos_api.aip_agent_registry_store import (
    AipAgentRegistryConflict,
    AipAgentRegistryNotFound,
    AipAgentRegistryPersistenceError,
    AipAgentRegistryStore,
    AipAgentRegistryTransitionBlocked,
)
from aos_api.aip_binding_api_contracts import CapabilityBindingPreviewRequest
from aos_api.aip_binding_readiness_service import AipBindingReadinessService
from aos_api.aip_contracts import TenantContext
from aos_api.tenant_scope import TenantScope

_TRANSITIONS = {
    "provisioning": {"active", "revoked"},
    "active": {"suspended", "revoked"},
    "suspended": {"active", "revoked"},
    "revoked": set(),
}


class AipCapabilityBindingService(AipAgentRegistryStore):
    def __init__(self, connect_factory=None, *, readiness_service: AipBindingReadinessService | None = None) -> None:
        super().__init__(connect_factory)
        self._readiness_service = readiness_service or AipBindingReadinessService()

    def preview(
        self,
        scope: TenantScope,
        request: CapabilityBindingPreviewRequest,
        *,
        evaluated_at: datetime,
    ) -> OperationalBindingReadiness:
        return self._readiness_service.evaluate_capability(
            scope,
            request.capability,
            request.dependencies,
            evaluated_at=evaluated_at,
        )

    def create(self, scope: TenantScope, request: CreateCapabilityBindingRequest, *, idempotency_key: str, actor: str, occurred_at: datetime) -> tuple[CapabilityBinding, RegistryReceipt]:
        self._validate_command(scope, idempotency_key, actor)
        operation = "capability_binding.create"
        request_hash = self._command_hash(request, actor)
        try:
            with self._connect_factory(scope) as conn:
                self._lock(conn, scope, operation, idempotency_key)
                replay = self._receipt_row(conn, scope, operation, idempotency_key)
                if replay:
                    self._require_replay_hash(replay, request_hash)
                    return self._from_row(scope, self._row(conn, scope, request.binding_id)), self._receipt_from_row(scope, replay)
                if self._row(conn, scope, request.binding_id):
                    raise AipAgentRegistryConflict("capability binding id already exists")
                binding = request.binding
                capability = conn.execute(
                    """SELECT lifecycle FROM aip_capability_revision
                       WHERE capability_id=%s AND revision=%s AND content_hash=%s""",
                    (
                        binding.capability.asset_id,
                        binding.capability.revision,
                        binding.capability.content_hash,
                    ),
                ).fetchone()
                if capability is None:
                    raise AipAgentRegistryNotFound(
                        "exact capability revision not found"
                    )
                if capability["lifecycle"] != "published":
                    raise AipAgentRegistryTransitionBlocked(
                        "only published capability revisions can be bound"
                    )
                row = conn.execute(
                    """INSERT INTO aip_capability_binding
                       (org_id,project_id,binding_id,capability_ref,secret_ref,health,
                        network_policy_revision,quota_policy_revision,timeout_ms,
                        max_concurrency,status,version,created_at,updated_at)
                       VALUES (%s,%s,%s,%s::jsonb,%s,'unknown',%s,%s,%s,%s,
                        'provisioning',1,%s,%s) RETURNING *""",
                    (*scope.key, request.binding_id, self._json(binding.capability),
                     binding.secret_ref, binding.network_policy_revision,
                     binding.quota_policy_revision, binding.timeout_ms,
                     binding.max_concurrency, occurred_at, occurred_at),
                ).fetchone()
                receipt = self._insert_receipt(conn, scope, operation, idempotency_key,
                    request_hash, "Capability", binding.capability.asset_id,
                    "CapabilityBinding", request.binding_id, actor, occurred_at)
                conn.commit()
                return self._from_row(scope, row), receipt
        except (
            AipAgentRegistryConflict,
            AipAgentRegistryNotFound,
            AipAgentRegistryTransitionBlocked,
        ):
            raise
        except Exception as exc:
            raise AipAgentRegistryPersistenceError("capability binding persistence failed") from exc

    def update(self, scope: TenantScope, binding_id: str, request: UpdateCapabilityBindingRequest, *, idempotency_key: str, actor: str) -> tuple[CapabilityBinding, RegistryReceipt]:
        self._validate_command(scope, idempotency_key, actor)
        if request.to_status not in _TRANSITIONS[request.from_status]:
            raise AipAgentRegistryTransitionBlocked("capability binding transition is not allowed")
        if request.to_status == "active" and request.health is not BindingHealth.HEALTHY:
            raise AipAgentRegistryTransitionBlocked("only healthy capability bindings can be active")
        operation = "capability_binding.update"
        request_hash = self._command_hash(request, actor)
        try:
            with self._connect_factory(scope) as conn:
                self._lock(conn, scope, operation, idempotency_key)
                replay = self._receipt_row(conn, scope, operation, idempotency_key)
                if replay:
                    self._require_replay_hash(replay, request_hash)
                    return self._from_row(scope, self._row(conn, scope, binding_id)), self._receipt_from_row(scope, replay)
                if request.to_status == "active":
                    binding_row = self._row(conn, scope, binding_id)
                    if binding_row is None:
                        raise AipAgentRegistryNotFound("capability binding not found")
                    readiness = binding_row["operational_readiness"]
                    allow_degraded = bool(binding_row["allow_degraded"])
                    usable = readiness == CapabilityReadiness.AVAILABLE.value or (
                        readiness == CapabilityReadiness.DEGRADED.value and allow_degraded
                    )
                    decision_at = datetime.now(UTC)
                    if (
                        not usable
                        or binding_row["dependency_snapshot_hash"] is None
                        or binding_row["readiness_expires_at"] is None
                        or binding_row["readiness_expires_at"] <= decision_at
                    ):
                        raise AipAgentRegistryTransitionBlocked(
                            "fresh operational binding readiness does not allow activation"
                        )
                    recomputed = self._readiness_service.evaluate_capability(
                        scope,
                        self._from_row(scope, binding_row).capability,
                        self._dependencies_from_row(binding_row),
                        evaluated_at=decision_at,
                    )
                    recomputed_usable = (
                        recomputed.readiness is CapabilityReadiness.AVAILABLE
                        or (
                            recomputed.readiness is CapabilityReadiness.DEGRADED
                            and allow_degraded
                        )
                    )
                    if (
                        not recomputed_usable
                        or recomputed.dependency_snapshot_hash
                        != binding_row["dependency_snapshot_hash"]
                    ):
                        raise AipAgentRegistryTransitionBlocked(
                            "operational dependency snapshot drifted before activation"
                        )
                row = conn.execute(
                    """UPDATE aip_capability_binding SET status=%s,health=%s,
                       observed_at=%s,version=version+1,updated_at=%s
                       WHERE org_id=%s AND project_id=%s AND binding_id=%s
                        AND version=%s AND status=%s RETURNING *""",
                    (request.to_status, request.health.value, request.observed_at,
                     request.observed_at, *scope.key, binding_id,
                     request.expected_version, request.from_status),
                ).fetchone()
                if row is None:
                    if self._row(conn, scope, binding_id) is None:
                        raise AipAgentRegistryNotFound("capability binding not found")
                    raise AipAgentRegistryConflict("capability binding version or status changed")
                receipt = self._insert_receipt(conn, scope, operation, idempotency_key,
                    request_hash, "CapabilityBinding", binding_id,
                    "CapabilityBinding", binding_id, actor, request.observed_at)
                conn.commit()
                return self._from_row(scope, row), receipt
        except (AipAgentRegistryConflict, AipAgentRegistryNotFound, AipAgentRegistryTransitionBlocked):
            raise
        except Exception as exc:
            raise AipAgentRegistryPersistenceError("capability binding update failed") from exc

    def evaluate(
        self,
        scope: TenantScope,
        binding_id: str,
        request: EvaluateOperationalBindingRequest,
        *,
        idempotency_key: str,
        actor: str,
        evaluated_at: datetime,
    ) -> tuple[CapabilityBinding, OperationalBindingReadiness, RegistryReceipt]:
        """Persist a short-lived, exact dependency snapshot without activating it."""
        self._validate_command(scope, idempotency_key, actor)
        current = self.get(scope, binding_id)
        result = self._readiness_service.evaluate_capability(
            scope, current.capability, request.dependencies, evaluated_at=evaluated_at
        )
        if (
            request.expected_dependency_snapshot_hash is not None
            and request.expected_dependency_snapshot_hash != result.dependency_snapshot_hash
        ):
            raise AipAgentRegistryConflict("dependency snapshot hash changed")
        operation = "capability_binding.evaluate"
        request_hash = self._command_hash(request, actor)
        deps = result.dependencies
        try:
            with self._connect_factory(scope) as conn:
                self._lock(conn, scope, operation, idempotency_key)
                replay = self._receipt_row(conn, scope, operation, idempotency_key)
                if replay:
                    self._require_replay_hash(replay, request_hash)
                    row = self._row(conn, scope, binding_id)
                    return (
                        self._from_row(scope, row),
                        self._readiness_from_row(row),
                        self._receipt_from_row(scope, replay),
                    )
                row = conn.execute(
                    """UPDATE aip_capability_binding SET
                       provider_ref=%s::jsonb,model_route_ref=%s::jsonb,
                       runtime_policy_ref=%s::jsonb,eval_gate_ref=%s::jsonb,
                       eval_contract_ref=%s::jsonb,license_evidence_refs=%s::jsonb,
                       data_dependency_refs=%s::jsonb,tool_dependency_refs=%s::jsonb,
                       budget_policy_ref=%s::jsonb,allow_degraded=%s,
                       dependency_snapshot_hash=%s,operational_readiness=%s,
                       readiness_reasons=%s::jsonb,last_evaluated_at=%s,
                       readiness_expires_at=%s,version=version+1,updated_at=%s
                       WHERE org_id=%s AND project_id=%s AND binding_id=%s
                         AND version=%s AND status IN ('provisioning','suspended')
                       RETURNING *""",
                    (
                        self._json(deps.provider_ref) if deps.provider_ref else None,
                        self._json(deps.model_route_ref) if deps.model_route_ref else None,
                        self._json(deps.runtime_policy_ref) if deps.runtime_policy_ref else None,
                        self._json(deps.eval_gate_ref) if deps.eval_gate_ref else None,
                        self._json(deps.eval_contract_ref) if deps.eval_contract_ref else None,
                        self._json(deps.license_evidence_refs),
                        self._json(deps.data_dependency_refs),
                        self._json(deps.tool_dependency_refs),
                        self._json(deps.budget_policy_ref) if deps.budget_policy_ref else None,
                        deps.allow_degraded,
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
                    existing = self._row(conn, scope, binding_id)
                    if existing is None:
                        raise AipAgentRegistryNotFound("capability binding not found")
                    raise AipAgentRegistryConflict(
                        "capability binding version or lifecycle changed"
                    )
                receipt = self._insert_receipt(
                    conn,
                    scope,
                    operation,
                    idempotency_key,
                    request_hash,
                    "CapabilityBinding",
                    binding_id,
                    "CapabilityBindingReadiness",
                    binding_id,
                    actor,
                    evaluated_at,
                )
                conn.commit()
                return self._from_row(scope, row), result, receipt
        except (AipAgentRegistryConflict, AipAgentRegistryNotFound):
            raise
        except Exception as exc:
            raise AipAgentRegistryPersistenceError(
                "capability binding evaluation failed"
            ) from exc

    def get(self, scope: TenantScope, binding_id: str) -> CapabilityBinding:
        with self._connect_factory(scope) as conn:
            row = self._row(conn, scope, binding_id)
        if row is None:
            raise AipAgentRegistryNotFound("capability binding not found")
        return self._from_row(scope, row)

    def list_bindings(
        self,
        scope: TenantScope,
        *,
        limit: int = 100,
    ) -> list[CapabilityBinding]:
        if limit < 1 or limit > 200:
            raise ValueError("list limit must be between 1 and 200")
        try:
            with self._connect_factory(scope) as conn:
                rows = conn.execute(
                    """SELECT * FROM aip_capability_binding
                       WHERE org_id=%s AND project_id=%s
                       ORDER BY updated_at DESC,binding_id LIMIT %s""",
                    (*scope.key, limit),
                ).fetchall()
            return [self._from_row(scope, row) for row in rows]
        except Exception as exc:
            raise AipAgentRegistryPersistenceError(
                "capability binding list failed"
            ) from exc

    @staticmethod
    def _row(conn, scope: TenantScope, binding_id: str):
        return conn.execute("""SELECT * FROM aip_capability_binding
            WHERE org_id=%s AND project_id=%s AND binding_id=%s""",
            (*scope.key, binding_id)).fetchone()

    @staticmethod
    def _from_row(scope: TenantScope, row) -> CapabilityBinding:
        if row is None:
            raise AipAgentRegistryNotFound("capability binding not found")
        return CapabilityBinding(tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
            binding_id=row["binding_id"], capability=row["capability_ref"], secret_ref=row["secret_ref"],
            health=row["health"], network_policy_revision=row["network_policy_revision"],
            quota_policy_revision=row["quota_policy_revision"], timeout_ms=row["timeout_ms"],
            max_concurrency=row["max_concurrency"], dependencies=AipCapabilityBindingService._dependencies_from_row(row),
            operational_readiness=row["operational_readiness"], readiness_reasons=row["readiness_reasons"],
            dependency_snapshot_hash=row["dependency_snapshot_hash"], last_evaluated_at=row["last_evaluated_at"],
            readiness_expires_at=row["readiness_expires_at"], status=row["status"], version=row["version"],
            observed_at=row["observed_at"], created_at=row["created_at"], updated_at=row["updated_at"])

    @staticmethod
    def _dependencies_from_row(row) -> OperationalBindingDependencies:
        return OperationalBindingDependencies(
            provider_ref=row["provider_ref"],
            model_route_ref=row["model_route_ref"],
            runtime_policy_ref=row["runtime_policy_ref"],
            eval_gate_ref=row["eval_gate_ref"],
            eval_contract_ref=row["eval_contract_ref"],
            license_evidence_refs=row["license_evidence_refs"],
            data_dependency_refs=row["data_dependency_refs"],
            tool_dependency_refs=row["tool_dependency_refs"],
            budget_policy_ref=row["budget_policy_ref"],
            allow_degraded=row["allow_degraded"],
        )

    @staticmethod
    def _readiness_from_row(row) -> OperationalBindingReadiness:
        if row is None or row["dependency_snapshot_hash"] is None:
            raise AipAgentRegistryTransitionBlocked(
                "capability binding has not been evaluated"
            )
        return OperationalBindingReadiness(
            readiness=row["operational_readiness"],
            reasons=row["readiness_reasons"],
            dependencies=AipCapabilityBindingService._dependencies_from_row(row),
            dependency_snapshot_hash=row["dependency_snapshot_hash"],
            evaluated_at=row["last_evaluated_at"],
            expires_at=row["readiness_expires_at"],
        )
