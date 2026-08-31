"""AIP-7 canonical exact model runtime API."""
from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, Query, status
from pydantic import BaseModel, Field

from aos_api.aip_model_runtime_contracts import (
    ModelPriceAuthoritySummary, ModelPriceSnapshotRevision, ModelRouteResolution,
    ModelRouteRevision, ModelRuntimeCostOverview, ModelRuntimeLifecycle,
    ModelRuntimeOverview, ProviderHealthObservation, ProviderInstanceRevision,
    RegisteredModelRevision, RuntimeBudgetAuthoritySummary,
    RuntimePolicyRevision, RuntimeUsageAuthoritySummary,
)
from aos_api.aip_budget_contracts import BudgetLifecycle
from aos_api.aip_budget_store import AipBudgetAuthorityStore, BudgetNotFound
from aos_api.aip_eval_authority_store import (
    AipEvalAuthorityPersistenceError,
    AipEvalAuthorityStore,
)
from aos_api.aip_eval_contracts import EvidenceQuality, UsageKind
from aos_api.aip_model_governance_policy_contracts import (
    ModelGovernancePolicyLifecycle,
)
from aos_api.aip_model_governance_policy_store import (
    AipModelGovernancePolicyStore,
    ModelGovernancePolicyNotFound,
)
from aos_api.aip_provider_plugin_authority import (
    ProviderPluginAuthority,
    ProviderPluginAuthorityError,
    ProviderPluginRevision,
)
from aos_api.aip_model_runtime_resolver import AipModelRuntimeResolver
from aos_api.aip_model_runtime_store import (
    AipModelRuntimeStore, ModelRuntimeConflict, ModelRuntimeDependencyBlocked,
    ModelRuntimeIdempotencyConflict, ModelRuntimeNotFound, ModelRuntimeStoreError,
)
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.tenant_scope import TenantScope

router = APIRouter(prefix="/v1/aip/model-runtime", tags=["aip-model-runtime"])
_STORE = AipModelRuntimeStore()
_PLUGIN_AUTHORITY = ProviderPluginAuthority()
_EVAL_AUTHORITY_STORE = AipEvalAuthorityStore()
_BUDGET_AUTHORITY_STORE = AipBudgetAuthorityStore()
_POLICY_AUTHORITY_STORE = AipModelGovernancePolicyStore(
    budget_store=_BUDGET_AUTHORITY_STORE
)


class RouteRollbackDraftRequest(BaseModel):
    source_revision: int = Field(alias="sourceRevision", ge=1)
    expected_revision: int = Field(alias="expectedRevision", ge=1)


def get_store() -> AipModelRuntimeStore:
    return _STORE


def get_plugin_authority() -> ProviderPluginAuthority:
    return _PLUGIN_AUTHORITY


def get_eval_authority_store() -> AipEvalAuthorityStore:
    return _EVAL_AUTHORITY_STORE


def get_budget_authority_store() -> AipBudgetAuthorityStore:
    return _BUDGET_AUTHORITY_STORE


def get_governance_policy_store() -> AipModelGovernancePolicyStore:
    return _POLICY_AUTHORITY_STORE


def _scope(principal: Principal) -> TenantScope:
    return TenantScope(principal.org_id, principal.project_id)


def _key(value: str) -> str:
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 120:
        raise ApiError(code="AIP_INVALID_ARGUMENT", message="Idempotency-Key must be 1..120 characters", status_code=400)
    return cleaned


def _version(value: str) -> int:
    cleaned = value.strip().strip('"')
    if not cleaned.isdigit():
        raise ApiError(code="AIP_INVALID_ARGUMENT", message="If-Match must be an integer authority version", status_code=400)
    return int(cleaned)


def _map(exc: ModelRuntimeStoreError) -> ApiError:
    if isinstance(exc, ModelRuntimeNotFound):
        return ApiError(code=exc.code, message=str(exc), status_code=404)
    if isinstance(exc, (ModelRuntimeConflict, ModelRuntimeIdempotencyConflict)):
        return ApiError(code=exc.code, message=str(exc), status_code=409)
    if isinstance(exc, ModelRuntimeDependencyBlocked):
        return ApiError(code=exc.code, message=str(exc), status_code=422)
    return ApiError(code=exc.code, message="model runtime persistence failed", status_code=503)


