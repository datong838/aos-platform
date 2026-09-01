from __future__ import annotations

from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from aos_api.aip_provider_plugin_authority import ProviderPluginAuthorityError
from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_budget_contracts import BudgetLifecycle
from aos_api.aip_contracts import ResourceRef, TenantContext
from aos_api.aip_eval_contracts import UsageAdjustment, UsageAttribution, UsageReceipt
from aos_api.aip_model_governance_policy_contracts import ModelGovernancePolicyLifecycle
from aos_api.aip_model_runtime_contracts import (
    ModelRouteRevision,
    ModelPriceSnapshotRevision,
    ModelRuntimeAssetSummary,
    ModelRuntimeLifecycle,
    ProviderHealthObservation,
    RegisteredModelRevision,
)
from aos_api.aip_model_runtime_store import AipModelRuntimeStore, ModelRuntimeNotFound, canonical_hash
from aos_api.routers import aip_model_runtime
from aos_api.tenant_scope import TenantScope


def headers(org_id: str = "org-org", **extra: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer dev",
        "X-Org-Id": org_id,
        "X-Project-Id": "dev-project",
        **extra,
    }


class CapturingStore:
    def __init__(self) -> None:
        self.scope = None

    def get_route(self, scope, route_id, revision=None):
        self.scope = scope
        raise ModelRuntimeNotFound("model_route not found")

    def list_route_revisions(self, scope, route_id):
        self.scope = scope
        raise ModelRuntimeNotFound("model_route not found")


class ExactReadStore:
    def __init__(self) -> None:
        self.calls = []

    def _missing(self, kind, scope, asset_id, revision):
        self.calls.append((kind, scope.key, asset_id, revision))
        raise ModelRuntimeNotFound(f"{kind} not found")

    def get_provider(self, scope, asset_id, revision=None):
        return self._missing("provider", scope, asset_id, revision)

    def get_model(self, scope, asset_id, revision=None):
        return self._missing("model", scope, asset_id, revision)

    def get_policy(self, scope, asset_id, revision=None):
        return self._missing("policy", scope, asset_id, revision)

    def get_price_snapshot(self, scope, asset_id, revision=None):
        return self._missing("price_snapshot", scope, asset_id, revision)


class PricePublishStore:
    call = None

    def publish_price_snapshot(self, scope, actor, key, item, *, expected_version=0):
        self.call = (scope.key, actor, key, expected_version, item)
        return item


class RollbackDraftStore:
    call = None

    def create_route_rollback_draft(
        self, scope, actor, key, route_id, source_revision, *, expected_revision
    ):
        self.call = (
            scope.key,
            actor,
            key,
            route_id,
            source_revision,
            expected_revision,
        )
        raise ModelRuntimeNotFound("test capture")


def test_canonical_route_read_uses_principal_scope_and_never_cross_tenant(client) -> None:
    store = CapturingStore()
    client.app.dependency_overrides[aip_model_runtime.get_store] = lambda: store
    try:
        response = client.get("/v1/aip/model-runtime/routes/missing", headers=headers())
        assert response.status_code == 404
        assert response.json()["code"] == "AIP_RESOURCE_NOT_FOUND"
        assert store.scope.key == ("org-org", "dev-project")
        response = client.get("/v1/aip/model-runtime/routes/missing", headers=headers("dev-org"))
        assert response.status_code == 404
        assert store.scope.key == ("dev-org", "dev-project")
    finally:
        client.app.dependency_overrides.pop(aip_model_runtime.get_store, None)


def test_canonical_route_history_is_principal_scoped_and_never_synthesizes_drafts(client) -> None:
    store = CapturingStore()
    client.app.dependency_overrides[aip_model_runtime.get_store] = lambda: store
    try:
        response = client.get(
            "/v1/aip/model-runtime/routes/missing/revisions", headers=headers()
        )
        assert response.status_code == 404
        assert response.json()["code"] == "AIP_RESOURCE_NOT_FOUND"
        assert store.scope.key == ("org-org", "dev-project")

        response = client.get(
            "/v1/aip/model-runtime/routes/missing/revisions",
            headers=headers("dev-org"),
        )
        assert response.status_code == 404
        assert store.scope.key == ("dev-org", "dev-project")
    finally:
        client.app.dependency_overrides.pop(aip_model_runtime.get_store, None)


def test_canonical_write_requires_idempotency_and_if_match(client) -> None:
    response = client.post("/v1/aip/model-runtime/routes", headers=headers(), json={})
    assert response.status_code == 400
    assert response.json()["code"] == "VALIDATION"


