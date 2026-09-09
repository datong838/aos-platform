"""Add atomic ecommerce analysis data-resume Run transition."""

from alembic import op


revision = "ar2_011"
down_revision = "ar2_010"
branch_labels = depends_on = None
SIGNATURE = "(text,bigint,text,text,jsonb,jsonb)"


def upgrade() -> None:
    op.execute("""DO $$ DECLARE v_constraint text; BEGIN
      SELECT c.conname INTO v_constraint FROM pg_constraint c
      WHERE c.conrelid='public.ecommerce_investigation_run_state_transition_receipt'::regclass
        AND c.contype='c'
        AND pg_get_constraintdef(c.oid) LIKE '%business_investigation_run.begin_reconcile%';
      IF v_constraint IS NULL THEN
        RAISE EXCEPTION 'Run transition operation constraint is missing';
      END IF;
      EXECUTE format('ALTER TABLE ecommerce_investigation_run_state_transition_receipt DROP CONSTRAINT %I',v_constraint);
    END $$""")
    op.execute("""ALTER TABLE ecommerce_investigation_run_state_transition_receipt
      ADD CONSTRAINT ecommerce_investigation_run_state_transition_operation_ar2_011 CHECK(
        operation IN('business_investigation_run.request_data',
          'business_investigation_run.mark_unknown',
          'business_investigation_run.begin_reconcile',
          'business_investigation_run.resume_after_data'))""")
    op.execute("""ALTER TABLE ecommerce_investigation_run_event
      DROP CONSTRAINT ecommerce_investigation_run_event_event_type_check""")
    op.execute("""ALTER TABLE ecommerce_investigation_run_event ADD CONSTRAINT
      ecommerce_investigation_run_event_event_type_check CHECK(event_type IN(
        'RUN_REQUESTED','RUN_PAUSED','RUN_RESUMED','RUN_CANCELLED',
        'RUN_WAITING_DATA','RUN_UNKNOWN','RUN_RECONCILING','RUN_DATA_RESUMED'))""")

    op.execute("""CREATE FUNCTION ecommerce_investigation_run_data_resume_ar2_011(
      p_run_id text,p_expected_version bigint,p_idempotency_key text,p_request_hash text,
      p_requirement_ref jsonb,p_payload jsonb)
      RETURNS TABLE(authority_data jsonb,replayed boolean)
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
      DECLARE v_org text:=NULLIF(current_setting('aos.org_id',true),'');
        v_project text:=NULLIF(current_setting('aos.project_id',true),'');
        v_existing record;v_head record;v_event_id text:=gen_random_uuid()::text;
        v_event_data jsonb;v_event_hash text;
      BEGIN
        SELECT r.authority_data,r.request_hash,r.run_id,r.expected_version INTO v_existing
          FROM public.ecommerce_investigation_run_state_transition_receipt r
          WHERE r.org_id=v_org AND r.project_id=v_project
            AND r.operation='business_investigation_run.resume_after_data'
            AND r.idempotency_key=p_idempotency_key;
        IF FOUND THEN
          IF v_existing.request_hash<>p_request_hash OR v_existing.run_id<>p_run_id
            OR v_existing.expected_version<>p_expected_version
          THEN RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='Run data-resume idempotency conflict';END IF;
          RETURN QUERY SELECT v_existing.authority_data,true;RETURN;
        END IF;
        IF v_org IS NULL OR v_project IS NULL OR p_expected_version<1
          OR length(BTRIM(p_run_id)) NOT BETWEEN 1 AND 200
          OR length(BTRIM(p_idempotency_key)) NOT BETWEEN 1 AND 200
          OR NOT COALESCE(p_request_hash ~ '^sha256:[0-9a-f]{64}$',false)
          OR jsonb_typeof(p_requirement_ref)<>'object'
          OR NOT (p_requirement_ref ?& ARRAY['resourceType','resourceId','revision','contentHash'])
          OR jsonb_typeof(p_requirement_ref->'revision')<>'number'
          OR p_requirement_ref->>'resourceType' IS DISTINCT FROM 'DataRequirementRevision'
          OR length(BTRIM(p_requirement_ref->>'resourceId')) NOT BETWEEN 1 AND 240
          OR NOT COALESCE(p_requirement_ref->>'revision' ~ '^[1-9][0-9]*$',false)
          OR NOT COALESCE(p_requirement_ref->>'contentHash' ~ '^sha256:[0-9a-f]{64}$',false)
          OR NULLIF(p_requirement_ref->'receiptId','null'::jsonb) IS NOT NULL
          OR p_requirement_ref-ARRAY['resourceType','resourceId','revision','contentHash','receiptId']<>'{}'::jsonb
          OR jsonb_typeof(p_payload)<>'object'
          OR NOT (p_payload ?& ARRAY['schemaVersion','tenant','runId','version','priorRef',
            'lifecycle','control','eventSequence','contentHash','pendingRequirementRef',
            'uncertainCommand','createdBy','createdAt'])
          OR jsonb_typeof(p_payload->'tenant')<>'object'
          OR jsonb_typeof(p_payload->'priorRef')<>'object'
          OR NOT (p_payload->'priorRef' ?& ARRAY[
            'resourceType','resourceId','revision','contentHash'])
          OR jsonb_typeof(p_payload#>'{priorRef,revision}')<>'number'
          OR NULLIF(p_payload#>'{priorRef,receiptId}','null'::jsonb) IS NOT NULL
          OR (p_payload->'priorRef')-ARRAY[
            'resourceType','resourceId','revision','contentHash','receiptId']<>'{}'::jsonb
          OR jsonb_typeof(p_payload->'version')<>'number'
          OR jsonb_typeof(p_payload->'eventSequence')<>'number'
          OR NOT COALESCE(p_payload->>'version' ~ '^[1-9][0-9]*$',false)
          OR NOT COALESCE(p_payload->>'eventSequence' ~ '^[1-9][0-9]*$',false)
          OR NOT COALESCE(p_payload#>>'{priorRef,revision}' ~ '^[1-9][0-9]*$',false)
          OR p_request_hash IS DISTINCT FROM 'sha256:'||encode(public.digest(convert_to(
            public.canonical_asset_registry_jsonb(jsonb_build_object(
              'runId',p_run_id,'expectedVersion',p_expected_version,
              'operation','business_investigation_run.resume_after_data',
              'requirementRef',p_requirement_ref)),'UTF8'),'sha256'),'hex')
        THEN RAISE EXCEPTION USING ERRCODE='BO001',MESSAGE='Run data-resume request invalid';END IF;

        SELECT * INTO v_head FROM public.ecommerce_investigation_run_state_head h
          WHERE h.org_id=v_org AND h.project_id=v_project AND h.run_id=p_run_id FOR UPDATE;
        IF NOT FOUND OR v_head.current_version<>p_expected_version
          OR v_head.lifecycle<>'WAITING_DATA' OR v_head.control<>'RUNNING'
          OR v_head.pending_requirement_ref IS DISTINCT FROM p_requirement_ref
          OR v_head.uncertain_command IS NOT NULL
        THEN RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='Run data-resume authority rejected';END IF;
        IF p_payload#>>'{tenant,orgId}' IS DISTINCT FROM v_org
          OR p_payload#>>'{tenant,projectId}' IS DISTINCT FROM v_project
          OR p_payload->>'schemaVersion' IS DISTINCT FROM 'aos.ecommerce.business-investigation-run-state/v1'
          OR p_payload->>'runId' IS DISTINCT FROM p_run_id
          OR (p_payload->>'version')::bigint IS DISTINCT FROM p_expected_version+1
          OR p_payload#>>'{priorRef,resourceType}' IS DISTINCT FROM 'BusinessInvestigationRunStateRevision'
          OR p_payload#>>'{priorRef,resourceId}' IS DISTINCT FROM p_run_id
          OR (p_payload#>>'{priorRef,revision}')::bigint IS DISTINCT FROM p_expected_version
          OR p_payload#>>'{priorRef,contentHash}' IS DISTINCT FROM v_head.content_hash
          OR p_payload->>'lifecycle' IS DISTINCT FROM 'PREPARING'
          OR p_payload->>'control' IS DISTINCT FROM 'RUNNING'
          OR (p_payload->>'eventSequence')::bigint IS DISTINCT FROM v_head.current_event_sequence+1
          OR NOT COALESCE(p_payload->>'contentHash' ~ '^sha256:[0-9a-f]{64}$',false)
          OR p_payload->>'contentHash' IS DISTINCT FROM 'sha256:'||encode(public.digest(
            convert_to(public.canonical_asset_registry_jsonb(p_payload-'contentHash'),'UTF8'),
            'sha256'),'hex')
          OR NULLIF(p_payload->'pendingRequirementRef','null'::jsonb) IS NOT NULL
          OR NULLIF(p_payload->'uncertainCommand','null'::jsonb) IS NOT NULL
          OR length(BTRIM(p_payload->>'createdBy')) NOT BETWEEN 1 AND 200
          OR p_payload-ARRAY['schemaVersion','tenant','runId','version','priorRef','lifecycle',
            'control','eventSequence','contentHash','pendingRequirementRef','uncertainCommand',
            'createdBy','createdAt']<>'{}'::jsonb
        THEN RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='Run data-resume successor rejected';END IF;

        INSERT INTO public.ecommerce_investigation_run_state_revision(
          org_id,project_id,run_id,version,prior_version,lifecycle,control,event_sequence,
          content_hash,authority_data,created_by,created_at,pending_requirement_ref,uncertain_command)
        VALUES(v_org,v_project,p_run_id,p_expected_version+1,p_expected_version,'PREPARING',
          'RUNNING',v_head.current_event_sequence+1,p_payload->>'contentHash',p_payload,
          p_payload->>'createdBy',(p_payload->>'createdAt')::timestamptz,NULL,NULL);
        UPDATE public.ecommerce_investigation_run_state_head SET current_version=p_expected_version+1,
          lifecycle='PREPARING',control='RUNNING',
          current_event_sequence=current_event_sequence+1,content_hash=p_payload->>'contentHash',
          authority_data=p_payload,updated_at=(p_payload->>'createdAt')::timestamptz,
          pending_requirement_ref=NULL,uncertain_command=NULL
          WHERE org_id=v_org AND project_id=v_project AND run_id=p_run_id;
        v_event_data:=jsonb_build_object(
          'schemaVersion','aos.ecommerce.business-investigation-run-event/v1',
          'tenant',p_payload->'tenant','eventId',v_event_id,
          'runStateRef',jsonb_build_object(
            'resourceType','BusinessInvestigationRunStateRevision','resourceId',p_run_id,
            'revision',p_expected_version+1,'contentHash',p_payload->>'contentHash'),
          'requirementRef',p_requirement_ref,'sequence',v_head.current_event_sequence+1,
          'eventType','RUN_DATA_RESUMED','occurredAt',p_payload->'createdAt',
          'nonClaims',jsonb_build_array('NO_AIP_TASKRUN','NO_ANALYSIS_STEP_COMPLETION','NO_EXTERNAL_EFFECT'));
        v_event_hash:='sha256:'||encode(public.digest(convert_to(v_event_data::text,'UTF8'),'sha256'),'hex');
        INSERT INTO public.ecommerce_investigation_run_event(
          org_id,project_id,event_id,run_id,sequence,event_type,content_hash,event_data,occurred_at)
        VALUES(v_org,v_project,v_event_id,p_run_id,v_head.current_event_sequence+1,
          'RUN_DATA_RESUMED',v_event_hash,v_event_data,(p_payload->>'createdAt')::timestamptz);
        INSERT INTO public.ecommerce_investigation_run_state_transition_receipt(
          org_id,project_id,receipt_id,run_id,operation,idempotency_key,request_hash,
          expected_version,result_version,authority_data)
        VALUES(v_org,v_project,gen_random_uuid()::text,p_run_id,
          'business_investigation_run.resume_after_data',p_idempotency_key,p_request_hash,
          p_expected_version,p_expected_version+1,p_payload);
        RETURN QUERY SELECT p_payload,false;
      END $$""")
    op.execute(f"REVOKE ALL ON FUNCTION ecommerce_investigation_run_data_resume_ar2_011{SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION ecommerce_investigation_run_data_resume_ar2_011{SIGNATURE} TO aos_runtime")