def _map_plugin(exc: ProviderPluginAuthorityError) -> ApiError:
    if exc.code in {
        "provider_plugin_not_found",
        "provider_plugin_not_approved",
        "provider_plugin_scope_not_approved",
    }:
        return ApiError(
            code="AIP_PROVIDER_PLUGIN_UNAVAILABLE",
            message="approved provider plugin revision is unavailable",
            status_code=404,
        )
    if exc.code in {
        "provider_plugin_approval_drifted",
        "provider_plugin_ref_drifted",
    }:
        return ApiError(
            code="AIP_PROVIDER_PLUGIN_REF_DRIFTED",
            message="provider plugin exact reference is drifted",
            status_code=422,
        )
    return ApiError(
        code="AIP_PROVIDER_PLUGIN_AUTHORITY_UNAVAILABLE",
        message="provider plugin authority is unavailable",
        status_code=503,
    )


def _publish(kind: str, item, key: str, if_match: str, principal: Principal, store: AipModelRuntimeStore):
    normalized = item.model_copy(update={"created_by": principal.subject})
    try:
        return getattr(store, f"publish_{kind}")(_scope(principal), principal.subject, _key(key), normalized, expected_version=_version(if_match))
    except ModelRuntimeStoreError as exc:
        raise _map(exc) from exc


def _get(kind: str, asset_id: str, revision: int | None, principal: Principal, store: AipModelRuntimeStore):
    try:
        return getattr(store, f"get_{kind}")(_scope(principal), asset_id, revision)
    except ModelRuntimeStoreError as exc:
        raise _map(exc) from exc


def _ref_matches(ref, item) -> bool:
    return ref.revision == item.revision and ref.content_hash == item.content_hash


def _is_effective(start: datetime, end: datetime | None, now: datetime) -> bool:
    return start <= now and (end is None or now < end)


def _price_summary(scope, model, runtime_store, governance_store, now):
    blockers: list[str] = []
    snapshot = None
    status_value = "unknown"
    zero_price_approval_ref = None
    try:
        snapshot = runtime_store.get_price_snapshot(
            scope, model.price_snapshot_ref.asset_id, model.price_snapshot_ref.revision
        )
    except ModelRuntimeStoreError:
        blockers.append("PRICE_SNAPSHOT_UNAVAILABLE")
    if model.lifecycle is not ModelRuntimeLifecycle.ACTIVE:
        status_value = "inactive"
        blockers.append("MODEL_NOT_ACTIVE")
    elif snapshot is None:
        status_value = "unknown"
    elif not _ref_matches(model.price_snapshot_ref, snapshot):
        status_value = "drifted"
        blockers.append("PRICE_SNAPSHOT_REF_DRIFTED")
    elif snapshot.lifecycle is not ModelRuntimeLifecycle.ACTIVE:
        status_value = "inactive"
        blockers.append("PRICE_SNAPSHOT_NOT_ACTIVE")
    elif not _is_effective(snapshot.effective_from, snapshot.effective_until, now):
        status_value = "out_of_window"
        blockers.append("PRICE_SNAPSHOT_OUT_OF_WINDOW")
    elif any(modality.value in {"image", "audio", "video"} for modality in model.output_modalities):
        status_value = "unit_mismatch"
        blockers.append("TOKEN_PRICE_UNIT_MISMATCH")
    else:
        prices = [
            value for value in (
                snapshot.input_token_price,
                snapshot.output_token_price,
                snapshot.cached_token_price,
            )
            if value is not None
        ]
        if any(value > 0 for value in prices):
            status_value = "priced"
        elif prices and all(value == 0 for value in prices):
            try:
                policy = governance_store.get_budget(
                    scope,
                    model.budget_policy_ref.asset_id,
                    model.budget_policy_ref.revision,
                )
                if not _ref_matches(model.budget_policy_ref, policy):
                    status_value = "drifted"
                    blockers.append("ZERO_PRICE_POLICY_REF_DRIFTED")
                elif policy.allow_zero_price and policy.zero_price_approval_ref:
                    status_value = "approved_zero"
                    zero_price_approval_ref = policy.zero_price_approval_ref
                else:
                    status_value = "unknown"
                    blockers.append("ZERO_PRICE_NOT_APPROVED")
            except ModelGovernancePolicyNotFound:
                status_value = "unknown"
                blockers.append("ZERO_PRICE_POLICY_UNAVAILABLE")
        else:
            blockers.append("PRICE_QUANTITY_UNKNOWN")
    return ModelPriceAuthoritySummary(
        modelRef={
            "assetType": "RegisteredModelRevision",
            "assetId": model.registered_model_id,
            "revision": model.revision,
            "contentHash": model.content_hash,
        },
        providerModelId=model.provider_model_id,
        outputModalities=model.output_modalities,
        priceSnapshotRef=model.price_snapshot_ref,
        status=status_value,
        currency=snapshot.currency if snapshot else None,
        inputTokenPrice=snapshot.input_token_price if snapshot else None,
        outputTokenPrice=snapshot.output_token_price if snapshot else None,
        cachedTokenPrice=snapshot.cached_token_price if snapshot else None,
        tokenUnit=snapshot.token_unit if snapshot else None,
        effectiveFrom=snapshot.effective_from if snapshot else None,
        effectiveUntil=snapshot.effective_until if snapshot else None,
        zeroPriceApprovalRef=zero_price_approval_ref,
        blockerCodes=blockers,
    )


