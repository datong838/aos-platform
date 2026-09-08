"""Reject absent description identity fields, including direct SQL callers."""

from alembic import op

revision = "ar2_007"
down_revision = "ar2_006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""ALTER TABLE ecommerce_investigation_description_receipt
        ADD CONSTRAINT description_required_identity CHECK (
            authority->>'schemaVersion' IS NOT DISTINCT FROM
                'aos.ecommerce.investigation-description/v1'
            AND authority->>'receiptId' IS NOT DISTINCT FROM receipt_id::text
        )""")
    op.execute("""DO $$ DECLARE definition TEXT; BEGIN
        SELECT pg_get_functiondef(
          'ecommerce_investigation_description_put_ar2_006(text,text,uuid,text,jsonb,timestamptz)'::regprocedure
        ) INTO definition;
        definition := replace(definition,
          'p_authority->>''schemaVersion''<>',
          'p_authority->>''schemaVersion'' IS DISTINCT FROM ');
        definition := replace(definition,
          'p_authority->>''receiptId''<>',
          'p_authority->>''receiptId'' IS DISTINCT FROM ');
        EXECUTE definition;
    END $$""")
    op.execute("""CREATE FUNCTION guard_investigation_description_identity_ar2_007()
        RETURNS TRIGGER LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
        DECLARE identity_bytes BYTEA; expected_id UUID; expected_hash TEXT;
        BEGIN
          identity_bytes := public.digest(
            uuid_send('2da59db9-653d-4995-8516-a1bd6fd08dc8'::uuid) ||
            convert_to(NEW.org_id || chr(31) || NEW.project_id || chr(31) ||
              btrim(NEW.idempotency_key), 'UTF8'), 'sha1');
          identity_bytes := set_byte(identity_bytes,6,
            (get_byte(identity_bytes,6) & 15) | 80);
          identity_bytes := set_byte(identity_bytes,8,
            (get_byte(identity_bytes,8) & 63) | 128);
          expected_id := encode(substring(identity_bytes from 1 for 16),'hex')::uuid;
          expected_hash := 'sha256:' || encode(public.digest(convert_to(
            public.canonical_asset_registry_jsonb(NEW.authority),'UTF8'),'sha256'),'hex');
          IF NEW.receipt_id IS DISTINCT FROM expected_id
             OR NEW.content_hash IS DISTINCT FROM expected_hash
             OR NEW.request_hash IS DISTINCT FROM ('sha256:' || encode(public.digest(
               convert_to(public.canonical_asset_registry_jsonb(jsonb_build_object(
                 'idempotencyKey',NEW.idempotency_key,
                 'analysisType',NEW.authority->>'analysisType')),'UTF8'),'sha256'),'hex'))
          THEN RAISE EXCEPTION USING ERRCODE='22023',
            MESSAGE='invalid investigation description identity or hash'; END IF;
          RETURN NEW;
        END $$""")
    op.execute("""CREATE TRIGGER investigation_description_identity_ar2_007
        BEFORE INSERT OR UPDATE ON ecommerce_investigation_description_receipt
        FOR EACH ROW EXECUTE FUNCTION guard_investigation_description_identity_ar2_007()""")
    # Validate pre-existing receipts as well; the migration cannot bless poisoned keys.
    op.execute("""UPDATE ecommerce_investigation_description_receipt
        SET content_hash=content_hash""")


def downgrade() -> None:
    raise RuntimeError("description identity safety constraint cannot be removed")
