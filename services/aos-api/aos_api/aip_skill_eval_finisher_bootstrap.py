"""Explicit maintenance prototype, never automatic or LOGIN provisioning."""
from psycopg.rows import dict_row

ROLE = 'aos_skill_eval_finisher'
POLICIES = ('skill_finisher_run_read','skill_finisher_run_update',
            'skill_finisher_event_read','skill_finisher_event_insert',
            'skill_finisher_run_scope','skill_finisher_event_scope')


def _require(ok):
    if not ok:
        raise RuntimeError('Skill finisher maintenance precondition differs')


def install_skill_finisher_permissions(conn, *, expected_database, expected_cluster):
    """Prepare an unused NOLOGIN role in the exact caller-owned maintenance DB.

    Formal zero-execution/backup/approval gates belong to the maintenance caller.
    This helper does not commit, assign members, create credentials or admit a
    producer. Existing unknown authority is refused rather than overwritten.
    """
    _require(conn.autocommit is False and conn.row_factory is dict_row
             and isinstance(expected_database,str) and bool(expected_database)
             and isinstance(expected_cluster,str) and bool(expected_cluster))
    context=conn.execute("""SELECT current_user AS role,session_user AS login,
        current_database() AS database,
        current_setting('transaction_isolation') AS isolation""").fetchone()
    _require(context['role']==context['login']=='aos_app'
             and context['database']==expected_database and context['isolation']=='serializable')
    _require(conn.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']==expected_cluster)
    _require(conn.execute('SELECT version_num FROM public.alembic_version').fetchone()['version_num']=='a0v_161')
    relations=conn.execute("""SELECT c.oid,r.rolname,c.relrowsecurity,c.relforcerowsecurity
        FROM pg_class c JOIN pg_roles r ON r.oid=c.relowner
        WHERE c.oid IN ('public.aip_eval_run'::regclass,'public.aip_eval_run_event'::regclass)
        AND c.relkind='r'""").fetchall()
    _require(len(relations)==2 and all(r['rolname']=='aos_app'
        and r['relrowsecurity'] and r['relforcerowsecurity'] for r in relations))
    _require(not conn.execute("""SELECT EXISTS(SELECT 1 FROM pg_attribute
        WHERE attrelid='public.aip_eval_run'::regclass AND attnum>0 AND NOT attisdropped
        AND has_column_privilege('aos_aip_eval_writer',attrelid,attnum,'UPDATE')) AS unsafe""").fetchone()['unsafe'])
    role=conn.execute("""SELECT oid,rolcanlogin,rolinherit,rolsuper,rolbypassrls,
        rolcreaterole,rolcreatedb,rolreplication FROM pg_roles WHERE rolname=%s""",(ROLE,)).fetchone()
    if role:
        _require(not any(role[k] for k in ('rolcanlogin','rolinherit','rolsuper',
            'rolbypassrls','rolcreaterole','rolcreatedb','rolreplication')))
        _require(not conn.execute("""SELECT EXISTS(SELECT 1 FROM pg_auth_members
            WHERE roleid=%s OR member=%s) AS unsafe""",(role['oid'],role['oid'])).fetchone()['unsafe'])
        _require(not conn.execute("""SELECT EXISTS(
            SELECT 1 FROM pg_class c CROSS JOIN LATERAL aclexplode(c.relacl) a WHERE a.grantee=%s
            UNION ALL SELECT 1 FROM pg_attribute at CROSS JOIN LATERAL aclexplode(at.attacl) a WHERE a.grantee=%s
            UNION ALL SELECT 1 FROM pg_class WHERE relowner=%s
            UNION ALL SELECT 1 FROM pg_namespace WHERE nspowner=%s
            UNION ALL SELECT 1 FROM pg_proc WHERE proowner=%s
            UNION ALL SELECT 1 FROM pg_namespace n CROSS JOIN LATERAL aclexplode(n.nspacl) a WHERE a.grantee=%s
            UNION ALL SELECT 1 FROM pg_proc p CROSS JOIN LATERAL aclexplode(p.proacl) a WHERE a.grantee=%s
            UNION ALL SELECT 1 FROM pg_database d CROSS JOIN LATERAL aclexplode(d.datacl) a WHERE a.grantee=%s
            UNION ALL SELECT 1 FROM pg_default_acl d CROSS JOIN LATERAL aclexplode(d.defaclacl) a WHERE a.grantee=%s
            UNION ALL SELECT 1 FROM pg_database WHERE datdba=%s
            UNION ALL SELECT 1 FROM pg_policy WHERE %s=ANY(polroles)) AS unsafe""",
            (role['oid'],)*11).fetchone()['unsafe'])
    _require(not conn.execute('SELECT EXISTS(SELECT 1 FROM pg_policy WHERE polname=ANY(%s)) AS present',
        (list(POLICIES),)).fetchone()['present'])
    with conn.transaction():
        if not role:
            conn.execute('CREATE ROLE aos_skill_eval_finisher NOLOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEROLE NOCREATEDB NOREPLICATION')
        conn.execute('GRANT SELECT,UPDATE(status,version,started_at,finished_at) ON public.aip_eval_run TO aos_skill_eval_finisher')
        conn.execute('GRANT SELECT,INSERT ON public.aip_eval_run_event TO aos_skill_eval_finisher')
        predicate="org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),'')"
        conn.execute('CREATE POLICY skill_finisher_run_read ON public.aip_eval_run FOR SELECT TO aos_skill_eval_finisher USING ('+predicate+')')
        conn.execute('CREATE POLICY skill_finisher_run_update ON public.aip_eval_run FOR UPDATE TO aos_skill_eval_finisher USING ('+predicate+') WITH CHECK ('+predicate+')')
        conn.execute('CREATE POLICY skill_finisher_event_read ON public.aip_eval_run_event FOR SELECT TO aos_skill_eval_finisher USING ('+predicate+')')
        conn.execute('CREATE POLICY skill_finisher_event_insert ON public.aip_eval_run_event FOR INSERT TO aos_skill_eval_finisher WITH CHECK ('+predicate+')')
        conn.execute('CREATE POLICY skill_finisher_run_scope ON public.aip_eval_run AS RESTRICTIVE TO aos_skill_eval_finisher USING ('+predicate+') WITH CHECK ('+predicate+')')
        conn.execute('CREATE POLICY skill_finisher_event_scope ON public.aip_eval_run_event AS RESTRICTIVE TO aos_skill_eval_finisher USING ('+predicate+') WITH CHECK ('+predicate+')')
