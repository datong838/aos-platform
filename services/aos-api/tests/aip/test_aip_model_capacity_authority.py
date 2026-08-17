from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
import uuid

import pytest

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_model_capacity_authority import (
    AipModelCapacityAuthorityStore,
    CapacityPoolRevisionCreate,
    CapacityPoolAuthorityConflict,
    CapacityPoolAuthorityNotFound,
    materialize_capacity_pool,
)
from aos_api.tenant_scope import TenantScope


NOW = datetime(2026, 8, 17, tzinfo=UTC)
HASH = "a" * 64


def ref(kind: str, asset_id: str, digest: str = HASH) -> VersionedAssetRef:
    return VersionedAssetRef(assetType=kind, assetId=asset_id, revision=1, contentHash=digest)


def request(pool_id: str | None = None) -> CapacityPoolRevisionCreate:
    return CapacityPoolRevisionCreate(
        poolId=pool_id or f"test-capacity-{uuid.uuid4().hex}",
        revision=1,
        routeRef=ref("ModelRouteRevision", "route-qyh-text-dev"),
        modelRef=ref("RegisteredModelRevision", "agnes-text-primary"),
        providerRef=ref("ProviderInstanceRevision", "agnes-text-qyh-dev"),
        maxConcurrency=2,
        maxTokenUnits=16_000,
        tokenUnitPerReservation=8_000,
        leaseSeconds=60,
        lifecycle="active",
    )


def test_contract_materializes_deterministic_hash_and_rejects_wrong_ref_kind():
    scope = TenantScope("org-org", "dev-project")
    item = request()
    first = materialize_capacity_pool(scope, "owner", item, created_at=NOW)
    second = materialize_capacity_pool(scope, "owner", item, created_at=NOW)
    assert first.content_hash == second.content_hash
    assert first.tenant.org_id == "org-org"

    with pytest.raises(ValueError, match="route_ref"):
        CapacityPoolRevisionCreate.model_validate(
            {
                **request().model_dump(by_alias=True),
                "routeRef": ref("RegisteredModelRevision", "bad").model_dump(
                    by_alias=True
                ),
            }
        )


class ModelStore:
    def get_route(self, _scope, _asset_id, _revision):
        return SimpleNamespace(
            route_id="route-qyh-text-dev", revision=1, content_hash=HASH,
            lifecycle=SimpleNamespace(value="active"),
            candidates=[SimpleNamespace(model=ref("RegisteredModelRevision", "agnes-text-primary"))],
        )

    def get_model(self, _scope, _asset_id, _revision):
        return SimpleNamespace(
            registered_model_id="agnes-text-primary", revision=1, content_hash=HASH,
            lifecycle=SimpleNamespace(value="active"),
            provider=ref("ProviderInstanceRevision", "agnes-text-qyh-dev"),
        )

    def get_provider(self, _scope, _asset_id, _revision):
        return SimpleNamespace(
            provider_instance_id="agnes-text-qyh-dev", revision=1, content_hash=HASH,
            lifecycle=SimpleNamespace(value="active"),
        )


def test_store_replays_exact_publication_and_isolates_canary():
    scope = TenantScope("org-org", "dev-project")
    canary = TenantScope("dev-org", "dev-project")
    store = AipModelCapacityAuthorityStore(model_store=ModelStore())
    item = request()
    first = store.publish(scope, "pytest", "capacity-r1", item)
    assert store.publish(scope, "pytest", "capacity-r1", item) == first
    assert store.get(scope, item.pool_id, 1).content_hash == first.content_hash
    with pytest.raises(CapacityPoolAuthorityNotFound):
        store.get(canary, item.pool_id, 1)
    with pytest.raises(CapacityPoolAuthorityConflict):
        store.publish(
            scope,
            "pytest",
            "capacity-r1-drift",
            item.model_copy(update={"max_concurrency": 3}),
        )
