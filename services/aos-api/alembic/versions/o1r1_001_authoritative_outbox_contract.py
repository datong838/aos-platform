"""O1-R1: distinguish legacy projection receipts from authoritative Outbox events.

Revision ID: o1r1_001
Revises: d5e1_001
Create Date: 2026-08-09
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "o1r1_001"
down_revision: str | Sequence[str] | None = "d5e1_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE IF NOT EXISTS projection_input_revision_seq;")
    op.execute("""
        SELECT setval(
          'projection_input_revision_seq',
          GREATEST(COALESCE((SELECT max(input_revision) FROM projection_outbox), 0), 1),
          true
        );
    """)
    op.execute("""
        ALTER TABLE projection_outbox
          ADD COLUMN IF NOT EXISTS event_key CHAR(64),
          ADD COLUMN IF NOT EXISTS payload_hash CHAR(64),
          ADD COLUMN IF NOT EXISTS event_source TEXT,
          ADD COLUMN IF NOT EXISTS authority_tx_id CHAR(64);
    """)
    op.execute("""
        UPDATE projection_outbox
           SET event_key = COALESCE(
                 event_key,
                 md5('legacy-' || outbox_id::text) || md5(outbox_id::text || '-legacy')
               ),
               event_source = COALESCE(event_source, 'legacy_post_projection')
         WHERE event_key IS NULL OR event_source IS NULL;
    """)
    op.execute("""
        ALTER TABLE projection_outbox
          ALTER COLUMN event_key SET NOT NULL,
          ALTER COLUMN event_source SET NOT NULL,
          ADD CONSTRAINT chk_projection_outbox_event_source
            CHECK (event_source IN ('legacy_post_projection', 'authoritative_store')),
          ADD CONSTRAINT chk_projection_outbox_authority_fields
            CHECK (
              event_source <> 'authoritative_store'
              OR (
                payload_hash ~ '^[0-9a-f]{64}$'
                AND authority_tx_id ~ '^[0-9a-f]{64}$'
              )
            ),
          ADD CONSTRAINT chk_projection_outbox_workspace_alias
            CHECK (project_id = workspace_id),
          ADD CONSTRAINT fk_projection_outbox_workspace
            FOREIGN KEY (org_id, project_id)
            REFERENCES twa_workspace(org_id, project_id)
            ON DELETE RESTRICT
            NOT VALID;
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_projection_outbox_authoritative_event
          ON projection_outbox (org_id, project_id, event_key)
          WHERE event_source = 'authoritative_store';
        CREATE INDEX IF NOT EXISTS idx_projection_outbox_authority_pending
          ON projection_outbox (org_id, project_id, input_revision)
          WHERE event_source = 'authoritative_store' AND projected = FALSE;
    """)
    op.execute("""
        ALTER TABLE projection_outbox
          VALIDATE CONSTRAINT fk_projection_outbox_workspace;
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_projection_outbox_authority_pending;")
    op.execute("DROP INDEX IF EXISTS uq_projection_outbox_authoritative_event;")
    op.execute("""
        ALTER TABLE projection_outbox
          DROP CONSTRAINT IF EXISTS fk_projection_outbox_workspace,
          DROP CONSTRAINT IF EXISTS chk_projection_outbox_workspace_alias,
          DROP CONSTRAINT IF EXISTS chk_projection_outbox_authority_fields,
          DROP CONSTRAINT IF EXISTS chk_projection_outbox_event_source,
          DROP COLUMN IF EXISTS authority_tx_id,
          DROP COLUMN IF EXISTS event_source,
          DROP COLUMN IF EXISTS payload_hash,
          DROP COLUMN IF EXISTS event_key;
    """)
    op.execute("DROP SEQUENCE IF EXISTS projection_input_revision_seq;")
