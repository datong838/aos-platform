"""O1-A/P12 derived metric CAS, receipt and outbox contract.

Revision ID: o1p12_001
Revises: o1r3_001
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "o1p12_001"
down_revision: str | Sequence[str] | None = "o1r3_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE ecom_object
          ADD COLUMN IF NOT EXISTS derived_payload_hash CHAR(64);
        ALTER TABLE ecom_object
          DROP CONSTRAINT IF EXISTS chk_ecom_object_derived_payload_hash;
        ALTER TABLE ecom_object
          ADD CONSTRAINT chk_ecom_object_derived_payload_hash
          CHECK (derived_payload_hash IS NULL OR derived_payload_hash ~ '^[0-9a-f]{64}$');
    """)
    op.execute("""
        ALTER TABLE ecom_derived_receipt
          ADD COLUMN IF NOT EXISTS platform TEXT,
          ADD COLUMN IF NOT EXISTS shop_or_marketplace_id TEXT,
          ADD COLUMN IF NOT EXISTS stream TEXT,
          ADD COLUMN IF NOT EXISTS expected_revision BIGINT,
          ADD COLUMN IF NOT EXISTS resulting_revision BIGINT,
          ADD COLUMN IF NOT EXISTS actor TEXT,
          ADD COLUMN IF NOT EXISTS request_hash CHAR(64),
          ADD COLUMN IF NOT EXISTS result_json JSONB;

        UPDATE ecom_derived_receipt
           SET platform = COALESCE(platform, 'legacy'),
               shop_or_marketplace_id = COALESCE(shop_or_marketplace_id, 'legacy'),
               stream = COALESCE(stream, 'legacy'),
               expected_revision = COALESCE(expected_revision, GREATEST(derived_revision - 1, 0)),
               resulting_revision = COALESCE(resulting_revision, derived_revision),
               actor = COALESCE(actor, 'legacy-migration'),
               request_hash = COALESCE(request_hash, payload_hash),
               result_json = COALESCE(
                 result_json,
                 jsonb_build_object(
                   'updated', TRUE,
                   'replayed', FALSE,
                   'resulting_revision', derived_revision,
                   'input_revision', input_revision,
                   'payload_hash', payload_hash
                 )
               );

        ALTER TABLE ecom_derived_receipt
          ALTER COLUMN platform SET NOT NULL,
          ALTER COLUMN shop_or_marketplace_id SET NOT NULL,
          ALTER COLUMN stream SET NOT NULL,
          ALTER COLUMN expected_revision SET NOT NULL,
          ALTER COLUMN resulting_revision SET NOT NULL,
          ALTER COLUMN actor SET NOT NULL,
          ALTER COLUMN request_hash SET NOT NULL,
          ALTER COLUMN result_json SET NOT NULL;

        ALTER TABLE ecom_derived_receipt
          DROP CONSTRAINT IF EXISTS chk_ecom_derived_request_hash,
          DROP CONSTRAINT IF EXISTS chk_ecom_derived_revision_transition;
        ALTER TABLE ecom_derived_receipt
          ADD CONSTRAINT chk_ecom_derived_request_hash
            CHECK (request_hash ~ '^[0-9a-f]{64}$'),
          ADD CONSTRAINT chk_ecom_derived_revision_transition
            CHECK (resulting_revision IN (expected_revision, expected_revision + 1));

        CREATE UNIQUE INDEX IF NOT EXISTS uq_ecom_derived_receipt_command
          ON ecom_derived_receipt (
            org_id, project_id, platform, shop_or_marketplace_id, stream, idempotency_key
          );
    """)


def downgrade() -> None:
    op.execute("""
        DROP INDEX IF EXISTS uq_ecom_derived_receipt_command;
        ALTER TABLE ecom_derived_receipt
          DROP CONSTRAINT IF EXISTS chk_ecom_derived_revision_transition,
          DROP CONSTRAINT IF EXISTS chk_ecom_derived_request_hash,
          DROP COLUMN IF EXISTS result_json,
          DROP COLUMN IF EXISTS request_hash,
          DROP COLUMN IF EXISTS actor,
          DROP COLUMN IF EXISTS resulting_revision,
          DROP COLUMN IF EXISTS expected_revision,
          DROP COLUMN IF EXISTS stream,
          DROP COLUMN IF EXISTS shop_or_marketplace_id,
          DROP COLUMN IF EXISTS platform;
        ALTER TABLE ecom_object
          DROP CONSTRAINT IF EXISTS chk_ecom_object_derived_payload_hash,
          DROP COLUMN IF EXISTS derived_payload_hash;
    """)
