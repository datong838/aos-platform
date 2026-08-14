"""Read-only AIP-7 model route readiness resolver.

Resolution never calls a provider and never changes AgentRun state.
"""
from __future__ import annotations

from datetime import UTC, datetime

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_eval_contracts import ReleaseGateStatus
from aos_api.aip_model_runtime_contracts import (
    ModelRouteResolution,
    ModelRuntimeLifecycle,
    ModelRuntimeReadiness,
)
from aos_api.aip_model_runtime_store import AipModelRuntimeStore, ModelRuntimeStoreError
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope


class AipModelRuntimeResolver:
    def __init__(self, store: AipModelRuntimeStore | None = None) -> None:
        self._store = store or AipModelRuntimeStore()

    def resolve(self, scope: TenantScope, route_id: str, *, now: datetime | None = None) -> ModelRouteResolution:
        resolved_at = now or datetime.now(UTC)
        route = self._store.get_route(scope, route_id)
        route_ref = self._ref("ModelRouteRevision", route.route_id, route.revision, route.content_hash)
        policy_ref = route.runtime_policy_ref
        blockers: list[str] = []
        if route.lifecycle is not ModelRuntimeLifecycle.ACTIVE:
            blockers.append("route_not_active")
        try:
            policy = self._store.get_policy(scope, policy_ref.asset_id, policy_ref.revision)
            if policy.content_hash != policy_ref.content_hash:
                blockers.append("runtime_policy_drifted")
            elif policy.lifecycle is not ModelRuntimeLifecycle.ACTIVE:
                blockers.append("runtime_policy_not_active")
            if policy.kill_switch_enabled:
                blockers.append("runtime_policy_kill_switch")
        except ModelRuntimeStoreError:
            blockers.append("runtime_policy_unavailable")

        if not self._gate_passed(scope, route.eval_gate_ref):
            blockers.append("route_eval_gate_not_passed")

        selected_model = None
        selected_provider = None
        selected_price_snapshot = None
        for candidate in route.candidates:
            candidate_blockers, model_ref, provider_ref, price_ref = self._candidate(scope, candidate.model, route, resolved_at)
            if not candidate_blockers:
                selected_model = model_ref
                selected_provider = provider_ref
                selected_price_snapshot = price_ref
                break
            blockers.extend(candidate_blockers)

        blockers = list(dict.fromkeys(blockers))
        if blockers or selected_model is None or selected_provider is None or selected_price_snapshot is None:
            return ModelRouteResolution(
                tenant={"orgId": scope.org_id, "projectId": scope.project_id},
                route=route_ref, policy=policy_ref, readiness=ModelRuntimeReadiness.BLOCKED,
                blockerCodes=blockers or ["no_route_candidate_ready"], resolvedAt=resolved_at,
            )
        return ModelRouteResolution(
            tenant={"orgId": scope.org_id, "projectId": scope.project_id},
            route=route_ref, policy=policy_ref, readiness=ModelRuntimeReadiness.READY,
            selectedModel=selected_model, selectedProvider=selected_provider,
            selectedPriceSnapshot=selected_price_snapshot, resolvedAt=resolved_at,
        )

    def _candidate(self, scope: TenantScope, model_ref: VersionedAssetRef, route, now: datetime):
        blockers: list[str] = []
        try:
            model = self._store.get_model(scope, model_ref.asset_id, model_ref.revision)
        except ModelRuntimeStoreError:
            return ["model_unavailable"], None, None, None
        if model.content_hash != model_ref.content_hash:
            blockers.append("model_drifted")
        if model.lifecycle is not ModelRuntimeLifecycle.ACTIVE:
            blockers.append("model_not_active")
        if route.required_input_modality not in model.input_modalities or route.required_output_modality not in model.output_modalities:
            blockers.append("model_modality_mismatch")
        if not set(route.required_capabilities).issubset(model.capabilities):
            blockers.append("model_capability_mismatch")
        if not self._gate_passed(scope, model.eval_gate_ref):
            blockers.append("model_eval_gate_not_passed")
        price_ref = model.price_snapshot_ref
        try:
            price = self._store.get_price_snapshot(
                scope, model.price_snapshot_ref.asset_id, model.price_snapshot_ref.revision
            )
            if price.content_hash != model.price_snapshot_ref.content_hash:
                blockers.append("model_price_snapshot_drifted")
            elif price.lifecycle is not ModelRuntimeLifecycle.ACTIVE:
                blockers.append("model_price_snapshot_not_active")
            elif price.effective_from > now or (
                price.effective_until is not None and price.effective_until <= now
            ):
                blockers.append("model_price_snapshot_not_effective")
        except ModelRuntimeStoreError:
            blockers.append("model_price_snapshot_unavailable")
        provider_ref = model.provider
        try:
            provider = self._store.get_provider(scope, provider_ref.asset_id, provider_ref.revision)
            if provider.content_hash != provider_ref.content_hash:
                blockers.append("provider_drifted")
            if provider.lifecycle is not ModelRuntimeLifecycle.ACTIVE:
                blockers.append("provider_not_active")
        except ModelRuntimeStoreError:
            blockers.append("provider_unavailable")
        if not self._health_is_fresh(scope, provider_ref, now):
            blockers.append("provider_health_unavailable_or_stale")
        exact_model = self._ref("RegisteredModelRevision", model.registered_model_id, model.revision, model.content_hash)
        return blockers, exact_model, provider_ref, price_ref

    @staticmethod
    def _ref(kind: str, asset_id: str, revision: int, content_hash: str) -> VersionedAssetRef:
        return VersionedAssetRef(assetType=kind, assetId=asset_id, revision=revision, contentHash=content_hash)

    @staticmethod
    def _gate_passed(scope: TenantScope, ref: VersionedAssetRef) -> bool:
        if ref.asset_type != "EvalGateDecision":
            return False
        with db_connect(scope) as conn:
            row = conn.execute(
                "SELECT status,decision_hash FROM aip_release_gate_decision WHERE org_id=%s AND project_id=%s AND decision_id=%s",
                (*scope.key, ref.asset_id),
            ).fetchone()
            return bool(row and row["status"] == ReleaseGateStatus.PASSED.value and row["decision_hash"] == ref.content_hash)

    @staticmethod
    def _health_is_fresh(scope: TenantScope, provider_ref: VersionedAssetRef, now: datetime) -> bool:
        with db_connect(scope) as conn:
            row = conn.execute(
                """SELECT status,provider_ref,expires_at FROM aip_provider_health_observation
                WHERE org_id=%s AND project_id=%s AND provider_ref->>'assetId'=%s
                ORDER BY observed_at DESC LIMIT 1""",
                (*scope.key, provider_ref.asset_id),
            ).fetchone()
            return bool(
                row and row["status"] == "healthy" and row["expires_at"] > now
                and row["provider_ref"].get("revision") == provider_ref.revision
                and row["provider_ref"].get("contentHash") == provider_ref.content_hash
            )
