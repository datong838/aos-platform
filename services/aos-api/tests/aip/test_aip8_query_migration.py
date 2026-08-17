from pathlib import Path


MIGRATION = Path(__file__).parents[2] / "alembic" / "versions" / "aip8_001_analyst_query_authority.py"


def test_query_authority_migration_is_append_only_and_tenant_scoped() -> None:
    text = MIGRATION.read_text()
    for table in ("aip_analyst_query_job", "aip_analyst_query_event", "aip_analyst_query_result_revision", "aip_analyst_query_receipt"):
        assert f"CREATE TABLE {table}" in text
        assert f"ALTER TABLE {{table}} ENABLE ROW LEVEL SECURITY" in text
        assert f"ALTER TABLE {{table}} FORCE ROW LEVEL SECURITY" in text
    assert "guard_aip8_append_only" in text
    assert "GRANT SELECT,INSERT" in text
    assert "bind1_003" in text
