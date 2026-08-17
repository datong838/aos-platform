from pathlib import Path


MIGRATION = (
    Path(__file__).parents[2]
    / "alembic"
    / "versions"
    / "aip8_002_assist_authority.py"
)


def test_assist_authority_migration_is_append_only_and_tenant_scoped() -> None:
    text = MIGRATION.read_text()
    for table in (
        "aip_assist_thread",
        "aip_assist_turn",
        "aip_assist_event",
        "aip_assist_receipt",
    ):
        assert f"CREATE TABLE {table}" in text
        assert f"ALTER TABLE {{table}} ENABLE ROW LEVEL SECURITY" in text
        assert f"ALTER TABLE {{table}} FORCE ROW LEVEL SECURITY" in text
    assert "guard_aip8_assist_append_only" in text
    assert "GRANT SELECT,INSERT" in text
    assert 'down_revision: str | Sequence[str] | None = "aip8_001"' in text
