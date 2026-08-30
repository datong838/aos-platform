"""Add tenant-scoped Logic automation policy and run authority.

Revision ID: aip_p3_001
Revises: wcat_003
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "aip_p3_001"
down_revision: str | Sequence[str] | None = "wcat_003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE aip_logic_automation_policy (
          org_id TEXT NOT NULL,
          project_id TEXT NOT NULL,
          automation_id TEXT NOT NULL,
          graph_id TEXT NOT NULL,
          publication_id TEXT NOT NULL,
          graph_revision BIGINT NOT NULL CHECK (graph_revision >= 1),
          graph_hash TEXT NOT NULL CHECK (graph_hash ~ '^[0-9a-f]{64}$'),
          name TEXT NOT NULL CHECK (btrim(name) <> ''),
          trigger_type TEXT NOT NULL CHECK (trigger_type IN ('manual','cron','event')),
          schedule TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL CHECK (status IN ('active','paused')),
          revision BIGINT NOT NULL CHECK (revision >= 1),
          actor TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id,project_id,automation_id),
          FOREIGN KEY (org_id,project_id,publication_id)
            REFERENCES aip_logic_publication (org_id,project_id,publication_id),
          FOREIGN KEY (org_id,project_id,graph_id,graph_revision)
            REFERENCES aip_logic_graph_revision (org_id,project_id,graph_id,revision)
        )
        """
    )
    op.execute(
        """CREATE INDEX idx_aip_logic_automation_graph
             ON aip_logic_automation_policy
             (org_id,project_id,graph_id,updated_at DESC)"""
    )
    op.execute(
        """
        CREATE TABLE aip_logic_automation_run (
          org_id TEXT NOT NULL,
          project_id TEXT NOT NULL,
          run_id TEXT NOT NULL,
          automation_id TEXT NOT NULL,
          policy_revision BIGINT NOT NULL CHECK (policy_revision >= 1),
          trigger TEXT NOT NULL CHECK (trigger IN ('manual','cron','event')),
          idempotency_key TEXT NOT NULL CHECK (char_length(idempotency_key) BETWEEN 1 AND 200),
          task_id TEXT NOT NULL,
          task_run_id TEXT NOT NULL,
          status TEXT NOT NULL CHECK (status IN ('accepted','failed')),
          receipt_id TEXT NOT NULL,
          production_written BOOLEAN NOT NULL DEFAULT FALSE CHECK (production_written=FALSE),
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          finished_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id,project_id,run_id),
          UNIQUE (org_id,project_id,receipt_id),
          UNIQUE (org_id,project_id,automation_id,idempotency_key),
          FOREIGN KEY (org_id,project_id,automation_id)
            REFERENCES aip_logic_automation_policy (org_id,project_id,automation_id),
          FOREIGN KEY (org_id,project_id,task_id)
            REFERENCES aip_task (org_id,project_id,task_id),
          FOREIGN KEY (org_id,project_id,task_run_id)
            REFERENCES aip_task_run (org_id,project_id,run_id)
        )
        """
    )
    op.execute(
        """CREATE INDEX idx_aip_logic_automation_run_history
             ON aip_logic_automation_run
             (org_id,project_id,automation_id,created_at DESC)"""
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS aip_logic_automation_run")
    op.execute("DROP TABLE IF EXISTS aip_logic_automation_policy")
