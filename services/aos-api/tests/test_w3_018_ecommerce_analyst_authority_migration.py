from pathlib import Path

MIGRATION = Path(__file__).parents[1] / "alembic/versions/w3_018_ecommerce_analyst_authority.py"


def test_w3_018_is_linear_tenant_safe_append_only_and_guarded() -> None:
    text = MIGRATION.read_text()
    assert 'revision: str = "w3_018"' in text
    assert 'down_revision: str | Sequence[str] | None = "w3_017"' in text
    for kind in ("insight", "decision", "growth_plan", "task_graph", "effect_review"):
        assert f'ecommerce_analyst_{kind}_head' in text
        assert f'ecommerce_analyst_{kind}_revision' in text
    assert "ENABLE ROW LEVEL SECURITY" in text and "FORCE ROW LEVEL SECURITY" in text
    assert "guard_aip4_append_only" in text
    assert "cannot downgrade w3_018 with canonical analyst data" in text
