from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "alembic" / "versions" / "aip4_007_research_job_authority.py"


def test_e3d_migration_is_linear_and_additive() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "aip4_007"' in text
    assert 'down_revision: str | Sequence[str] | None = "aip4_006"' in text
    for table in (
        "aip_research_provider_revision",
        "aip_research_job_manifest",
        "aip_research_submission_receipt",
        "aip_research_event_receipt",
        "aip_research_callback_nonce",
        "aip_research_artifact_receipt",
        "aip_research_delivery_receipt",
    ):
        assert f"CREATE TABLE {table}" in text


def test_e3d_authority_tables_are_scoped_and_append_only() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    assert 'op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")' in text
    assert 'op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")' in text
    assert 'f"""CREATE TRIGGER trg_{table}_append_only' in text
    assert 'f"""CREATE TRIGGER trg_{table}_truncate_guard' in text
    assert 'op.execute(f"GRANT SELECT,INSERT ON {table} TO aos_runtime")' in text
    assert "GRANT UPDATE" not in text
    assert "GRANT DELETE" not in text
    assert "REFERENCES aip_task_run(org_id,project_id,run_id)" in text
    assert "REFERENCES aip_artifact(org_id,project_id,artifact_id)" in text
