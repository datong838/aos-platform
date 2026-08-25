"""W5-06 canonical Action webhook inbox, replay and ordering authority.

Revision ID: w5_005
Revises: w5_004
"""
from __future__ import annotations

from alembic import op

revision = "w5_005"
down_revision = "w5_004"
branch_labels = None
depends_on = None


TENANT_TABLES = (
    "aip_action_webhook_endpoint_revision",
    "aip_action_webhook_inbox_receipt",
    "aip_action_webhook_replay_key",
    "aip_action_webhook_observation",
    "aip_action_webhook_reducer_view",
    "aip_action_webhook_case",
)


def upgrade() -> None:
    op.execute(
        """CREATE TABLE aip_action_webhook_endpoint_directory (
          endpoint_key TEXT PRIMARY KEY, org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          endpoint_id TEXT NOT NULL, active_revision BIGINT NOT NULL,
          status TEXT NOT NULL DEFAULT 'active', created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          UNIQUE (org_id,project_id,endpoint_id), CHECK (active_revision >= 1),
          CHECK (status IN ('active','disabled','retired'))
        )"""
    )
    op.execute(
        """CREATE TABLE aip_action_webhook_endpoint_revision (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, endpoint_id TEXT NOT NULL,
          revision BIGINT NOT NULL, content_hash TEXT NOT NULL, lifecycle TEXT NOT NULL,
          adapter_revision_ref JSONB NOT NULL, account_binding_ref JSONB NOT NULL,
          signature_policy JSONB NOT NULL, secret_ref TEXT NOT NULL,
          event_schema JSONB NOT NULL, max_body_bytes INTEGER NOT NULL,
          valid_from TIMESTAMPTZ NOT NULL DEFAULT NOW(), expires_at TIMESTAMPTZ,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id,project_id,endpoint_id,revision),
          UNIQUE (org_id,project_id,endpoint_id,content_hash),
          CHECK (revision >= 1), CHECK (content_hash ~ '^[0-9a-f]{64}$'),
          CHECK (lifecycle IN ('published','disabled','retired')),
          CHECK (max_body_bytes BETWEEN 1 AND 1048576),
          CHECK (jsonb_typeof(adapter_revision_ref)='object'),
          CHECK (jsonb_typeof(account_binding_ref)='object'),
          CHECK (jsonb_typeof(signature_policy)='object'),
          CHECK (jsonb_typeof(event_schema)='object')
        )"""
    )
    op.execute(
        """CREATE TABLE aip_action_webhook_inbox_receipt (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, receipt_id TEXT NOT NULL,
          endpoint_id TEXT NOT NULL, endpoint_revision BIGINT NOT NULL,
          endpoint_hash TEXT NOT NULL, body_hash TEXT NOT NULL, headers_hash TEXT NOT NULL,
          verification_status TEXT NOT NULL, verification_reason TEXT NOT NULL,
          replay_status TEXT NOT NULL, processing_status TEXT NOT NULL,
          provider_event_id TEXT, event_key TEXT, quarantine_ref JSONB,
          received_at TIMESTAMPTZ NOT NULL, source_hash TEXT NOT NULL,
          PRIMARY KEY (org_id,project_id,receipt_id),
          CHECK (body_hash ~ '^[0-9a-f]{64}$'), CHECK (headers_hash ~ '^[0-9a-f]{64}$'),
          CHECK (source_hash ~ '^[0-9a-f]{64}$'),
          CHECK (verification_status IN ('verified','rejected')),
          CHECK (replay_status IN ('new','duplicate','drift','not_checked')),
          CHECK (processing_status IN ('accepted','quarantined','rejected')),
          CHECK (quarantine_ref IS NULL OR jsonb_typeof(quarantine_ref)='object')
        )"""
    )
    op.execute(
        """CREATE TABLE aip_action_webhook_replay_key (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, endpoint_id TEXT NOT NULL,
          event_key TEXT NOT NULL, body_hash TEXT NOT NULL, receipt_id TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id,project_id,endpoint_id,event_key),
          CHECK (body_hash ~ '^[0-9a-f]{64}$')
        )"""
    )
    op.execute(
        """CREATE TABLE aip_action_webhook_observation (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, observation_id TEXT NOT NULL,
          receipt_id TEXT NOT NULL, attempt_id TEXT NOT NULL, provider_event_id TEXT NOT NULL,
          event_type TEXT NOT NULL, provider_outcome TEXT NOT NULL,
          provider_sequence BIGINT, provider_event_at TIMESTAMPTZ,
          payload_hash TEXT NOT NULL, adapter_schema_ref JSONB NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id,project_id,observation_id),
          UNIQUE (org_id,project_id,attempt_id,provider_event_id),
          CHECK (provider_sequence IS NULL OR provider_sequence >= 1),
          CHECK (provider_outcome IN ('accepted','applied','failed','partial','unknown')),
          CHECK (payload_hash ~ '^[0-9a-f]{64}$'),
          CHECK (jsonb_typeof(adapter_schema_ref)='object')
        )"""
    )
    op.execute(
        """CREATE TABLE aip_action_webhook_reducer_view (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, attempt_id TEXT NOT NULL,
          status TEXT NOT NULL, provider_outcome TEXT,
          latest_contiguous_sequence BIGINT NOT NULL DEFAULT 0,
          highest_observed_sequence BIGINT NOT NULL DEFAULT 0,
          missing_sequences JSONB NOT NULL DEFAULT '[]'::jsonb,
          observation_count BIGINT NOT NULL DEFAULT 0, version BIGINT NOT NULL DEFAULT 1,
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id,project_id,attempt_id),
          CHECK (status IN ('pending','awaiting_gap','applied','failed','partial','disputed')),
          CHECK (provider_outcome IS NULL OR provider_outcome IN ('accepted','applied','failed','partial','unknown')),
          CHECK (latest_contiguous_sequence >= 0 AND highest_observed_sequence >= 0),
          CHECK (jsonb_typeof(missing_sequences)='array'), CHECK (version >= 1)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_action_webhook_case (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, case_id TEXT NOT NULL,
          receipt_id TEXT NOT NULL, case_type TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open',
          reason_code TEXT NOT NULL, safe_facts JSONB NOT NULL DEFAULT '{}'::jsonb,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id,project_id,case_id),
          CHECK (case_type IN ('replay_drift','unmatched','multi_match','schema_drift','binding_drift','terminal_conflict')),
          CHECK (status IN ('open','resolved')), CHECK (jsonb_typeof(safe_facts)='object')
        )"""
    )
    op.execute(
        """ALTER TABLE aip_action_webhook_endpoint_revision
          ADD CONSTRAINT fk_action_webhook_endpoint_workspace
            FOREIGN KEY (org_id,project_id) REFERENCES twa_workspace(org_id,project_id);
        ALTER TABLE aip_action_webhook_endpoint_directory
          ADD CONSTRAINT fk_action_webhook_directory_revision
            FOREIGN KEY (org_id,project_id,endpoint_id,active_revision)
            REFERENCES aip_action_webhook_endpoint_revision(org_id,project_id,endpoint_id,revision);
        ALTER TABLE aip_action_webhook_inbox_receipt
          ADD CONSTRAINT fk_action_webhook_receipt_endpoint
            FOREIGN KEY (org_id,project_id,endpoint_id,endpoint_revision)
            REFERENCES aip_action_webhook_endpoint_revision(org_id,project_id,endpoint_id,revision);
        ALTER TABLE aip_action_webhook_replay_key
          ADD CONSTRAINT fk_action_webhook_replay_receipt
            FOREIGN KEY (org_id,project_id,receipt_id)
            REFERENCES aip_action_webhook_inbox_receipt(org_id,project_id,receipt_id);
        ALTER TABLE aip_action_webhook_observation
          ADD CONSTRAINT fk_action_webhook_observation_receipt
            FOREIGN KEY (org_id,project_id,receipt_id)
            REFERENCES aip_action_webhook_inbox_receipt(org_id,project_id,receipt_id),
          ADD CONSTRAINT fk_action_webhook_observation_attempt
            FOREIGN KEY (org_id,project_id,attempt_id)
            REFERENCES aip_action_execution_attempt(org_id,project_id,attempt_id);
        ALTER TABLE aip_action_webhook_reducer_view
          ADD CONSTRAINT fk_action_webhook_reducer_attempt
            FOREIGN KEY (org_id,project_id,attempt_id)
            REFERENCES aip_action_execution_attempt(org_id,project_id,attempt_id);
        ALTER TABLE aip_action_webhook_case
          ADD CONSTRAINT fk_action_webhook_case_receipt
            FOREIGN KEY (org_id,project_id,receipt_id)
            REFERENCES aip_action_webhook_inbox_receipt(org_id,project_id,receipt_id)"""
    )
    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""CREATE POLICY {table}_tenant_scope ON {table}
                USING (org_id=current_setting('aos.org_id', true)
                   AND project_id=current_setting('aos.project_id', true))
                WITH CHECK (org_id=current_setting('aos.org_id', true)
                   AND project_id=current_setting('aos.project_id', true))"""
        )
        privileges = (
            "SELECT,INSERT,UPDATE"
            if table == "aip_action_webhook_reducer_view"
            else "SELECT,INSERT"
        )
        op.execute(f"GRANT {privileges} ON {table} TO aos_runtime")
    for table in (
        "aip_action_webhook_endpoint_revision",
        "aip_action_webhook_inbox_receipt",
        "aip_action_webhook_replay_key",
        "aip_action_webhook_observation",
        "aip_action_webhook_case",
    ):
        op.execute(
            f"""CREATE TRIGGER {table}_append_only
                BEFORE UPDATE OR DELETE ON {table}
                FOR EACH ROW EXECUTE FUNCTION guard_aip4_append_only()"""
        )


def downgrade() -> None:
    op.execute(
        """DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM aip_action_webhook_inbox_receipt LIMIT 1)
             OR EXISTS (SELECT 1 FROM aip_action_webhook_observation LIMIT 1)
             OR EXISTS (SELECT 1 FROM aip_action_webhook_case LIMIT 1) THEN
            RAISE EXCEPTION 'W5_005_FACTS_EXIST';
          END IF;
        END $$"""
    )
    # The directory owns a foreign key to endpoint_revision, so it must be
    # removed before the tenant table family.  Keep the explicit order instead
    # of CASCADE so unexpected dependencies still fail closed.
    op.execute("DROP TABLE aip_action_webhook_endpoint_directory")
    for table in reversed(TENANT_TABLES):
        op.execute(f"DROP TABLE {table}")
