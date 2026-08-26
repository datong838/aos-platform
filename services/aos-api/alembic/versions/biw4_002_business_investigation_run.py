"""Add BusinessInvestigationRun, Event and local Outbox. Revision ID: biw4_002."""

from collections.abc import Sequence

from alembic import op


revision: str = "biw4_002"
down_revision: str | Sequence[str] | None = "biw4_001"
branch_labels = depends_on = None
SIGNATURE = "(text,text,text,jsonb)"


def upgrade() -> None:
    op.execute("""CREATE FUNCTION guard_ecommerce_investigation_run_biw4_002() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN RAISE EXCEPTION 'ECOMMERCE_INVESTIGATION_RUN_IMMUTABLE' USING ERRCODE='55000';END $$""")
    op.execute("""CREATE TABLE ecommerce_investigation_run(
      org_id TEXT NOT NULL,project_id TEXT NOT NULL,run_id TEXT NOT NULL,version BIGINT NOT NULL,
      content_hash TEXT NOT NULL,case_id TEXT NOT NULL,case_revision BIGINT NOT NULL,
      lifecycle TEXT NOT NULL,control TEXT NOT NULL,analysis_type TEXT NOT NULL,trigger_kind TEXT NOT NULL,
      trigger_key TEXT NOT NULL,current_event_sequence BIGINT NOT NULL,authority_data JSONB NOT NULL,
      created_by TEXT NOT NULL,created_at TIMESTAMPTZ NOT NULL,
      PRIMARY KEY(org_id,project_id,run_id),
      FOREIGN KEY(org_id,project_id,case_id,case_revision)
        REFERENCES ecommerce_investigation_case_revision(org_id,project_id,case_id,revision),
      CHECK(version=1),CHECK(content_hash ~ '^sha256:[0-9a-f]{64}$'),
      CHECK(lifecycle='PREPARING'),CHECK(control='RUNNING'),CHECK(current_event_sequence=1),
      CHECK(analysis_type IN('initial_store_analysis','weekly_business_review','experience_growth','creator_sales','product_structure')),
      CHECK(trigger_kind IN('manual','scheduled','topic','recovery')),CHECK(jsonb_typeof(authority_data)='object'))""")
    op.execute("""CREATE TABLE ecommerce_investigation_run_event(
      org_id TEXT NOT NULL,project_id TEXT NOT NULL,event_id TEXT NOT NULL,run_id TEXT NOT NULL,
      sequence BIGINT NOT NULL,event_type TEXT NOT NULL,content_hash TEXT NOT NULL,event_data JSONB NOT NULL,
      occurred_at TIMESTAMPTZ NOT NULL,PRIMARY KEY(org_id,project_id,event_id),
      UNIQUE(org_id,project_id,run_id,sequence),
      FOREIGN KEY(org_id,project_id,run_id) REFERENCES ecommerce_investigation_run(org_id,project_id,run_id),
      CHECK(sequence>=1),CHECK(event_type='RUN_REQUESTED'),CHECK(content_hash ~ '^sha256:[0-9a-f]{64}$'),
      CHECK(jsonb_typeof(event_data)='object'))""")
    op.execute("""CREATE TABLE ecommerce_investigation_run_outbox(
      org_id TEXT NOT NULL,project_id TEXT NOT NULL,outbox_id TEXT NOT NULL,event_id TEXT NOT NULL,
      run_id TEXT NOT NULL,status TEXT NOT NULL,payload JSONB NOT NULL,created_at TIMESTAMPTZ NOT NULL,
      PRIMARY KEY(org_id,project_id,outbox_id),UNIQUE(org_id,project_id,event_id),
      FOREIGN KEY(org_id,project_id,event_id) REFERENCES ecommerce_investigation_run_event(org_id,project_id,event_id),
      CHECK(status='PENDING'),CHECK(jsonb_typeof(payload)='object'))""")
    op.execute("""CREATE TABLE ecommerce_investigation_run_command_receipt(
      org_id TEXT NOT NULL,project_id TEXT NOT NULL,receipt_id TEXT NOT NULL,operation TEXT NOT NULL,
      idempotency_key TEXT NOT NULL,request_hash TEXT NOT NULL,run_id TEXT NOT NULL,
      authority_data JSONB NOT NULL,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY(org_id,project_id,receipt_id),UNIQUE(org_id,project_id,operation,idempotency_key),
      FOREIGN KEY(org_id,project_id,run_id) REFERENCES ecommerce_investigation_run(org_id,project_id,run_id),
      CHECK(operation='business_investigation_run.request'),CHECK(request_hash ~ '^sha256:[0-9a-f]{64}$'),
      CHECK(jsonb_typeof(authority_data)='object'))""")
    for table in (
        "ecommerce_investigation_run",
        "ecommerce_investigation_run_event",
        "ecommerce_investigation_run_outbox",
        "ecommerce_investigation_run_command_receipt",
    ):
        op.execute(f"CREATE TRIGGER trg_{table}_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION guard_ecommerce_investigation_run_biw4_002()")
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""CREATE POLICY tenant_scope_{table}_biw4_002 ON {table} TO aos_runtime
          USING(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))
          WITH CHECK(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
        op.execute(f"GRANT SELECT ON {table} TO aos_runtime")
        op.execute(f"REVOKE INSERT,UPDATE,DELETE,TRUNCATE ON {table} FROM aos_runtime")
    op.execute("""CREATE FUNCTION ecommerce_investigation_run_request_biw4_002(
      p_run_id text,p_idempotency_key text,p_request_hash text,p_payload jsonb)
      RETURNS TABLE(authority_data jsonb,replayed boolean) LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
      DECLARE v_org text:=NULLIF(current_setting('aos.org_id',true),'');v_project text:=NULLIF(current_setting('aos.project_id',true),'');
        v_existing record;v_case record;v_event_id text:=gen_random_uuid()::text;v_event_data jsonb;v_event_hash text;
      BEGIN
        SELECT r.authority_data,r.request_hash,r.run_id INTO v_existing FROM ecommerce_investigation_run_command_receipt r
          WHERE r.org_id=v_org AND r.project_id=v_project AND r.operation='business_investigation_run.request'
            AND r.idempotency_key=p_idempotency_key;
        IF FOUND THEN IF v_existing.request_hash<>p_request_hash OR v_existing.run_id<>p_run_id THEN RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='Run idempotency conflict';END IF;
          RETURN QUERY SELECT v_existing.authority_data,true;RETURN;END IF;
        IF v_org IS NULL OR v_project IS NULL OR p_run_id IS NULL OR length(BTRIM(p_run_id)) NOT BETWEEN 1 AND 200
          OR p_idempotency_key IS NULL OR length(BTRIM(p_idempotency_key)) NOT BETWEEN 1 AND 200
          OR NOT (p_payload ?& ARRAY['schemaVersion','tenant','runId','version','contentHash','caseRef','analysisType','triggerKind','triggerKey','lifecycle','control','createdBy','createdAt'])
          OR p_payload#>>'{tenant,orgId}'<>v_org OR p_payload#>>'{tenant,projectId}'<>v_project
          OR p_payload->>'schemaVersion'<>'aos.ecommerce.business-investigation-run/v1' OR p_payload->>'runId'<>p_run_id
          OR (p_payload->>'version')::bigint<>1 OR p_payload->>'lifecycle'<>'PREPARING' OR p_payload->>'control'<>'RUNNING'
          OR p_payload->>'contentHash' !~ '^sha256:[0-9a-f]{64}$' OR p_request_hash !~ '^sha256:[0-9a-f]{64}$'
          OR NOT COALESCE(ecommerce_investigation_exact_ref_valid_biw4_001(p_payload->'caseRef','BusinessInvestigationCaseRevision'),false)
          OR p_payload->>'analysisType' NOT IN('initial_store_analysis','weekly_business_review','experience_growth','creator_sales','product_structure')
          OR p_payload->>'triggerKind' NOT IN('manual','scheduled','topic','recovery')
          OR length(BTRIM(p_payload->>'triggerKey')) NOT BETWEEN 1 AND 240
          OR length(BTRIM(p_payload->>'createdBy')) NOT BETWEEN 1 AND 200
          OR p_payload-ARRAY['schemaVersion','tenant','runId','version','contentHash','caseRef','analysisType','triggerKind','triggerKey','lifecycle','control','createdBy','createdAt']<>'{}'::jsonb
          OR p_payload ?| ARRAY['taskRunRef','taskRunStatus','artifactPayload','evidencePayload','rawPayload','modelResponse','sql','url','secret','token','cookie','password']
        THEN RAISE EXCEPTION USING ERRCODE='BO001',MESSAGE='Run request violates authority contract';END IF;
        SELECT r.*,h.current_revision,h.lifecycle AS head_lifecycle INTO v_case
          FROM ecommerce_investigation_case_revision r JOIN ecommerce_investigation_case_head h
          ON h.org_id=r.org_id AND h.project_id=r.project_id AND h.case_id=r.case_id
          WHERE r.org_id=v_org AND r.project_id=v_project AND r.case_id=p_payload#>>'{caseRef,resourceId}'
            AND r.revision=(p_payload#>>'{caseRef,revision}')::bigint
            AND r.content_hash=p_payload#>>'{caseRef,contentHash}' FOR SHARE OF r,h;
        IF v_case IS NULL OR v_case.current_revision<>v_case.revision OR v_case.head_lifecycle<>'ACTIVE'
          OR v_case.analysis_type<>p_payload->>'analysisType'
        THEN RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='current exact ACTIVE Case is required';END IF;
        IF EXISTS(SELECT 1 FROM ecommerce_investigation_run r WHERE r.org_id=v_org AND r.project_id=v_project AND r.run_id=p_run_id)
        THEN RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='Run already exists';END IF;
        INSERT INTO ecommerce_investigation_run(org_id,project_id,run_id,version,content_hash,case_id,case_revision,lifecycle,control,analysis_type,trigger_kind,trigger_key,current_event_sequence,authority_data,created_by,created_at)
        VALUES(v_org,v_project,p_run_id,1,p_payload->>'contentHash',v_case.case_id,v_case.revision,'PREPARING','RUNNING',p_payload->>'analysisType',p_payload->>'triggerKind',p_payload->>'triggerKey',1,p_payload,p_payload->>'createdBy',(p_payload->>'createdAt')::timestamptz);
        v_event_data:=jsonb_build_object('schemaVersion','aos.ecommerce.business-investigation-run-event/v1','tenant',p_payload->'tenant','eventId',v_event_id,'runRef',jsonb_build_object('resourceType','BusinessInvestigationRun','resourceId',p_run_id,'revision',1,'contentHash',p_payload->>'contentHash'),'caseRef',p_payload->'caseRef','sequence',1,'eventType','RUN_REQUESTED','occurredAt',p_payload->'createdAt');
        v_event_hash:='sha256:'||encode(public.digest(convert_to(v_event_data::text,'UTF8'),'sha256'),'hex');
        INSERT INTO ecommerce_investigation_run_event(org_id,project_id,event_id,run_id,sequence,event_type,content_hash,event_data,occurred_at)
        VALUES(v_org,v_project,v_event_id,p_run_id,1,'RUN_REQUESTED',v_event_hash,v_event_data,(p_payload->>'createdAt')::timestamptz);
        INSERT INTO ecommerce_investigation_run_outbox(org_id,project_id,outbox_id,event_id,run_id,status,payload,created_at)
        VALUES(v_org,v_project,gen_random_uuid()::text,v_event_id,p_run_id,'PENDING',jsonb_build_object('eventRef',jsonb_build_object('resourceType','BusinessInvestigationRunEvent','resourceId',v_event_id,'revision',1,'contentHash',v_event_hash),'nonClaims',jsonb_build_array('NO_AIP_TASKRUN','NO_DELIVERY_CLAIM','NO_EXTERNAL_EFFECT')),(p_payload->>'createdAt')::timestamptz);
        INSERT INTO ecommerce_investigation_run_command_receipt(org_id,project_id,receipt_id,operation,idempotency_key,request_hash,run_id,authority_data)
        VALUES(v_org,v_project,gen_random_uuid()::text,'business_investigation_run.request',p_idempotency_key,p_request_hash,p_run_id,p_payload);
        RETURN QUERY SELECT p_payload,false;
      END $$""")
    op.execute(f"REVOKE ALL ON FUNCTION ecommerce_investigation_run_request_biw4_002{SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION ecommerce_investigation_run_request_biw4_002{SIGNATURE} TO aos_runtime")


def downgrade() -> None:
    op.execute("""DO $$ BEGIN IF EXISTS(SELECT 1 FROM ecommerce_investigation_run LIMIT 1)
      OR EXISTS(SELECT 1 FROM ecommerce_investigation_run_event LIMIT 1)
      OR EXISTS(SELECT 1 FROM ecommerce_investigation_run_outbox LIMIT 1)
      OR EXISTS(SELECT 1 FROM ecommerce_investigation_run_command_receipt LIMIT 1)
      THEN RAISE EXCEPTION 'cannot downgrade biw4_002 with Run authority' USING ERRCODE='55000';END IF;END $$""")
    op.execute(f"DROP FUNCTION ecommerce_investigation_run_request_biw4_002{SIGNATURE}")
    op.execute("DROP TABLE ecommerce_investigation_run_command_receipt")
    op.execute("DROP TABLE ecommerce_investigation_run_outbox")
    op.execute("DROP TABLE ecommerce_investigation_run_event")
    op.execute("DROP TABLE ecommerce_investigation_run")
    op.execute("DROP FUNCTION guard_ecommerce_investigation_run_biw4_002()")
