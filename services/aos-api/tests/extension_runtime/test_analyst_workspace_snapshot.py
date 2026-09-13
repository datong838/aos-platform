from datetime import datetime, timezone
from types import SimpleNamespace
import pytest
from aos_api.tenant_scope import TenantScope
from aos_api.extension_runtime.analyst_workspace_snapshot import read_analyst_workspace_snapshot

class Result:
    def __init__(self,one=None,rows=None):self.one=one;self.rows=rows
    def fetchone(self):return self.one
    def fetchall(self):return self.rows

class Connection:
    def __init__(self,rows):
        from psycopg.pq import TransactionStatus
        self.info=SimpleNamespace(transaction_status=TransactionStatus.INTRANS)
        self.rows=rows;self.queries=[];self.isolation='repeatable read'
    def execute(self,q,p=()):
        self.queries.append((q,p))
        if q=='SHOW transaction_isolation':return Result(one={'transaction_isolation':self.isolation})
        if 'clock_timestamp()' in q:return Result(one={'cutoff_at':datetime.now(timezone.utc)})
        if 'WITH selected_cases' in q:return Result(rows=self.rows)
        raise AssertionError(q)


def row(case_id='case-1',run_id=None):
    return dict(case_id=case_id,case_authority={'caseId':case_id},run_id=run_id,
                run_authority={'runId':run_id} if run_id else None,state_authority={'runId':run_id} if run_id else None)


def test_bounded_source_keeps_scope_and_explicit_truncation(monkeypatch):
    calls=[]
    monkeypatch.setattr('aos_api.extension_runtime.analyst_workspace_snapshot.read_current_ui_principal',lambda **kw:calls.append(kw))
    conn=Connection([row('case-1','r1'),row('case-1','r2'),row('case-2')])
    scope=TenantScope('org-org','dev-project')
    result=read_analyst_workspace_snapshot(conn=conn,scope=scope,subject='reader',required_markings=(),case_limit=1,run_limit=1)
    assert calls[0]['scope']==scope and calls[0]['subject']=='reader'
    assert result['truncated'] is True and len(result['cases'])==1 and len(result['cases'][0]['runs'])==1
    assert conn.queries[-1][1]==('org-org','dev-project',2,2)
    assert all(q.startswith(('SHOW','SELECT','WITH')) for q,_ in conn.queries)


@pytest.mark.parametrize('problem',['isolation','missing-state','duplicate-run','permission'])
def test_invalid_snapshot_cannot_be_returned(monkeypatch,problem):
    def current(**kw):
        if problem=='permission':raise PermissionError('revoked')
    monkeypatch.setattr('aos_api.extension_runtime.analyst_workspace_snapshot.read_current_ui_principal',current)
    values=[row('case-1','r1')];conn=Connection(values)
    if problem=='isolation':conn.isolation='read committed'
    if problem=='missing-state':values[0]['state_authority']=None
    if problem=='duplicate-run':values.append(row('case-1','r1'))
    with pytest.raises((ValueError,PermissionError)):
        read_analyst_workspace_snapshot(conn=conn,scope=TenantScope('org-org','dev-project'),subject='reader',required_markings=())
    if problem=='permission':assert not any('WITH selected_cases' in q for q,_ in conn.queries)
