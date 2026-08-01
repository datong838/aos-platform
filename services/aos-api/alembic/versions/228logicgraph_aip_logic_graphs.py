"""Add tenant-scoped canonical AIP Logic graph snapshots and revisions.

Revision ID: 228logicgraph
Revises: 228ec03linkguard
Create Date: 2026-08-01
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "228logicgraph"
down_revision: Union[str, Sequence[str], None] = "228ec03linkguard"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE aip_logic_graph (
          org_id TEXT NOT NULL,
          project_id TEXT NOT NULL,
          graph_id TEXT NOT NULL,
          name TEXT NOT NULL,
          description TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL DEFAULT 'draft'
            CHECK (status IN ('draft', 'published', 'archived')),
          schema_version INTEGER NOT NULL DEFAULT 1 CHECK (schema_version >= 1),
          revision BIGINT NOT NULL DEFAULT 1 CHECK (revision >= 1),
          published_version BIGINT CHECK (published_version IS NULL OR published_version >= 1),
          graph_hash TEXT NOT NULL CHECK (length(graph_hash) = 64),
          payload JSONB NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          deleted_at TIMESTAMPTZ,
          PRIMARY KEY (org_id, project_id, graph_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE aip_logic_graph_revision (
          org_id TEXT NOT NULL,
          project_id TEXT NOT NULL,
          graph_id TEXT NOT NULL,
          revision BIGINT NOT NULL CHECK (revision >= 1),
          graph_hash TEXT NOT NULL CHECK (length(graph_hash) = 64),
          snapshot JSONB NOT NULL,
          actor TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id, project_id, graph_id, revision),
          FOREIGN KEY (org_id, project_id, graph_id)
            REFERENCES aip_logic_graph (org_id, project_id, graph_id)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX idx_aip_logic_graph_scope_updated
          ON aip_logic_graph (org_id, project_id, updated_at DESC)
          WHERE deleted_at IS NULL
        """
    )
    op.execute(
        """
        CREATE INDEX idx_aip_logic_graph_revision_created
          ON aip_logic_graph_revision
             (org_id, project_id, graph_id, created_at DESC)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS aip_logic_graph_revision")
    op.execute("DROP TABLE IF EXISTS aip_logic_graph")
