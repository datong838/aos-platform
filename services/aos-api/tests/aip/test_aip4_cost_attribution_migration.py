from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = (
    ROOT / "alembic" / "versions" / "aip4_006_cost_attribution_capability_receipt.py"
)


def test_e3c_migration_is_linear_and_additive() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "aip4_006"' in text
    assert 'down_revision: str | Sequence[str] | None = "aip4_005"' in text
    assert "CREATE TABLE aip_usage_attribution" in text
    assert "CREATE TABLE aip_capability_receipt" in text


def test_e3c_authority_tables_are_scoped_and_append_only() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    assert 'op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")' in text
    assert 'op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")' in text
    assert 'f"""CREATE TRIGGER trg_{table}_append_only' in text
    assert 'f"""CREATE TRIGGER trg_{table}_truncate_guard' in text
    assert 'op.execute(f"GRANT SELECT,INSERT ON {table} TO aos_runtime")' in text
    for table in ("aip_usage_attribution", "aip_capability_receipt"):
        assert table in text
    assert "provider_receipt_id" in text
    assert "subject_revision TEXT NOT NULL" in text