def test_route_rollback_draft_is_tenant_scoped_idempotent_and_never_activates(client) -> None:
    store = RollbackDraftStore()
    client.app.dependency_overrides[aip_model_runtime.get_store] = lambda: store
    try:
        response = client.post(
            "/v1/aip/model-runtime/routes/route-a/rollback-draft",
            headers=headers(**{"Idempotency-Key": "rollback-route-a-2"}),
            json={"sourceRevision": 2, "expectedRevision": 7},
        )
        assert response.status_code == 404
        assert store.call == (
            ("org-org", "dev-project"),
            "user:dev",
            "rollback-route-a-2",
            "route-a",
            2,
            7,
        )
    finally:
        client.app.dependency_overrides.pop(aip_model_runtime.get_store, None)


def test_store_rollback_copies_history_into_new_draft_without_mutating_source() -> None:
    scope = TenantScope(org_id="org-org", project_id="dev-project")
    ref = lambda asset_type, asset_id: {
        "assetType": asset_type,
        "assetId": asset_id,
        "revision": 1,
        "contentHash": "a" * 64,
    }
    common = {
        "tenant": {"orgId": "org-org", "projectId": "dev-project"},
        "routeId": "route-a",
        "contentHash": "a" * 64,
        "taskTypes": ["summary"],
        "requiredInputModality": "text",
        "requiredOutputModality": "text",
        "requiredCapabilities": ["chat"],
        "candidates": [{"model": ref("RegisteredModelRevision", "model-a"), "weight": 100}],
        "strategy": "failover",
        "runtimePolicyRef": ref("RuntimePolicyRevision", "policy-a"),
        "evalGateRef": ref("EvalGateDecision", "eval-a"),
        "createdBy": "reviewer",
        "createdAt": datetime(2026, 8, 29, tzinfo=UTC),
    }
    head = ModelRouteRevision.model_validate({**common, "revision": 3, "lifecycle": "active"})
    source = ModelRouteRevision.model_validate({**common, "revision": 2, "lifecycle": "validated"})
    store = object.__new__(AipModelRuntimeStore)
    store._connect_factory = lambda read_scope: nullcontext(
        SimpleNamespace(execute=lambda *args, **kwargs: SimpleNamespace(fetchone=lambda: {"current_revision": 3, "version": 7}))
    )
    store.get_route = lambda read_scope, asset_id, revision=None: source if revision == 2 else head
    captured = {}

    def publish_route(read_scope, actor, key, item, *, expected_version=0):
        captured.update(scope=read_scope, actor=actor, key=key, item=item, expected_version=expected_version)
        return item

    store.publish_route = publish_route
    draft = store.create_route_rollback_draft(
        scope,
        "user:dev",
        "rollback-route-a-2-3",
        "route-a",
        2,
        expected_revision=3,
    )

    assert source.lifecycle is ModelRuntimeLifecycle.VALIDATED
    assert head.lifecycle is ModelRuntimeLifecycle.ACTIVE
    assert draft.revision == 4
    assert draft.lifecycle is ModelRuntimeLifecycle.DRAFT
    assert draft.created_by == "user:dev"
    assert captured["expected_version"] == 7
    content = {
        name: value
        for name, value in draft.model_dump(mode="json", by_alias=True).items()
        if name not in AipModelRuntimeStore._META_FIELDS
    }
    assert draft.content_hash == canonical_hash(content)


def test_exact_runtime_asset_reads_are_principal_scoped_and_revision_aware(client) -> None:
    store = ExactReadStore()
    client.app.dependency_overrides[aip_model_runtime.get_store] = lambda: store
    try:
        paths = (
            ("provider", "/v1/aip/model-runtime/providers/provider-1?revision=2"),
            ("model", "/v1/aip/model-runtime/models/model-1?revision=2"),
            ("policy", "/v1/aip/model-runtime/policies/policy-1?revision=2"),
            ("price_snapshot", "/v1/aip/model-runtime/price-snapshots/price-1?revision=2"),
        )
        for kind, path in paths:
            response = client.get(path, headers=headers())
            assert response.status_code == 404
            assert response.json()["code"] == "AIP_RESOURCE_NOT_FOUND"
            assert store.calls[-1] == (kind, ("org-org", "dev-project"), path.split("/")[-1].split("?")[0], 2)
    finally:
        client.app.dependency_overrides.pop(aip_model_runtime.get_store, None)


