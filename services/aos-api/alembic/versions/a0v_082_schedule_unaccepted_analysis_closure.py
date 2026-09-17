"""Audited terminal closure of an unaccepted schedule analysis initialization."""

from alembic import op


revision = "a0v_082"
down_revision = "a0v_081"
branch_labels = depends_on = None


def upgrade():
    op.execute(r"""
    CREATE FUNCTION public.ecommerce_unaccepted_schedule_analysis_close_a0v_082(
      p_request jsonb,p_actor text)
    RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
    DECLARE
      v_org text:=nullif(current_setting('aos.org_id',true),'');
      v_project text:=nullif(current_setting('aos.project_id',true),'');
      v_key text:=p_request->>'idempotencyKey'; v_occurrence uuid; v_control_id uuid;
      v_o record; v_a record; v_control record; v_old record; v_route record;
      v_hash text; v_body jsonb; v_content_hash text; v_run_id text;
      v_receipt_count bigint; v_run_count bigint; v_now timestamptz;
      v_receipt_id uuid:=gen_random_uuid();
    BEGIN
      IF current_setting('role',true) IS DISTINCT FROM 'aos_extension_maintainer'
        OR current_setting('transaction_isolation') IS DISTINCT FROM 'serializable'
        OR NOT pg_has_role(session_user,'aos_extension_maintainer','member')
        OR EXISTS(SELECT 1 FROM pg_roles WHERE rolname=session_user AND (rolsuper OR rolbypassrls))
        OR v_org IS NULL OR v_project IS NULL
      THEN RAISE EXCEPTION 'scoped schedule closure maintainer required' USING ERRCODE='42501'; END IF;
      IF jsonb_typeof(p_request) IS DISTINCT FROM 'object'
        OR p_request->>'schemaVersion' IS DISTINCT FROM 'aos.ecommerce.unaccepted-schedule-analysis-closure/v1'
        OR p_request-ARRAY['schemaVersion','occurrenceId','scheduleControlReceiptId',
                           'scheduleControlContentHash','idempotencyKey']<>'{}'::jsonb
        OR v_key IS NULL OR v_key<>btrim(v_key) OR length(v_key) NOT BETWEEN 1 AND 160 OR v_key ~ '[[:cntrl:]]'
        OR p_actor IS NULL OR p_actor<>btrim(p_actor) OR length(p_actor) NOT BETWEEN 1 AND 240 OR p_actor ~ '[[:cntrl:]]'
        OR coalesce(p_request->>'scheduleControlContentHash','') !~ '^sha256:[0-9a-f]{64}$'
      THEN RAISE EXCEPTION 'invalid schedule analysis closure request' USING ERRCODE='22023'; END IF;
      v_occurrence:=(p_request->>'occurrenceId')::uuid;
      v_control_id:=(p_request->>'scheduleControlReceiptId')::uuid;
      IF v_occurrence IS NULL OR v_control_id IS NULL
        OR v_occurrence::text<>p_request->>'occurrenceId'
        OR v_control_id::text<>p_request->>'scheduleControlReceiptId'
      THEN RAISE EXCEPTION 'canonical schedule closure identity required' USING ERRCODE='22023'; END IF;
      PERFORM 1 FROM public.meta_membership WHERE org_id=v_org AND project_id=v_project
        AND subject=p_actor FOR SHARE;
      IF NOT EXISTS(SELECT 1 FROM public.meta_membership WHERE org_id=v_org AND project_id=v_project
          AND subject=p_actor AND lower(role) IN ('admin','owner'))
      THEN RAISE EXCEPTION 'current schedule closure administrator required' USING ERRCODE='42501'; END IF;
      v_hash:='sha256:'||encode(sha256(convert_to(
        public.canonical_asset_registry_jsonb(p_request),'UTF8')),'hex');
      SELECT * INTO v_old FROM public.ecommerce_unaccepted_analysis_closure_receipt
        WHERE org_id=v_org AND project_id=v_project AND idempotency_key=v_key;
      IF FOUND THEN
        IF v_old.request_hash<>v_hash OR v_old.actor<>p_actor
        THEN RAISE EXCEPTION 'schedule closure idempotency drift' USING ERRCODE='40001'; END IF;
        RETURN v_old.authority_data||jsonb_build_object('contentHash',v_old.content_hash,'replayed',true);
      END IF;

      SELECT * INTO v_o FROM public.automation_occurrence WHERE org_id=v_org AND project_id=v_project
        AND occurrence_id=v_occurrence FOR UPDATE;
      IF NOT FOUND OR v_o.status<>'needs_attention' OR v_o.trigger_source<>'schedule'
        OR v_o.operation_id<>'ecommerce_growth_schedule_trigger' OR v_o.receipt_ref IS NOT NULL
        OR v_o.source_event_id IS NOT NULL
      THEN RAISE EXCEPTION 'held original schedule initialization required' USING ERRCODE='55000'; END IF;
      SELECT * INTO v_a FROM public.automation_occurrence_dispatch_attempt
        WHERE org_id=v_org AND project_id=v_project AND occurrence_id=v_occurrence FOR UPDATE;
      IF NOT FOUND OR v_a.status<>'unknown' OR v_a.claim_until>=clock_timestamp()
        OR v_a.receipt_ref IS NOT NULL
      THEN RAISE EXCEPTION 'expired unknown schedule initialization required' USING ERRCODE='55000'; END IF;

      SELECT * INTO v_control FROM public.ecommerce_schedule_policy_control_receipt
        WHERE org_id=v_org AND project_id=v_project AND receipt_id=v_control_id;
      IF NOT FOUND OR v_control.content_hash IS DISTINCT FROM p_request->>'scheduleControlContentHash'
        OR v_control.content_hash IS DISTINCT FROM 'sha256:'||encode(sha256(convert_to(
          public.canonical_asset_registry_jsonb(v_control.authority-'contentHash'-'receiptRef'),'UTF8')),'hex')
        OR v_control.authority#>>'{receiptRef,resourceId}' IS DISTINCT FROM v_control.receipt_id::text
        OR v_control.authority#>>'{receiptRef,contentHash}' IS DISTINCT FROM v_control.content_hash
        OR v_control.schedule_policy_id IS DISTINCT FROM v_o.policy_id
        OR v_control.policy_revision IS DISTINCT FROM v_o.policy_revision
        OR v_control.installation_id IS DISTINCT FROM v_o.installation_id
        OR v_control.generation IS DISTINCT FROM v_o.generation
        OR v_control.execution_epoch IS DISTINCT FROM v_o.execution_epoch
        OR v_control.authority#>>'{policyRef,contentHash}' IS DISTINCT FROM v_o.policy_hash
      THEN RAISE EXCEPTION 'exact schedule control receipt required' USING ERRCODE='40001'; END IF;

      SELECT * INTO v_route FROM public.extension_operation_dispatch_binding
        WHERE org_id=v_org AND project_id=v_project
          AND operation_id='ecommerce_growth_schedule_trigger' FOR UPDATE;
      IF NOT FOUND OR v_route.handler_kind<>'extension' OR v_route.operation_fence
        OR v_route.installation_id<>v_o.installation_id OR v_route.generation<>v_o.generation
        OR v_route.execution_epoch<>v_o.execution_epoch
      THEN RAISE EXCEPTION 'current schedule dispatch differs' USING ERRCODE='40001'; END IF;

      v_run_id:='analysis-'||substr(encode(sha256(convert_to(
        v_org||chr(31)||v_project||chr(31)||v_a.target_idempotency_key,'UTF8')),'hex'),1,32);
      SELECT count(*) INTO v_receipt_count FROM public.ecommerce_growth_runtime_command_receipt
        WHERE org_id=v_org AND project_id=v_project AND operation_id='ecommerce_growth_analysis_advance'
          AND idempotency_key=v_a.target_idempotency_key;
      SELECT count(*) INTO v_run_count FROM public.ecommerce_investigation_run
        WHERE org_id=v_org AND project_id=v_project
          AND (run_id=v_run_id OR trigger_key=v_a.target_idempotency_key);
      IF v_receipt_count<>0 OR v_run_count<>0
      THEN RAISE EXCEPTION 'schedule target accepted or requires receipt reconciliation' USING ERRCODE='55000'; END IF;

      v_now:=clock_timestamp();
      v_body:=jsonb_build_object(
        'schemaVersion','aos.ecommerce.unaccepted-schedule-analysis-closure-receipt/v1',
        'receiptId',v_receipt_id::text,
        'tenant',jsonb_build_object('orgId',v_org,'projectId',v_project),
        'request',p_request,'requestHash',v_hash,'actor',p_actor,'createdAt',v_now,
        'businessAccepted',false,'priorOccurrence',to_jsonb(v_o),'priorAttempt',to_jsonb(v_a),
        'scheduleControlReceiptRef',jsonb_build_object('resourceType','SchedulePolicyControlReceipt',
          'resourceId',v_control.receipt_id::text,'revision',1,'contentHash',v_control.content_hash),
        'targetEvidence',jsonb_build_object('receiptCount',v_receipt_count,'runCount',v_run_count,
          'runId',v_run_id,'targetIdempotencyKey',v_a.target_idempotency_key,'checkedAt',v_now));
      v_content_hash:='sha256:'||encode(sha256(convert_to(
        public.canonical_asset_registry_jsonb(v_body),'UTF8')),'hex');
      INSERT INTO public.ecommerce_unaccepted_analysis_closure_receipt(
        org_id,project_id,receipt_id,occurrence_id,idempotency_key,request_hash,actor,
        authority_data,content_hash,created_at)
      VALUES(v_org,v_project,v_receipt_id,v_occurrence,v_key,v_hash,p_actor,v_body,v_content_hash,v_now);
      UPDATE public.automation_occurrence SET status='cancelled',updated_at=v_now
        WHERE org_id=v_org AND project_id=v_project AND occurrence_id=v_occurrence;
      UPDATE public.automation_occurrence_dispatch_attempt
        SET status='closed_unaccepted',resolved_at=v_now
        WHERE org_id=v_org AND project_id=v_project AND occurrence_id=v_occurrence;
      UPDATE public.automation_occurrence_outbox
        SET delivered_at=coalesce(delivered_at,v_now),claim_until=NULL
        WHERE org_id=v_org AND project_id=v_project AND occurrence_id=v_occurrence;
      RETURN v_body||jsonb_build_object('contentHash',v_content_hash,'replayed',false);
    END $$;
    REVOKE ALL ON FUNCTION public.ecommerce_unaccepted_schedule_analysis_close_a0v_082(jsonb,text)
      FROM PUBLIC,aos_runtime;
    GRANT EXECUTE ON FUNCTION public.ecommerce_unaccepted_schedule_analysis_close_a0v_082(jsonb,text)
      TO aos_extension_maintainer;
    """)


def downgrade():
    raise RuntimeError("unaccepted schedule initialization history must be retained")