def _budget_summary(scope, ref, governance_store, budget_store, now):
    blockers: list[str] = []
    policy = None
    budget = None
    status_value = "unknown"
    try:
        policy = governance_store.get_budget(scope, ref.asset_id, ref.revision)
    except ModelGovernancePolicyNotFound:
        blockers.append("BUDGET_POLICY_UNAVAILABLE")
    if policy is None:
        return RuntimeBudgetAuthoritySummary(
            budgetPolicyRef=ref, status=status_value, blockerCodes=blockers
        )
    if not _ref_matches(ref, policy):
        status_value = "drifted"
        blockers.append("BUDGET_POLICY_REF_DRIFTED")
    elif policy.lifecycle is not ModelGovernancePolicyLifecycle.ACTIVE:
        status_value = "inactive"
        blockers.append("BUDGET_POLICY_NOT_ACTIVE")
    elif not _is_effective(policy.effective_from, policy.effective_until, now):
        status_value = "out_of_window"
        blockers.append("BUDGET_POLICY_OUT_OF_WINDOW")
    else:
        try:
            budget = budget_store.get(
                scope,
                policy.budget_revision_ref.asset_id,
                policy.budget_revision_ref.revision,
            )
        except BudgetNotFound:
            blockers.append("BUDGET_REVISION_UNAVAILABLE")
        if budget is None:
            status_value = "unknown"
        elif not _ref_matches(policy.budget_revision_ref, budget):
            status_value = "drifted"
            blockers.append("BUDGET_REVISION_REF_DRIFTED")
        elif budget.lifecycle is not BudgetLifecycle.ACTIVE:
            status_value = "inactive"
            blockers.append("BUDGET_REVISION_NOT_ACTIVE")
        elif not _is_effective(budget.effective_from, budget.effective_until, now):
            status_value = "out_of_window"
            blockers.append("BUDGET_REVISION_OUT_OF_WINDOW")
        else:
            status_value = "active"
    return RuntimeBudgetAuthoritySummary(
        budgetPolicyRef=ref,
        budgetRef=policy.budget_revision_ref,
        status=status_value,
        currency=budget.currency if budget else policy.currency,
        dailyLimitMinor=budget.daily_limit_minor if budget else None,
        monthlyLimitMinor=budget.monthly_limit_minor if budget else None,
        hardStop=budget.hard_stop if budget else policy.hard_stop,
        unknownUsageBehavior=(
            budget.unknown_usage_behavior if budget else policy.unknown_usage_behavior
        ),
        unknownPriceBehavior=policy.unknown_price_behavior,
        effectiveFrom=budget.effective_from if budget else policy.effective_from,
        effectiveUntil=budget.effective_until if budget else policy.effective_until,
        blockerCodes=blockers,
    )


