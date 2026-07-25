"""Phase B · 222plan — Model Router Configuration Engine.

Extends aip_kv_store RouteRule with V2 fields:
  - weights: multi-model percentage distribution
  - fallback_chain: ordered chain of model IDs
  - circuit_config: per-route circuit breaker thresholds
  - global_circuit_config: system-wide circuit breaker defaults
  - strategy: weighted | failover | lowest_latency | lowest_cost

Also bridges to llm_routing.py's FailoverEngine for live circuit state.
"""
from __future__ import annotations

from typing import Any
from datetime import datetime, timezone

from aos_api.aip_kv_store import (
    get_payload,
    put_payload,
    get_model_routes,
    put_model_routes,
    DEFAULT_ROUTE_DEFS,
    EGRESS_DEFAULTS,
)
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.model_router_config")

# ---------------------------------------------------------------------------
# KV keys
# ---------------------------------------------------------------------------

KEY_ROUTER_V2 = "model_router_v2"
KEY_GLOBAL_CIRCUIT = "global_circuit_config"

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_GLOBAL_CIRCUIT: dict[str, Any] = {
    "error_rate_threshold_pct": 10,
    "latency_p99_ms": 3000,
    "cooldown_seconds": 30,
    "half_open_probes": 3,
}

STRATEGIES = ["weighted", "failover", "lowest_latency", "lowest_cost"]


def _default_weights(primary: str, fallback: str) -> list[dict[str, Any]]:
    """Build a default 100%/0% weight list from primary/fallback."""
    weights: list[dict[str, Any]] = []
    if primary and primary != "—":
        weights.append({"model": primary, "pct": 100})
    if fallback and fallback != "—":
        weights.append({"model": fallback, "pct": 0})
    return weights


def _default_fallback_chain(primary: str, fallback: str) -> list[str]:
    chain: list[str] = []
    if primary and primary != "—":
        chain.append(primary)
    if fallback and fallback != "—":
        chain.append(fallback)
    chain.append("报错")
    return chain


def _default_circuit_config() -> dict[str, Any]:
    return dict(DEFAULT_GLOBAL_CIRCUIT)


