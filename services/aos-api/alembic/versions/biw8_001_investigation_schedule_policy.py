"""Add versioned investigation SchedulePolicy authority. Revision ID: biw8_001."""

from collections.abc import Sequence

from alembic import op


revision: str = "biw8_001"
down_revision: str | Sequence[str] | None = "biw6_002"
branch_labels = depends_on = None
SIGNATURE = "(text,bigint,text,bigint,text,text,jsonb,jsonb)"


def upgrade() -> None:
    op.execute("""CREATE TABLE ecommerce_investigation_schedule_policy_head(
      org_id TEXT NOT NULL,project_id TEXT NOT NULL,schedule_policy_id TEXT NOT NULL,
      current_revision BIGINT NOT NULL,case_id TEXT NOT NULL,analysis_type TEXT NOT NULL,
      enabled BOOLEAN NOT NULL,content_hash TEXT NOT NULL,authority_data JSONB NOT NULL,
      updated_at TIMESTAMPTZ NOT NULL,PRIMARY KEY(org_id,project_id,schedule_policy_id),
      FOREIGN KEY(org_id,project_id,case_id) REFERENCES ecommerce_investigation_case_head(org_id,project_id,case_id),
      CHECK(current_revision>=1),CHECK(content_hash ~ '^sha256:[0-9a-f]{64}$'),
      CHECK(jsonb_typeof(authority_data)='object'))""")
    op.execute("""CREATE TABLE ecommerce_investigation_schedule_policy_revision(
      org_id TEXT NOT NULL,project_id TEXT NOT NULL,schedule_policy_id TEXT NOT NULL,
      revision BIGINT NOT NULL,prior_revision BIGINT,case_id TEXT NOT NULL,case_revision BIGINT NOT NULL,
      analysis_type TEXT NOT NULL,policy_kind TEXT NOT NULL,cadence TEXT NOT NULL,enabled BOOLEAN NOT NULL,
      content_hash TEXT NOT NULL,authority_data JSONB NOT NULL,created_by TEXT NOT NULL,created_at TIMESTAMPTZ NOT NULL,
      PRIMARY KEY(org_id,project_id,schedule_policy_id,revision),
      FOREIGN KEY(org_id,project_id,case_id,case_revision)
        REFERENCES ecommerce_investigation_case_revision(org_id,project_id,case_id,revision),
      CHECK((revision=1 AND prior_revision IS NULL) OR (revision>1 AND prior_revision=revision-1)),
      CHECK(policy_kind IN('initial_checkup','weekly_review','topic_analysis')),
      CHECK(cadence IN('once','weekly','on_demand')),CHECK(content_hash ~ '^sha256:[0-9a-f]{64}$'),
      CHECK(jsonb_typeof(authority_data)='object'))""")
    op.execute("""CREATE TABLE ecommerce_investigation_schedule_policy_command_receipt(
      org_id TEXT NOT NULL,project_id TEXT NOT NULL,receipt_id TEXT NOT NULL,operation TEXT NOT NULL,
      idempotency_key TEXT NOT NULL,request_hash TEXT NOT NULL,schedule_policy_id TEXT NOT NULL,
      expected_policy_revision BIGINT NOT NULL,result_policy_revision BIGINT NOT NULL,
      case_id TEXT NOT NULL,expected_case_version BIGINT NOT NULL,result_case_revision BIGINT NOT NULL,
      policy_authority JSONB NOT NULL,case_authority JSONB NOT NULL,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY(org_id,project_id,receipt_id),UNIQUE(org_id,project_id,operation,idempotency_key),
      FOREIGN KEY(org_id,project_id,schedule_policy_id,result_policy_revision)
        REFERENCES ecommerce_investigation_schedule_policy_revision(org_id,project_id,schedule_policy_id,revision),
      FOREIGN KEY(org_id,project_id,case_id,result_case_revision)
        REFERENCES ecommerce_investigation_case_revision(org_id,project_id,case_id,revision),
      CHECK(operation='business_investigation_schedule_policy.put'),
      CHECK(result_policy_revision=expected_policy_revision+1),CHECK(result_case_revision=expected_case_version+1),
      CHECK(request_hash ~ '^sha256:[0-9a-f]{64}$'),CHECK(jsonb_typeof(policy_authority)='object'),
      CHECK(jsonb_typeof(case_authority)='object'))""")
    for table in (
        "ecommerce_investigation_schedule_policy_head",
        "ecommerce_investigation_schedule_policy_revision",
        "ecommerce_investigation_schedule_policy_command_receipt",
    ):
        if table != "ecommerce_investigation_schedule_policy_head":
            op.execute(f"""CREATE TRIGGER trg_{table}_immutable BEFORE UPDATE OR DELETE ON {table}
              FOR EACH ROW EXECUTE FUNCTION guard_ecommerce_investigation_case_biw4_001()""")
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""CREATE POLICY tenant_scope_{table}_biw8_001 ON {table} TO aos_runtime
          USING(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))
          WITH CHECK(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
        op.execute(f"GRANT SELECT ON {table} TO aos_runtime")
        op.execute(f"REVOKE INSERT,UPDATE,DELETE,TRUNCATE ON {table} FROM aos_runtime")

    op.execute("""CREATE FUNCTION ecommerce_investigation_schedule_policy_put_biw8_001(
      p_schedule_policy_id text,p_expected_policy_revision bigint,p_case_id text,p_expected_case_version bigint,
      p_idempotency_key text,p_request_hash text,p_policy jsonb,p_case jsonb)
      RETURNS TABLE(policy_authority jsonb,case_authority jsonb,replayed boolean)
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
      DECLARE v_org text:=NULLIF(current_setting('aos.org_id',true),'');
        v_project text:=NULLIF(current_setting('aos.project_id',true),'');v_existing record;
        v_case_head record;v_case_prior record;v_policy_head record;v_policy_prior record;
      BEGIN
        SELECT r.policy_authority,r.case_authority,r.request_hash,r.schedule_policy_id,r.case_id,
          r.expected_policy_revision,r.expected_case_version INTO v_existing
        FROM ecommerce_investigation_schedule_policy_command_receipt r
        WHERE r.org_id=v_org AND r.project_id=v_project
          AND r.operation='business_investigation_schedule_policy.put' AND r.idempotency_key=p_idempotency_key;
        IF FOUND THEN
          IF v_existing.request_hash<>p_request_hash OR v_existing.schedule_policy_id<>p_schedule_policy_id
            OR v_existing.case_id<>p_case_id OR v_existing.expected_policy_revision<>p_expected_policy_revision
            OR v_existing.expected_case_version<>p_expected_case_version
          THEN RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='SchedulePolicy idempotency conflict';END IF;
          RETURN QUERY SELECT v_existing.policy_authority,v_existing.case_authority,true;RETURN;
        END IF;
        IF v_org IS NULL OR v_project IS NULL OR p_expected_policy_revision<0 OR p_expected_case_version<1
          OR length(BTRIM(p_schedule_policy_id)) NOT BETWEEN 1 AND 200
          OR length(BTRIM(p_case_id)) NOT BETWEEN 1 AND 200
          OR length(BTRIM(p_idempotency_key)) NOT BETWEEN 1 AND 200
          OR p_request_hash !~ '^sha256:[0-9a-f]{64}$' OR jsonb_typeof(p_policy)<>'object'
          OR jsonb_typeof(p_case)<>'object'
        THEN RAISE EXCEPTION USING ERRCODE='BO001',MESSAGE='SchedulePolicy request invalid';END IF;
        SELECT * INTO v_case_head FROM ecommerce_investigation_case_head h
          WHERE h.org_id=v_org AND h.project_id=v_project AND h.case_id=p_case_id FOR UPDATE;
        IF NOT FOUND OR v_case_head.version<>p_expected_case_version
        THEN RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='SchedulePolicy Case version conflict';END IF;
        SELECT * INTO v_case_prior FROM ecommerce_investigation_case_revision r
          WHERE r.org_id=v_org AND r.project_id=v_project AND r.case_id=p_case_id
            AND r.revision=p_expected_case_version;
        SELECT * INTO v_policy_head FROM ecommerce_investigation_schedule_policy_head h
          WHERE h.org_id=v_org AND h.project_id=v_project AND h.schedule_policy_id=p_schedule_policy_id FOR UPDATE;
        IF (p_expected_policy_revision=0 AND FOUND) OR
          (p_expected_policy_revision>0 AND (NOT FOUND OR v_policy_head.current_revision<>p_expected_policy_revision))
        THEN RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='SchedulePolicy expected revision conflict';END IF;
        IF p_expected_policy_revision>0 THEN
          SELECT * INTO v_policy_prior FROM ecommerce_investigation_schedule_policy_revision r
            WHERE r.org_id=v_org AND r.project_id=v_project AND r.schedule_policy_id=p_schedule_policy_id
              AND r.revision=p_expected_policy_revision;
        END IF;
        IF p_policy#>>'{tenant,orgId}'<>v_org OR p_policy#>>'{tenant,projectId}'<>v_project
          OR p_policy->>'schemaVersion'<>'aos.ecommerce.business-investigation-schedule-policy/v1'
          OR p_policy->>'schedulePolicyId'<>p_schedule_policy_id
          OR (p_policy->>'revision')::bigint<>p_expected_policy_revision+1
          OR (p_policy->>'version')::bigint<>p_expected_policy_revision+1
          OR p_policy#>>'{caseRef,resourceType}'<>'BusinessInvestigationCaseRevision'
          OR p_policy#>>'{caseRef,resourceId}'<>p_case_id
          OR (p_policy#>>'{caseRef,revision}')::bigint<>p_expected_case_version
          OR p_policy#>>'{caseRef,contentHash}'<>v_case_prior.content_hash
          OR p_policy->>'analysisType'<>v_case_prior.analysis_type
          OR p_policy->>'overlapPolicy'<>'skip' OR p_policy->>'timezone'<>'Asia/Shanghai'
          OR p_policy->>'contentHash' !~ '^sha256:[0-9a-f]{64}$'
          OR p_policy->>'policyKind' NOT IN('initial_checkup','weekly_review','topic_analysis')
          OR NOT ((p_policy->>'policyKind'='initial_checkup' AND p_policy->>'cadence'='once'
              AND p_policy->>'analysisType'='initial_store_analysis')
            OR (p_policy->>'policyKind'='weekly_review' AND p_policy->>'cadence'='weekly'
              AND p_policy->>'analysisType'='weekly_business_review'
              AND (p_policy->>'weeklyDay')::int BETWEEN 1 AND 7
              AND p_policy->>'localTime' ~ '^([01][0-9]|2[0-3]):[0-5][0-9]$')
            OR (p_policy->>'policyKind'='topic_analysis' AND p_policy->>'cadence'='on_demand'
              AND p_policy->>'analysisType' IN('experience_growth','creator_sales','product_structure')))
        THEN RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='SchedulePolicy authority rejected';END IF;
        IF p_expected_policy_revision=0 THEN
          IF p_policy->'priorRef'<>'null'::jsonb
          THEN RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='SchedulePolicy authority rejected';END IF;
        ELSE
          IF p_policy#>>'{priorRef,resourceType}'<>'SchedulePolicyRevision'
            OR p_policy#>>'{priorRef,resourceId}'<>p_schedule_policy_id
            OR (p_policy#>>'{priorRef,revision}')::bigint<>p_expected_policy_revision
            OR p_policy#>>'{priorRef,contentHash}'<>v_policy_prior.content_hash
            OR p_policy#>>'{caseRef,resourceId}'<>v_policy_prior.case_id
            OR p_policy->>'analysisType'<>v_policy_prior.analysis_type
            OR p_policy->>'policyKind'<>v_policy_prior.policy_kind
            OR p_policy->>'cadence'<>v_policy_prior.cadence
          THEN RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='SchedulePolicy authority rejected';END IF;
        END IF;
        IF p_case#>>'{tenant,orgId}'<>v_org OR p_case#>>'{tenant,projectId}'<>v_project
          OR p_case->>'caseId'<>p_case_id OR (p_case->>'revision')::bigint<>p_expected_case_version+1
          OR (p_case->>'version')::bigint<>p_expected_case_version+1
          OR p_case#>>'{priorRef,resourceType}'<>'BusinessInvestigationCaseRevision'
          OR p_case#>>'{priorRef,resourceId}'<>p_case_id
          OR (p_case#>>'{priorRef,revision}')::bigint<>p_expected_case_version
          OR p_case#>>'{priorRef,contentHash}'<>v_case_prior.content_hash
          OR p_case#>>'{schedulePolicyRef,resourceType}'<>'SchedulePolicyRevision'
          OR p_case#>>'{schedulePolicyRef,resourceId}'<>p_schedule_policy_id
          OR (p_case#>>'{schedulePolicyRef,revision}')::bigint<>p_expected_policy_revision+1
          OR p_case#>>'{schedulePolicyRef,contentHash}'<>p_policy->>'contentHash'
          OR p_case->>'contentHash' !~ '^sha256:[0-9a-f]{64}$'
          OR (p_case-ARRAY['revision','version','priorRef','contentHash','schedulePolicyRef','createdBy','createdAt'])
            <>(v_case_prior.authority_data-ARRAY['revision','version','priorRef','contentHash','schedulePolicyRef','createdBy','createdAt'])
        THEN RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='SchedulePolicy Case binding rejected';END IF;
        INSERT INTO ecommerce_investigation_schedule_policy_revision(
          org_id,project_id,schedule_policy_id,revision,prior_revision,case_id,case_revision,
          analysis_type,policy_kind,cadence,enabled,content_hash,authority_data,created_by,created_at)
        VALUES(v_org,v_project,p_schedule_policy_id,p_expected_policy_revision+1,
          NULLIF(p_expected_policy_revision,0),p_case_id,p_expected_case_version,p_policy->>'analysisType',
          p_policy->>'policyKind',p_policy->>'cadence',(p_policy->>'enabled')::boolean,
          p_policy->>'contentHash',p_policy,p_policy->>'createdBy',(p_policy->>'createdAt')::timestamptz);
        IF p_expected_policy_revision=0 THEN
          INSERT INTO ecommerce_investigation_schedule_policy_head(
            org_id,project_id,schedule_policy_id,current_revision,case_id,analysis_type,enabled,
            content_hash,authority_data,updated_at)
          VALUES(v_org,v_project,p_schedule_policy_id,1,p_case_id,p_policy->>'analysisType',
            (p_policy->>'enabled')::boolean,p_policy->>'contentHash',p_policy,(p_policy->>'createdAt')::timestamptz);
        ELSE
          UPDATE ecommerce_investigation_schedule_policy_head SET current_revision=p_expected_policy_revision+1,
            enabled=(p_policy->>'enabled')::boolean,content_hash=p_policy->>'contentHash',
            authority_data=p_policy,updated_at=(p_policy->>'createdAt')::timestamptz
          WHERE org_id=v_org AND project_id=v_project AND schedule_policy_id=p_schedule_policy_id;
        END IF;
        INSERT INTO ecommerce_investigation_case_revision(
          org_id,project_id,case_id,revision,version,prior_revision,content_hash,lifecycle,
          analysis_type,channel_id,business_entity_id,entity_channel_binding_id,idempotency_key,
          request_hash,authority_data,created_by,created_at)
        VALUES(v_org,v_project,p_case_id,p_expected_case_version+1,p_expected_case_version+1,
          p_expected_case_version,p_case->>'contentHash',v_case_prior.lifecycle,v_case_prior.analysis_type,
          v_case_prior.channel_id,v_case_prior.business_entity_id,v_case_prior.entity_channel_binding_id,
          p_idempotency_key,p_request_hash,p_case,p_case->>'createdBy',(p_case->>'createdAt')::timestamptz);
        UPDATE ecommerce_investigation_case_head SET current_revision=p_expected_case_version+1,
          version=p_expected_case_version+1,updated_at=(p_case->>'createdAt')::timestamptz
        WHERE org_id=v_org AND project_id=v_project AND case_id=p_case_id;
        INSERT INTO ecommerce_investigation_schedule_policy_command_receipt(
          org_id,project_id,receipt_id,operation,idempotency_key,request_hash,schedule_policy_id,
          expected_policy_revision,result_policy_revision,case_id,expected_case_version,
          result_case_revision,policy_authority,case_authority)
        VALUES(v_org,v_project,gen_random_uuid()::text,'business_investigation_schedule_policy.put',
          p_idempotency_key,p_request_hash,p_schedule_policy_id,p_expected_policy_revision,
          p_expected_policy_revision+1,p_case_id,p_expected_case_version,p_expected_case_version+1,p_policy,p_case);
        RETURN QUERY SELECT p_policy,p_case,false;
      END $$""")
    op.execute(f"REVOKE ALL ON FUNCTION ecommerce_investigation_schedule_policy_put_biw8_001{SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION ecommerce_investigation_schedule_policy_put_biw8_001{SIGNATURE} TO aos_runtime")


def downgrade() -> None:
    op.execute("""DO $$ BEGIN IF EXISTS(SELECT 1 FROM ecommerce_investigation_schedule_policy_revision LIMIT 1)
      OR EXISTS(SELECT 1 FROM ecommerce_investigation_schedule_policy_command_receipt LIMIT 1)
      THEN RAISE EXCEPTION 'cannot downgrade biw8_001 with SchedulePolicy authority' USING ERRCODE='55000';END IF;END $$""")
    op.execute(f"DROP FUNCTION ecommerce_investigation_schedule_policy_put_biw8_001{SIGNATURE}")
    op.execute("DROP TABLE ecommerce_investigation_schedule_policy_command_receipt")
    op.execute("DROP TABLE ecommerce_investigation_schedule_policy_revision")
    op.execute("DROP TABLE ecommerce_investigation_schedule_policy_head")
