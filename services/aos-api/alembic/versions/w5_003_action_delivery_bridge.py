"""Add durable Action execution intent and exact delivery bridge facts.

Revision ID: w5_003
Revises: w5_002
Create Date: 2026-08-25
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "w5_003"
down_revision: str | Sequence[str] | None = "w5_002"
branch_labels = None
depends_on = None


def _scope(table: str, *, write: bool = True) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""CREATE POLICY tenant_scope_{table}_w5_003 ON {table} TO aos_runtime
        USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
           AND project_id=NULLIF(current_setting('aos.project_id',true),''))
        WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
           AND project_id=NULLIF(current_setting('aos.project_id',true),''))"""
    )
    op.execute(f"GRANT SELECT,INSERT{',UPDATE' if write else ''} ON {table} TO aos_runtime")


def upgrade() -> None:
    op.execute(
        """CREATE TABLE aip_action_execution_attempt (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, attempt_id TEXT NOT NULL,
          lease_id TEXT NOT NULL, proposal_id TEXT NOT NULL, status TEXT NOT NULL,
          action_binding_hash TEXT, approval_set_hash TEXT,
          adapter_revision_ref JSONB, account_binding_ref JSONB,
          capability_binding_ref JSONB, reservation_ref JSONB,
          output_schema_ref JSONB, receipt_schema_ref JSONB,
          usage_schema_ref JSONB, redaction_policy_ref JSONB,
          idempotency_envelope TEXT NOT NULL, request_hash TEXT NOT NULL,
          request_artifact_ref JSONB, provider_request_id TEXT,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), claimed_at TIMESTAMPTZ,
          finished_at TIMESTAMPTZ,
          PRIMARY KEY (org_id,project_id,attempt_id),
          UNIQUE (org_id,project_id,lease_id),
          CHECK (status IN ('prepared','dispatch_claimed','accepted','applied','failed','unknown')),
          CHECK (action_binding_hash IS NULL OR action_binding_hash ~ '^[0-9a-f]{64}$'),
          CHECK (approval_set_hash IS NULL OR approval_set_hash ~ '^[0-9a-f]{64}$'),
          CHECK (idempotency_envelope ~ '^[0-9a-f]{64}$'),
          CHECK (request_hash ~ '^[0-9a-f]{64}$'),
          FOREIGN KEY (org_id,project_id,lease_id)
            REFERENCES aip_action_execution_lease(org_id,project_id,lease_id),
          FOREIGN KEY (org_id,project_id,proposal_id)
            REFERENCES aip_action_proposal(org_id,project_id,proposal_id)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_action_dispatch_outbox (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, outbox_id TEXT NOT NULL,
          attempt_id TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
          claim_token TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          claimed_at TIMESTAMPTZ, completed_at TIMESTAMPTZ,
          PRIMARY KEY (org_id,project_id,outbox_id),
          UNIQUE (org_id,project_id,attempt_id),
          CHECK (status IN ('pending','dispatching','delivered','unknown')),
          FOREIGN KEY (org_id,project_id,attempt_id)
            REFERENCES aip_action_execution_attempt(org_id,project_id,attempt_id)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_action_response_artifact (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, artifact_id TEXT NOT NULL,
          attempt_id TEXT NOT NULL, content_hash TEXT NOT NULL,
          controlled_payload JSONB NOT NULL, redaction_manifest JSONB NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id,project_id,artifact_id),
          UNIQUE (org_id,project_id,attempt_id),
          CHECK (content_hash ~ '^[0-9a-f]{64}$'),
          CHECK (jsonb_typeof(controlled_payload)='object'),
          CHECK (jsonb_typeof(redaction_manifest)='object'),
          FOREIGN KEY (org_id,project_id,attempt_id)
            REFERENCES aip_action_execution_attempt(org_id,project_id,attempt_id)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_action_settlement_request (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, settlement_request_id TEXT NOT NULL,
          attempt_id TEXT NOT NULL, receipt_id TEXT NOT NULL, reservation_ref JSONB,
          status TEXT NOT NULL, source_hash TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id,project_id,settlement_request_id),
          UNIQUE (org_id,project_id,attempt_id),
          CHECK (status IN ('pending','unknown','not_required','settled')),
          CHECK (source_hash ~ '^[0-9a-f]{64}$'),
          FOREIGN KEY (org_id,project_id,attempt_id)
            REFERENCES aip_action_execution_attempt(org_id,project_id,attempt_id)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_action_lineage_projection_request (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, projection_request_id TEXT NOT NULL,
          attempt_id TEXT NOT NULL, receipt_id TEXT NOT NULL,
          lineage_id TEXT NOT NULL, source_hash TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'pending',
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), projected_at TIMESTAMPTZ,
          PRIMARY KEY (org_id,project_id,projection_request_id),
          UNIQUE (org_id,project_id,receipt_id),
          CHECK (status IN ('pending','projected','conflict')),
          CHECK (source_hash ~ '^[0-9a-f]{64}$'),
          FOREIGN KEY (org_id,project_id,attempt_id)
            REFERENCES aip_action_execution_attempt(org_id,project_id,attempt_id)
        )"""
    )
    op.execute(
        """ALTER TABLE aip_action_receipt
        ADD COLUMN attempt_id TEXT,
        ADD COLUMN action_binding_hash TEXT,
        ADD COLUMN approval_set_hash TEXT,
        ADD COLUMN adapter_revision_ref JSONB,
        ADD COLUMN account_binding_ref JSONB,
        ADD COLUMN capability_binding_ref JSONB,
        ADD COLUMN reservation_ref JSONB,
        ADD COLUMN response_artifact_ref JSONB,
        ADD COLUMN response_hash TEXT,
        ADD COLUMN output_schema_ref JSONB,
        ADD COLUMN receipt_schema_ref JSONB,
        ADD COLUMN usage_schema_ref JSONB,
        ADD COLUMN redaction_policy_ref JSONB,
        ADD COLUMN usage_receipt_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
        ADD COLUMN lineage_source_ref JSONB,
        ADD COLUMN receipt_content_hash TEXT,
        ADD CONSTRAINT ck_aip_action_receipt_attempt_hashes_w5_003 CHECK (
          (action_binding_hash IS NULL OR action_binding_hash ~ '^[0-9a-f]{64}$')
          AND (approval_set_hash IS NULL OR approval_set_hash ~ '^[0-9a-f]{64}$')
          AND (response_hash IS NULL OR response_hash ~ '^[0-9a-f]{64}$')
          AND (receipt_content_hash IS NULL OR receipt_content_hash ~ '^[0-9a-f]{64}$')
          AND jsonb_typeof(usage_receipt_refs)='array'),
        ADD CONSTRAINT fk_aip_action_receipt_attempt_w5_003
          FOREIGN KEY (org_id,project_id,attempt_id)
          REFERENCES aip_action_execution_attempt(org_id,project_id,attempt_id)"""
    )
    op.execute(
        """ALTER TABLE aip_action_settlement_request
        ADD CONSTRAINT fk_action_settlement_receipt_w5_003
          FOREIGN KEY (org_id,project_id,receipt_id)
          REFERENCES aip_action_receipt(org_id,project_id,receipt_id)"""
    )
    op.execute(
        """ALTER TABLE aip_action_lineage_projection_request
        ADD CONSTRAINT fk_action_lineage_receipt_w5_003
          FOREIGN KEY (org_id,project_id,receipt_id)
          REFERENCES aip_action_receipt(org_id,project_id,receipt_id)"""
    )
    for table in (
        "aip_action_execution_attempt",
        "aip_action_dispatch_outbox",
        "aip_action_response_artifact",
        "aip_action_settlement_request",
        "aip_action_lineage_projection_request",
    ):
        _scope(table, write=table in {"aip_action_execution_attempt", "aip_action_dispatch_outbox", "aip_action_lineage_projection_request"})
    for table in ("aip_action_response_artifact", "aip_action_settlement_request"):
        op.execute(
            f"""CREATE TRIGGER {table}_append_only_w5_003
            BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION guard_aip4_append_only()"""
        )


