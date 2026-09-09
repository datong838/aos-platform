"""Validation-window rollback authority for ecommerce growth cutover."""

from alembic import op


revision = "ar2_016"
down_revision = "ar2_015"
branch_labels = depends_on = None


def upgrade() -> None:
    op.execute("""
    ALTER TABLE extension_dispatch_cutover_operation
      ADD COLUMN parent_cutover_operation_id uuid,
      ADD COLUMN parent_receipt_ref jsonb,
      ADD COLUMN failure_reason text;
    ALTER TABLE extension_dispatch_cutover_operation
      ADD CONSTRAINT extension_dispatch_cutover_parent_fk
      FOREIGN KEY(org_id,project_id,parent_cutover_operation_id)
      REFERENCES extension_dispatch_cutover_operation(org_id,project_id,cutover_operation_id);
    ALTER TABLE extension_dispatch_cutover_operation
      ADD CONSTRAINT extension_dispatch_cutover_parent_shape CHECK(
        (kind='activate' AND parent_cutover_operation_id IS NULL
          AND parent_receipt_ref IS NULL AND failure_reason IS NULL)
        OR
        (kind='rollback' AND parent_cutover_operation_id IS NOT NULL
          AND jsonb_typeof(parent_receipt_ref)='object'
          AND length(failure_reason) BETWEEN 1 AND 1000));

    CREATE OR REPLACE FUNCTION extension_dispatch_cutover_history_guard_ar2_014() RETURNS trigger
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
      DECLARE v_phase text;
      BEGIN
        v_phase:=CASE
          WHEN NEW.kind='activate' AND NEW.status='draining' THEN 'pause'
          WHEN NEW.kind='activate' AND NEW.status='committed' THEN 'commit'
          WHEN NEW.kind='activate' AND NEW.status='validated' THEN 'validate'
          WHEN NEW.kind='activate' AND NEW.status='resumed' THEN 'resume'
          WHEN NEW.kind='rollback' AND NEW.status='draining' THEN 'fence'
          WHEN NEW.kind='rollback' AND NEW.status='rolled_back' THEN 'rollback'
          ELSE NULL END;
        IF v_phase IS NOT NULL AND OLD.status IS DISTINCT FROM NEW.status
          AND NOT EXISTS(SELECT 1 FROM public.extension_dispatch_cutover_receipt r
            WHERE r.org_id=NEW.org_id AND r.project_id=NEW.project_id
              AND r.cutover_operation_id=NEW.cutover_operation_id AND r.phase=v_phase)
        THEN RAISE EXCEPTION '% cutover requires % Receipt',NEW.status,v_phase
          USING ERRCODE='23514'; END IF;
        RETURN NEW;
      END $$;

    CREATE FUNCTION extension_dispatch_cutover_fence_rollback_ar2_016(
      p_cutover_operation_id uuid,p_actor text) RETURNS bigint
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
      DECLARE v_org text:=NULLIF(current_setting('aos.org_id',true),'');
        v_project text:=NULLIF(current_setting('aos.project_id',true),'');
        v_operation record; v_parent record; v_gate record; v_snapshot jsonb;
        v_rows bigint; v_now timestamptz:=clock_timestamp();
      BEGIN
        IF v_org IS NULL OR v_project IS NULL OR length(BTRIM(p_actor)) NOT BETWEEN 1 AND 240
          OR NOT pg_has_role(session_user,'aos_extension_maintainer','member')
          OR EXISTS(SELECT 1 FROM pg_catalog.pg_roles
            WHERE rolname=session_user AND (rolsuper OR rolbypassrls))
        THEN RAISE EXCEPTION 'dedicated non-privileged cutover maintainer is required'
          USING ERRCODE='42501'; END IF;
        SELECT * INTO v_operation FROM public.extension_dispatch_cutover_operation
          WHERE org_id=v_org AND project_id=v_project
            AND cutover_operation_id=p_cutover_operation_id FOR UPDATE;
        IF NOT FOUND OR v_operation.kind<>'rollback' OR v_operation.status<>'fencing'
        THEN RAISE EXCEPTION 'rollback operation is not fencing' USING ERRCODE='55000'; END IF;
        SELECT * INTO v_parent FROM public.extension_dispatch_cutover_operation
          WHERE org_id=v_org AND project_id=v_project
            AND cutover_operation_id=v_operation.parent_cutover_operation_id FOR UPDATE;
        IF NOT FOUND OR v_parent.kind<>'activate' OR v_parent.status NOT IN ('committed','validated')
        THEN RAISE EXCEPTION 'activation is outside validation rollback window'
          USING ERRCODE='55000'; END IF;
        PERFORM 1 FROM public.extension_runtime_binding r
          WHERE r.org_id=v_org AND r.project_id=v_project
            AND r.installation_id=v_parent.target_installation_id
            AND r.generation=v_parent.target_generation
            AND r.execution_epoch=v_parent.target_execution_epoch
            AND r.revision=v_parent.target_runtime_revision+1
            AND r.desired_state='enabled' AND r.observed_state='ready'
            AND NOT r.enabled AND r.operation_fence FOR UPDATE;
        IF NOT FOUND THEN RAISE EXCEPTION 'target runtime drain fence drifted'
          USING ERRCODE='40001'; END IF;
        SELECT * INTO v_gate FROM public.extension_dispatch_claim_gate
          WHERE org_id=v_org AND project_id=v_project
            AND cutover_group_id=v_parent.cutover_group_id FOR UPDATE;
        IF NOT FOUND OR v_gate.cutover_operation_id<>v_parent.cutover_operation_id
          OR NOT v_gate.claim_paused
        THEN RAISE EXCEPTION 'activation claim gate is not exact and paused'
          USING ERRCODE='40001'; END IF;
        PERFORM 1 FROM public.extension_operation_dispatch_binding d
          WHERE d.org_id=v_org AND d.project_id=v_project
            AND d.cutover_group_id=v_operation.cutover_group_id
          ORDER BY d.operation_id FOR UPDATE;
        SELECT jsonb_agg(jsonb_build_object(
          'operationId',d.operation_id,'handlerKind',d.handler_kind,
          'installationId',d.installation_id::text,'generation',d.generation::text,
          'executionEpoch',d.execution_epoch,'operationFence',d.operation_fence,
          'revision',d.revision,'cutoverGroupId',d.cutover_group_id::text,
          'cutoverGroupRevision',d.cutover_group_revision) ORDER BY d.operation_id)
          INTO v_snapshot FROM public.extension_operation_dispatch_binding d
          WHERE d.org_id=v_org AND d.project_id=v_project
            AND d.cutover_group_id=v_operation.cutover_group_id;
        IF v_snapshot IS DISTINCT FROM v_operation.old_dispatch_snapshot
          OR jsonb_array_length(v_snapshot)<>9
        THEN RAISE EXCEPTION 'rollback source dispatch authority drifted'
          USING ERRCODE='40001'; END IF;
        UPDATE public.extension_operation_dispatch_binding d SET
          operation_fence=true,revision=d.revision+1,
          cutover_group_revision=v_operation.target_group_revision,
          updated_by=BTRIM(p_actor),updated_at=v_now
          WHERE d.org_id=v_org AND d.project_id=v_project
            AND d.cutover_group_id=v_operation.cutover_group_id;
        GET DIAGNOSTICS v_rows=ROW_COUNT;
        IF v_rows<>9 THEN RAISE EXCEPTION 'rollback fence group update was not exact'
          USING ERRCODE='40001'; END IF;
        UPDATE public.extension_dispatch_claim_gate SET
          cutover_operation_id=p_cutover_operation_id,revision=revision+1,
          updated_by=BTRIM(p_actor),updated_at=v_now
          WHERE org_id=v_org AND project_id=v_project
            AND cutover_group_id=v_operation.cutover_group_id;
        UPDATE public.extension_dispatch_cutover_operation SET
          status='draining',updated_at=v_now
          WHERE org_id=v_org AND project_id=v_project
            AND cutover_operation_id=p_cutover_operation_id AND status='fencing';
        RETURN v_rows;
      END $$;

    CREATE FUNCTION extension_dispatch_cutover_rollback_ar2_016(
      p_cutover_operation_id uuid,p_actor text) RETURNS bigint
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
      DECLARE v_org text:=NULLIF(current_setting('aos.org_id',true),'');
        v_project text:=NULLIF(current_setting('aos.project_id',true),'');
        v_operation record; v_parent record; v_gate record; v_snapshot jsonb;
        v_rows bigint; v_now timestamptz:=clock_timestamp();
      BEGIN
        IF v_org IS NULL OR v_project IS NULL OR length(BTRIM(p_actor)) NOT BETWEEN 1 AND 240
          OR NOT pg_has_role(session_user,'aos_extension_maintainer','member')
          OR EXISTS(SELECT 1 FROM pg_catalog.pg_roles
            WHERE rolname=session_user AND (rolsuper OR rolbypassrls))
        THEN RAISE EXCEPTION 'dedicated non-privileged cutover maintainer is required'
          USING ERRCODE='42501'; END IF;
        SELECT * INTO v_operation FROM public.extension_dispatch_cutover_operation
          WHERE org_id=v_org AND project_id=v_project
            AND cutover_operation_id=p_cutover_operation_id FOR UPDATE;
        IF NOT FOUND OR v_operation.kind<>'rollback' OR v_operation.status<>'draining'
        THEN RAISE EXCEPTION 'rollback operation is not draining' USING ERRCODE='55000'; END IF;
        SELECT * INTO v_parent FROM public.extension_dispatch_cutover_operation
          WHERE org_id=v_org AND project_id=v_project
            AND cutover_operation_id=v_operation.parent_cutover_operation_id FOR UPDATE;
        IF NOT FOUND OR v_parent.kind<>'activate' OR v_parent.status NOT IN ('committed','validated')
        THEN RAISE EXCEPTION 'activation is outside validation rollback window'
          USING ERRCODE='55000'; END IF;
        SELECT * INTO v_gate FROM public.extension_dispatch_claim_gate
          WHERE org_id=v_org AND project_id=v_project
            AND cutover_group_id=v_operation.cutover_group_id FOR UPDATE;
        IF NOT FOUND OR v_gate.cutover_operation_id<>p_cutover_operation_id OR NOT v_gate.claim_paused
        THEN RAISE EXCEPTION 'rollback claim gate authority drifted' USING ERRCODE='40001'; END IF;
        PERFORM 1 FROM public.extension_operation_dispatch_binding d
          WHERE d.org_id=v_org AND d.project_id=v_project
            AND d.cutover_group_id=v_operation.cutover_group_id
          ORDER BY d.operation_id FOR UPDATE;
        SELECT jsonb_agg(jsonb_build_object(
          'operationId',d.operation_id,'handlerKind',d.handler_kind,
          'installationId',d.installation_id::text,'generation',d.generation::text,
          'executionEpoch',d.execution_epoch,'operationFence',d.operation_fence,
          'revision',d.revision,'cutoverGroupId',d.cutover_group_id::text,
          'cutoverGroupRevision',d.cutover_group_revision) ORDER BY d.operation_id)
          INTO v_snapshot FROM public.extension_operation_dispatch_binding d
          WHERE d.org_id=v_org AND d.project_id=v_project
            AND d.cutover_group_id=v_operation.cutover_group_id;
        IF v_snapshot IS DISTINCT FROM v_operation.new_dispatch_snapshot
          OR jsonb_array_length(v_snapshot)<>9
        THEN RAISE EXCEPTION 'rollback fenced dispatch authority drifted'
          USING ERRCODE='40001'; END IF;
        IF EXISTS(SELECT 1 FROM public.automation_occurrence o
          WHERE o.org_id=v_org AND o.project_id=v_project
            AND o.installation_id=v_parent.target_installation_id
            AND o.generation=v_parent.target_generation
            AND o.execution_epoch=v_parent.target_execution_epoch AND o.status='claimed')
          OR EXISTS(SELECT 1 FROM public.automation_occurrence_dispatch_attempt a
            JOIN public.automation_occurrence o USING(org_id,project_id,occurrence_id)
            WHERE a.org_id=v_org AND a.project_id=v_project
              AND o.installation_id=v_parent.target_installation_id
              AND o.generation=v_parent.target_generation
              AND o.execution_epoch=v_parent.target_execution_epoch AND a.status='claimed')
          OR EXISTS(SELECT 1 FROM public.extension_runtime_execution_attempt a
            WHERE a.org_id=v_org AND a.project_id=v_project
              AND a.installation_id=v_parent.target_installation_id
              AND a.generation=v_parent.target_generation
              AND a.execution_epoch=v_parent.target_execution_epoch AND a.state='running')
        THEN RAISE EXCEPTION 'rollback target execution is not drained' USING ERRCODE='55000'; END IF;
        UPDATE public.extension_operation_dispatch_binding d SET
          handler_kind=item.value->>'handlerKind',
          installation_id=NULLIF(item.value->>'installationId','')::uuid,
          generation=NULLIF(item.value->>'generation','')::uuid,
          execution_epoch=NULLIF(item.value->>'executionEpoch','')::bigint,
          operation_fence=(item.value->>'operationFence')::boolean,
          revision=d.revision+1,
          cutover_group_revision=v_operation.target_group_revision+1,
          updated_by=BTRIM(p_actor),updated_at=v_now
          FROM jsonb_array_elements(v_parent.old_dispatch_snapshot) AS item(value)
          WHERE d.org_id=v_org AND d.project_id=v_project
            AND d.cutover_group_id=v_operation.cutover_group_id
            AND d.operation_id=item.value->>'operationId';
        GET DIAGNOSTICS v_rows=ROW_COUNT;
        IF v_rows<>9 THEN RAISE EXCEPTION 'rollback group update was not exact'
          USING ERRCODE='40001'; END IF;
        DELETE FROM public.extension_dispatch_claim_gate
          WHERE org_id=v_org AND project_id=v_project
            AND cutover_group_id=v_operation.cutover_group_id
            AND cutover_operation_id=p_cutover_operation_id AND claim_paused;
        IF NOT FOUND THEN RAISE EXCEPTION 'rollback claim gate delete drifted'
          USING ERRCODE='40001'; END IF;
        UPDATE public.extension_dispatch_cutover_operation SET
          status='rolled_back',updated_at=v_now
          WHERE org_id=v_org AND project_id=v_project
            AND cutover_operation_id=p_cutover_operation_id AND status='draining';
        RETURN v_rows;
      END $$;
    """)
    for function in (
        "extension_dispatch_cutover_fence_rollback_ar2_016(uuid,text)",
        "extension_dispatch_cutover_rollback_ar2_016(uuid,text)",
    ):
        op.execute(f"REVOKE ALL ON FUNCTION {function} FROM PUBLIC,aos_runtime")
        op.execute(f"GRANT EXECUTE ON FUNCTION {function} TO aos_extension_maintainer")


