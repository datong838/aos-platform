"""Read-only AIP-7 model route readiness resolver.

Resolution never calls a provider and never changes AgentRun state.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_eval_authority_store import (
    AipEvalAuthorityStore,
    AipEvalGateDependencyBlocked,
)
from aos_api.aip_model_eval_authorization import ModelEvalPreflight
from aos_api.aip_model_runtime_contracts import (
    ModelRouteResolution,
    ModelRuntimeLifecycle,
    ModelRuntimeReadiness,
    RouteStrategy,
)
from aos_api.aip_model_runtime_store import (
    AipModelRuntimeStore,
    ModelRuntimeStoreError,
    evaluation_candidate_ref,
)
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope

if TYPE_CHECKING:
    from aos_api.aip_model_route_eval_proof_authority import RouteEvalReleaseEvidence


class AipModelRuntimeResolver:
    def __init__(self, store: AipModelRuntimeStore | None = None) -> None:
        self._store = store or AipModelRuntimeStore()
        self._connect_factory = getattr(self._store, "_connect_factory", db_connect)
        self._eval_authority_store = getattr(self._store, "_eval_authority_store", None) or AipEvalAuthorityStore(self._connect_factory)

    def preflight_model_evaluation(
        self, scope: TenantScope, source_ref: VersionedAssetRef,
        target_ref: VersionedAssetRef, *, expected_head_version: int,
        now: datetime | None = None,
    ) -> ModelEvalPreflight:
        """Recheck a current Model candidate without granting execution.

        These reads may span transactions. GT-b must recheck under its own
        approval/intent transaction; this object cannot authorize transport.
        """
        if (type(scope) is not TenantScope
            or type(source_ref) is not VersionedAssetRef
            or type(target_ref) is not VersionedAssetRef
            or type(expected_head_version) is not int
            or expected_head_version < 1):
            raise ValueError("exact Model evaluation candidate required")
        checked_at = now or datetime.now(UTC)
        if checked_at.utcoffset() is None:
            raise ValueError("timezone-aware Model evaluation clock required")
        matching = [item for item in self._store.list_eval_candidates(scope)
                    if item.source_ref == source_ref
                    and item.target_ref == target_ref
                    and item.expected_head_version == expected_head_version]
        if len(matching) != 1 or source_ref.asset_type != "RegisteredModelRevision":
            raise ValueError("current exact Model evaluation candidate unavailable")
        candidate = matching[0]
        try:
            model = self._store.get_model(scope, source_ref.asset_id, source_ref.revision)
        except ModelRuntimeStoreError as exc:
            raise ValueError("current Model evaluation source unavailable") from exc
        if ((model.tenant.org_id, model.tenant.project_id) != scope.key
            or model.registered_model_id != source_ref.asset_id
            or model.revision != source_ref.revision
            or model.content_hash != source_ref.content_hash
            or model.lifecycle.value != candidate.source_lifecycle
            or model.lifecycle not in {ModelRuntimeLifecycle.DRAFT, ModelRuntimeLifecycle.VALIDATED}
            or evaluation_candidate_ref(model.model_copy(update={
                "revision": model.revision + 1,
                "lifecycle": ModelRuntimeLifecycle.ACTIVE,
                "eval_gate_ref": None,
            })) != target_ref):
            raise ValueError("Model evaluation source or next-active target drifted")

        blockers = ["eval_approval_missing", "budget_capacity_unverified",
                    "provider_transport_unverified"]
        provider_ref, price_ref = model.provider, model.price_snapshot_ref
        try:
            provider = self._store.get_provider(scope, provider_ref.asset_id, provider_ref.revision)
        except ModelRuntimeStoreError:
            blockers.append("provider_unavailable")
        else:
            if ((provider.tenant.org_id, provider.tenant.project_id) != scope.key
                or provider.provider_instance_id != provider_ref.asset_id
                or provider.revision != provider_ref.revision
                or provider.content_hash != provider_ref.content_hash):
                blockers.append("provider_drifted")
            if provider.lifecycle is not ModelRuntimeLifecycle.ACTIVE:
                blockers.append("provider_not_active")
        try:
            price = self._store.get_price_snapshot(scope, price_ref.asset_id, price_ref.revision)
        except ModelRuntimeStoreError:
            blockers.append("model_price_snapshot_unavailable")
        else:
            if ((price.tenant.org_id, price.tenant.project_id) != scope.key
                or price.price_snapshot_id != price_ref.asset_id
                or price.revision != price_ref.revision
                or price.content_hash != price_ref.content_hash):
                blockers.append("model_price_snapshot_drifted")
            if price.lifecycle is not ModelRuntimeLifecycle.ACTIVE:
                blockers.append("model_price_snapshot_not_active")
            if (price.effective_from > checked_at
                or (price.effective_until is not None
                    and price.effective_until <= checked_at)):
                blockers.append("model_price_snapshot_not_effective")
            try:
                self._store.require_model_governance(scope, model, price, now=checked_at)
            except ModelRuntimeStoreError:
                blockers.append("model_governance_policy_blocked")
        try:
            if not self._health_is_fresh(scope, provider_ref, checked_at):
                blockers.append("provider_health_unavailable_or_stale")
        except Exception:
            blockers.append("provider_health_unavailable_or_stale")
        return ModelEvalPreflight(
            tenant={"orgId": scope.org_id, "projectId": scope.project_id},
            sourceRef=source_ref, targetRef=target_ref,
            expectedHeadVersion=expected_head_version,
            providerRef=provider_ref, priceRef=price_ref,
            quotaPolicyRef=model.quota_policy_ref,
            budgetPolicyRef=model.budget_policy_ref,
            checkedAt=checked_at, blockerCodes=list(dict.fromkeys(blockers)),
        )

    def resolve(
        self, scope: TenantScope, route_id: str, *, now: datetime | None = None,
        route_evidence: RouteEvalReleaseEvidence | None = None,
    ) -> ModelRouteResolution:
        return self._resolve(scope, route_id, now=now, route_evidence=route_evidence)

    def revalidate_selection(
        self, scope: TenantScope, selection: ModelRouteResolution, *,
        now: datetime | None = None,
        route_evidence: RouteEvalReleaseEvidence | None = None,
    ) -> ModelRouteResolution:
        """Recheck a saved identity, never choose an alternative or grant admission.

        Reads retain the original non-atomic resolution semantics. The original
        invoker must still enforce its current execution dependencies.
        """
        checked_at = datetime.now(UTC) if now is None else now
        if (type(scope) is not TenantScope
            or type(selection) is not ModelRouteResolution
            or getattr(selection, "readiness", None) is not ModelRuntimeReadiness.READY
            or getattr(selection, "blocker_codes", None) != []
            or (getattr(getattr(selection, "tenant", None), "org_id", None),
                getattr(getattr(selection, "tenant", None), "project_id", None)) != scope.key
            or not isinstance(checked_at, datetime)
            or checked_at.utcoffset() is None
            or not isinstance(getattr(selection, "resolved_at", None), datetime)
            or selection.resolved_at.utcoffset() is None
            or selection.resolved_at > checked_at):
            raise ValueError("exact saved selection required")
        refs = tuple(getattr(selection, name, None) for name in (
            "route", "policy", "selected_model", "selected_provider", "selected_price_snapshot"))
        if any(type(ref) is not VersionedAssetRef
               or type(ref.revision) is not int or ref.revision < 1 for ref in refs):
            raise ValueError("exact saved selection required")
        snapshot = ModelRouteResolution.model_validate(
            selection.model_dump(mode="json", by_alias=True)
        )
        return self._resolve(
            scope, snapshot.route.asset_id, now=checked_at,
            expected_selection=snapshot, route_evidence=route_evidence,
        )

    def _resolve(
        self, scope: TenantScope, route_id: str, *, now: datetime | None = None,
        expected_selection: ModelRouteResolution | None = None,
        route_evidence: RouteEvalReleaseEvidence | None = None,
    ) -> ModelRouteResolution:
        resolved_at = now or datetime.now(UTC)
        route = self._store.get_route(scope, route_id)
        route_ref = self._ref("ModelRouteRevision", route.route_id, route.revision, route.content_hash)
        policy_ref = route.runtime_policy_ref
        blockers: list[str] = []
        if expected_selection is not None and (
            route_ref != expected_selection.route
            or policy_ref != expected_selection.policy
            or (route.tenant.org_id, route.tenant.project_id) != scope.key
        ):
            blockers.append("saved_route_selection_drifted")
        if route.lifecycle is not ModelRuntimeLifecycle.ACTIVE:
            blockers.append("route_not_active")
        try:
            policy = self._store.get_policy(scope, policy_ref.asset_id, policy_ref.revision)
            if expected_selection is not None and (
                (policy.tenant.org_id, policy.tenant.project_id) != scope.key
                or self._ref("RuntimePolicyRevision", policy.policy_id,
                             policy.revision, policy.content_hash) != expected_selection.policy
            ):
                blockers.append("saved_policy_selection_drifted")
            if policy.content_hash != policy_ref.content_hash:
                blockers.append("runtime_policy_drifted")
            elif policy.lifecycle is not ModelRuntimeLifecycle.ACTIVE:
                blockers.append("runtime_policy_not_active")
            if policy.kill_switch_enabled:
                blockers.append("runtime_policy_kill_switch")
        except ModelRuntimeStoreError:
            blockers.append("runtime_policy_unavailable")

        route_target = evaluation_candidate_ref(route)
        route_gate_passed = (
            self._gate_passed(
                scope, route.eval_gate_ref, route_target, resolved_at,
                route_evidence=route_evidence,
            )
            if route_evidence is not None
            else self._gate_passed(
                scope, route.eval_gate_ref, route_target, resolved_at,
            )
        )
        if not route_gate_passed:
            blockers.append("route_eval_gate_not_passed")

        selected_model = None
        selected_provider = None
        selected_price_snapshot = None
        candidates = route.candidates
        if expected_selection is not None:
            candidates = [candidate for candidate in route.candidates
                          if candidate.model == expected_selection.selected_model]
            if len(candidates) != 1 or (
                route.strategy is RouteStrategy.WEIGHTED and candidates[0].weight == 0
            ):
                blockers.append("saved_route_candidate_unavailable")
                candidates = []
        for candidate in candidates:
            candidate_blockers, model_ref, provider_ref, price_ref = self._candidate(scope, candidate.model, route, resolved_at)
            if expected_selection is not None and (
                model_ref != expected_selection.selected_model
                or provider_ref != expected_selection.selected_provider
                or price_ref != expected_selection.selected_price_snapshot
            ):
                candidate_blockers.append("saved_model_selection_drifted")
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
        exact_model = self._ref("RegisteredModelRevision", model.registered_model_id, model.revision, model.content_hash)
        if not self._gate_passed(
            scope, model.eval_gate_ref, evaluation_candidate_ref(model), now
        ):
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
            else:
                try:
                    self._store.require_model_governance(scope, model, price, now=now)
                except ModelRuntimeStoreError:
                    blockers.append("model_governance_policy_blocked")
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
        return blockers, exact_model, provider_ref, price_ref

    @staticmethod
    def _ref(kind: str, asset_id: str, revision: int, content_hash: str) -> VersionedAssetRef:
        return VersionedAssetRef(assetType=kind, assetId=asset_id, revision=revision, contentHash=content_hash)

    def _gate_passed(
        self,
        scope: TenantScope,
        ref: VersionedAssetRef,
        expected_target: VersionedAssetRef,
        now: datetime,
        *,
        route_evidence: RouteEvalReleaseEvidence | None = None,
    ) -> bool:
        try:
            kwargs = {"expected_target": expected_target, "now": now}
            if (route_evidence is not None
                and expected_target.asset_type == "ModelRouteRevision"):
                kwargs["route_evidence"] = route_evidence
            self._eval_authority_store.require_exact_passed(scope, ref, **kwargs)
        except AipEvalGateDependencyBlocked:
            return False
        return True

    def _health_is_fresh(self, scope: TenantScope, provider_ref: VersionedAssetRef, now: datetime) -> bool:
        with self._connect_factory(scope) as conn:
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
