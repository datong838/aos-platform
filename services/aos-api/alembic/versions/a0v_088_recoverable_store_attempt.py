"""Allow recoverable authoritative Store work to participate in runtime drain."""
from alembic import op

revision = "a0v_088"
down_revision = "a0v_087"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    ALTER TABLE extension_runtime_execution_attempt
      DROP CONSTRAINT extension_runtime_execution_attempt_operation_kind_check;
    ALTER TABLE extension_runtime_execution_attempt
      ADD CONSTRAINT extension_runtime_execution_attempt_operation_kind_check
      CHECK(operation_kind IN ('signed_read','recoverable_store'));

    CREATE OR REPLACE FUNCTION extension_runtime_attempt_insert_guard() RETURNS trigger
      LANGUAGE plpgsql AS $$
    DECLARE
      binding_enabled boolean;
      binding_fenced boolean;
      binding_epoch bigint;
    BEGIN
      IF NEW.org_id IS DISTINCT FROM current_setting('aos.org_id',true)
         OR NEW.project_id IS DISTINCT FROM current_setting('aos.project_id',true) THEN
        RAISE EXCEPTION 'runtime attempt tenant scope mismatch';
      END IF;
      IF NEW.operation_kind NOT IN ('signed_read','recoverable_store') OR NEW.state <> 'running'
         OR NEW.revision <> 1 OR NEW.completed_at IS NOT NULL
         OR NEW.heartbeat_at IS NOT NULL THEN
        RAISE EXCEPTION 'invalid initial runtime attempt state';
      END IF;
      SELECT enabled,operation_fence,execution_epoch
        INTO binding_enabled,binding_fenced,binding_epoch
        FROM extension_runtime_binding
       WHERE org_id=NEW.org_id AND project_id=NEW.project_id
         AND installation_id=NEW.installation_id AND generation=NEW.generation
       FOR SHARE;
      IF NOT FOUND OR binding_enabled IS DISTINCT FROM true
         OR binding_fenced IS DISTINCT FROM false
         OR binding_epoch IS DISTINCT FROM NEW.execution_epoch THEN
        RAISE EXCEPTION 'runtime binding is not accepting attempts';
      END IF;
      RETURN NEW;
    END;
    $$;
    """)


def downgrade():
    raise RuntimeError("recoverable Store attempt authority must be retained")
