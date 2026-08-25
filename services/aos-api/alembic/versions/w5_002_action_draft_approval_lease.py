"""Add explicit Action Draft revisions and exact approval/lease lineage.

Revision ID: w5_002
Revises: w5_001
Create Date: 2026-08-25
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "w5_002"
down_revision: str | Sequence[str] | None = "w5_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """CREATE TABLE aip_action_draft_head (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, draft_id TEXT NOT NULL,
          current_revision BIGINT NOT NULL, version BIGINT NOT NULL DEFAULT 1,
          lifecycle TEXT NOT NULL DEFAULT 'editable', submitted_proposal_id TEXT,
          idempotency_key TEXT NOT NULL, request_hash TEXT NOT NULL,
          created_by TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id,project_id,draft_id),
          UNIQUE (org_id,project_id,idempotency_key),
          CHECK (current_revision >= 1 AND version >= 1),
          CHECK (lifecycle IN ('editable','submitted','superseded')),
          FOREIGN KEY (org_id,project_id) REFERENCES twa_workspace(org_id,project_id)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_action_draft_revision (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, draft_id TEXT NOT NULL,
          revision BIGINT NOT NULL, lifecycle TEXT NOT NULL,
          request_payload JSONB NOT NULL, action_type_snapshot JSONB NOT NULL,
          risk_snapshot JSONB NOT NULL, approval_policy_hash TEXT NOT NULL,
          content_hash TEXT NOT NULL, created_by TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id,project_id,draft_id,revision),
          CHECK (revision >= 1),
          CHECK (lifecycle IN ('editable','submitted','superseded')),
          CHECK (jsonb_typeof(request_payload)='object'),
          CHECK (jsonb_typeof(action_type_snapshot)='object'),
          CHECK (jsonb_typeof(risk_snapshot)='object'),
          CHECK (approval_policy_hash ~ '^[0-9a-f]{64}$'),
          CHECK (content_hash ~ '^[0-9a-f]{64}$'),
          FOREIGN KEY (org_id,project_id,draft_id)
            REFERENCES aip_action_draft_head(org_id,project_id,draft_id)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_action_draft_command (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, command_id TEXT NOT NULL,
          draft_id TEXT NOT NULL, command_kind TEXT NOT NULL, request_hash TEXT NOT NULL,
          result_revision BIGINT, result_proposal_id TEXT, idempotency_key TEXT NOT NULL,
          actor_id TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id,project_id,command_id),
          UNIQUE (org_id,project_id,idempotency_key),
          CHECK (command_kind IN ('create','revise','submit')),
          FOREIGN KEY (org_id,project_id,draft_id)
            REFERENCES aip_action_draft_head(org_id,project_id,draft_id)
        )"""
    )
    op.execute(
        """ALTER TABLE aip_action_proposal
        ADD COLUMN source_draft_id TEXT,
        ADD COLUMN source_draft_revision BIGINT,
        ADD COLUMN source_draft_hash TEXT,
        ADD COLUMN approval_policy_hash TEXT,
        ADD CONSTRAINT ck_aip_action_proposal_source_draft_w5_002 CHECK(
          (source_draft_id IS NULL AND source_draft_revision IS NULL AND source_draft_hash IS NULL)
          OR (source_draft_id IS NOT NULL AND source_draft_revision >= 1
              AND source_draft_hash ~ '^[0-9a-f]{64}$')),
        ADD CONSTRAINT ck_aip_action_proposal_policy_hash_w5_002 CHECK(
          approval_policy_hash IS NULL OR approval_policy_hash ~ '^[0-9a-f]{64}$')"""
    )
    op.execute(
        """ALTER TABLE aip_action_approval_event
        ADD COLUMN action_binding_hash TEXT,
        ADD COLUMN approval_policy_hash TEXT,
        ADD COLUMN slot_id TEXT,
        ADD COLUMN eligibility_snapshot_hash TEXT,
        ADD CONSTRAINT ck_aip_action_approval_binding_hash_w5_002 CHECK(
          action_binding_hash IS NULL OR action_binding_hash ~ '^[0-9a-f]{64}$'),
        ADD CONSTRAINT ck_aip_action_approval_policy_hash_w5_002 CHECK(
          approval_policy_hash IS NULL OR approval_policy_hash ~ '^[0-9a-f]{64}$'),
        ADD CONSTRAINT ck_aip_action_approval_eligibility_hash_w5_002 CHECK(
          eligibility_snapshot_hash IS NULL OR eligibility_snapshot_hash ~ '^[0-9a-f]{64}$')"""
    )
    op.execute(
        """ALTER TABLE aip_action_execution_lease
        ADD COLUMN action_binding_hash TEXT,
        ADD COLUMN approval_set_hash TEXT,
        ADD COLUMN reservation_ref JSONB,
        ADD COLUMN idempotency_key TEXT,
        ADD CONSTRAINT ck_aip_action_lease_binding_hash_w5_002 CHECK(
          action_binding_hash IS NULL OR action_binding_hash ~ '^[0-9a-f]{64}$'),
        ADD CONSTRAINT ck_aip_action_lease_approval_hash_w5_002 CHECK(
          approval_set_hash IS NULL OR approval_set_hash ~ '^[0-9a-f]{64}$'),
        ADD CONSTRAINT ck_aip_action_lease_reservation_w5_002 CHECK(
          reservation_ref IS NULL OR jsonb_typeof(reservation_ref)='object')"""
    )
    for table in (
        "aip_action_draft_head",
        "aip_action_draft_revision",
        "aip_action_draft_command",
    ):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""CREATE POLICY tenant_scope_{table}_w5_002 ON {table} TO aos_runtime
            USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
               AND project_id=NULLIF(current_setting('aos.project_id',true),''))
            WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
               AND project_id=NULLIF(current_setting('aos.project_id',true),''))"""
        )
        op.execute(f"GRANT SELECT,INSERT,UPDATE ON {table} TO aos_runtime")
    op.execute("REVOKE UPDATE,DELETE ON aip_action_draft_revision FROM aos_runtime")
    op.execute("REVOKE UPDATE,DELETE ON aip_action_draft_command FROM aos_runtime")
    op.execute(
        """CREATE OR REPLACE FUNCTION reject_aip_action_draft_revision_mutation_w5_002()
        RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
          RAISE EXCEPTION 'AIP_ACTION_DRAFT_REVISION_IMMUTABLE' USING ERRCODE='55000';
        END $$"""
    )
    op.execute(
        """CREATE TRIGGER aip_action_draft_revision_immutable_w5_002
        BEFORE UPDATE OR DELETE ON aip_action_draft_revision
        FOR EACH ROW EXECUTE FUNCTION reject_aip_action_draft_revision_mutation_w5_002()"""
    )


