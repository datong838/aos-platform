"""Protect both old and new classifications during compatibility updates."""
from alembic import op
revision='a0v_010'
down_revision='a0v_009'
branch_labels=None
depends_on=None


def upgrade():
    op.execute("""
    CREATE OR REPLACE FUNCTION enforce_ecom_projection_actor()
    RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE actor TEXT := current_setting('aos.projection_actor',true);
    DECLARE old_kind TEXT;
    DECLARE new_kind TEXT;
    DECLARE protected_kinds TEXT[];
    BEGIN
      IF TG_TABLE_NAME='obj_instance' THEN
        protected_kinds := ARRAY['Shop','Product','ProductSku','Category','Order','OrderLine','Shipment',
          'CustomerLite','Weapp','SystemConfig','ProductReview','Payment'];
        IF TG_OP <> 'INSERT' THEN old_kind := OLD.object_type; END IF;
        IF TG_OP <> 'DELETE' THEN new_kind := NEW.object_type; END IF;
      ELSIF TG_TABLE_NAME='graph_edge' THEN
        protected_kinds := ARRAY['Order.lines','OrderLine.ofSku','OrderLine.ofProduct','ProductSku.ofProduct',
          'Product.inCategory','Shop.sellsProduct','Order.fulfilledBy','Order.placedByLite',
          'Shop.hasWeapp','Product.hasReview','ProductReview.ofSku','ProductReview.byMember',
          'Order.hasPayment','Order.fromWeapp'];
        IF TG_OP <> 'INSERT' THEN old_kind := OLD.rel; END IF;
        IF TG_OP <> 'DELETE' THEN new_kind := NEW.rel; END IF;
      END IF;
      IF (COALESCE(old_kind=ANY(protected_kinds),false) OR COALESCE(new_kind=ANY(protected_kinds),false))
         AND actor IS DISTINCT FROM 'ecom-projector-v1' THEN
        RAISE EXCEPTION 'ECOM_PROJECTION_ACTOR_REQUIRED' USING ERRCODE='42501';
      END IF;
      IF TG_OP='DELETE' THEN RETURN OLD; END IF;
      RETURN NEW;
    END $$;
    """)


def downgrade():
    raise RuntimeError('Forward-only projector guard fix: downgrade would restore a known write bypass')
