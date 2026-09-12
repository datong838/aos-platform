"""Query projection is enforced at the source; it is not an authorization grant."""
from unittest.mock import MagicMock

import pytest

from aos_api.jdbc_connector_runtime import JdbcConnectorRuntime


def runtime():
    value = JdbcConnectorRuntime({'dbHost': 'fixture', 'database': 'fixture', 'username': 'fixture'})
    value._conn = MagicMock()
    value._conn.get_autocommit.return_value = True
    return value


def test_only_selected_columns_leave_source_with_parameterized_scope_and_cursor():
    value = runtime()
    cursor = value._conn.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = [{'site_id': 1, 'site_name': 'fixture'}]
    result = value.read_rows(
        'ns_site', columns=('site_id', 'site_name'), limit=10,
        where_equals={'site_id': 1}, cursor=(0, 'site_id'),
    )
    assert result == [{'site_id': 1, 'site_name': 'fixture'}]
    assert cursor.execute.call_args_list[0].args == ('START TRANSACTION READ ONLY',)
    sql, params = cursor.execute.call_args.args
    assert sql == 'SELECT `site_id`, `site_name` FROM `ns_site` WHERE `site_id` = %s AND `site_id` > %s ORDER BY `site_id` LIMIT %s'
    assert params == (1, 0, 10)
    assert 'site_tel' not in sql
    value._conn.rollback.assert_called_once()
    value._conn.autocommit.assert_any_call(True)


@pytest.mark.parametrize('columns', [
    (), [], 'site_id', ('*',), ('site_id', 'site_id'), ('site_id; SELECT 1',),
    ('COUNT(*)',), ('a.b',), ('site_id --',), (' padded',), (1,),
    tuple(f'field_{i}' for i in range(101)),
])
def test_invalid_projection_is_rejected_before_database_access(columns):
    value = runtime()
    with pytest.raises(ValueError):
        value.read_rows('ns_site', columns=columns, limit=10)
    assert not value._conn.mock_calls


@pytest.mark.parametrize('limit', [None, 0, -1, 1001, True, 1.0, '10'])
def test_selected_reads_require_a_bounded_integer_limit(limit):
    value = runtime()
    with pytest.raises(ValueError):
        value.read_rows('ns_site', columns=('site_id',), limit=limit)
    assert not value._conn.mock_calls


def test_projection_read_error_rolls_back_without_retry():
    value = runtime()
    cursor = value._conn.cursor.return_value.__enter__.return_value
    cursor.execute.side_effect = [None, RuntimeError('fixture read failed')]
    conn = value._conn
    with pytest.raises(RuntimeError, match='fixture read failed'):
        value.read_rows('ns_site', columns=['site_id'], limit=1)
    assert cursor.execute.call_count == 2
    conn.rollback.assert_called_once()
    conn.close.assert_called_once()
