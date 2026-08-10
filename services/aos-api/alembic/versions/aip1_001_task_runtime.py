"""AIP-1 canonical Task/Plan/Run runtime.

Revision ID: aip1_001
Revises: o1ux2_001
Create Date: 2026-08-11
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "aip1_001"
down_revision: str | Sequence[str] | None = "o1ux2_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    "aip_task",
    "aip_plan_revision",
    "aip_task_run",
    "aip_step_run",
    "aip_checkpoint",
    "aip_artifact",
    "aip_evidence",
)


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE aip_task (
          org_id TEXT NOT NULL,
          project_id TEXT NOT NULL,
          task_id TEXT NOT NULL,
          task_type TEXT NOT NULL,
          title TEXT NOT NULL,
          description TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL,
          priority INTEGER NOT NULL DEFAULT 50,
          goal JSONB NOT NULL DEFAULT '{}'::jsonb,
          selection_ref JSONB,
          policy_revision TEXT,
          idempotency_key TEXT NOT NULL,
          request_hash TEXT NOT NULL,
          current_plan_revision_id TEXT,
          version BIGINT NOT NULL DEFAULT 1,
          created_by TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id, project_id, task_id),
          UNIQUE (org_id, project_id, idempotency_key),
          CHECK (priority BETWEEN 0 AND 100),
          CHECK (version >= 1),
          CHECK (status IN ('pending','planning','awaiting_approval','approved','executing','paused','completed','failed','cancelled','rolled_back')),
          FOREIGN KEY (org_id, project_id)
            REFERENCES twa_workspace(org_id, project_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE aip_plan_revision (
          org_id TEXT NOT NULL,
          project_id TEXT NOT NULL,
          plan_revision_id TEXT NOT NULL,
          task_id TEXT NOT NULL,
          revision BIGINT NOT NULL,
          content_hash TEXT NOT NULL,
          steps JSONB NOT NULL,
          dependencies JSONB NOT NULL DEFAULT '[]'::jsonb,
          risk JSONB NOT NULL DEFAULT '{}'::jsonb,
          approval_status TEXT NOT NULL DEFAULT 'draft',
          approved_by TEXT,
          approved_at TIMESTAMPTZ,
          idempotency_key TEXT NOT NULL,
          request_hash TEXT NOT NULL,
          created_by TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id, project_id, plan_revision_id),
          UNIQUE (org_id, project_id, task_id, revision),
          UNIQUE (org_id, project_id, task_id, idempotency_key),
          CHECK (revision >= 1),
          CHECK (approval_status IN ('draft','approved','superseded','rejected')),
          FOREIGN KEY (org_id, project_id, task_id)
            REFERENCES aip_task(org_id, project_id, task_id)
        )
        """
    )
    op.execute(
        """ALTER TABLE aip_task
        ADD CONSTRAINT aip_task_current_plan_fk
        FOREIGN KEY (org_id, project_id, current_plan_revision_id)
        REFERENCES aip_plan_revision(org_id, project_id, plan_revision_id)
        DEFERRABLE INITIALLY DEFERRED"""
    )
    op.execute(
        """
        CREATE TABLE aip_task_run (
          org_id TEXT NOT NULL,
          project_id TEXT NOT NULL,
          run_id TEXT NOT NULL,
          task_id TEXT NOT NULL,
          plan_revision_id TEXT NOT NULL,
          logic_graph_id TEXT,
          logic_revision BIGINT,
          status TEXT NOT NULL DEFAULT 'queued',
          idempotency_key TEXT NOT NULL,
          request_hash TEXT NOT NULL,
          last_checkpoint_id TEXT,
          version BIGINT NOT NULL DEFAULT 1,
          created_by TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          started_at TIMESTAMPTZ,
          finished_at TIMESTAMPTZ,
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id, project_id, run_id),
          UNIQUE (org_id, project_id, task_id, idempotency_key),
          CHECK (status IN ('queued','running','succeeded','failed','cancelled','unknown')),
          CHECK (version >= 1),
          FOREIGN KEY (org_id, project_id, task_id)
            REFERENCES aip_task(org_id, project_id, task_id),
          FOREIGN KEY (org_id, project_id, plan_revision_id)
            REFERENCES aip_plan_revision(org_id, project_id, plan_revision_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE aip_step_run (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, step_run_id TEXT NOT NULL,
          run_id TEXT NOT NULL, step_key TEXT NOT NULL, attempt INTEGER NOT NULL,
          status TEXT NOT NULL DEFAULT 'queued', input_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
          output_refs JSONB NOT NULL DEFAULT '[]'::jsonb, think_ref JSONB, action_ref JSONB,
          verify_ref JSONB, observe_ref JSONB, error JSONB, token_count BIGINT NOT NULL DEFAULT 0,
          cost_amount NUMERIC(20,8) NOT NULL DEFAULT 0, lease_owner TEXT,
          lease_expires_at TIMESTAMPTZ, heartbeat_at TIMESTAMPTZ,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id, project_id, step_run_id),
          UNIQUE (org_id, project_id, run_id, step_key, attempt),
          CHECK (attempt >= 1),
          CHECK (status IN ('queued','running','succeeded','failed','skipped','unknown')),
          FOREIGN KEY (org_id, project_id, run_id)
            REFERENCES aip_task_run(org_id, project_id, run_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE aip_checkpoint (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, checkpoint_id TEXT NOT NULL,
          run_id TEXT NOT NULL, sequence BIGINT NOT NULL, schema_version INTEGER NOT NULL DEFAULT 1,
          step_key TEXT, state_hash TEXT NOT NULL, state_snapshot_ref JSONB,
          artifact_refs JSONB NOT NULL DEFAULT '[]'::jsonb, resume_token_hash TEXT,
          created_by TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id, project_id, checkpoint_id),
          UNIQUE (org_id, project_id, run_id, sequence),
          CHECK (sequence >= 1), CHECK (schema_version >= 1),
          FOREIGN KEY (org_id, project_id, run_id)
            REFERENCES aip_task_run(org_id, project_id, run_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE aip_artifact (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, artifact_id TEXT NOT NULL,
          run_id TEXT, artifact_type TEXT NOT NULL, content_ref TEXT, schema_ref TEXT,
          source JSONB NOT NULL DEFAULT '{}'::jsonb, evidence_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
          marking JSONB NOT NULL DEFAULT '[]'::jsonb, content_hash TEXT,
          metadata JSONB NOT NULL DEFAULT '{}'::jsonb, created_by TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id, project_id, artifact_id),
          FOREIGN KEY (org_id, project_id, run_id)
            REFERENCES aip_task_run(org_id, project_id, run_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE aip_evidence (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, evidence_id TEXT NOT NULL,
          run_id TEXT, evidence_type TEXT NOT NULL, subject_ref JSONB NOT NULL,
          source_type TEXT NOT NULL, source_ref TEXT NOT NULL, observed_at TIMESTAMPTZ NOT NULL,
          freshness_at TIMESTAMPTZ NOT NULL, content_hash TEXT NOT NULL, redaction JSONB NOT NULL DEFAULT '{}'::jsonb,
          payload JSONB NOT NULL DEFAULT '{}'::jsonb, created_by TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id, project_id, evidence_id),
          FOREIGN KEY (org_id, project_id, run_id)
            REFERENCES aip_task_run(org_id, project_id, run_id)
        )
        """
    )
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""CREATE POLICY tenant_scope_{table}_aip1 ON {table} TO aos_runtime
            USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
               AND project_id=NULLIF(current_setting('aos.project_id',true),''))
            WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
               AND project_id=NULLIF(current_setting('aos.project_id',true),''))"""
        )
        op.execute(f"GRANT SELECT,INSERT,UPDATE,DELETE ON {table} TO aos_runtime")

    op.execute("CREATE INDEX aip_task_updated_idx ON aip_task(org_id,project_id,updated_at DESC,task_id)")
    op.execute("CREATE INDEX aip_task_run_updated_idx ON aip_task_run(org_id,project_id,updated_at DESC,run_id)")


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
