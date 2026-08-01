"""Add immutable tenant-scoped AIP Logic dry-run history.

Revision ID: 228logicrun
Revises: 228logicgraph
Create Date: 2026-08-01
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "228logicrun"
down_revision: str | Sequence[str] | None = "228logicgraph"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE aip_logic_graph_runs (
          org_id TEXT NOT NULL,
          project_id TEXT NOT NULL,
          graph_id TEXT NOT NULL,
          run_id TEXT NOT NULL,
          evaluated_revision BIGINT NOT NULL CHECK (evaluated_revision >= 1),
          graph_hash TEXT NOT NULL CHECK (length(graph_hash) = 64),
          mode TEXT NOT NULL DEFAULT 'dry_run' CHECK (mode = 'dry_run'),
          status TEXT NOT NULL CHECK (status IN ('running','succeeded','failed')),
          production_written BOOLEAN NOT NULL DEFAULT FALSE CHECK (production_written = FALSE),
          started_at TIMESTAMPTZ NOT NULL,
          finished_at TIMESTAMPTZ,
          elapsed_ms BIGINT CHECK (elapsed_ms IS NULL OR elapsed_ms >= 0),
          total_tokens BIGINT CHECK (total_tokens IS NULL OR total_tokens >= 0),
          inputs_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
          output_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
          proposed_edits JSONB NOT NULL DEFAULT '[]'::jsonb,
          error JSONB,
          actor TEXT NOT NULL,
          idempotency_key TEXT,
          request_hash TEXT NOT NULL CHECK (length(request_hash) = 64),
          PRIMARY KEY (org_id, project_id, graph_id, run_id),
          FOREIGN KEY (org_id, project_id, graph_id, evaluated_revision)
            REFERENCES aip_logic_graph_revision (org_id, project_id, graph_id, revision),
          UNIQUE (org_id, project_id, graph_id, idempotency_key)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE aip_logic_graph_run_nodes (
          org_id TEXT NOT NULL,
          project_id TEXT NOT NULL,
          graph_id TEXT NOT NULL,
          run_id TEXT NOT NULL,
          node_id TEXT NOT NULL,
          topo_index INTEGER NOT NULL CHECK (topo_index >= 0),
          kind TEXT NOT NULL,
          status TEXT NOT NULL CHECK (status IN ('executed','skipped','failed','canceled')),
          started_at TIMESTAMPTZ,
          finished_at TIMESTAMPTZ,
          elapsed_ms BIGINT CHECK (elapsed_ms IS NULL OR elapsed_ms >= 0),
          summary TEXT NOT NULL,
          input_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
          output_summary JSONB,
          usage JSONB,
          tool_call JSONB,
          selected_branch_path TEXT,
          proposed_edits JSONB NOT NULL DEFAULT '[]'::jsonb,
          error JSONB,
          truncated BOOLEAN NOT NULL DEFAULT FALSE,
          PRIMARY KEY (org_id, project_id, graph_id, run_id, node_id),
          FOREIGN KEY (org_id, project_id, graph_id, run_id)
            REFERENCES aip_logic_graph_runs (org_id, project_id, graph_id, run_id)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX idx_aip_logic_graph_runs_history
          ON aip_logic_graph_runs
             (org_id, project_id, graph_id, started_at DESC, run_id DESC)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS aip_logic_graph_run_nodes")
    op.execute("DROP TABLE IF EXISTS aip_logic_graph_runs")
