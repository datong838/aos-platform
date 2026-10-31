"""Explicit maintenance-only Skill writer ACL installation, never admission.

The caller owns the physical database maintenance window and commit. This
function neither connects nor creates roles, identities, approvals or sources.
All original signature, source and producer checks remain mandatory.
"""
from psycopg.rows import dict_row

ROLE='aos_aip_eval_writer'
READ_TABLES=('aip_eval_issuer_root','aip_eval_executor_identity',
    'aip_eval_authority_revocation','aip_eval_execution_receipt','aip_eval_run',
    'aip_eval_report_revision','aip_eval_case_execution_proof',
    'aip_eval_dataset_revision','aip_eval_suite_revision')
WRITE_TABLES=('aip_eval_execution_receipt','aip_eval_report_revision',
    'aip_eval_case_execution_proof')
_FLAGS=('rolcanlogin','rolinherit','rolsuper','rolbypassrls','rolcreaterole',
    'rolcreatedb','rolreplication')
_PREDICATE="org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),'')"

def _require(ok):
    if not ok:raise RuntimeError('Skill writer maintenance precondition differs')

def install_skill_eval_writer_permissions(conn,*,expected_database,
        expected_cluster,expected_schema_head='a0v_163'):
    """Add only scoped reads and append inserts in the exact schema163 DB.

    A returned value is uncommitted metadata, never execution permission.
    Existing wide privileges, changed original objects or policy collisions
    are refused. Caller must reconcile any commit uncertainty without replay.
    """
    _require(conn.autocommit is False and conn.row_factory is dict_row
        and type(expected_database) is str and bool(expected_database.strip())
        and expected_database==expected_database.strip()
        and type(expected_cluster) is str and bool(expected_cluster.strip())
        and expected_cluster==expected_cluster.strip()
        and type(expected_schema_head) is str and expected_schema_head=='a0v_163')
    context=conn.execute("""SELECT current_user AS role,session_user AS login,
        current_database() AS database,
        current_setting('transaction_isolation') AS isolation""").fetchone()
    _require(context is not None and context['role']==context['login']=='aos_app'
        and context['database']==expected_database
        and context['isolation']=='serializable')
    _require(conn.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']==expected_cluster)
    _require(conn.execute('SELECT version_num FROM public.alembic_version').fetchone()['version_num']==expected_schema_head)
    profile=conn.execute("""SELECT oid,rolcanlogin,rolinherit,rolsuper,rolbypassrls,
        rolcreaterole,rolcreatedb,rolreplication FROM pg_roles WHERE rolname=%s""",(ROLE,)).fetchone()
    _require(profile is not None and all(profile[k] is False for k in _FLAGS))
    relations=conn.execute("""SELECT c.relname,pg_get_userbyid(c.relowner) AS owner,
        c.relrowsecurity,c.relforcerowsecurity FROM pg_class c
        JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public' AND c.relkind='r' AND c.relname=ANY(%s)""",(list(READ_TABLES),)).fetchall()
    _require(len(relations)==len(READ_TABLES)
        and {r['relname'] for r in relations}==set(READ_TABLES)
        and all(r['owner']=='aos_app' and r['relrowsecurity'] is True
            and r['relforcerowsecurity'] is True for r in relations))
    unsafe=conn.execute("""SELECT
        has_schema_privilege(%s,'public','CREATE') OR
        EXISTS(SELECT 1 FROM pg_auth_members WHERE member=%s) OR
        EXISTS(SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
          WHERE n.nspname='public' AND c.relname=ANY(%s) AND (
            has_table_privilege(%s,c.oid,'UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
            OR has_any_column_privilege(%s,c.oid,'UPDATE,REFERENCES')
            OR (c.relname<>ALL(%s) AND (
              has_table_privilege(%s,c.oid,'INSERT')
              OR has_any_column_privilege(%s,c.oid,'INSERT'))))) AS unsafe""",
        (ROLE,profile['oid'],list(READ_TABLES),ROLE,ROLE,list(WRITE_TABLES),ROLE,ROLE)).fetchone()
    _require(unsafe is not None and unsafe['unsafe'] is False)
    names=[f'skill_writer_read_{t}' for t in READ_TABLES]
    names.extend(f'skill_writer_scope_{t}' for t in READ_TABLES)
    names.extend(f'skill_writer_insert_{t}' for t in WRITE_TABLES)
    present=conn.execute('SELECT EXISTS(SELECT 1 FROM pg_policy WHERE polname=ANY(%s)) AS present',(names,)).fetchone()
    _require(present is not None and present['present'] is False)
    # All identifiers below are module constants. A savepoint also protects a
    # caller that catches a late SQL failure and later commits its outer work.
    with conn.transaction():
        for table in READ_TABLES:
            conn.execute(f'GRANT SELECT ON public.{table} TO {ROLE}')
            conn.execute(f'CREATE POLICY skill_writer_read_{table} ON public.{table} FOR SELECT TO {ROLE} USING ({_PREDICATE})')
            conn.execute(f'CREATE POLICY skill_writer_scope_{table} ON public.{table} AS RESTRICTIVE FOR ALL TO {ROLE} USING ({_PREDICATE}) WITH CHECK ({_PREDICATE})')
        for table in WRITE_TABLES:
            conn.execute(f'GRANT INSERT ON public.{table} TO {ROLE}')
            conn.execute(f'CREATE POLICY skill_writer_insert_{table} ON public.{table} FOR INSERT TO {ROLE} WITH CHECK ({_PREDICATE})')
    return {'role':ROLE,'read_relations':READ_TABLES,
        'append_relations':WRITE_TABLES,'caller_commit_required':True}
