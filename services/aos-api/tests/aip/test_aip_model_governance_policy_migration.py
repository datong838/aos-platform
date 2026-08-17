from pathlib import Path


def test_model_governance_policy_migration_is_linear_tenant_safe_and_append_only() -> None:
    path = Path(__file__).parents[2] / "alembic" / "versions" / "aip10_003_model_governance_policy_authority.py"
    text = path.read_text(encoding="utf-8")
    assert 'down_revision: str | Sequence[str] | None = "aip10_002"' in text
    for table in ("aip_model_governance_policy_head", "aip_model_governance_policy_revision", "aip_model_governance_policy_receipt"):
        assert table in text
    assert "ENABLE ROW LEVEL SECURITY" in text
    assert "FORCE ROW LEVEL SECURITY" in text
    assert "guard_aip4_append_only" in text
    assert "REVOKE UPDATE,DELETE,TRUNCATE" in text
