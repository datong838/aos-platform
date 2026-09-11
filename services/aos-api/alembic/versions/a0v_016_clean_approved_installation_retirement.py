"""Allow only clean never-active approved installations to retire."""
from alembic import op

revision = "a0v_016"
down_revision = "a0v_015"
branch_labels = None
depends_on = None


_GUARD = r"""
CREATE OR REPLACE FUNCTION guard_bundle_installation_revision_insert()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  parent_row bundle_installation_revision%ROWTYPE;
  lock_row bundle_composition_lock%ROWTYPE;
  installation_uuid UUID;
BEGIN
  SELECT * INTO lock_row
    FROM bundle_composition_lock
   WHERE org_id = NEW.org_id
     AND project_id = NEW.project_id
     AND composition_pk = NEW.composition_pk
     AND revision = NEW.lock_revision;
  IF NOT FOUND
     OR NEW.lock_hash IS DISTINCT FROM lock_row.lock_hash
     OR NEW.permission_diff_hash IS DISTINCT FROM lock_row.permission_diff_hash
     OR NEW.migration_plan_hash IS DISTINCT FROM lock_row.migration_plan_hash
     OR NEW.contribution_diff_hash IS DISTINCT FROM lock_row.contribution_diff_hash THEN
    RAISE EXCEPTION 'installation revision does not match its canonical lock'
      USING ERRCODE = '23514';
  END IF;

  IF NEW.revision = 1 THEN
    IF NEW.state <> 'draft' OR NEW.parent_revision IS NOT NULL
       OR NEW.decision_id IS NOT NULL THEN
      RAISE EXCEPTION 'installation revision 1 must be an undecided draft'
        USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
  END IF;

  SELECT * INTO parent_row
    FROM bundle_installation_revision
   WHERE org_id = NEW.org_id
     AND project_id = NEW.project_id
     AND installation_pk = NEW.installation_pk
     AND revision = NEW.parent_revision;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'installation revision parent is missing'
      USING ERRCODE = '23514';
  END IF;
  IF NEW.composition_pk IS DISTINCT FROM parent_row.composition_pk
     OR NEW.lock_revision IS DISTINCT FROM parent_row.lock_revision
     OR NEW.lock_hash IS DISTINCT FROM parent_row.lock_hash
     OR NEW.permission_diff_hash IS DISTINCT FROM parent_row.permission_diff_hash
     OR NEW.migration_plan_hash IS DISTINCT FROM parent_row.migration_plan_hash
     OR NEW.contribution_diff_hash IS DISTINCT FROM parent_row.contribution_diff_hash
     OR NEW.overlay_revision IS DISTINCT FROM parent_row.overlay_revision
     OR NEW.requested_by IS DISTINCT FROM parent_row.requested_by THEN
    RAISE EXCEPTION 'installation revision changed its immutable plan'
      USING ERRCODE = '23514';
  END IF;

  IF parent_row.state = 'approved' AND NEW.state = 'uninstalled' THEN
    SELECT installation_id INTO installation_uuid
      FROM bundle_installation
     WHERE org_id = NEW.org_id
       AND project_id = NEW.project_id
       AND installation_pk = NEW.installation_pk;
    IF NOT FOUND
       OR EXISTS (
         SELECT 1 FROM extension_runtime_binding b
          WHERE b.org_id = NEW.org_id AND b.project_id = NEW.project_id
            AND b.installation_id = installation_uuid
       )
       OR EXISTS (
         SELECT 1 FROM extension_runtime_operation o
          WHERE o.org_id = NEW.org_id AND o.project_id = NEW.project_id
            AND o.installation_id = installation_uuid
            AND o.status NOT IN ('succeeded', 'failed', 'cancelled')
       )
       OR EXISTS (
         SELECT 1 FROM extension_runtime_resource_lease r
         JOIN extension_runtime_operation o
           ON o.org_id = r.org_id AND o.project_id = r.project_id
          AND o.operation_id = r.operation_id
          WHERE o.org_id = NEW.org_id AND o.project_id = NEW.project_id
            AND o.installation_id = installation_uuid
            AND (r.cleanup_state <> 'released' OR r.observed_release IS NOT TRUE)
       ) THEN
      RAISE EXCEPTION 'approved installation runtime is not clean for uninstall'
        USING ERRCODE = '23514';
    END IF;
  END IF;

  IF NOT (
    (parent_row.state = 'draft' AND NEW.state = 'submitted')
    OR (parent_row.state = 'submitted' AND NEW.state IN ('approved', 'rejected'))
    OR (parent_row.state = 'approved' AND NEW.state IN ('applied', 'uninstalled'))
    OR (parent_row.state = 'applied' AND NEW.state = 'active')
    OR (parent_row.state = 'active' AND NEW.state IN ('rolled_back', 'uninstalled'))
  ) THEN
    RAISE EXCEPTION 'invalid immutable installation revision transition'
      USING ERRCODE = '23514';
  END IF;
  IF NEW.state IN ('approved', 'rejected') THEN
    IF NEW.decision_id IS NULL THEN
      RAISE EXCEPTION 'installation decision state requires decision id'
        USING ERRCODE = '23514';
    END IF;
  ELSIF NEW.state IN ('applied', 'active', 'rolled_back', 'uninstalled') THEN
    IF NEW.decision_id IS NULL
       OR NEW.decision_id IS DISTINCT FROM parent_row.decision_id THEN
      RAISE EXCEPTION 'approved decision id must be inherited by descendants'
        USING ERRCODE = '23514';
    END IF;
  ELSE
    IF NEW.decision_id IS NOT NULL THEN
      RAISE EXCEPTION 'pre-decision installation revision cannot have decision id'
        USING ERRCODE = '23514';
    END IF;
  END IF;
  RETURN NEW;
END;
$$
"""


def upgrade():
    op.execute(_GUARD)


def downgrade():
    raise RuntimeError(
        "Forward-only clean retirement authority; preserve immutable installation history"
    )
