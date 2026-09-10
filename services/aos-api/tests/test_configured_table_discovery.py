from contextlib import contextmanager
from types import SimpleNamespace
import pytest
from aos_api.jdbc_connector_runtime import JdbcConnectorRuntime


@pytest.mark.parametrize('count',[0,2,501])
def test_discovery_binds_configured_database_and_bounds_result(count):
    runtime=object.__new__(JdbcConnectorRuntime)
    runtime.database='configured_shop'
    calls=[]
    active=[]
    @contextmanager
    def transaction():
        active.append(True)
        try: yield
        finally: active.pop()
    runtime._read_only_transaction=transaction
    class Cursor:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def execute(self,query,params):
            assert active
            assert 'table_schema=%s' in query and 'LIMIT 501' in query
            assert 'table_rows' not in query and 'table_comment' not in query
            assert params==('configured_shop',)
            calls.append(query)
        def fetchall(self):return [dict(table_name=f't{i}',table_type='BASE TABLE') for i in range(count)]
    runtime._conn=SimpleNamespace(cursor=Cursor)
    result=runtime.list_configured_tables()
    assert len(result['tables'])==min(500,count)
    assert result['truncated']==(count>500)
    assert len(calls)==1 and not active
    assert all(set(item)=={'name','type'} for item in result['tables'])
