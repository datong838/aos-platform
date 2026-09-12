"""Clean applied preparation may append recovery without rewriting history."""
from alembic import op
import sqlalchemy as sa

revision = "a0v_017"
down_revision = "a0v_016"
branch_labels = None
depends_on = None


def upgrade():
    # Preserve every existing lock and retirement guard. Fail closed if a prior
    # migration does not contain the exact clauses this revision extends.
    conn = op.get_bind()
    source = conn.execute(sa.text("SELECT pg_get_functiondef('guard_bundle_installation_revision_insert()'::regprocedure)")).scalar_one()
    replacements = {
        "IF parent_row.state = 'approved' AND NEW.state = 'uninstalled' THEN":
        "IF (parent_row.state = 'approved' AND NEW.state = 'uninstalled') OR (parent_row.state = 'applied' AND NEW.state = 'approved') THEN",
        "(parent_row.state = 'applied' AND NEW.state = 'active')":
        "(parent_row.state = 'applied' AND NEW.state IN ('active', 'approved'))",
        "IF NEW.state IN ('approved', 'rejected') THEN": """IF parent_row.state = 'applied' AND NEW.state = 'approved' THEN
    IF NEW.decision_id IS NULL OR NEW.decision_id IS DISTINCT FROM parent_row.decision_id
       OR NOT EXISTS (SELECT 1 FROM extension_runtime_resource_lease r
         JOIN extension_runtime_operation o ON o.org_id=r.org_id AND o.project_id=r.project_id
         AND o.operation_id=r.operation_id WHERE o.org_id=NEW.org_id AND o.project_id=NEW.project_id
         AND o.installation_id=installation_uuid)
       OR NOT EXISTS (SELECT 1 FROM extension_runtime_operation o
         WHERE o.org_id=NEW.org_id AND o.project_id=NEW.project_id
         AND o.installation_id=installation_uuid AND o.kind='runtime-apply' AND o.status='succeeded')
       OR EXISTS (SELECT 1 FROM extension_runtime_operation o
         WHERE o.org_id=NEW.org_id AND o.project_id=NEW.project_id
         AND o.installation_id=installation_uuid AND o.kind='runtime-verify'
         AND (o.status='succeeded' OR o.phase='committing')) THEN
      RAISE EXCEPTION 'preparation recovery history or decision is unsafe' USING ERRCODE='23514';
    END IF;
  ELSIF NEW.state IN ('approved', 'rejected') THEN""",
    }
    for old, new in replacements.items():
        if source.count(old) != 1:
            raise RuntimeError("preparation reset guard baseline differs")
        source = source.replace(old, new)
    op.execute(source)


def downgrade():
    raise RuntimeError("Forward-only recovery preserves immutable history")
