from contextlib import contextmanager
from datetime import UTC, datetime

import pytest

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_agent_registry_store import (
    AipAgentRegistryConflict,
    AipAgentRegistryTransitionBlocked,
)
from aos_api.aip_contracts import TenantContext
from aos_api.aip_model_capacity_reservation import AipModelCapacityReservationGate
from aos_api.aip_model_runtime_contracts import ModelRouteResolution, ModelRuntimeReadiness
from aos_api.tenant_scope import TenantScope

NOW = datetime(2026, 8, 14, tzinfo=UTC)
SCOPE = TenantScope("org-org", "dev-project")
HASH = "a" * 64


def ref(kind: str, asset_id: str) -> VersionedAssetRef:
    return VersionedAssetRef(
        assetType=kind, assetId=asset_id, revision=1, contentHash=HASH
    )


def resolution() -> ModelRouteResolution:
    return ModelRouteResolution(
        tenant=TenantContext(orgId="org-org", projectId="dev-project"),
        route=ref("ModelRouteRevision", "route-1"),
        policy=ref("RuntimePolicyRevision", "policy-1"),
        readiness=ModelRuntimeReadiness.READY,
        selectedModel=ref("RegisteredModelRevision", "model-1"),
        selectedProvider=ref("ProviderInstanceRevision", "provider-1"),
        selectedPriceSnapshot=ref("ModelPriceSnapshotRevision", "price-1"),
        blockerCodes=[],
        resolvedAt=NOW,
    )


class Result:
    def __init__(self, *, one=None, all_rows=None):
        self.one = one
        self.all_rows = all_rows or []

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.all_rows


class Conn:
    def __init__(self, *, pool=True, replay=None, requests=0, tokens=0):
        self.pool = pool
        self.replay = replay
        if self.replay is not None and "is_active" not in self.replay:
            self.replay["is_active"] = self.replay.get("status") in {"reserved", "consumed"}
        self.requests = requests
        self.tokens = tokens
        self.events = []
        self.inserted_reservation = None
        self.updated_status = None
        self.commits = 0

    def execute(self, query, args):
        sql = " ".join(query.split())
        if "FROM aip_model_capacity_pool_head" in sql:
            if not self.pool:
                return Result(one=None)
            return Result(
                one={
                    "pool_id": "pool-1",
                    "current_revision": 1,
                    "max_concurrency": 100,
                    "max_token_units": 10_000,
                    "token_unit_per_reservation": 100,
                    "lease_seconds": 300,
                }
            )
        if "WHERE org_id=%s AND project_id=%s AND agent_run_id=%s" in sql:
            return Result(one=self.replay)
        if sql.startswith("UPDATE aip_model_capacity_reservation") and "expires_at<=NOW()" in sql:
            return Result(all_rows=[])
        if sql.startswith("SELECT COUNT(*)"):
            return Result(one={"request_units": self.requests, "token_units": self.tokens})
        if sql.startswith("INSERT INTO aip_model_capacity_reservation"):
            self.inserted_reservation = args[2]
            return Result(one={"reservation_id": args[2]})
        if sql.startswith("UPDATE aip_model_capacity_reservation") and "SET status='reserved'" in sql:
            self.updated_status = "reserved"
            return Result(one={"reservation_id": args[-1]})
        if sql.startswith("INSERT INTO aip_model_capacity_event"):
            self.events.append(args[4])
            return Result()
        if "WHERE org_id=%s AND project_id=%s AND reservation_id=%s FOR UPDATE" in sql:
            return Result(one=self.replay)
        if "SELECT reservation_id FROM aip_model_capacity_reservation" in sql:
            return Result(one=self.replay)
        if sql.startswith("UPDATE aip_model_capacity_reservation SET status=%s"):
            self.updated_status = args[0]
            return Result()
        raise AssertionError(sql)

    def commit(self):
        self.commits += 1


def factory(conn: Conn):
    @contextmanager
    def connect(scope):
        assert scope == SCOPE
        yield conn

    return connect


def test_reserve_binds_exact_pool_and_writes_append_event() -> None:
    conn = Conn()
    reservation_id = AipModelCapacityReservationGate(factory(conn)).reserve(
        SCOPE, resolution(), "run-1"
    )
    assert reservation_id == conn.inserted_reservation
    assert conn.events == ["reserved"]
    assert conn.commits == 1


def test_reserve_replays_same_agent_run_and_rejects_payload_drift() -> None:
    gate = AipModelCapacityReservationGate()
    exact = gate._exact_resolution(resolution())
    replay = {
        "reservation_id": "capres-1",
        "request_hash": gate._request_hash("run-1", exact, "pool-1", 1, 100),
        "status": "reserved",
    }
    conn = Conn(replay=replay)
    assert AipModelCapacityReservationGate(factory(conn)).reserve(
        SCOPE, resolution(), "run-1"
    ) == "capres-1"
    replay["request_hash"] = "b" * 64
    with pytest.raises(AipAgentRegistryConflict, match="payload drifted"):
        AipModelCapacityReservationGate(factory(conn)).reserve(
            SCOPE, resolution(), "run-1"
        )


def test_reserve_fails_closed_without_pool_and_at_100_concurrency() -> None:
    with pytest.raises(AipAgentRegistryTransitionBlocked, match="pool_authority"):
        AipModelCapacityReservationGate(factory(Conn(pool=False))).reserve(
            SCOPE, resolution(), "run-1"
        )
    with pytest.raises(AipAgentRegistryTransitionBlocked, match="concurrency_exhausted"):
        AipModelCapacityReservationGate(
            factory(Conn(requests=100, tokens=10_000))
        ).reserve(SCOPE, resolution(), "run-101")


def test_release_and_consume_are_idempotent_and_state_guarded() -> None:
    reserved = Conn(replay={"status": "reserved"})
    gate = AipModelCapacityReservationGate(factory(reserved))
    gate.release(SCOPE, "capres-1")
    assert reserved.updated_status == "released"
    assert reserved.events == ["released"]
    already = Conn(replay={"status": "consumed"})
    AipModelCapacityReservationGate(factory(already)).consume(SCOPE, "capres-1")
    assert already.commits == 0
    with pytest.raises(AipAgentRegistryConflict, match="cannot become released"):
        AipModelCapacityReservationGate(factory(already)).release(SCOPE, "capres-1")


def test_released_reservation_can_be_reactivated_for_same_exact_run() -> None:
    gate = AipModelCapacityReservationGate()
    exact = gate._exact_resolution(resolution())
    conn = Conn(
        replay={
            "reservation_id": "capres-1",
            "request_hash": gate._request_hash("run-1", exact, "pool-1", 1, 100),
            "status": "released",
        }
    )
    assert AipModelCapacityReservationGate(factory(conn)).reserve(
        SCOPE, resolution(), "run-1"
    ) == "capres-1"
    assert conn.updated_status == "reserved" and conn.events == ["reserved"]


def test_release_for_run_resolves_tenant_scoped_reservation() -> None:
    conn = Conn(replay={"reservation_id": "capres-1", "status": "reserved"})
    AipModelCapacityReservationGate(factory(conn)).release_for_run(SCOPE, "run-1")
    assert conn.updated_status == "released" and conn.events == ["released"]


def test_tenant_scope_is_always_forwarded_to_connection_factory() -> None:
    seen = []

    @contextmanager
    def scoped(scope):
        seen.append(scope)
        yield Conn(pool=False)

    with pytest.raises(AipAgentRegistryTransitionBlocked):
        AipModelCapacityReservationGate(scoped).reserve(SCOPE, resolution(), "run-1")
    assert seen == [SCOPE]