@router.get("/provider-plugins/{plugin_id}", response_model=ProviderPluginRevision)
def get_provider_plugin(
    plugin_id: str,
    revision: int | None = Query(default=None, ge=1),
    principal: Principal = Depends(require_principal),
    authority: ProviderPluginAuthority = Depends(get_plugin_authority),
):
    try:
        return authority.get(_scope(principal), plugin_id, revision)
    except ProviderPluginAuthorityError as exc:
        raise _map_plugin(exc) from None


@router.post("/providers", response_model=ProviderInstanceRevision, status_code=status.HTTP_201_CREATED)
def publish_provider(body: ProviderInstanceRevision, idempotency_key: str = Header(alias="Idempotency-Key"), if_match: str = Header(alias="If-Match"), principal: Principal = Depends(require_principal), store: AipModelRuntimeStore = Depends(get_store), authority: ProviderPluginAuthority = Depends(get_plugin_authority)):
    try:
        authority.validate_ref(_scope(principal), body.plugin_ref)
    except ProviderPluginAuthorityError as exc:
        raise _map_plugin(exc) from None
    return _publish("provider", body, idempotency_key, if_match, principal, store)


@router.get("/providers/{provider_id}", response_model=ProviderInstanceRevision)
def get_provider(provider_id: str, revision: int | None = Query(default=None, ge=1), principal: Principal = Depends(require_principal), store: AipModelRuntimeStore = Depends(get_store)):
    return _get("provider", provider_id, revision, principal, store)


@router.post("/models", response_model=RegisteredModelRevision, status_code=status.HTTP_201_CREATED)
def publish_model(body: RegisteredModelRevision, idempotency_key: str = Header(alias="Idempotency-Key"), if_match: str = Header(alias="If-Match"), principal: Principal = Depends(require_principal), store: AipModelRuntimeStore = Depends(get_store)):
    return _publish("model", body, idempotency_key, if_match, principal, store)


@router.get("/models/{model_id}", response_model=RegisteredModelRevision)
def get_model(model_id: str, revision: int | None = Query(default=None, ge=1), principal: Principal = Depends(require_principal), store: AipModelRuntimeStore = Depends(get_store)):
    return _get("model", model_id, revision, principal, store)


@router.post("/policies", response_model=RuntimePolicyRevision, status_code=status.HTTP_201_CREATED)
def publish_policy(body: RuntimePolicyRevision, idempotency_key: str = Header(alias="Idempotency-Key"), if_match: str = Header(alias="If-Match"), principal: Principal = Depends(require_principal), store: AipModelRuntimeStore = Depends(get_store)):
    return _publish("policy", body, idempotency_key, if_match, principal, store)


@router.get("/policies/{policy_id}", response_model=RuntimePolicyRevision)
def get_policy(policy_id: str, revision: int | None = Query(default=None, ge=1), principal: Principal = Depends(require_principal), store: AipModelRuntimeStore = Depends(get_store)):
    return _get("policy", policy_id, revision, principal, store)


@router.post("/price-snapshots", response_model=ModelPriceSnapshotRevision, status_code=status.HTTP_201_CREATED)
def publish_price_snapshot(body: ModelPriceSnapshotRevision, idempotency_key: str = Header(alias="Idempotency-Key"), if_match: str = Header(alias="If-Match"), principal: Principal = Depends(require_principal), store: AipModelRuntimeStore = Depends(get_store)):
    return _publish("price_snapshot", body, idempotency_key, if_match, principal, store)


@router.get("/price-snapshots/{price_snapshot_id}", response_model=ModelPriceSnapshotRevision)
def get_price_snapshot(price_snapshot_id: str, revision: int | None = Query(default=None, ge=1), principal: Principal = Depends(require_principal), store: AipModelRuntimeStore = Depends(get_store)):
    return _get("price_snapshot", price_snapshot_id, revision, principal, store)


