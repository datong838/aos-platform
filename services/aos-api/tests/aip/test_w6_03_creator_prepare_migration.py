from pathlib import Path


def test_w6_003_is_unique_tenant_rls_append_only_head() -> None:
    root = Path(__file__).resolve().parents[2]
    migration = root / "alembic/versions/w6_003_creator_prepare.py"
    text = migration.read_text(encoding="utf-8")
    assert 'revision: str = "w6_003"' in text
    assert 'down_revision: str | Sequence[str] | None = "w6_002"' in text
    assert text.count("FORCE ROW LEVEL SECURITY") == 1  # loop source, applied to every table
    assert "GRANT SELECT, INSERT" in text
    assert "UPDATE" not in text and "DELETE FROM" not in text
    revisions = list((root / "alembic/versions").glob("*.py"))
    assert sum('revision: str = "w6_003"' in item.read_text(encoding="utf-8") for item in revisions) == 1
