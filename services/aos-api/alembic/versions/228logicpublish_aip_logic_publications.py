"""Add immutable tenant-scoped AIP Logic publications.

Revision ID: 228logicpublish
Revises: 228logiceval
Create Date: 2026-08-02
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "228logicpublish"
down_revision: str | Sequence[str] | None = "228logiceval"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE aip_logic_publication (
          org_id TEXT NOT NULL,
          project_id TEXT NOT NULL,
          publication_id TEXT NOT NULL,
          graph_id TEXT NOT NULL,
          graph_revision BIGINT NOT NULL CHECK (graph_revision >= 1),
          graph_hash TEXT NOT NULL CHECK (graph_hash ~ '^[0-9a-f]{64}$'),
          graph_snapshot JSONB NOT NULL CHECK (jsonb_typeof(graph_snapshot) = 'object'),
          dry_run_id TEXT NOT NULL,
          eval_suite_id TEXT NOT NULL,
          eval_report_id TEXT NOT NULL,
          eval_gate JSONB NOT NULL CHECK (jsonb_typeof(eval_gate) = 'object'),
          actor TEXT NOT NULL,
          idempotency_key TEXT NOT NULL,
          request_hash TEXT NOT NULL CHECK (request_hash ~ '^[0-9a-f]{64}$'),
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id, project_id, publication_id),
          UNIQUE (org_id, project_id, graph_id, graph_revision),
          UNIQUE (org_id, project_id, graph_id, idempotency_key),
          FOREIGN KEY (org_id, project_id, graph_id, graph_revision)
            REFERENCES aip_logic_graph_revision
              (org_id, project_id, graph_id, revision),
          FOREIGN KEY (org_id, project_id, graph_id, dry_run_id)
            REFERENCES aip_logic_graph_runs
              (org_id, project_id, graph_id, run_id),
          FOREIGN KEY (org_id, project_id, eval_report_id)
            REFERENCES aip_eval_report
              (org_id, project_id, report_id)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX idx_aip_logic_publication_history
          ON aip_logic_publication
             (org_id, project_id, graph_id, graph_revision DESC, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE FUNCTION reject_aip_logic_publication_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          RAISE EXCEPTION 'aip_logic_publication rows are immutable';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_aip_logic_publication_immutable
        BEFORE UPDATE OR DELETE ON aip_logic_publication
        FOR EACH ROW EXECUTE FUNCTION reject_aip_logic_publication_mutation()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_aip_logic_publication_immutable "
        "ON aip_logic_publication"
    )
    op.execute("DROP TABLE IF EXISTS aip_logic_publication")
    op.execute("DROP FUNCTION IF EXISTS reject_aip_logic_publication_mutation()")