def downgrade() -> None:
    op.execute(
        """DO $$ BEGIN IF EXISTS (SELECT 1 FROM aip_action_execution_attempt LIMIT 1)
        OR EXISTS (SELECT 1 FROM aip_action_receipt WHERE attempt_id IS NOT NULL LIMIT 1)
        THEN RAISE EXCEPTION 'cannot downgrade w5_003 with Action delivery facts'
          USING ERRCODE='55000'; END IF; END $$"""
    )
    op.execute("ALTER TABLE aip_action_receipt DROP CONSTRAINT IF EXISTS fk_aip_action_receipt_attempt_w5_003")
    op.execute("ALTER TABLE aip_action_receipt DROP CONSTRAINT IF EXISTS ck_aip_action_receipt_attempt_hashes_w5_003")
    for column in (
        "attempt_id", "action_binding_hash", "approval_set_hash", "adapter_revision_ref",
        "account_binding_ref", "capability_binding_ref", "reservation_ref",
        "response_artifact_ref", "response_hash", "output_schema_ref",
        "receipt_schema_ref", "usage_schema_ref", "redaction_policy_ref",
        "usage_receipt_refs", "lineage_source_ref",
        "receipt_content_hash",
    ):
        op.execute(f"ALTER TABLE aip_action_receipt DROP COLUMN IF EXISTS {column}")
    for table in (
        "aip_action_lineage_projection_request",
        "aip_action_settlement_request",
        "aip_action_response_artifact",
        "aip_action_dispatch_outbox",
        "aip_action_execution_attempt",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table}")
