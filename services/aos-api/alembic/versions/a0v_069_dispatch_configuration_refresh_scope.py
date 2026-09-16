"""Limit configuration refresh mutation to the nine requested business operations."""
from alembic import op

revision='a0v_069'
down_revision='a0v_068'
branch_labels=depends_on=None


def upgrade():
    op.execute(r'''
    CREATE OR REPLACE FUNCTION public.extension_dispatch_configuration_refresh_a0v_068(
      p_request jsonb,p_actor text) RETURNS uuid
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
    DECLARE v_org text:=NULLIF(current_setting('aos.org_id',true),'');
      v_project text:=NULLIF(current_setting('aos.project_id',true),'');
      v_now timestamptz:=clock_timestamp(); v_hash text; v_existing record;
      v_root record; v_parent record; v_binding record; v_installation record;
      v_configure record; v_enable record; v_configure_target jsonb; v_enable_target jsonb;
      v_group uuid; v_installation_id uuid; v_generation uuid; v_receipt uuid:=gen_random_uuid();
      v_revision bigint; v_expected_group bigint; v_operations text[]; v_rows bigint;
      v_body jsonb; v_content_hash text; v_previous_id uuid; v_previous_hash text;
    BEGIN
      IF v_org IS NULL OR v_project IS NULL OR p_actor IS NULL OR p_actor<>btrim(p_actor)
        OR length(p_actor) NOT BETWEEN 1 AND 240
        OR NOT pg_has_role(session_user,'aos_extension_maintainer','member')
        OR EXISTS(SELECT 1 FROM pg_catalog.pg_roles WHERE rolname=session_user AND (rolsuper OR rolbypassrls))
      THEN RAISE EXCEPTION 'dedicated non-privileged configuration maintainer is required'
        USING ERRCODE='42501'; END IF;
      IF p_request->>'schemaVersion'<>'aos.ecommerce.dispatch-configuration-refresh/v1'
        OR p_request->>'orgId' IS DISTINCT FROM v_org OR p_request->>'projectId' IS DISTINCT FROM v_project
        OR p_request->'externalEffectsAllowed'<>'false'::jsonb OR p_request->'resumeBusinessRuns'<>'false'::jsonb
      THEN RAISE EXCEPTION 'exact tenant-scoped configuration refresh request required'
        USING ERRCODE='23514'; END IF;
      v_hash:=public.canonical_bundle_control_sha256(p_request);
      SELECT * INTO v_existing FROM public.extension_dispatch_configuration_refresh_receipt
        WHERE org_id=v_org AND project_id=v_project
          AND cutover_group_id=(p_request->>'cutoverGroupId')::uuid
          AND idempotency_key=p_request->>'idempotencyKey';
      IF FOUND THEN
        IF v_existing.request_hash<>v_hash OR v_existing.actor<>p_actor OR v_existing.request<>p_request
          OR EXISTS(SELECT 1 FROM public.extension_dispatch_configuration_refresh_receipt newer
            WHERE newer.org_id=v_org AND newer.project_id=v_project
              AND newer.cutover_group_id=v_existing.cutover_group_id
              AND newer.revision>v_existing.revision)
        THEN RAISE EXCEPTION 'configuration refresh idempotency conflict' USING ERRCODE='23505'; END IF;
        RETURN v_existing.receipt_id;
      END IF;

      v_group:=(p_request->>'cutoverGroupId')::uuid;
      v_installation_id:=(p_request->'installationRef'->>'installationId')::uuid;
      v_generation:=(p_request->>'generation')::uuid;
      v_expected_group:=(p_request->>'expectedGroupRevision')::bigint;
      SELECT i.*,r.lock_hash,r.overlay_revision INTO v_installation
        FROM public.bundle_installation i JOIN public.bundle_installation_revision r
          ON r.org_id=i.org_id AND r.project_id=i.project_id AND r.installation_pk=i.installation_pk
         AND r.revision=i.active_revision
        WHERE i.org_id=v_org AND i.project_id=v_project AND i.installation_id=v_installation_id FOR UPDATE OF i;
      IF NOT FOUND OR v_installation.active_revision<>(p_request->'installationRef'->>'revision')::bigint
        OR v_installation.lock_hash<>p_request->'installationRef'->>'lockHash'
        OR v_installation.overlay_revision<>p_request->'installationRef'->>'overlayRevision'
      THEN RAISE EXCEPTION 'current installation authority drifted' USING ERRCODE='40001'; END IF;

      SELECT * INTO v_root FROM public.extension_dispatch_cutover_operation
        WHERE org_id=v_org AND project_id=v_project AND cutover_group_id=v_group
          AND kind='activate' AND status='resumed' AND target_installation_id=v_installation_id
          AND target_generation=v_generation FOR UPDATE;
      IF NOT FOUND THEN RAISE EXCEPTION 'resumed activation root unavailable' USING ERRCODE='55000'; END IF;
      SELECT * INTO v_parent FROM public.extension_dispatch_configuration_refresh_receipt
        WHERE org_id=v_org AND project_id=v_project AND cutover_group_id=v_group
        ORDER BY revision DESC LIMIT 1 FOR UPDATE;
      IF FOUND THEN
        v_revision:=v_parent.revision+1;v_previous_id:=v_parent.receipt_id;v_previous_hash:=v_parent.content_hash;
        IF p_request->'sourceAuthorityRef' IS DISTINCT FROM jsonb_build_object(
          'resourceType','DispatchConfigurationRefreshReceipt','resourceId',v_parent.receipt_id::text,
          'revision',v_parent.revision,'contentHash',v_parent.content_hash)
        THEN RAISE EXCEPTION 'latest configuration refresh authority required' USING ERRCODE='40001'; END IF;
      ELSE
        v_revision:=1;
        PERFORM 1 FROM public.extension_dispatch_cutover_receipt r
          WHERE r.org_id=v_org AND r.project_id=v_project AND r.cutover_operation_id=v_root.cutover_operation_id
            AND r.phase='resume' AND p_request->'sourceAuthorityRef'=jsonb_build_object(
              'resourceType','CutoverResumeReceipt','resourceId',r.receipt_id::text,
              'revision',1,'contentHash',r.content_hash);
        IF NOT FOUND THEN RAISE EXCEPTION 'original resume authority required' USING ERRCODE='40001'; END IF;
      END IF;

      SELECT * INTO v_binding FROM public.extension_runtime_binding
        WHERE org_id=v_org AND project_id=v_project AND installation_id=v_installation_id
          AND generation=v_generation FOR UPDATE;
      IF NOT FOUND OR v_binding.revision<>(p_request->>'targetRuntimeRevision')::bigint
        OR v_binding.execution_epoch<>(p_request->>'targetExecutionEpoch')::bigint
        OR v_binding.config_ref IS DISTINCT FROM p_request->'targetConfigurationRef'
        OR NOT v_binding.enabled OR v_binding.operation_fence
        OR v_binding.desired_state<>'enabled' OR v_binding.observed_state<>'ready'
      THEN RAISE EXCEPTION 'target runtime binding is not exact and ready' USING ERRCODE='40001'; END IF;

      SELECT * INTO v_configure FROM public.extension_runtime_operation
        WHERE org_id=v_org AND project_id=v_project
          AND operation_id=(p_request->>'configureOperationId')::uuid FOR UPDATE;
      SELECT payload->'configurationTarget' INTO v_configure_target FROM public.extension_runtime_event
        WHERE org_id=v_org AND project_id=v_project AND operation_id=v_configure.operation_id
          AND sequence=1 AND type='accepted';
      IF NOT FOUND OR v_configure.kind<>'configure' OR v_configure.status<>'succeeded' OR v_configure.phase<>'succeeded'
        OR v_configure.installation_id<>v_installation_id OR v_configure.requested_by<>p_actor
        OR v_configure.revision<>(p_request->>'configureOperationRevision')::bigint
        OR v_configure_target IS DISTINCT FROM jsonb_build_object('generation',v_generation::text,
          'bindingRevision',(p_request->>'sourceRuntimeRevision')::bigint,
          'configRef',p_request->'targetConfigurationRef')
      THEN RAISE EXCEPTION 'completed exact configure operation required' USING ERRCODE='40001'; END IF;

      SELECT * INTO v_enable FROM public.extension_runtime_operation
        WHERE org_id=v_org AND project_id=v_project
          AND operation_id=(p_request->>'enableOperationId')::uuid FOR UPDATE;
      SELECT payload->'configurationTarget' INTO v_enable_target FROM public.extension_runtime_event
        WHERE org_id=v_org AND project_id=v_project AND operation_id=v_enable.operation_id
          AND sequence=1 AND type='accepted';
      IF NOT FOUND OR v_enable.kind<>'enable' OR v_enable.status<>'succeeded' OR v_enable.phase<>'succeeded'
        OR v_enable.installation_id<>v_installation_id OR v_enable.requested_by<>p_actor
        OR v_enable.revision<>(p_request->>'enableOperationRevision')::bigint
        OR v_enable_target IS DISTINCT FROM jsonb_build_object('generation',v_generation::text,
          'bindingRevision',(p_request->>'targetRuntimeRevision')::bigint-1,
          'configRef',p_request->'targetConfigurationRef')
      THEN RAISE EXCEPTION 'completed exact enable operation required' USING ERRCODE='40001'; END IF;

      SELECT array_agg(value ORDER BY value) INTO v_operations
        FROM jsonb_array_elements_text(p_request->'operationIds');
      PERFORM 1 FROM public.extension_operation_dispatch_binding d
        WHERE d.org_id=v_org AND d.project_id=v_project AND d.cutover_group_id=v_group
          AND d.operation_id=ANY(v_operations) ORDER BY d.operation_id FOR UPDATE;
      IF v_operations IS DISTINCT FROM ARRAY(SELECT d.operation_id FROM public.extension_operation_dispatch_binding d
          WHERE d.org_id=v_org AND d.project_id=v_project AND d.cutover_group_id=v_group
            AND d.operation_id=ANY(v_operations) ORDER BY d.operation_id)
        OR EXISTS(SELECT 1 FROM public.extension_operation_dispatch_binding d
          WHERE d.org_id=v_org AND d.project_id=v_project AND d.cutover_group_id=v_group
            AND d.operation_id=ANY(v_operations) AND (d.handler_kind<>'extension' OR d.installation_id<>v_installation_id OR d.generation<>v_generation
              OR d.execution_epoch<>(p_request->>'sourceExecutionEpoch')::bigint OR d.operation_fence
              OR d.cutover_group_revision<>v_expected_group))
      THEN RAISE EXCEPTION 'source dispatch group authority drifted' USING ERRCODE='40001'; END IF;
      UPDATE public.extension_operation_dispatch_binding SET
        execution_epoch=(p_request->>'targetExecutionEpoch')::bigint,revision=revision+1,
        cutover_group_revision=v_expected_group+1,updated_by=p_actor,updated_at=v_now
        WHERE org_id=v_org AND project_id=v_project AND cutover_group_id=v_group
          AND operation_id=ANY(v_operations);
      GET DIAGNOSTICS v_rows=ROW_COUNT;
      IF v_rows<>cardinality(v_operations) THEN RAISE EXCEPTION 'dispatch refresh group update was not exact'
        USING ERRCODE='40001'; END IF;
      v_body:=jsonb_build_object('schemaVersion','aos.ecommerce.dispatch-configuration-refresh-receipt/v1',
        'receiptId',v_receipt::text,'revision',v_revision,'activationOperationId',v_root.cutover_operation_id::text,
        'activationResumeReceiptId',CASE WHEN v_revision=1 THEN p_request->'sourceAuthorityRef'->>'resourceId'
          ELSE v_parent.activation_resume_receipt_id::text END,'actor',p_actor,'request',p_request,
        'requestHash',v_hash,'createdAt',to_char(v_now AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US+00:00'));
      v_content_hash:=public.canonical_bundle_control_sha256(v_body);
      INSERT INTO public.extension_dispatch_configuration_refresh_receipt(
        org_id,project_id,cutover_group_id,receipt_id,revision,activation_operation_id,
        activation_resume_receipt_id,installation_id,generation,previous_receipt_id,previous_hash,
        actor,idempotency_key,request,request_hash,body,content_hash,created_at)
      VALUES(v_org,v_project,v_group,v_receipt,v_revision,v_root.cutover_operation_id,
        CASE WHEN v_revision=1 THEN (p_request->'sourceAuthorityRef'->>'resourceId')::uuid
          ELSE v_parent.activation_resume_receipt_id END,v_installation_id,v_generation,
        v_previous_id,v_previous_hash,p_actor,p_request->>'idempotencyKey',p_request,v_hash,
        v_body,v_content_hash,v_now);
      RETURN v_receipt;
    END $$;
    REVOKE ALL ON FUNCTION public.extension_dispatch_configuration_refresh_a0v_068(jsonb,text)
      FROM PUBLIC,aos_runtime;
    GRANT EXECUTE ON FUNCTION public.extension_dispatch_configuration_refresh_a0v_068(jsonb,text)
      TO aos_extension_maintainer;
    ''')


def downgrade():
    raise RuntimeError('configuration refresh execution authority must be retained')
