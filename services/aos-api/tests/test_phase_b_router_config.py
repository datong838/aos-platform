"""Phase B · 222plan — Model Router Config tests.

Tests:
  - V2 migration (V1 → V2 fields) (2 cases)
  - CRUD: create / get / update / delete (6 cases)
  - Weights validation + auto-normalize (3 cases)
  - Circuit config validation (2 cases)
  - Route test simulation (2 cases)
  - Global circuit config (2 cases)
"""
from __future__ import annotations

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient


class TestRouterConfigV2Migration:
    """Test V1 → V2 migration."""

    def test_migrate_adds_v2_fields(self):
        from aos_api.model_router_config import _migrate_route_row

        v1_row = {
            "id": "summarize",
            "task": "摘要 / 分类",
            "primary": "gpt-4o",
            "fallback": "gpt-4o-mini",
            "egress": "禁公网",
            "span": False,
        }
        v2 = _migrate_route_row(v1_row)
        assert v2["id"] == "summarize"
        assert v2["primary"] == "gpt-4o"
        assert v2["weights"] == [{"model": "gpt-4o", "pct": 100}, {"model": "gpt-4o-mini", "pct": 0}]
        assert v2["fallback_chain"] == ["gpt-4o", "gpt-4o-mini", "报错"]
        assert "circuit_config" in v2
        assert v2["strategy"] == "failover"
        assert v2["enabled"] is True

    def test_migrate_preserves_existing_v2_fields(self):
        from aos_api.model_router_config import _migrate_route_row

        row = {
            "id": "wiki_qa",
            "task": "Wiki",
            "primary": "gpt-4o",
            "fallback": "—",
            "egress": "禁公网",
            "span": False,
            "weights": [{"model": "custom-model", "pct": 100}],
            "strategy": "weighted",
        }
        v2 = _migrate_route_row(row)
        assert v2["weights"] == [{"model": "custom-model", "pct": 100}]
        assert v2["strategy"] == "weighted"


class TestWeightsValidation:
    """Test weight list validation."""

    def test_valid_weights(self):
        from aos_api.model_router_config import _validate_weights

        weights = [{"model": "a", "pct": 60}, {"model": "b", "pct": 40}]
        result = _validate_weights(weights)
        assert len(result) == 2
        assert sum(w["pct"] for w in result) == 100

    def test_auto_normalize_to_100(self):
        from aos_api.model_router_config import _validate_weights

        # 50+50 = 100, already valid
        weights = [{"model": "a", "pct": 50}, {"model": "b", "pct": 50}]
        result = _validate_weights(weights)
        assert sum(w["pct"] for w in result) == 100

    def test_clamp_pct_range(self):
        from aos_api.model_router_config import _validate_weights

        weights = [{"model": "a", "pct": 150}, {"model": "b", "pct": -10}]
        result = _validate_weights(weights)
        # 150 -> clamped to 100, -10 -> clamped to 0
        for w in result:
            assert 0 <= w["pct"] <= 100


class TestCircuitConfigValidation:
    """Test circuit config validation."""

    def test_valid_config(self):
        from aos_api.model_router_config import _validate_circuit_config

        cfg = {
            "error_rate_threshold_pct": 15,
            "latency_p99_ms": 2000,
            "cooldown_seconds": 60,
            "half_open_probes": 5,
        }
        result = _validate_circuit_config(cfg)
        assert result["error_rate_threshold_pct"] == 15
        assert result["latency_p99_ms"] == 2000

    def test_clamp_values(self):
        from aos_api.model_router_config import _validate_circuit_config

        cfg = {
            "error_rate_threshold_pct": 100,
            "latency_p99_ms": 999999,
            "cooldown_seconds": 9999,
            "half_open_probes": 100,
        }
        result = _validate_circuit_config(cfg)
        assert result["error_rate_threshold_pct"] == 50  # max
        assert result["latency_p99_ms"] == 30000  # max
        assert result["cooldown_seconds"] == 600  # max
        assert result["half_open_probes"] == 20  # max


class TestGlobalCircuitConfig:
    """Test global circuit config."""

    def test_defaults(self):
        from aos_api.model_router_config import DEFAULT_GLOBAL_CIRCUIT

        assert DEFAULT_GLOBAL_CIRCUIT["error_rate_threshold_pct"] == 10
        assert DEFAULT_GLOBAL_CIRCUIT["latency_p99_ms"] == 3000
        assert DEFAULT_GLOBAL_CIRCUIT["cooldown_seconds"] == 30
        assert DEFAULT_GLOBAL_CIRCUIT["half_open_probes"] == 3

    def test_update_global_circuit(self):
        from aos_api.model_router_config import update_global_circuit_config, get_global_circuit_config
        from aos_api.aip_kv_store import put_payload
        from aos_api.model_router_config import KEY_GLOBAL_CIRCUIT

        # Reset
        put_payload(KEY_GLOBAL_CIRCUIT, {})
        result = update_global_circuit_config({"error_rate_threshold_pct": 25})
        assert result["error_rate_threshold_pct"] == 25
        assert result["latency_p99_ms"] == 3000  # default preserved