def test_price_snapshot_publish_uses_principal_scope_cas_and_idempotency(client) -> None:
    store = PricePublishStore()
    client.app.dependency_overrides[aip_model_runtime.get_store] = lambda: store
    try:
        response = client.post(
            "/v1/aip/model-runtime/price-snapshots",
            headers=headers(**{"Idempotency-Key": "price-1", "If-Match": "0"}),
            json={
                "tenant": {"orgId": "org-org", "projectId": "dev-project"},
                "priceSnapshotId": "price-1",
                "revision": 1,
                "contentHash": "a" * 64,
                "currency": "CNY",
                "inputTokenPrice": 0.001,
                "outputTokenPrice": 0.002,
                "cachedTokenPrice": None,
                "tokenUnit": 1000,
                "effectiveFrom": "2026-08-16T00:00:00Z",
                "effectiveUntil": None,
                "lifecycle": "draft",
                "createdBy": "caller-must-not-win",
                "createdAt": "2026-08-16T00:00:00Z",
            },
        )
        assert response.status_code == 201, response.text
        assert store.call[:4] == (("org-org", "dev-project"), "user:dev", "price-1", 0)
        assert store.call[4].created_by == "user:dev"
    finally:
        client.app.dependency_overrides.pop(aip_model_runtime.get_store, None)


def test_all_legacy_route_writes_fail_closed_but_reads_remain(client) -> None:
    read = client.get("/v1/aip/model-admin/routes", headers=headers())
    assert read.status_code == 200
    for method, path, body in (
        ("put", "/v1/aip/model-admin/routes", {"routes": []}),
        ("post", "/api/models/router", {"id": "legacy", "task": "copy.generate"}),
        ("put", "/api/models/router/legacy", {"enabled": False}),
        ("delete", "/api/models/router/legacy", None),
        ("put", "/api/models/router/circuit-config", {"failure_threshold": 3}),
    ):
        response = client.request(method.upper(), path, headers=headers(), json=body)
        assert response.status_code == 410, (method, path, response.text)
        assert response.json()["code"] == "AIP_MODEL_LEGACY_WRITE_DISABLED"


def test_compatibility_route_draft_is_writable_without_activating_runtime(client) -> None:
    current = client.get("/api/models/router/draft", headers=headers())
    assert current.status_code == 200, current.text
    payload = current.json()
    response = client.put(
        "/api/models/router/draft",
        headers=headers(),
        json={"items": payload["items"], "expectedVersion": payload["version"]},
    )
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved["version"] == payload["version"] + 1
    runtime = client.get("/v1/aip/model-runtime/overview", headers=headers())
    assert runtime.status_code == 200, runtime.text
    assert all(item["ref"]["revision"] >= 1 for item in runtime.json()["routes"])


def test_openapi_registers_canonical_model_runtime_paths(client) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    assert "/v1/aip/model-runtime/provider-plugins/{plugin_id}" in paths
    assert "/v1/aip/model-runtime/providers" in paths
    assert "/v1/aip/model-runtime/providers/{provider_id}" in paths
    assert "/v1/aip/model-runtime/models" in paths
    assert "/v1/aip/model-runtime/models/{model_id}" in paths
    assert "/v1/aip/model-runtime/policies" in paths
    assert "/v1/aip/model-runtime/policies/{policy_id}" in paths
    assert "/v1/aip/model-runtime/price-snapshots" in paths
    assert "/v1/aip/model-runtime/price-snapshots/{price_snapshot_id}" in paths
    assert "/v1/aip/model-runtime/routes/{route_id}/resolution" in paths
    assert "/v1/aip/model-runtime/routes/{route_id}/revisions" in paths
    assert "/v1/aip/model-runtime/routes/{route_id}/rollback-draft" in paths
    assert "/v1/aip/model-runtime/overview" in paths
    assert "/v1/aip/model-runtime/chain-overview" in paths
    assert "/v1/aip/model-runtime/cost-overview" in paths


class EmptyUsageAuthorityStore:
    scopes = []

    def list_scope_usage_receipts(self, scope, *, limit=1000):
        self.scopes.append(("receipts", scope.key, limit))
        return []

    def list_scope_usage_adjustments(self, scope, *, limit=1000):
        self.scopes.append(("adjustments", scope.key, limit))
        return []

    def list_scope_usage_attributions(self, scope, *, limit=5000):
        self.scopes.append(("attributions", scope.key, limit))
        return []

    def resolve_lineage_task_bindings(self, scope, lineage_ids):
        self.scopes.append(("task-bindings", scope.key, len(lineage_ids)))
        return {}


