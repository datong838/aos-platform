"""Permit formal unaccepted closure after a proven dispatch configuration refresh."""
from alembic import op

revision = 'a0v_071'
down_revision = 'a0v_070'
branch_labels = depends_on = None


def upgrade():
    op.execute(r'''
    CREATE OR REPLACE FUNCTION public.ecommerce_unaccepted_analysis_close_a0v_060(p_request jsonb,p_actor text)
    RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
    DECLARE
      v_org text:=nullif(current_setting('aos.org_id',true),'');
      v_project text:=nullif(current_setting('aos.project_id',true),'');
      v_key text:=p_request->>'idempotencyKey'; v_occurrence uuid; v_fence_id uuid;
      v_fence record; v_runtime record; v_refresh record; v_refresh_ref jsonb;
      v_o record; v_a record; v_origin record; v_old record;
      v_hash text; v_body jsonb; v_snapshot jsonb; v_origin_body jsonb; v_content_hash text;
      v_run_id text; v_receipt_count bigint; v_run_count bigint; v_now timestamptz;
      v_receipt_id uuid:=gen_random_uuid();
    BEGIN
      IF current_setting('role',true) IS DISTINCT FROM 'aos_extension_maintainer'
        OR current_setting('transaction_isolation') IS DISTINCT FROM 'serializable'
        OR NOT pg_has_role(session_user,'aos_extension_maintainer','member')
        OR EXISTS(SELECT 1 FROM pg_roles WHERE rolname=session_user AND (rolsuper OR rolbypassrls))
        OR v_org IS NULL OR v_project IS NULL
      THEN RAISE EXCEPTION 'scoped analysis closure maintainer required' USING ERRCODE='42501'; END IF;
      IF jsonb_typeof(p_request) IS DISTINCT FROM 'object'
        OR p_request->>'schemaVersion' IS DISTINCT FROM 'aos.ecommerce.unaccepted-analysis-closure/v1'
        OR p_request-ARRAY['schemaVersion','occurrenceId','fenceReceiptId','fenceContentHash','idempotencyKey']<>'{}'::jsonb
        OR v_key IS NULL OR v_key<>btrim(v_key) OR length(v_key) NOT BETWEEN 1 AND 160 OR v_key ~ '[[:cntrl:]]'
        OR p_actor IS NULL OR p_actor<>btrim(p_actor) OR length(p_actor) NOT BETWEEN 1 AND 240 OR p_actor ~ '[[:cntrl:]]'
        OR coalesce(p_request->>'fenceContentHash','') !~ '^sha256:[0-9a-f]{64}$'
      THEN RAISE EXCEPTION 'invalid analysis closure request' USING ERRCODE='22023'; END IF;
      v_occurrence:=(p_request->>'occurrenceId')::uuid; v_fence_id:=(p_request->>'fenceReceiptId')::uuid;
      IF v_occurrence IS NULL OR v_fence_id IS NULL OR v_occurrence::text<>p_request->>'occurrenceId'
        OR v_fence_id::text<>p_request->>'fenceReceiptId'
      THEN RAISE EXCEPTION 'canonical closure identity required' USING ERRCODE='22023'; END IF;
      PERFORM 1 FROM public.meta_membership WHERE org_id=v_org AND project_id=v_project AND subject=p_actor FOR SHARE;
      IF NOT EXISTS(SELECT 1 FROM public.meta_membership WHERE org_id=v_org AND project_id=v_project
          AND subject=p_actor AND lower(role) IN ('admin','owner'))
      THEN RAISE EXCEPTION 'current closure administrator required' USING ERRCODE='42501'; END IF;
      v_hash:='sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(p_request),'UTF8')),'hex');
      SELECT * INTO v_old FROM public.ecommerce_unaccepted_analysis_closure_receipt
        WHERE org_id=v_org AND project_id=v_project AND idempotency_key=v_key;
      IF FOUND THEN
        IF v_old.request_hash<>v_hash OR v_old.actor<>p_actor
        THEN RAISE EXCEPTION 'closure idempotency drift' USING ERRCODE='40001'; END IF;
        RETURN v_old.authority_data||jsonb_build_object('contentHash',v_old.content_hash,'replayed',true);
      END IF;
      SELECT * INTO v_fence FROM public.extension_event_control_dispatch_receipt
        WHERE org_id=v_org AND project_id=v_project AND receipt_id=v_fence_id AND phase='fence';
      IF NOT FOUND OR v_fence.content_hash IS DISTINCT FROM p_request->>'fenceContentHash'
        OR v_fence.content_hash IS DISTINCT FROM 'sha256:'||encode(sha256(convert_to(
          public.canonical_asset_registry_jsonb(v_fence.authority_data),'UTF8')),'hex')
        OR v_fence.authority_data->'afterSnapshot' IS DISTINCT FROM v_fence.after_snapshot
      THEN RAISE EXCEPTION 'verified fence receipt required' USING ERRCODE='40001'; END IF;
      -- Same row order as the original Host; settle any transaction that entered before fencing.
      PERFORM 1 FROM public.extension_operation_dispatch_binding WHERE org_id=v_org AND project_id=v_project
        AND cutover_group_id=v_fence.cutover_group_id ORDER BY operation_id,installation_id,generation FOR UPDATE;
      SELECT jsonb_agg(jsonb_build_object('operationId',operation_id,'handlerKind',handler_kind,
        'installationId',installation_id::text,'generation',generation::text,'executionEpoch',execution_epoch,
        'operationFence',operation_fence,'revision',revision,'cutoverGroupId',cutover_group_id::text,
        'cutoverGroupRevision',cutover_group_revision) ORDER BY operation_id) INTO v_snapshot
        FROM public.extension_operation_dispatch_binding WHERE org_id=v_org AND project_id=v_project
        AND cutover_group_id=v_fence.cutover_group_id;
      IF v_snapshot IS DISTINCT FROM v_fence.after_snapshot OR NOT EXISTS(
        SELECT 1 FROM public.extension_operation_dispatch_binding WHERE org_id=v_org AND project_id=v_project
        AND operation_id='ecommerce_growth_event_control' AND operation_fence
        AND installation_id=v_fence.installation_id AND generation=v_fence.generation
        AND execution_epoch=v_fence.execution_epoch AND cutover_group_id=v_fence.cutover_group_id)
      THEN RAISE EXCEPTION 'current fenced dispatch required' USING ERRCODE='40001'; END IF;
      SELECT * INTO v_runtime FROM public.extension_runtime_binding WHERE org_id=v_org AND project_id=v_project
        AND installation_id=v_fence.installation_id AND generation=v_fence.generation FOR UPDATE;
      v_refresh_ref:=v_fence.authority_data->'configurationRefreshReceiptRef';
      IF jsonb_typeof(v_refresh_ref)='object' THEN
        SELECT * INTO v_refresh FROM public.extension_dispatch_configuration_refresh_receipt
          WHERE org_id=v_org AND project_id=v_project
            AND receipt_id=(v_refresh_ref->>'resourceId')::uuid
            AND revision=(v_refresh_ref->>'revision')::bigint
            AND content_hash=v_refresh_ref->>'contentHash' FOR SHARE;
        IF NOT FOUND OR v_refresh_ref->>'resourceType'<>'DispatchConfigurationRefreshReceipt'
          OR v_refresh.request_hash IS DISTINCT FROM 'sha256:'||encode(sha256(convert_to(
            public.canonical_asset_registry_jsonb(v_refresh.request),'UTF8')),'hex')
          OR v_refresh.content_hash IS DISTINCT FROM 'sha256:'||encode(sha256(convert_to(
            public.canonical_asset_registry_jsonb(v_refresh.body),'UTF8')),'hex')
          OR v_refresh.body->'request' IS DISTINCT FROM v_refresh.request
          OR v_refresh.installation_id<>v_fence.installation_id OR v_refresh.generation<>v_fence.generation
          OR v_refresh.cutover_group_id<>v_fence.cutover_group_id
          OR (v_refresh.request->>'sourceExecutionEpoch')::bigint<>v_fence.execution_epoch
          OR (v_refresh.request->>'targetExecutionEpoch')::bigint<>v_runtime.execution_epoch
          OR (v_refresh.request->>'targetRuntimeRevision')::bigint<>v_fence.runtime_revision
          OR v_refresh.request->'targetConfigurationRef' IS DISTINCT FROM v_runtime.config_ref
          OR v_refresh.request->'externalEffectsAllowed'<>'false'::jsonb
          OR v_refresh.request->'resumeBusinessRuns'<>'false'::jsonb
        THEN RAISE EXCEPTION 'refresh-proven closure runtime required' USING ERRCODE='40001'; END IF;
      ELSIF v_refresh_ref IS NOT NULL THEN
        RAISE EXCEPTION 'canonical refresh closure reference required' USING ERRCODE='40001';
      ELSIF NOT FOUND OR v_runtime.execution_epoch<>v_fence.execution_epoch
        OR v_runtime.revision<>v_fence.runtime_revision THEN
        RAISE EXCEPTION 'closure runtime drift' USING ERRCODE='40001';
      END IF;
      IF v_runtime.revision<>v_fence.runtime_revision OR NOT v_runtime.enabled
        OR v_runtime.operation_fence OR v_runtime.desired_state<>'enabled' OR v_runtime.observed_state<>'ready'
      THEN RAISE EXCEPTION 'closure runtime drift' USING ERRCODE='40001'; END IF;
      PERFORM 1 FROM public.automation_schedule_binding WHERE org_id=v_org AND project_id=v_project
        AND installation_id=v_fence.installation_id AND generation=v_fence.generation ORDER BY policy_id,policy_revision FOR UPDATE;
      IF EXISTS(SELECT 1 FROM public.automation_schedule_binding WHERE org_id=v_org AND project_id=v_project
          AND installation_id=v_fence.installation_id AND generation=v_fence.generation AND enabled)
        OR EXISTS(SELECT 1 FROM public.extension_runtime_execution_attempt WHERE org_id=v_org AND project_id=v_project
          AND installation_id=v_fence.installation_id AND generation=v_fence.generation AND state='running')
      THEN RAISE EXCEPTION 'closure target still active' USING ERRCODE='55000'; END IF;
      SELECT * INTO v_o FROM public.automation_occurrence WHERE org_id=v_org AND project_id=v_project
        AND occurrence_id=v_occurrence FOR UPDATE;
      IF NOT FOUND OR v_o.status<>'needs_attention' OR v_o.trigger_source<>'event'
        OR v_o.operation_id<>'ecommerce_growth_analysis_advance' OR v_o.receipt_ref IS NOT NULL
        OR v_o.installation_id<>v_fence.installation_id OR v_o.generation<>v_fence.generation
        OR v_o.execution_epoch<>v_fence.execution_epoch OR v_o.policy_id<>v_fence.policy_id
      THEN RAISE EXCEPTION 'held original event initialization required' USING ERRCODE='55000'; END IF;
      SELECT * INTO v_a FROM public.automation_occurrence_dispatch_attempt WHERE org_id=v_org AND project_id=v_project
        AND occurrence_id=v_occurrence FOR UPDATE;
      IF NOT FOUND OR v_a.status<>'unknown' OR v_a.claim_until>=clock_timestamp() OR v_a.receipt_ref IS NOT NULL
      THEN RAISE EXCEPTION 'expired unknown initialization required' USING ERRCODE='55000'; END IF;
      SELECT * INTO v_origin FROM public.ecommerce_product_event_origin WHERE org_id=v_org AND project_id=v_project
        AND occurrence_id=v_occurrence;
      IF NOT FOUND OR v_origin.source_event_id<>v_o.source_event_id
      THEN RAISE EXCEPTION 'original product event required' USING ERRCODE='55000'; END IF;
      v_origin_body:=jsonb_build_object('orgId',v_org,'projectId',v_project,'occurrenceId',v_occurrence::text,
        'sourceEventId',v_origin.source_event_id,'runId',v_origin.run_id,'actor',v_origin.actor);
      IF v_origin.content_hash IS DISTINCT FROM 'sha256:'||encode(sha256(convert_to(
          public.canonical_asset_registry_jsonb(v_origin_body),'UTF8')),'hex')
      THEN RAISE EXCEPTION 'product event origin hash drift' USING ERRCODE='40001'; END IF;
      v_run_id:='analysis-'||substr(encode(sha256(convert_to(v_org||chr(31)||v_project||chr(31)||
        v_a.target_idempotency_key,'UTF8')),'hex'),1,32);
      SELECT count(*) INTO v_receipt_count FROM public.ecommerce_growth_runtime_command_receipt
        WHERE org_id=v_org AND project_id=v_project AND operation_id='ecommerce_growth_analysis_advance'
          AND idempotency_key=v_a.target_idempotency_key;
      SELECT count(*) INTO v_run_count FROM public.ecommerce_investigation_run WHERE org_id=v_org AND project_id=v_project
        AND (run_id=v_run_id OR trigger_key=v_a.target_idempotency_key);
      IF v_receipt_count<>0 OR v_run_count<>0
      THEN RAISE EXCEPTION 'target accepted or requires receipt reconciliation' USING ERRCODE='55000'; END IF;
      v_now:=clock_timestamp();
      v_body:=jsonb_build_object('schemaVersion','aos.ecommerce.unaccepted-analysis-closure-receipt/v1',
        'receiptId',v_receipt_id::text,'tenant',jsonb_build_object('orgId',v_org,'projectId',v_project),
        'request',p_request,'requestHash',v_hash,'actor',p_actor,'createdAt',v_now,'businessAccepted',false,
        'priorOccurrence',to_jsonb(v_o),'priorAttempt',to_jsonb(v_a),'origin',v_origin_body,
        'fenceReceiptRef',jsonb_build_object('receiptId',v_fence_id::text,'contentHash',v_fence.content_hash),
        'targetEvidence',jsonb_build_object('receiptCount',v_receipt_count,'runCount',v_run_count,
          'runId',v_run_id,'targetIdempotencyKey',v_a.target_idempotency_key,'checkedAt',v_now));
      v_content_hash:='sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(v_body),'UTF8')),'hex');
      INSERT INTO public.ecommerce_unaccepted_analysis_closure_receipt VALUES(v_org,v_project,v_receipt_id,
        v_occurrence,v_key,v_hash,p_actor,v_body,v_content_hash,v_now);
      UPDATE public.automation_occurrence SET status='cancelled',updated_at=v_now
        WHERE org_id=v_org AND project_id=v_project AND occurrence_id=v_occurrence;
      UPDATE public.automation_occurrence_dispatch_attempt SET status='closed_unaccepted',resolved_at=v_now
        WHERE org_id=v_org AND project_id=v_project AND occurrence_id=v_occurrence;
      UPDATE public.automation_occurrence_outbox SET delivered_at=coalesce(delivered_at,v_now),claim_until=NULL
        WHERE org_id=v_org AND project_id=v_project AND occurrence_id=v_occurrence;
      RETURN v_body||jsonb_build_object('contentHash',v_content_hash,'replayed',false);
    END $$;
    REVOKE ALL ON FUNCTION public.ecommerce_unaccepted_analysis_close_a0v_060(jsonb,text) FROM PUBLIC,aos_runtime;
    GRANT EXECUTE ON FUNCTION public.ecommerce_unaccepted_analysis_close_a0v_060(jsonb,text) TO aos_extension_maintainer;

    ''')


def downgrade():
    raise RuntimeError('refresh-proven unaccepted closure authority must be retained')
