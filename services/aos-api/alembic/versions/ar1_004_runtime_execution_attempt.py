"""Persistent generation execution attempts; additive and empty by default."""
from alembic import op

revision = "ar1_004"
down_revision = "ar1_003"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE TABLE extension_runtime_execution_attempt (
      org_id text NOT NULL, project_id text NOT NULL, attempt_id uuid NOT NULL,
      installation_id uuid NOT NULL, generation uuid NOT NULL, execution_epoch bigint NOT NULL CHECK(execution_epoch>0),
      operation_kind text NOT NULL CHECK(operation_kind='signed_read'),
      operation_key text NOT NULL CHECK(length(operation_key) BETWEEN 1 AND 160),
      idempotency_key text NOT NULL CHECK(length(idempotency_key) BETWEEN 1 AND 240),
      request_hash text NOT NULL CHECK(request_hash ~ '^sha256:[0-9a-f]{64}$'),
      owner_token_hash text NOT NULL CHECK(owner_token_hash ~ '^sha256:[0-9a-f]{64}$'),
      state text NOT NULL CHECK(state IN ('running','succeeded','failed','abandoned')),
      lease_until timestamptz NOT NULL, revision bigint NOT NULL DEFAULT 1 CHECK(revision>0),
      accepted_at timestamptz NOT NULL DEFAULT clock_timestamp(), heartbeat_at timestamptz, completed_at timestamptz,
      PRIMARY KEY(org_id,project_id,attempt_id),
      UNIQUE(org_id,project_id,installation_id,generation,execution_epoch,operation_kind,idempotency_key),
      FOREIGN KEY(org_id,project_id,installation_id,generation)
        REFERENCES extension_runtime_binding(org_id,project_id,installation_id,generation),
      CHECK((state='running' AND completed_at IS NULL) OR (state<>'running' AND completed_at IS NOT NULL))
    );
    CREATE TABLE extension_runtime_execution_attempt_event (
      org_id text NOT NULL, project_id text NOT NULL, attempt_id uuid NOT NULL,
      sequence bigint NOT NULL CHECK(sequence>0), event_id uuid NOT NULL UNIQUE,
      type text NOT NULL CHECK(type IN ('attempt_accepted','attempt_heartbeat','attempt_succeeded','attempt_failed','attempt_abandoned')),
      state text NOT NULL CHECK(state IN ('running','succeeded','failed','abandoned')),
      revision bigint NOT NULL CHECK(revision>0), occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(org_id,project_id,attempt_id,sequence),
      FOREIGN KEY(org_id,project_id,attempt_id)
        REFERENCES extension_runtime_execution_attempt(org_id,project_id,attempt_id)
    );
    ALTER TABLE extension_runtime_execution_attempt ENABLE ROW LEVEL SECURITY;
    ALTER TABLE extension_runtime_execution_attempt FORCE ROW LEVEL SECURITY;
    ALTER TABLE extension_runtime_execution_attempt_event ENABLE ROW LEVEL SECURITY;
    ALTER TABLE extension_runtime_execution_attempt_event FORCE ROW LEVEL SECURITY;
    CREATE POLICY tenant_scope ON extension_runtime_execution_attempt
      USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
      WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true));
    CREATE POLICY tenant_scope ON extension_runtime_execution_attempt_event
      USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
      WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true));
    CREATE FUNCTION extension_runtime_attempt_insert_guard() RETURNS trigger
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
      IF NEW.operation_kind <> 'signed_read' OR NEW.state <> 'running'
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
    CREATE FUNCTION extension_runtime_attempt_update_guard() RETURNS trigger
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
           OR NEW.lease_until <= OLD.lease_until THEN
          RAISE EXCEPTION 'invalid runtime attempt heartbeat';
        END IF;
      ELSIF NEW.state IN ('succeeded','failed','abandoned') THEN
        IF NEW.completed_at IS NULL
           OR NEW.lease_until IS DISTINCT FROM OLD.lease_until
           OR NEW.heartbeat_at IS DISTINCT FROM OLD.heartbeat_at THEN
          RAISE EXCEPTION 'invalid runtime attempt settlement';
        END IF;
      ELSE
        RAISE EXCEPTION 'unknown runtime attempt state';
      END IF;
      RETURN NEW;
    END;
    $$;
    CREATE FUNCTION extension_runtime_attempt_event_guard() RETURNS trigger
      LANGUAGE plpgsql AS $$
    DECLARE
      head_state text;
      head_revision bigint;
      expected_type text;
    BEGIN
      SELECT state,revision INTO head_state,head_revision
        FROM extension_runtime_execution_attempt
       WHERE org_id=NEW.org_id AND project_id=NEW.project_id AND attempt_id=NEW.attempt_id;
      IF NOT FOUND OR NEW.sequence <> NEW.revision OR NEW.revision <> head_revision
         OR NEW.state <> head_state THEN
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
    CREATE TRIGGER attempt_insert_guard BEFORE INSERT ON extension_runtime_execution_attempt
      FOR EACH ROW EXECUTE FUNCTION extension_runtime_attempt_insert_guard();
    CREATE TRIGGER attempt_update_guard BEFORE UPDATE ON extension_runtime_execution_attempt
      FOR EACH ROW EXECUTE FUNCTION extension_runtime_attempt_update_guard();
    CREATE TRIGGER attempt_event_guard BEFORE INSERT ON extension_runtime_execution_attempt_event
      FOR EACH ROW EXECUTE FUNCTION extension_runtime_attempt_event_guard();
    CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE ON extension_runtime_execution_attempt_event
      FOR EACH ROW EXECUTE FUNCTION extension_reject_history_mutation();
    REVOKE ALL ON extension_runtime_execution_attempt,extension_runtime_execution_attempt_event FROM PUBLIC;
    GRANT SELECT,INSERT,UPDATE ON extension_runtime_execution_attempt TO aos_runtime;
    GRANT SELECT,INSERT ON extension_runtime_execution_attempt_event TO aos_runtime;
    """)


def downgrade():
    raise RuntimeError("runtime execution attempt authority must be retained")
