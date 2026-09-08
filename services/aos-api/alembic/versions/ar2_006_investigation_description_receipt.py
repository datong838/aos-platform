"""Persist exact read-only investigation description receipts."""

from alembic import op


revision = "ar2_006"
down_revision = "ar2_005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """CREATE TABLE ecommerce_investigation_description_receipt (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          idempotency_key TEXT NOT NULL CHECK(length(btrim(idempotency_key)) BETWEEN 1 AND 200),
          request_hash TEXT NOT NULL CHECK(request_hash ~ '^sha256:[0-9a-f]{64}$'),
          receipt_id UUID NOT NULL,
          content_hash TEXT NOT NULL CHECK(content_hash ~ '^sha256:[0-9a-f]{64}$'),
          authority JSONB NOT NULL CHECK(
            jsonb_typeof(authority)='object'
            AND authority->>'schemaVersion'='aos.ecommerce.investigation-description/v1'
            AND authority->>'receiptId'=receipt_id::text
            AND coalesce(length(btrim(authority->>'analysisType')),0) BETWEEN 1 AND 120
            AND coalesce(length(btrim(authority->>'businessTitle')),0) BETWEEN 1 AND 240
            AND jsonb_typeof(authority->'caseCreatable') IS NOT DISTINCT FROM 'boolean'
            AND jsonb_typeof(authority->'selection') IS NOT DISTINCT FROM 'object'
            AND jsonb_typeof(authority->'sourceReadiness') IS NOT DISTINCT FROM 'object'
            AND coalesce(length(btrim(authority->>'checkedAt')),0)>0),
          created_at TIMESTAMPTZ NOT NULL,
          PRIMARY KEY(org_id,project_id,idempotency_key),
          UNIQUE(org_id,project_id,receipt_id)
        )"""
    )
    op.execute("ALTER TABLE ecommerce_investigation_description_receipt ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE ecommerce_investigation_description_receipt FORCE ROW LEVEL SECURITY")
    op.execute(
        """CREATE POLICY tenant_scope_investigation_description_ar2_006
          ON ecommerce_investigation_description_receipt TO aos_runtime
          USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
            AND project_id=NULLIF(current_setting('aos.project_id',true),''))
          WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
            AND project_id=NULLIF(current_setting('aos.project_id',true),''))"""
    )
    op.execute("REVOKE ALL ON ecommerce_investigation_description_receipt FROM PUBLIC")
    op.execute("GRANT SELECT ON ecommerce_investigation_description_receipt TO aos_runtime")
    op.execute(
        """CREATE FUNCTION ecommerce_investigation_description_put_ar2_006(
          p_idempotency_key TEXT,p_request_hash TEXT,p_receipt_id UUID,
          p_content_hash TEXT,p_authority JSONB,p_created_at TIMESTAMPTZ
        ) RETURNS TABLE(authority JSONB,replayed BOOLEAN)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
        DECLARE v_org TEXT:=NULLIF(current_setting('aos.org_id',true),'');
          v_project TEXT:=NULLIF(current_setting('aos.project_id',true),'');
          v_existing RECORD;
        BEGIN
          IF coalesce(v_org,'')='' OR coalesce(v_project,'')=''
             OR length(btrim(coalesce(p_idempotency_key,''))) NOT BETWEEN 1 AND 200
             OR p_request_hash !~ '^sha256:[0-9a-f]{64}$'
             OR p_receipt_id IS NULL OR p_content_hash !~ '^sha256:[0-9a-f]{64}$'
             OR jsonb_typeof(p_authority)<>'object'
             OR p_authority->>'schemaVersion'<>'aos.ecommerce.investigation-description/v1'
             OR p_authority->>'receiptId'<>p_receipt_id::text
             OR coalesce(length(btrim(p_authority->>'analysisType')),0) NOT BETWEEN 1 AND 120
             OR coalesce(length(btrim(p_authority->>'businessTitle')),0) NOT BETWEEN 1 AND 240
             OR jsonb_typeof(p_authority->'caseCreatable') IS DISTINCT FROM 'boolean'
             OR jsonb_typeof(p_authority->'selection') IS DISTINCT FROM 'object'
             OR jsonb_typeof(p_authority->'sourceReadiness') IS DISTINCT FROM 'object'
             OR coalesce(length(btrim(p_authority->>'checkedAt')),0)<1
             OR p_created_at IS NULL
          THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='invalid investigation description Receipt'; END IF;
          PERFORM pg_advisory_xact_lock(hashtextextended(
            v_org||E'\x1f'||v_project||E'\x1f'||btrim(p_idempotency_key),0));
          SELECT * INTO v_existing FROM ecommerce_investigation_description_receipt
           WHERE org_id=v_org AND project_id=v_project
             AND idempotency_key=btrim(p_idempotency_key) FOR UPDATE;
          IF FOUND THEN
            IF v_existing.request_hash<>p_request_hash
               OR v_existing.receipt_id<>p_receipt_id
               OR v_existing.content_hash<>p_content_hash
               OR v_existing.authority IS DISTINCT FROM p_authority
            THEN RAISE EXCEPTION USING ERRCODE='23505',MESSAGE='investigation description Receipt drifted'; END IF;
            RETURN QUERY SELECT v_existing.authority,TRUE; RETURN;
          END IF;
          INSERT INTO ecommerce_investigation_description_receipt(
            org_id,project_id,idempotency_key,request_hash,receipt_id,content_hash,authority,created_at)
          VALUES(v_org,v_project,btrim(p_idempotency_key),p_request_hash,p_receipt_id,
            p_content_hash,p_authority,p_created_at);
          RETURN QUERY SELECT p_authority,FALSE;
        END $$"""
    )
    op.execute(
        "REVOKE ALL ON FUNCTION ecommerce_investigation_description_put_ar2_006(TEXT,TEXT,UUID,TEXT,JSONB,TIMESTAMPTZ) FROM PUBLIC"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION ecommerce_investigation_description_put_ar2_006(TEXT,TEXT,UUID,TEXT,JSONB,TIMESTAMPTZ) TO aos_runtime"
    )


def downgrade() -> None:
    op.execute(
        """DO $$ BEGIN IF EXISTS(SELECT 1 FROM ecommerce_investigation_description_receipt LIMIT 1)
          THEN RAISE EXCEPTION 'investigation description Receipt is not empty'; END IF; END $$"""
    )
    op.execute(
        "DROP FUNCTION ecommerce_investigation_description_put_ar2_006(TEXT,TEXT,UUID,TEXT,JSONB,TIMESTAMPTZ)"
    )
    op.execute("DROP TABLE ecommerce_investigation_description_receipt")