def _migrate_route_row(row: dict[str, Any]) -> dict[str, Any]:
    """Ensure a V1 RouteRow has all V2 fields."""
    primary = row.get("primary", "—")
    fallback = row.get("fallback", "—")
    return {
        "id": row["id"],
        "task": row.get("task", row["id"]),
        "primary": primary,
        "fallback": fallback,
        "egress": row.get("egress", EGRESS_DEFAULTS.get(row["id"], "继承")),
        "span": bool(row.get("span", False)),
        # V2 fields (with defaults)
        "weights": row.get("weights") or _default_weights(primary, fallback),
        "fallback_chain": row.get("fallback_chain") or _default_fallback_chain(primary, fallback),
        "circuit_config": row.get("circuit_config") or _default_circuit_config(),
        "strategy": row.get("strategy", "failover"),
        "enabled": row.get("enabled", True),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_route_rules_v2(model_ids: list[str] | None = None) -> list[dict[str, Any]]:
    """Get all route rules with V2 fields. Falls back to V1 + migration."""
    stored = get_payload(KEY_ROUTER_V2)
    if stored and isinstance(stored.get("items"), list) and stored["items"]:
        return [_migrate_route_row(r) for r in stored["items"]]
    # Migrate from V1
    v1 = get_model_routes(model_ids)
    migrated = [_migrate_route_row(r) for r in v1]
    # Persist migration
    put_payload(KEY_ROUTER_V2, {"items": migrated})
    log.info("router_v2_migrated rows=%d", len(migrated))
    return migrated


def get_route_rule_v2(route_id: str) -> dict[str, Any] | None:
    rules = get_route_rules_v2()
    return next((r for r in rules if r["id"] == route_id), None)


def update_route_rule_v2(route_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    """Update a single route rule. Returns the updated rule."""
    rules = get_route_rules_v2()
    found = None
    for r in rules:
        if r["id"] == route_id:
            # Apply updates
            if "weights" in updates:
                r["weights"] = _validate_weights(updates["weights"])
            if "fallback_chain" in updates:
                r["fallback_chain"] = [str(m) for m in updates["fallback_chain"]]
            if "circuit_config" in updates:
                r["circuit_config"] = _validate_circuit_config(updates["circuit_config"])
            if "strategy" in updates:
                strategy = updates["strategy"]
                if strategy not in STRATEGIES:
                    raise ValueError(f"Invalid strategy: {strategy}")
                r["strategy"] = strategy
            if "primary" in updates:
                r["primary"] = str(updates["primary"])
            if "fallback" in updates:
                r["fallback"] = str(updates["fallback"])
            if "egress" in updates:
                r["egress"] = str(updates["egress"])
            if "task" in updates:
                r["task"] = str(updates["task"])
            if "enabled" in updates:
                r["enabled"] = bool(updates["enabled"])
            found = r
            break
    if not found:
        raise KeyError(f"Route rule not found: {route_id}")
    put_payload(KEY_ROUTER_V2, {"items": rules})
    log.info("router_v2_updated id=%s", route_id)
    return found


def create_route_rule_v2(data: dict[str, Any]) -> dict[str, Any]:
    """Create a new route rule."""
    rules = get_route_rules_v2()
    new_id = str(data.get("id") or f"route_{len(rules) + 1}")
    if any(r["id"] == new_id for r in rules):
        raise ValueError(f"Route rule already exists: {new_id}")
    row = _migrate_route_row({
        "id": new_id,
        "task": str(data.get("task", new_id)),
        "primary": str(data.get("primary", "—")),
        "fallback": str(data.get("fallback", "—")),
        "egress": str(data.get("egress", "继承")),
        "span": bool(data.get("span", False)),
    })
    # Apply V2 fields from data
    if "weights" in data:
        row["weights"] = _validate_weights(data["weights"])
    if "fallback_chain" in data:
        row["fallback_chain"] = [str(m) for m in data["fallback_chain"]]
    if "circuit_config" in data:
        row["circuit_config"] = _validate_circuit_config(data["circuit_config"])
    if "strategy" in data:
        row["strategy"] = data["strategy"]
    if "enabled" in data:
        row["enabled"] = bool(data["enabled"])
    rules.append(row)
    put_payload(KEY_ROUTER_V2, {"items": rules})
    log.info("router_v2_created id=%s", new_id)
    return row


def delete_route_rule_v2(route_id: str) -> bool:
    """Delete a route rule by ID."""
    rules = get_route_rules_v2()
    filtered = [r for r in rules if r["id"] != route_id]
    if len(filtered) == len(rules):
        return False
    put_payload(KEY_ROUTER_V2, {"items": filtered})
    log.info("router_v2_deleted id=%s", route_id)
    return True


# ---------------------------------------------------------------------------
# Global circuit config
# ---------------------------------------------------------------------------

def get_global_circuit_config() -> dict[str, Any]:
    stored = get_payload(KEY_GLOBAL_CIRCUIT)
    if stored:
        return {**DEFAULT_GLOBAL_CIRCUIT, **stored}
    return dict(DEFAULT_GLOBAL_CIRCUIT)


def update_global_circuit_config(updates: dict[str, Any]) -> dict[str, Any]:
    cfg = get_global_circuit_config()
    validated = _validate_circuit_config(updates)
    cfg.update(validated)
    put_payload(KEY_GLOBAL_CIRCUIT, cfg)
    log.info("global_circuit_updated")
    return cfg


# ---------------------------------------------------------------------------
# Route test (simulation)
# ---------------------------------------------------------------------------

def test_route(route_id: str, prompt: str = "", context_length: int = 0) -> dict[str, Any]:
    """Simulate a routing decision for a given route rule + prompt.

    Returns which model(s) would be selected and simulated metrics.
    """
    rule = get_route_rule_v2(route_id)
    if not rule:
        raise KeyError(f"Route not found: {route_id}")

    strategy = rule.get("strategy", "failover")
    weights = rule.get("weights", [])
    chain = rule.get("fallback_chain", [])

    # Simulate based on strategy
    selected_models: list[dict[str, Any]] = []

    if strategy == "weighted" and weights:
        # Pick the model with highest weight
        best = max(weights, key=lambda w: w.get("pct", 0))
        selected_models.append({
            "model": best["model"],
            "weight_pct": best["pct"],
            "reason": "highest_weight",
        })
        # List alternatives
        for w in sorted(weights, key=lambda w: w.get("pct", 0), reverse=True)[1:]:
            selected_models.append({
                "model": w["model"],
                "weight_pct": w["pct"],
                "reason": "weight_fallback",
            })
    elif strategy == "lowest_latency":
        # Simulate: pick the first in chain (assumed fastest)
        if chain:
            selected_models.append({
                "model": chain[0],
                "weight_pct": 100,
                "reason": "lowest_latency_estimate",
            })
    elif strategy == "lowest_cost":
        # Simulate: pick the smallest model (heuristic)
        for w in weights:
            m = w["model"].lower()
            if "mini" in m or "small" in m or "flash" in m or "lite" in m:
                selected_models.append({
                    "model": w["model"],
                    "weight_pct": 100,
                    "reason": "lowest_cost_estimate",
                })
                break
        if not selected_models and weights:
            selected_models.append({
                "model": weights[-1]["model"],
                "weight_pct": 100,
                "reason": "lowest_cost_estimate",
            })
    else:
        # failover: primary first, then chain
        selected_models.append({
            "model": rule.get("primary", "—"),
            "weight_pct": 100,
            "reason": "primary",
        })

    # Simulate metrics
    import random
    primary_model = selected_models[0]["model"] if selected_models else "—"
    latency_ms = random.randint(200, 800) if primary_model != "—" else 0

    # Get circuit breaker state from FailoverEngine if available
    circuit_state = "closed"
    try:
        from aos_api.llm_routing import get_failover_engine
        engine = get_failover_engine()
        circuits = engine.list_circuits()
        for c in circuits:
            if c.model_id == primary_model:
                circuit_state = c.state
                break
    except Exception:
        pass

    return {
        "route_id": route_id,
        "strategy": strategy,
        "prompt": prompt[:200],
        "context_length": context_length,
        "selected": selected_models,
        "estimated_latency_ms": latency_ms,
        "estimated_input_tokens": max(1, context_length // 4),
        "estimated_output_tokens": 256,
        "circuit_state": circuit_state,
        "tested_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _validate_weights(weights: list[Any]) -> list[dict[str, Any]]:
    """Validate weight list. Total must be 100 (or all 0 for 'disabled')."""
    if not isinstance(weights, list):
        raise ValueError("weights must be a list")
    clean: list[dict[str, Any]] = []
    for w in weights:
        if isinstance(w, dict):
            model = str(w.get("model", ""))
            pct = int(w.get("pct", 0))
            if model:
                clean.append({"model": model, "pct": max(0, min(100, pct))})
    # Validate sum
    total = sum(w["pct"] for w in clean)
    if total > 0 and total != 100:
        log.warning("weights_total_not_100 got=%d", total)
        # Auto-normalize to 100
        if clean and total > 0:
            factor = 100.0 / total
            clean = [{"model": w["model"], "pct": round(w["pct"] * factor)} for w in clean]
            # Fix rounding to sum exactly 100
            diff = 100 - sum(w["pct"] for w in clean)
            if diff != 0 and clean:
                clean[0]["pct"] += diff
    return clean


def _validate_circuit_config(cfg: dict[str, Any]) -> dict[str, Any]:
    """Validate circuit breaker config fields."""
    clean: dict[str, Any] = {}
    if "error_rate_threshold_pct" in cfg:
        v = cfg["error_rate_threshold_pct"]
        clean["error_rate_threshold_pct"] = max(1, min(50, int(v)))
    if "latency_p99_ms" in cfg:
        v = cfg["latency_p99_ms"]
        clean["latency_p99_ms"] = max(100, min(30000, int(v)))
    if "cooldown_seconds" in cfg:
        v = cfg["cooldown_seconds"]
        clean["cooldown_seconds"] = max(5, min(600, int(v)))
    if "half_open_probes" in cfg:
        v = cfg["half_open_probes"]
        clean["half_open_probes"] = max(1, min(20, int(v)))
    if "failure_threshold" in cfg:
        v = cfg["failure_threshold"]
        clean["failure_threshold"] = max(1, min(100, int(v)))
    if "success_threshold" in cfg:
        v = cfg["success_threshold"]
        clean["success_threshold"] = max(1, min(20, int(v)))
    return clean
