"""Add tenant-scoped Evals suites and immutable Logic report evidence.

Revision ID: 228logiceval
Revises: 228logicrun
Create Date: 2026-08-02
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "228logiceval"
down_revision: str | Sequence[str] | None = "228logicrun"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE aip_eval_suite (
          org_id TEXT NOT NULL,
          project_id TEXT NOT NULL,
          suite_id TEXT NOT NULL,
          name TEXT NOT NULL,
          cases JSONB NOT NULL DEFAULT '[]'::jsonb,
          gate_threshold DOUBLE PRECISION NOT NULL DEFAULT 0.8
            CHECK (gate_threshold >= 0.0 AND gate_threshold <= 1.0),
          actor TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id, project_id, suite_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE aip_eval_report (
          org_id TEXT NOT NULL,
          project_id TEXT NOT NULL,
          report_id TEXT NOT NULL,
          suite_id TEXT NOT NULL,
          target_type TEXT NOT NULL CHECK (target_type = 'logic_graph'),
          target_id TEXT NOT NULL,
          target_revision BIGINT NOT NULL CHECK (target_revision >= 1),
          target_hash TEXT NOT NULL CHECK (length(target_hash) = 64),
          results JSONB NOT NULL DEFAULT '[]'::jsonb,
          pass_rate DOUBLE PRECISION NOT NULL
            CHECK (pass_rate >= 0.0 AND pass_rate <= 1.0),
          passed INTEGER NOT NULL CHECK (passed >= 0),
          failed INTEGER NOT NULL CHECK (failed >= 0),
          total INTEGER NOT NULL CHECK (total >= 0 AND total = passed + failed),
          gate_passed BOOLEAN NOT NULL,
          run_at TIMESTAMPTZ NOT NULL,
          actor TEXT NOT NULL,
          PRIMARY KEY (org_id, project_id, report_id),
          FOREIGN KEY (org_id, project_id, suite_id)
            REFERENCES aip_eval_suite (org_id, project_id, suite_id),
          FOREIGN KEY (org_id, project_id, target_id, target_revision)
            REFERENCES aip_logic_graph_revision
              (org_id, project_id, graph_id, revision)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX idx_aip_eval_suite_created
          ON aip_eval_suite (org_id, project_id, created_at DESC, suite_id ASC)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_aip_eval_report_history
          ON aip_eval_report
             (org_id, project_id, suite_id, run_at DESC, report_id DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_aip_eval_report_target
          ON aip_eval_report
             (org_id, project_id, target_id, target_revision, target_hash)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS aip_eval_report")
    op.execute("DROP TABLE IF EXISTS aip_eval_suite")
