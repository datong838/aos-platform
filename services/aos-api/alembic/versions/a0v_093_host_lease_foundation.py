"""Add an empty, opt-in, database-clock Host lease foundation; no worker wiring."""

from alembic import op


revision = "a0v_093"
down_revision = "a0v_092"
branch_labels = depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE public.extension_runtime_host_lease_a0v_093 (
      org_id text NOT NULL, project_id text NOT NULL,
      host_id text NOT NULL, database_role name NOT NULL, database_role_oid oid NOT NULL,
      assignment_revision bigint NOT NULL CHECK(assignment_revision>0),
      token_hash text NOT NULL CHECK(token_hash ~ '^sha256:[0-9a-f]{64}$'),
      epoch bigint NOT NULL CHECK(epoch>0), expires_at timestamptz NOT NULL,
      updated_at timestamptz NOT NULL,
      PRIMARY KEY(org_id,project_id),
      FOREIGN KEY(org_id,project_id) REFERENCES public.twa_workspace(org_id,project_id)
    );
    CREATE TABLE public.extension_runtime_host_lease_event_a0v_093 (
      event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
      org_id text NOT NULL, project_id text NOT NULL,
      host_id text NOT NULL, database_role name NOT NULL,
      epoch bigint NOT NULL CHECK(epoch>0),
      event_kind text NOT NULL CHECK(event_kind IN ('acquire','renew','release')),
      occurred_at timestamptz NOT NULL,
      expires_at timestamptz NOT NULL
    );
    CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE ON
      public.extension_runtime_host_lease_event_a0v_093
      FOR EACH ROW EXECUTE FUNCTION public.extension_reject_history_mutation();
    CREATE TRIGGER immutable_truncate BEFORE TRUNCATE ON
      public.extension_runtime_host_lease_event_a0v_093
      FOR EACH STATEMENT EXECUTE FUNCTION public.extension_reject_history_mutation();

    CREATE FUNCTION public.extension_runtime_host_lease_guard_a0v_093(
      p_org text,p_project text) RETURNS TABLE(host_id text,database_role_oid oid,
      assignment_revision bigint)
      LANGUAGE plpgsql SECURITY DEFINER
      SET search_path=pg_catalog,public,pg_temp AS $$
    DECLARE v_role record; v_identity record; v_assignment record;
    BEGIN
      IF p_org IS NULL OR p_project IS NULL
        OR p_org IS DISTINCT FROM NULLIF(current_setting('aos.org_id',true),'')
        OR p_project IS DISTINCT FROM NULLIF(current_setting('aos.project_id',true),'')
      THEN RAISE EXCEPTION 'exact Host lease tenant scope required' USING ERRCODE='42501'; END IF;
      SELECT oid,rolcanlogin,rolsuper,rolbypassrls INTO v_role
        FROM pg_catalog.pg_roles WHERE rolname=session_user;
      IF NOT FOUND OR NOT v_role.rolcanlogin OR v_role.rolsuper OR v_role.rolbypassrls
        OR NOT pg_has_role(session_user,'aos_extension_directory','member')
      THEN RAISE EXCEPTION 'eligible non-privileged directory login required'
        USING ERRCODE='42501'; END IF;
      SELECT * INTO v_identity FROM public.extension_runtime_host_identity
        WHERE database_role=session_user::name AND enabled FOR SHARE;
      SELECT * INTO v_assignment FROM public.extension_runtime_host_assignment
        WHERE org_id=p_org AND project_id=p_project AND state='assigned' FOR SHARE;
      IF v_identity.database_role_oid IS DISTINCT FROM v_role.oid
        OR v_assignment.host_id IS DISTINCT FROM v_identity.host_id
        OR v_assignment.revision IS NULL
      THEN RAISE EXCEPTION 'current Host directory authority differs'
        USING ERRCODE='55000'; END IF;
      RETURN QUERY SELECT v_identity.host_id,v_role.oid,v_assignment.revision;
    END $$;

    CREATE FUNCTION public.extension_runtime_host_lease_acquire_a0v_093(
      p_org text,p_project text,p_token uuid,p_ttl_seconds integer)
      RETURNS TABLE(epoch bigint,expires_at timestamptz)
      LANGUAGE plpgsql SECURITY DEFINER
      SET search_path=pg_catalog,public,pg_temp AS $$
    DECLARE v_guard record; v_old record; v_now timestamptz; v_epoch bigint;
      v_expiry timestamptz; v_hash text;
    BEGIN
      IF p_token IS NULL OR p_ttl_seconds NOT BETWEEN 5 AND 30
      THEN RAISE EXCEPTION 'bounded Host lease token and TTL required' USING ERRCODE='22023'; END IF;
      PERFORM pg_advisory_xact_lock(hashtextextended(
        'a0v-host-lease:'||jsonb_build_array(p_org,p_project)::text,0));
      SELECT * INTO v_guard FROM public.extension_runtime_host_lease_guard_a0v_093(p_org,p_project);
      SELECT * INTO v_old FROM public.extension_runtime_host_lease_a0v_093
        WHERE org_id=p_org AND project_id=p_project FOR UPDATE;
      v_now:=clock_timestamp();
      IF FOUND AND v_old.expires_at>v_now
      THEN RAISE EXCEPTION 'active Host lease already held' USING ERRCODE='55P03'; END IF;
      v_epoch:=coalesce(v_old.epoch,0)+1;
      v_expiry:=v_now+make_interval(secs=>p_ttl_seconds);
      v_hash:='sha256:'||encode(sha256(convert_to(p_token::text,'UTF8')),'hex');
      INSERT INTO public.extension_runtime_host_lease_a0v_093
        (org_id,project_id,host_id,database_role,database_role_oid,
         assignment_revision,token_hash,epoch,expires_at,updated_at)
      VALUES(p_org,p_project,v_guard.host_id,session_user::name,v_guard.database_role_oid,
             v_guard.assignment_revision,v_hash,v_epoch,v_expiry,v_now)
      ON CONFLICT(org_id,project_id) DO UPDATE SET
        host_id=excluded.host_id,database_role=excluded.database_role,
        database_role_oid=excluded.database_role_oid,
        assignment_revision=excluded.assignment_revision,
        token_hash=excluded.token_hash,epoch=excluded.epoch,
        expires_at=excluded.expires_at,updated_at=excluded.updated_at;
      INSERT INTO public.extension_runtime_host_lease_event_a0v_093
        (org_id,project_id,host_id,database_role,epoch,event_kind,occurred_at,expires_at)
      VALUES(p_org,p_project,v_guard.host_id,session_user::name,v_epoch,'acquire',v_now,v_expiry);
      RETURN QUERY SELECT v_epoch,v_expiry;
    END $$;

    CREATE FUNCTION public.extension_runtime_host_lease_renew_a0v_093(
      p_org text,p_project text,p_token uuid,p_epoch bigint,p_ttl_seconds integer)
      RETURNS timestamptz LANGUAGE plpgsql SECURITY DEFINER
      SET search_path=pg_catalog,public,pg_temp AS $$
    DECLARE v_guard record; v_old record; v_now timestamptz; v_expiry timestamptz;
    BEGIN
      IF p_token IS NULL OR p_epoch IS NULL OR p_ttl_seconds NOT BETWEEN 5 AND 30
      THEN RAISE EXCEPTION 'bounded Host lease renewal required' USING ERRCODE='22023'; END IF;
      PERFORM pg_advisory_xact_lock(hashtextextended(
        'a0v-host-lease:'||jsonb_build_array(p_org,p_project)::text,0));
      SELECT * INTO v_guard FROM public.extension_runtime_host_lease_guard_a0v_093(p_org,p_project);
      SELECT * INTO v_old FROM public.extension_runtime_host_lease_a0v_093
        WHERE org_id=p_org AND project_id=p_project FOR UPDATE;
      v_now:=clock_timestamp();
      IF NOT FOUND OR v_old.expires_at<=v_now OR v_old.epoch<>p_epoch
        OR v_old.token_hash IS DISTINCT FROM
          'sha256:'||encode(sha256(convert_to(p_token::text,'UTF8')),'hex')
        OR v_old.database_role IS DISTINCT FROM session_user::name
        OR v_old.database_role_oid IS DISTINCT FROM v_guard.database_role_oid
        OR v_old.host_id IS DISTINCT FROM v_guard.host_id
        OR v_old.assignment_revision IS DISTINCT FROM v_guard.assignment_revision
      THEN RAISE EXCEPTION 'current Host lease holder differs' USING ERRCODE='55000'; END IF;
      v_expiry:=v_now+make_interval(secs=>p_ttl_seconds);
      UPDATE public.extension_runtime_host_lease_a0v_093 SET expires_at=v_expiry,
        updated_at=v_now WHERE org_id=p_org AND project_id=p_project;
      INSERT INTO public.extension_runtime_host_lease_event_a0v_093
        (org_id,project_id,host_id,database_role,epoch,event_kind,occurred_at,expires_at)
      VALUES(p_org,p_project,v_guard.host_id,session_user::name,p_epoch,'renew',v_now,v_expiry);
      RETURN v_expiry;
    END $$;

    CREATE FUNCTION public.extension_runtime_host_lease_release_a0v_093(
      p_org text,p_project text,p_token uuid,p_epoch bigint)
      RETURNS void LANGUAGE plpgsql SECURITY DEFINER
      SET search_path=pg_catalog,public,pg_temp AS $$
    DECLARE v_guard record; v_old record; v_now timestamptz;
    BEGIN
      IF p_token IS NULL OR p_epoch IS NULL
      THEN RAISE EXCEPTION 'exact Host lease release required' USING ERRCODE='22023'; END IF;
      PERFORM pg_advisory_xact_lock(hashtextextended(
        'a0v-host-lease:'||jsonb_build_array(p_org,p_project)::text,0));
      SELECT * INTO v_guard FROM public.extension_runtime_host_lease_guard_a0v_093(p_org,p_project);
      SELECT * INTO v_old FROM public.extension_runtime_host_lease_a0v_093
        WHERE org_id=p_org AND project_id=p_project FOR UPDATE;
      v_now:=clock_timestamp();
      IF NOT FOUND OR v_old.expires_at<=v_now OR v_old.epoch<>p_epoch
        OR v_old.token_hash IS DISTINCT FROM
          'sha256:'||encode(sha256(convert_to(p_token::text,'UTF8')),'hex')
        OR v_old.database_role IS DISTINCT FROM session_user::name
        OR v_old.database_role_oid IS DISTINCT FROM v_guard.database_role_oid
        OR v_old.host_id IS DISTINCT FROM v_guard.host_id
        OR v_old.assignment_revision IS DISTINCT FROM v_guard.assignment_revision
      THEN RAISE EXCEPTION 'current Host lease holder differs' USING ERRCODE='55000'; END IF;
      UPDATE public.extension_runtime_host_lease_a0v_093 SET expires_at=v_now,
        updated_at=v_now WHERE org_id=p_org AND project_id=p_project;
      INSERT INTO public.extension_runtime_host_lease_event_a0v_093
        (org_id,project_id,host_id,database_role,epoch,event_kind,occurred_at,expires_at)
      VALUES(p_org,p_project,v_guard.host_id,session_user::name,p_epoch,'release',v_now,v_now);
    END $$;

    REVOKE ALL ON public.extension_runtime_host_lease_a0v_093,
      public.extension_runtime_host_lease_event_a0v_093
      FROM PUBLIC,aos_runtime,aos_extension_directory,aos_extension_maintainer;
    REVOKE ALL ON FUNCTION public.extension_runtime_host_lease_guard_a0v_093(text,text),
      public.extension_runtime_host_lease_acquire_a0v_093(text,text,uuid,integer),
      public.extension_runtime_host_lease_renew_a0v_093(text,text,uuid,bigint,integer),
      public.extension_runtime_host_lease_release_a0v_093(text,text,uuid,bigint)
      FROM PUBLIC,aos_runtime,aos_extension_maintainer;
    GRANT EXECUTE ON FUNCTION public.extension_runtime_host_lease_guard_a0v_093(text,text),
      public.extension_runtime_host_lease_acquire_a0v_093(text,text,uuid,integer),
      public.extension_runtime_host_lease_renew_a0v_093(text,text,uuid,bigint,integer),
      public.extension_runtime_host_lease_release_a0v_093(text,text,uuid,bigint)
      TO aos_extension_directory;
    """)


def downgrade() -> None:
    op.execute("""
    DROP FUNCTION public.extension_runtime_host_lease_release_a0v_093(text,text,uuid,bigint);
    DROP FUNCTION public.extension_runtime_host_lease_renew_a0v_093(text,text,uuid,bigint,integer);
    DROP FUNCTION public.extension_runtime_host_lease_acquire_a0v_093(text,text,uuid,integer);
    DROP FUNCTION public.extension_runtime_host_lease_guard_a0v_093(text,text);
    DROP TABLE public.extension_runtime_host_lease_event_a0v_093;
    DROP TABLE public.extension_runtime_host_lease_a0v_093;
    """)
