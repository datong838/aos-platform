"""Audited terminal closure of fenced, unaccepted product-event initialization."""
from alembic import op
revision = 'a0v_060'
down_revision = 'a0v_059'
branch_labels = depends_on = None


def upgrade():
    op.execute(r'''
    ALTER TABLE public.automation_occurrence DROP CONSTRAINT automation_occurrence_status_check;
    ALTER TABLE public.automation_occurrence ADD CONSTRAINT automation_occurrence_status_check
      CHECK(status IN ('pending','claimed','accepted','missed','not_applicable','needs_attention','cancelled'));
    ALTER TABLE public.automation_occurrence_dispatch_attempt DROP CONSTRAINT automation_occurrence_dispatch_attempt_status_check;
    ALTER TABLE public.automation_occurrence_dispatch_attempt ADD CONSTRAINT automation_occurrence_dispatch_attempt_status_check
      CHECK(status IN ('claimed','receipt_recorded','unknown','closed_unaccepted'));
    CREATE TABLE public.ecommerce_unaccepted_analysis_closure_receipt(
      org_id text NOT NULL, project_id text NOT NULL, receipt_id uuid NOT NULL,
      occurrence_id uuid NOT NULL, idempotency_key text NOT NULL,
      request_hash text NOT NULL, actor text NOT NULL, authority_data jsonb NOT NULL,
      content_hash text NOT NULL, created_at timestamptz NOT NULL,
      PRIMARY KEY(org_id,project_id,receipt_id), UNIQUE(org_id,project_id,idempotency_key),
      UNIQUE(org_id,project_id,occurrence_id),
      FOREIGN KEY(org_id,project_id,occurrence_id) REFERENCES public.automation_occurrence(org_id,project_id,occurrence_id)
    );
    ALTER TABLE public.ecommerce_unaccepted_analysis_closure_receipt ENABLE ROW LEVEL SECURITY;
    ALTER TABLE public.ecommerce_unaccepted_analysis_closure_receipt FORCE ROW LEVEL SECURITY;
    CREATE POLICY tenant_scope ON public.ecommerce_unaccepted_analysis_closure_receipt
      USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
      WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true));
    REVOKE ALL ON public.ecommerce_unaccepted_analysis_closure_receipt FROM PUBLIC,aos_runtime,aos_extension_maintainer;
    GRANT SELECT ON public.ecommerce_unaccepted_analysis_closure_receipt TO aos_runtime,aos_extension_maintainer;
    CREATE TRIGGER unaccepted_analysis_history_guard BEFORE UPDATE OR DELETE
      ON public.ecommerce_unaccepted_analysis_closure_receipt FOR EACH ROW
      EXECUTE FUNCTION public.extension_event_control_dispatch_history_guard_a0v_054();

    CREATE TRIGGER unaccepted_analysis_no_truncate BEFORE TRUNCATE
      ON public.ecommerce_unaccepted_analysis_closure_receipt FOR EACH STATEMENT
      EXECUTE FUNCTION public.extension_event_control_dispatch_history_guard_a0v_054();
    CREATE FUNCTION public.unaccepted_analysis_terminal_guard_a0v_060()
    RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
    BEGIN
      IF TG_OP='UPDATE' AND OLD.status IN ('cancelled','closed_unaccepted')
      THEN RAISE EXCEPTION 'closed initialization is terminal' USING ERRCODE='55000'; END IF;
      IF NEW.status IN ('cancelled','closed_unaccepted') AND NOT EXISTS(
        SELECT 1 FROM public.ecommerce_unaccepted_analysis_closure_receipt
          WHERE org_id=NEW.org_id AND project_id=NEW.project_id AND occurrence_id=NEW.occurrence_id)
      THEN RAISE EXCEPTION 'immutable closure receipt required' USING ERRCODE='55000'; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER occurrence_closure_terminal BEFORE INSERT OR UPDATE ON public.automation_occurrence
      FOR EACH ROW EXECUTE FUNCTION public.unaccepted_analysis_terminal_guard_a0v_060();
    CREATE TRIGGER attempt_closure_terminal BEFORE INSERT OR UPDATE ON public.automation_occurrence_dispatch_attempt
      FOR EACH ROW EXECUTE FUNCTION public.unaccepted_analysis_terminal_guard_a0v_060();

    CREATE FUNCTION public.ecommerce_unaccepted_analysis_close_a0v_060(p_request jsonb,p_actor text)
    RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
    DECLARE
      v_org text:=nullif(current_setting('aos.org_id',true),'');
      v_project text:=nullif(current_setting('aos.project_id',true),'');
      v_key text:=p_request->>'idempotencyKey'; v_occurrence uuid; v_fence_id uuid;
      v_fence record; v_runtime record; v_o record; v_a record; v_origin record; v_old record;
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
      IF NOT FOUND OR v_runtime.execution_epoch<>v_fence.execution_epoch OR v_runtime.revision<>v_fence.runtime_revision
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
    raise RuntimeError('unaccepted initialization history must be retained')
