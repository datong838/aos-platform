"""Bind runtime disable to exact ecommerce growth dispatch detachment."""

from alembic import op


revision = "ar2_017"
down_revision = "ar2_016"
branch_labels = depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE extension_dispatch_lifecycle_operation(
      org_id text NOT NULL,project_id text NOT NULL,runtime_operation_id uuid NOT NULL,
      activation_operation_id uuid NOT NULL,cutover_group_id uuid NOT NULL,
      status text NOT NULL CHECK(status IN ('fencing','fenced','detached')),
      request_hash text NOT NULL CHECK(request_hash ~ '^sha256:[0-9a-f]{64}$'),
      operation_ids jsonb NOT NULL CHECK(jsonb_typeof(operation_ids)='array'),
      extension_snapshot jsonb NOT NULL CHECK(jsonb_typeof(extension_snapshot)='array'),
      fenced_snapshot jsonb NOT NULL CHECK(jsonb_typeof(fenced_snapshot)='array'),
      legacy_snapshot jsonb NOT NULL CHECK(jsonb_typeof(legacy_snapshot)='array'),
      fenced_group_revision bigint NOT NULL CHECK(fenced_group_revision>0),
      requested_by text NOT NULL CHECK(length(requested_by) BETWEEN 1 AND 240),
      created_at timestamptz NOT NULL,updated_at timestamptz NOT NULL,
      PRIMARY KEY(org_id,project_id,runtime_operation_id),
      UNIQUE(org_id,project_id,activation_operation_id,runtime_operation_id),
      FOREIGN KEY(org_id,project_id,runtime_operation_id)
        REFERENCES extension_runtime_operation(org_id,project_id,operation_id),
      FOREIGN KEY(org_id,project_id,activation_operation_id)
        REFERENCES extension_dispatch_cutover_operation(org_id,project_id,cutover_operation_id),
      CHECK(jsonb_array_length(operation_ids)=9
        AND jsonb_array_length(extension_snapshot)=9
        AND jsonb_array_length(fenced_snapshot)=9
        AND jsonb_array_length(legacy_snapshot)=9)
    );
    CREATE TABLE extension_dispatch_lifecycle_event(
      org_id text NOT NULL,project_id text NOT NULL,runtime_operation_id uuid NOT NULL,
      sequence bigint NOT NULL CHECK(sequence IN (1,2)),event_type text NOT NULL
        CHECK(event_type IN ('DISPATCH_DISABLE_FENCED','DISPATCH_DISABLED_DETACHED')),
      payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'),
      payload_hash text NOT NULL CHECK(payload_hash ~ '^sha256:[0-9a-f]{64}$'),
      occurred_at timestamptz NOT NULL,
      PRIMARY KEY(org_id,project_id,runtime_operation_id,sequence),
      FOREIGN KEY(org_id,project_id,runtime_operation_id)
        REFERENCES extension_dispatch_lifecycle_operation(org_id,project_id,runtime_operation_id)
    );
    CREATE TABLE extension_dispatch_lifecycle_receipt(
      org_id text NOT NULL,project_id text NOT NULL,receipt_id uuid NOT NULL,
      runtime_operation_id uuid NOT NULL,phase text NOT NULL CHECK(phase IN ('fence','detach')),
      request_hash text NOT NULL CHECK(request_hash ~ '^sha256:[0-9a-f]{64}$'),
      authority_data jsonb NOT NULL CHECK(jsonb_typeof(authority_data)='object'),
      content_hash text NOT NULL CHECK(content_hash ~ '^sha256:[0-9a-f]{64}$'),
      created_at timestamptz NOT NULL,
      PRIMARY KEY(org_id,project_id,receipt_id),
      UNIQUE(org_id,project_id,runtime_operation_id,phase),
      FOREIGN KEY(org_id,project_id,runtime_operation_id)
        REFERENCES extension_dispatch_lifecycle_operation(org_id,project_id,runtime_operation_id)
    );
    """)
    for table in (
        "extension_dispatch_lifecycle_operation",
        "extension_dispatch_lifecycle_event",
        "extension_dispatch_lifecycle_receipt",
    ):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""CREATE POLICY tenant_scope ON {table} TO aos_runtime
              USING(org_id=current_setting('aos.org_id',true)
                AND project_id=current_setting('aos.project_id',true))
              WITH CHECK(org_id=current_setting('aos.org_id',true)
                AND project_id=current_setting('aos.project_id',true))"""
        )
        op.execute(f"REVOKE ALL ON {table} FROM PUBLIC,aos_runtime")
        op.execute(f"GRANT SELECT,INSERT ON {table} TO aos_runtime")
    op.execute(
        "GRANT UPDATE(status,updated_at) ON extension_dispatch_lifecycle_operation TO aos_runtime"
    )
    op.execute(
        """CREATE POLICY lifecycle_runtime_read ON extension_dispatch_cutover_operation
          FOR SELECT TO aos_runtime
          USING(org_id=current_setting('aos.org_id',true)
            AND project_id=current_setting('aos.project_id',true))"""
    )
    op.execute("GRANT SELECT ON extension_dispatch_cutover_operation TO aos_runtime")
    for table in (
        "extension_dispatch_lifecycle_event",
        "extension_dispatch_lifecycle_receipt",
    ):
        op.execute(
            f"""CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE ON {table}
              FOR EACH ROW EXECUTE FUNCTION extension_reject_history_mutation()"""
        )
    op.execute("""
    CREATE FUNCTION extension_dispatch_lifecycle_history_guard_ar2_017() RETURNS trigger
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
      DECLARE v_phase text;
      BEGIN
        v_phase:=CASE NEW.status WHEN 'fenced' THEN 'fence' WHEN 'detached' THEN 'detach' ELSE NULL END;
        IF v_phase IS NOT NULL AND OLD.status IS DISTINCT FROM NEW.status
          AND NOT EXISTS(SELECT 1 FROM public.extension_dispatch_lifecycle_receipt r
            WHERE r.org_id=NEW.org_id AND r.project_id=NEW.project_id
              AND r.runtime_operation_id=NEW.runtime_operation_id AND r.phase=v_phase)
        THEN RAISE EXCEPTION 'dispatch lifecycle % requires % Receipt',NEW.status,v_phase
          USING ERRCODE='23514'; END IF;
        RETURN NEW;
      END $$;
    CREATE CONSTRAINT TRIGGER lifecycle_receipt_guard
      AFTER UPDATE OF status ON extension_dispatch_lifecycle_operation
      DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
      EXECUTE FUNCTION extension_dispatch_lifecycle_history_guard_ar2_017();

    CREATE FUNCTION extension_dispatch_lifecycle_fence_ar2_017(
      p_runtime_operation_id uuid,p_actor text) RETURNS bigint
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
      DECLARE v_org text:=NULLIF(current_setting('aos.org_id',true),'');
        v_project text:=NULLIF(current_setting('aos.project_id',true),'');
        v_lifecycle record; v_activation record; v_runtime record; v_binding record;
        v_gate record; v_snapshot jsonb; v_rows bigint; v_now timestamptz:=clock_timestamp();
      BEGIN
        IF v_org IS NULL OR v_project IS NULL OR length(BTRIM(p_actor)) NOT BETWEEN 1 AND 240
          OR NOT pg_has_role(session_user,'aos_runtime','member')
          OR EXISTS(SELECT 1 FROM pg_catalog.pg_roles
            WHERE rolname=session_user AND (rolsuper OR rolbypassrls))
        THEN RAISE EXCEPTION 'dedicated non-privileged runtime role is required'
          USING ERRCODE='42501'; END IF;
        SELECT * INTO v_lifecycle FROM public.extension_dispatch_lifecycle_operation
          WHERE org_id=v_org AND project_id=v_project
            AND runtime_operation_id=p_runtime_operation_id FOR UPDATE;
        IF NOT FOUND OR v_lifecycle.status<>'fencing'
        THEN RAISE EXCEPTION 'dispatch lifecycle operation is not fencing'
          USING ERRCODE='55000'; END IF;
        SELECT * INTO v_activation FROM public.extension_dispatch_cutover_operation
          WHERE org_id=v_org AND project_id=v_project
            AND cutover_operation_id=v_lifecycle.activation_operation_id FOR UPDATE;
        IF NOT FOUND OR v_activation.kind<>'activate' OR v_activation.status<>'resumed'
        THEN RAISE EXCEPTION 'resumed activation authority is required'
          USING ERRCODE='55000'; END IF;
        SELECT * INTO v_runtime FROM public.extension_runtime_operation
          WHERE org_id=v_org AND project_id=v_project
            AND operation_id=p_runtime_operation_id FOR UPDATE;
        IF NOT FOUND OR v_runtime.kind<>'disable' OR v_runtime.phase<>'fencing'
          OR v_runtime.status<>'running' OR v_runtime.requested_by<>BTRIM(p_actor)
        THEN RAISE EXCEPTION 'current runtime disable fence is required'
          USING ERRCODE='55000'; END IF;
        SELECT * INTO v_binding FROM public.extension_runtime_binding
          WHERE org_id=v_org AND project_id=v_project
            AND installation_id=v_activation.target_installation_id
            AND generation=v_activation.target_generation FOR UPDATE;
        IF NOT FOUND OR v_runtime.installation_id<>v_binding.installation_id
          OR v_runtime.expected_binding_revision+1<>v_binding.revision
          OR v_binding.execution_epoch<>v_activation.target_execution_epoch+1
          OR v_binding.enabled OR NOT v_binding.operation_fence
          OR v_binding.observed_state<>'draining'
        THEN RAISE EXCEPTION 'runtime disable fence authority drifted'
          USING ERRCODE='40001'; END IF;
        SELECT * INTO v_gate FROM public.extension_dispatch_claim_gate
          WHERE org_id=v_org AND project_id=v_project
            AND cutover_group_id=v_lifecycle.cutover_group_id FOR UPDATE;
        IF NOT FOUND OR v_gate.cutover_operation_id<>v_activation.cutover_operation_id
          OR v_gate.claim_paused OR v_gate.revision<>2
        THEN RAISE EXCEPTION 'open activation claim gate authority drifted'
          USING ERRCODE='40001'; END IF;
        PERFORM 1 FROM public.extension_operation_dispatch_binding d
          WHERE d.org_id=v_org AND d.project_id=v_project
            AND d.cutover_group_id=v_lifecycle.cutover_group_id
          ORDER BY d.operation_id FOR UPDATE;
        SELECT jsonb_agg(jsonb_build_object(
          'operationId',d.operation_id,'handlerKind',d.handler_kind,
          'installationId',d.installation_id::text,'generation',d.generation::text,
          'executionEpoch',d.execution_epoch,'operationFence',d.operation_fence,
          'revision',d.revision,'cutoverGroupId',d.cutover_group_id::text,
          'cutoverGroupRevision',d.cutover_group_revision) ORDER BY d.operation_id)
          INTO v_snapshot FROM public.extension_operation_dispatch_binding d
          WHERE d.org_id=v_org AND d.project_id=v_project
            AND d.cutover_group_id=v_lifecycle.cutover_group_id;
        IF v_snapshot IS DISTINCT FROM v_lifecycle.extension_snapshot
          OR jsonb_array_length(v_snapshot)<>9
        THEN RAISE EXCEPTION 'disable source dispatch authority drifted'
          USING ERRCODE='40001'; END IF;
        UPDATE public.extension_operation_dispatch_binding d SET
          operation_fence=true,revision=d.revision+1,
          cutover_group_revision=v_lifecycle.fenced_group_revision,
          updated_by=BTRIM(p_actor),updated_at=v_now
          WHERE d.org_id=v_org AND d.project_id=v_project
            AND d.cutover_group_id=v_lifecycle.cutover_group_id;
        GET DIAGNOSTICS v_rows=ROW_COUNT;
        IF v_rows<>9 THEN RAISE EXCEPTION 'disable fence group update was not exact'
          USING ERRCODE='40001'; END IF;
        UPDATE public.extension_dispatch_claim_gate SET
          claim_paused=true,revision=revision+1,updated_by=BTRIM(p_actor),updated_at=v_now
          WHERE org_id=v_org AND project_id=v_project
            AND cutover_group_id=v_lifecycle.cutover_group_id
            AND cutover_operation_id=v_activation.cutover_operation_id
            AND NOT claim_paused AND revision=2;
        IF NOT FOUND THEN RAISE EXCEPTION 'disable claim gate update drifted'
          USING ERRCODE='40001'; END IF;
        UPDATE public.extension_dispatch_lifecycle_operation SET
          status='fenced',updated_at=v_now
          WHERE org_id=v_org AND project_id=v_project
            AND runtime_operation_id=p_runtime_operation_id AND status='fencing';
        RETURN v_rows;
      END $$;

    CREATE FUNCTION extension_dispatch_lifecycle_detach_ar2_017(
      p_runtime_operation_id uuid,p_actor text) RETURNS bigint
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
      DECLARE v_org text:=NULLIF(current_setting('aos.org_id',true),'');
        v_project text:=NULLIF(current_setting('aos.project_id',true),'');
        v_lifecycle record; v_activation record; v_runtime record; v_binding record;
        v_gate record; v_snapshot jsonb; v_rows bigint; v_now timestamptz:=clock_timestamp();
      BEGIN
        IF v_org IS NULL OR v_project IS NULL OR length(BTRIM(p_actor)) NOT BETWEEN 1 AND 240
          OR NOT pg_has_role(session_user,'aos_runtime','member')
          OR EXISTS(SELECT 1 FROM pg_catalog.pg_roles
            WHERE rolname=session_user AND (rolsuper OR rolbypassrls))
        THEN RAISE EXCEPTION 'dedicated non-privileged runtime role is required'
          USING ERRCODE='42501'; END IF;
        SELECT * INTO v_lifecycle FROM public.extension_dispatch_lifecycle_operation
          WHERE org_id=v_org AND project_id=v_project
            AND runtime_operation_id=p_runtime_operation_id FOR UPDATE;
        IF NOT FOUND OR v_lifecycle.status<>'fenced'
        THEN RAISE EXCEPTION 'dispatch lifecycle operation is not fenced'
          USING ERRCODE='55000'; END IF;
        SELECT * INTO v_activation FROM public.extension_dispatch_cutover_operation
          WHERE org_id=v_org AND project_id=v_project
            AND cutover_operation_id=v_lifecycle.activation_operation_id FOR UPDATE;
        SELECT * INTO v_runtime FROM public.extension_runtime_operation
          WHERE org_id=v_org AND project_id=v_project
            AND operation_id=p_runtime_operation_id FOR UPDATE;
        SELECT * INTO v_binding FROM public.extension_runtime_binding
          WHERE org_id=v_org AND project_id=v_project
            AND installation_id=v_activation.target_installation_id
            AND generation=v_activation.target_generation FOR UPDATE;
        IF v_activation.status<>'resumed' OR v_runtime.kind<>'disable'
          OR v_runtime.phase<>'succeeded' OR v_runtime.status<>'succeeded'
          OR v_runtime.requested_by<>BTRIM(p_actor)
          OR v_binding.revision<>v_runtime.expected_binding_revision+2
          OR v_binding.execution_epoch<>v_activation.target_execution_epoch+1
          OR v_binding.enabled OR NOT v_binding.operation_fence
          OR v_binding.desired_state<>'disabled' OR v_binding.observed_state<>'unknown'
        THEN RAISE EXCEPTION 'completed runtime disable authority drifted'
          USING ERRCODE='40001'; END IF;
        SELECT * INTO v_gate FROM public.extension_dispatch_claim_gate
          WHERE org_id=v_org AND project_id=v_project
            AND cutover_group_id=v_lifecycle.cutover_group_id FOR UPDATE;
        IF NOT FOUND OR v_gate.cutover_operation_id<>v_activation.cutover_operation_id
          OR NOT v_gate.claim_paused OR v_gate.revision<>3
        THEN RAISE EXCEPTION 'paused disable claim gate authority drifted'
          USING ERRCODE='40001'; END IF;
        PERFORM 1 FROM public.extension_operation_dispatch_binding d
          WHERE d.org_id=v_org AND d.project_id=v_project
            AND d.cutover_group_id=v_lifecycle.cutover_group_id
          ORDER BY d.operation_id FOR UPDATE;
        SELECT jsonb_agg(jsonb_build_object(
          'operationId',d.operation_id,'handlerKind',d.handler_kind,
          'installationId',d.installation_id::text,'generation',d.generation::text,
          'executionEpoch',d.execution_epoch,'operationFence',d.operation_fence,
          'revision',d.revision,'cutoverGroupId',d.cutover_group_id::text,
          'cutoverGroupRevision',d.cutover_group_revision) ORDER BY d.operation_id)
          INTO v_snapshot FROM public.extension_operation_dispatch_binding d
          WHERE d.org_id=v_org AND d.project_id=v_project
            AND d.cutover_group_id=v_lifecycle.cutover_group_id;
        IF v_snapshot IS DISTINCT FROM v_lifecycle.fenced_snapshot
          OR jsonb_array_length(v_snapshot)<>9
        THEN RAISE EXCEPTION 'disable fenced dispatch authority drifted'
          USING ERRCODE='40001'; END IF;
        IF EXISTS(SELECT 1 FROM public.automation_occurrence o
          WHERE o.org_id=v_org AND o.project_id=v_project
            AND o.installation_id=v_activation.target_installation_id
            AND o.generation=v_activation.target_generation
            AND o.execution_epoch=v_activation.target_execution_epoch AND o.status='claimed')
          OR EXISTS(SELECT 1 FROM public.automation_occurrence_dispatch_attempt a
            JOIN public.automation_occurrence o USING(org_id,project_id,occurrence_id)
            WHERE a.org_id=v_org AND a.project_id=v_project
              AND o.installation_id=v_activation.target_installation_id
              AND o.generation=v_activation.target_generation
              AND o.execution_epoch=v_activation.target_execution_epoch AND a.status='claimed')
          OR EXISTS(SELECT 1 FROM public.extension_runtime_execution_attempt a
            WHERE a.org_id=v_org AND a.project_id=v_project
              AND a.installation_id=v_activation.target_installation_id
              AND a.generation=v_activation.target_generation AND a.state='running')
        THEN RAISE EXCEPTION 'disable target execution is not drained' USING ERRCODE='55000'; END IF;
        UPDATE public.extension_operation_dispatch_binding d SET
          handler_kind=item.value->>'handlerKind',
          installation_id=NULLIF(item.value->>'installationId','')::uuid,
          generation=NULLIF(item.value->>'generation','')::uuid,
          execution_epoch=NULLIF(item.value->>'executionEpoch','')::bigint,
          operation_fence=(item.value->>'operationFence')::boolean,
          revision=d.revision+1,
          cutover_group_revision=v_lifecycle.fenced_group_revision+1,
          updated_by=BTRIM(p_actor),updated_at=v_now
          FROM jsonb_array_elements(v_lifecycle.legacy_snapshot) AS item(value)
          WHERE d.org_id=v_org AND d.project_id=v_project
            AND d.cutover_group_id=v_lifecycle.cutover_group_id
            AND d.operation_id=item.value->>'operationId';
        GET DIAGNOSTICS v_rows=ROW_COUNT;
        IF v_rows<>9 THEN RAISE EXCEPTION 'disable detach group update was not exact'
          USING ERRCODE='40001'; END IF;
        DELETE FROM public.extension_dispatch_claim_gate
          WHERE org_id=v_org AND project_id=v_project
            AND cutover_group_id=v_lifecycle.cutover_group_id
            AND cutover_operation_id=v_activation.cutover_operation_id
            AND claim_paused AND revision=3;
        IF NOT FOUND THEN RAISE EXCEPTION 'disable claim gate delete drifted'
          USING ERRCODE='40001'; END IF;
        UPDATE public.extension_dispatch_lifecycle_operation SET
          status='detached',updated_at=v_now
          WHERE org_id=v_org AND project_id=v_project
            AND runtime_operation_id=p_runtime_operation_id AND status='fenced';
        RETURN v_rows;
      END $$;
    """)
    for function in (
        "extension_dispatch_lifecycle_fence_ar2_017(uuid,text)",
        "extension_dispatch_lifecycle_detach_ar2_017(uuid,text)",
    ):
        op.execute(f"REVOKE ALL ON FUNCTION {function} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {function} TO aos_runtime")


def downgrade() -> None:
    op.execute("""DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM extension_dispatch_lifecycle_operation)
      THEN RAISE EXCEPTION 'cannot downgrade ar2_017 with dispatch lifecycle authority'
        USING ERRCODE='55000'; END IF;
    END $$""")
    op.execute("REVOKE SELECT ON extension_dispatch_cutover_operation FROM aos_runtime")
    op.execute("DROP POLICY lifecycle_runtime_read ON extension_dispatch_cutover_operation")
    op.execute("DROP FUNCTION extension_dispatch_lifecycle_detach_ar2_017(uuid,text)")
    op.execute("DROP FUNCTION extension_dispatch_lifecycle_fence_ar2_017(uuid,text)")
    op.execute("DROP FUNCTION extension_dispatch_lifecycle_history_guard_ar2_017() CASCADE")
    op.execute("DROP TABLE extension_dispatch_lifecycle_receipt")
    op.execute("DROP TABLE extension_dispatch_lifecycle_event")
    op.execute("DROP TABLE extension_dispatch_lifecycle_operation")
