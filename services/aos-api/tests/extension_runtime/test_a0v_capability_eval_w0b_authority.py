"""Contract tests for A0-V Capability EvalPack and W0B authority."""

import importlib.util
from pathlib import Path

from aos_api.aip_capability_w0b_authority import (
    REQUIRED_RELATIONS,
    close_definition_reasons,
    evaluate_w0b_relations,
)


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_capability_eval_w0b_authority.py"
SPEC = importlib.util.spec_from_file_location("a0v_capability_eval_w0b", SCRIPT)
assert SPEC and SPEC.loader
AUTHORITY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUTHORITY)


def healthy_rows():
    return [
        {"relation": name, "tenant_key_columns": 2, "rls": True, "force_rls": True, "policy_count": 1}
        for name in REQUIRED_RELATIONS
    ]


def test_w0b_requires_all_fifteen_tenant_scoped_forced_rls_relations():
    assert len(REQUIRED_RELATIONS) == 15
    assert evaluate_w0b_relations(healthy_rows()) == []
    missing = sorted(REQUIRED_RELATIONS)[0]
    rows = [row for row in healthy_rows() if row["relation"] != missing]
    assert evaluate_w0b_relations(rows) == [f"missing_relation:{missing}"]


def test_w0b_rejects_missing_tenant_key_rls_force_or_policy():
    for field, expected in (
        ("tenant_key_columns", "tenant_key_missing"),
        ("rls", "rls_missing"),
        ("force_rls", "force_rls_missing"),
        ("policy_count", "policy_missing"),
    ):
        rows = healthy_rows()
        rows[0][field] = 0 if field in {"tenant_key_columns", "policy_count"} else False
        assert any(item.startswith(expected) for item in evaluate_w0b_relations(rows))


def test_reason_closure_is_exact_and_keeps_provider_route_blockers():
    reasons = [
        "provider_unknown", "eval_pack_unavailable", "w0b_contracts_unavailable",
        "aip7_route_authority_unavailable",
    ]
    assert close_definition_reasons(reasons, eval_pack_ready=True, w0b_ready=True) == [
        "provider_unknown", "aip7_route_authority_unavailable"
    ]
    assert close_definition_reasons(reasons, eval_pack_ready=True, w0b_ready=False) == [
        "provider_unknown", "w0b_contracts_unavailable", "aip7_route_authority_unavailable"
    ]


def test_signed_source_paths_and_exact_counts_are_frozen():
    assert len(AUTHORITY.CAPABILITY_IDS) == 10
    assert str(AUTHORITY.SOURCE_RELATIVE).endswith("ecommerce-capability-catalog.json")
    assert str(AUTHORITY.EXPECTED_RELATIVE).endswith("bundle-evals.json")
