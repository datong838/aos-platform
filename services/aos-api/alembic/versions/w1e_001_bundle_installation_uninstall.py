"""Make bundle installation uninstall a complete immutable transition.

Revision ID: w1e_001
Revises: w2_003
Create Date: 2026-08-14
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "w1e_001"
down_revision: str | Sequence[str] | None = "w2_003"
branch_labels = None
depends_on = None


_REVISION_GUARD_WITH_UNINSTALL = """
CREATE OR REPLACE FUNCTION guard_bundle_installation_revision_insert()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  parent_row bundle_installation_revision%ROWTYPE;
  lock_row bundle_composition_lock%ROWTYPE;
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
    RAISE EXCEPTION
      'installation revision does not match its canonical lock'
      USING ERRCODE = '23514';
  END IF;

  IF NEW.revision = 1 THEN
    IF NEW.state <> 'draft' OR NEW.parent_revision IS NOT NULL
       OR NEW.decision_id IS NOT NULL THEN
      RAISE EXCEPTION
        'installation revision 1 must be an undecided draft'
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
    RAISE EXCEPTION
      'installation revision parent is missing'
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
    RAISE EXCEPTION
      'installation revision changed its immutable plan'
      USING ERRCODE = '23514';
  END IF;
  IF NOT (
    (parent_row.state = 'draft' AND NEW.state = 'submitted')
    OR (
      parent_row.state = 'submitted'
      AND NEW.state IN ('approved', 'rejected')
    )
    OR (parent_row.state = 'approved' AND NEW.state = 'applied')
    OR (parent_row.state = 'applied' AND NEW.state = 'active')
    OR (
      parent_row.state = 'active'
      AND NEW.state IN ('rolled_back', 'uninstalled')
    )
  ) THEN
    RAISE EXCEPTION
      'invalid immutable installation revision transition'
      USING ERRCODE = '23514';
  END IF;
  IF NEW.state IN ('approved', 'rejected') THEN
    IF NEW.decision_id IS NULL THEN
      RAISE EXCEPTION
        'installation decision state requires decision id'
        USING ERRCODE = '23514';
    END IF;
  ELSIF NEW.state IN ('applied', 'active', 'rolled_back', 'uninstalled') THEN
    IF NEW.decision_id IS NULL
       OR NEW.decision_id IS DISTINCT FROM parent_row.decision_id THEN
      RAISE EXCEPTION
        'approved decision id must be inherited by descendants'
        USING ERRCODE = '23514';
    END IF;
  ELSE
    IF NEW.decision_id IS NOT NULL THEN
      RAISE EXCEPTION
        'pre-decision installation revision cannot have decision id'
        USING ERRCODE = '23514';
    END IF;
  END IF;
  RETURN NEW;
