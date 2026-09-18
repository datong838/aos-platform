"""Persist bounded runtime-attempt terminal reasons without raw errors."""
from alembic import op

revision = "a0v_089"
down_revision = "a0v_088"
branch_labels = None
depends_on = None


_REASONS = """(
  'RECOVERABLE_EXECUTION_EXCEPTION',
  'RECOVERABLE_INGRESS_CANCELLED',
  'RECOVERABLE_INGRESS_DEADLINE_EXCEEDED',
  'RECOVERABLE_HEARTBEAT_FAILED',
  'RECOVERABLE_HEARTBEAT_STOP_TIMEOUT',
  'ATTEMPT_LEASE_EXPIRED',
  'READ_ACCESS_REVOKED',
  'READ_FAILED',
  'READ_RESULT_INVALID',
  'READ_OUTCOME_UNKNOWN',
  'READ_DEADLINE_EXPIRED',
  'READ_RUNTIME_CHANGED'
)"""


def upgrade():
    op.execute(f"""
    ALTER TABLE extension_runtime_execution_attempt
      ADD COLUMN terminal_reason_code text,
      ADD COLUMN terminal_error_type text,
      ADD CONSTRAINT extension_runtime_attempt_terminal_reason_check
        CHECK(terminal_reason_code IS NULL OR terminal_reason_code IN {_REASONS}),
      ADD CONSTRAINT extension_runtime_attempt_terminal_error_type_check
        CHECK(terminal_error_type IS NULL OR terminal_error_type ~ '^[A-Za-z_][A-Za-z0-9_.]{{0,159}}$');
    ALTER TABLE extension_runtime_execution_attempt_event
      ADD COLUMN terminal_reason_code text,
      ADD COLUMN terminal_error_type text,
      ADD CONSTRAINT extension_runtime_attempt_event_terminal_reason_check
        CHECK(terminal_reason_code IS NULL OR terminal_reason_code IN {_REASONS}),
      ADD CONSTRAINT extension_runtime_attempt_event_terminal_error_type_check
        CHECK(terminal_error_type IS NULL OR terminal_error_type ~ '^[A-Za-z_][A-Za-z0-9_.]{{0,159}}$');

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
         OR NEW.heartbeat_at IS NOT NULL OR NEW.terminal_reason_code IS NOT NULL
         OR NEW.terminal_error_type IS NOT NULL THEN
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

    CREATE OR REPLACE FUNCTION extension_runtime_attempt_update_guard() RETURNS trigger
      LANGUAGE plpgsql AS $$
    BEGIN
      IF ROW(NEW.org_id,NEW.project_id,NEW.attempt_id,NEW.installation_id,NEW.generation,
             NEW.execution_epoch,NEW.operation_kind,NEW.operation_key,NEW.idempotency_key,
             NEW.request_hash,NEW.owner_token_hash,NEW.accepted_at)
         IS DISTINCT FROM
         ROW(OLD.org_id,OLD.project_id,OLD.attempt_id,OLD.installation_id,OLD.generation,
             OLD.execution_epoch,OLD.operation_kind,OLD.operation_key,OLD.idempotency_key,
             OLD.request_hash,OLD.owner_token_hash,OLD.accepted_at) THEN
        RAISE EXCEPTION 'runtime attempt identity is immutable';
      END IF;
      IF OLD.state <> 'running' OR NEW.revision <> OLD.revision + 1 THEN
        RAISE EXCEPTION 'invalid runtime attempt transition';
      END IF;
      IF NEW.state = 'running' THEN
        IF NEW.completed_at IS NOT NULL OR NEW.heartbeat_at IS NULL
           OR NEW.heartbeat_at IS NOT DISTINCT FROM OLD.heartbeat_at
           OR NEW.lease_until <= OLD.lease_until
           OR NEW.terminal_reason_code IS NOT NULL OR NEW.terminal_error_type IS NOT NULL THEN
          RAISE EXCEPTION 'invalid runtime attempt heartbeat';
        END IF;
      ELSIF NEW.state = 'succeeded' THEN
        IF NEW.completed_at IS NULL OR NEW.lease_until IS DISTINCT FROM OLD.lease_until
           OR NEW.heartbeat_at IS DISTINCT FROM OLD.heartbeat_at
           OR NEW.terminal_reason_code IS NOT NULL OR NEW.terminal_error_type IS NOT NULL THEN
          RAISE EXCEPTION 'invalid runtime attempt settlement';
        END IF;
      ELSIF NEW.state = 'failed' THEN
        IF NEW.completed_at IS NULL OR NEW.lease_until IS DISTINCT FROM OLD.lease_until
           OR NEW.heartbeat_at IS DISTINCT FROM OLD.heartbeat_at
           OR NEW.terminal_reason_code IS NULL THEN
          RAISE EXCEPTION 'invalid runtime attempt failure';
        END IF;
      ELSIF NEW.state = 'abandoned' THEN
        IF NEW.completed_at IS NULL OR NEW.lease_until IS DISTINCT FROM OLD.lease_until
           OR NEW.heartbeat_at IS DISTINCT FROM OLD.heartbeat_at
           OR NEW.terminal_reason_code <> 'ATTEMPT_LEASE_EXPIRED'
           OR NEW.terminal_error_type IS NOT NULL THEN
          RAISE EXCEPTION 'invalid runtime attempt abandonment';
        END IF;
      ELSE
        RAISE EXCEPTION 'unknown runtime attempt state';
      END IF;
      RETURN NEW;
    END;
    $$;

    CREATE OR REPLACE FUNCTION extension_runtime_attempt_event_guard() RETURNS trigger
      LANGUAGE plpgsql AS $$
    DECLARE
      head_state text;
      head_revision bigint;
      head_reason text;
      head_error_type text;
      expected_type text;
    BEGIN
      SELECT state,revision,terminal_reason_code,terminal_error_type
        INTO head_state,head_revision,head_reason,head_error_type
        FROM extension_runtime_execution_attempt
       WHERE org_id=NEW.org_id AND project_id=NEW.project_id AND attempt_id=NEW.attempt_id;
      IF NOT FOUND OR NEW.sequence <> NEW.revision OR NEW.revision <> head_revision
         OR NEW.state <> head_state
         OR NEW.terminal_reason_code IS DISTINCT FROM head_reason
         OR NEW.terminal_error_type IS DISTINCT FROM head_error_type THEN
        RAISE EXCEPTION 'runtime attempt event does not match authority head';
      END IF;
      expected_type := CASE
        WHEN NEW.state='running' AND NEW.revision=1 THEN 'attempt_accepted'
        WHEN NEW.state='running' THEN 'attempt_heartbeat'
        ELSE 'attempt_' || NEW.state
      END;
      IF NEW.type <> expected_type THEN
        RAISE EXCEPTION 'runtime attempt event type mismatch';
      END IF;
      RETURN NEW;
    END;
    $$;
    """)


def downgrade():
    raise RuntimeError("runtime attempt terminal reasons must be retained")
