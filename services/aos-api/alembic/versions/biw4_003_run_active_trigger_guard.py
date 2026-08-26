"""Add active Run slot and trigger idempotency. Revision ID: biw4_003."""

from collections.abc import Sequence

from alembic import op


revision: str = "biw4_003"
down_revision: str | Sequence[str] | None = "biw4_002"
branch_labels = depends_on = None
SIGNATURE = "(text,text,text,jsonb)"


def upgrade() -> None:
    op.execute("""DO $$ BEGIN
      IF EXISTS(
        SELECT 1 FROM ecommerce_investigation_run
        GROUP BY org_id,project_id,case_id,analysis_type HAVING count(*)>1
      ) THEN RAISE EXCEPTION 'cannot establish single active Run: duplicate active scope' USING ERRCODE='55000';END IF;
      IF EXISTS(
        SELECT 1 FROM ecommerce_investigation_run
        GROUP BY org_id,project_id,case_id,analysis_type,trigger_key HAVING count(*)>1
      ) THEN RAISE EXCEPTION 'cannot establish trigger idempotency: duplicate triggerKey' USING ERRCODE='55000';END IF;
    END $$""")
    op.execute("""CREATE TABLE ecommerce_investigation_run_active_slot(
      org_id TEXT NOT NULL,project_id TEXT NOT NULL,case_id TEXT NOT NULL,analysis_type TEXT NOT NULL,
      run_id TEXT NOT NULL,trigger_kind TEXT NOT NULL,trigger_key TEXT NOT NULL,acquired_at TIMESTAMPTZ NOT NULL,
      PRIMARY KEY(org_id,project_id,case_id,analysis_type),UNIQUE(org_id,project_id,run_id),
      FOREIGN KEY(org_id,project_id,run_id) REFERENCES ecommerce_investigation_run(org_id,project_id,run_id),
      CHECK(analysis_type IN('initial_store_analysis','weekly_business_review','experience_growth','creator_sales','product_structure')),
      CHECK(trigger_kind IN('manual','scheduled','topic','recovery')))""")
    op.execute("""CREATE TABLE ecommerce_investigation_run_trigger_receipt(
      org_id TEXT NOT NULL,project_id TEXT NOT NULL,receipt_id TEXT NOT NULL,case_id TEXT NOT NULL,
      analysis_type TEXT NOT NULL,trigger_kind TEXT NOT NULL,trigger_key TEXT NOT NULL,
      requested_run_id TEXT NOT NULL,active_run_id TEXT NOT NULL,outcome TEXT NOT NULL,
      request_hash TEXT NOT NULL,authority_data JSONB NOT NULL,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY(org_id,project_id,receipt_id),
      UNIQUE(org_id,project_id,case_id,analysis_type,trigger_key),
      FOREIGN KEY(org_id,project_id,active_run_id) REFERENCES ecommerce_investigation_run(org_id,project_id,run_id),
      CHECK(analysis_type IN('initial_store_analysis','weekly_business_review','experience_growth','creator_sales','product_structure')),
      CHECK(trigger_kind IN('manual','scheduled','topic','recovery')),
      CHECK(outcome IN('CREATED','SKIPPED_OVERLAP')),
      CHECK(request_hash ~ '^sha256:[0-9a-f]{64}$'),CHECK(jsonb_typeof(authority_data)='object'))""")
    op.execute("""INSERT INTO ecommerce_investigation_run_active_slot(
      org_id,project_id,case_id,analysis_type,run_id,trigger_kind,trigger_key,acquired_at)
      SELECT org_id,project_id,case_id,analysis_type,run_id,trigger_kind,trigger_key,created_at
      FROM ecommerce_investigation_run""")
    op.execute("""INSERT INTO ecommerce_investigation_run_trigger_receipt(
      org_id,project_id,receipt_id,case_id,analysis_type,trigger_kind,trigger_key,
      requested_run_id,active_run_id,outcome,request_hash,authority_data,created_at)
      SELECT r.org_id,r.project_id,gen_random_uuid()::text,r.case_id,r.analysis_type,r.trigger_kind,r.trigger_key,
        r.run_id,r.run_id,'CREATED',c.request_hash,r.authority_data,r.created_at
      FROM ecommerce_investigation_run r JOIN ecommerce_investigation_run_command_receipt c
        ON c.org_id=r.org_id AND c.project_id=r.project_id AND c.run_id=r.run_id""")
    for table in (
        "ecommerce_investigation_run_active_slot",
        "ecommerce_investigation_run_trigger_receipt",
    ):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""CREATE POLICY tenant_scope_{table}_biw4_003 ON {table} TO aos_runtime
          USING(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))
          WITH CHECK(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
        op.execute(f"GRANT SELECT ON {table} TO aos_runtime")
        op.execute(f"REVOKE INSERT,UPDATE,DELETE,TRUNCATE ON {table} FROM aos_runtime")
    op.execute("""CREATE TRIGGER trg_ecommerce_investigation_run_trigger_receipt_immutable
      BEFORE UPDATE OR DELETE ON ecommerce_investigation_run_trigger_receipt FOR EACH ROW
      EXECUTE FUNCTION guard_ecommerce_investigation_run_biw4_002()""")
    op.execute("""CREATE FUNCTION ecommerce_investigation_run_request_biw4_003(
      p_run_id text,p_idempotency_key text,p_request_hash text,p_payload jsonb)
      RETURNS TABLE(authority_data jsonb,outcome text,replayed boolean)
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
      DECLARE
        v_org text:=NULLIF(current_setting('aos.org_id',true),'');
        v_project text:=NULLIF(current_setting('aos.project_id',true),'');
        v_case_id text:=p_payload#>>'{caseRef,resourceId}';
        v_analysis_type text:=p_payload->>'analysisType';
        v_trigger_kind text:=p_payload->>'triggerKind';
        v_trigger_key text:=p_payload->>'triggerKey';
        v_existing record;v_active record;v_authority jsonb;v_inner_replayed boolean;
      BEGIN
        IF v_org IS NULL OR v_project IS NULL OR p_payload IS NULL OR jsonb_typeof(p_payload)<>'object'
          OR p_run_id IS NULL OR length(BTRIM(p_run_id)) NOT BETWEEN 1 AND 200
          OR p_idempotency_key IS NULL OR length(BTRIM(p_idempotency_key)) NOT BETWEEN 1 AND 200
          OR p_request_hash !~ '^sha256:[0-9a-f]{64}$'
          OR NOT COALESCE(ecommerce_investigation_exact_ref_valid_biw4_001(p_payload->'caseRef','BusinessInvestigationCaseRevision'),false)
          OR v_analysis_type NOT IN('initial_store_analysis','weekly_business_review','experience_growth','creator_sales','product_structure')
          OR v_trigger_kind NOT IN('manual','scheduled','topic','recovery')
          OR length(BTRIM(v_trigger_key)) NOT BETWEEN 1 AND 240
        THEN RAISE EXCEPTION USING ERRCODE='BO001',MESSAGE='Run guard request violates authority contract';END IF;

        PERFORM pg_advisory_xact_lock(hashtextextended(concat_ws(E'\\x1f',v_org,v_project,v_case_id,v_analysis_type),0));
        SELECT t.trigger_kind,t.authority_data,t.outcome INTO v_existing
          FROM ecommerce_investigation_run_trigger_receipt t
          WHERE t.org_id=v_org AND t.project_id=v_project AND t.case_id=v_case_id
            AND t.analysis_type=v_analysis_type AND t.trigger_key=v_trigger_key;
        IF FOUND THEN
          IF v_existing.trigger_kind<>v_trigger_kind THEN
            RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='triggerKey kind conflict';
          END IF;
          RETURN QUERY SELECT v_existing.authority_data,v_existing.outcome,true;RETURN;
        END IF;

        SELECT s.run_id,r.authority_data INTO v_active
          FROM ecommerce_investigation_run_active_slot s JOIN ecommerce_investigation_run r
            ON r.org_id=s.org_id AND r.project_id=s.project_id AND r.run_id=s.run_id
          WHERE s.org_id=v_org AND s.project_id=v_project AND s.case_id=v_case_id
            AND s.analysis_type=v_analysis_type FOR SHARE OF r;
        IF FOUND THEN
          IF v_trigger_kind<>'scheduled' THEN
            RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='active Run overlap is not mergeable';
          END IF;
          INSERT INTO ecommerce_investigation_run_trigger_receipt(
            org_id,project_id,receipt_id,case_id,analysis_type,trigger_kind,trigger_key,
            requested_run_id,active_run_id,outcome,request_hash,authority_data)
          VALUES(v_org,v_project,gen_random_uuid()::text,v_case_id,v_analysis_type,v_trigger_kind,v_trigger_key,
            p_run_id,v_active.run_id,'SKIPPED_OVERLAP',p_request_hash,v_active.authority_data);
          RETURN QUERY SELECT v_active.authority_data,'SKIPPED_OVERLAP'::text,false;RETURN;
        END IF;

        SELECT inner_result.authority_data,inner_result.replayed INTO v_authority,v_inner_replayed
          FROM ecommerce_investigation_run_request_biw4_002(p_run_id,p_idempotency_key,p_request_hash,p_payload) inner_result;
        INSERT INTO ecommerce_investigation_run_active_slot(
          org_id,project_id,case_id,analysis_type,run_id,trigger_kind,trigger_key,acquired_at)
        VALUES(v_org,v_project,v_case_id,v_analysis_type,p_run_id,v_trigger_kind,v_trigger_key,(p_payload->>'createdAt')::timestamptz);
        INSERT INTO ecommerce_investigation_run_trigger_receipt(
          org_id,project_id,receipt_id,case_id,analysis_type,trigger_kind,trigger_key,
          requested_run_id,active_run_id,outcome,request_hash,authority_data)
        VALUES(v_org,v_project,gen_random_uuid()::text,v_case_id,v_analysis_type,v_trigger_kind,v_trigger_key,
          p_run_id,p_run_id,'CREATED',p_request_hash,v_authority);
        RETURN QUERY SELECT v_authority,'CREATED'::text,v_inner_replayed;
      END $$""")
    op.execute(f"REVOKE EXECUTE ON FUNCTION ecommerce_investigation_run_request_biw4_002{SIGNATURE} FROM aos_runtime")
    op.execute(f"REVOKE ALL ON FUNCTION ecommerce_investigation_run_request_biw4_003{SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION ecommerce_investigation_run_request_biw4_003{SIGNATURE} TO aos_runtime")


def downgrade() -> None:
    op.execute("""DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM ecommerce_investigation_run_active_slot LIMIT 1)
        OR EXISTS(SELECT 1 FROM ecommerce_investigation_run_trigger_receipt LIMIT 1)
      THEN RAISE EXCEPTION 'cannot downgrade biw4_003 with active Run/trigger authority' USING ERRCODE='55000';END IF;
    END $$""")
    op.execute(f"DROP FUNCTION ecommerce_investigation_run_request_biw4_003{SIGNATURE}")
    op.execute(f"GRANT EXECUTE ON FUNCTION ecommerce_investigation_run_request_biw4_002{SIGNATURE} TO aos_runtime")
    op.execute("DROP TABLE ecommerce_investigation_run_trigger_receipt")
    op.execute("DROP TABLE ecommerce_investigation_run_active_slot")
