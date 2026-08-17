from pathlib import Path


def test_network_policy_eval_expiry_migration_is_linear_tenant_safe_and_append_only() -> None:
    path = Path(__file__).parents[2] / "alembic" / "versions" / "aip10_004_network_policy_eval_gate_expiry.py"
    text = path.read_text(encoding="utf-8")
    assert 'down_revision: str | Sequence[str] | None = "aip10_003"' in text
    for table in (
        "aip_network_policy_head",
        "aip_network_policy_revision",
        "aip_network_policy_receipt",
    ):
        assert table in text
    assert "ENABLE ROW LEVEL SECURITY" in text
    assert "FORCE ROW LEVEL SECURITY" in text
    assert "guard_aip4_append_only" in text
    assert "REVOKE UPDATE,DELETE,TRUNCATE" in text
    assert "decided_at + INTERVAL '30 days'" in text
    assert "expires_at>decided_at" in text
