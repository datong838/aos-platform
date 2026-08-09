"""O1-D make the manifest run part of the immutable sidecar identity.

Revision ID: o1d_002
Revises: o1d_001
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "o1d_002"
down_revision: str | Sequence[str] | None = "o1d_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
      DROP INDEX IF EXISTS uq_o1d_run_alias;
      ALTER TABLE ecom_alias_migration
        DROP CONSTRAINT ecom_alias_migration_pkey,
        ADD CONSTRAINT ecom_alias_migration_pkey
          PRIMARY KEY (org_id,project_id,run_id,alias_entry_id);
      CREATE INDEX idx_o1d_alias_history
        ON ecom_alias_migration(org_id,project_id,alias_entry_id,created_at DESC);
    """)


def downgrade() -> None:
    op.execute("""
      DROP INDEX IF EXISTS idx_o1d_alias_history;
      ALTER TABLE ecom_alias_migration
        DROP CONSTRAINT ecom_alias_migration_pkey,
        ADD CONSTRAINT ecom_alias_migration_pkey
          PRIMARY KEY (org_id,project_id,alias_entry_id);
      CREATE UNIQUE INDEX uq_o1d_run_alias
        ON ecom_alias_migration(org_id,project_id,run_id,alias_entry_id);
    """)
