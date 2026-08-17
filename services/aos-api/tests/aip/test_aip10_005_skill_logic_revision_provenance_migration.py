from pathlib import Path


MIGRATION = (
    Path(__file__).parents[2]
    / "alembic"
    / "versions"
    / "aip10_005_skill_logic_revision_provenance.py"
)


def test_aip10_005_is_linear_additive_and_exact() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    assert 'down_revision: str | Sequence[str] | None = "aip10_004"' in text
    assert "ADD COLUMN logic_revision_ref JSONB" in text
    assert "aip_skill_logic_revision_provenance_chk" in text
    assert "lifecycle='published' AND logic_revision_ref IS NOT NULL" in text
    assert "assetType'='LogicRevision" in text
    assert "contentHash' ~ '^[0-9a-f]{64}$'" in text
    assert "NOT VALID" in text


def test_aip10_005_downgrade_preserves_bound_skill_history() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    assert "AIP10_005_DOWNGRADE_REQUIRES_NO_LOGIC_BOUND_SKILLS" in text
    assert "WHERE logic_revision_ref IS NOT NULL" in text
