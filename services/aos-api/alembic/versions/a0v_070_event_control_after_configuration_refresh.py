"""Permit event-control retirement after an exact dispatch configuration refresh."""
from alembic import op

revision = "a0v_070"
down_revision = "a0v_069"
branch_labels = depends_on = None


def upgrade() -> None:
    op.execute(r"""
    CREATE OR REPLACE FUNCTION public.extension_event_control_dispatch_transition_a0v_054(p_request jsonb,p_actor text)
    RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
    DECLARE
      v_org text:=nullif(current_setting('aos.org_id',true),'');
      v_project text:=nullif(current_setting('aos.project_id',true),'');
      v_phase text; v_key text; v_install uuid; v_generation uuid; v_group uuid;
      v_epoch bigint; v_runtime_revision bigint; v_expected bigint; v_target bigint;
      v_prior record; v_prior_ref jsonb := NULL; v_refresh record; v_refresh_mode boolean:=false;
      v_running bigint; v_claimed bigint; v_dispatching bigint; v_drain jsonb;
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

      SELECT * INTO v_refresh FROM public.extension_dispatch_configuration_refresh_receipt
        WHERE org_id=v_org AND project_id=v_project AND cutover_group_id=v_group
          AND installation_id=v_install AND generation=v_generation
        ORDER BY revision DESC LIMIT 1 FOR SHARE;
      v_refresh_mode:=FOUND AND v_phase IN ('fence','shrink');
      IF v_refresh_mode AND (
          v_refresh.request->>'sourceExecutionEpoch' IS DISTINCT FROM v_epoch::text
          OR v_refresh.request->>'targetRuntimeRevision' IS DISTINCT FROM v_runtime_revision::text
          OR v_refresh.request->>'cutoverGroupId' IS DISTINCT FROM v_group::text
          OR v_refresh.request->>'generation' IS DISTINCT FROM v_generation::text
          OR v_refresh.request#>>'{installationRef,installationId}' IS DISTINCT FROM v_install::text
          OR v_refresh.request->'externalEffectsAllowed' IS DISTINCT FROM 'false'::jsonb
          OR v_refresh.request->'resumeBusinessRuns' IS DISTINCT FROM 'false'::jsonb
          OR v_refresh.body->'request' IS DISTINCT FROM v_refresh.request
          OR v_refresh.request_hash IS DISTINCT FROM 'sha256:'||encode(sha256(convert_to(
            public.canonical_asset_registry_jsonb(v_refresh.request),'UTF8')),'hex')
          OR v_refresh.content_hash IS DISTINCT FROM 'sha256:'||encode(sha256(convert_to(
            public.canonical_asset_registry_jsonb(v_refresh.body),'UTF8')),'hex'))
      THEN RAISE EXCEPTION 'latest configuration refresh does not authorize event retirement'
        USING ERRCODE='40001'; END IF;

      SELECT * INTO v_runtime FROM public.extension_runtime_binding WHERE org_id=v_org AND project_id=v_project
        AND installation_id=v_install AND generation=v_generation FOR UPDATE;
      IF NOT FOUND
        OR v_runtime.revision IS DISTINCT FROM v_runtime_revision OR v_runtime.enabled IS NOT TRUE
        OR v_runtime.installation_revision IS DISTINCT FROM (p_request#>>'{installationRef,revision}')::bigint
        OR v_runtime.operation_fence IS NOT FALSE OR v_runtime.desired_state IS DISTINCT FROM 'enabled'
        OR v_runtime.observed_state IS DISTINCT FROM 'ready'
        OR (NOT v_refresh_mode AND v_runtime.execution_epoch IS DISTINCT FROM v_epoch)
        OR (v_refresh_mode AND (
          v_runtime.execution_epoch IS DISTINCT FROM (v_refresh.request->>'targetExecutionEpoch')::bigint
          OR v_runtime.config_ref IS DISTINCT FROM v_refresh.request->'targetConfigurationRef'))
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
              OR d.handler_kind<>'extension' OR d.installation_id<>v_install OR d.generation<>v_generation))
        OR EXISTS(SELECT 1 FROM unnest(v_base) b(name) WHERE NOT EXISTS(
          SELECT 1 FROM public.extension_operation_dispatch_binding d WHERE d.org_id=v_org
            AND d.project_id=v_project AND d.cutover_group_id=v_group AND d.operation_id=b.name))
        OR (NOT v_refresh_mode AND EXISTS(SELECT 1 FROM public.extension_operation_dispatch_binding d
          WHERE d.org_id=v_org AND d.project_id=v_project AND d.cutover_group_id=v_group
            AND (d.execution_epoch<>v_epoch OR d.cutover_group_revision<>v_expected)))
        OR (v_refresh_mode AND EXISTS(SELECT 1 FROM public.extension_operation_dispatch_binding d
          WHERE d.org_id=v_org AND d.project_id=v_project AND d.cutover_group_id=v_group
            AND d.operation_id=ANY(v_base) AND (
              d.execution_epoch<>(v_refresh.request->>'targetExecutionEpoch')::bigint
              OR d.operation_fence OR d.cutover_group_revision<>v_expected)))
        OR (v_refresh_mode AND v_phase='fence' AND
          v_expected<>(v_refresh.request->>'expectedGroupRevision')::bigint+1)
      THEN RAISE EXCEPTION 'complete current event dispatch group required' USING ERRCODE='40001'; END IF;
      SELECT * INTO v_control FROM public.extension_operation_dispatch_binding WHERE org_id=v_org
        AND project_id=v_project AND operation_id='ecommerce_growth_event_control' FOR UPDATE;
      IF (v_phase='expand' AND FOUND) OR (v_phase<>'expand' AND NOT FOUND)
        OR (v_phase='fence' AND v_control.operation_fence IS NOT FALSE)
        OR (v_phase='shrink' AND v_control.operation_fence IS NOT TRUE)
        OR (v_refresh_mode AND v_control.execution_epoch<>v_epoch)
        OR (v_refresh_mode AND v_phase='fence' AND v_control.cutover_group_revision<>v_expected-1)
        OR (v_refresh_mode AND v_phase='shrink' AND v_control.cutover_group_revision<>v_expected)
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
        SELECT count(*) INTO v_running FROM public.extension_runtime_execution_attempt a
          WHERE a.org_id=v_org AND a.project_id=v_project AND a.installation_id=v_install
            AND a.generation=v_generation AND a.state='running';
        SELECT count(*) INTO v_claimed FROM public.automation_occurrence o
          WHERE o.org_id=v_org AND o.project_id=v_project AND o.installation_id=v_install
            AND o.generation=v_generation AND o.execution_epoch=v_epoch AND o.status='claimed';
        SELECT count(*) INTO v_dispatching FROM public.automation_occurrence_dispatch_attempt a
          JOIN public.automation_occurrence o USING(org_id,project_id,occurrence_id)
          WHERE a.org_id=v_org AND a.project_id=v_project AND o.installation_id=v_install
            AND o.generation=v_generation AND o.execution_epoch=v_epoch
            AND a.status IN ('claimed','unknown');
        IF v_running<>0 OR v_claimed<>0 OR v_dispatching<>0
        THEN RAISE EXCEPTION 'event dispatch target is not drained' USING ERRCODE='55000'; END IF;
        v_drain:=jsonb_build_object('installationId',v_install::text,'generation',v_generation::text,
          'executionEpoch',v_epoch,'runningExecutionAttempts',v_running,
          'claimedOccurrences',v_claimed,'unresolvedDispatchAttempts',v_dispatching,
          'checkedAt',clock_timestamp());
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
      IF v_refresh_mode THEN
        v_body:=v_body||jsonb_build_object('configurationRefreshReceiptRef',jsonb_build_object(
          'resourceType','DispatchConfigurationRefreshReceipt','resourceId',v_refresh.receipt_id::text,
          'revision',v_refresh.revision,'contentHash',v_refresh.content_hash));
      END IF;
      IF v_phase='shrink' THEN
        v_body:=v_body||jsonb_build_object('priorFenceReceiptRef',v_prior_ref,'drainEvidence',v_drain);
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
    raise RuntimeError("event-control refresh continuation authority must be retained")
