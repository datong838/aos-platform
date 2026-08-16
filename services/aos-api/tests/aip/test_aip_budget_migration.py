from pathlib import Path


def test_budget_migration_is_single_head_tenant_safe_and_append_only() -> None:
    path = Path(__file__).parents[2] / "alembic" / "versions" / "aip10_001_budget_authority.py"
    text = path.read_text(encoding="utf-8")
    assert 'down_revision: str | Sequence[str] | None = "aip9_002"' in text
    for table in ("aip_budget_head", "aip_budget_revision", "aip_budget_receipt"):
        assert table in text
    assert "ENABLE ROW LEVEL SECURITY" in text
    assert "FORCE ROW LEVEL SECURITY" in text
    assert "guard_aip4_append_only" in text
    assert "REVOKE UPDATE,DELETE,TRUNCATE" in text
