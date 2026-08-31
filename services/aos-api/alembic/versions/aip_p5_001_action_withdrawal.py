"""Add fail-closed Action Proposal withdrawal authority.

Revision ID: aip_p5_001
Revises: aip_p4_001
Create Date: 2026-08-31
"""
from __future__ import annotations

from alembic import op

revision = "aip_p5_001"
down_revision = "aip_p4_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE aip_action_proposal DROP CONSTRAINT aip_action_proposal_status_check")
    op.execute("""ALTER TABLE aip_action_proposal ADD CONSTRAINT aip_action_proposal_status_check
        CHECK (status IN ('proposed','drafted','approved','rejected','expired','leased','executing','applied','failed','unknown','reconciled','compensated','withdrawn'))""")
    op.execute("ALTER TABLE aip_action_draft DROP CONSTRAINT aip_action_draft_status_check")
    op.execute("""ALTER TABLE aip_action_draft ADD CONSTRAINT aip_action_draft_status_check
        CHECK (status IN ('awaiting_approval','approved','rejected','expired','withdrawn'))""")
    op.execute("""CREATE TABLE aip_action_withdrawal_event (
        org_id TEXT NOT NULL, project_id TEXT NOT NULL, withdrawal_event_id TEXT NOT NULL,
        proposal_id TEXT NOT NULL, proposal_version BIGINT NOT NULL, proposal_hash TEXT NOT NULL,
        actor_id TEXT NOT NULL, reason TEXT NOT NULL, idempotency_key TEXT NOT NULL,
        request_hash TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY (org_id,project_id,withdrawal_event_id),
        UNIQUE (org_id,project_id,idempotency_key),
        FOREIGN KEY (org_id,project_id,proposal_id)
          REFERENCES aip_action_proposal(org_id,project_id,proposal_id)
    )""")
    op.execute("ALTER TABLE aip_action_withdrawal_event ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE aip_action_withdrawal_event FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY aip_action_withdrawal_event_tenant_isolation
        ON aip_action_withdrawal_event TO aos_runtime USING (
          org_id = NULLIF(current_setting('aos.org_id', true), '')
          AND project_id = NULLIF(current_setting('aos.project_id', true), '')
        ) WITH CHECK (
          org_id = NULLIF(current_setting('aos.org_id', true), '')
          AND project_id = NULLIF(current_setting('aos.project_id', true), '')
        )""")
    op.execute("GRANT SELECT,INSERT ON aip_action_withdrawal_event TO aos_runtime")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS aip_action_withdrawal_event")
    op.execute("ALTER TABLE aip_action_draft DROP CONSTRAINT aip_action_draft_status_check")
    op.execute("""ALTER TABLE aip_action_draft ADD CONSTRAINT aip_action_draft_status_check
        CHECK (status IN ('awaiting_approval','approved','rejected','expired'))""")
    op.execute("ALTER TABLE aip_action_proposal DROP CONSTRAINT aip_action_proposal_status_check")
    op.execute("""ALTER TABLE aip_action_proposal ADD CONSTRAINT aip_action_proposal_status_check
        CHECK (status IN ('proposed','drafted','approved','rejected','expired','leased','executing','applied','failed','unknown','reconciled','compensated'))""")
