"""a0v087 anchors replacement chains to the prior recovery receipt."""
from pathlib import Path

PATH=Path(__file__).resolve().parents[4]/"services/aos-api/alembic/versions/a0v_087_snapshot_prior_recovery_anchor.py"

def test_prior_recovery_anchor_and_exact_disable_bridge_are_enforced():
    source=PATH.read_text(encoding="utf-8")
    assert "prior_definition_revision,prior_definition_hash" in source
    assert "current_definition_revision,current_definition_hash" in source
    assert "transfer_predecessor.request->>'intent'='disable'" in source
    assert "transfer_predecessor.body->'members'=disable_predecessor.body->'members'" in source
    assert "(disable_predecessor.revision,disable_predecessor.content_hash)=" in source
    assert "snapshot replacement disable bridge differs" in source

def test_migration_never_disables_constraints_or_mutates_authority_rows():
    source=PATH.read_text(encoding="utf-8")
    assert "DISABLE TRIGGER" not in source
    assert "DROP CONSTRAINT" not in source
    assert "UPDATE public.pipeline_snapshot" not in source
    assert "DELETE FROM public.pipeline_snapshot" not in source