def downgrade() -> None:
    op.execute(
        """DO $$ BEGIN IF EXISTS (SELECT 1 FROM aip_action_draft_head LIMIT 1)
        OR EXISTS (SELECT 1 FROM aip_action_approval_event WHERE approval_policy_hash IS NOT NULL LIMIT 1)
        OR EXISTS (SELECT 1 FROM aip_action_execution_lease WHERE approval_set_hash IS NOT NULL LIMIT 1)
        THEN RAISE EXCEPTION 'cannot downgrade w5_002 with Draft/Approval/Lease facts'
          USING ERRCODE='55000'; END IF; END $$"""
    )
    op.execute(
        """DROP TRIGGER IF EXISTS aip_action_draft_revision_immutable_w5_002
        ON aip_action_draft_revision"""
    )
    op.execute("DROP FUNCTION IF EXISTS reject_aip_action_draft_revision_mutation_w5_002()")
    op.execute(
        """ALTER TABLE aip_action_execution_lease
        DROP CONSTRAINT IF EXISTS ck_aip_action_lease_binding_hash_w5_002,
        DROP CONSTRAINT IF EXISTS ck_aip_action_lease_approval_hash_w5_002,
        DROP CONSTRAINT IF EXISTS ck_aip_action_lease_reservation_w5_002,
        DROP COLUMN IF EXISTS action_binding_hash,
        DROP COLUMN IF EXISTS approval_set_hash,
        DROP COLUMN IF EXISTS reservation_ref,
        DROP COLUMN IF EXISTS idempotency_key"""
    )
    op.execute(
        """ALTER TABLE aip_action_approval_event
        DROP CONSTRAINT IF EXISTS ck_aip_action_approval_binding_hash_w5_002,
        DROP CONSTRAINT IF EXISTS ck_aip_action_approval_policy_hash_w5_002,
        DROP CONSTRAINT IF EXISTS ck_aip_action_approval_eligibility_hash_w5_002,
        DROP COLUMN IF EXISTS action_binding_hash,
        DROP COLUMN IF EXISTS approval_policy_hash,
        DROP COLUMN IF EXISTS slot_id,
        DROP COLUMN IF EXISTS eligibility_snapshot_hash"""
    )
    op.execute(
        """ALTER TABLE aip_action_proposal
        DROP CONSTRAINT IF EXISTS ck_aip_action_proposal_source_draft_w5_002,
        DROP CONSTRAINT IF EXISTS ck_aip_action_proposal_policy_hash_w5_002,
        DROP COLUMN IF EXISTS source_draft_id,
        DROP COLUMN IF EXISTS source_draft_revision,
        DROP COLUMN IF EXISTS source_draft_hash,
        DROP COLUMN IF EXISTS approval_policy_hash"""
    )
    op.execute("DROP TABLE IF EXISTS aip_action_draft_command")
    op.execute("DROP TABLE IF EXISTS aip_action_draft_revision")
    op.execute("DROP TABLE IF EXISTS aip_action_draft_head")