def test_cost_overview_reports_unobserved_instead_of_fake_zero(client) -> None:
    runtime = EmptyOverviewStore()
    usage = EmptyUsageAuthorityStore()
    client.app.dependency_overrides[aip_model_runtime.get_store] = lambda: runtime
    client.app.dependency_overrides[aip_model_runtime.get_eval_authority_store] = lambda: usage
    try:
        response = client.get("/v1/aip/model-runtime/cost-overview", headers=headers())
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["tenant"] == {"orgId": "org-org", "projectId": "dev-project"}
        assert payload["modelPrices"] == []
        assert payload["budgets"] == []
        assert payload["quotas"] == []
        assert {key: value for key, value in payload["usage"].items() if key != "periods"} == {
            "state": "unobserved",
            "receiptCount": 0,
            "measuredCount": 0,
            "estimatedCount": 0,
            "unknownCount": 0,
            "adjustmentCount": 0,
            "costTotals": {},
            "latestObservedAt": None,
            "truncated": False,
        }
        assert [item["period"] for item in payload["usage"]["periods"]] == ["today", "week", "month"]
        assert {item["timeZone"] for item in payload["usage"]["periods"]} == {"Asia/Shanghai"}
        today_start = datetime.fromisoformat(payload["usage"]["periods"][0]["startsAt"])
        assert today_start.astimezone(ZoneInfo("Asia/Shanghai")).time() == datetime.min.time()
        assert all(item["receiptCount"] == 0 for item in payload["usage"]["periods"])
        assert all(
            [dimension["dimension"] for dimension in item["attributionDimensions"]]
            == ["tenant", "task", "agent", "logic", "model"]
            for item in payload["usage"]["periods"]
        )
        assert {item[1] for item in usage.scopes} == {("org-org", "dev-project")}
        assert "secret" not in response.text.lower()
    finally:
        client.app.dependency_overrides.pop(aip_model_runtime.get_store, None)
        client.app.dependency_overrides.pop(aip_model_runtime.get_eval_authority_store, None)


def exact_ref(asset_type: str, asset_id: str, digest: str) -> VersionedAssetRef:
    return VersionedAssetRef(
        assetType=asset_type, assetId=asset_id, revision=1, contentHash=digest
    )


def registered_model(model_id: str, modality: str, price_id: str) -> RegisteredModelRevision:
    digest = {"text-model": "1", "image-model": "2"}[model_id] * 64
    return RegisteredModelRevision(
        tenant=TenantContext(orgId="org-org", projectId="dev-project"),
        registeredModelId=model_id,
        revision=1,
        contentHash=digest,
        provider=exact_ref("ProviderInstanceRevision", "provider-1", "3" * 64),
        providerModelId=f"provider-{model_id}",
        inputModalities=["text"],
        outputModalities=[modality],
        capabilities=["generate"],
        contextWindow=4096,
        quotaPolicyRef=exact_ref("QuotaPolicyRevision", "quota-1", "4" * 64),
        budgetPolicyRef=exact_ref("BudgetPolicyRevision", "budget-policy-1", "5" * 64),
        priceSnapshotRef=exact_ref("ModelPriceSnapshotRevision", price_id, "6" * 64),
        evalGateRef=exact_ref("EvalGateDecision", "eval-1", "7" * 64),
        lifecycle="active",
        createdBy="test",
        createdAt=datetime(2026, 8, 20, tzinfo=UTC),
    )


class CostRuntimeStore:
    def __init__(self) -> None:
        now = datetime.now(UTC)
        self.models = {
            "text-model": registered_model("text-model", "text", "price-text"),
            "image-model": registered_model("image-model", "image", "price-image"),
        }
        self.prices = {
            price_id: ModelPriceSnapshotRevision(
                tenant=TenantContext(orgId="org-org", projectId="dev-project"),
                priceSnapshotId=price_id,
                revision=1,
                contentHash="6" * 64,
                currency="CNY",
                inputTokenPrice=0,
                outputTokenPrice=0,
                tokenUnit=1000,
                effectiveFrom=now - timedelta(days=30),
                effectiveUntil=now + timedelta(days=30),
                lifecycle="active",
                createdBy="test",
                createdAt=datetime(2026, 8, 1, tzinfo=UTC),
            )
            for price_id in ("price-text", "price-image")
        }

    def list_current_assets(self, scope, kind):
        assert scope.key in {("org-org", "dev-project"), ("dev-org", "dev-project")}
        if scope.org_id == "dev-org" or kind != "registered_model":
            return []
        return [
            ModelRuntimeAssetSummary(
                ref=exact_ref("RegisteredModelRevision", model.registered_model_id, model.content_hash),
                lifecycle="active",
            )
            for model in self.models.values()
        ]

    def get_model(self, scope, asset_id, revision=None):
        return self.models[asset_id]

    def get_price_snapshot(self, scope, asset_id, revision=None):
        return self.prices[asset_id]


