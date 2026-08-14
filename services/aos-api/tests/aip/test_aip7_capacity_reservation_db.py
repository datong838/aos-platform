from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import psycopg
from psycopg.types.json import Jsonb

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_agent_registry_store import AipAgentRegistryTransitionBlocked
from aos_api.aip_contracts import TenantContext
from aos_api.aip_model_capacity_reservation import AipModelCapacityReservationGate
from aos_api.aip_model_runtime_contracts import ModelRouteResolution, ModelRuntimeReadiness
from aos_api.db import connect, get_dsn
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope("org-org", "dev-project")
CANARY = TenantScope("dev-org", "dev-project")
HASH = "c" * 64
POOL = "test:aip7-capacity:pool"


def ref(kind: str, asset_id: str) -> VersionedAssetRef:
    return VersionedAssetRef(assetType=kind, assetId=asset_id, revision=1, contentHash=HASH)


def resolved() -> ModelRouteResolution:
    return ModelRouteResolution(
        tenant=TenantContext(orgId=SCOPE.org_id, projectId=SCOPE.project_id),
        route=ref("ModelRouteRevision", "test:aip7-capacity:route"),
        policy=ref("RuntimePolicyRevision", "test:aip7-capacity:policy"),
        readiness=ModelRuntimeReadiness.READY,
        selectedModel=ref("RegisteredModelRevision", "test:aip7-capacity:model"),
        selectedProvider=ref("ProviderInstanceRevision", "test:aip7-capacity:provider"),
        selectedPriceSnapshot=ref("ModelPriceSnapshotRevision", "test:aip7-capacity:price"),
        blockerCodes=[],
        resolvedAt=datetime.now(UTC),
    )


def setup_pool() -> None:
    with psycopg.connect(get_dsn()) as conn:
        conn.execute(
            "INSERT INTO twa_org(id,name) VALUES (%s,%s) ON CONFLICT(id) DO NOTHING",
            (SCOPE.org_id, "栖月汇商贸有限公司"),
        )
        conn.execute(
            """INSERT INTO twa_workspace(org_id,project_id,name) VALUES (%s,%s,%s)
               ON CONFLICT(org_id,project_id) DO NOTHING""",
            (*SCOPE.key, "默认工作区"),
        )
        conn.commit()
    route = ref("ModelRouteRevision", "test:aip7-capacity:route")
    model = ref("RegisteredModelRevision", "test:aip7-capacity:model")
    provider = ref("ProviderInstanceRevision", "test:aip7-capacity:provider")
    with connect(SCOPE) as conn:
        conn.execute(
            """INSERT INTO aip_model_capacity_pool_head
               (org_id,project_id,pool_id,current_revision,version)
               VALUES (%s,%s,%s,1,1)""",
            (*SCOPE.key, POOL),
        )
        conn.execute(
            """INSERT INTO aip_model_capacity_pool_revision
               (org_id,project_id,pool_id,revision,content_hash,
                route_ref,model_ref,provider_ref,
                route_id,route_revision,route_hash,model_id,model_revision,model_hash,
                provider_id,provider_revision,provider_hash,max_concurrency,max_token_units,
                token_unit_per_reservation,lease_seconds,lifecycle,created_by)
               VALUES (%s,%s,%s,1,%s,%s,%s,%s,%s,1,%s,%s,1,%s,%s,1,%s,100,10000,100,300,'active','pytest')""",
            (
                *SCOPE.key,
                POOL,
                HASH,
                Jsonb(route.model_dump(mode="json", by_alias=True)),
                Jsonb(model.model_dump(mode="json", by_alias=True)),
                Jsonb(provider.model_dump(mode="json", by_alias=True)),
                route.asset_id,
                route.content_hash,
                model.asset_id,
                model.content_hash,
                provider.asset_id,
                provider.content_hash,
            ),
        )
        conn.commit()


def test_101_concurrent_reservations_never_oversell_100_and_canary_sees_zero() -> None:
    setup_pool()
    gate = AipModelCapacityReservationGate()

    def reserve(index: int) -> bool:
        try:
            gate.reserve(SCOPE, resolved(), f"test:aip7-capacity:run:{index}")
            return True
        except AipAgentRegistryTransitionBlocked as exc:
            assert "capacity_concurrency_exhausted" in str(exc)
            return False

    with ThreadPoolExecutor(max_workers=24) as executor:
        outcomes = list(executor.map(reserve, range(101)))
    assert outcomes.count(True) == 100
    assert outcomes.count(False) == 1
    with connect(CANARY) as conn:
        visible = conn.execute(
            "SELECT COUNT(*) AS count FROM aip_model_capacity_reservation"
        ).fetchone()
    assert int(visible["count"]) == 0
