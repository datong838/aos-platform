"""GT-b4 RED: Route pool authority cannot stand in for a physical Provider cap."""

import pytest
import psycopg
from psycopg.types.json import Jsonb
from datetime import UTC, datetime

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_agent_registry_store import AipAgentRegistryTransitionBlocked
from aos_api.aip_contracts import TenantContext
from aos_api.aip_model_capacity_reservation import AipModelCapacityReservationGate
from aos_api.aip_model_runtime_contracts import ModelRouteResolution, ModelRuntimeReadiness
from aos_api.db import connect, get_dsn
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
HASH = "d" * 64


def _ref(kind: str, asset_id: str) -> VersionedAssetRef:
    return VersionedAssetRef(assetType=kind, assetId=asset_id, revision=1, contentHash=HASH)


def _seed_route_pool_without_physical_account(suffix: str = "one") -> ModelRouteResolution:
    with psycopg.connect(get_dsn()) as conn:
        conn.execute("INSERT INTO twa_org(id,name) VALUES (%s,%s) ON CONFLICT(id) DO NOTHING",
                     (SCOPE.org_id, "栖月汇商贸有限公司"))
        conn.execute("""INSERT INTO twa_workspace(org_id,project_id,name) VALUES (%s,%s,%s)
                        ON CONFLICT(org_id,project_id) DO NOTHING""",
                     (*SCOPE.key, "默认工作区"))
    route = _ref("ModelRouteRevision", f"test:gtb4:route:{suffix}")
    model = _ref("RegisteredModelRevision", f"test:gtb4:model:{suffix}")
    provider = _ref("ProviderInstanceRevision", "test:gtb4:provider")
    pool_id = f"test:gtb4:pool:{suffix}"
    with connect(SCOPE) as conn:
        conn.execute("""INSERT INTO aip_model_capacity_pool_head
            (org_id,project_id,pool_id,current_revision,version)
            VALUES (%s,%s,%s,1,1)""", (*SCOPE.key, pool_id))
        conn.execute("""INSERT INTO aip_model_capacity_pool_revision
            (org_id,project_id,pool_id,revision,content_hash,route_ref,model_ref,provider_ref,
             route_id,route_revision,route_hash,model_id,model_revision,model_hash,
             provider_id,provider_revision,provider_hash,max_concurrency,max_token_units,
             token_unit_per_reservation,lease_seconds,lifecycle,created_by)
            VALUES (%s,%s,%s,1,%s,%s,%s,%s,%s,1,%s,%s,1,%s,%s,1,%s,
                    1,100,10,300,'active','pytest')""",
            (*SCOPE.key, pool_id, HASH, Jsonb(route.model_dump(mode="json", by_alias=True)),
             Jsonb(model.model_dump(mode="json", by_alias=True)),
             Jsonb(provider.model_dump(mode="json", by_alias=True)),
             route.asset_id, route.content_hash, model.asset_id, model.content_hash,
             provider.asset_id, provider.content_hash))
    return ModelRouteResolution(
        tenant=TenantContext(orgId=SCOPE.org_id, projectId=SCOPE.project_id),
        route=route, policy=_ref("RuntimePolicyRevision", "test:gtb4:policy"),
        readiness=ModelRuntimeReadiness.READY, selectedModel=model,
        selectedProvider=provider,
        selectedPriceSnapshot=_ref("ModelPriceSnapshotRevision", "test:gtb4:price"),
        blockerCodes=[], resolvedAt=datetime.now(UTC),
    )


@pytest.mark.xfail(
    strict=True,
    reason="GT-b4: no formal shared Provider capacity account or ledger exists yet",
)
def test_normal_reservation_requires_shared_provider_capacity_authority() -> None:
    """Future ordinary path must reject a pool-only reservation at cutover."""
    resolution = _seed_route_pool_without_physical_account()
    with pytest.raises(AipAgentRegistryTransitionBlocked, match="physical_capacity_authority_unavailable"):
        AipModelCapacityReservationGate().reserve(SCOPE, resolution, "test:gtb4:no-physical-account")


@pytest.mark.xfail(
    strict=True,
    reason="GT-b4: two Route pools for one Provider do not share a physical occupancy ledger",
)
def test_two_route_pools_for_one_provider_cannot_each_take_full_physical_slot() -> None:
    first = _seed_route_pool_without_physical_account("first")
    second = _seed_route_pool_without_physical_account("second")
    gate = AipModelCapacityReservationGate()
    gate.reserve(SCOPE, first, "test:gtb4:ordinary:first")
    with pytest.raises(AipAgentRegistryTransitionBlocked, match="physical_capacity"):
        gate.reserve(SCOPE, second, "test:gtb4:ordinary:second")


@pytest.mark.parametrize("fault", ["tenant", "blocked_mutation", "ref_kind", "empty_run", "spaced_run", "missing_scope"])
def test_capacity_entry_rejects_invalid_source_before_original_pg_occupation(fault):
    """Maintenance pool negative; this is no legitimate model quality positive."""
    from uuid import uuid4
    resolution = _seed_route_pool_without_physical_account("entry-" + uuid4().hex)
    run_id = "capacity-entry-" + uuid4().hex
    if fault == "tenant":
        resolution = resolution.model_copy(update={"tenant": TenantContext(
            orgId="dev-org", projectId="dev-project")})
    elif fault == "blocked_mutation":
        resolution = resolution.model_copy(update={"readiness": ModelRuntimeReadiness.BLOCKED,
                                                   "blocker_codes": ["unavailable"]})
    elif fault == "ref_kind":
        resolution = resolution.model_copy(update={"selected_provider":
            resolution.selected_provider.model_copy(update={"asset_type": "RegisteredModelRevision"})})
    elif fault == "empty_run":
        run_id = ""
    elif fault == "spaced_run":
        run_id = " " + run_id
    def snapshot(scope):
        with connect(scope) as conn:
            return [conn.execute(f"SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text),"
                f"'[]'::jsonb) AS value FROM {table} t").fetchone()['value']
                for table in ('aip_model_capacity_reservation', 'aip_model_capacity_event')]
    canary = TenantScope('dev-org', 'dev-project')
    before, isolated = snapshot(SCOPE), snapshot(canary)
    from contextlib import contextmanager
    opened = []
    @contextmanager
    def traced_caller(scope):
        opened.append(scope)
        with connect(scope) as conn:
            yield conn
    with pytest.raises(AipAgentRegistryTransitionBlocked, match="capacity_exact_resolution_required"):
        AipModelCapacityReservationGate(traced_caller).reserve(
            None if fault == "missing_scope" else SCOPE, resolution, run_id)
    assert opened == []
    assert snapshot(SCOPE) == before and snapshot(canary) == isolated
