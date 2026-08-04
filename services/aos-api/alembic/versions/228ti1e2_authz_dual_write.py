"""TI-1 E2 authz dual-write evidence ledger.

Revision ID: 228ti1e2dual
Revises: 228ti1e1expand
Create Date: 2026-08-04
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "228ti1e2dual"
down_revision: str | Sequence[str] | None = "228ti1e1expand"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE tenant_dual_write_ledger (
          org_id TEXT NOT NULL,
          project_id TEXT NOT NULL,
          ledger_id BIGSERIAL NOT NULL,
          resource TEXT NOT NULL CHECK (resource = 'authz_tuple'),
          operation TEXT NOT NULL CHECK (operation = 'INSERT'),
          key_hash TEXT NOT NULL CHECK (
            key_hash ~ '^[0-9a-f]{64}$'
          ),
          observed_org_id TEXT,
          observed_project_id TEXT,
          status TEXT NOT NULL CHECK (status IN ('MATCH', 'MISMATCH')),
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id, project_id, ledger_id),
          FOREIGN KEY (org_id, project_id)
            REFERENCES twa_workspace (org_id, project_id),
          CHECK (
            (observed_org_id IS NULL AND observed_project_id IS NULL)
            OR (observed_org_id IS NOT NULL AND observed_project_id IS NOT NULL)
          )
        )
        """
    )
    op.execute(
        """
        CREATE INDEX idx_tenant_dual_write_ledger_status
          ON tenant_dual_write_ledger (
            org_id, project_id, resource, status, created_at DESC, ledger_id DESC
          )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS tenant_dual_write_ledger")
