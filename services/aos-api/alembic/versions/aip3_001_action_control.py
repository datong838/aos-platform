"""AIP-3 canonical Action Proposal, Approval, Lease and Receipt authority.

Revision ID: aip3_001
Revises: aip1_001
Create Date: 2026-08-11
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "aip3_001"
down_revision: str | Sequence[str] | None = "aip1_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    "aip_action_proposal",
    "aip_action_draft",
    "aip_action_approval_event",
    "aip_action_execution_lease",
    "aip_action_receipt",
    "aip_action_event",
)


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE aip_action_proposal (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, proposal_id TEXT NOT NULL,
          action_type_id TEXT NOT NULL, action_type_revision_hash TEXT NOT NULL,
          action_type_snapshot JSONB NOT NULL, task_id TEXT, run_id TEXT, object_ref JSONB,
          purpose TEXT NOT NULL, client_risk_hint TEXT, risk_level TEXT NOT NULL,
          policy_snapshot JSONB NOT NULL, payload JSONB NOT NULL, diff JSONB NOT NULL DEFAULT '{}'::jsonb,
          evidence_refs JSONB NOT NULL DEFAULT '[]'::jsonb, proposal_hash TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'drafted', expires_at TIMESTAMPTZ NOT NULL,
          idempotency_key TEXT NOT NULL, request_hash TEXT NOT NULL, version BIGINT NOT NULL DEFAULT 1,
          created_by TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id,project_id,proposal_id),
          UNIQUE (org_id,project_id,idempotency_key),
          CHECK (risk_level IN ('R0','R1','R2','R3','R4')),
          CHECK (status IN ('proposed','drafted','approved','rejected','expired','leased','executing','applied','failed','unknown','reconciled','compensated')),
          CHECK (version >= 1),
          FOREIGN KEY (org_id,project_id) REFERENCES twa_workspace(org_id,project_id),
          FOREIGN KEY (org_id,project_id,task_id) REFERENCES aip_task(org_id,project_id,task_id),
          FOREIGN KEY (org_id,project_id,run_id) REFERENCES aip_task_run(org_id,project_id,run_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE aip_action_draft (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, draft_id TEXT NOT NULL,
          proposal_id TEXT NOT NULL, proposal_version BIGINT NOT NULL, proposal_hash TEXT NOT NULL,
          snapshot JSONB NOT NULL, diff JSONB NOT NULL DEFAULT '{}'::jsonb,
          evidence_refs JSONB NOT NULL DEFAULT '[]'::jsonb, approval_policy JSONB NOT NULL,
          status TEXT NOT NULL DEFAULT 'awaiting_approval', created_by TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id,project_id,draft_id), UNIQUE (org_id,project_id,proposal_id),
          CHECK (status IN ('awaiting_approval','approved','rejected','expired')),
          FOREIGN KEY (org_id,project_id,proposal_id)
            REFERENCES aip_action_proposal(org_id,project_id,proposal_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE aip_action_approval_event (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, approval_event_id TEXT NOT NULL,
          proposal_id TEXT NOT NULL, proposal_version BIGINT NOT NULL, proposal_hash TEXT NOT NULL,
          decision TEXT NOT NULL, actor_id TEXT NOT NULL, reason TEXT NOT NULL DEFAULT '',
          expires_at TIMESTAMPTZ, idempotency_key TEXT NOT NULL, request_hash TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id,project_id,approval_event_id),
          UNIQUE (org_id,project_id,idempotency_key),
          CHECK (decision IN ('approved','rejected')),
          FOREIGN KEY (org_id,project_id,proposal_id)
            REFERENCES aip_action_proposal(org_id,project_id,proposal_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE aip_action_execution_lease (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, lease_id TEXT NOT NULL,
          proposal_id TEXT NOT NULL, proposal_hash TEXT NOT NULL, attempt INTEGER NOT NULL,
          status TEXT NOT NULL DEFAULT 'active', owner_id TEXT NOT NULL,
          expires_at TIMESTAMPTZ NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          consumed_at TIMESTAMPTZ,
          PRIMARY KEY (org_id,project_id,lease_id), UNIQUE (org_id,project_id,proposal_id,attempt),
          CHECK (attempt >= 1), CHECK (status IN ('active','consumed','expired','revoked')),
          FOREIGN KEY (org_id,project_id,proposal_id)
            REFERENCES aip_action_proposal(org_id,project_id,proposal_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE aip_action_receipt (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, receipt_id TEXT NOT NULL,
          proposal_id TEXT NOT NULL, lease_id TEXT NOT NULL, status TEXT NOT NULL,
          provider_request_id TEXT, request_fingerprint TEXT NOT NULL,
          evidence_refs JSONB NOT NULL DEFAULT '[]'::jsonb, payload JSONB NOT NULL DEFAULT '{}'::jsonb,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id,project_id,receipt_id),
          UNIQUE (org_id,project_id,lease_id),
          CHECK (status IN ('accepted','applied','failed','unknown','reconciled')),
          FOREIGN KEY (org_id,project_id,proposal_id)
            REFERENCES aip_action_proposal(org_id,project_id,proposal_id),
          FOREIGN KEY (org_id,project_id,lease_id)
            REFERENCES aip_action_execution_lease(org_id,project_id,lease_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE aip_action_event (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, event_id TEXT NOT NULL,
          proposal_id TEXT NOT NULL, event_type TEXT NOT NULL, actor_id TEXT NOT NULL,
          proposal_version BIGINT NOT NULL, proposal_hash TEXT NOT NULL,
          payload JSONB NOT NULL DEFAULT '{}'::jsonb, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id,project_id,event_id),
          FOREIGN KEY (org_id,project_id,proposal_id)
            REFERENCES aip_action_proposal(org_id,project_id,proposal_id)
        )
        """
    )
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""CREATE POLICY tenant_scope_{table}_aip3 ON {table} TO aos_runtime
            USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
               AND project_id=NULLIF(current_setting('aos.project_id',true),''))
            WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
               AND project_id=NULLIF(current_setting('aos.project_id',true),''))"""
        )
        privilege = "SELECT,INSERT" if table in {"aip_action_approval_event", "aip_action_receipt", "aip_action_event"} else "SELECT,INSERT,UPDATE"
        op.execute(f"GRANT {privilege} ON {table} TO aos_runtime")
    op.execute("CREATE INDEX aip_action_proposal_updated_idx ON aip_action_proposal(org_id,project_id,updated_at DESC,proposal_id)")
    op.execute("CREATE INDEX aip_action_event_timeline_idx ON aip_action_event(org_id,project_id,proposal_id,created_at,event_id)")


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
