"""Fail-closed operational readiness for tenant capability bindings.

Catalog readiness describes whether an immutable Capability revision may be
offered.  This module separately proves whether one tenant binding has the
exact runtime dependencies required to execute it now.
"""
from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime, timedelta
import json
from typing import Any, Protocol

from aos_api.aip_agent_registry_contracts import (
    CapabilityReadiness,
    OperationalBindingDependencies,
    OperationalBindingReadiness,
    VersionedAssetRef,
)
from aos_api.aip_contracts import ResourceRef
from aos_api.aip_model_runtime_contracts import ModelRuntimeReadiness
from aos_api.aip_model_runtime_resolver import AipModelRuntimeResolver
from aos_api.aip_model_runtime_store import AipModelRuntimeStore, ModelRuntimeStoreError
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope

ConnectFactory = Callable[..., AbstractContextManager[Any]]


class BindingDependencyAuthority(Protocol):
    def capability(self, ref: VersionedAssetRef) -> Any | None: ...

    def eval_gate_passed(self, scope: TenantScope, ref: VersionedAssetRef) -> bool: ...

    def eval_contract_frozen(self, scope: TenantScope, ref: VersionedAssetRef) -> bool: ...

    def license_evidence_available(self, scope: TenantScope, refs: list[ResourceRef]) -> bool: ...

    def exact_assets_available(self, scope: TenantScope, refs: list[VersionedAssetRef]) -> bool: ...


class PostgresBindingDependencyAuthority:
    """Read existing authorities without creating another source of truth."""

    def __init__(self, connect_factory: ConnectFactory | None = None) -> None:
        self._connect_factory = connect_factory or db_connect

    def capability(self, ref: VersionedAssetRef):
        with self._connect_factory() as conn:
            return conn.execute(
                """SELECT lifecycle,content_hash,risk_level,required_data_refs,
                          required_tool_refs
                   FROM aip_capability_revision
                   WHERE capability_id=%s AND revision=%s""",
                (ref.asset_id, ref.revision),
            ).fetchone()

    def eval_gate_passed(self, scope: TenantScope, ref: VersionedAssetRef) -> bool:
        with self._connect_factory(scope) as conn:
            row = conn.execute(
                """SELECT status,decision_hash FROM aip_release_gate_decision
                   WHERE org_id=%s AND project_id=%s AND decision_id=%s""",
                (*scope.key, ref.asset_id),
            ).fetchone()
        return bool(row and row["status"] == "passed" and row["decision_hash"] == ref.content_hash)

    def eval_contract_frozen(self, scope: TenantScope, ref: VersionedAssetRef) -> bool:
        with self._connect_factory(scope) as conn:
            row = conn.execute(
                """SELECT lifecycle,content_hash FROM aip_eval_contract_revision
                   WHERE org_id=%s AND project_id=%s AND contract_id=%s AND revision=%s""",
                (*scope.key, ref.asset_id, ref.revision),
            ).fetchone()
        return bool(row and row["lifecycle"] == "frozen" and row["content_hash"] == ref.content_hash)

    def license_evidence_available(self, scope: TenantScope, refs: list[ResourceRef]) -> bool:
        if not refs:
            return False
        with self._connect_factory(scope) as conn:
            for ref in refs:
                if ref.resource_type != "EvidenceBundleRevision" or not ref.revision:
                    return False
                try:
                    revision = int(ref.revision)
                except ValueError:
                    return False
                row = conn.execute(
                    """SELECT lifecycle,license_summary FROM aip_evidence_bundle_revision
                       WHERE org_id=%s AND project_id=%s AND bundle_id=%s AND revision=%s""",
                    (*scope.key, ref.resource_id, revision),
                ).fetchone()
                if not row or row["lifecycle"] != "frozen" or not row["license_summary"]:
                    return False
        return True

    def exact_assets_available(self, scope: TenantScope, refs: list[VersionedAssetRef]) -> bool:
        """Verify exact refs where an AOS authority exists; unknown kinds fail closed."""
        if not refs:
            return True
        specs = {
            "EvalDatasetRevision": ("aip_eval_dataset_revision", "dataset_id"),
            "EvidenceBundleRevision": ("aip_evidence_bundle_revision", "bundle_id"),
        }
        with self._connect_factory(scope) as conn:
            for ref in refs:
                spec = specs.get(ref.asset_type)
                if spec is None:
                    return False
                table, id_column = spec
                row = conn.execute(
                    f"""SELECT content_hash FROM {table}
                        WHERE org_id=%s AND project_id=%s AND {id_column}=%s AND revision=%s""",
                    (*scope.key, ref.asset_id, ref.revision),
                ).fetchone()
                if not row or row["content_hash"] != ref.content_hash:
                    return False
        return True


