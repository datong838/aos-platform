from pathlib import Path


MIGRATION = (
    Path(__file__).parents[2]
    / "alembic"
    / "versions"
    / "bind1_003_skill_publication_provenance.py"
)


def test_bind1_003_is_linear_additive_and_exact() -> None:
    text = MIGRATION.read_text()
    assert 'down_revision: str | Sequence[str] | None = "bind1_002"' in text
    for column in (
        "parent_ref",
        "publication_tenant",
        "release_gate_ref",
        "publication_ref",
        "model_route_ref",
        "runtime_policy_ref",
    ):
        assert f"ADD COLUMN {column} JSONB" in text
    assert "lifecycle='published'" in text
    assert "assetType'='SkillTemplate" in text
    assert "assetType'='EvalGateDecision" in text
    assert "resourceType'='PublicationEvent" in text
    assert "assetType'='ModelRouteRevision" in text
    assert "assetType'='RuntimePolicyRevision" in text


def test_bind1_003_downgrade_fails_closed_with_published_skills() -> None:
    text = MIGRATION.read_text()
    assert "BIND1_003_DOWNGRADE_REQUIRES_NO_PUBLISHED_SKILLS" in text
    assert "WHERE lifecycle='published'" in text
