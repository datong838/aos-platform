"""Actual S/O/A behavior on the admitted full-schema native lab; no setup."""
import pytest
from psycopg import sql

from asset_registry.test_terminal_source_readlock_pg import (
    _isolated_postgres_database, terminal_native_lab, NativeSQLFailure,
    ROW_COLUMNS, ROW_MUTABLE, insert_row, update_row, delete_row, execute, require,
)

TABLES = ('automation_schedule_binding','automation_occurrence','automation_occurrence_dispatch_attempt')
IDENTITY_FIELDS = tuple((table,column) for table in TABLES for column in ROW_COLUMNS[table]
                        if column not in ROW_MUTABLE[table])
PARENT_MISMATCHES = (
    ('automation_schedule_binding','operation_id'),
    ('automation_schedule_binding','installation_id'),
    ('automation_schedule_binding','generation'),
    ('automation_schedule_binding','execution_epoch'),
    ('automation_occurrence','policy_hash'),
    ('automation_occurrence','operation_id'),
    ('automation_occurrence','installation_id'),
    ('automation_occurrence','generation'),
    ('automation_occurrence','execution_epoch'),
    ('automation_occurrence_dispatch_attempt','occurrence_id'),
    ('automation_occurrence_dispatch_attempt','claim_owner'),
    ('automation_occurrence_dispatch_attempt','claim_until'),
    ('automation_occurrence_dispatch_attempt','target_idempotency_key'),
)
# Explicit real FK child closure, no CASCADE and no lab-only constraints.
TRUNCATE_RELATIONS = {
    'automation_schedule_binding': ('automation_schedule_binding','automation_occurrence',
        'automation_occurrence_dispatch_attempt','automation_occurrence_outbox'),
    'automation_occurrence': ('automation_occurrence','automation_occurrence_dispatch_attempt',
        'automation_occurrence_outbox'),
    'automation_occurrence_dispatch_attempt': ('automation_occurrence_dispatch_attempt',),
}


@pytest.mark.parametrize('table',TABLES)
def test_native_legal_projection_insert_and_mutable_transition(terminal_native_lab, table):
    case = terminal_native_lab.projection_case(table)
    with terminal_native_lab.open('probe') as conn:
        insert_row(conn,case)
        update_row(conn,case,dict(case.mutable_changes))
        # Lab.open always rolls back this controlled transition.


@pytest.mark.parametrize('table,column',IDENTITY_FIELDS)
def test_native_projection_identity_is_immutable(terminal_native_lab, table, column):
    case = terminal_native_lab.projection_case(table)
    with terminal_native_lab.open('probe') as conn:
        insert_row(conn,case)
        with pytest.raises(NativeSQLFailure) as observed:
            with conn.transaction():
                update_row(conn,case,{column:case.identity_changes[column]})
        require(observed.value.state=='23514', 'native projection identity rejection differs')


@pytest.mark.parametrize('table',TABLES)
def test_native_projection_history_delete_rejected(terminal_native_lab, table):
    case = terminal_native_lab.projection_case(table)
    with terminal_native_lab.open('probe') as conn:
        insert_row(conn,case)
        with pytest.raises(NativeSQLFailure) as observed:
            with conn.transaction():delete_row(conn,case)
        require(observed.value.state=='55000', 'native projection history deletion must fail')


@pytest.mark.parametrize('table',TABLES)
def test_native_projection_history_truncate_rejected(terminal_native_lab, table):
    case = terminal_native_lab.projection_case(table)
    with terminal_native_lab.open('probe') as conn:
        insert_row(conn,case)
        with pytest.raises(NativeSQLFailure) as observed:
            with conn.transaction():
                execute(conn,sql.SQL('TRUNCATE {}').format(sql.SQL(',').join(
                    sql.Identifier('public',name) for name in TRUNCATE_RELATIONS[table])))
        require(observed.value.state=='55000', 'native projection truncation must fail')


@pytest.mark.parametrize('table,column',PARENT_MISMATCHES)
def test_native_insert_rejects_wrong_parent_projection(terminal_native_lab, table, column):
    case = terminal_native_lab.projection_case(table)
    with terminal_native_lab.open('probe') as conn:
        with pytest.raises(NativeSQLFailure) as observed:
            with conn.transaction():
                insert_row(conn,case,{column:case.identity_changes[column]})
        require(observed.value.state=='23514', 'native insertion must match its actual parent projection')


PARENTS = ('schedule_dispatch','schedule_runtime','occurrence_schedule','attempt_occurrence')


def _parent(case, kind):
    row = case.row
    scope = (row['org_id'],row['project_id'])
    if kind=='schedule_dispatch':
        return ('SELECT operation_id FROM public.extension_operation_dispatch_binding '
                'WHERE org_id=%s AND project_id=%s AND operation_id=%s', (*scope,row['operation_id']))
    if kind=='schedule_runtime':
        return ('SELECT installation_id FROM public.extension_runtime_binding '
                'WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s',
                (*scope,row['installation_id'],row['generation']))
    if kind=='occurrence_schedule':
        return ('SELECT policy_id FROM public.automation_schedule_binding '
                'WHERE org_id=%s AND project_id=%s AND policy_id=%s AND policy_revision=%s',
                (*scope,row['policy_id'],row['policy_revision']))
    require(kind=='attempt_occurrence', 'fixed native parent required')
    return ('SELECT occurrence_id FROM public.automation_occurrence '
            'WHERE org_id=%s AND project_id=%s AND occurrence_id=%s',(*scope,row['occurrence_id']))


def _case_for_parent(lab, kind):
    table = ('automation_schedule_binding' if kind.startswith('schedule_') else
             'automation_occurrence' if kind=='occurrence_schedule' else
             'automation_occurrence_dispatch_attempt')
    return lab.projection_case(table)


@pytest.mark.parametrize('kind',PARENTS)
def test_native_projection_insert_refuses_existing_nonkey_parent_writer(terminal_native_lab, kind):
    case = _case_for_parent(terminal_native_lab,kind)
    statement,params = _parent(case,kind)
    with terminal_native_lab.open('probe') as writer:
        require(execute(writer,statement+' FOR NO KEY UPDATE NOWAIT',params).fetchone() is not None,
                'actual native parent row required')
        with terminal_native_lab.open('probe') as inserter:
            require(writer.info.backend_pid!=inserter.info.backend_pid, 'independent native backends required')
            with pytest.raises(NativeSQLFailure) as observed:
                with inserter.transaction():insert_row(inserter,case)
            # KEY SHARE alone is compatible with NO KEY UPDATE, so an FK alone
            # cannot satisfy this projection barrier test.
            require(observed.value.state=='55P03', 'native projection parent SHARE barrier missing')


@pytest.mark.parametrize('kind',PARENTS)
def test_native_projection_insert_keeps_parent_share_until_transaction_end(terminal_native_lab, kind):
    case = _case_for_parent(terminal_native_lab,kind)
    statement,params = _parent(case,kind)
    with terminal_native_lab.open('probe') as inserter:
        insert_row(inserter,case)
        with terminal_native_lab.open('probe') as writer:
            require(writer.info.backend_pid!=inserter.info.backend_pid, 'independent native backends required')
            with pytest.raises(NativeSQLFailure) as observed:
                with writer.transaction():execute(writer,statement+' FOR NO KEY UPDATE NOWAIT',params)
            require(observed.value.state=='55P03', 'native projection parent barrier released too early')
    with terminal_native_lab.open('probe') as writer:
        require(execute(writer,statement+' FOR NO KEY UPDATE NOWAIT',params).fetchone() is not None,
                'native parent lock must be released after transaction cleanup')
