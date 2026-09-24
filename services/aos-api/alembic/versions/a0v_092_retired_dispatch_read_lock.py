"""Lock exact retired-dispatch evidence without broad runtime table UPDATE grants."""

from alembic import op


revision = "a0v_092"
down_revision = "a0v_091"
branch_labels = depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE FUNCTION public.extension_dispatch_retired_read_lock_a0v_092(
      p_runtime_operation_id uuid,p_activation_operation_id uuid) RETURNS void
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
    DECLARE v_org text:=NULLIF(current_setting('aos.org_id',true),'');
      v_project text:=NULLIF(current_setting('aos.project_id',true),'');
      v_runtime record; v_activation record; v_rows bigint;
    BEGIN
      IF v_org IS NULL OR v_project IS NULL
        OR NOT pg_has_role(session_user,'aos_runtime','member')
        OR EXISTS(SELECT 1 FROM pg_catalog.pg_roles
          WHERE rolname=session_user AND (rolsuper OR rolbypassrls))
      THEN RAISE EXCEPTION 'dedicated non-privileged runtime role is required'
        USING ERRCODE='42501'; END IF;
      SELECT * INTO v_runtime FROM public.extension_runtime_operation
        WHERE org_id=v_org AND project_id=v_project
          AND operation_id=p_runtime_operation_id FOR UPDATE;
      IF NOT FOUND OR v_runtime.kind<>'disable' OR v_runtime.status<>'running'
        OR v_runtime.phase<>'fencing'
      THEN RAISE EXCEPTION 'exact running disable fence is required'
        USING ERRCODE='55000'; END IF;
      SELECT * INTO v_activation FROM public.extension_dispatch_cutover_operation
        WHERE org_id=v_org AND project_id=v_project
          AND cutover_operation_id=p_activation_operation_id FOR UPDATE;
      IF NOT FOUND OR v_activation.kind<>'activate' OR v_activation.status<>'resumed'
        OR v_activation.target_installation_id<>v_runtime.installation_id
      THEN RAISE EXCEPTION 'exact resumed activation is required'
        USING ERRCODE='55000'; END IF;
      PERFORM 1 FROM public.extension_runtime_binding b
        WHERE b.org_id=v_org AND b.project_id=v_project
          AND b.installation_id=v_runtime.installation_id
          AND b.generation=v_activation.target_generation
          AND b.revision=v_runtime.expected_binding_revision+1
          AND NOT b.enabled AND b.operation_fence AND b.observed_state='draining'
        FOR UPDATE;
      IF NOT FOUND THEN RAISE EXCEPTION 'exact disable binding fence is required'
        USING ERRCODE='55000'; END IF;
      PERFORM 1 FROM public.extension_operation_dispatch_binding d
        WHERE d.org_id=v_org AND d.project_id=v_project
          AND d.cutover_group_id=v_activation.cutover_group_id
        ORDER BY d.operation_id FOR UPDATE;
      GET DIAGNOSTICS v_rows=ROW_COUNT;
      IF v_rows<>9 THEN RAISE EXCEPTION 'exact dispatch group is required'
        USING ERRCODE='55000'; END IF;
    END $$;
    REVOKE ALL ON FUNCTION public.extension_dispatch_retired_read_lock_a0v_092(uuid,uuid)
      FROM PUBLIC,aos_extension_maintainer;
    GRANT EXECUTE ON FUNCTION public.extension_dispatch_retired_read_lock_a0v_092(uuid,uuid)
      TO aos_runtime;
    """)


def downgrade() -> None:
    op.execute("DROP FUNCTION public.extension_dispatch_retired_read_lock_a0v_092(uuid,uuid)")