class ApprovedZeroGovernanceStore:
    def get_budget(self, scope, policy_id, revision=None):
        now = datetime.now(UTC)
        return SimpleNamespace(
            revision=1,
            content_hash="5" * 64,
            lifecycle=ModelGovernancePolicyLifecycle.ACTIVE,
            owner="test",
            approval_ref="approval:test",
            effective_from=now - timedelta(days=30),
            effective_until=now + timedelta(days=30),
            allow_zero_price=True,
            zero_price_approval_ref="approval://zero-price/dev",
            budget_revision_ref=exact_ref("BudgetRevision", "budget-1", "8" * 64),
            currency="CNY",
            hard_stop=True,
            unknown_usage_behavior="block",
            unknown_price_behavior="block",
        )

    def get_quota(self, scope, policy_id, revision=None):
        return self._quota(revision or 1)

    def get_quota_head(self, scope, policy_id):
        return self._quota(1), 1

    @staticmethod
    def _quota(revision):
        now = datetime.now(UTC)
        return SimpleNamespace(
            policy_id="quota-1",
            revision=revision,
            content_hash="4" * 64,
            lifecycle=ModelGovernancePolicyLifecycle.ACTIVE,
            owner="test",
            approval_ref="approval:test",
            effective_from=now - timedelta(days=30),
            effective_until=now + timedelta(days=30),
            rpm_limit=40,
            tpm_limit=40_000,
            max_concurrency=2,
            max_input_tokens=8000,
            max_output_tokens=2000,
            hourly_request_limit=50,
            daily_request_limit=200,
            overflow_behavior="reject",
            reservation_lease_seconds=60,
            allow_public_provider_fallback=False,
            allow_auto_scale=False,
        )


class ActiveBudgetStore:
    def get(self, scope, budget_id, revision=None):
        now = datetime.now(UTC)
        return SimpleNamespace(
            revision=1,
            content_hash="8" * 64,
            lifecycle=BudgetLifecycle.ACTIVE,
            effective_from=now - timedelta(days=30),
            effective_until=now + timedelta(days=30),
            currency="CNY",
            daily_limit_minor=10_000,
            monthly_limit_minor=100_000,
            hard_stop=True,
            unknown_usage_behavior="block",
        )


def test_cost_overview_requires_exact_zero_price_approval_and_rejects_token_unit_for_image(client) -> None:
    runtime = CostRuntimeStore()
    client.app.dependency_overrides[aip_model_runtime.get_store] = lambda: runtime
    client.app.dependency_overrides[aip_model_runtime.get_eval_authority_store] = lambda: EmptyUsageAuthorityStore()
    client.app.dependency_overrides[aip_model_runtime.get_governance_policy_store] = lambda: ApprovedZeroGovernanceStore()
    client.app.dependency_overrides[aip_model_runtime.get_budget_authority_store] = lambda: ActiveBudgetStore()
    try:
        response = client.get("/v1/aip/model-runtime/cost-overview", headers=headers())
        assert response.status_code == 200, response.text
        prices = {item["modelRef"]["assetId"]: item for item in response.json()["modelPrices"]}
        assert prices["text-model"]["status"] == "approved_zero"
        assert prices["text-model"]["zeroPriceApprovalRef"] == "approval://zero-price/dev"
        assert prices["image-model"]["status"] == "unit_mismatch"
        assert prices["image-model"]["blockerCodes"] == ["TOKEN_PRICE_UNIT_MISMATCH"]
        assert response.json()["budgets"][0]["status"] == "active"
        assert response.json()["quotas"][0]["rpmLimit"] == 40
        assert response.json()["quotas"][0]["headVersion"] == 1

        canary = client.get("/v1/aip/model-runtime/cost-overview", headers=headers("dev-org"))
        assert canary.status_code == 200
        assert canary.json()["modelPrices"] == []
    finally:
        client.app.dependency_overrides.pop(aip_model_runtime.get_store, None)
        client.app.dependency_overrides.pop(aip_model_runtime.get_eval_authority_store, None)
        client.app.dependency_overrides.pop(aip_model_runtime.get_governance_policy_store, None)
        client.app.dependency_overrides.pop(aip_model_runtime.get_budget_authority_store, None)


