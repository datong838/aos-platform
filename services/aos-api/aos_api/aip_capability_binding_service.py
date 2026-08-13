"""Tenant-scoped AIP-6 CapabilityBinding lifecycle; secrets remain opaque refs."""
from __future__ import annotations

from datetime import datetime

from aos_api.aip_agent_registry_contracts import (
    BindingHealth,
    CapabilityBinding,
    CreateCapabilityBindingRequest,
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
from aos_api.aip_contracts import TenantContext
from aos_api.tenant_scope import TenantScope

_TRANSITIONS = {
    "provisioning": {"active", "revoked"},
    "active": {"suspended", "revoked"},
    "suspended": {"active", "revoked"},
    "revoked": set(),
}


class AipCapabilityBindingService(AipAgentRegistryStore):
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

    def get(self, scope: TenantScope, binding_id: str) -> CapabilityBinding:
        with self._connect_factory(scope) as conn:
            row = self._row(conn, scope, binding_id)
        if row is None:
            raise AipAgentRegistryNotFound("capability binding not found")
        return self._from_row(scope, row)

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
            max_concurrency=row["max_concurrency"], status=row["status"], version=row["version"],
            observed_at=row["observed_at"], created_at=row["created_at"], updated_at=row["updated_at"])