@router.post("/routes", response_model=ModelRouteRevision, status_code=status.HTTP_201_CREATED)
def publish_route(body: ModelRouteRevision, idempotency_key: str = Header(alias="Idempotency-Key"), if_match: str = Header(alias="If-Match"), principal: Principal = Depends(require_principal), store: AipModelRuntimeStore = Depends(get_store)):
    return _publish("route", body, idempotency_key, if_match, principal, store)


@router.post("/provider-health", response_model=ProviderHealthObservation, status_code=status.HTTP_201_CREATED)
def record_health(body: ProviderHealthObservation, idempotency_key: str = Header(alias="Idempotency-Key"), principal: Principal = Depends(require_principal), store: AipModelRuntimeStore = Depends(get_store)):
    try:
        return store.record_health(_scope(principal), principal.subject, _key(idempotency_key), body)
    except ModelRuntimeStoreError as exc:
        raise _map(exc) from exc


@router.get("/routes/{route_id}", response_model=ModelRouteRevision)
def get_route(route_id: str, revision: int | None = Query(default=None, ge=1), principal: Principal = Depends(require_principal), store: AipModelRuntimeStore = Depends(get_store)):
    return _get("route", route_id, revision, principal, store)


@router.get("/routes/{route_id}/revisions", response_model=list[ModelRouteRevision])
def list_route_revisions(
    route_id: str,
    principal: Principal = Depends(require_principal),
    store: AipModelRuntimeStore = Depends(get_store),
):
    try:
        return store.list_route_revisions(_scope(principal), route_id)
    except ModelRuntimeStoreError as exc:
        raise _map(exc) from exc


@router.post(
    "/routes/{route_id}/rollback-draft",
    response_model=ModelRouteRevision,
    status_code=status.HTTP_201_CREATED,
)
def create_route_rollback_draft(
    route_id: str,
    body: RouteRollbackDraftRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
    store: AipModelRuntimeStore = Depends(get_store),
):
    try:
        return store.create_route_rollback_draft(
            _scope(principal),
            principal.subject,
            _key(idempotency_key),
            route_id,
            body.source_revision,
            expected_revision=body.expected_revision,
        )
    except ModelRuntimeStoreError as exc:
        raise _map(exc) from exc


@router.get("/routes/{route_id}/resolution", response_model=ModelRouteResolution)
def resolve_route(route_id: str, principal: Principal = Depends(require_principal), store: AipModelRuntimeStore = Depends(get_store)):
    try:
        return AipModelRuntimeResolver(store).resolve(_scope(principal), route_id)
    except ModelRuntimeStoreError as exc:
        raise _map(exc) from exc


@router.get("/overview", response_model=ModelRuntimeOverview)
def get_overview(principal: Principal = Depends(require_principal), store: AipModelRuntimeStore = Depends(get_store)):
    scope = _scope(principal)
    try:
        providers = store.list_current_assets(scope, "provider_instance")
        models = store.list_current_assets(scope, "registered_model")
        policies = store.list_current_assets(scope, "runtime_policy")
        routes = store.list_current_assets(scope, "model_route")
        prices = store.list_current_assets(scope, "model_price_snapshot")
        eval_refs = [ref for item in [*models, *routes] for ref in item.dependency_refs if ref.asset_type == "EvalGateDecision"]
        resolutions = [AipModelRuntimeResolver(store).resolve(scope, route.ref.asset_id) for route in routes]
        current_provider_refs = {
            (item.ref.asset_id, item.ref.revision, item.ref.content_hash)
            for item in providers
        }
        health_observations = [
            item for item in store.list_latest_provider_health(scope)
            if (item.provider.asset_id, item.provider.revision, item.provider.content_hash)
            in current_provider_refs
        ]
        return ModelRuntimeOverview(
            tenant={"orgId": scope.org_id, "projectId": scope.project_id}, providers=providers,
            models=models, routes=routes, policies=policies, priceSnapshots=prices,
            evalGates=store.list_eval_gates(scope, eval_refs),
            capacityPools=store.list_capacity_pools(scope), resolutions=resolutions,
            healthObservations=health_observations,
            generatedAt=datetime.now(UTC),
        )
    except ModelRuntimeStoreError as exc:
        raise _map(exc) from exc


