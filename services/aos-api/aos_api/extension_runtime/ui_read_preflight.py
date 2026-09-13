"""Read-only schema/role checks before adding the UI consumer to a real host."""
from psycopg.pq import TransactionStatus
from .lifecycle_store import _values
from .ui_read_consumer import UI_READ_PROTECTED_RELATIONS

_COLUMNS=('state','revision','claimed_at','completed_at','owner_token_hash','attempt_id','snapshot_hash',
          'attempt_request_hash','result_json','result_hash','failure_code')


def runtime_ui_read_ready(conn):
    if conn.info.transaction_status!=TransactionStatus.IDLE:
        raise RuntimeError('UI read preflight requires idle connection')
    with conn.transaction():
        rows=conn.execute('''SELECT c.relrowsecurity,c.relforcerowsecurity,
            pg_has_role(session_user,c.relowner,'MEMBER') AS owns
            FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='public' AND c.relname=ANY(%s)''',(list(UI_READ_PROTECTED_RELATIONS),)).fetchall()
        if len(rows)!=len(UI_READ_PROTECTED_RELATIONS) or any(_values(row,('relrowsecurity','relforcerowsecurity','owns'))!=(True,True,False) for row in rows):return False
        function=conn.execute("""SELECT p.oid,p.prosecdef FROM pg_proc p
            WHERE p.oid=to_regprocedure('public.extension_ui_read_host_principal_a0v_033(text,text[])')""").fetchone()
        if function is None:return False
        oid,definer=_values(function,('oid','prosecdef'))
        if definer is not True:return False
        row=conn.execute('''SELECT has_function_privilege('aos_runtime',%s,'EXECUTE') AS worker,
            has_function_privilege('aos_ui_read_api',%s,'EXECUTE') AS api,
            has_table_privilege('aos_runtime','public.extension_runtime_ui_read_request','SELECT') AS readable,
            has_any_column_privilege('aos_runtime','public.extension_runtime_ui_read_request','INSERT') AS insertable,
            has_table_privilege('aos_runtime','public.extension_runtime_ui_read_request','DELETE') AS deletable''',(oid,oid)).fetchone()
        if _values(row,('worker','api','readable','insertable','deletable'))!=(True,False,True,False,False):return False
        row=conn.execute('''SELECT bool_and(has_column_privilege('aos_runtime',
            'public.extension_runtime_ui_read_request',name,'UPDATE')) AS allowed FROM unnest(%s::text[]) name''',(list(_COLUMNS),)).fetchone()
        if _values(row,('allowed',))[0] is not True:return False
        row=conn.execute('''SELECT bool_or(has_column_privilege('aos_runtime',
            'public.extension_runtime_ui_read_request',name,'UPDATE')) AS allowed
            FROM unnest(ARRAY['subject','target_json','deadline','idempotency_key','request_hash']) name''').fetchone()
        return _values(row,('allowed',))[0] is False
