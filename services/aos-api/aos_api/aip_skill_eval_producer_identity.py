"""Independent producer identity prerequisite, never execution admission.

The original Eval writer's one-role identity contract remains unchanged. This
separate boundary permits only the two roles needed by a future bounded ending
transaction. It neither creates roles nor grants Run mutation privileges.
"""
import psycopg
from psycopg.rows import dict_row

_ROLES = frozenset({'aos_aip_eval_writer', 'aos_skill_eval_finisher'})
_PRIVILEGES = ('rolsuper', 'rolbypassrls', 'rolcreaterole', 'rolcreatedb', 'rolreplication')
_REJECTION = 'independent Skill producer identity is unavailable'


def require_skill_producer_identity(conn, *, expected_database: str) -> None:
    """Validate authenticated session and role graph; caller owns transaction.

    Owner, budget, approval, signature, tenant and currentness admission must
    still run in the producer. Passing this check is not permission to execute.
    """
    if not isinstance(expected_database, str) or not expected_database.strip():
        raise RuntimeError(_REJECTION)
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            row = cur.execute("""SELECT session_user AS session_name,
                current_user AS current_name,current_database() AS database_name,
                rolcanlogin,rolinherit,rolsuper,rolbypassrls,rolcreaterole,
                rolcreatedb,rolreplication
                FROM pg_catalog.pg_roles WHERE rolname=session_user""").fetchone()
            if (row is None or row['database_name'] != expected_database
                or row['session_name'] != row['current_name']
                or row['session_name'] in _ROLES | {'aos_app', 'aos_runtime'}
                or row['rolcanlogin'] is not True or row['rolinherit'] is not False
                or any(row[key] is not False for key in _PRIVILEGES)):
                raise RuntimeError(_REJECTION)
            reachable = cur.execute("""SELECT rolname,rolcanlogin,rolinherit,
                rolsuper,rolbypassrls,rolcreaterole,rolcreatedb,rolreplication
                FROM pg_catalog.pg_roles WHERE rolname<>session_user
                AND pg_catalog.pg_has_role(session_user,oid,'MEMBER')""").fetchall()
            if (len(reachable) != 2 or {r['rolname'] for r in reachable} != _ROLES
                or any(r[key] is not False for r in reachable
                       for key in ('rolcanlogin', 'rolinherit', *_PRIVILEGES))):
                raise RuntimeError(_REJECTION)
            grants = cur.execute("""SELECT r.rolname,m.admin_option,
                m.inherit_option,m.set_option FROM pg_catalog.pg_auth_members m
                JOIN pg_catalog.pg_roles r ON r.oid=m.roleid
                WHERE m.member=(SELECT oid FROM pg_catalog.pg_roles
                                WHERE rolname=session_user)""").fetchall()
            if (len(grants) != 2 or {g['rolname'] for g in grants} != _ROLES
                or any(g['admin_option'] is not False
                       or g['inherit_option'] is not False
                       or g['set_option'] is not True for g in grants)):
                raise RuntimeError(_REJECTION)
    except psycopg.Error:
        raise RuntimeError(_REJECTION) from None
