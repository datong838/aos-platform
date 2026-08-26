"""Add ecommerce BusinessInvestigationCase draft authority. Revision ID: biw4_001."""

from collections.abc import Sequence

from alembic import op


revision: str = "biw4_001"
down_revision: str | Sequence[str] | None = "biw3_006"
branch_labels = depends_on = None
SIGNATURE = "(text,text,text,jsonb)"


def upgrade() -> None:
    op.execute("""CREATE FUNCTION guard_ecommerce_investigation_case_biw4_001() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN RAISE EXCEPTION 'ECOMMERCE_INVESTIGATION_CASE_IMMUTABLE' USING ERRCODE='55000';END $$""")
    op.execute("""CREATE FUNCTION ecommerce_investigation_exact_ref_valid_biw4_001(p_ref jsonb,p_type text)
      RETURNS boolean LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$ SELECT
        jsonb_typeof(p_ref)='object'
        AND p_ref-ARRAY['resourceType','resourceId','revision','contentHash','receiptId']='{}'::jsonb
        AND p_ref->>'resourceType'=p_type AND length(BTRIM(p_ref->>'resourceId')) BETWEEN 1 AND 240
        AND jsonb_typeof(p_ref->'revision')='number' AND p_ref->>'revision' ~ '^[1-9][0-9]*$'
        AND p_ref->>'contentHash' ~ '^sha256:[0-9a-f]{64}$'
        AND (NOT p_ref ? 'receiptId' OR p_ref->'receiptId'='null'::jsonb
          OR (jsonb_typeof(p_ref->'receiptId')='string' AND length(BTRIM(p_ref->>'receiptId')) BETWEEN 1 AND 240)) $$""")
    op.execute("""CREATE TABLE ecommerce_investigation_case_head(
      org_id TEXT NOT NULL,project_id TEXT NOT NULL,case_id TEXT NOT NULL,current_revision BIGINT NOT NULL,
      version BIGINT NOT NULL,lifecycle TEXT NOT NULL,analysis_type TEXT NOT NULL,
      channel_id TEXT NOT NULL,business_entity_id TEXT NOT NULL,updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY(org_id,project_id,case_id),CHECK(current_revision>=1),CHECK(version>=1),
      CHECK(lifecycle IN('DRAFT','ACTIVE','ARCHIVED','CLOSED')),
      CHECK(analysis_type IN('initial_store_analysis','weekly_business_review','experience_growth','creator_sales','product_structure')))""")
    op.execute("""CREATE TABLE ecommerce_investigation_case_revision(
      org_id TEXT NOT NULL,project_id TEXT NOT NULL,case_id TEXT NOT NULL,revision BIGINT NOT NULL,
      version BIGINT NOT NULL,prior_revision BIGINT,content_hash TEXT NOT NULL,lifecycle TEXT NOT NULL,
      analysis_type TEXT NOT NULL,channel_id TEXT NOT NULL,business_entity_id TEXT NOT NULL,
      entity_channel_binding_id TEXT NOT NULL,idempotency_key TEXT NOT NULL,request_hash TEXT NOT NULL,
      authority_data JSONB NOT NULL,created_by TEXT NOT NULL,created_at TIMESTAMPTZ NOT NULL,
      PRIMARY KEY(org_id,project_id,case_id,revision),UNIQUE(org_id,project_id,idempotency_key),
      CHECK(revision>=1),CHECK(version=revision),
      CHECK((revision=1 AND prior_revision IS NULL) OR (revision>1 AND prior_revision=revision-1)),
      CHECK(content_hash ~ '^sha256:[0-9a-f]{64}$'),CHECK(request_hash ~ '^sha256:[0-9a-f]{64}$'),
      CHECK(lifecycle IN('DRAFT','ACTIVE','ARCHIVED','CLOSED')),
      CHECK(analysis_type IN('initial_store_analysis','weekly_business_review','experience_growth','creator_sales','product_structure')),
      CHECK(jsonb_typeof(authority_data)='object'))""")
    op.execute("""CREATE TABLE ecommerce_investigation_case_command_receipt(
      org_id TEXT NOT NULL,project_id TEXT NOT NULL,receipt_id TEXT NOT NULL,operation TEXT NOT NULL,
      idempotency_key TEXT NOT NULL,request_hash TEXT NOT NULL,case_id TEXT NOT NULL,case_revision BIGINT NOT NULL,
      authority_data JSONB NOT NULL,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY(org_id,project_id,receipt_id),UNIQUE(org_id,project_id,operation,idempotency_key),
      FOREIGN KEY(org_id,project_id,case_id,case_revision)
        REFERENCES ecommerce_investigation_case_revision(org_id,project_id,case_id,revision),
      CHECK(operation='business_investigation_case.create_draft'),
      CHECK(request_hash ~ '^sha256:[0-9a-f]{64}$'),CHECK(jsonb_typeof(authority_data)='object'))""")
    for table in (
        "ecommerce_investigation_case_head",
        "ecommerce_investigation_case_revision",
        "ecommerce_investigation_case_command_receipt",
    ):
        if table != "ecommerce_investigation_case_head":
            op.execute(f"CREATE TRIGGER trg_{table}_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION guard_ecommerce_investigation_case_biw4_001()")
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""CREATE POLICY tenant_scope_{table}_biw4_001 ON {table} TO aos_runtime
          USING(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))
          WITH CHECK(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
        op.execute(f"GRANT SELECT ON {table} TO aos_runtime")
        op.execute(f"REVOKE INSERT,UPDATE,DELETE,TRUNCATE ON {table} FROM aos_runtime")

    op.execute("""CREATE FUNCTION ecommerce_investigation_case_create_biw4_001(
      p_case_id text,p_idempotency_key text,p_request_hash text,p_payload jsonb)
      RETURNS TABLE(authority_data jsonb,replayed boolean) LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
      DECLARE v_org text:=NULLIF(current_setting('aos.org_id',true),'');
        v_project text:=NULLIF(current_setting('aos.project_id',true),'');v_existing record;
      BEGIN
        SELECT r.authority_data,r.request_hash INTO v_existing FROM ecommerce_investigation_case_command_receipt r
          WHERE r.org_id=v_org AND r.project_id=v_project AND r.operation='business_investigation_case.create_draft'
            AND r.idempotency_key=p_idempotency_key;
        IF FOUND THEN
          IF v_existing.request_hash<>p_request_hash THEN RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='Case idempotency conflict';END IF;
          RETURN QUERY SELECT v_existing.authority_data,true;RETURN;
        END IF;
        IF v_org IS NULL OR v_project IS NULL OR p_case_id IS NULL OR length(BTRIM(p_case_id)) NOT BETWEEN 1 AND 200
          OR p_idempotency_key IS NULL OR length(BTRIM(p_idempotency_key)) NOT BETWEEN 1 AND 200 OR p_request_hash IS NULL
          OR p_payload#>>'{tenant,orgId}'<>v_org OR p_payload#>>'{tenant,projectId}'<>v_project
          OR p_payload->>'caseId'<>p_case_id OR p_payload->>'schemaVersion'<>'aos.ecommerce.business-investigation-case/v1'
          OR NOT (p_payload ?& ARRAY['schemaVersion','tenant','caseId','revision','version','contentHash','lifecycle','analysisType','title','purposeCode','channelRef','businessEntityRef','entityChannelBindingRef','investigationProfileRef','scopeRef','createdBy','createdAt'])
          OR (p_payload->>'revision')::bigint<>1 OR (p_payload->>'version')::bigint<>1
          OR (p_payload ? 'priorRef' AND p_payload->'priorRef'<>'null'::jsonb) OR p_payload->>'lifecycle'<>'DRAFT'
          OR p_payload->>'contentHash' !~ '^sha256:[0-9a-f]{64}$' OR p_request_hash !~ '^sha256:[0-9a-f]{64}$'
          OR length(BTRIM(p_payload->>'title')) NOT BETWEEN 1 AND 500
          OR p_payload->>'purposeCode' !~ '^[a-z][a-z0-9_.-]{1,119}$'
          OR length(BTRIM(p_payload->>'createdBy')) NOT BETWEEN 1 AND 200
          OR p_payload->>'analysisType' NOT IN('initial_store_analysis','weekly_business_review','experience_growth','creator_sales','product_structure')
          OR NOT COALESCE(ecommerce_investigation_exact_ref_valid_biw4_001(p_payload->'channelRef','ChannelRevision'),false)
          OR NOT COALESCE(ecommerce_investigation_exact_ref_valid_biw4_001(p_payload->'businessEntityRef','BusinessEntityRevision'),false)
          OR NOT COALESCE(ecommerce_investigation_exact_ref_valid_biw4_001(p_payload->'entityChannelBindingRef','BusinessEntityChannelBindingRevision'),false)
          OR NOT COALESCE(ecommerce_investigation_exact_ref_valid_biw4_001(p_payload->'investigationProfileRef','InvestigationProfileRevision'),false)
          OR NOT COALESCE(ecommerce_investigation_exact_ref_valid_biw4_001(p_payload->'scopeRef','InvestigationScopeRevision'),false)
          OR (p_payload ? 'schedulePolicyRef' AND p_payload->'schedulePolicyRef'<>'null'::jsonb
              AND NOT COALESCE(ecommerce_investigation_exact_ref_valid_biw4_001(p_payload->'schedulePolicyRef','SchedulePolicyRevision'),false))
          OR p_payload-ARRAY['schemaVersion','tenant','caseId','revision','version','priorRef','contentHash','lifecycle','analysisType','title','purposeCode','channelRef','businessEntityRef','entityChannelBindingRef','investigationProfileRef','scopeRef','schedulePolicyRef','createdBy','createdAt']<>'{}'::jsonb
          OR p_payload ?| ARRAY['taskRunRef','runStatus','stageStatus','artifactPayload','evidencePayload','rawPayload','modelResponse','sql','url','secret','token','cookie','password']
        THEN RAISE EXCEPTION USING ERRCODE='BO001',MESSAGE='Case draft violates authority contract';END IF;
        IF EXISTS(SELECT 1 FROM ecommerce_investigation_case_head h WHERE h.org_id=v_org AND h.project_id=v_project AND h.case_id=p_case_id)
        THEN RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='Case already exists';END IF;
        INSERT INTO ecommerce_investigation_case_head(org_id,project_id,case_id,current_revision,version,lifecycle,analysis_type,channel_id,business_entity_id)
        VALUES(v_org,v_project,p_case_id,1,1,'DRAFT',p_payload->>'analysisType',p_payload#>>'{channelRef,resourceId}',p_payload#>>'{businessEntityRef,resourceId}');
        INSERT INTO ecommerce_investigation_case_revision(org_id,project_id,case_id,revision,version,prior_revision,content_hash,lifecycle,analysis_type,channel_id,business_entity_id,entity_channel_binding_id,idempotency_key,request_hash,authority_data,created_by,created_at)
        VALUES(v_org,v_project,p_case_id,1,1,NULL,p_payload->>'contentHash','DRAFT',p_payload->>'analysisType',p_payload#>>'{channelRef,resourceId}',p_payload#>>'{businessEntityRef,resourceId}',p_payload#>>'{entityChannelBindingRef,resourceId}',p_idempotency_key,p_request_hash,p_payload,p_payload->>'createdBy',(p_payload->>'createdAt')::timestamptz);
        INSERT INTO ecommerce_investigation_case_command_receipt(org_id,project_id,receipt_id,operation,idempotency_key,request_hash,case_id,case_revision,authority_data)
        VALUES(v_org,v_project,gen_random_uuid()::text,'business_investigation_case.create_draft',p_idempotency_key,p_request_hash,p_case_id,1,p_payload);
        RETURN QUERY SELECT p_payload,false;
      END $$""")
    op.execute(f"REVOKE ALL ON FUNCTION ecommerce_investigation_case_create_biw4_001{SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION ecommerce_investigation_case_create_biw4_001{SIGNATURE} TO aos_runtime")
    op.execute("REVOKE ALL ON FUNCTION ecommerce_investigation_exact_ref_valid_biw4_001(jsonb,text) FROM PUBLIC")


def downgrade() -> None:
    op.execute("""DO $$ BEGIN IF EXISTS(SELECT 1 FROM ecommerce_investigation_case_revision LIMIT 1)
      OR EXISTS(SELECT 1 FROM ecommerce_investigation_case_command_receipt LIMIT 1)
      THEN RAISE EXCEPTION 'cannot downgrade biw4_001 with Case authority' USING ERRCODE='55000';END IF;END $$""")
    op.execute(f"DROP FUNCTION ecommerce_investigation_case_create_biw4_001{SIGNATURE}")
    op.execute("DROP TABLE ecommerce_investigation_case_command_receipt")
    op.execute("DROP TABLE ecommerce_investigation_case_revision")
    op.execute("DROP TABLE ecommerce_investigation_case_head")
    op.execute("DROP FUNCTION ecommerce_investigation_exact_ref_valid_biw4_001(jsonb,text)")
    op.execute("DROP FUNCTION guard_ecommerce_investigation_case_biw4_001()")
