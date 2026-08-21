"""ResearchJob cancel/retry command receipts (W-L17).

Revision ID: aip11_001
Revises: o1ux2_002
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "aip11_001"
down_revision: str | Sequence[str] | None = "o1ux2_002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ADR W4-07: retry mints a new job for the same run/step; unique(run,step) blocks that.
    op.execute(
        """ALTER TABLE aip_research_job_manifest
           DROP CONSTRAINT IF EXISTS aip_research_job_manifest_org_id_project_id_run_id_step_key_key"""
    )
    op.execute(
        """CREATE INDEX IF NOT EXISTS aip_research_job_manifest_run_step_idx
           ON aip_research_job_manifest(org_id, project_id, run_id, step_key, created_at DESC)"""
    )
    op.execute(
        """CREATE TABLE aip_research_job_command_receipt (
          org_id TEXT NOT NULL,
          project_id TEXT NOT NULL,
          receipt_id TEXT NOT NULL,
          job_id TEXT NOT NULL,
          command TEXT NOT NULL CHECK (command IN ('cancel','retry')),
          idempotency_key TEXT NOT NULL,
          request_hash CHAR(64) NOT NULL CHECK (request_hash ~ '^[0-9a-f]{64}$'),
          actor TEXT NOT NULL,
          outcome_status TEXT,
          retry_job_id TEXT,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id, project_id, receipt_id),
          UNIQUE (org_id, project_id, command, idempotency_key),
          FOREIGN KEY (org_id, project_id, job_id)
            REFERENCES aip_research_job_manifest(org_id, project_id, job_id)
            ON DELETE RESTRICT
        )"""
    )
    op.execute(
        """CREATE INDEX aip_research_job_command_job_idx
           ON aip_research_job_command_receipt(org_id, project_id, job_id, created_at DESC)"""
    )
    op.execute(
        "ALTER TABLE aip_research_job_command_receipt ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE aip_research_job_command_receipt FORCE ROW LEVEL SECURITY"
    )
    op.execute(
        """CREATE POLICY tenant_scope_aip_research_job_command_receipt
           ON aip_research_job_command_receipt TO aos_runtime
           USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
              AND project_id=NULLIF(current_setting('aos.project_id',true),''))
           WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
              AND project_id=NULLIF(current_setting('aos.project_id',true),''))"""
    )
    op.execute(
        "GRANT SELECT,INSERT ON aip_research_job_command_receipt TO aos_runtime"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS aip_research_job_command_receipt CASCADE")
    op.execute("DROP INDEX IF EXISTS aip_research_job_manifest_run_step_idx")
    op.execute(
        """DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conname = 'aip_research_job_manifest_org_id_project_id_run_id_step_key_key'
          ) THEN
            ALTER TABLE aip_research_job_manifest
              ADD CONSTRAINT aip_research_job_manifest_org_id_project_id_run_id_step_key_key
              UNIQUE (org_id, project_id, run_id, step_key);
          END IF;
        END $$"""
    )
