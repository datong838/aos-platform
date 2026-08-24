from __future__ import annotations

from pathlib import Path


MIGRATION = (
    Path(__file__).parents[2]
    / "alembic"
    / "versions"
    / "w5_001_impact_action_binding.py"
)


def test_w5_001_is_nullable_append_only_and_downgrade_guarded() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "w5_001"' in source
    assert 'down_revision: str | Sequence[str] | None = "w4_003"' in source
    assert "ADD COLUMN external_action_binding JSONB" in source
    assert "ADD COLUMN action_binding_hash TEXT" in source
    assert "cannot downgrade w5_001 with Action binding facts" in source
    assert "UPDATE " not in source.upper()