def downgrade() -> None:
    op.execute("""DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM extension_dispatch_cutover_operation WHERE kind='rollback')
      THEN RAISE EXCEPTION 'cannot downgrade ar2_016 with rollback authority'
        USING ERRCODE='55000'; END IF;
    END $$""")
    op.execute("DROP FUNCTION extension_dispatch_cutover_rollback_ar2_016(uuid,text)")
    op.execute("DROP FUNCTION extension_dispatch_cutover_fence_rollback_ar2_016(uuid,text)")
    op.execute("ALTER TABLE extension_dispatch_cutover_operation DROP CONSTRAINT extension_dispatch_cutover_parent_shape")
    op.execute("ALTER TABLE extension_dispatch_cutover_operation DROP CONSTRAINT extension_dispatch_cutover_parent_fk")
    op.execute("ALTER TABLE extension_dispatch_cutover_operation DROP COLUMN failure_reason")
    op.execute("ALTER TABLE extension_dispatch_cutover_operation DROP COLUMN parent_receipt_ref")
    op.execute("ALTER TABLE extension_dispatch_cutover_operation DROP COLUMN parent_cutover_operation_id")
    op.execute("""CREATE OR REPLACE FUNCTION extension_dispatch_cutover_history_guard_ar2_014()
      RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
      SET search_path=pg_catalog,public,pg_temp AS $$
      DECLARE v_phase text;
      BEGIN
        v_phase:=CASE NEW.status
          WHEN 'draining' THEN 'pause' WHEN 'committed' THEN 'commit'
          WHEN 'validated' THEN 'validate' WHEN 'resumed' THEN 'resume' ELSE NULL END;
        IF v_phase IS NOT NULL AND OLD.status IS DISTINCT FROM NEW.status
          AND NOT EXISTS(SELECT 1 FROM public.extension_dispatch_cutover_receipt r
            WHERE r.org_id=NEW.org_id AND r.project_id=NEW.project_id
              AND r.cutover_operation_id=NEW.cutover_operation_id AND r.phase=v_phase)
        THEN RAISE EXCEPTION '% cutover requires % Receipt',NEW.status,v_phase
          USING ERRCODE='23514'; END IF;
        RETURN NEW;
      END $$""")