class AipBindingReadinessService:
    """Aggregate exact dependency evidence into a short-lived snapshot."""

    def __init__(
        self,
        *,
        authority: BindingDependencyAuthority | None = None,
        model_resolver: AipModelRuntimeResolver | None = None,
        model_store: AipModelRuntimeStore | None = None,
        ttl: timedelta = timedelta(minutes=15),
    ) -> None:
        if ttl <= timedelta(0):
            raise ValueError("binding readiness ttl must be positive")
        self._authority = authority or PostgresBindingDependencyAuthority()
        self._model_store = model_store or AipModelRuntimeStore()
        self._model_resolver = model_resolver or AipModelRuntimeResolver(self._model_store)
        self._ttl = ttl

    def evaluate_capability(
        self,
        scope: TenantScope,
        capability_ref: VersionedAssetRef,
        dependencies: OperationalBindingDependencies,
        *,
        evaluated_at: datetime,
    ) -> OperationalBindingReadiness:
        reasons: list[str] = []
        capability = self._authority.capability(capability_ref)
        if (
            capability is None
            or capability["lifecycle"] != "published"
            or capability["content_hash"] != capability_ref.content_hash
        ):
            reasons.append("CAPABILITY_REVISION_UNAVAILABLE")

        route_resolution = None
        route_revision = None
        if dependencies.model_route_ref is None:
            reasons.append("MODEL_ROUTE_REF_MISSING")
        else:
            try:
                route_revision = self._model_store.get_route(
                    scope,
                    dependencies.model_route_ref.asset_id,
                    dependencies.model_route_ref.revision,
                )
                route_resolution = self._model_resolver.resolve(
                    scope, dependencies.model_route_ref.asset_id, now=evaluated_at
                )
            except ModelRuntimeStoreError:
                reasons.append("MODEL_ROUTE_BLOCKED")
            else:
                if (
                    route_revision.content_hash != dependencies.model_route_ref.content_hash
                    or route_resolution.route != dependencies.model_route_ref
                    or route_resolution.readiness is not ModelRuntimeReadiness.READY
                ):
                    reasons.append("MODEL_ROUTE_BLOCKED")

        if dependencies.provider_ref is None:
            reasons.append("PROVIDER_REF_MISSING")
        elif route_resolution is None or route_resolution.selected_provider != dependencies.provider_ref:
            reasons.append("PROVIDER_HEALTH_UNAVAILABLE")

        if dependencies.runtime_policy_ref is None:
            reasons.append("RUNTIME_POLICY_REF_MISSING")
        elif route_resolution is None or route_resolution.policy != dependencies.runtime_policy_ref:
            reasons.append("MODEL_ROUTE_BLOCKED")

        if dependencies.eval_gate_ref is None:
            reasons.append("EVAL_GATE_REF_MISSING")
        elif (
            route_revision is None
            or route_revision.eval_gate_ref != dependencies.eval_gate_ref
            or not self._authority.eval_gate_passed(scope, dependencies.eval_gate_ref)
        ):
            reasons.append("EVAL_GATE_BLOCKED")

        if dependencies.eval_contract_ref is None:
            reasons.append("EVAL_CONTRACT_REF_MISSING")
        elif not self._authority.eval_contract_frozen(scope, dependencies.eval_contract_ref):
            reasons.append("EVAL_CONTRACT_BLOCKED")

        if not self._authority.license_evidence_available(scope, dependencies.license_evidence_refs):
            reasons.append("LICENSE_EVIDENCE_MISSING")

        required_data = list(capability["required_data_refs"]) if capability else []
        required_tools = list(capability["required_tool_refs"]) if capability else []
        provided_data = {self._ref_key(ref) for ref in dependencies.data_dependency_refs}
        provided_tools = {self._ref_key(ref) for ref in dependencies.tool_dependency_refs}
        if any(self._ref_key(VersionedAssetRef.model_validate(ref)) not in provided_data for ref in required_data):
            reasons.append("DATA_DEPENDENCY_UNAVAILABLE")
        elif not self._authority.exact_assets_available(scope, dependencies.data_dependency_refs):
            reasons.append("DATA_DEPENDENCY_UNAVAILABLE")
        if any(self._ref_key(VersionedAssetRef.model_validate(ref)) not in provided_tools for ref in required_tools):
            reasons.append("TOOL_DEPENDENCY_UNAVAILABLE")
        elif not self._authority.exact_assets_available(scope, dependencies.tool_dependency_refs):
            reasons.append("TOOL_DEPENDENCY_UNAVAILABLE")

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
                ):
                    reasons.append("BUDGET_POLICY_MISSING")

        reasons = sorted(set(reasons))
        readiness = CapabilityReadiness.BLOCKED if reasons else CapabilityReadiness.AVAILABLE
        snapshot_hash = self.snapshot_hash(capability_ref, dependencies)
        return OperationalBindingReadiness(
            readiness=readiness,
            reasons=reasons,
            dependencies=dependencies,
            dependency_snapshot_hash=snapshot_hash,
            evaluated_at=evaluated_at,
            expires_at=evaluated_at + self._ttl,
        )

    @staticmethod
    def snapshot_hash(
        capability_ref: VersionedAssetRef,
        dependencies: OperationalBindingDependencies,
    ) -> str:
        from aos_api.aip_agent_registry_store import AipAgentRegistryStore

        serialized = dependencies.model_dump(mode="json", by_alias=True)
        for key in ("licenseEvidenceRefs", "dataDependencyRefs", "toolDependencyRefs"):
            serialized[key] = sorted(
                serialized[key],
                key=lambda value: json.dumps(
                    value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                ),
            )
        document = {
            "capability": capability_ref.model_dump(mode="json", by_alias=True),
            "dependencies": serialized,
        }
        return AipAgentRegistryStore._hash(document)

    @staticmethod
    def _ref_key(ref: VersionedAssetRef) -> tuple[str, str, int, str]:
        return ref.asset_type, ref.asset_id, ref.revision, ref.content_hash
