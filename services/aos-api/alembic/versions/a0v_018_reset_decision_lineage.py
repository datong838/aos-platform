"""Inherit the exact original approval on clean preparation recovery."""
from alembic import op
import sqlalchemy as sa

revision = "a0v_018"
down_revision = "a0v_017"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    source = conn.execute(sa.text("SELECT pg_get_functiondef('ensure_bundle_installation_revision_decision()'::regprocedure)")).scalar_one()
    old = "IF NEW.state IN ('approved', 'rejected')"
    new = """IF NEW.state IN ('approved', 'rejected')
             AND NOT (NEW.state = 'approved' AND EXISTS (
               SELECT 1 FROM bundle_installation_revision p
               WHERE p.org_id=NEW.org_id AND p.project_id=NEW.project_id
                 AND p.installation_pk=NEW.installation_pk AND p.revision=NEW.parent_revision
                 AND p.state='applied' AND p.decision_id=NEW.decision_id))"""
    if source.count(old) != 1:
        raise RuntimeError("decision lineage guard baseline differs")
    op.execute(source.replace(old, new))


def downgrade():
    raise RuntimeError("Forward-only inherited recovery decision")
