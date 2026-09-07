"""Persistent schedule binding, occurrence and atomic delivery authority."""

from alembic import op

revision = "ar2_002"
down_revision = "ar2_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE TABLE automation_schedule_binding (
      org_id text NOT NULL,
      project_id text NOT NULL,
      policy_id text NOT NULL CHECK(length(policy_id) BETWEEN 1 AND 200),
      policy_revision bigint NOT NULL CHECK(policy_revision > 0),
      policy_hash text NOT NULL CHECK(policy_hash ~ '^sha256:[0-9a-f]{64}$'),
      operation_id text NOT NULL,
      installation_id uuid NOT NULL,
      generation uuid NOT NULL,
      execution_epoch bigint NOT NULL CHECK(execution_epoch > 0),
      timezone text NOT NULL CHECK(timezone = 'Asia/Shanghai'),
      cadence text NOT NULL CHECK(cadence IN ('once','weekly','event')),
      weekly_day smallint CHECK(weekly_day BETWEEN 1 AND 7),
      local_time time,
      effective_from timestamptz NOT NULL,
      effective_until timestamptz,
      approved boolean NOT NULL DEFAULT false,
      enabled boolean NOT NULL DEFAULT false,
      watermark timestamptz,
      revision bigint NOT NULL DEFAULT 1 CHECK(revision > 0),
      PRIMARY KEY(org_id, project_id, policy_id, policy_revision),
      FOREIGN KEY(org_id, project_id, operation_id)
        REFERENCES extension_operation_dispatch_binding(org_id, project_id, operation_id),
      FOREIGN KEY(org_id, project_id, installation_id, generation)
        REFERENCES extension_runtime_binding(org_id, project_id, installation_id, generation),
      CHECK(effective_until IS NULL OR effective_until > effective_from),
      CHECK((cadence='weekly' AND weekly_day IS NOT NULL AND local_time IS NOT NULL)
         OR (cadence<>'weekly' AND weekly_day IS NULL AND local_time IS NULL))
    );
    CREATE UNIQUE INDEX automation_schedule_one_enabled_revision
      ON automation_schedule_binding(org_id, project_id, policy_id) WHERE enabled;

    CREATE TABLE automation_occurrence (
      org_id text NOT NULL,
      project_id text NOT NULL,
      occurrence_id uuid NOT NULL,
      policy_id text NOT NULL,
      policy_revision bigint NOT NULL,
      policy_hash text NOT NULL CHECK(policy_hash ~ '^sha256:[0-9a-f]{64}$'),
      operation_id text NOT NULL,
      installation_id uuid NOT NULL,
      generation uuid NOT NULL,
      execution_epoch bigint NOT NULL CHECK(execution_epoch > 0),
      scheduled_at timestamptz,
      local_slot text,
      trigger_source text NOT NULL CHECK(trigger_source IN ('schedule','event')),
      source_event_id text,
      status text NOT NULL CHECK(status IN ('pending','claimed','accepted','missed','not_applicable','needs_attention')),
      deadline timestamptz NOT NULL,
      claim_owner text,
      claim_until timestamptz,
      receipt_ref jsonb,
      created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(org_id, project_id, occurrence_id),
      FOREIGN KEY(org_id, project_id, policy_id, policy_revision)
        REFERENCES automation_schedule_binding(org_id, project_id, policy_id, policy_revision),
      CHECK((trigger_source='schedule' AND scheduled_at IS NOT NULL AND local_slot IS NOT NULL
               AND source_event_id IS NULL)
         OR (trigger_source='event' AND scheduled_at IS NULL AND local_slot IS NULL
               AND source_event_id IS NOT NULL)),
      CHECK((status='claimed' AND claim_owner IS NOT NULL AND claim_until IS NOT NULL)
         OR (status<>'claimed' AND claim_owner IS NULL AND claim_until IS NULL))
    );
    CREATE UNIQUE INDEX automation_occurrence_schedule_unique
      ON automation_occurrence(org_id, project_id, policy_id, scheduled_at)
      WHERE trigger_source='schedule';
    CREATE UNIQUE INDEX automation_occurrence_event_unique
      ON automation_occurrence(org_id, project_id, policy_id, source_event_id)
      WHERE trigger_source='event';
    CREATE INDEX automation_occurrence_claim_queue
      ON automation_occurrence(org_id, project_id, status, deadline, created_at);

    CREATE TABLE automation_occurrence_outbox (
      org_id text NOT NULL,
      project_id text NOT NULL,
      event_id uuid NOT NULL,
      occurrence_id uuid NOT NULL,
      payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'),
      payload_hash text NOT NULL CHECK(payload_hash ~ '^sha256:[0-9a-f]{64}$'),
      attempt integer NOT NULL DEFAULT 0 CHECK(attempt >= 0),
      next_attempt timestamptz NOT NULL DEFAULT clock_timestamp(),
      claim_until timestamptz,
      delivered_at timestamptz,
      PRIMARY KEY(org_id, project_id, event_id),
      UNIQUE(org_id, project_id, occurrence_id),
      FOREIGN KEY(org_id, project_id, occurrence_id)
        REFERENCES automation_occurrence(org_id, project_id, occurrence_id)
    );

    CREATE TABLE automation_occurrence_dispatch_attempt (
      org_id text NOT NULL,
      project_id text NOT NULL,
      attempt_id uuid NOT NULL,
      occurrence_id uuid NOT NULL,
      claim_owner text NOT NULL,
      target_idempotency_key text NOT NULL,
      status text NOT NULL CHECK(status IN ('claimed','receipt_recorded','unknown')),
      claimed_at timestamptz NOT NULL,
      claim_until timestamptz NOT NULL,
      receipt_ref jsonb,
      resolved_at timestamptz,
      PRIMARY KEY(org_id, project_id, attempt_id),
      UNIQUE(org_id, project_id, occurrence_id),
      UNIQUE(org_id, project_id, target_idempotency_key),
      FOREIGN KEY(org_id, project_id, occurrence_id)
        REFERENCES automation_occurrence(org_id, project_id, occurrence_id)
    );

    ALTER TABLE automation_schedule_binding ENABLE ROW LEVEL SECURITY;
    ALTER TABLE automation_schedule_binding FORCE ROW LEVEL SECURITY;
    ALTER TABLE automation_occurrence ENABLE ROW LEVEL SECURITY;
    ALTER TABLE automation_occurrence FORCE ROW LEVEL SECURITY;
    ALTER TABLE automation_occurrence_outbox ENABLE ROW LEVEL SECURITY;
    ALTER TABLE automation_occurrence_outbox FORCE ROW LEVEL SECURITY;
    ALTER TABLE automation_occurrence_dispatch_attempt ENABLE ROW LEVEL SECURITY;
    ALTER TABLE automation_occurrence_dispatch_attempt FORCE ROW LEVEL SECURITY;
    CREATE POLICY tenant_scope ON automation_schedule_binding
      USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
      WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true));
    CREATE POLICY tenant_scope ON automation_occurrence
      USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
      WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true));
    CREATE POLICY tenant_scope ON automation_occurrence_outbox
      USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
      WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true));
    CREATE POLICY tenant_scope ON automation_occurrence_dispatch_attempt
      USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
      WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true));
    REVOKE ALL ON automation_schedule_binding, automation_occurrence,
      automation_occurrence_outbox, automation_occurrence_dispatch_attempt FROM PUBLIC;
    GRANT SELECT, INSERT, UPDATE ON automation_schedule_binding, automation_occurrence,
      automation_occurrence_outbox, automation_occurrence_dispatch_attempt TO aos_runtime;
    GRANT SELECT ON extension_operation_dispatch_binding, extension_runtime_binding TO aos_runtime;
    """)


def downgrade():
    raise RuntimeError("automation occurrence authority must be retained")
