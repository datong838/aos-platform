"""Static migration contract for tenant-bound AIP feature activation authority."""

from pathlib import Path


MIGRATION = Path(__file__).resolve().parents[2] / "alembic/versions/wcat_001_aip_feature_activation.py"


def test_feature_activation_migration_is_tenant_scoped_and_read_only() -> None:
    text = MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "wcat_001"' in text
    assert 'down_revision: str | Sequence[str] | None = "biw8_001"' in text
    assert "CREATE TABLE aip_feature_activation" in text
    assert "PRIMARY KEY(org_id,project_id,feature_id,revision)" in text
    assert "uq_aip_feature_activation_active" in text
    assert "ENABLE ROW LEVEL SECURITY" in text
    assert "FORCE ROW LEVEL SECURITY" in text
    assert "current_setting('aos.org_id',true)" in text
    assert "current_setting('aos.project_id',true)" in text
    assert "GRANT SELECT ON aip_feature_activation TO aos_runtime" in text
    assert "REVOKE INSERT,UPDATE,DELETE,TRUNCATE" in text
    assert "cannot downgrade wcat_001 with AIP feature authority" in text