class MixedUsageAuthorityStore(EmptyUsageAuthorityStore):
    def list_scope_usage_receipts(self, scope, *, limit=1000):
        tenant = TenantContext(orgId=scope.org_id, projectId=scope.project_id)
        common = {
            "tenant": tenant,
            "provider": "agnes",
            "lineageId": "lineage-1",
            "sourceHash": "9" * 64,
            "observedAt": datetime.now(UTC) - timedelta(minutes=5),
        }
        return [
            UsageReceipt(receiptId="cost-measured", providerReceiptId="p-1", usageKind="cost", quantity=1.5, unit="currency", currency="CNY", quality="measured", **common),
            UsageReceipt(receiptId="tokens-estimated", providerReceiptId="p-2", usageKind="input_token", quantity=12, unit="token", quality="estimated", **common),
            UsageReceipt(receiptId="cost-unknown", providerReceiptId="p-3", usageKind="cost", quantity=None, unit="currency", currency="CNY", quality="unknown", **common),
        ]

    def list_scope_usage_adjustments(self, scope, *, limit=1000):
        return [
            UsageAdjustment(
                tenant=TenantContext(orgId=scope.org_id, projectId=scope.project_id),
                adjustmentId="adjust-1",
                receiptId="cost-measured",
                delta=0.25,
                reasonHash="a" * 64,
                actor="test",
                createdAt=datetime(2026, 8, 21, tzinfo=UTC),
            )
        ]

    def resolve_lineage_task_bindings(self, scope, lineage_ids):
        return {"lineage-1": ("task-qyh-sales-review", "plan-qyh-sales-review@3")}

    def list_scope_usage_attributions(self, scope, *, limit=5000):
        tenant = TenantContext(orgId=scope.org_id, projectId=scope.project_id)
        common = {
            "tenant": tenant,
            "receiptId": "cost-measured",
            "lineageId": "lineage-1",
            "quality": "measured",
            "weight": 1,
            "sourceHash": "b" * 64,
            "createdAt": datetime.now(UTC),
        }
        return [
            UsageAttribution(
                attributionId=f"attribution-{kind}",
                subjectType=kind,
                subject=ResourceRef(resourceType=kind, resourceId=subject_id, revision="rev-1", authority="aip"),
                **common,
            )
            for kind, subject_id in (("agent", "数据参谋"), ("logic", "经营复盘"), ("model", "agnes-2.5-flash"))
        ]


def test_chain_overview_traces_only_same_receipt_facts_and_preserves_missing_dimensions(client) -> None:
    runtime = EmptyOverviewStore()
    client.app.dependency_overrides[aip_model_runtime.get_store] = lambda: runtime
    client.app.dependency_overrides[aip_model_runtime.get_eval_authority_store] = lambda: MixedUsageAuthorityStore()
    try:
        response = client.get("/v1/aip/model-runtime/chain-overview", headers=headers())
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["chains"] == []
        task_trace = payload["taskTraces"][0]
        assert task_trace["task"] == {
            "resourceType": "task",
            "resourceId": "task-qyh-sales-review",
            "revision": "plan-qyh-sales-review@3",
        }
        assert task_trace["receiptCount"] == 3
        assert task_trace["models"] == [
            {"resourceType": "model", "resourceId": "agnes-2.5-flash", "revision": "rev-1"}
        ]
        assert task_trace["agents"][0]["resourceId"] == "数据参谋"
        assert task_trace["logics"][0]["resourceId"] == "经营复盘"
        assert task_trace["missingDimensions"] == []

        impact = payload["modelImpacts"][0]
        assert impact["model"]["resourceId"] == "agnes-2.5-flash"
        assert impact["receiptCount"] == 1
        assert impact["tasks"][0]["resourceId"] == "task-qyh-sales-review"
        assert impact["agents"][0]["resourceId"] == "数据参谋"
        assert impact["logics"][0]["resourceId"] == "经营复盘"
    finally:
        client.app.dependency_overrides.pop(aip_model_runtime.get_store, None)
        client.app.dependency_overrides.pop(aip_model_runtime.get_eval_authority_store, None)


def test_cost_overview_aggregates_adjustments_without_hiding_usage_quality(client) -> None:
    runtime = EmptyOverviewStore()
    client.app.dependency_overrides[aip_model_runtime.get_store] = lambda: runtime
    client.app.dependency_overrides[aip_model_runtime.get_eval_authority_store] = lambda: MixedUsageAuthorityStore()
    try:
        response = client.get("/v1/aip/model-runtime/cost-overview", headers=headers())
        assert response.status_code == 200, response.text
        usage = response.json()["usage"]
        assert usage["state"] == "partial"
        assert (usage["measuredCount"], usage["estimatedCount"], usage["unknownCount"]) == (1, 1, 1)
        assert usage["adjustmentCount"] == 1
        assert usage["costTotals"] == {"CNY": 1.75}
        assert [item["period"] for item in usage["periods"]] == ["today", "week", "month"]
        assert usage["periods"][0]["receiptCount"] == 3
        assert usage["periods"][0]["quantityTotals"] == {
            "cost:CNY": 1.75,
            "input_token:token": 12.0,
        }
        assert usage["periods"][0]["providerCounts"] == {"agnes": 3}
        dimensions = {item["dimension"]: item for item in usage["periods"][0]["attributionDimensions"]}
        assert dimensions["tenant"]["attributedReceiptCount"] == 3
        assert dimensions["tenant"]["missingReceiptCount"] == 0
        assert dimensions["task"]["attributedReceiptCount"] == 3
        assert dimensions["task"]["missingReceiptCount"] == 0
        assert dimensions["agent"]["attributedReceiptCount"] == 1
        assert dimensions["logic"]["entries"][0]["subjectId"] == "经营复盘"
        assert dimensions["model"]["entries"][0]["quantityTotals"] == {"cost:CNY": 1.75}
    finally:
        client.app.dependency_overrides.pop(aip_model_runtime.get_store, None)
        client.app.dependency_overrides.pop(aip_model_runtime.get_eval_authority_store, None)