def downgrade() -> None:
    op.execute("""DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM public.ecommerce_investigation_run_state_transition_receipt
        WHERE operation='business_investigation_run.resume_after_data' LIMIT 1)
      THEN RAISE EXCEPTION 'cannot downgrade ar2_011 with data-resume authority'
        USING ERRCODE='55000';END IF;
    END $$""")
    op.execute(f"DROP FUNCTION ecommerce_investigation_run_data_resume_ar2_011{SIGNATURE}")
    op.execute("""ALTER TABLE ecommerce_investigation_run_event
      DROP CONSTRAINT ecommerce_investigation_run_event_event_type_check""")
    op.execute("""ALTER TABLE ecommerce_investigation_run_event ADD CONSTRAINT
      ecommerce_investigation_run_event_event_type_check CHECK(event_type IN(
        'RUN_REQUESTED','RUN_PAUSED','RUN_RESUMED','RUN_CANCELLED',
        'RUN_WAITING_DATA','RUN_UNKNOWN','RUN_RECONCILING'))""")
    op.execute("""ALTER TABLE ecommerce_investigation_run_state_transition_receipt
      DROP CONSTRAINT ecommerce_investigation_run_state_transition_operation_ar2_011""")
    op.execute("""ALTER TABLE ecommerce_investigation_run_state_transition_receipt
      ADD CONSTRAINT ecommerce_investigation_run_state_transition_operation_biw4_007 CHECK(
        operation IN('business_investigation_run.request_data',
          'business_investigation_run.mark_unknown',
          'business_investigation_run.begin_reconcile'))""")