@router.get("/cost-overview", response_model=ModelRuntimeCostOverview)
def get_cost_overview(
    principal: Principal = Depends(require_principal),
    runtime_store: AipModelRuntimeStore = Depends(get_store),
    eval_store: AipEvalAuthorityStore = Depends(get_eval_authority_store),
    budget_store: AipBudgetAuthorityStore = Depends(get_budget_authority_store),
    governance_store: AipModelGovernancePolicyStore = Depends(
        get_governance_policy_store
    ),
):
    """Return a tenant-scoped, Secret-free projection of price, budget and usage facts."""
    scope = _scope(principal)
    now = datetime.now(UTC)
    try:
        model_heads = runtime_store.list_current_assets(scope, "registered_model")
        policy_heads = runtime_store.list_current_assets(scope, "runtime_policy")
        models = [
            runtime_store.get_model(scope, item.ref.asset_id, item.ref.revision)
            for item in model_heads
        ]
        policies = [
            runtime_store.get_policy(scope, item.ref.asset_id, item.ref.revision)
            for item in policy_heads
        ]
        model_prices = [
            _price_summary(scope, model, runtime_store, governance_store, now)
            for model in models
        ]
        budget_refs = {
            (
                ref.asset_type,
                ref.asset_id,
                ref.revision,
                ref.content_hash,
            ): ref
            for ref in [
                *(model.budget_policy_ref for model in models),
                *(policy.budget_policy_ref for policy in policies),
            ]
        }
        budgets = [
            _budget_summary(scope, ref, governance_store, budget_store, now)
            for ref in budget_refs.values()
        ]
        receipt_limit = 1000
        receipts = eval_store.list_scope_usage_receipts(scope, limit=receipt_limit)
        adjustments = eval_store.list_scope_usage_adjustments(scope, limit=receipt_limit)
    except ModelRuntimeStoreError as exc:
        raise _map(exc) from exc
    except AipEvalAuthorityPersistenceError as exc:
        raise ApiError(
            code="AIP_USAGE_AUTHORITY_UNAVAILABLE",
            message="usage authority is unavailable",
            status_code=503,
        ) from exc

    quality_counts = {
        EvidenceQuality.MEASURED: 0,
        EvidenceQuality.ESTIMATED: 0,
        EvidenceQuality.UNKNOWN: 0,
    }
    for receipt in receipts:
        quality_counts[receipt.quality] += 1
    if not receipts:
        usage_state = "unobserved"
    elif quality_counts[EvidenceQuality.UNKNOWN] == len(receipts):
        usage_state = "unknown"
    elif quality_counts[EvidenceQuality.ESTIMATED] or quality_counts[EvidenceQuality.UNKNOWN]:
        usage_state = "partial"
    else:
        usage_state = "measured"

    deltas = defaultdict(float)
    for adjustment in adjustments:
        deltas[adjustment.receipt_id] += adjustment.delta
    cost_totals = defaultdict(float)
    for receipt in receipts:
        if (
            receipt.usage_kind is UsageKind.COST
            and receipt.quantity is not None
            and receipt.currency is not None
        ):
            cost_totals[receipt.currency] += receipt.quantity + deltas[receipt.receipt_id]

    return ModelRuntimeCostOverview(
        tenant={"orgId": scope.org_id, "projectId": scope.project_id},
        modelPrices=model_prices,
        budgets=budgets,
        usage=RuntimeUsageAuthoritySummary(
            state=usage_state,
            receiptCount=len(receipts),
            measuredCount=quality_counts[EvidenceQuality.MEASURED],
            estimatedCount=quality_counts[EvidenceQuality.ESTIMATED],
            unknownCount=quality_counts[EvidenceQuality.UNKNOWN],
            adjustmentCount=len(adjustments),
            costTotals=dict(cost_totals),
            latestObservedAt=max(
                (receipt.observed_at for receipt in receipts), default=None
            ),
            truncated=(len(receipts) >= receipt_limit or len(adjustments) >= receipt_limit),
        ),
        generatedAt=now,
    )