END;
$$
"""


_REVISION_GUARD_BEFORE_UNINSTALL = _REVISION_GUARD_WITH_UNINSTALL.replace(
    "AND NEW.state IN ('rolled_back', 'uninstalled')",
    "AND NEW.state = 'rolled_back'",
).replace(
    "('applied', 'active', 'rolled_back', 'uninstalled')",
    "('applied', 'active', 'rolled_back')",
)


_CONSISTENCY_WITH_UNINSTALL = """
CREATE OR REPLACE FUNCTION assert_bundle_installation_consistency(
  target_org TEXT,
  target_project TEXT,
  target_installation UUID
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
  installation_row bundle_installation%ROWTYPE;
  current_state TEXT;
  active_state TEXT;
  previous_state TEXT;
  maximum_revision BIGINT;
  maximum_sequence BIGINT;
  tail_revision BIGINT;
  tail_state TEXT;
BEGIN
  SELECT * INTO installation_row
    FROM bundle_installation
   WHERE org_id = target_org
     AND project_id = target_project
     AND installation_pk = target_installation;
  IF NOT FOUND THEN
    RAISE EXCEPTION
      'installation consistency parent is missing'
      USING ERRCODE = '23514';
  END IF;
  SELECT state INTO current_state
    FROM bundle_installation_revision
   WHERE org_id = target_org
     AND project_id = target_project
     AND installation_pk = target_installation
     AND revision = installation_row.current_revision;
  SELECT MAX(revision) INTO maximum_revision
    FROM bundle_installation_revision
   WHERE org_id = target_org
     AND project_id = target_project
     AND installation_pk = target_installation;
  SELECT sequence, to_revision, to_state
    INTO maximum_sequence, tail_revision, tail_state
    FROM bundle_installation_event
   WHERE org_id = target_org
     AND project_id = target_project
     AND installation_pk = target_installation
   ORDER BY sequence DESC
   LIMIT 1;
  IF current_state IS NULL
     OR maximum_revision IS DISTINCT FROM installation_row.current_revision
     OR maximum_sequence IS DISTINCT FROM installation_row.current_revision
     OR tail_revision IS DISTINCT FROM installation_row.current_revision
     OR tail_state IS DISTINCT FROM current_state
     OR installation_row.etag_version IS DISTINCT FROM
          installation_row.current_revision THEN
    RAISE EXCEPTION
      'installation pointer, event tail, revision, and etag disagree'
      USING ERRCODE = '23514';
  END IF;

  IF installation_row.active_revision IS NOT NULL THEN
    SELECT state INTO active_state
      FROM bundle_installation_revision
     WHERE org_id = target_org
       AND project_id = target_project
       AND installation_pk = target_installation
       AND revision = installation_row.active_revision;
    IF active_state <> 'active' THEN
      RAISE EXCEPTION
        'installation active pointer does not reference active revision'
        USING ERRCODE = '23514';
    END IF;
  END IF;
  IF installation_row.previous_active_revision IS NOT NULL THEN
    SELECT state INTO previous_state
      FROM bundle_installation_revision
     WHERE org_id = target_org
       AND project_id = target_project
       AND installation_pk = target_installation
       AND revision = installation_row.previous_active_revision;
    IF previous_state <> 'active' THEN
      RAISE EXCEPTION
        'installation previous pointer does not reference active revision'
        USING ERRCODE = '23514';
    END IF;
  END IF;

  IF current_state = 'active' THEN
    IF installation_row.active_revision IS DISTINCT FROM
         installation_row.current_revision
       OR (
         installation_row.previous_active_revision IS NOT NULL
         AND installation_row.previous_active_revision >=
             installation_row.current_revision
       ) THEN
      RAISE EXCEPTION
        'active installation pointers do not describe valid history'
        USING ERRCODE = '23514';
    END IF;
  ELSIF current_state IN ('rolled_back', 'uninstalled') THEN
    IF installation_row.active_revision IS DISTINCT FROM
         installation_row.previous_active_revision
       OR installation_row.active_revision IS NOT DISTINCT FROM
            installation_row.current_revision
       OR installation_row.previous_active_revision IS NOT DISTINCT FROM
            installation_row.current_revision THEN
      RAISE EXCEPTION
        'inactive installation pointers do not restore valid history'
        USING ERRCODE = '23514';
    END IF;
  ELSIF installation_row.active_revision IS NOT NULL
        OR installation_row.previous_active_revision IS NOT NULL THEN
    RAISE EXCEPTION
      'pre-active installation cannot expose active pointers'
      USING ERRCODE = '23514';
  END IF;
END;
$$
"""


_CONSISTENCY_BEFORE_UNINSTALL = _CONSISTENCY_WITH_UNINSTALL.replace(
    "current_state IN ('rolled_back', 'uninstalled')",
    "current_state = 'rolled_back'",
).replace(
    "'inactive installation pointers do not restore valid history'",
    "'rolled back installation pointers do not restore valid history'",
)


_STATE_CHECK_WITH_UNINSTALL = """
ALTER TABLE bundle_installation_revision
  DROP CONSTRAINT IF EXISTS bundle_installation_revision_state_check;
ALTER TABLE bundle_installation_revision
  ADD CONSTRAINT bundle_installation_revision_state_check CHECK (
    state = ANY (ARRAY[
      'draft', 'submitted', 'approved', 'rejected',
      'applied', 'active', 'rolled_back', 'uninstalled'
    ])
  )
"""


_EVENT_STATE_CHECKS_WITH_UNINSTALL = """
ALTER TABLE bundle_installation_event
  DROP CONSTRAINT IF EXISTS bundle_installation_event_from_state_check,
  DROP CONSTRAINT IF EXISTS bundle_installation_event_to_state_check;
ALTER TABLE bundle_installation_event
  ADD CONSTRAINT bundle_installation_event_from_state_check CHECK (
    from_state IS NULL OR from_state IN (
      'draft', 'submitted', 'approved', 'rejected',
      'applied', 'active', 'rolled_back', 'uninstalled'
    )
  ),
  ADD CONSTRAINT bundle_installation_event_to_state_check CHECK (
    to_state IN (
      'draft', 'submitted', 'approved', 'rejected',
      'applied', 'active', 'rolled_back', 'uninstalled'
    )
  )
"""


_EVENT_STATE_CHECKS_BEFORE_UNINSTALL = _EVENT_STATE_CHECKS_WITH_UNINSTALL.replace(
    ", 'uninstalled'", ""
)


_DOWNGRADE_GUARD = """
DO $$
BEGIN
  IF EXISTS (
    SELECT 1
      FROM bundle_installation_revision
     WHERE state = 'uninstalled'
  ) THEN
    RAISE EXCEPTION
      'cannot downgrade w1e_001 while uninstalled revisions exist'
      USING ERRCODE = '55000';
  END IF;
END;
$$
"""


def upgrade() -> None:
    op.execute(_STATE_CHECK_WITH_UNINSTALL)
    op.execute(_EVENT_STATE_CHECKS_WITH_UNINSTALL)
    op.execute(_REVISION_GUARD_WITH_UNINSTALL)
    op.execute(_CONSISTENCY_WITH_UNINSTALL)


def downgrade() -> None:
    op.execute(_DOWNGRADE_GUARD)
    op.execute(_REVISION_GUARD_BEFORE_UNINSTALL)
    op.execute(_CONSISTENCY_BEFORE_UNINSTALL)
    op.execute(_EVENT_STATE_CHECKS_BEFORE_UNINSTALL)
