"""Close unaccepted analysis occurrences after an exact released-runtime fence."""
from alembic import op


revision = "a0v_076"
down_revision = "a0v_075"
branch_labels = depends_on = None


def upgrade():
    op.execute(r"""
    DO $migration$
    DECLARE definition text;
      old_mode text := $old$v_released_mode:=NOT v_refresh_mode AND v_phase IN ('fence','shrink')
        AND EXISTS(SELECT 1 FROM public.extension_runtime_binding r
          WHERE r.org_id=v_org AND r.project_id=v_project AND r.installation_id=v_install
            AND r.generation=v_generation AND r.revision=v_runtime_revision
            AND r.execution_epoch>v_epoch AND NOT r.enabled AND r.operation_fence
            AND r.desired_state='enabled' AND r.observed_state='unknown')
        AND 3=(SELECT count(*) FROM public.extension_runtime_resource_lease l
          JOIN public.extension_runtime_operation o USING(org_id,project_id,operation_id)
          WHERE o.org_id=v_org AND o.project_id=v_project AND o.installation_id=v_install
            AND l.generation=v_generation AND l.cleanup_state='released' AND l.observed_release)
        AND NOT EXISTS(SELECT 1 FROM public.extension_runtime_resource_lease l
          JOIN public.extension_runtime_operation o USING(org_id,project_id,operation_id)
          WHERE o.org_id=v_org AND o.project_id=v_project AND o.installation_id=v_install
            AND l.generation=v_generation AND (l.cleanup_state<>'released' OR NOT l.observed_release))
        AND NOT EXISTS(SELECT 1 FROM public.automation_schedule_binding s
          WHERE s.org_id=v_org AND s.project_id=v_project AND s.installation_id=v_install
            AND s.generation=v_generation AND s.enabled)
        AND NOT EXISTS(SELECT 1 FROM public.extension_runtime_execution_attempt a
          WHERE a.org_id=v_org AND a.project_id=v_project AND a.installation_id=v_install
            AND a.generation=v_generation AND a.state='running')
        AND NOT EXISTS(SELECT 1 FROM public.automation_occurrence o
          WHERE o.org_id=v_org AND o.project_id=v_project AND o.installation_id=v_install
            AND o.generation=v_generation AND o.status='claimed')
        AND NOT EXISTS(SELECT 1 FROM public.automation_occurrence_dispatch_attempt a
          JOIN public.automation_occurrence o USING(org_id,project_id,occurrence_id)
          WHERE a.org_id=v_org AND a.project_id=v_project AND o.installation_id=v_install
            AND o.generation=v_generation AND a.status IN ('claimed','unknown'));$old$;
      new_mode text := $new$v_released_mode:=NOT v_refresh_mode AND v_phase IN ('fence','shrink')
        AND EXISTS(SELECT 1 FROM public.extension_runtime_binding r
          WHERE r.org_id=v_org AND r.project_id=v_project AND r.installation_id=v_install
            AND r.generation=v_generation AND r.revision=v_runtime_revision
            AND r.execution_epoch>v_epoch AND NOT r.enabled AND r.operation_fence
            AND r.desired_state='enabled' AND r.observed_state='unknown')
        AND 3=(SELECT count(*) FROM public.extension_runtime_resource_lease l
          JOIN public.extension_runtime_operation o USING(org_id,project_id,operation_id)
          WHERE o.org_id=v_org AND o.project_id=v_project AND o.installation_id=v_install
            AND l.generation=v_generation AND l.cleanup_state='released' AND l.observed_release)
        AND NOT EXISTS(SELECT 1 FROM public.extension_runtime_resource_lease l
          JOIN public.extension_runtime_operation o USING(org_id,project_id,operation_id)
          WHERE o.org_id=v_org AND o.project_id=v_project AND o.installation_id=v_install
            AND l.generation=v_generation AND (l.cleanup_state<>'released' OR NOT l.observed_release))
        AND NOT EXISTS(SELECT 1 FROM public.automation_schedule_binding s
          WHERE s.org_id=v_org AND s.project_id=v_project AND s.installation_id=v_install
            AND s.generation=v_generation AND s.enabled)
        AND NOT EXISTS(SELECT 1 FROM public.extension_runtime_execution_attempt a
          WHERE a.org_id=v_org AND a.project_id=v_project AND a.installation_id=v_install
            AND a.generation=v_generation AND a.state='running')
        AND NOT EXISTS(SELECT 1 FROM public.automation_occurrence o
          WHERE o.org_id=v_org AND o.project_id=v_project AND o.installation_id=v_install
            AND o.generation=v_generation AND o.status='claimed')
        AND NOT EXISTS(SELECT 1 FROM public.automation_occurrence_dispatch_attempt a
          JOIN public.automation_occurrence o USING(org_id,project_id,occurrence_id)
          WHERE a.org_id=v_org AND a.project_id=v_project AND o.installation_id=v_install
            AND o.generation=v_generation AND a.status='claimed')
        AND NOT EXISTS(SELECT 1 FROM public.automation_occurrence_dispatch_attempt a
          JOIN public.automation_occurrence o USING(org_id,project_id,occurrence_id)
          WHERE a.org_id=v_org AND a.project_id=v_project AND o.installation_id=v_install
            AND o.generation=v_generation AND a.status='unknown' AND (
              o.status<>'needs_attention' OR o.trigger_source<>'event'
              OR o.operation_id<>'ecommerce_growth_analysis_advance'
              OR o.receipt_ref IS NOT NULL OR a.receipt_ref IS NOT NULL
              OR a.claim_until>=clock_timestamp()
              OR EXISTS(SELECT 1 FROM public.ecommerce_growth_runtime_command_receipt r
                WHERE r.org_id=o.org_id AND r.project_id=o.project_id
                  AND r.operation_id='ecommerce_growth_analysis_advance'
                  AND r.idempotency_key=a.target_idempotency_key)
              OR EXISTS(SELECT 1 FROM public.ecommerce_investigation_run x
                WHERE x.org_id=o.org_id AND x.project_id=o.project_id
                  AND (x.trigger_key=a.target_idempotency_key OR x.run_id='analysis-'||substr(encode(
                    sha256(convert_to(o.org_id||chr(31)||o.project_id||chr(31)||
                      a.target_idempotency_key,'UTF8')),'hex'),1,32)))));$new$;
    BEGIN
      definition:=pg_get_functiondef(to_regprocedure(
        'public.extension_event_control_dispatch_transition_a0v_054(jsonb,text)'));
      IF definition IS NULL
        OR (length(definition)-length(replace(definition,old_mode,'')))/length(old_mode)<>1
      THEN RAISE EXCEPTION 'exact released event dispatch function required'; END IF;
      EXECUTE replace(definition,old_mode,new_mode);
    END $migration$;

    DO $migration$
    DECLARE definition text;
      old_declare text := 'v_fence record; v_runtime record; v_refresh record; v_refresh_ref jsonb;';
      new_declare text := 'v_fence record; v_runtime record; v_refresh record; v_refresh_ref jsonb; v_released_mode boolean:=false; v_target_key text; v_prior_attempt jsonb:=NULL;';
      old_refresh text := $old$v_refresh_ref:=v_fence.authority_data->'configurationRefreshReceiptRef';
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
      THEN RAISE EXCEPTION 'closure runtime drift' USING ERRCODE='40001'; END IF;$old$;
      new_refresh text := $new$v_refresh_ref:=v_fence.authority_data->'configurationRefreshReceiptRef';
      v_released_mode:=coalesce((v_fence.authority_data->>'releasedRuntimeRecovery')::boolean,false);
      IF v_released_mode THEN
        IF v_refresh_ref IS NOT NULL OR v_runtime.revision<>v_fence.runtime_revision
          OR v_runtime.execution_epoch<=v_fence.execution_epoch OR v_runtime.enabled
          OR NOT v_runtime.operation_fence OR v_runtime.desired_state<>'enabled'
          OR v_runtime.observed_state<>'unknown'
          OR 3<>(SELECT count(*) FROM public.extension_runtime_resource_lease l
            JOIN public.extension_runtime_operation o USING(org_id,project_id,operation_id)
            WHERE o.org_id=v_org AND o.project_id=v_project
              AND o.installation_id=v_fence.installation_id AND l.generation=v_fence.generation
              AND l.cleanup_state='released' AND l.observed_release)
          OR EXISTS(SELECT 1 FROM public.extension_runtime_resource_lease l
            JOIN public.extension_runtime_operation o USING(org_id,project_id,operation_id)
            WHERE o.org_id=v_org AND o.project_id=v_project
              AND o.installation_id=v_fence.installation_id AND l.generation=v_fence.generation
              AND (l.cleanup_state<>'released' OR NOT l.observed_release))
        THEN RAISE EXCEPTION 'released closure runtime required' USING ERRCODE='40001'; END IF;
      ELSIF jsonb_typeof(v_refresh_ref)='object' THEN
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
      IF NOT v_released_mode AND (v_runtime.revision<>v_fence.runtime_revision OR NOT v_runtime.enabled
        OR v_runtime.operation_fence OR v_runtime.desired_state<>'enabled' OR v_runtime.observed_state<>'ready')
      THEN RAISE EXCEPTION 'closure runtime drift' USING ERRCODE='40001'; END IF;$new$;
      old_occurrence text := $old$SELECT * INTO v_o FROM public.automation_occurrence WHERE org_id=v_org AND project_id=v_project
        AND occurrence_id=v_occurrence FOR UPDATE;
      IF NOT FOUND OR v_o.status<>'needs_attention' OR v_o.trigger_source<>'event'
        OR v_o.operation_id<>'ecommerce_growth_analysis_advance' OR v_o.receipt_ref IS NOT NULL
        OR v_o.installation_id<>v_fence.installation_id OR v_o.generation<>v_fence.generation
        OR v_o.execution_epoch<>v_fence.execution_epoch OR v_o.policy_id<>v_fence.policy_id
      THEN RAISE EXCEPTION 'held original event initialization required' USING ERRCODE='55000'; END IF;
      SELECT * INTO v_a FROM public.automation_occurrence_dispatch_attempt WHERE org_id=v_org AND project_id=v_project
        AND occurrence_id=v_occurrence FOR UPDATE;
      IF NOT FOUND OR v_a.status<>'unknown' OR v_a.claim_until>=clock_timestamp() OR v_a.receipt_ref IS NOT NULL
      THEN RAISE EXCEPTION 'expired unknown initialization required' USING ERRCODE='55000'; END IF;$old$;
      new_occurrence text := $new$SELECT * INTO v_o FROM public.automation_occurrence WHERE org_id=v_org AND project_id=v_project
        AND occurrence_id=v_occurrence FOR UPDATE;
      IF NOT FOUND OR v_o.status NOT IN ('needs_attention','pending') OR v_o.trigger_source<>'event'
        OR v_o.operation_id<>'ecommerce_growth_analysis_advance' OR v_o.receipt_ref IS NOT NULL
        OR v_o.installation_id<>v_fence.installation_id OR v_o.generation<>v_fence.generation
        OR v_o.execution_epoch<>v_fence.execution_epoch OR v_o.policy_id<>v_fence.policy_id
      THEN RAISE EXCEPTION 'unaccepted original event initialization required' USING ERRCODE='55000'; END IF;
      SELECT * INTO v_a FROM public.automation_occurrence_dispatch_attempt WHERE org_id=v_org AND project_id=v_project
        AND occurrence_id=v_occurrence FOR UPDATE;
      IF v_o.status='needs_attention' THEN
        IF NOT FOUND OR v_a.status<>'unknown' OR v_a.claim_until>=clock_timestamp() OR v_a.receipt_ref IS NOT NULL
        THEN RAISE EXCEPTION 'expired unknown initialization required' USING ERRCODE='55000'; END IF;
        v_prior_attempt:=to_jsonb(v_a); v_target_key:=v_a.target_idempotency_key;
      ELSE
        IF FOUND THEN RAISE EXCEPTION 'pending initialization must be unclaimed' USING ERRCODE='55000'; END IF;
        v_target_key:='automation-occurrence:'||v_occurrence::text;
      END IF;$new$;
      old_target text := $old$v_run_id:='analysis-'||substr(encode(sha256(convert_to(v_org||chr(31)||v_project||chr(31)||
        v_a.target_idempotency_key,'UTF8')),'hex'),1,32);
      SELECT count(*) INTO v_receipt_count FROM public.ecommerce_growth_runtime_command_receipt
        WHERE org_id=v_org AND project_id=v_project AND operation_id='ecommerce_growth_analysis_advance'
          AND idempotency_key=v_a.target_idempotency_key;
      SELECT count(*) INTO v_run_count FROM public.ecommerce_investigation_run WHERE org_id=v_org AND project_id=v_project
        AND (run_id=v_run_id OR trigger_key=v_a.target_idempotency_key);$old$;
      new_target text := $new$v_run_id:='analysis-'||substr(encode(sha256(convert_to(v_org||chr(31)||v_project||chr(31)||
        v_target_key,'UTF8')),'hex'),1,32);
      SELECT count(*) INTO v_receipt_count FROM public.ecommerce_growth_runtime_command_receipt
        WHERE org_id=v_org AND project_id=v_project AND operation_id='ecommerce_growth_analysis_advance'
          AND idempotency_key=v_target_key;
      SELECT count(*) INTO v_run_count FROM public.ecommerce_investigation_run WHERE org_id=v_org AND project_id=v_project
        AND (run_id=v_run_id OR trigger_key=v_target_key);$new$;
      old_body text := $old$'priorOccurrence',to_jsonb(v_o),'priorAttempt',to_jsonb(v_a),'origin',v_origin_body,$old$;
      new_body text := $new$'priorOccurrence',to_jsonb(v_o),'priorAttempt',v_prior_attempt,'origin',v_origin_body,
        'closureMode',CASE WHEN v_o.status='pending' THEN 'pending_unclaimed' ELSE 'expired_unknown' END,$new$;
      old_key text := $old$'runId',v_run_id,'targetIdempotencyKey',v_a.target_idempotency_key,'checkedAt',v_now)$old$;
      new_key text := $new$'runId',v_run_id,'targetIdempotencyKey',v_target_key,'checkedAt',v_now)$new$;
    BEGIN
      definition:=pg_get_functiondef(to_regprocedure(
        'public.ecommerce_unaccepted_analysis_close_a0v_060(jsonb,text)'));
      IF definition IS NULL
        OR (length(definition)-length(replace(definition,old_declare,'')))/length(old_declare)<>1
        OR (length(definition)-length(replace(definition,old_refresh,'')))/length(old_refresh)<>1
        OR (length(definition)-length(replace(definition,old_occurrence,'')))/length(old_occurrence)<>1
        OR (length(definition)-length(replace(definition,old_target,'')))/length(old_target)<>1
        OR (length(definition)-length(replace(definition,old_body,'')))/length(old_body)<>1
        OR (length(definition)-length(replace(definition,old_key,'')))/length(old_key)<>1
      THEN RAISE EXCEPTION 'exact unaccepted closure function required'; END IF;
      definition:=replace(definition,old_declare,new_declare);
      definition:=replace(definition,old_refresh,new_refresh);
      definition:=replace(definition,old_occurrence,new_occurrence);
      definition:=replace(definition,old_target,new_target);
      definition:=replace(definition,old_body,new_body);
      definition:=replace(definition,old_key,new_key);
      EXECUTE definition;
    END $migration$;
    """)


def downgrade():
    raise RuntimeError("released occurrence retirement authority must be retained")
