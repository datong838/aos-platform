"""Trusted runtime-host directory; no default assignments or worker startup."""
from alembic import op

revision = "ar1_003"
down_revision = "ar1_002"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    DO $$ BEGIN
      IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='aos_extension_directory') THEN
        CREATE ROLE aos_extension_directory NOLOGIN NOSUPERUSER NOBYPASSRLS NOINHERIT;
      END IF;
      IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='aos_extension_maintainer') THEN
        CREATE ROLE aos_extension_maintainer NOLOGIN NOSUPERUSER NOBYPASSRLS NOINHERIT;
      END IF;
    END $$;

    CREATE TABLE extension_runtime_host_identity (
      database_role name PRIMARY KEY,
      database_role_oid oid NOT NULL UNIQUE,
      host_id text NOT NULL UNIQUE CHECK(host_id ~ '^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,79}$'),
      enabled boolean NOT NULL,
      revision bigint NOT NULL CHECK(revision > 0),
      updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
    );
    CREATE TABLE extension_runtime_host_identity_revision (
      database_role name NOT NULL,
      revision bigint NOT NULL CHECK(revision > 0),
      database_role_oid oid NOT NULL,
      host_id text NOT NULL CHECK(host_id ~ '^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,79}$'),
      enabled boolean NOT NULL,
      actor text NOT NULL CHECK(length(actor) BETWEEN 1 AND 240),
      request_hash text NOT NULL CHECK(request_hash ~ '^sha256:[0-9a-f]{64}$'),
      occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(database_role, revision)
    );
    CREATE TABLE extension_runtime_host_assignment (
      org_id text NOT NULL,
      project_id text NOT NULL,
      host_id text,
      state text NOT NULL CHECK(state IN ('assigned','revoked')),
      revision bigint NOT NULL CHECK(revision > 0),
      updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(org_id, project_id),
      FOREIGN KEY(org_id,project_id) REFERENCES twa_workspace(org_id,project_id),
      FOREIGN KEY(host_id) REFERENCES extension_runtime_host_identity(host_id),
      CHECK((state='assigned' AND host_id IS NOT NULL) OR (state='revoked' AND host_id IS NULL))
    );
    CREATE TABLE extension_runtime_host_assignment_revision (
      org_id text NOT NULL,
      project_id text NOT NULL,
      revision bigint NOT NULL CHECK(revision > 0),
      host_id text,
      state text NOT NULL CHECK(state IN ('assigned','revoked')),
      actor text NOT NULL CHECK(length(actor) BETWEEN 1 AND 240),
      request_hash text NOT NULL CHECK(request_hash ~ '^sha256:[0-9a-f]{64}$'),
      occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(org_id, project_id, revision),
      CHECK((state='assigned' AND host_id IS NOT NULL) OR (state='revoked' AND host_id IS NULL))
    );
    CREATE TABLE extension_runtime_host_command_receipt (
      target_kind text NOT NULL CHECK(target_kind IN ('identity','assignment')),
      target_key text NOT NULL CHECK(length(target_key) BETWEEN 1 AND 400),
      idempotency_key text NOT NULL CHECK(length(idempotency_key) BETWEEN 1 AND 160),
      request_hash text NOT NULL CHECK(request_hash ~ '^sha256:[0-9a-f]{64}$'),
      resulting_revision bigint NOT NULL CHECK(resulting_revision > 0),
      created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(target_kind, target_key, idempotency_key)
    );

    CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE ON extension_runtime_host_identity_revision
      FOR EACH ROW EXECUTE FUNCTION extension_reject_history_mutation();
    CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE ON extension_runtime_host_assignment_revision
      FOR EACH ROW EXECUTE FUNCTION extension_reject_history_mutation();
    CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE ON extension_runtime_host_command_receipt
      FOR EACH ROW EXECUTE FUNCTION extension_reject_history_mutation();
    CREATE TRIGGER immutable_truncate BEFORE TRUNCATE ON extension_runtime_host_identity_revision
      FOR EACH STATEMENT EXECUTE FUNCTION extension_reject_history_mutation();
    CREATE TRIGGER immutable_truncate BEFORE TRUNCATE ON extension_runtime_host_assignment_revision
      FOR EACH STATEMENT EXECUTE FUNCTION extension_reject_history_mutation();
    CREATE TRIGGER immutable_truncate BEFORE TRUNCATE ON extension_runtime_host_command_receipt
      FOR EACH STATEMENT EXECUTE FUNCTION extension_reject_history_mutation();

    CREATE FUNCTION extension_runtime_read_host_assignments()
    RETURNS TABLE(org_id text, project_id text, assignment_revision bigint)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path = pg_catalog, public
    AS $$
    DECLARE bound_host text;
    BEGIN
      IF current_setting('transaction_read_only') <> 'on' THEN
        RAISE EXCEPTION 'runtime directory requires a read-only transaction';
      END IF;
      IF NOT pg_has_role(session_user, 'aos_extension_directory', 'member') THEN
        RAISE EXCEPTION 'runtime directory role required';
      END IF;
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=session_user AND (rolsuper OR rolbypassrls)) THEN
        RAISE EXCEPTION 'privileged runtime directory sessions are forbidden';
      END IF;
      SELECT identity.host_id INTO STRICT bound_host
        FROM public.extension_runtime_host_identity AS identity
       WHERE identity.database_role=session_user
         AND identity.database_role_oid=session_user::regrole::oid
         AND identity.enabled=true;
      RETURN QUERY
      SELECT assignment.org_id, assignment.project_id, assignment.revision
        FROM public.extension_runtime_host_assignment AS assignment
       WHERE assignment.state='assigned' AND assignment.host_id=bound_host
       ORDER BY assignment.org_id, assignment.project_id
       LIMIT 1001;
    END $$;

    CREATE FUNCTION extension_runtime_bind_host_identity(
      p_database_role name, p_host_id text, p_enabled boolean,
      p_expected_revision bigint, p_actor text, p_idempotency_key text,
      p_request_hash text
    ) RETURNS bigint
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path = pg_catalog, public
    AS $$
    DECLARE old_revision bigint; old_role_oid oid; old_host_id text;
            replay record; next_revision bigint; current_role_oid oid;
    BEGIN
      IF p_expected_revision IS NULL OR p_expected_revision < 0
         OR length(p_actor) NOT BETWEEN 1 AND 240
         OR length(p_idempotency_key) NOT BETWEEN 1 AND 160
         OR p_request_hash !~ '^sha256:[0-9a-f]{64}$'
         OR p_host_id !~ '^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,79}$' THEN
        RAISE EXCEPTION 'invalid runtime host identity command';
      END IF;
      PERFORM pg_advisory_xact_lock(hashtextextended('runtime-host-identity:'||p_database_role::text, 0));
      SELECT request_hash,resulting_revision INTO replay
        FROM public.extension_runtime_host_command_receipt
       WHERE target_kind='identity' AND target_key=p_database_role::text
         AND idempotency_key=p_idempotency_key;
      IF FOUND THEN
        IF replay.request_hash<>p_request_hash THEN RAISE EXCEPTION 'runtime host identity idempotency conflict'; END IF;
        RETURN replay.resulting_revision;
      END IF;
      SELECT revision,database_role_oid,host_id INTO old_revision,old_role_oid,old_host_id
        FROM public.extension_runtime_host_identity
       WHERE database_role=p_database_role FOR UPDATE;
      old_revision:=coalesce(old_revision,0);
      IF old_revision<>p_expected_revision THEN RAISE EXCEPTION 'runtime host identity revision conflict'; END IF;
      IF p_enabled THEN
        SELECT oid INTO current_role_oid FROM pg_roles WHERE rolname=p_database_role::text
                       AND rolcanlogin AND NOT rolsuper AND NOT rolbypassrls;
        IF current_role_oid IS NULL
           OR NOT pg_has_role(p_database_role, 'aos_extension_directory', 'member') THEN
          RAISE EXCEPTION 'runtime host database role is not eligible';
        END IF;
      ELSE
        IF old_revision=0 OR p_host_id<>old_host_id THEN
          RAISE EXCEPTION 'runtime host identity unavailable for disable';
        END IF;
        current_role_oid:=old_role_oid;
      END IF;
      next_revision:=old_revision+1;
      INSERT INTO public.extension_runtime_host_identity(database_role,database_role_oid,host_id,enabled,revision)
      VALUES(p_database_role,current_role_oid,p_host_id,p_enabled,next_revision)
      ON CONFLICT(database_role) DO UPDATE SET database_role_oid=excluded.database_role_oid,
        host_id=excluded.host_id,enabled=excluded.enabled,
        revision=excluded.revision,updated_at=clock_timestamp();
      INSERT INTO public.extension_runtime_host_identity_revision
        (database_role,revision,database_role_oid,host_id,enabled,actor,request_hash)
      VALUES(p_database_role,next_revision,current_role_oid,p_host_id,p_enabled,p_actor,p_request_hash);
      INSERT INTO public.extension_runtime_host_command_receipt
        (target_kind,target_key,idempotency_key,request_hash,resulting_revision)
      VALUES('identity',p_database_role::text,p_idempotency_key,p_request_hash,next_revision);
      RETURN next_revision;
    END $$;

    CREATE FUNCTION extension_runtime_set_host_assignment(
      p_org_id text, p_project_id text, p_host_id text, p_state text,
      p_expected_revision bigint, p_actor text, p_idempotency_key text,
      p_request_hash text
    ) RETURNS bigint
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path = pg_catalog, public
    AS $$
    DECLARE old_revision bigint; replay record; next_revision bigint; stored_host text; scope_key text;
    BEGIN
      IF p_expected_revision IS NULL OR p_expected_revision < 0
         OR p_state NOT IN ('assigned','revoked')
         OR (p_state='assigned' AND p_host_id IS NULL)
         OR (p_state='revoked' AND p_host_id IS NOT NULL)
         OR length(p_actor) NOT BETWEEN 1 AND 240
         OR length(p_idempotency_key) NOT BETWEEN 1 AND 160
         OR p_request_hash !~ '^sha256:[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'invalid runtime host assignment command';
      END IF;
      scope_key:=jsonb_build_array(p_org_id,p_project_id)::text;
      PERFORM pg_advisory_xact_lock(hashtextextended('runtime-host-assignment:'||scope_key, 0));
      SELECT request_hash,resulting_revision INTO replay
        FROM public.extension_runtime_host_command_receipt
       WHERE target_kind='assignment' AND target_key=scope_key
         AND idempotency_key=p_idempotency_key;
      IF FOUND THEN
        IF replay.request_hash<>p_request_hash THEN RAISE EXCEPTION 'runtime host assignment idempotency conflict'; END IF;
        RETURN replay.resulting_revision;
      END IF;
      SELECT revision INTO old_revision FROM public.extension_runtime_host_assignment
       WHERE org_id=p_org_id AND project_id=p_project_id FOR UPDATE;
      old_revision:=coalesce(old_revision,0);
      IF old_revision<>p_expected_revision THEN RAISE EXCEPTION 'runtime host assignment revision conflict'; END IF;
      IF p_state='assigned' THEN
        SELECT identity.host_id INTO stored_host
          FROM public.extension_runtime_host_identity identity
          JOIN pg_roles role ON role.rolname=identity.database_role::text
                            AND role.oid=identity.database_role_oid
                            AND role.rolcanlogin AND NOT role.rolsuper AND NOT role.rolbypassrls
         WHERE identity.host_id=p_host_id AND identity.enabled=true
           AND pg_has_role(role.rolname,'aos_extension_directory','member')
         FOR SHARE OF identity;
        IF stored_host IS NULL THEN RAISE EXCEPTION 'runtime host identity unavailable'; END IF;
      END IF;
      next_revision:=old_revision+1;
      INSERT INTO public.extension_runtime_host_assignment(org_id,project_id,host_id,state,revision)
      VALUES(p_org_id,p_project_id,p_host_id,p_state,next_revision)
      ON CONFLICT(org_id,project_id) DO UPDATE SET host_id=excluded.host_id,state=excluded.state,
        revision=excluded.revision,updated_at=clock_timestamp();
      INSERT INTO public.extension_runtime_host_assignment_revision
        (org_id,project_id,revision,host_id,state,actor,request_hash)
      VALUES(p_org_id,p_project_id,next_revision,p_host_id,p_state,p_actor,p_request_hash);
      INSERT INTO public.extension_runtime_host_command_receipt
        (target_kind,target_key,idempotency_key,request_hash,resulting_revision)
      VALUES('assignment',scope_key,p_idempotency_key,p_request_hash,next_revision);
      RETURN next_revision;
    END $$;

    REVOKE ALL ON extension_runtime_host_identity,
      extension_runtime_host_identity_revision,
      extension_runtime_host_assignment,
      extension_runtime_host_assignment_revision,
      extension_runtime_host_command_receipt FROM PUBLIC, aos_runtime, aos_extension_directory;
    REVOKE ALL ON FUNCTION extension_runtime_read_host_assignments() FROM PUBLIC, aos_runtime, aos_extension_maintainer;
    REVOKE ALL ON FUNCTION extension_runtime_bind_host_identity(name,text,boolean,bigint,text,text,text) FROM PUBLIC, aos_runtime, aos_extension_directory;
    REVOKE ALL ON FUNCTION extension_runtime_set_host_assignment(text,text,text,text,bigint,text,text,text) FROM PUBLIC, aos_runtime, aos_extension_directory;
    GRANT EXECUTE ON FUNCTION extension_runtime_read_host_assignments() TO aos_extension_directory;
    GRANT EXECUTE ON FUNCTION extension_runtime_bind_host_identity(name,text,boolean,bigint,text,text,text) TO aos_extension_maintainer;
    GRANT EXECUTE ON FUNCTION extension_runtime_set_host_assignment(text,text,text,text,bigint,text,text,text) TO aos_extension_maintainer;
    """)


def downgrade():
    op.execute("""
    DROP FUNCTION extension_runtime_read_host_assignments();
    DROP FUNCTION extension_runtime_bind_host_identity(name,text,boolean,bigint,text,text,text);
    DROP FUNCTION extension_runtime_set_host_assignment(text,text,text,text,bigint,text,text,text);
    DROP TABLE extension_runtime_host_command_receipt;
    DROP TABLE extension_runtime_host_assignment_revision;
    DROP TABLE extension_runtime_host_assignment;
    DROP TABLE extension_runtime_host_identity_revision;
    DROP TABLE extension_runtime_host_identity;
    """)
