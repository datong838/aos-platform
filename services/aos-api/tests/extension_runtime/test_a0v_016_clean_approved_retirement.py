from pathlib import Path


MIGRATION = Path(__file__).parents[2] / "alembic/versions/a0v_016_clean_approved_installation_retirement.py"


def test_migration_is_chained_and_fail_closed() -> None:
    text = MIGRATION.read_text()
    assert 'revision = "a0v_016"' in text
    assert 'down_revision = "a0v_015"' in text
    assert "parent_row.state = 'approved' AND NEW.state = 'uninstalled'" in text
    assert "extension_runtime_binding" in text
    assert "status NOT IN ('succeeded', 'failed', 'cancelled')" in text
    assert "cleanup_state <> 'released' OR r.observed_release IS NOT TRUE" in text
    assert "approved installation runtime is not clean for uninstall" in text


def test_migration_preserves_active_uninstall_and_is_forward_only() -> None:
    text = MIGRATION.read_text()
    assert "parent_row.state = 'active' AND NEW.state IN ('rolled_back', 'uninstalled')" in text
    assert "Forward-only clean retirement authority" in text
