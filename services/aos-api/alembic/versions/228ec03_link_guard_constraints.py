"""Add database guards for ecommerce Link tenant and endpoint shape.

Revision ID: 228ec03linkguard
Revises: b7e2c4a92283
Create Date: 2026-08-01
"""
from typing import Sequence, Union

from alembic import op


revision: str = "228ec03linkguard"
down_revision: Union[str, Sequence[str], None] = "b7e2c4a92283"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE ecom_link
        ADD CONSTRAINT ck_ecom_link_same_shop CHECK (
          source_platform = target_platform AND
          source_shop_or_marketplace_id = target_shop_or_marketplace_id
        )
        """
    )
    op.execute(
        """
        ALTER TABLE ecom_link
        ADD CONSTRAINT ck_ecom_link_endpoint_types CHECK (
          (link_type = 'Order.lines' AND source_object_type = 'Order' AND target_object_type = 'OrderLine') OR
          (link_type = 'OrderLine.ofSku' AND source_object_type = 'OrderLine' AND target_object_type = 'ProductSku') OR
          (link_type = 'ProductSku.ofProduct' AND source_object_type = 'ProductSku' AND target_object_type = 'Product') OR
          (link_type = 'Product.inCategory' AND source_object_type = 'Product' AND target_object_type = 'Category') OR
          (link_type = 'Shop.sellsProduct' AND source_object_type = 'Shop' AND target_object_type = 'Product') OR
          (link_type = 'Order.fulfilledBy' AND source_object_type = 'Order' AND target_object_type = 'Shipment')
        )
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE ecom_link DROP CONSTRAINT IF EXISTS ck_ecom_link_endpoint_types"
    )
    op.execute(
        "ALTER TABLE ecom_link DROP CONSTRAINT IF EXISTS ck_ecom_link_same_shop"
    )
