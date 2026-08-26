"""Add canonical Case lifecycle and Run control state. Revision ID: biw4_006."""

from collections.abc import Sequence

from alembic import op


revision: str = "biw4_006"
down_revision: str | Sequence[str] | None = "biw4_005"
branch_labels = depends_on = None
CASE_SIGNATURE = "(text,bigint,text,text,jsonb)"
RUN_SIGNATURE = "(text,bigint,text,text,jsonb)"


def upgrade() -> None:
    op.execute("""CREATE TABLE ecommerce_investigation_case_lifecycle_receipt(
      org_id TEXT NOT NULL,project_id TEXT NOT NULL,receipt_id TEXT NOT NULL,case_id TEXT NOT NULL,
      operation TEXT NOT NULL,idempotency_key TEXT NOT NULL,request_hash TEXT NOT NULL,
      expected_version BIGINT NOT NULL,result_revision BIGINT NOT NULL,authority_data JSONB NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),PRIMARY KEY(org_id,project_id,receipt_id),
      UNIQUE(org_id,project_id,operation,idempotency_key),
      FOREIGN KEY(org_id,project_id,case_id,result_revision)
        REFERENCES ecommerce_investigation_case_revision(org_id,project_id,case_id,revision),
      CHECK(operation='business_investigation_case.transition'),CHECK(expected_version>=1),
      CHECK(result_revision=expected_version+1),CHECK(request_hash ~ '^sha256:[0-9a-f]{64}$'),
      CHECK(jsonb_typeof(authority_data)='object'))""")
    op.execute("""CREATE TRIGGER trg_ecommerce_investigation_case_lifecycle_receipt_immutable
      BEFORE UPDATE OR DELETE ON ecommerce_investigation_case_lifecycle_receipt FOR EACH ROW
      EXECUTE FUNCTION guard_ecommerce_investigation_case_biw4_001()""")

    op.execute("""CREATE TABLE ecommerce_investigation_run_state_head(
      org_id TEXT NOT NULL,project_id TEXT NOT NULL,run_id TEXT NOT NULL,current_version BIGINT NOT NULL,
      lifecycle TEXT NOT NULL,control TEXT NOT NULL,current_event_sequence BIGINT NOT NULL,
      content_hash TEXT NOT NULL,authority_data JSONB NOT NULL,updated_at TIMESTAMPTZ NOT NULL,
      PRIMARY KEY(org_id,project_id,run_id),
      FOREIGN KEY(org_id,project_id,run_id) REFERENCES ecommerce_investigation_run(org_id,project_id,run_id),
      CHECK(current_version>=1),CHECK(lifecycle='PREPARING'),
      CHECK(control IN('RUNNING','PAUSED','CANCELLED')),CHECK(current_event_sequence>=1),
      CHECK(content_hash ~ '^sha256:[0-9a-f]{64}$'),CHECK(jsonb_typeof(authority_data)='object'))""")
    op.execute("""CREATE TABLE ecommerce_investigation_run_state_revision(
      org_id TEXT NOT NULL,project_id TEXT NOT NULL,run_id TEXT NOT NULL,version BIGINT NOT NULL,
      prior_version BIGINT,lifecycle TEXT NOT NULL,control TEXT NOT NULL,event_sequence BIGINT NOT NULL,
      content_hash TEXT NOT NULL,authority_data JSONB NOT NULL,created_by TEXT NOT NULL,
      created_at TIMESTAMPTZ NOT NULL,PRIMARY KEY(org_id,project_id,run_id,version),
      FOREIGN KEY(org_id,project_id,run_id) REFERENCES ecommerce_investigation_run(org_id,project_id,run_id),
      CHECK((version=1 AND prior_version IS NULL) OR (version>1 AND prior_version=version-1)),
      CHECK(lifecycle='PREPARING'),CHECK(control IN('RUNNING','PAUSED','CANCELLED')),
      CHECK(event_sequence=version),CHECK(content_hash ~ '^sha256:[0-9a-f]{64}$'),
      CHECK(jsonb_typeof(authority_data)='object'))""")
    op.execute("""CREATE TABLE ecommerce_investigation_run_control_receipt(
      org_id TEXT NOT NULL,project_id TEXT NOT NULL,receipt_id TEXT NOT NULL,run_id TEXT NOT NULL,
      operation TEXT NOT NULL,idempotency_key TEXT NOT NULL,request_hash TEXT NOT NULL,
      expected_version BIGINT NOT NULL,result_version BIGINT NOT NULL,authority_data JSONB NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),PRIMARY KEY(org_id,project_id,receipt_id),
      UNIQUE(org_id,project_id,operation,idempotency_key),
      FOREIGN KEY(org_id,project_id,run_id,result_version)
        REFERENCES ecommerce_investigation_run_state_revision(org_id,project_id,run_id,version),
      CHECK(operation='business_investigation_run.control'),CHECK(expected_version>=1),
      CHECK(result_version=expected_version+1),CHECK(request_hash ~ '^sha256:[0-9a-f]{64}$'),
      CHECK(jsonb_typeof(authority_data)='object'))""")

    op.execute("""CREATE FUNCTION ecommerce_investigation_run_state_init_biw4_006()
      RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
      DECLARE v_base jsonb;v_hash text;v_state jsonb;
      BEGIN
        v_base:=jsonb_build_object(
          'schemaVersion','aos.ecommerce.business-investigation-run-state/v1',
          'tenant',jsonb_build_object('orgId',NEW.org_id,'projectId',NEW.project_id),
          'runId',NEW.run_id,'version',1,'lifecycle','PREPARING','control','RUNNING',
          'eventSequence',1,'createdBy',NEW.created_by,'createdAt',NEW.created_at);
        v_hash:='sha256:'||encode(public.digest(convert_to(v_base::text,'UTF8'),'sha256'),'hex');
        v_state:=v_base||jsonb_build_object('contentHash',v_hash);
        INSERT INTO ecommerce_investigation_run_state_revision(
          org_id,project_id,run_id,version,prior_version,lifecycle,control,event_sequence,
          content_hash,authority_data,created_by,created_at)
        VALUES(NEW.org_id,NEW.project_id,NEW.run_id,1,NULL,'PREPARING','RUNNING',1,
          v_hash,v_state,NEW.created_by,NEW.created_at);
        INSERT INTO ecommerce_investigation_run_state_head(
          org_id,project_id,run_id,current_version,lifecycle,control,current_event_sequence,
          content_hash,authority_data,updated_at)
        VALUES(NEW.org_id,NEW.project_id,NEW.run_id,1,'PREPARING','RUNNING',1,
          v_hash,v_state,NEW.created_at);
        RETURN NEW;
      END $$""")
    op.execute("""INSERT INTO ecommerce_investigation_run_state_revision(
      org_id,project_id,run_id,version,prior_version,lifecycle,control,event_sequence,
      content_hash,authority_data,created_by,created_at)
      SELECT r.org_id,r.project_id,r.run_id,1,NULL,'PREPARING','RUNNING',1,
        'sha256:'||encode(public.digest(convert_to((jsonb_build_object(
          'schemaVersion','aos.ecommerce.business-investigation-run-state/v1',
          'tenant',jsonb_build_object('orgId',r.org_id,'projectId',r.project_id),
          'runId',r.run_id,'version',1,'lifecycle','PREPARING','control','RUNNING',
          'eventSequence',1,'createdBy',r.created_by,'createdAt',r.created_at))::text,'UTF8'),'sha256'),'hex'),
        jsonb_build_object(
          'schemaVersion','aos.ecommerce.business-investigation-run-state/v1',
          'tenant',jsonb_build_object('orgId',r.org_id,'projectId',r.project_id),
          'runId',r.run_id,'version',1,'lifecycle','PREPARING','control','RUNNING',
          'eventSequence',1,'createdBy',r.created_by,'createdAt',r.created_at,
          'contentHash','sha256:'||encode(public.digest(convert_to((jsonb_build_object(
            'schemaVersion','aos.ecommerce.business-investigation-run-state/v1',
            'tenant',jsonb_build_object('orgId',r.org_id,'projectId',r.project_id),
            'runId',r.run_id,'version',1,'lifecycle','PREPARING','control','RUNNING',
            'eventSequence',1,'createdBy',r.created_by,'createdAt',r.created_at))::text,'UTF8'),'sha256'),'hex')),
        r.created_by,r.created_at FROM ecommerce_investigation_run r""")
    op.execute("""INSERT INTO ecommerce_investigation_run_state_head(
      org_id,project_id,run_id,current_version,lifecycle,control,current_event_sequence,
      content_hash,authority_data,updated_at)
      SELECT org_id,project_id,run_id,version,lifecycle,control,event_sequence,
        content_hash,authority_data,created_at FROM ecommerce_investigation_run_state_revision WHERE version=1""")
    op.execute("""CREATE TRIGGER trg_ecommerce_investigation_run_state_init_biw4_006
      AFTER INSERT ON ecommerce_investigation_run FOR EACH ROW
      EXECUTE FUNCTION ecommerce_investigation_run_state_init_biw4_006()""")

    for table in (
        "ecommerce_investigation_case_lifecycle_receipt",
        "ecommerce_investigation_run_state_head",
        "ecommerce_investigation_run_state_revision",
        "ecommerce_investigation_run_control_receipt",
    ):
        if table in {
            "ecommerce_investigation_run_state_revision",
            "ecommerce_investigation_run_control_receipt",
        }:
            op.execute(f"""CREATE TRIGGER trg_{table}_immutable BEFORE UPDATE OR DELETE ON {table}
              FOR EACH ROW EXECUTE FUNCTION guard_ecommerce_investigation_run_biw4_002()""")
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""CREATE POLICY tenant_scope_{table}_biw4_006 ON {table} TO aos_runtime
          USING(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))
          WITH CHECK(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
        op.execute(f"GRANT SELECT ON {table} TO aos_runtime")
        op.execute(f"REVOKE INSERT,UPDATE,DELETE,TRUNCATE ON {table} FROM aos_runtime")

    op.execute("""ALTER TABLE ecommerce_investigation_run_event
      DROP CONSTRAINT ecommerce_investigation_run_event_event_type_check""")
    op.execute("""ALTER TABLE ecommerce_investigation_run_event ADD CONSTRAINT
      ecommerce_investigation_run_event_event_type_check
      CHECK(event_type IN('RUN_REQUESTED','RUN_PAUSED','RUN_RESUMED','RUN_CANCELLED'))""")

    op.execute("""CREATE FUNCTION ecommerce_investigation_case_transition_biw4_006(
      p_case_id text,p_expected_version bigint,p_idempotency_key text,p_request_hash text,p_payload jsonb)
      RETURNS TABLE(authority_data jsonb,replayed boolean)
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
      DECLARE v_org text:=NULLIF(current_setting('aos.org_id',true),'');
        v_project text:=NULLIF(current_setting('aos.project_id',true),'');v_existing record;
        v_head record;v_prior record;v_target text:=p_payload->>'lifecycle';
      BEGIN
        SELECT r.authority_data,r.request_hash,r.case_id INTO v_existing
          FROM ecommerce_investigation_case_lifecycle_receipt r
          WHERE r.org_id=v_org AND r.project_id=v_project
            AND r.operation='business_investigation_case.transition' AND r.idempotency_key=p_idempotency_key;
        IF FOUND THEN
          IF v_existing.request_hash<>p_request_hash OR v_existing.case_id<>p_case_id THEN
            RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='Case lifecycle idempotency conflict';END IF;
          RETURN QUERY SELECT v_existing.authority_data,true;RETURN;
        END IF;
        IF v_org IS NULL OR v_project IS NULL OR p_expected_version<1
          OR length(BTRIM(p_case_id)) NOT BETWEEN 1 AND 200
          OR length(BTRIM(p_idempotency_key)) NOT BETWEEN 1 AND 200
          OR p_request_hash !~ '^sha256:[0-9a-f]{64}$' OR jsonb_typeof(p_payload)<>'object'
        THEN RAISE EXCEPTION USING ERRCODE='BO001',MESSAGE='Case lifecycle request invalid';END IF;
        SELECT * INTO v_head FROM ecommerce_investigation_case_head h
          WHERE h.org_id=v_org AND h.project_id=v_project AND h.case_id=p_case_id FOR UPDATE;
        IF NOT FOUND OR v_head.version<>p_expected_version THEN
          RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='Case expected version conflict';END IF;
        SELECT * INTO v_prior FROM ecommerce_investigation_case_revision r
          WHERE r.org_id=v_org AND r.project_id=v_project AND r.case_id=p_case_id
            AND r.revision=v_head.current_revision;
        IF p_payload#>>'{tenant,orgId}'<>v_org OR p_payload#>>'{tenant,projectId}'<>v_project
          OR p_payload->>'caseId'<>p_case_id OR (p_payload->>'revision')::bigint<>p_expected_version+1
          OR (p_payload->>'version')::bigint<>p_expected_version+1
          OR p_payload#>>'{priorRef,resourceType}'<>'BusinessInvestigationCaseRevision'
          OR p_payload#>>'{priorRef,resourceId}'<>p_case_id
          OR (p_payload#>>'{priorRef,revision}')::bigint<>p_expected_version
          OR p_payload#>>'{priorRef,contentHash}'<>v_prior.content_hash
          OR p_payload->>'contentHash' !~ '^sha256:[0-9a-f]{64}$'
          OR (p_payload-ARRAY['revision','version','priorRef','contentHash','lifecycle','createdBy','createdAt'])
             <>(v_prior.authority_data-ARRAY['revision','version','priorRef','contentHash','lifecycle','createdBy','createdAt'])
          OR NOT ((v_head.lifecycle='DRAFT' AND v_target='ACTIVE')
            OR (v_head.lifecycle='ACTIVE' AND v_target IN('ARCHIVED','CLOSED'))
            OR (v_head.lifecycle='ARCHIVED' AND v_target IN('ACTIVE','CLOSED')))
        THEN RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='Case lifecycle transition rejected';END IF;
        INSERT INTO ecommerce_investigation_case_revision(
          org_id,project_id,case_id,revision,version,prior_revision,content_hash,lifecycle,
          analysis_type,channel_id,business_entity_id,entity_channel_binding_id,idempotency_key,
          request_hash,authority_data,created_by,created_at)
        VALUES(v_org,v_project,p_case_id,p_expected_version+1,p_expected_version+1,p_expected_version,
          p_payload->>'contentHash',v_target,v_prior.analysis_type,v_prior.channel_id,v_prior.business_entity_id,
          v_prior.entity_channel_binding_id,p_idempotency_key,p_request_hash,p_payload,
          p_payload->>'createdBy',(p_payload->>'createdAt')::timestamptz);
        UPDATE ecommerce_investigation_case_head SET current_revision=p_expected_version+1,
          version=p_expected_version+1,lifecycle=v_target,updated_at=(p_payload->>'createdAt')::timestamptz
          WHERE org_id=v_org AND project_id=v_project AND case_id=p_case_id;
        INSERT INTO ecommerce_investigation_case_lifecycle_receipt(
          org_id,project_id,receipt_id,case_id,operation,idempotency_key,request_hash,
          expected_version,result_revision,authority_data)
        VALUES(v_org,v_project,gen_random_uuid()::text,p_case_id,'business_investigation_case.transition',
          p_idempotency_key,p_request_hash,p_expected_version,p_expected_version+1,p_payload);
        RETURN QUERY SELECT p_payload,false;
      END $$""")

    op.execute("""CREATE FUNCTION ecommerce_investigation_run_control_biw4_006(
      p_run_id text,p_expected_version bigint,p_idempotency_key text,p_request_hash text,p_payload jsonb)
      RETURNS TABLE(authority_data jsonb,replayed boolean)
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
      DECLARE v_org text:=NULLIF(current_setting('aos.org_id',true),'');
        v_project text:=NULLIF(current_setting('aos.project_id',true),'');v_existing record;
        v_head record;v_target text:=p_payload->>'control';v_event_type text;v_event_id text:=gen_random_uuid()::text;
        v_event_data jsonb;v_event_hash text;
      BEGIN
        SELECT r.authority_data,r.request_hash,r.run_id INTO v_existing
          FROM ecommerce_investigation_run_control_receipt r
          WHERE r.org_id=v_org AND r.project_id=v_project
            AND r.operation='business_investigation_run.control' AND r.idempotency_key=p_idempotency_key;
        IF FOUND THEN
          IF v_existing.request_hash<>p_request_hash OR v_existing.run_id<>p_run_id THEN
            RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='Run control idempotency conflict';END IF;
          RETURN QUERY SELECT v_existing.authority_data,true;RETURN;
        END IF;
        IF v_org IS NULL OR v_project IS NULL OR p_expected_version<1
          OR length(BTRIM(p_run_id)) NOT BETWEEN 1 AND 200
          OR length(BTRIM(p_idempotency_key)) NOT BETWEEN 1 AND 200
          OR p_request_hash !~ '^sha256:[0-9a-f]{64}$' OR jsonb_typeof(p_payload)<>'object'
        THEN RAISE EXCEPTION USING ERRCODE='BO001',MESSAGE='Run control request invalid';END IF;
        SELECT * INTO v_head FROM ecommerce_investigation_run_state_head h
          WHERE h.org_id=v_org AND h.project_id=v_project AND h.run_id=p_run_id FOR UPDATE;
        IF NOT FOUND OR v_head.current_version<>p_expected_version THEN
          RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='Run expected version conflict';END IF;
        IF p_payload#>>'{tenant,orgId}'<>v_org OR p_payload#>>'{tenant,projectId}'<>v_project
          OR p_payload->>'runId'<>p_run_id OR (p_payload->>'version')::bigint<>p_expected_version+1
          OR p_payload->>'lifecycle'<>'PREPARING' OR (p_payload->>'eventSequence')::bigint<>v_head.current_event_sequence+1
          OR p_payload#>>'{priorRef,resourceType}'<>'BusinessInvestigationRunStateRevision'
          OR p_payload#>>'{priorRef,resourceId}'<>p_run_id
          OR (p_payload#>>'{priorRef,revision}')::bigint<>p_expected_version
          OR p_payload#>>'{priorRef,contentHash}'<>v_head.content_hash
          OR p_payload->>'contentHash' !~ '^sha256:[0-9a-f]{64}$'
          OR NOT ((v_head.control='RUNNING' AND v_target IN('PAUSED','CANCELLED'))
            OR (v_head.control='PAUSED' AND v_target IN('RUNNING','CANCELLED')))
        THEN RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='Run control transition rejected';END IF;
        v_event_type:=CASE v_target WHEN 'PAUSED' THEN 'RUN_PAUSED'
          WHEN 'RUNNING' THEN 'RUN_RESUMED' ELSE 'RUN_CANCELLED' END;
        INSERT INTO ecommerce_investigation_run_state_revision(
          org_id,project_id,run_id,version,prior_version,lifecycle,control,event_sequence,
          content_hash,authority_data,created_by,created_at)
        VALUES(v_org,v_project,p_run_id,p_expected_version+1,p_expected_version,'PREPARING',v_target,
          v_head.current_event_sequence+1,p_payload->>'contentHash',p_payload,
          p_payload->>'createdBy',(p_payload->>'createdAt')::timestamptz);
        UPDATE ecommerce_investigation_run_state_head SET current_version=p_expected_version+1,
          lifecycle='PREPARING',control=v_target,current_event_sequence=current_event_sequence+1,
          content_hash=p_payload->>'contentHash',authority_data=p_payload,
          updated_at=(p_payload->>'createdAt')::timestamptz
          WHERE org_id=v_org AND project_id=v_project AND run_id=p_run_id;
        v_event_data:=jsonb_build_object(
          'schemaVersion','aos.ecommerce.business-investigation-run-event/v1',
          'tenant',p_payload->'tenant','eventId',v_event_id,
          'runStateRef',jsonb_build_object('resourceType','BusinessInvestigationRunStateRevision',
            'resourceId',p_run_id,'revision',p_expected_version+1,'contentHash',p_payload->>'contentHash'),
          'sequence',v_head.current_event_sequence+1,'eventType',v_event_type,
          'occurredAt',p_payload->'createdAt','nonClaims',jsonb_build_array('NO_AIP_TASKRUN_CONTROL','NO_EXTERNAL_EFFECT'));
        v_event_hash:='sha256:'||encode(public.digest(convert_to(v_event_data::text,'UTF8'),'sha256'),'hex');
        INSERT INTO ecommerce_investigation_run_event(
          org_id,project_id,event_id,run_id,sequence,event_type,content_hash,event_data,occurred_at)
        VALUES(v_org,v_project,v_event_id,p_run_id,v_head.current_event_sequence+1,v_event_type,
          v_event_hash,v_event_data,(p_payload->>'createdAt')::timestamptz);
        IF v_target='CANCELLED' THEN
          DELETE FROM ecommerce_investigation_run_active_slot
            WHERE org_id=v_org AND project_id=v_project AND run_id=p_run_id;
        END IF;
        INSERT INTO ecommerce_investigation_run_control_receipt(
          org_id,project_id,receipt_id,run_id,operation,idempotency_key,request_hash,
          expected_version,result_version,authority_data)
        VALUES(v_org,v_project,gen_random_uuid()::text,p_run_id,'business_investigation_run.control',
          p_idempotency_key,p_request_hash,p_expected_version,p_expected_version+1,p_payload);
        RETURN QUERY SELECT p_payload,false;
      END $$""")

    op.execute(f"REVOKE ALL ON FUNCTION ecommerce_investigation_case_transition_biw4_006{CASE_SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION ecommerce_investigation_case_transition_biw4_006{CASE_SIGNATURE} TO aos_runtime")
    op.execute(f"REVOKE ALL ON FUNCTION ecommerce_investigation_run_control_biw4_006{RUN_SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION ecommerce_investigation_run_control_biw4_006{RUN_SIGNATURE} TO aos_runtime")
    op.execute("REVOKE ALL ON FUNCTION ecommerce_investigation_run_state_init_biw4_006() FROM PUBLIC")


def downgrade() -> None:
    op.execute("""DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM ecommerce_investigation_case_lifecycle_receipt LIMIT 1)
        OR EXISTS(SELECT 1 FROM ecommerce_investigation_run_control_receipt LIMIT 1)
        OR EXISTS(SELECT 1 FROM ecommerce_investigation_run_state_revision LIMIT 1)
      THEN RAISE EXCEPTION 'cannot downgrade biw4_006 with lifecycle authority' USING ERRCODE='55000';END IF;
    END $$""")
    op.execute(f"DROP FUNCTION ecommerce_investigation_run_control_biw4_006{RUN_SIGNATURE}")
    op.execute(f"DROP FUNCTION ecommerce_investigation_case_transition_biw4_006{CASE_SIGNATURE}")
    op.execute("ALTER TABLE ecommerce_investigation_run_event DROP CONSTRAINT ecommerce_investigation_run_event_event_type_check")
    op.execute("ALTER TABLE ecommerce_investigation_run_event ADD CONSTRAINT ecommerce_investigation_run_event_event_type_check CHECK(event_type='RUN_REQUESTED')")
    op.execute("DROP TRIGGER trg_ecommerce_investigation_run_state_init_biw4_006 ON ecommerce_investigation_run")
    op.execute("DROP FUNCTION ecommerce_investigation_run_state_init_biw4_006()")
    op.execute("DROP TABLE ecommerce_investigation_run_control_receipt")
    op.execute("DROP TABLE ecommerce_investigation_run_state_revision")
    op.execute("DROP TABLE ecommerce_investigation_run_state_head")
    op.execute("DROP TABLE ecommerce_investigation_case_lifecycle_receipt")