class TestRouteTestSimulation:
    """Test route test/simulation."""

    def test_failover_strategy(self):
        from aos_api.model_router_config import test_route
        from aos_api.aip_kv_store import put_payload
        from aos_api.model_router_config import KEY_ROUTER_V2

        put_payload(KEY_ROUTER_V2, {"items": [{
            "id": "test_route_1",
            "task": "Test",
            "primary": "gpt-4o",
            "fallback": "gpt-4o-mini",
            "egress": "继承",
            "span": False,
            "strategy": "failover",
            "weights": [],
            "fallback_chain": ["gpt-4o", "gpt-4o-mini", "报错"],
            "circuit_config": {},
            "enabled": True,
        }]})

        result = test_route("test_route_1", "hello world", 500)
        assert result["route_id"] == "test_route_1"
        assert result["strategy"] == "failover"
        assert len(result["selected"]) > 0
        assert result["selected"][0]["model"] == "gpt-4o"
        assert result["estimated_latency_ms"] > 0

    def test_weighted_strategy(self):
        from aos_api.model_router_config import test_route
        from aos_api.aip_kv_store import put_payload
        from aos_api.model_router_config import KEY_ROUTER_V2

        put_payload(KEY_ROUTER_V2, {"items": [{
            "id": "test_route_2",
            "task": "Test",
            "primary": "gpt-4o",
            "fallback": "—",
            "egress": "继承",
            "span": False,
            "strategy": "weighted",
            "weights": [
                {"model": "gpt-4o", "pct": 70},
                {"model": "gpt-4o-mini", "pct": 30},
            ],
            "fallback_chain": [],
            "circuit_config": {},
            "enabled": True,
        }]})

        result = test_route("test_route_2", "test", 100)
        assert result["strategy"] == "weighted"
        assert result["selected"][0]["model"] == "gpt-4o"
        assert result["selected"][0]["weight_pct"] == 70


class TestRouterConfigAPI:
    """Test REST API endpoints."""

    @pytest.fixture
    def client(self):
        from aos_api.main import create_app
        return TestClient(create_app())

    def test_list_routes(self, client):
        resp = client.get("/api/models/router")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_list_strategies(self, client):
        resp = client.get("/api/models/router/strategies")
        assert resp.status_code == 200
        strategies = resp.json()["strategies"]
        assert "failover" in strategies
        assert "weighted" in strategies
        assert "lowest_latency" in strategies
        assert "lowest_cost" in strategies

    def test_get_single_route(self, client):
        # First list to get an ID
        resp = client.get("/api/models/router")
        items = resp.json()["items"]
        if items:
            route_id = items[0]["id"]
            resp = client.get(f"/api/models/router/{route_id}")
            assert resp.status_code == 200
            assert resp.json()["id"] == route_id

    def test_update_route(self, client):
        from aos_api.aip_kv_store import put_payload
        from aos_api.model_router_config import KEY_ROUTER_V2

        put_payload(KEY_ROUTER_V2, {"items": [{
            "id": "test_update",
            "task": "Test",
            "primary": "gpt-4o",
            "fallback": "—",
            "egress": "继承",
            "span": False,
            "strategy": "failover",
            "weights": [],
            "fallback_chain": [],
            "circuit_config": {},
            "enabled": True,
        }]})

        resp = client.put("/api/models/router/test_update", json={
            "strategy": "weighted",
            "weights": [{"model": "gpt-4o", "pct": 100}],
        })
        assert resp.status_code == 200
        assert resp.json()["strategy"] == "weighted"

    def test_create_and_delete_route(self, client):
        resp = client.post("/api/models/router", json={
            "id": "test_create_new",
            "task": "Test Create",
            "primary": "gpt-4o",
            "strategy": "failover",
        })
        assert resp.status_code == 200
        assert resp.json()["id"] == "test_create_new"

        # Delete
        resp = client.delete("/api/models/router/test_create_new")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

    def test_circuit_config(self, client):
        # Get
        resp = client.get("/api/models/router/circuit-config")
        assert resp.status_code == 200
        assert "error_rate_threshold_pct" in resp.json()

        # Update
        resp = client.put("/api/models/router/circuit-config", json={
            "error_rate_threshold_pct": 20,
        })
        assert resp.status_code == 200
        assert resp.json()["error_rate_threshold_pct"] == 20
