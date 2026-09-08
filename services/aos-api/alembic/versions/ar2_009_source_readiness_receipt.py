"""Retain content-addressed snapshots of existing source readiness evaluations."""
from alembic import op

revision = "ar2_009"
down_revision = "ar2_008"
branch_labels = depends_on = None


def upgrade():
    op.execute("""CREATE TABLE source_readiness_receipt(
      org_id TEXT NOT NULL,project_id TEXT NOT NULL,receipt_id TEXT NOT NULL,
      content_hash TEXT NOT NULL CHECK(content_hash ~ '^[0-9a-f]{64}$'),
      authority JSONB NOT NULL,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY(org_id,project_id,receipt_id),UNIQUE(org_id,project_id,content_hash),
      CHECK(receipt_id='readiness-'||content_hash))""")
    op.execute("ALTER TABLE source_readiness_receipt ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE source_readiness_receipt FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY source_readiness_receipt_tenant_ar2_009 ON source_readiness_receipt TO aos_runtime
      USING(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))
      WITH CHECK(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
    op.execute("REVOKE ALL ON source_readiness_receipt FROM PUBLIC,aos_runtime")
    op.execute("GRANT SELECT ON source_readiness_receipt TO aos_runtime")
    op.execute("""CREATE FUNCTION source_readiness_immutable_ar2_009() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$ BEGIN
      RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='readiness receipts are immutable'; END $$""")
    op.execute("CREATE TRIGGER source_readiness_immutable BEFORE UPDATE OR DELETE ON source_readiness_receipt FOR EACH ROW EXECUTE FUNCTION source_readiness_immutable_ar2_009()")
    op.execute("CREATE TRIGGER source_readiness_no_truncate BEFORE TRUNCATE ON source_readiness_receipt FOR EACH STATEMENT EXECUTE FUNCTION source_readiness_immutable_ar2_009()")
    op.execute(r"""CREATE FUNCTION source_readiness_snapshot_put_ar2_009(p_body JSONB,p_hash TEXT)
      RETURNS TABLE(authority JSONB,content_hash TEXT,replayed BOOLEAN)
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
      DECLARE v_org TEXT:=NULLIF(current_setting('aos.org_id',true),'');
        v_project TEXT:=NULLIF(current_setting('aos.project_id',true),'');
        v_digest TEXT; v_old RECORD; v_source JSONB; v_index INTEGER:=0;
        v_statuses TEXT[]:=ARRAY['ready','empty','degraded','unknown','stale','failed','blocked','forbidden'];
        v_rank INTEGER:=0;
        v_pipelines TEXT[]:=ARRAY['P01-shop-qyh','P02-product-qyh','P03-product-sku-qyh','P04-category-qyh',
          'P05-order-qyh','P06-order-line-qyh','P07-shipment-qyh','P08-customer-lite-qyh','P09-weapp-qyh',
          'P10-system-config-qyh','P11-product-review-qyh','P12-payment-qyh'];
      BEGIN
        v_digest:=encode(public.digest(convert_to(public.canonical_asset_registry_jsonb(p_body),'UTF8'),'sha256'),'hex');
        IF v_org IS NULL OR v_project IS NULL OR p_hash IS DISTINCT FROM v_digest
          OR jsonb_typeof(p_body) IS DISTINCT FROM 'object'
          OR NOT p_body ?& ARRAY['schemaVersion','tenant','checkedAt','cutoffAt','status','sources','receiptRef','investigation']
          OR p_body-ARRAY['schemaVersion','tenant','checkedAt','cutoffAt','status','sources','receiptRef','investigation']<>'{}'::jsonb
          OR p_body->>'schemaVersion' IS DISTINCT FROM 'aos.source-readiness/v1'
          OR p_body->'tenant' IS DISTINCT FROM jsonb_build_object('orgId',v_org,'projectId',v_project)
          OR p_body->'receiptRef' IS DISTINCT FROM 'null'::jsonb
          OR jsonb_typeof(p_body->'sources') IS DISTINCT FROM 'array'
          OR octet_length(public.canonical_asset_registry_jsonb(p_body))>2000000
          OR (p_body->>'checkedAt' ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}T([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]\.[0-9]{6}\+00:00$') IS NOT TRUE
          OR (p_body->>'cutoffAt' ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}T([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]\.[0-9]{6}\+00:00$') IS NOT TRUE
        THEN RAISE EXCEPTION USING ERRCODE='SR001',MESSAGE='invalid canonical readiness snapshot'; END IF;
        IF jsonb_array_length(p_body->'sources')<>12
        THEN RAISE EXCEPTION USING ERRCODE='SR001',MESSAGE='invalid canonical source set'; END IF;
        FOR v_source IN SELECT value FROM jsonb_array_elements(p_body->'sources') LOOP
          v_index:=v_index+1;
          IF jsonb_typeof(v_source) IS DISTINCT FROM 'object'
            OR v_source->>'schemaVersion' IS DISTINCT FROM 'aos.source-readiness/v1'
            OR v_source->'tenant' IS DISTINCT FROM p_body->'tenant'
            OR v_source->'checkedAt' IS DISTINCT FROM p_body->'checkedAt'
            OR v_source->>'pipelineId' IS DISTINCT FROM v_pipelines[v_index]
            OR array_position(v_statuses,v_source->>'status') IS NULL
          THEN RAISE EXCEPTION USING ERRCODE='SR001',MESSAGE='readiness source scope or identity drifted'; END IF;
          v_rank:=greatest(v_rank,array_position(v_statuses,v_source->>'status'));
        END LOOP;
        IF p_body->>'status' IS DISTINCT FROM v_statuses[v_rank]
        THEN RAISE EXCEPTION USING ERRCODE='SR001',MESSAGE='readiness aggregate status drifted'; END IF;
        PERFORM pg_advisory_xact_lock(hashtextextended(v_org||E'\x1f'||v_project||E'\x1f'||v_digest,0));
        SELECT r.* INTO v_old FROM source_readiness_receipt r
          WHERE r.org_id=v_org AND r.project_id=v_project AND r.content_hash=v_digest;
        IF FOUND THEN
          IF v_old.authority IS DISTINCT FROM p_body
          THEN RAISE EXCEPTION USING ERRCODE='SR002',MESSAGE='readiness snapshot content conflict'; END IF;
          RETURN QUERY SELECT v_old.authority,v_old.content_hash,TRUE; RETURN;
        END IF;
        INSERT INTO source_readiness_receipt(org_id,project_id,receipt_id,content_hash,authority)
          VALUES(v_org,v_project,'readiness-'||v_digest,v_digest,p_body);
        RETURN QUERY SELECT p_body,v_digest,FALSE;
      END $$""")
    op.execute("REVOKE ALL ON FUNCTION source_readiness_immutable_ar2_009() FROM PUBLIC")
    op.execute("REVOKE ALL ON FUNCTION source_readiness_snapshot_put_ar2_009(JSONB,TEXT) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION source_readiness_snapshot_put_ar2_009(JSONB,TEXT) TO aos_runtime")


def downgrade():
    op.execute("""DO $$ BEGIN IF EXISTS(SELECT 1 FROM source_readiness_receipt)
      THEN RAISE EXCEPTION 'cannot remove persisted source readiness receipts'; END IF; END $$""")
    op.execute("DROP FUNCTION source_readiness_snapshot_put_ar2_009(JSONB,TEXT)")
    op.execute("DROP TABLE source_readiness_receipt")
    op.execute("DROP FUNCTION source_readiness_immutable_ar2_009()")
