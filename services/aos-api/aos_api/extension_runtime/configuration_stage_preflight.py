"""Read-only schema and least-privilege gate before Host staging is selected."""
from psycopg.pq import TransactionStatus
from .lifecycle_store import _values

_TABLE = 'public.extension_runtime_configuration_stage_request'
_UPDATE = ('state', 'revision', 'completed_at', 'result_json', 'failure_code')
_SOURCE_TABLES = (
    'public.aip_responsibility_plan_head',
    'public.aip_responsibility_plan_revision',
    'public.aip_production_contract_receipt',
)


def configuration_stage_ready(conn):
    if conn.info.transaction_status != TransactionStatus.IDLE:
        raise RuntimeError('configuration staging preflight requires idle connection')
    with conn.transaction():
        rows = conn.execute('''SELECT c.relrowsecurity,c.relforcerowsecurity,
            pg_has_role(session_user,c.relowner,'MEMBER') AS owns
            FROM pg_class c WHERE c.oid=ANY(ARRAY[to_regclass(%s),to_regclass(%s)])''',
            (_TABLE, 'public.extension_runtime_configuration')).fetchall()
        if len(rows) != 2 or any(_values(row, ('relrowsecurity','relforcerowsecurity','owns')) != (True,True,False) for row in rows):
            return False
        row = conn.execute('''SELECT has_table_privilege('aos_runtime',%s,'SELECT') AS readable,
            has_any_column_privilege('aos_runtime',%s,'INSERT') AS insertable,
            has_table_privilege('aos_runtime',%s,'DELETE') AS deletable,
            has_table_privilege('aos_runtime',%s,'TRUNCATE') AS truncatable,
            has_table_privilege('aos_runtime','public.extension_runtime_configuration','INSERT') AS configuration_insertable''',
            (_TABLE,)*4).fetchone()
        if _values(row, ('readable','insertable','deletable','truncatable','configuration_insertable')) != (True,False,False,False,True):
            return False
        rows = conn.execute('''SELECT attname,has_column_privilege('aos_runtime',%s,attname,'UPDATE') AS allowed
            FROM pg_attribute WHERE attrelid=to_regclass(%s) AND attnum>0 AND NOT attisdropped''',
            (_TABLE,_TABLE)).fetchall()
        if { _values(row, ('attname','allowed'))[0] for row in rows if _values(row, ('attname','allowed'))[1] } != set(_UPDATE):
            return False
        rows = conn.execute('''SELECT t.tgname,t.tgenabled,p.proname,p.prosecdef FROM pg_trigger t
            JOIN pg_proc p ON p.oid=t.tgfoid WHERE t.tgrelid=to_regclass(%s) AND NOT t.tgisinternal''', (_TABLE,)).fetchall()
        actual = {_values(row, ('tgname','tgenabled','proname','prosecdef')) for row in rows}
        if actual != {
            ('configuration_stage_guard','O','extension_runtime_configuration_stage_guard',False),
            ('configuration_stage_no_truncate','O','extension_reject_history_mutation',False),
        }:
            return False
        # A current source row or Receipt cannot be an issuance authority if
        # the ordinary Host role can create or change it in the same tenant.
        sources = conn.execute('''SELECT c.relrowsecurity,c.relforcerowsecurity,
            has_table_privilege('aos_runtime',c.oid,'SELECT') AS readable,
            has_table_privilege('aos_runtime',c.oid,'INSERT') AS insertable,
            has_table_privilege('aos_runtime',c.oid,'UPDATE') AS updatable,
            has_table_privilege('aos_runtime',c.oid,'DELETE') AS deletable,
            has_table_privilege('aos_runtime',c.oid,'TRUNCATE') AS truncatable
            FROM (VALUES (%s::text),(%s::text),(%s::text)) AS source(name)
            LEFT JOIN pg_class c ON c.oid=to_regclass(source.name)''',
            _SOURCE_TABLES).fetchall()
        return len(sources) == len(_SOURCE_TABLES) and all(
            _values(row, ('relrowsecurity','relforcerowsecurity','readable',
                          'insertable','updatable','deletable','truncatable'))
            == (True,True,True,False,False,False,False) for row in sources)
