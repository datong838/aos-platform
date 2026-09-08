"""Retain complete fulfillment authority, including original timezone and blockers."""
from alembic import op

revision = "ar2_008"
down_revision = "ar2_007"
branch_labels = depends_on = None


def upgrade():
    op.execute("ALTER TABLE data_fulfillment_receipt ADD COLUMN authority_data JSONB")
    op.execute(r"""CREATE FUNCTION fulfillment_strip_ar2_008(t TEXT) RETURNS TEXT
      LANGUAGE sql IMMUTABLE SET search_path=pg_catalog,public AS $$
      SELECT btrim(t,U&'\0009\000A\000B\000C\000D\001C\001D\001E\001F\0020\0085\00A0\1680\2000\2001\2002\2003\2004\2005\2006\2007\2008\2009\200A\2028\2029\202F\205F\3000') $$""")
    op.execute("REVOKE ALL ON FUNCTION fulfillment_strip_ar2_008(TEXT) FROM PUBLIC")
    op.execute(r"""CREATE FUNCTION fulfillment_exact_ref_ar2_008(r JSONB) RETURNS BOOLEAN
      LANGUAGE sql IMMUTABLE SET search_path=pg_catalog,public AS $$ SELECT coalesce(
        jsonb_typeof(r)='object'
        AND r ?& ARRAY['resourceType','resourceId','revision','contentHash','receiptId']
        AND r-ARRAY['resourceType','resourceId','revision','contentHash','receiptId']='{}'::jsonb
        AND jsonb_typeof(r->'resourceType')='string' AND length(r->>'resourceType') BETWEEN 1 AND 120
        AND r->>'resourceType'=fulfillment_strip_ar2_008(r->>'resourceType')
        AND jsonb_typeof(r->'resourceId')='string' AND length(r->>'resourceId') BETWEEN 1 AND 240
        AND r->>'resourceId'=fulfillment_strip_ar2_008(r->>'resourceId')
        AND jsonb_typeof(r->'contentHash')='string' AND r->>'contentHash' ~ '^sha256:[0-9a-f]{64}$'
        AND ((jsonb_typeof(r->'revision')='number' AND r->>'revision' ~ '^[1-9][0-9]*$')
          OR (jsonb_typeof(r->'revision')='string' AND length(r->>'revision') BETWEEN 1 AND 160
              AND r->>'revision'=fulfillment_strip_ar2_008(r->>'revision')))
        AND (r->'receiptId'='null'::jsonb OR (jsonb_typeof(r->'receiptId')='string'
              AND length(r->>'receiptId') BETWEEN 1 AND 240)),false) $$""")
    op.execute("REVOKE ALL ON FUNCTION fulfillment_exact_ref_ar2_008(JSONB) FROM PUBLIC")
    op.execute(r"""CREATE FUNCTION data_fulfillment_bind_ar2_008(
        p_authority JSONB,p_key TEXT,p_request_hash TEXT)
      RETURNS TABLE(bound_receipt_id TEXT,result_content_hash TEXT,replayed BOOLEAN)
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
      DECLARE v_org TEXT:=NULLIF(current_setting('aos.org_id',true),'');
        v_project TEXT:=NULLIF(current_setting('aos.project_id',true),'');
        v_old RECORD; v_head RECORD; v_hash TEXT;
      BEGIN
        v_hash := 'sha256:'||encode(public.digest(convert_to(
          public.canonical_asset_registry_jsonb(p_authority-'contentHash'),'UTF8'),'sha256'),'hex');
        IF v_org IS NULL OR v_project IS NULL
          OR jsonb_typeof(p_authority) IS DISTINCT FROM 'object'
          OR NOT p_authority ?& ARRAY['schemaVersion','tenant','fulfillmentId','receiptId',
            'requirementRef','status','artifactRefs','sourceReadinessRef','cutoffAt','fulfilledAt',
            'contentHash','createdBy','blockers']
          OR p_authority-ARRAY['schemaVersion','tenant','fulfillmentId','receiptId',
            'requirementRef','status','artifactRefs','sourceReadinessRef','cutoffAt','fulfilledAt',
            'contentHash','createdBy','blockers'] <> '{}'::jsonb
          OR p_authority->>'schemaVersion' IS DISTINCT FROM 'aos.data-fulfillment-authority-receipt/v1'
          OR p_authority->'tenant'->>'orgId' IS DISTINCT FROM v_org
          OR p_authority->'tenant'->>'projectId' IS DISTINCT FROM v_project
          OR (p_authority->'tenant')-ARRAY['orgId','projectId'] <> '{}'::jsonb
          OR jsonb_typeof(p_authority->'fulfillmentId') IS DISTINCT FROM 'string'
          OR jsonb_typeof(p_authority->'receiptId') IS DISTINCT FROM 'string'
          OR jsonb_typeof(p_authority->'createdBy') IS DISTINCT FROM 'string'
          OR (p_authority->>'cutoffAt' ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2} ([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](\.[0-9]{6})?[+-]([01][0-9]|2[0-3]):[0-5][0-9]$') IS NOT TRUE
          OR (p_authority->>'fulfilledAt' ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2} ([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](\.[0-9]{6})?[+-]([01][0-9]|2[0-3]):[0-5][0-9]$') IS NOT TRUE
          OR p_authority->>'cutoffAt' ~ '(\.000000[+-]|-00:00$)'
          OR p_authority->>'fulfilledAt' ~ '(\.000000[+-]|-00:00$)'
          OR coalesce(length(btrim(p_authority->>'fulfillmentId')),0) NOT BETWEEN 1 AND 200
          OR coalesce(length(btrim(p_authority->>'receiptId')),0) NOT BETWEEN 1 AND 200
          OR coalesce(length(btrim(p_authority->>'createdBy')),0) NOT BETWEEN 1 AND 200
          OR length(p_authority->>'fulfillmentId')>200
          OR length(p_authority->>'receiptId')>200
          OR length(p_authority->>'createdBy')>200
          OR p_authority->>'contentHash' IS DISTINCT FROM v_hash
          OR coalesce(length(btrim(p_key)),0) NOT BETWEEN 1 AND 200
          OR p_request_hash IS DISTINCT FROM encode(public.digest(convert_to(
            public.canonical_asset_registry_jsonb(jsonb_build_object('operation','fulfillment.bind',
              'receipt',p_authority)),'UTF8'),'sha256'),'hex')
          OR p_authority->'requirementRef'->>'resourceType' IS DISTINCT FROM 'DataRequirementRevision'
          OR p_authority->'sourceReadinessRef'->>'resourceType' IS DISTINCT FROM 'SourceReadinessEnvelope'
          OR fulfillment_exact_ref_ar2_008(p_authority->'requirementRef') IS NOT TRUE
          OR jsonb_typeof(p_authority->'requirementRef'->'revision') IS DISTINCT FROM 'number'
          OR fulfillment_exact_ref_ar2_008(p_authority->'sourceReadinessRef') IS NOT TRUE
          OR coalesce(length(p_authority->'sourceReadinessRef'->>'receiptId'),0)=0
          OR jsonb_typeof(p_authority->'artifactRefs') IS DISTINCT FROM 'array'
          OR jsonb_typeof(p_authority->'blockers') IS DISTINCT FROM 'array'
        THEN RAISE EXCEPTION USING ERRCODE='DF001',MESSAGE='invalid complete fulfillment authority'; END IF;
        IF EXISTS(SELECT 1 FROM jsonb_array_elements(p_authority->'artifactRefs') a
          WHERE a->>'resourceType' NOT IN ('DatasetRevision','DataProductRevision','OntologyHydrationRevision','EvidenceBundleRevision')
            OR fulfillment_exact_ref_ar2_008(a) IS NOT TRUE)
          OR (SELECT count(*)<>count(DISTINCT (a->>'resourceType',a->>'resourceId',a->>'revision',a->>'contentHash'))
              FROM jsonb_array_elements(p_authority->'artifactRefs') a)
        THEN RAISE EXCEPTION USING ERRCODE='DF001',MESSAGE='invalid fulfillment artifact references'; END IF;
        IF jsonb_array_length(p_authority->'artifactRefs')>200 OR jsonb_array_length(p_authority->'blockers')>50
          OR EXISTS(SELECT 1 FROM jsonb_array_elements(p_authority->'blockers') b WHERE
            jsonb_typeof(b) IS DISTINCT FROM 'object'
            OR b-ARRAY['code','severity','dependency','requiredAction'] <> '{}'::jsonb
            OR jsonb_typeof(b->'code') IS DISTINCT FROM 'string'
            OR jsonb_typeof(b->'severity') IS DISTINCT FROM 'string'
            OR jsonb_typeof(b->'dependency') IS DISTINCT FROM 'string'
            OR jsonb_typeof(b->'requiredAction') IS DISTINCT FROM 'string'
            OR (b->>'code' ~ '^[A-Z][A-Z0-9_]{1,119}$') IS NOT TRUE
            OR (b->>'severity' IN ('warning','blocking')) IS NOT TRUE
            OR coalesce(length(b->>'dependency'),0) NOT BETWEEN 1 AND 160
            OR coalesce(length(b->>'requiredAction'),0) NOT BETWEEN 1 AND 500)
        THEN RAISE EXCEPTION USING ERRCODE='DF001',MESSAGE='invalid fulfillment blockers'; END IF;
        IF (p_authority->>'status'='fulfilled' AND
              (jsonb_array_length(p_authority->'artifactRefs')=0 OR jsonb_array_length(p_authority->'blockers')<>0))
           OR (p_authority->>'status'<>'fulfilled' AND jsonb_array_length(p_authority->'blockers')=0)
        THEN RAISE EXCEPTION USING ERRCODE='DF001',MESSAGE='invalid fulfillment result shape'; END IF;
        PERFORM pg_advisory_xact_lock(hashtextextended(concat_ws(':',v_org,v_project,'fulfillment.bind',p_key),0));
        SELECT * INTO v_old FROM data_fulfillment_receipt
         WHERE org_id=v_org AND project_id=v_project AND operation='fulfillment.bind' AND idempotency_key=p_key;
        IF FOUND THEN
          IF v_old.request_hash IS DISTINCT FROM p_request_hash
             OR v_old.authority_data IS DISTINCT FROM p_authority
          THEN RAISE EXCEPTION USING ERRCODE='DF002',MESSAGE='fulfillment idempotency conflict'; END IF;
          RETURN QUERY SELECT v_old.receipt_id,btrim(v_old.content_hash),TRUE; RETURN;
        END IF;
        SELECT current_revision,current_content_hash INTO v_head FROM data_requirement_head
          WHERE org_id=v_org AND project_id=v_project
            AND requirement_id=p_authority->'requirementRef'->>'resourceId' FOR SHARE;
        IF NOT FOUND
          OR v_head.current_revision IS DISTINCT FROM (p_authority->'requirementRef'->>'revision')::bigint
          OR btrim(v_head.current_content_hash) IS DISTINCT FROM substring(p_authority->'requirementRef'->>'contentHash' from 8)
        THEN RAISE EXCEPTION USING ERRCODE='DF001',MESSAGE='requirement exact ref is not current'; END IF;
        INSERT INTO data_fulfillment_receipt(org_id,project_id,fulfillment_id,receipt_id,
          requirement_id,requirement_revision,status,artifact_refs,source_readiness_ref,
          cutoff_at,fulfilled_at,content_hash,created_by,operation,idempotency_key,request_hash,authority_data)
        VALUES(v_org,v_project,p_authority->>'fulfillmentId',p_authority->>'receiptId',
          p_authority->'requirementRef'->>'resourceId',(p_authority->'requirementRef'->>'revision')::bigint,
          p_authority->>'status',p_authority->'artifactRefs',p_authority->'sourceReadinessRef',
          (p_authority->>'cutoffAt')::timestamptz,(p_authority->>'fulfilledAt')::timestamptz,
          substring(v_hash from 8),p_authority->>'createdBy','fulfillment.bind',p_key,p_request_hash,p_authority);
        RETURN QUERY SELECT p_authority->>'receiptId',substring(v_hash from 8),FALSE;
      END $$""")
    op.execute("REVOKE ALL ON FUNCTION data_fulfillment_bind_ar2_008(JSONB,TEXT,TEXT) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION data_fulfillment_bind_ar2_008(JSONB,TEXT,TEXT) TO aos_runtime")


def downgrade():
    op.execute("""DO $$ BEGIN IF EXISTS(SELECT 1 FROM data_fulfillment_receipt WHERE authority_data IS NOT NULL)
      THEN RAISE EXCEPTION 'cannot discard complete fulfillment authority'; END IF; END $$""")
    op.execute("DROP FUNCTION data_fulfillment_bind_ar2_008(JSONB,TEXT,TEXT)")
    op.execute("DROP FUNCTION fulfillment_exact_ref_ar2_008(JSONB)")
    op.execute("DROP FUNCTION fulfillment_strip_ar2_008(TEXT)")
    op.execute("ALTER TABLE data_fulfillment_receipt DROP COLUMN authority_data")
