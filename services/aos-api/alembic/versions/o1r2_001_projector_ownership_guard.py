"""O1-R2: enforce the single-projector compatibility-write boundary.

Revision ID: o1r2_001
Revises: o1r1_002
Create Date: 2026-08-09
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "o1r2_001"
down_revision: str | Sequence[str] | None = "o1r1_002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
      CREATE OR REPLACE FUNCTION enforce_ecom_projection_actor()
      RETURNS trigger LANGUAGE plpgsql AS $$
      DECLARE actor TEXT := current_setting('aos.projection_actor', true);
      DECLARE owned BOOLEAN := FALSE;
      BEGIN
        IF TG_TABLE_NAME = 'obj_instance' THEN
          owned := COALESCE(NEW.object_type, OLD.object_type) IN (
            'Shop','Product','ProductSku','Category','Order','OrderLine','Shipment',
            'CustomerLite','Weapp','SystemConfig','ProductReview','Payment'
          );
        ELSIF TG_TABLE_NAME = 'graph_edge' THEN
          owned := COALESCE(NEW.rel, OLD.rel) IN (
            'Order.lines','OrderLine.ofSku','OrderLine.ofProduct','ProductSku.ofProduct',
            'Product.inCategory','Shop.sellsProduct','Order.fulfilledBy','Order.placedByLite',
            'Shop.hasWeapp','Product.hasReview','ProductReview.ofSku',
            'ProductReview.byMember','Order.hasPayment','Order.fromWeapp'
          );
        END IF;
        IF owned AND actor IS DISTINCT FROM 'ecom-projector-v1' THEN
          RAISE EXCEPTION 'ECOM_PROJECTION_ACTOR_REQUIRED'
            USING ERRCODE = '42501';
        END IF;
        RETURN COALESCE(NEW, OLD);
      END $$;

      CREATE TRIGGER trg_obj_instance_ecom_projector
        BEFORE INSERT OR UPDATE OR DELETE ON obj_instance
        FOR EACH ROW EXECUTE FUNCTION enforce_ecom_projection_actor();
      CREATE TRIGGER trg_graph_edge_ecom_projector
        BEFORE INSERT OR UPDATE OR DELETE ON graph_edge
        FOR EACH ROW EXECUTE FUNCTION enforce_ecom_projection_actor();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_graph_edge_ecom_projector ON graph_edge;")
    op.execute("DROP TRIGGER IF EXISTS trg_obj_instance_ecom_projector ON obj_instance;")
    op.execute("DROP FUNCTION IF EXISTS enforce_ecom_projection_actor();")
