from __future__ import annotations

import importlib.util
import json
import logging
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


def test_goldset_requires_exact_20_case_schema_and_never_returns_metadata_only(tmp_path):
    case = {
        "caseId": "case-01",
        "kind": "positive",
        "prompt": "公开合成输入",
        "expectedBehavior": "non_empty",
        "routeTaskType": "chat.answer",
        "routeInputModality": "text",
        "routeCapability": "chat",
        "routeExpected": "SELECT",
    }
    path = tmp_path / "goldset.json"
    path.write_text(
        json.dumps([{**case, "caseId": f"case-{index:02d}"} for index in range(1, 21)]),
        encoding="utf-8",
    )
    loaded = MODULE._load_goldset(path)
    assert len(loaded) == 20 and loaded[0]["prompt"] == "公开合成输入"
    path.write_text(json.dumps(loaded[:-1]), encoding="utf-8")
    try:
        MODULE._load_goldset(path)
    except ValueError as exc:
        assert "exactly 20" in str(exc)
    else:
        raise AssertionError("19-case GoldSet must fail closed")


def test_cli_suppresses_third_party_http_debug(monkeypatch, capsys):
    monkeypatch.setattr(MODULE.argparse.ArgumentParser, "parse_args", lambda self: type(
        "Args", (), {"apply_prerequisites": False, "apply_runtime": False,
                     "verify_runtime": False, "goldset_file": None}
    )())
    assert MODULE.main() == 0
    assert MODULE.logging.getLogger("httpcore").level == logging.WARNING
    assert MODULE.logging.getLogger("httpx").level == logging.WARNING
    assert "forbiddenSideEffects" in capsys.readouterr().out
