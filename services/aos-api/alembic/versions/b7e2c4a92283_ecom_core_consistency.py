"""Add tenant-safe ecommerce core objects, links and sync state.

Revision ID: b7e2c4a92283
Revises: 228ec02oauth
Create Date: 2026-07-31
"""
from typing import Sequence, Union

from alembic import op


revision: str = "b7e2c4a92283"
down_revision: Union[str, Sequence[str], None] = "228ec02oauth"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    statements = (
        """
        CREATE TABLE ecom_object (
          org_id TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          platform TEXT NOT NULL,
          shop_or_marketplace_id TEXT NOT NULL,
          object_type TEXT NOT NULL,
          external_id TEXT NOT NULL,
          properties JSONB NOT NULL DEFAULT '{}'::jsonb,
          source_updated_at TIMESTAMPTZ NOT NULL,
          source_timezone TEXT NOT NULL,
          canonical_status TEXT NOT NULL,
          raw_status TEXT NOT NULL DEFAULT '',
          schema_version INTEGER NOT NULL DEFAULT 1 CHECK (schema_version > 0),
          payload_hash CHAR(64) NOT NULL,
          deleted_at TIMESTAMPTZ,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (
            org_id, workspace_id, platform, shop_or_marketplace_id,
            object_type, external_id
          ),
          CHECK (org_id = BTRIM(org_id) AND org_id <> ''),
          CHECK (workspace_id = BTRIM(workspace_id) AND workspace_id <> ''),
          CHECK (platform = LOWER(BTRIM(platform)) AND platform <> ''),
          CHECK (shop_or_marketplace_id = BTRIM(shop_or_marketplace_id) AND shop_or_marketplace_id <> ''),
          CHECK (external_id = BTRIM(external_id) AND external_id <> ''),
          CHECK (object_type IN ('Shop','Product','ProductSku','Category','Order','OrderLine','Shipment'))
        )
        """,
        """
        CREATE INDEX idx_ecom_object_active_cursor
          ON ecom_object (
            org_id, workspace_id, platform, shop_or_marketplace_id,
            object_type, source_updated_at, external_id
          ) WHERE deleted_at IS NULL
        """,
        """
        CREATE TABLE ecom_link (
          org_id TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          link_type TEXT NOT NULL,
          source_platform TEXT NOT NULL,
          source_shop_or_marketplace_id TEXT NOT NULL,
          source_object_type TEXT NOT NULL,
          source_external_id TEXT NOT NULL,
          target_platform TEXT NOT NULL,
          target_shop_or_marketplace_id TEXT NOT NULL,
          target_object_type TEXT NOT NULL,
          target_external_id TEXT NOT NULL,
          properties JSONB NOT NULL DEFAULT '{}'::jsonb,
          source_updated_at TIMESTAMPTZ NOT NULL,
          payload_hash CHAR(64) NOT NULL,
          deleted_at TIMESTAMPTZ,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (
            org_id, workspace_id, link_type,
            source_platform, source_shop_or_marketplace_id, source_object_type, source_external_id,
            target_platform, target_shop_or_marketplace_id, target_object_type, target_external_id
          ),
          FOREIGN KEY (
            org_id, workspace_id, source_platform,
            source_shop_or_marketplace_id, source_object_type, source_external_id
          ) REFERENCES ecom_object (
            org_id, workspace_id, platform,
            shop_or_marketplace_id, object_type, external_id
          ) ON DELETE RESTRICT,
          FOREIGN KEY (
            org_id, workspace_id, target_platform,
            target_shop_or_marketplace_id, target_object_type, target_external_id
          ) REFERENCES ecom_object (
            org_id, workspace_id, platform,
            shop_or_marketplace_id, object_type, external_id
          ) ON DELETE RESTRICT,
          CHECK (link_type IN (
            'Order.lines','OrderLine.ofSku','ProductSku.ofProduct',
            'Product.inCategory','Shop.sellsProduct','Order.fulfilledBy'
          )),
          CONSTRAINT ck_ecom_link_same_shop CHECK (
            source_platform = target_platform AND
            source_shop_or_marketplace_id = target_shop_or_marketplace_id
          ),
          CONSTRAINT ck_ecom_link_endpoint_types CHECK (
            (link_type = 'Order.lines' AND source_object_type = 'Order' AND target_object_type = 'OrderLine') OR
            (link_type = 'OrderLine.ofSku' AND source_object_type = 'OrderLine' AND target_object_type = 'ProductSku') OR
            (link_type = 'ProductSku.ofProduct' AND source_object_type = 'ProductSku' AND target_object_type = 'Product') OR
            (link_type = 'Product.inCategory' AND source_object_type = 'Product' AND target_object_type = 'Category') OR
            (link_type = 'Shop.sellsProduct' AND source_object_type = 'Shop' AND target_object_type = 'Product') OR
            (link_type = 'Order.fulfilledBy' AND source_object_type = 'Order' AND target_object_type = 'Shipment')
          )
        )
        """,
        """
        CREATE INDEX idx_ecom_link_active_source
          ON ecom_link (
            org_id, workspace_id, source_platform,
            source_shop_or_marketplace_id, source_object_type, source_external_id
          ) WHERE deleted_at IS NULL
        """,
        """
        CREATE INDEX idx_ecom_link_active_target
          ON ecom_link (
            org_id, workspace_id, target_platform,
            target_shop_or_marketplace_id, target_object_type, target_external_id
          ) WHERE deleted_at IS NULL
        """,
        """
        CREATE TABLE ecom_sync_checkpoint (
          org_id TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          platform TEXT NOT NULL,
          shop_or_marketplace_id TEXT NOT NULL,
          stream TEXT NOT NULL,
          cursor_updated_at TIMESTAMPTZ NOT NULL,
          cursor_external_id TEXT NOT NULL,
          version BIGINT NOT NULL CHECK (version > 0),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id, workspace_id, platform, shop_or_marketplace_id, stream),
          CHECK (platform = LOWER(BTRIM(platform)) AND platform <> ''),
          CHECK (cursor_external_id = BTRIM(cursor_external_id) AND cursor_external_id <> '')
        )
        """,
        """
        CREATE TABLE ecom_ingest_receipt (
          org_id TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          platform TEXT NOT NULL,
          shop_or_marketplace_id TEXT NOT NULL,
          stream TEXT NOT NULL,
          idempotency_key TEXT NOT NULL,
          request_hash CHAR(64) NOT NULL,
          result JSONB NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (
            org_id, workspace_id, platform, shop_or_marketplace_id,
            stream, idempotency_key
          ),
          CHECK (idempotency_key = BTRIM(idempotency_key) AND idempotency_key <> '')
        )
        """,
    )
    for statement in statements:
        op.execute(statement)


def downgrade() -> None:
    """Drop only the isolated ecom tables; legacy Ontology data is untouched."""
    for statement in (
        "DROP TABLE IF EXISTS ecom_ingest_receipt",
        "DROP TABLE IF EXISTS ecom_sync_checkpoint",
        "DROP TABLE IF EXISTS ecom_link",
        "DROP TABLE IF EXISTS ecom_object",
    ):
        op.execute(statement)
