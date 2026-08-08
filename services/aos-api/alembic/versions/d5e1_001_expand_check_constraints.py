"""D5-E1: Expand ecom_object/ecom_link CHECK constraints for 12 OT + 14 Link types.

Revision ID: d5e1_001
Revises: o1a0_001
Create Date: 2026-08-09

Root cause: Original migration b7e2c4a92283 only allows 8 object types and 6 link
types in CHECK constraints. D4 added 4 new OTs (Weapp/SystemConfig/ProductReview/
Payment) and 8 new link types, but the DB constraints were never updated.

This migration:
1. Expands ecom_object CHECK to include all 12 OTs
2. Expands ecom_link link_type CHECK to include all 14 link types
3. Expands ck_ecom_link_endpoint_types to include all 14 endpoint type combinations
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "d5e1_001"
down_revision: str | Sequence[str] | None = "o1a0_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Expand ecom_object object_type CHECK (8 -> 12 OTs)
    op.execute("""
        ALTER TABLE ecom_object
          DROP CONSTRAINT IF EXISTS ecom_object_object_type_check;
    """)
    op.execute("""
        ALTER TABLE ecom_object
          ADD CONSTRAINT ecom_object_object_type_check CHECK (
            object_type IN (
              'Shop', 'Product', 'ProductSku', 'Category',
              'Order', 'OrderLine', 'Shipment', 'CustomerLite',
              'Weapp', 'SystemConfig', 'ProductReview', 'Payment'
            )
          );
    """)

    # 2. Expand ecom_link link_type CHECK (6 -> 14 link types)
    op.execute("""
        ALTER TABLE ecom_link
          DROP CONSTRAINT IF EXISTS ecom_link_link_type_check;
    """)
    op.execute("""
        ALTER TABLE ecom_link
          ADD CONSTRAINT ecom_link_link_type_check CHECK (
            link_type IN (
              'Order.lines', 'OrderLine.ofSku', 'OrderLine.ofProduct',
              'ProductSku.ofProduct', 'Product.inCategory', 'Shop.sellsProduct',
              'Order.fulfilledBy', 'Order.placedByLite',
              'Shop.hasWeapp', 'Product.hasReview',
              'ProductReview.ofSku', 'ProductReview.byMember',
              'Order.hasPayment', 'Order.fromWeapp'
            )
          );
    """)

    # 3. Expand ck_ecom_link_endpoint_types to include all 14 combinations
    op.execute("""
        ALTER TABLE ecom_link
          DROP CONSTRAINT IF EXISTS ck_ecom_link_endpoint_types;
    """)
    op.execute("""
        ALTER TABLE ecom_link
          ADD CONSTRAINT ck_ecom_link_endpoint_types CHECK (
            (link_type = 'Order.lines' AND source_object_type = 'Order' AND target_object_type = 'OrderLine')
            OR (link_type = 'OrderLine.ofSku' AND source_object_type = 'OrderLine' AND target_object_type = 'ProductSku')
            OR (link_type = 'OrderLine.ofProduct' AND source_object_type = 'OrderLine' AND target_object_type = 'Product')
            OR (link_type = 'ProductSku.ofProduct' AND source_object_type = 'ProductSku' AND target_object_type = 'Product')
            OR (link_type = 'Product.inCategory' AND source_object_type = 'Product' AND target_object_type = 'Category')
            OR (link_type = 'Shop.sellsProduct' AND source_object_type = 'Shop' AND target_object_type = 'Product')
            OR (link_type = 'Order.fulfilledBy' AND source_object_type = 'Order' AND target_object_type = 'Shipment')
            OR (link_type = 'Order.placedByLite' AND source_object_type = 'Order' AND target_object_type = 'CustomerLite')
            OR (link_type = 'Shop.hasWeapp' AND source_object_type = 'Shop' AND target_object_type = 'Weapp')
            OR (link_type = 'Product.hasReview' AND source_object_type = 'Product' AND target_object_type = 'ProductReview')
            OR (link_type = 'ProductReview.ofSku' AND source_object_type = 'ProductReview' AND target_object_type = 'ProductSku')
            OR (link_type = 'ProductReview.byMember' AND source_object_type = 'ProductReview' AND target_object_type = 'CustomerLite')
            OR (link_type = 'Order.hasPayment' AND source_object_type = 'Order' AND target_object_type = 'Payment')
            OR (link_type = 'Order.fromWeapp' AND source_object_type = 'Order' AND target_object_type = 'Weapp')
          );
    """)


def downgrade() -> None:
    # Revert to original 8 OT / 6 link type constraints
    op.execute("""
        ALTER TABLE ecom_object
          DROP CONSTRAINT IF EXISTS ecom_object_object_type_check;
        ALTER TABLE ecom_object
          ADD CONSTRAINT ecom_object_object_type_check CHECK (
            object_type IN ('Shop','Product','ProductSku','Category','Order','OrderLine','Shipment','CustomerLite')
          );
    """)

    op.execute("""
        ALTER TABLE ecom_link
          DROP CONSTRAINT IF EXISTS ecom_link_link_type_check;
        ALTER TABLE ecom_link
          ADD CONSTRAINT ecom_link_link_type_check CHECK (
            link_type IN (
              'Order.lines','OrderLine.ofSku','ProductSku.ofProduct',
              'Product.inCategory','Shop.sellsProduct','Order.fulfilledBy'
            )
          );
    """)

    op.execute("""
        ALTER TABLE ecom_link
          DROP CONSTRAINT IF EXISTS ck_ecom_link_endpoint_types;
        ALTER TABLE ecom_link
          ADD CONSTRAINT ck_ecom_link_endpoint_types CHECK (
            (link_type = 'Order.lines' AND source_object_type = 'Order' AND target_object_type = 'OrderLine')
            OR (link_type = 'OrderLine.ofSku' AND source_object_type = 'OrderLine' AND target_object_type = 'ProductSku')
            OR (link_type = 'ProductSku.ofProduct' AND source_object_type = 'ProductSku' AND target_object_type = 'Product')
            OR (link_type = 'Product.inCategory' AND source_object_type = 'Product' AND target_object_type = 'Category')
            OR (link_type = 'Shop.sellsProduct' AND source_object_type = 'Shop' AND target_object_type = 'Product')
            OR (link_type = 'Order.fulfilledBy' AND source_object_type = 'Order' AND target_object_type = 'Shipment')
          );
    """)
