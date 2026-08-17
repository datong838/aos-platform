from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[4]
    / "scripts/aip/bootstrap_r1_runtime_authority.py"
)
SPEC = importlib.util.spec_from_file_location("bootstrap_r1_runtime_authority", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_dry_run_plan_is_fixed_tenant_secret_free_and_has_no_r2_side_effects():
    plan = MODULE.build_plan()
    assert plan["scope"] == {"orgId": "org-org", "projectId": "dev-project"}
    assert plan["approvalRef"] == "35-R1-C"
    assert plan["forbiddenSideEffects"] == [
        "CapabilityBinding",
        "SkillBinding",
        "AgentRun",
    ]
    rendered = str(plan).lower()
    assert "api-key" not in rendered
    assert "authorization" not in rendered


def test_runtime_rehash_is_deterministic():
    now = MODULE.datetime(2026, 8, 17, tzinfo=MODULE.UTC)
    payload = {
        "tenant": {"orgId": "org-org", "projectId": "dev-project"},
        "priceSnapshotId": "price-qyh-text-dev",
        "revision": 1,
        "currency": "CNY",
        "inputTokenPrice": 0,
        "outputTokenPrice": 0,
        "cachedTokenPrice": 0,
        "tokenUnit": 1000,
        "effectiveFrom": MODULE.WINDOW_START,
        "effectiveUntil": MODULE.WINDOW_END,
        "lifecycle": "active",
        "createdBy": MODULE.ACTOR,
        "createdAt": now,
    }
    first = MODULE.rehash_runtime(MODULE.ModelPriceSnapshotRevision, payload)
    second = MODULE.rehash_runtime(MODULE.ModelPriceSnapshotRevision, payload)
    assert first.content_hash == second.content_hash
