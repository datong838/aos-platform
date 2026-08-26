"""Add immutable cross-layer compilation receipts. Revision ID: biw6_001."""

from collections.abc import Sequence

from alembic import op


revision: str = "biw6_001"
down_revision: str | Sequence[str] | None = "biw4_007"
branch_labels = depends_on = None
SIGNATURE = "(text,text,text,jsonb)"


def upgrade() -> None:
    op.execute("""CREATE TABLE aip_business_investigation_compile_receipt(
      org_id TEXT NOT NULL,project_id TEXT NOT NULL,receipt_id TEXT NOT NULL,
      command_id TEXT NOT NULL,request_hash TEXT NOT NULL,run_id TEXT NOT NULL,
      run_version BIGINT NOT NULL,run_content_hash TEXT NOT NULL,task_id TEXT NOT NULL,
      plan_revision_id TEXT NOT NULL,plan_revision BIGINT NOT NULL,plan_content_hash TEXT NOT NULL,
      receipt_data JSONB NOT NULL,created_at TIMESTAMPTZ NOT NULL,
      PRIMARY KEY(org_id,project_id,receipt_id),UNIQUE(org_id,project_id,command_id),
      FOREIGN KEY(org_id,project_id,run_id)
        REFERENCES ecommerce_investigation_run(org_id,project_id,run_id),
      FOREIGN KEY(org_id,project_id,plan_revision_id)
        REFERENCES aip_plan_revision(org_id,project_id,plan_revision_id),
      CHECK(length(BTRIM(command_id)) BETWEEN 1 AND 200),
      CHECK(request_hash ~ '^sha256:[0-9a-f]{64}$'),CHECK(run_version>=1),
      CHECK(run_content_hash ~ '^sha256:[0-9a-f]{64}$'),CHECK(plan_revision>=1),
      CHECK(plan_content_hash ~ '^[0-9a-f]{64}$'),CHECK(jsonb_typeof(receipt_data)='object'))""")
    op.execute("""CREATE TRIGGER trg_aip_business_investigation_compile_receipt_immutable
      BEFORE UPDATE OR DELETE ON aip_business_investigation_compile_receipt FOR EACH ROW
      EXECUTE FUNCTION guard_ecommerce_investigation_run_biw4_002()""")
    op.execute("ALTER TABLE aip_business_investigation_compile_receipt ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE aip_business_investigation_compile_receipt FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY tenant_scope_aip_business_investigation_compile_receipt_biw6_001
      ON aip_business_investigation_compile_receipt TO aos_runtime
      USING(org_id=NULLIF(current_setting('aos.org_id',true),'')
        AND project_id=NULLIF(current_setting('aos.project_id',true),''))
      WITH CHECK(org_id=NULLIF(current_setting('aos.org_id',true),'')
        AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
    op.execute("GRANT SELECT ON aip_business_investigation_compile_receipt TO aos_runtime")
    op.execute("REVOKE INSERT,UPDATE,DELETE,TRUNCATE ON aip_business_investigation_compile_receipt FROM aos_runtime")
    op.execute("""CREATE FUNCTION aip_business_investigation_compile_receipt_biw6_001(
      p_command_id text,p_request_hash text,p_receipt_id text,p_payload jsonb)
      RETURNS TABLE(receipt_data jsonb,replayed boolean)
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
      DECLARE v_org text:=NULLIF(current_setting('aos.org_id',true),'');
        v_project text:=NULLIF(current_setting('aos.project_id',true),'');v_existing record;
        v_run record;v_state record;v_plan record;
      BEGIN
        IF v_org IS NOT NULL AND v_project IS NOT NULL AND p_command_id IS NOT NULL THEN
          PERFORM pg_advisory_xact_lock(hashtext(v_org||E'\\x1f'||v_project),hashtext(p_command_id));
        END IF;
        SELECT r.receipt_data,r.request_hash INTO v_existing
          FROM aip_business_investigation_compile_receipt r
          WHERE r.org_id=v_org AND r.project_id=v_project AND r.command_id=p_command_id;
        IF FOUND THEN
          IF v_existing.request_hash<>p_request_hash THEN
            RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='Compilation receipt command conflict';END IF;
          RETURN QUERY SELECT v_existing.receipt_data,true;RETURN;
        END IF;
        IF v_org IS NULL OR v_project IS NULL
          OR length(BTRIM(p_command_id)) NOT BETWEEN 1 AND 200
          OR length(BTRIM(p_receipt_id)) NOT BETWEEN 1 AND 200
          OR p_request_hash !~ '^sha256:[0-9a-f]{64}$' OR jsonb_typeof(p_payload)<>'object'
          OR NOT (p_payload ?& ARRAY['schemaVersion','tenant','receiptId','commandId','requestHash',
            'runRef','taskId','planRef','profileRef','logicRef','skillBindingSetRef',
            'responsibilityPlanRef','inputHash','stageCompilationHash','compilationHash',
            'runtimeAuthorized','createdAt'])
          OR p_payload->>'schemaVersion'<>'aos.aip.business-investigation-compilation-receipt/v1'
          OR p_payload#>>'{tenant,orgId}'<>v_org OR p_payload#>>'{tenant,projectId}'<>v_project
          OR p_payload->>'receiptId'<>p_receipt_id OR p_payload->>'commandId'<>p_command_id
          OR p_payload->>'requestHash'<>p_request_hash OR (p_payload->>'runtimeAuthorized')::boolean
          OR p_payload->>'inputHash' !~ '^[0-9a-f]{64}$'
          OR p_payload->>'stageCompilationHash' !~ '^[0-9a-f]{64}$'
          OR p_payload->>'compilationHash' !~ '^[0-9a-f]{64}$'
          OR p_payload-ARRAY['schemaVersion','tenant','receiptId','commandId','requestHash',
            'runRef','taskId','planRef','profileRef','logicRef','skillBindingSetRef',
            'responsibilityPlanRef','inputHash','stageCompilationHash','compilationHash',
            'runtimeAuthorized','createdAt']<>'{}'::jsonb
          OR p_payload ?| ARRAY['rawPayload','modelResponse','sql','url','secret','credential','token','cookie','password']
        THEN RAISE EXCEPTION USING ERRCODE='BO001',MESSAGE='Compilation receipt violates authority contract';END IF;
        IF p_payload#>>'{runRef,resourceType}'<>'BusinessInvestigationRun'
          OR p_payload#>>'{runRef,contentHash}' !~ '^sha256:[0-9a-f]{64}$'
          OR p_payload#>>'{planRef,resourceType}'<>'PlanRevision'
          OR p_payload#>>'{planRef,contentHash}' !~ '^[0-9a-f]{64}$'
          OR p_payload#>>'{profileRef,resourceType}'<>'InvestigationProfileRevision'
          OR p_payload#>>'{logicRef,resourceType}'<>'LogicRevision'
          OR p_payload#>>'{skillBindingSetRef,resourceType}'<>'SkillBindingSetRevision'
          OR p_payload#>>'{responsibilityPlanRef,resourceType}'<>'ResponsibilityPlanRevision'
        THEN RAISE EXCEPTION USING ERRCODE='BO001',MESSAGE='Compilation receipt exact refs invalid';END IF;
        SELECT * INTO v_run FROM ecommerce_investigation_run r
          WHERE r.org_id=v_org AND r.project_id=v_project
            AND r.run_id=p_payload#>>'{runRef,resourceId}'
            AND r.version=(p_payload#>>'{runRef,revision}')::bigint
            AND r.content_hash=p_payload#>>'{runRef,contentHash}' FOR SHARE;
        SELECT * INTO v_state FROM ecommerce_investigation_run_state_head h
          WHERE h.org_id=v_org AND h.project_id=v_project
            AND h.run_id=p_payload#>>'{runRef,resourceId}' FOR SHARE;
        IF v_run IS NULL OR v_state IS NULL OR v_state.lifecycle<>'PREPARING'
          OR v_state.control<>'RUNNING' THEN
          RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='Exact PREPARING RUNNING Run is required';END IF;
        SELECT * INTO v_plan FROM aip_plan_revision p
          WHERE p.org_id=v_org AND p.project_id=v_project
            AND p.plan_revision_id=p_payload#>>'{planRef,resourceId}'
            AND p.task_id=p_payload->>'taskId'
            AND p.revision=(p_payload#>>'{planRef,revision}')::bigint
            AND p.content_hash=p_payload#>>'{planRef,contentHash}' FOR SHARE;
        IF v_plan IS NULL THEN
          RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='Exact canonical Plan is required';END IF;
        INSERT INTO aip_business_investigation_compile_receipt(
          org_id,project_id,receipt_id,command_id,request_hash,run_id,run_version,
          run_content_hash,task_id,plan_revision_id,plan_revision,plan_content_hash,
          receipt_data,created_at)
        VALUES(v_org,v_project,p_receipt_id,p_command_id,p_request_hash,v_run.run_id,v_run.version,
          v_run.content_hash,v_plan.task_id,v_plan.plan_revision_id,v_plan.revision,v_plan.content_hash,
          p_payload,(p_payload->>'createdAt')::timestamptz);
        RETURN QUERY SELECT p_payload,false;
      END $$""")
    op.execute(f"REVOKE ALL ON FUNCTION aip_business_investigation_compile_receipt_biw6_001{SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION aip_business_investigation_compile_receipt_biw6_001{SIGNATURE} TO aos_runtime")


def downgrade() -> None:
    op.execute("""DO $$ BEGIN IF EXISTS(
      SELECT 1 FROM aip_business_investigation_compile_receipt LIMIT 1)
      THEN RAISE EXCEPTION 'cannot downgrade biw6_001 with compilation receipt authority'
        USING ERRCODE='55000';END IF;END $$""")
    op.execute(f"DROP FUNCTION aip_business_investigation_compile_receipt_biw6_001{SIGNATURE}")
    op.execute("DROP TABLE aip_business_investigation_compile_receipt")
