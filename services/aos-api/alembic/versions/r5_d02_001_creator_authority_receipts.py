"""Bind creator outreach and lifecycle authorities to persistent read receipts.

Revision ID: r5_d02_001
Revises: aip_p5_001
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "r5_d02_001"
down_revision: str | Sequence[str] | None = "aip_p5_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TABLES = (
    ("ecommerce_creator_batch_preparation_revision", "CreatorBatchPreparationRevision", "batchId"),
    ("ecommerce_creator_contract_revision", "CreatorContractRevision", "collaborationId"),
    ("ecommerce_creator_delivery_observation", "CreatorDeliveryObservation", "observationId"),
    ("ecommerce_creator_relationship_revision", "CreatorRelationshipRevision", "relationshipId"),
)


def upgrade() -> None:
    for table, resource_type, identity_key in TABLES:
        op.execute(f"ALTER TABLE {table} ADD COLUMN authority_receipt_id TEXT")
        op.execute(
            f"UPDATE {table} SET authority_receipt_id = 'creator-authority-' || "
            f"substr(encode(sha256(convert_to(org_id || ':' || project_id || ':' || "
            f"'{resource_type}' || ':' || (authority_data->>'{identity_key}') || ':' || "
            "revision::text || ':' || content_hash, 'UTF8')), 'hex'), 1, 40) "
            "WHERE authority_receipt_id IS NULL"
        )
        op.execute(f"ALTER TABLE {table} ALTER COLUMN authority_receipt_id SET NOT NULL")
        op.execute(
            f"CREATE UNIQUE INDEX {table}_authority_receipt_uq "
            f"ON {table}(org_id,project_id,authority_receipt_id)"
        )


def downgrade() -> None:
    for table, _resource_type, _identity_key in reversed(TABLES):
        op.execute(f"DROP INDEX {table}_authority_receipt_uq")
        op.execute(f"ALTER TABLE {table} DROP COLUMN authority_receipt_id")
