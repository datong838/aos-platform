"""O1-D versioned and reversible canonical alias migration contract.

Revision ID: o1d_001
Revises: o1p12_001
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "o1d_001"
down_revision: str | Sequence[str] | None = "o1p12_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
      ALTER TABLE ecom_alias_migration
        ADD COLUMN IF NOT EXISTS run_id UUID NOT NULL DEFAULT gen_random_uuid(),
        ADD COLUMN IF NOT EXISTS evidence_ref TEXT NOT NULL DEFAULT 'legacy:pre-o1d',
        ADD COLUMN IF NOT EXISTS canonical_props_hash CHAR(64),
        ADD COLUMN IF NOT EXISTS classification TEXT NOT NULL DEFAULT 'UNRESOLVED',
        ADD COLUMN IF NOT EXISTS state TEXT NOT NULL DEFAULT 'inventoried',
        ADD COLUMN IF NOT EXISTS legacy_snapshot JSONB,
        ADD COLUMN IF NOT EXISTS verification_cycle INTEGER NOT NULL DEFAULT 0,
        ADD COLUMN IF NOT EXISTS verified_at TIMESTAMPTZ,
        ADD COLUMN IF NOT EXISTS cleanup_approved_by TEXT,
        ADD COLUMN IF NOT EXISTS cleanup_approved_at TIMESTAMPTZ,
        ADD COLUMN IF NOT EXISTS cleaned_at TIMESTAMPTZ;

      ALTER TABLE ecom_alias_migration
        ADD CONSTRAINT ck_o1d_project_workspace_same CHECK (project_id=workspace_id),
        ADD CONSTRAINT ck_o1d_props_hash CHECK (props_hash ~ '^[0-9a-f]{64}$'),
        ADD CONSTRAINT ck_o1d_canonical_hash CHECK (
          canonical_props_hash IS NULL OR canonical_props_hash ~ '^[0-9a-f]{64}$'
        ),
        ADD CONSTRAINT ck_o1d_classification CHECK (
          classification IN ('COPY','ALREADY_EQUAL','HASH_CONFLICT','UNRESOLVED')
        ),
        ADD CONSTRAINT ck_o1d_state CHECK (
          state IN ('inventoried','verified','quarantined','cleanup_approved','cleaned','restored')
        ),
        ADD CONSTRAINT ck_o1d_cycle_nonnegative CHECK (verification_cycle>=0),
        ADD CONSTRAINT fk_o1d_workspace FOREIGN KEY (org_id,project_id)
          REFERENCES twa_workspace(org_id,project_id) ON DELETE RESTRICT;

      CREATE UNIQUE INDEX uq_o1d_run_alias
        ON ecom_alias_migration(org_id,project_id,run_id,alias_entry_id);
      CREATE INDEX idx_o1d_run_state
        ON ecom_alias_migration(org_id,project_id,run_id,state);
    """)


def downgrade() -> None:
    op.execute("""
      DROP INDEX IF EXISTS idx_o1d_run_state;
      DROP INDEX IF EXISTS uq_o1d_run_alias;
      ALTER TABLE ecom_alias_migration
        DROP CONSTRAINT IF EXISTS fk_o1d_workspace,
        DROP CONSTRAINT IF EXISTS ck_o1d_cycle_nonnegative,
        DROP CONSTRAINT IF EXISTS ck_o1d_state,
        DROP CONSTRAINT IF EXISTS ck_o1d_classification,
        DROP CONSTRAINT IF EXISTS ck_o1d_canonical_hash,
        DROP CONSTRAINT IF EXISTS ck_o1d_props_hash,
        DROP CONSTRAINT IF EXISTS ck_o1d_project_workspace_same,
        DROP COLUMN IF EXISTS cleaned_at,
        DROP COLUMN IF EXISTS cleanup_approved_at,
        DROP COLUMN IF EXISTS cleanup_approved_by,
        DROP COLUMN IF EXISTS verified_at,
        DROP COLUMN IF EXISTS verification_cycle,
        DROP COLUMN IF EXISTS legacy_snapshot,
        DROP COLUMN IF EXISTS state,
        DROP COLUMN IF EXISTS classification,
        DROP COLUMN IF EXISTS canonical_props_hash,
        DROP COLUMN IF EXISTS evidence_ref,
        DROP COLUMN IF EXISTS run_id;
    """)
