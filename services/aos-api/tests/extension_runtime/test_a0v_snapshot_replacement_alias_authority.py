from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]


def test_a0v090_keeps_alias_authority_digest_exact():
    source = (ROOT / "services/aos-api/alembic/versions/a0v_090_snapshot_replacement_alias_authority.py").read_text()
    assert "down_revision='a0v_089'" in source
    assert "original.body->'policyRef'->>'resourceType'=NEW.policy_ref->>'resourceType'" in source
    assert "original.body->'policyRef'->>'resourceId'=NEW.policy_ref->>'resourceId'" in source
    assert "(m.old_draft->'mappingRef')- 'revision'=(m.new_draft->'mappingRef')- 'revision'" in source
    assert "(m.old_draft->'schemaRef')- 'revision'=(m.new_draft->'schemaRef')- 'revision'" in source
    assert "(m.old_draft->'maskingPolicyRef')- 'revision'=(m.new_draft->'maskingPolicyRef')- 'revision'" in source


def test_a0v090_deploy_requires_backup_and_unchanged_authority_fingerprints():
    source = (ROOT / "scripts/a0v_snapshot_replacement_alias_authority_deploy.py").read_text()
    inherited = (ROOT / "scripts/a0v_snapshot_prior_recovery_anchor_deploy.py").read_text()
    assert 'deploy.SOURCE = "a0v_089"' in source
    assert 'deploy.TARGET = "a0v_090"' in source
    assert "if after!=before" in inherited
    assert "pg_dump" in inherited
