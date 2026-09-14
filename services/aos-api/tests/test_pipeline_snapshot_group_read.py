from contextlib import contextmanager
import pytest
from aos_api.jdbc_connector_runtime import JdbcConnectorRuntime
from aos_api.pipeline_source_selection import MappingReadSpec
from aos_api.pipeline_snapshot_group_read import read_snapshot_group


class Connection:
    def __init__(self,rows=None,engine='InnoDB'):
        self.calls=[];self.rows=rows if rows is not None else [{'id':1,'site_id':1}];self.engine=engine;self.active=False;self.tables=('table_a',)
    def get_autocommit(self):return True
    def autocommit(self,value):self.calls.append(('autocommit',value))
    def rollback(self):self.active=False;self.calls.append(('rollback',))
    def close(self):self.calls.append(('close',))
    @contextmanager
    def cursor(self):
        db=self
        class Cursor:
            def execute(self,query,params=None):
                db.calls.append((query,params));self.query=query
                if query=='START TRANSACTION READ ONLY':db.active=True
            def fetchall(self):
                assert db.active
                if 'information_schema' in self.query:return [{'TABLE_NAME':name,'ENGINE':db.engine} for name in db.tables]
                if type(db.rows) is dict:
                    return next(rows for name,rows in db.rows.items() if f'FROM `{name}`' in self.query)
                return db.rows
        yield Cursor()


def runtime(rows=None,engine='InnoDB'):
    rt=JdbcConnectorRuntime({'dbHost':'fixture.invalid','database':'fixture','username':'fixture'},reuse_cache=False);rt._conn=Connection(rows,engine)
    return rt


def spec():return MappingReadSpec('table_a','Shop','id',('id','site_id'),(('site_id',1),))


def test_group_uses_one_read_only_transaction_and_parameterized_rows():
    rt=runtime();conn=rt._conn
    result=read_snapshot_group(rt,(spec(),),row_limit=10,timeout_seconds=30)
    assert result.rows_by_table=={'table_a':[{'id':1,'site_id':1}]}
    assert result.completed_at>=result.started_at
    commands=[c[0] for c in conn.calls]
    assert commands.count('START TRANSACTION READ ONLY')==1
    assert commands.index('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')<commands.index('START TRANSACTION READ ONLY')
    assert commands[-2:]==['rollback','autocommit']
    row_query=[c for c in conn.calls if c[0].startswith('SELECT `')][0]
    assert row_query[1]==(1,10) and 'ORDER BY `id`' in row_query[0]


@pytest.mark.parametrize('fault',['engine','truncated','extra','scope','duplicate','bool_pk','missing_scope'])
def test_bad_group_returns_no_partial_result(fault):
    rows=[{'id':1,'site_id':1}];engine='InnoDB';selected=spec()
    if fault=='engine':engine='MyISAM'
    elif fault=='truncated':rows=[{'id':i,'site_id':1} for i in range(10)]
    elif fault=='extra':rows[0]['secret']='private'
    elif fault=='scope':rows[0]['site_id']=2
    elif fault=='duplicate':rows.append(dict(rows[0]))
    elif fault=='bool_pk':rows[0]['id']=True
    elif fault=='missing_scope':selected=MappingReadSpec('table_a','Shop','id',('id',),(('site_id',1),))
    rt=runtime(rows,engine)
    with pytest.raises(ValueError,match='SNAPSHOT_GROUP_READ_FAILED'):read_snapshot_group(rt,(selected,),row_limit=10,timeout_seconds=30)


@pytest.mark.parametrize('fault',['cached','empty','duplicates','limit','timeout'])
def test_invalid_group_rejected_before_sql(fault):
    rt=runtime();conn=rt._conn;specs=(spec(),);limit=10;timeout=30
    if fault=='cached':rt._reuse_cache=True
    elif fault=='empty':specs=()
    elif fault=='duplicates':specs=(spec(),spec())
    elif fault=='limit':limit=True
    else:timeout=0
    with pytest.raises(ValueError,match='SNAPSHOT_GROUP_READ_FAILED'):read_snapshot_group(rt,specs,row_limit=limit,timeout_seconds=timeout)
    assert conn.calls==[]


@pytest.mark.parametrize('bad_second',[False,True])
def test_multiple_tables_share_transaction_and_late_failure_returns_nothing(bad_second):
    rt=runtime();conn=rt._conn;conn.tables=('table_a','table_b')
    conn.rows={'table_a':[{'id':1,'site_id':1}],'table_b':[{'id':2,'site_id':2 if bad_second else 1}]}
    specs=(spec(),MappingReadSpec('table_b','Shop','id',('id','site_id'),(('site_id',1),)))
    if bad_second:
        with pytest.raises(ValueError,match='SNAPSHOT_GROUP_READ_FAILED'):read_snapshot_group(rt,specs,row_limit=10,timeout_seconds=30)
    else:
        assert set(read_snapshot_group(rt,specs,row_limit=10,timeout_seconds=30).rows_by_table)==set(conn.tables)
    assert sum(c[0]=='START TRANSACTION READ ONLY' for c in conn.calls)==1
    assert sum(c[0].startswith('SELECT `') for c in conn.calls)==2
    assert any(c[0]=='rollback' for c in conn.calls)


def test_expired_group_does_not_return_read_rows(monkeypatch):
    import aos_api.pipeline_snapshot_group_read as module
    ticks=iter([0,0,0,31]);monkeypatch.setattr(module,'monotonic',lambda:next(ticks))
    with pytest.raises(ValueError,match='SNAPSHOT_GROUP_READ_FAILED'):read_snapshot_group(runtime(),(spec(),),row_limit=10,timeout_seconds=30)
