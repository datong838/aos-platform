"""Extend canonical Run state with waiting and reconciliation. Revision ID: biw4_007."""

from collections.abc import Sequence

from alembic import op


revision: str = "biw4_007"
down_revision: str | Sequence[str] | None = "biw4_006"
branch_labels = depends_on = None
TRANSITION_SIGNATURE = "(text,bigint,text,text,text,jsonb)"


def upgrade() -> None:
    op.execute("ALTER TABLE ecommerce_investigation_run_state_head DROP CONSTRAINT ecommerce_investigation_run_state_head_lifecycle_check")
    op.execute("ALTER TABLE ecommerce_investigation_run_state_head DROP CONSTRAINT ecommerce_investigation_run_state_head_control_check")
    op.execute("ALTER TABLE ecommerce_investigation_run_state_revision DROP CONSTRAINT ecommerce_investigation_run_state_revision_lifecycle_check")
    op.execute("ALTER TABLE ecommerce_investigation_run_state_revision DROP CONSTRAINT ecommerce_investigation_run_state_revision_control_check")
    for table in ("ecommerce_investigation_run_state_head", "ecommerce_investigation_run_state_revision"):
        op.execute(f"ALTER TABLE {table} ADD COLUMN pending_requirement_ref JSONB")
        op.execute(f"ALTER TABLE {table} ADD COLUMN uncertain_command JSONB")
        op.execute(f"""ALTER TABLE {table} ADD CONSTRAINT {table}_biw4_007_state_check CHECK(
          lifecycle IN('PREPARING','WAITING_DATA')
          AND control IN('RUNNING','PAUSED','UNKNOWN','RECONCILING','CANCELLED')
          AND ((lifecycle='PREPARING' AND pending_requirement_ref IS NULL)
            OR (lifecycle='WAITING_DATA' AND jsonb_typeof(pending_requirement_ref)='object'
              AND pending_requirement_ref->>'resourceType'='DataRequirementRevision'
              AND length(BTRIM(pending_requirement_ref->>'resourceId')) BETWEEN 1 AND 240
              AND (pending_requirement_ref->>'revision') ~ '^[1-9][0-9]*$'
              AND pending_requirement_ref->>'contentHash' ~ '^sha256:[0-9a-f]{{64}}$'))
          AND ((control IN('UNKNOWN','RECONCILING') AND jsonb_typeof(uncertain_command)='object'
              AND length(BTRIM(uncertain_command->>'commandId')) BETWEEN 1 AND 200
              AND uncertain_command->>'operation' ~ '^[a-z][a-z0-9_.-]{{1,119}}$'
              AND uncertain_command->>'requestHash' ~ '^sha256:[0-9a-f]{{64}}$')
            OR (control NOT IN('UNKNOWN','RECONCILING') AND uncertain_command IS NULL)))""")

    op.execute("""CREATE TABLE ecommerce_investigation_run_state_transition_receipt(
      org_id TEXT NOT NULL,project_id TEXT NOT NULL,receipt_id TEXT NOT NULL,run_id TEXT NOT NULL,
      operation TEXT NOT NULL,idempotency_key TEXT NOT NULL,request_hash TEXT NOT NULL,
      expected_version BIGINT NOT NULL,result_version BIGINT NOT NULL,authority_data JSONB NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),PRIMARY KEY(org_id,project_id,receipt_id),
      UNIQUE(org_id,project_id,operation,idempotency_key),
      FOREIGN KEY(org_id,project_id,run_id,result_version)
        REFERENCES ecommerce_investigation_run_state_revision(org_id,project_id,run_id,version),
      CHECK(operation IN('business_investigation_run.request_data','business_investigation_run.mark_unknown','business_investigation_run.begin_reconcile')),
      CHECK(expected_version>=1),CHECK(result_version=expected_version+1),
      CHECK(request_hash ~ '^sha256:[0-9a-f]{64}$'),CHECK(jsonb_typeof(authority_data)='object'))""")
    op.execute("""CREATE TRIGGER trg_ecommerce_investigation_run_state_transition_receipt_immutable
      BEFORE UPDATE OR DELETE ON ecommerce_investigation_run_state_transition_receipt FOR EACH ROW
      EXECUTE FUNCTION guard_ecommerce_investigation_run_biw4_002()""")
    op.execute("ALTER TABLE ecommerce_investigation_run_state_transition_receipt ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE ecommerce_investigation_run_state_transition_receipt FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY tenant_scope_ecommerce_investigation_run_state_transition_receipt_biw4_007
      ON ecommerce_investigation_run_state_transition_receipt TO aos_runtime
      USING(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))
      WITH CHECK(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
    op.execute("GRANT SELECT ON ecommerce_investigation_run_state_transition_receipt TO aos_runtime")
    op.execute("REVOKE INSERT,UPDATE,DELETE,TRUNCATE ON ecommerce_investigation_run_state_transition_receipt FROM aos_runtime")

    op.execute("ALTER TABLE ecommerce_investigation_run_event DROP CONSTRAINT ecommerce_investigation_run_event_event_type_check")
    op.execute("""ALTER TABLE ecommerce_investigation_run_event ADD CONSTRAINT
      ecommerce_investigation_run_event_event_type_check CHECK(event_type IN(
        'RUN_REQUESTED','RUN_PAUSED','RUN_RESUMED','RUN_CANCELLED',
        'RUN_WAITING_DATA','RUN_UNKNOWN','RUN_RECONCILING'))""")

    op.execute("""CREATE FUNCTION ecommerce_investigation_run_state_transition_biw4_007(
      p_run_id text,p_expected_version bigint,p_operation text,p_idempotency_key text,
      p_request_hash text,p_payload jsonb)
      RETURNS TABLE(authority_data jsonb,replayed boolean)
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
      DECLARE v_org text:=NULLIF(current_setting('aos.org_id',true),'');
        v_project text:=NULLIF(current_setting('aos.project_id',true),'');v_existing record;
        v_head record;v_event_type text;v_event_id text:=gen_random_uuid()::text;
        v_event_data jsonb;v_event_hash text;v_target_lifecycle text:=p_payload->>'lifecycle';
        v_target_control text:=p_payload->>'control';
        v_pending jsonb:=NULLIF(p_payload->'pendingRequirementRef','null'::jsonb);
        v_uncertain jsonb:=NULLIF(p_payload->'uncertainCommand','null'::jsonb);
      BEGIN
        SELECT r.authority_data,r.request_hash,r.run_id INTO v_existing
          FROM ecommerce_investigation_run_state_transition_receipt r
          WHERE r.org_id=v_org AND r.project_id=v_project
            AND r.operation=p_operation AND r.idempotency_key=p_idempotency_key;
        IF FOUND THEN
          IF v_existing.request_hash<>p_request_hash OR v_existing.run_id<>p_run_id THEN
            RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='Run state idempotency conflict';END IF;
          RETURN QUERY SELECT v_existing.authority_data,true;RETURN;
        END IF;
        IF v_org IS NULL OR v_project IS NULL OR p_expected_version<1
          OR p_operation NOT IN('business_investigation_run.request_data','business_investigation_run.mark_unknown','business_investigation_run.begin_reconcile')
          OR length(BTRIM(p_run_id)) NOT BETWEEN 1 AND 200
          OR length(BTRIM(p_idempotency_key)) NOT BETWEEN 1 AND 200
          OR p_request_hash !~ '^sha256:[0-9a-f]{64}$' OR jsonb_typeof(p_payload)<>'object'
        THEN RAISE EXCEPTION USING ERRCODE='BO001',MESSAGE='Run state transition request invalid';END IF;
        SELECT * INTO v_head FROM ecommerce_investigation_run_state_head h
          WHERE h.org_id=v_org AND h.project_id=v_project AND h.run_id=p_run_id FOR UPDATE;
        IF NOT FOUND OR v_head.current_version<>p_expected_version THEN
          RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='Run expected version conflict';END IF;
        IF p_payload#>>'{tenant,orgId}'<>v_org OR p_payload#>>'{tenant,projectId}'<>v_project
          OR p_payload->>'runId'<>p_run_id OR (p_payload->>'version')::bigint<>p_expected_version+1
          OR (p_payload->>'eventSequence')::bigint<>v_head.current_event_sequence+1
          OR p_payload#>>'{priorRef,resourceType}'<>'BusinessInvestigationRunStateRevision'
          OR p_payload#>>'{priorRef,resourceId}'<>p_run_id
          OR (p_payload#>>'{priorRef,revision}')::bigint<>p_expected_version
          OR p_payload#>>'{priorRef,contentHash}'<>v_head.content_hash
          OR p_payload->>'contentHash' !~ '^sha256:[0-9a-f]{64}$'
        THEN RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='Run state successor rejected';END IF;

        IF p_operation='business_investigation_run.request_data' THEN
          IF v_head.lifecycle<>'PREPARING' OR v_head.control<>'RUNNING'
            OR v_target_lifecycle<>'WAITING_DATA' OR v_target_control<>'RUNNING'
            OR v_pending->>'resourceType'<>'DataRequirementRevision'
            OR length(BTRIM(v_pending->>'resourceId')) NOT BETWEEN 1 AND 240
            OR v_pending->>'contentHash' !~ '^sha256:[0-9a-f]{64}$'
            OR NOT EXISTS(SELECT 1 FROM data_requirement_revision d
              WHERE d.org_id=v_org AND d.project_id=v_project
                AND d.requirement_id=v_pending->>'resourceId'
                AND d.revision=(v_pending->>'revision')::bigint
                AND 'sha256:'||d.content_hash=v_pending->>'contentHash')
            OR v_uncertain IS NOT NULL
          THEN RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='Run request-data transition rejected';END IF;
          v_event_type:='RUN_WAITING_DATA';
        ELSIF p_operation='business_investigation_run.mark_unknown' THEN
          IF v_head.control NOT IN('RUNNING','PAUSED') OR v_target_control<>'UNKNOWN'
            OR v_target_lifecycle<>v_head.lifecycle OR v_pending IS DISTINCT FROM v_head.pending_requirement_ref
            OR jsonb_typeof(v_uncertain)<>'object'
          THEN RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='Run UNKNOWN transition rejected';END IF;
          v_event_type:='RUN_UNKNOWN';
        ELSE
          IF v_head.control<>'UNKNOWN' OR v_target_control<>'RECONCILING'
            OR v_target_lifecycle<>v_head.lifecycle OR v_pending IS DISTINCT FROM v_head.pending_requirement_ref
            OR v_uncertain IS DISTINCT FROM v_head.uncertain_command
          THEN RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='Run RECONCILING transition rejected';END IF;
          v_event_type:='RUN_RECONCILING';
        END IF;

        INSERT INTO ecommerce_investigation_run_state_revision(
          org_id,project_id,run_id,version,prior_version,lifecycle,control,event_sequence,
          content_hash,authority_data,created_by,created_at,pending_requirement_ref,uncertain_command)
        VALUES(v_org,v_project,p_run_id,p_expected_version+1,p_expected_version,v_target_lifecycle,
          v_target_control,v_head.current_event_sequence+1,p_payload->>'contentHash',p_payload,
          p_payload->>'createdBy',(p_payload->>'createdAt')::timestamptz,v_pending,v_uncertain);
        UPDATE ecommerce_investigation_run_state_head SET current_version=p_expected_version+1,
          lifecycle=v_target_lifecycle,control=v_target_control,
          current_event_sequence=current_event_sequence+1,content_hash=p_payload->>'contentHash',
          authority_data=p_payload,updated_at=(p_payload->>'createdAt')::timestamptz,
          pending_requirement_ref=v_pending,uncertain_command=v_uncertain
          WHERE org_id=v_org AND project_id=v_project AND run_id=p_run_id;
        v_event_data:=jsonb_build_object(
          'schemaVersion','aos.ecommerce.business-investigation-run-event/v1','tenant',p_payload->'tenant',
          'eventId',v_event_id,'runStateRef',jsonb_build_object(
            'resourceType','BusinessInvestigationRunStateRevision','resourceId',p_run_id,
            'revision',p_expected_version+1,'contentHash',p_payload->>'contentHash'),
          'sequence',v_head.current_event_sequence+1,'eventType',v_event_type,
          'occurredAt',p_payload->'createdAt',
          'nonClaims',jsonb_build_array('NO_RETRY','NO_RECONCILE_SUCCESS','NO_EXTERNAL_EFFECT'));
        v_event_hash:='sha256:'||encode(public.digest(convert_to(v_event_data::text,'UTF8'),'sha256'),'hex');
        INSERT INTO ecommerce_investigation_run_event(
          org_id,project_id,event_id,run_id,sequence,event_type,content_hash,event_data,occurred_at)
        VALUES(v_org,v_project,v_event_id,p_run_id,v_head.current_event_sequence+1,v_event_type,
          v_event_hash,v_event_data,(p_payload->>'createdAt')::timestamptz);
        INSERT INTO ecommerce_investigation_run_state_transition_receipt(
          org_id,project_id,receipt_id,run_id,operation,idempotency_key,request_hash,
          expected_version,result_version,authority_data)
        VALUES(v_org,v_project,gen_random_uuid()::text,p_run_id,p_operation,p_idempotency_key,
          p_request_hash,p_expected_version,p_expected_version+1,p_payload);
        RETURN QUERY SELECT p_payload,false;
      END $$""")
    op.execute(f"REVOKE ALL ON FUNCTION ecommerce_investigation_run_state_transition_biw4_007{TRANSITION_SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION ecommerce_investigation_run_state_transition_biw4_007{TRANSITION_SIGNATURE} TO aos_runtime")


def downgrade() -> None:
    op.execute("""DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM ecommerce_investigation_run_state_transition_receipt LIMIT 1)
        OR EXISTS(SELECT 1 FROM ecommerce_investigation_run_state_revision
          WHERE lifecycle<>'PREPARING' OR control IN('UNKNOWN','RECONCILING')
            OR pending_requirement_ref IS NOT NULL OR uncertain_command IS NOT NULL LIMIT 1)
      THEN RAISE EXCEPTION 'cannot downgrade biw4_007 with extended Run state authority' USING ERRCODE='55000';END IF;
    END $$""")
    op.execute(f"DROP FUNCTION ecommerce_investigation_run_state_transition_biw4_007{TRANSITION_SIGNATURE}")
    op.execute("ALTER TABLE ecommerce_investigation_run_event DROP CONSTRAINT ecommerce_investigation_run_event_event_type_check")
    op.execute("""ALTER TABLE ecommerce_investigation_run_event ADD CONSTRAINT
      ecommerce_investigation_run_event_event_type_check
      CHECK(event_type IN('RUN_REQUESTED','RUN_PAUSED','RUN_RESUMED','RUN_CANCELLED'))""")
    op.execute("DROP TABLE ecommerce_investigation_run_state_transition_receipt")
    for table in ("ecommerce_investigation_run_state_revision", "ecommerce_investigation_run_state_head"):
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {table}_biw4_007_state_check")
        op.execute(f"ALTER TABLE {table} DROP COLUMN uncertain_command")
        op.execute(f"ALTER TABLE {table} DROP COLUMN pending_requirement_ref")
    op.execute("ALTER TABLE ecommerce_investigation_run_state_head ADD CONSTRAINT ecommerce_investigation_run_state_head_lifecycle_check CHECK(lifecycle='PREPARING')")
    op.execute("ALTER TABLE ecommerce_investigation_run_state_head ADD CONSTRAINT ecommerce_investigation_run_state_head_control_check CHECK(control IN('RUNNING','PAUSED','CANCELLED'))")
    op.execute("ALTER TABLE ecommerce_investigation_run_state_revision ADD CONSTRAINT ecommerce_investigation_run_state_revision_lifecycle_check CHECK(lifecycle='PREPARING')")
    op.execute("ALTER TABLE ecommerce_investigation_run_state_revision ADD CONSTRAINT ecommerce_investigation_run_state_revision_control_check CHECK(control IN('RUNNING','PAUSED','CANCELLED'))")
