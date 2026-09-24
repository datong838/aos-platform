"""Add a restricted in-transaction Host lease guard; no worker is wired yet."""

from alembic import op


revision = "a0v_094"
down_revision = "a0v_093"
branch_labels = depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE FUNCTION public.extension_runtime_host_lease_worker_fence_a0v_094(
      p_org text,p_project text,p_token uuid,p_epoch bigint)
      RETURNS timestamptz LANGUAGE plpgsql SECURITY DEFINER
      SET search_path=pg_catalog,public,pg_temp AS $$
    DECLARE v_role record; v_lease record; v_identity record; v_assignment record;
      v_now timestamptz;
    BEGIN
      IF p_org IS NULL OR p_project IS NULL OR p_token IS NULL OR p_epoch IS NULL
        OR p_epoch<1
        OR p_org IS DISTINCT FROM NULLIF(current_setting('aos.org_id',true),'')
        OR p_project IS DISTINCT FROM NULLIF(current_setting('aos.project_id',true),'')
      THEN RAISE EXCEPTION 'exact worker fence scope and holder required'
        USING ERRCODE='42501'; END IF;
      SELECT oid,rolcanlogin,rolsuper,rolbypassrls INTO v_role
        FROM pg_catalog.pg_roles WHERE rolname=session_user;
      IF NOT FOUND OR NOT v_role.rolcanlogin OR v_role.rolsuper OR v_role.rolbypassrls
        OR NOT pg_has_role(session_user,'aos_runtime','member')
      THEN RAISE EXCEPTION 'eligible non-privileged runtime login required'
        USING ERRCODE='42501'; END IF;
      PERFORM pg_advisory_xact_lock(hashtextextended(
        'a0v-host-lease:'||jsonb_build_array(p_org,p_project)::text,0));
      SELECT * INTO v_lease FROM public.extension_runtime_host_lease_a0v_093
        WHERE org_id=p_org AND project_id=p_project FOR SHARE;
      IF NOT FOUND THEN RAISE EXCEPTION 'Host lease absent'
        USING ERRCODE='55000'; END IF;
      SELECT * INTO v_identity FROM public.extension_runtime_host_identity
        WHERE database_role=v_lease.database_role AND enabled FOR SHARE;
      SELECT * INTO v_assignment FROM public.extension_runtime_host_assignment
        WHERE org_id=p_org AND project_id=p_project AND state='assigned' FOR SHARE;
      v_now:=clock_timestamp();
      IF v_lease.expires_at<=v_now OR v_lease.epoch<>p_epoch
        OR v_lease.token_hash IS DISTINCT FROM
          'sha256:'||encode(sha256(convert_to(p_token::text,'UTF8')),'hex')
        OR v_identity.host_id IS DISTINCT FROM v_lease.host_id
        OR v_identity.database_role_oid IS DISTINCT FROM v_lease.database_role_oid
        OR v_identity.database_role_oid IS DISTINCT FROM
          (SELECT oid FROM pg_catalog.pg_roles WHERE rolname=v_lease.database_role)
        OR v_assignment.host_id IS DISTINCT FROM v_lease.host_id
        OR v_assignment.revision IS DISTINCT FROM v_lease.assignment_revision
      THEN RAISE EXCEPTION 'current Host lease holder differs'
        USING ERRCODE='55000'; END IF;
      RETURN v_lease.expires_at;
    END $$;
    REVOKE ALL ON FUNCTION
      public.extension_runtime_host_lease_worker_fence_a0v_094(text,text,uuid,bigint)
      FROM PUBLIC,aos_extension_directory,aos_extension_maintainer;
    GRANT EXECUTE ON FUNCTION
      public.extension_runtime_host_lease_worker_fence_a0v_094(text,text,uuid,bigint)
      TO aos_runtime;
    """)


def downgrade() -> None:
    op.execute("DROP FUNCTION public.extension_runtime_host_lease_worker_fence_a0v_094(text,text,uuid,bigint)")
