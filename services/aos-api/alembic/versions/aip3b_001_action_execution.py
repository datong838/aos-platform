"""AIP-3B execution guardrails and append-only receipt reconciliation.

Revision ID: aip3b_001
Revises: aip3_001
Create Date: 2026-08-11
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "aip3b_001"
down_revision: str | Sequence[str] | None = "aip3_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE aip_action_receipt DROP CONSTRAINT aip_action_receipt_org_id_project_id_lease_id_key")
    op.execute("ALTER TABLE aip_action_receipt ADD COLUMN receipt_kind TEXT NOT NULL DEFAULT 'initial'")
    op.execute("ALTER TABLE aip_action_receipt ADD COLUMN supersedes_receipt_id TEXT")
    op.execute("ALTER TABLE aip_action_receipt ADD CONSTRAINT aip_action_receipt_kind_check CHECK (receipt_kind IN ('initial','reconcile'))")
    op.execute(
        """ALTER TABLE aip_action_receipt ADD CONSTRAINT aip_action_receipt_supersedes_fk
        FOREIGN KEY (org_id,project_id,supersedes_receipt_id)
        REFERENCES aip_action_receipt(org_id,project_id,receipt_id)"""
    )
    op.execute(
        """CREATE UNIQUE INDEX aip_action_receipt_initial_lease_uq
        ON aip_action_receipt(org_id,project_id,lease_id) WHERE receipt_kind='initial'"""
    )
    op.execute(
        """CREATE UNIQUE INDEX aip_action_receipt_reconcile_parent_uq
        ON aip_action_receipt(org_id,project_id,supersedes_receipt_id)
        WHERE receipt_kind='reconcile'"""
    )
    op.execute(
        """ALTER TABLE aip_action_receipt ADD CONSTRAINT aip_action_receipt_chain_check CHECK (
          (receipt_kind='initial' AND supersedes_receipt_id IS NULL)
          OR (receipt_kind='reconcile' AND supersedes_receipt_id IS NOT NULL AND status='reconciled')
        )"""
    )

    op.execute(
        """CREATE TABLE aip_action_guardrail (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, guardrail_id TEXT NOT NULL,
          level TEXT NOT NULL, action_type_id TEXT, kill_enabled BOOLEAN NOT NULL DEFAULT FALSE,
          daily_budget BIGINT, rate_limit_per_minute INTEGER,
          updated_by TEXT NOT NULL, updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id,project_id,guardrail_id),
          CHECK (level IN ('org','project','action_type')),
          CHECK (daily_budget IS NULL OR daily_budget >= 0),
          CHECK (rate_limit_per_minute IS NULL OR rate_limit_per_minute >= 0),
          CHECK ((level='action_type' AND action_type_id IS NOT NULL) OR (level<>'action_type' AND action_type_id IS NULL)),
          FOREIGN KEY (org_id,project_id) REFERENCES twa_workspace(org_id,project_id)
        )"""
    )
    op.execute(
        """CREATE UNIQUE INDEX aip_action_guardrail_effective_uq
        ON aip_action_guardrail(org_id,project_id,level,COALESCE(action_type_id,''))"""
    )
    op.execute(
        """CREATE TABLE aip_action_usage (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, action_type_id TEXT NOT NULL,
          usage_day DATE NOT NULL, usage_minute TIMESTAMPTZ NOT NULL,
          execution_count BIGINT NOT NULL DEFAULT 0, budget_units BIGINT NOT NULL DEFAULT 0,
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id,project_id,action_type_id,usage_day,usage_minute),
          CHECK (execution_count >= 0), CHECK (budget_units >= 0),
          FOREIGN KEY (org_id,project_id) REFERENCES twa_workspace(org_id,project_id)
        )"""
    )

    for table in ("aip_action_guardrail", "aip_action_usage"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""CREATE POLICY tenant_scope_{table}_aip3b ON {table} TO aos_runtime
            USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
               AND project_id=NULLIF(current_setting('aos.project_id',true),''))
            WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
               AND project_id=NULLIF(current_setting('aos.project_id',true),''))"""
        )
        op.execute(f"GRANT SELECT,INSERT,UPDATE ON {table} TO aos_runtime")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS aip_action_usage CASCADE")
    op.execute("DROP TABLE IF EXISTS aip_action_guardrail CASCADE")
    op.execute("DROP INDEX IF EXISTS aip_action_receipt_reconcile_parent_uq")
    op.execute("DROP INDEX IF EXISTS aip_action_receipt_initial_lease_uq")
    op.execute("ALTER TABLE aip_action_receipt DROP CONSTRAINT IF EXISTS aip_action_receipt_chain_check")
    op.execute("ALTER TABLE aip_action_receipt DROP CONSTRAINT IF EXISTS aip_action_receipt_supersedes_fk")
    op.execute("ALTER TABLE aip_action_receipt DROP CONSTRAINT IF EXISTS aip_action_receipt_kind_check")
    op.execute("ALTER TABLE aip_action_receipt DROP COLUMN IF EXISTS supersedes_receipt_id")
    op.execute("ALTER TABLE aip_action_receipt DROP COLUMN IF EXISTS receipt_kind")
    op.execute("ALTER TABLE aip_action_receipt ADD CONSTRAINT aip_action_receipt_org_id_project_id_lease_id_key UNIQUE (org_id,project_id,lease_id)")
