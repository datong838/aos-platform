"""Permit negative event retirement after an exact runtime lease release."""
from alembic import op

revision='a0v_074'
down_revision='a0v_073'
branch_labels=depends_on=None


def upgrade():
    op.execute(r"""
    DO $migration$
    DECLARE definition text;
      old_declare text := 'v_prior record; v_prior_ref jsonb := NULL; v_refresh record; v_refresh_mode boolean:=false;';
      new_declare text := 'v_prior record; v_prior_ref jsonb := NULL; v_refresh record; v_refresh_mode boolean:=false; v_released_mode boolean:=false;';
      old_mode text := 'v_refresh_mode:=FOUND AND v_phase IN (''fence'',''shrink'');';
      new_mode text := $body$v_refresh_mode:=FOUND AND v_phase IN ('fence','shrink');
      v_released_mode:=NOT v_refresh_mode AND v_phase IN ('fence','shrink')
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
            AND o.generation=v_generation AND a.status IN ('claimed','unknown'));$body$;
      old_runtime text := $body$IF NOT FOUND
        OR v_runtime.revision IS DISTINCT FROM v_runtime_revision OR v_runtime.enabled IS NOT TRUE
        OR v_runtime.installation_revision IS DISTINCT FROM (p_request#>>'{installationRef,revision}')::bigint
        OR v_runtime.operation_fence IS NOT FALSE OR v_runtime.desired_state IS DISTINCT FROM 'enabled'
        OR v_runtime.observed_state IS DISTINCT FROM 'ready'
        OR (NOT v_refresh_mode AND v_runtime.execution_epoch IS DISTINCT FROM v_epoch)
        OR (v_refresh_mode AND (
          v_runtime.execution_epoch IS DISTINCT FROM (v_refresh.request->>'targetExecutionEpoch')::bigint
          OR v_runtime.config_ref IS DISTINCT FROM v_refresh.request->'targetConfigurationRef'))
      THEN RAISE EXCEPTION 'event dispatch runtime drifted' USING ERRCODE='40001'; END IF;$body$;
      new_runtime text := $body$IF NOT FOUND
        OR v_runtime.revision IS DISTINCT FROM v_runtime_revision
        OR v_runtime.installation_revision IS DISTINCT FROM (p_request#>>'{installationRef,revision}')::bigint
        OR (NOT v_released_mode AND (v_runtime.enabled IS NOT TRUE
          OR v_runtime.operation_fence IS NOT FALSE OR v_runtime.desired_state IS DISTINCT FROM 'enabled'
          OR v_runtime.observed_state IS DISTINCT FROM 'ready'))
        OR (v_released_mode AND (v_runtime.enabled OR NOT v_runtime.operation_fence
          OR v_runtime.desired_state IS DISTINCT FROM 'enabled'
          OR v_runtime.observed_state IS DISTINCT FROM 'unknown'
          OR v_runtime.execution_epoch<=v_epoch))
        OR (NOT v_refresh_mode AND NOT v_released_mode
          AND v_runtime.execution_epoch IS DISTINCT FROM v_epoch)
        OR (v_refresh_mode AND (
          v_runtime.execution_epoch IS DISTINCT FROM (v_refresh.request->>'targetExecutionEpoch')::bigint
          OR v_runtime.config_ref IS DISTINCT FROM v_refresh.request->'targetConfigurationRef'))
      THEN RAISE EXCEPTION 'event dispatch runtime drifted' USING ERRCODE='40001'; END IF;$body$;
      old_body text := $body$'afterSnapshot',coalesce(v_after,'[]'::jsonb),'actor',p_actor,'createdAt',v_now);$body$;
      new_body text := $body$'afterSnapshot',coalesce(v_after,'[]'::jsonb),'actor',p_actor,'createdAt',v_now,
        'releasedRuntimeRecovery',v_released_mode);$body$;
    BEGIN
      definition:=pg_get_functiondef(to_regprocedure(
        'public.extension_event_control_dispatch_transition_a0v_054(jsonb,text)'));
      IF definition IS NULL
        OR (length(definition)-length(replace(definition,old_declare,'')))/length(old_declare)<>1
        OR (length(definition)-length(replace(definition,old_mode,'')))/length(old_mode)<>1
        OR (length(definition)-length(replace(definition,old_runtime,'')))/length(old_runtime)<>1
        OR (length(definition)-length(replace(definition,old_body,'')))/length(old_body)<>1
      THEN RAISE EXCEPTION 'exact current event dispatch function required'; END IF;
      definition:=replace(definition,old_declare,new_declare);
      definition:=replace(definition,old_mode,new_mode);
      definition:=replace(definition,old_runtime,new_runtime);
      definition:=replace(definition,old_body,new_body);
      EXECUTE definition;
    END $migration$;
    """)


def downgrade():
    raise RuntimeError('released event retirement authority must be retained')
