from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "alembic" / "versions" / "aip4_008_research_job_lineage_binding.py"


def test_e3d_lineage_migration_is_linear_and_fail_closed() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "aip4_008"' in text
    assert 'down_revision: str | Sequence[str] | None = "aip4_007"' in text
    assert "IF EXISTS (SELECT 1 FROM aip_research_job_manifest)" in text
    assert "exact lineage cannot be guessed" in text


def test_e3d_job_binds_one_exact_lineage_event() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    assert "uq_aip_lineage_event_exact" in text
    assert "lineage_sequence >= 1" in text
    assert "fk_aip_research_job_exact_lineage" in text
    assert "lineage_id,lineage_sequence,lineage_event_id" in text
