"""Native resource history retention; never creates a container or reads tokens."""
import pytest

from asset_registry.test_terminal_source_readlock_pg import (
    _isolated_postgres_database, terminal_native_lab, NativeSQLFailure,
    ROW_COLUMNS, ROW_MUTABLE, insert_row, update_row, delete_row, execute, require,
)

IDENTITY = tuple(column for column in ROW_COLUMNS['extension_runtime_resource_lease']
                 if column not in ROW_MUTABLE['extension_runtime_resource_lease'])


def test_native_resource_legal_insert_and_original_mutable_fields(terminal_native_lab):
    case = terminal_native_lab.resource_case()
    with terminal_native_lab.open('probe') as conn:
        insert_row(conn,case)
        update_row(conn,case,dict(case.mutable_changes))


@pytest.mark.parametrize('column',IDENTITY)
def test_native_resource_identity_change_rejected(terminal_native_lab, column):
    case = terminal_native_lab.resource_case()
    with terminal_native_lab.open('probe') as conn:
        insert_row(conn,case)
        with pytest.raises(NativeSQLFailure) as observed:
            with conn.transaction():update_row(conn,case,{column:case.identity_changes[column]})
        require(observed.value.state=='23514', 'native resource identity rejection differs')


def test_native_resource_history_delete_rejected(terminal_native_lab):
    case = terminal_native_lab.resource_case()
    with terminal_native_lab.open('probe') as conn:
        insert_row(conn,case)
        with pytest.raises(NativeSQLFailure) as observed:
            with conn.transaction():delete_row(conn,case)
        require(observed.value.state=='55000', 'native resource history deletion must fail')


def test_native_resource_history_truncate_rejected(terminal_native_lab):
    case = terminal_native_lab.resource_case()
    with terminal_native_lab.open('probe') as conn:
        insert_row(conn,case)
        with pytest.raises(NativeSQLFailure) as observed:
            with conn.transaction():execute(conn,'TRUNCATE public.extension_runtime_resource_lease')
        require(observed.value.state=='55000', 'native resource history truncation must fail')