def test_approved_provider_plugin_exact_readback_is_principal_scoped(client) -> None:
    current = client.get(
        "/v1/aip/model-runtime/provider-plugins/agnes-text",
        headers=headers(),
    )
    assert current.status_code == 200, current.text
    current_revision = current.json()["revision"]
    response = client.get(
        f"/v1/aip/model-runtime/provider-plugins/agnes-text?revision={current_revision}",
        headers=headers(),
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["providerPluginId"] == "agnes-text"
    assert payload["revision"] == current_revision
    assert len(payload["contentHash"]) == 64
    assert payload["approvedCapabilities"] == ["llm", "chat", "structured_output"]
    assert "secret" not in response.text.lower()

    canary = client.get(
        f"/v1/aip/model-runtime/provider-plugins/agnes-text?revision={current_revision}",
        headers=headers("dev-org"),
    )
    assert canary.status_code == 404
    assert canary.json()["code"] == "AIP_PROVIDER_PLUGIN_UNAVAILABLE"


class ProviderPublishStore:
    called = False

    def publish_provider(self, scope, actor, key, item, *, expected_version=0):
        self.called = True
        return item


class PluginAuthorityProbe:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls = []

    def validate_ref(self, scope, ref):
        self.calls.append((scope.key, ref.asset_type, ref.asset_id, ref.revision, ref.content_hash))
        if self.fail:
            raise ProviderPluginAuthorityError("provider_plugin_ref_drifted")


def provider_body() -> dict:
    return {
        "tenant": {"orgId": "org-org", "projectId": "dev-project"},
        "providerInstanceId": "agnes-text-qyh-dev",
        "revision": 1,
        "contentHash": "a" * 64,
        "pluginRef": {
            "assetType": "ProviderPluginRevision",
            "assetId": "agnes-text",
            "revision": 1,
            "contentHash": "b" * 64,
        },
        "endpointProfile": {
            "baseUrl": "https://apihub.agnes-ai.com/v1",
            "region": "development-external-unspecified",
            "timeoutMs": 60000,
            "metadata": {},
        },
        "secretRef": "keychain://com.aos.llm/agnes-text/org-org/dev-project/agnes-text-qyh-dev#api-key",
        "secretVersion": "v1",
        "egressPolicyRef": {
            "assetType": "EgressPolicyRevision",
            "assetId": "egress-1",
            "revision": 1,
            "contentHash": "c" * 64,
        },
        "dataClassificationPolicyRef": {
            "assetType": "DataClassificationPolicyRevision",
            "assetId": "classification-1",
            "revision": 1,
            "contentHash": "d" * 64,
        },
        "lifecycle": "validated",
        "createdBy": "caller",
        "createdAt": "2026-08-16T00:00:00Z",
    }


def test_provider_publish_validates_exact_plugin_ref_before_store_write(client) -> None:
    store = ProviderPublishStore()
    authority = PluginAuthorityProbe()
    client.app.dependency_overrides[aip_model_runtime.get_store] = lambda: store
    client.app.dependency_overrides[aip_model_runtime.get_plugin_authority] = lambda: authority
    try:
        response = client.post(
            "/v1/aip/model-runtime/providers",
            headers=headers(**{"Idempotency-Key": "provider-1", "If-Match": "0"}),
            json=provider_body(),
        )
        assert response.status_code == 201, response.text
        assert store.called is True
        assert authority.calls == [
            (("org-org", "dev-project"), "ProviderPluginRevision", "agnes-text", 1, "b" * 64)
        ]
    finally:
        client.app.dependency_overrides.pop(aip_model_runtime.get_store, None)
        client.app.dependency_overrides.pop(aip_model_runtime.get_plugin_authority, None)


def test_provider_publish_fails_before_store_when_plugin_ref_drifted(client) -> None:
    store = ProviderPublishStore()
    authority = PluginAuthorityProbe(fail=True)
    client.app.dependency_overrides[aip_model_runtime.get_store] = lambda: store
    client.app.dependency_overrides[aip_model_runtime.get_plugin_authority] = lambda: authority
    try:
        response = client.post(
            "/v1/aip/model-runtime/providers",
            headers=headers(**{"Idempotency-Key": "provider-2", "If-Match": "0"}),
            json=provider_body(),
        )
        assert response.status_code == 422
        assert response.json()["code"] == "AIP_PROVIDER_PLUGIN_REF_DRIFTED"
        assert store.called is False
    finally:
        client.app.dependency_overrides.pop(aip_model_runtime.get_store, None)
        client.app.dependency_overrides.pop(aip_model_runtime.get_plugin_authority, None)


class EmptyOverviewStore:
    scopes = []

    def list_current_assets(self, scope, kind):
        self.scopes.append((scope.key, kind))
        return []

    def list_eval_gates(self, scope, refs):
        assert refs == []
        return []

    def list_capacity_pools(self, scope):
        return []

    def list_latest_provider_health(self, scope):
        assert scope.key == ("org-org", "dev-project")
        return []


def test_overview_is_secret_free_empty_and_tenant_scoped(client) -> None:
    store = EmptyOverviewStore()
    client.app.dependency_overrides[aip_model_runtime.get_store] = lambda: store
    try:
        response = client.get("/v1/aip/model-runtime/overview", headers=headers())
        assert response.status_code == 200
        payload = response.json()
        assert payload["tenant"] == {"orgId": "org-org", "projectId": "dev-project"}
        assert payload["providers"] == payload["models"] == payload["routes"] == []
        assert payload["capacityPools"] == payload["resolutions"] == []
        assert payload["healthObservations"] == []
        assert "secret" not in response.text.lower()
        assert {scope for scope, _ in store.scopes} == {("org-org", "dev-project")}
        assert {kind for _, kind in store.scopes} == {
            "provider_instance", "registered_model", "runtime_policy", "model_route", "model_price_snapshot",
        }
    finally:
        client.app.dependency_overrides.pop(aip_model_runtime.get_store, None)


def test_chain_overview_is_secret_free_empty_and_tenant_scoped(client) -> None:
    runtime = EmptyOverviewStore()
    usage = EmptyUsageAuthorityStore()
    runtime.scopes = []
    usage.scopes = []
    client.app.dependency_overrides[aip_model_runtime.get_store] = lambda: runtime
    client.app.dependency_overrides[aip_model_runtime.get_eval_authority_store] = lambda: usage
    try:
        response = client.get("/v1/aip/model-runtime/chain-overview", headers=headers())
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["tenant"] == {"orgId": "org-org", "projectId": "dev-project"}
        assert payload["chains"] == []
        assert payload["taskTraces"] == []
        assert payload["modelImpacts"] == []
        assert "secretref" not in response.text.lower()
        assert runtime.scopes[-1] == (("org-org", "dev-project"), "model_route")
        assert usage.scopes == [
            ("receipts", ("org-org", "dev-project"), 1000),
            ("attributions", ("org-org", "dev-project"), 5000),
            ("task-bindings", ("org-org", "dev-project"), 0),
        ]
    finally:
        client.app.dependency_overrides.pop(aip_model_runtime.get_store, None)
        client.app.dependency_overrides.pop(aip_model_runtime.get_eval_authority_store, None)


class CurrentHealthOverviewStore(EmptyOverviewStore):
    current = VersionedAssetRef(
        assetType="ProviderInstanceRevision", assetId="provider-current", revision=2,
        contentHash="a" * 64,
    )
    historical = VersionedAssetRef(
        assetType="ProviderInstanceRevision", assetId="provider-current", revision=1,
        contentHash="b" * 64,
    )

    def list_current_assets(self, scope, kind):
        self.scopes.append((scope.key, kind))
        if kind == "provider_instance":
            return [ModelRuntimeAssetSummary(ref=self.current, lifecycle=ModelRuntimeLifecycle.ACTIVE)]
        return []

    def list_latest_provider_health(self, scope):
        observed_at = datetime.now(UTC)
        common = {
            "tenant": TenantContext(orgId="org-org", projectId="dev-project"),
            "status": "healthy", "observedAt": observed_at,
            "expiresAt": observed_at + timedelta(minutes=15),
        }
        return [
            ProviderHealthObservation(observationId="health-current", provider=self.current, **common),
            ProviderHealthObservation(observationId="health-historical", provider=self.historical, **common),
        ]


def test_overview_only_exposes_health_for_current_exact_provider_revisions(client) -> None:
    store = CurrentHealthOverviewStore()
    client.app.dependency_overrides[aip_model_runtime.get_store] = lambda: store
    try:
        response = client.get("/v1/aip/model-runtime/overview", headers=headers())
        assert response.status_code == 200, response.text
        health = response.json()["healthObservations"]
        assert [item["observationId"] for item in health] == ["health-current"]
        assert health[0]["provider"]["revision"] == 2
    finally:
        client.app.dependency_overrides.pop(aip_model_runtime.get_store, None)
