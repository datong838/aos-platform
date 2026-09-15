"""Receipt-first lifecycle for the one optional ecommerce event-control dispatch."""
from alembic import op

revision = "a0v_054"
down_revision = "a0v_053"
branch_labels = depends_on = None


def upgrade() -> None:
    op.execute(r"""
    CREATE TABLE public.extension_event_control_dispatch_receipt(
      org_id text NOT NULL, project_id text NOT NULL, receipt_id uuid NOT NULL,
      idempotency_key text NOT NULL CHECK(length(idempotency_key) BETWEEN 1 AND 160),
      phase text NOT NULL CHECK(phase IN ('expand','fence','shrink')),
      request_hash text NOT NULL CHECK(request_hash ~ '^sha256:[0-9a-f]{64}$'),
      installation_id uuid NOT NULL, generation uuid NOT NULL,
      execution_epoch bigint NOT NULL CHECK(execution_epoch>0),
      runtime_revision bigint NOT NULL CHECK(runtime_revision>0),
      cutover_group_id uuid NOT NULL,
      expected_group_revision bigint NOT NULL CHECK(expected_group_revision>0),
      target_group_revision bigint NOT NULL CHECK(target_group_revision=expected_group_revision+1),
      case_id text NOT NULL CHECK(length(case_id) BETWEEN 1 AND 240),
      policy_id text NOT NULL CHECK(length(policy_id) BETWEEN 1 AND 240),
      approval_ref jsonb NOT NULL CHECK(jsonb_typeof(approval_ref)='object'),
      before_snapshot jsonb NOT NULL CHECK(jsonb_typeof(before_snapshot)='array'),
      after_snapshot jsonb NOT NULL CHECK(jsonb_typeof(after_snapshot)='array'),
      actor text NOT NULL CHECK(length(actor) BETWEEN 1 AND 240),
      authority_data jsonb NOT NULL CHECK(jsonb_typeof(authority_data)='object'),
      content_hash text NOT NULL CHECK(content_hash ~ '^sha256:[0-9a-f]{64}$'),
      created_at timestamptz NOT NULL,
      PRIMARY KEY(org_id,project_id,receipt_id),
      UNIQUE(org_id,project_id,idempotency_key),
      FOREIGN KEY(org_id,project_id,installation_id,generation)
        REFERENCES public.extension_runtime_binding(org_id,project_id,installation_id,generation)
    );
    ALTER TABLE public.extension_event_control_dispatch_receipt ENABLE ROW LEVEL SECURITY;
    ALTER TABLE public.extension_event_control_dispatch_receipt FORCE ROW LEVEL SECURITY;
    CREATE POLICY tenant_scope ON public.extension_event_control_dispatch_receipt
      USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
      WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true));
    REVOKE ALL ON public.extension_event_control_dispatch_receipt FROM PUBLIC,aos_runtime,aos_extension_maintainer;
    GRANT SELECT ON public.extension_event_control_dispatch_receipt TO aos_runtime,aos_extension_maintainer;
    GRANT INSERT ON public.extension_event_control_dispatch_receipt TO aos_extension_maintainer;

    CREATE FUNCTION public.extension_event_control_dispatch_history_guard_a0v_054()
    RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
    BEGIN RAISE EXCEPTION 'event control dispatch receipts are immutable' USING ERRCODE='55000'; END $$;
    CREATE TRIGGER event_control_dispatch_history_guard
      BEFORE UPDATE OR DELETE ON public.extension_event_control_dispatch_receipt
      FOR EACH ROW EXECUTE FUNCTION public.extension_event_control_dispatch_history_guard_a0v_054();

    CREATE FUNCTION public.extension_event_control_dispatch_transition_a0v_054(p_request jsonb,p_actor text)
    RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
    DECLARE
      v_org text:=nullif(current_setting('aos.org_id',true),'');
      v_project text:=nullif(current_setting('aos.project_id',true),'');
      v_phase text; v_key text; v_install uuid; v_generation uuid; v_group uuid;
      v_epoch bigint; v_runtime_revision bigint; v_expected bigint; v_target bigint;
      v_prior record; v_prior_ref jsonb := NULL;
      v_existing record; v_runtime record; v_rows bigint; v_control record;
      v_before jsonb; v_after jsonb; v_hash text; v_body jsonb; v_content_hash text;
      v_receipt uuid:=gen_random_uuid(); v_now timestamptz; v_ref jsonb; v_number jsonb;
      v_base text[]:=ARRAY['ecommerce_growth_analysis_advance','ecommerce_growth_case_put',
        'ecommerce_growth_content_generate','ecommerce_growth_content_review','ecommerce_growth_data_fulfill',
        'ecommerce_growth_investigation_describe','ecommerce_growth_review_advance',
        'ecommerce_growth_schedule_put','ecommerce_growth_schedule_trigger'];
    BEGIN
      IF current_setting('role',true) IS DISTINCT FROM 'aos_extension_maintainer'
        OR current_setting('transaction_isolation') IS DISTINCT FROM 'serializable'
        OR NOT pg_has_role(session_user,'aos_extension_maintainer','member')
        OR EXISTS(SELECT 1 FROM pg_catalog.pg_roles WHERE rolname=session_user AND (rolsuper OR rolbypassrls))
      THEN RAISE EXCEPTION 'dedicated event dispatch maintainer required' USING ERRCODE='42501'; END IF;
      IF v_org IS NULL OR v_project IS NULL OR p_actor IS NULL OR p_actor<>btrim(p_actor)
        OR length(p_actor) NOT BETWEEN 1 AND 240 OR p_actor ~ '[[:cntrl:]]'
        OR jsonb_typeof(p_request) IS DISTINCT FROM 'object'
        OR p_request->>'schemaVersion' IS DISTINCT FROM 'aos.ecommerce.event-control-dispatch/v1'
        OR p_request-ARRAY['schemaVersion','phase','installationRef','generation','executionEpoch',
          'runtimeRevision','cutoverGroupId','expectedGroupRevision','caseId','schedulePolicyId',
          'approvalRef','idempotencyKey'] <> '{}'::jsonb
      THEN RAISE EXCEPTION 'invalid event dispatch request' USING ERRCODE='22023'; END IF;
      v_phase:=p_request->>'phase'; v_key:=p_request->>'idempotencyKey'; v_ref:=p_request->'approvalRef';
      IF v_phase NOT IN ('expand','fence','shrink') OR v_key IS NULL OR v_key<>btrim(v_key)
        OR length(v_key) NOT BETWEEN 1 AND 160 OR v_key ~ '[[:cntrl:]]'
        OR coalesce(p_request->>'caseId','')='' OR p_request->>'caseId'<>btrim(p_request->>'caseId')
        OR coalesce(p_request->>'schedulePolicyId','')='' OR p_request->>'schedulePolicyId'<>btrim(p_request->>'schedulePolicyId')
        OR jsonb_typeof(v_ref) IS DISTINCT FROM 'object'
        OR v_ref-ARRAY['resourceType','resourceId','revision','contentHash'] <> '{}'::jsonb
        OR v_ref->>'resourceType' IS DISTINCT FROM 'ActionApprovalEvent'
        OR coalesce(v_ref->>'contentHash','') !~ '^sha256:[0-9a-f]{64}$'
      THEN RAISE EXCEPTION 'invalid event dispatch authority' USING ERRCODE='22023'; END IF;
      IF jsonb_typeof(p_request->'installationRef') IS DISTINCT FROM 'object'
        OR (p_request->'installationRef')-ARRAY['installationId','revision','lockHash','overlayRevision'] <> '{}'::jsonb
        OR coalesce(p_request#>>'{installationRef,lockHash}','') !~ '^sha256:[0-9a-f]{64}$'
        OR coalesce(p_request#>>'{installationRef,overlayRevision}','')=''
      THEN RAISE EXCEPTION 'invalid event dispatch installation reference' USING ERRCODE='22023'; END IF;
      FOREACH v_number IN ARRAY ARRAY[p_request->'executionEpoch',p_request->'runtimeRevision',
          p_request->'expectedGroupRevision',v_ref->'revision',p_request#>'{installationRef,revision}'] LOOP
        IF jsonb_typeof(v_number) IS DISTINCT FROM 'number' OR v_number::text !~ '^[1-9][0-9]*$'
          OR (v_number::text)::numeric>9223372036854775807
        THEN RAISE EXCEPTION 'invalid event dispatch revision' USING ERRCODE='22023'; END IF;
      END LOOP;
      BEGIN
        v_install:=(p_request#>>'{installationRef,installationId}')::uuid; v_generation:=(p_request->>'generation')::uuid;
        v_group:=(p_request->>'cutoverGroupId')::uuid;
      EXCEPTION WHEN invalid_text_representation THEN
        RAISE EXCEPTION 'invalid event dispatch identity' USING ERRCODE='22023';
      END;
      IF v_install::text IS DISTINCT FROM p_request#>>'{installationRef,installationId}'
        OR v_generation::text IS DISTINCT FROM p_request->>'generation'
        OR v_group::text IS DISTINCT FROM p_request->>'cutoverGroupId'
      THEN RAISE EXCEPTION 'noncanonical event dispatch identity' USING ERRCODE='22023'; END IF;
      v_epoch:=(p_request->>'executionEpoch')::bigint;
      v_runtime_revision:=(p_request->>'runtimeRevision')::bigint;
      v_expected:=(p_request->>'expectedGroupRevision')::bigint; v_target:=v_expected+1;
      v_hash:='sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(p_request),'UTF8')),'hex');

      SELECT * INTO v_existing FROM public.extension_event_control_dispatch_receipt
        WHERE org_id=v_org AND project_id=v_project AND idempotency_key=v_key;
      IF FOUND THEN
        IF v_existing.request_hash IS DISTINCT FROM v_hash OR v_existing.actor IS DISTINCT FROM p_actor
        THEN RAISE EXCEPTION 'event dispatch idempotency conflict' USING ERRCODE='40001'; END IF;
        RETURN v_existing.authority_data||jsonb_build_object('contentHash',v_existing.content_hash,'replayed',true);
      END IF;
      PERFORM pg_advisory_xact_lock(hashtextextended(v_org||chr(31)||v_project||chr(31)||v_group::text,0));
      PERFORM 1 FROM public.meta_membership WHERE org_id=v_org AND project_id=v_project
        AND subject=p_actor FOR SHARE;
      IF (SELECT count(*) FROM public.meta_membership WHERE org_id=v_org AND project_id=v_project
          AND subject=p_actor)<>1 OR NOT EXISTS(SELECT 1 FROM public.meta_membership
          WHERE org_id=v_org AND project_id=v_project AND subject=p_actor
            AND lower(role) IN ('admin','owner','asset-installer'))
      THEN RAISE EXCEPTION 'current event dispatch actor denied' USING ERRCODE='42501'; END IF;
      SELECT * INTO v_runtime FROM public.extension_runtime_binding WHERE org_id=v_org AND project_id=v_project
        AND installation_id=v_install AND generation=v_generation FOR UPDATE;
      IF NOT FOUND OR v_runtime.execution_epoch IS DISTINCT FROM v_epoch
        OR v_runtime.revision IS DISTINCT FROM v_runtime_revision OR v_runtime.enabled IS NOT TRUE
        OR v_runtime.installation_revision IS DISTINCT FROM (p_request#>>'{installationRef,revision}')::bigint
        OR v_runtime.operation_fence IS NOT FALSE OR v_runtime.desired_state IS DISTINCT FROM 'enabled'
        OR v_runtime.observed_state IS DISTINCT FROM 'ready'
      THEN RAISE EXCEPTION 'event dispatch runtime drifted' USING ERRCODE='40001'; END IF;
      PERFORM 1 FROM public.extension_operation_dispatch_binding
        WHERE org_id=v_org AND project_id=v_project AND cutover_group_id=v_group FOR UPDATE;
      GET DIAGNOSTICS v_rows=ROW_COUNT;
      SELECT jsonb_agg(jsonb_build_object('operationId',operation_id,'handlerKind',handler_kind,
        'installationId',installation_id::text,'generation',generation::text,'executionEpoch',execution_epoch,
        'operationFence',operation_fence,'revision',revision,'cutoverGroupId',cutover_group_id::text,
        'cutoverGroupRevision',cutover_group_revision) ORDER BY operation_id) INTO v_before
        FROM public.extension_operation_dispatch_binding
        WHERE org_id=v_org AND project_id=v_project AND cutover_group_id=v_group;
      IF v_rows<>(CASE WHEN v_phase='expand' THEN 9 ELSE 10 END)
        OR EXISTS(SELECT 1 FROM public.extension_operation_dispatch_binding d
          WHERE d.org_id=v_org AND d.project_id=v_project AND d.cutover_group_id=v_group
            AND (d.operation_id<>ALL(v_base||ARRAY['ecommerce_growth_event_control'])
              OR d.handler_kind<>'extension' OR d.installation_id<>v_install OR d.generation<>v_generation
              OR d.execution_epoch<>v_epoch OR d.cutover_group_revision<>v_expected))
        OR EXISTS(SELECT 1 FROM unnest(v_base) b(name) WHERE NOT EXISTS(
          SELECT 1 FROM public.extension_operation_dispatch_binding d WHERE d.org_id=v_org
            AND d.project_id=v_project AND d.cutover_group_id=v_group AND d.operation_id=b.name))
      THEN RAISE EXCEPTION 'complete current event dispatch group required' USING ERRCODE='40001'; END IF;
      SELECT * INTO v_control FROM public.extension_operation_dispatch_binding WHERE org_id=v_org
        AND project_id=v_project AND operation_id='ecommerce_growth_event_control' FOR UPDATE;
      IF (v_phase='expand' AND FOUND) OR (v_phase<>'expand' AND NOT FOUND)
        OR (v_phase='fence' AND v_control.operation_fence IS NOT FALSE)
        OR (v_phase='shrink' AND v_control.operation_fence IS NOT TRUE)
      THEN RAISE EXCEPTION 'event dispatch phase precondition drifted' USING ERRCODE='40001'; END IF;

      IF v_phase='shrink' THEN
        SELECT r.*,count(*) OVER () AS matches INTO v_prior FROM public.extension_event_control_dispatch_receipt r
          WHERE org_id=v_org AND project_id=v_project AND phase='fence'
            AND installation_id=v_install AND generation=v_generation
            AND execution_epoch=v_epoch AND runtime_revision=v_runtime_revision
            AND cutover_group_id=v_group AND target_group_revision=v_expected
            AND case_id=p_request->>'caseId' AND policy_id=p_request->>'schedulePolicyId'
            AND authority_data->'installationRef'=p_request->'installationRef'
            AND after_snapshot=v_before;
        GET DIAGNOSTICS v_rows=ROW_COUNT;
        IF v_rows<>1 OR v_prior.matches<>1 OR v_prior.content_hash IS DISTINCT FROM
            'sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(v_prior.authority_data),'UTF8')),'hex')
          OR v_prior.authority_data->'afterSnapshot' IS DISTINCT FROM v_before
        THEN RAISE EXCEPTION 'exact fence receipt required' USING ERRCODE='40001'; END IF;
        v_prior_ref:=jsonb_build_object('receiptId',v_prior.receipt_id::text,
          'contentHash',v_prior.content_hash);
      END IF;

      UPDATE public.extension_operation_dispatch_binding SET cutover_group_revision=v_target,updated_by=p_actor,
        updated_at=clock_timestamp() WHERE org_id=v_org AND project_id=v_project AND cutover_group_id=v_group;
      IF v_phase='expand' THEN
        INSERT INTO public.extension_operation_dispatch_binding(org_id,project_id,operation_id,handler_kind,
          installation_id,generation,execution_epoch,operation_fence,revision,cutover_group_id,
          cutover_group_revision,updated_by) VALUES(v_org,v_project,'ecommerce_growth_event_control','extension',
          v_install,v_generation,v_epoch,false,1,v_group,v_target,p_actor);
      ELSIF v_phase='fence' THEN
        UPDATE public.extension_operation_dispatch_binding SET operation_fence=true,revision=revision+1,
          updated_by=p_actor,updated_at=clock_timestamp() WHERE org_id=v_org AND project_id=v_project
          AND operation_id='ecommerce_growth_event_control';
      ELSE
        DELETE FROM public.extension_operation_dispatch_binding WHERE org_id=v_org AND project_id=v_project
          AND operation_id='ecommerce_growth_event_control';
      END IF;
      SELECT jsonb_agg(jsonb_build_object('operationId',operation_id,'handlerKind',handler_kind,
        'installationId',installation_id::text,'generation',generation::text,'executionEpoch',execution_epoch,
        'operationFence',operation_fence,'revision',revision,'cutoverGroupId',cutover_group_id::text,
        'cutoverGroupRevision',cutover_group_revision) ORDER BY operation_id) INTO v_after
        FROM public.extension_operation_dispatch_binding
        WHERE org_id=v_org AND project_id=v_project AND cutover_group_id=v_group;
      v_now:=clock_timestamp();
      v_body:=jsonb_build_object('schemaVersion','aos.ecommerce.event-control-dispatch-receipt/v1',
        'tenant',jsonb_build_object('orgId',v_org,'projectId',v_project),'receiptId',v_receipt::text,
        'phase',v_phase,'operationId','ecommerce_growth_event_control','installationRef',p_request->'installationRef',
        'generation',v_generation::text,'executionEpoch',v_epoch,'runtimeRevision',v_runtime_revision,
        'cutoverGroupId',v_group::text,'expectedGroupRevision',v_expected,'targetGroupRevision',v_target,
        'caseId',p_request->>'caseId','schedulePolicyId',p_request->>'schedulePolicyId',
        'approvalRef',v_ref,'idempotencyKey',v_key,'requestHash',v_hash,'beforeSnapshot',v_before,
        'afterSnapshot',coalesce(v_after,'[]'::jsonb),'actor',p_actor,'createdAt',v_now);
      IF v_phase='shrink' THEN
        v_body:=v_body||jsonb_build_object('priorFenceReceiptRef',v_prior_ref);
      END IF;
      v_content_hash:='sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(v_body),'UTF8')),'hex');
      INSERT INTO public.extension_event_control_dispatch_receipt(org_id,project_id,receipt_id,idempotency_key,
        phase,request_hash,installation_id,generation,execution_epoch,runtime_revision,cutover_group_id,
        expected_group_revision,target_group_revision,case_id,policy_id,approval_ref,before_snapshot,
        after_snapshot,actor,authority_data,content_hash,created_at)
      VALUES(v_org,v_project,v_receipt,v_key,v_phase,v_hash,v_install,v_generation,v_epoch,v_runtime_revision,
        v_group,v_expected,v_target,p_request->>'caseId',p_request->>'schedulePolicyId',v_ref,v_before,
        coalesce(v_after,'[]'::jsonb),p_actor,v_body,v_content_hash,v_now);
      RETURN v_body||jsonb_build_object('contentHash',v_content_hash,'replayed',false);
    END $$;
    REVOKE ALL ON FUNCTION public.extension_event_control_dispatch_transition_a0v_054(jsonb,text)
      FROM PUBLIC,aos_runtime;
    GRANT EXECUTE ON FUNCTION public.extension_event_control_dispatch_transition_a0v_054(jsonb,text)
      TO aos_extension_maintainer;
    """)


def downgrade() -> None:
    raise RuntimeError("event control dispatch authority and history must be retained")
