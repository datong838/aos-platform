from types import SimpleNamespace
import pytest
from aos_api.tenant_scope import TenantScope
from aos_api.extension_runtime.ui_current_principal import read_current_ui_principal
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict

class Result:
    def __init__(self, row=None, rows=None):self.row=row;self.rows=rows
    def fetchone(self):return self.row
    def fetchall(self):return self.rows

class Connection:
    def __init__(self):
        from psycopg.pq import TransactionStatus
        self.info=SimpleNamespace(transaction_status=TransactionStatus.INTRANS)
        self.role_rows=[{'role':'operator'}];self.marking_rows=[{'object_key':'marking:public'}]
        self.scope={'org_id':'org-org','project_id':'dev-project'};self.calls=[]
    def execute(self,query,params=()):
        self.calls.append((query,params))
        if 'current_setting' in query:return Result(row=self.scope)
        if 'meta_membership' in query:return Result(rows=self.role_rows)
        if 'authz_tuple' in query:return Result(rows=self.marking_rows)
        raise AssertionError(query)

def read(conn):
    return read_current_ui_principal(conn=conn,scope=TenantScope('org-org','dev-project'),subject='user:reader',required_markings=('public',))

def test_current_identity_has_no_execution_grant(monkeypatch):
    monkeypatch.setattr('aos_api.extension_runtime.ui_current_principal.openfga_api_url',lambda:None)
    conn=Connection(); result=read(conn)
    assert result.subject=='user:reader' and result.roles==('operator',) and result.markings==('public',)
    assert all('FOR SHARE' in q for q,_ in conn.calls[1:])
    from aos_api.openfga import user_key
    assert conn.calls[1][1][-1] == 'user:reader'
    assert conn.calls[2][1][-2] == user_key('user:reader')
    assert not hasattr(result,'executable')

@pytest.mark.parametrize('drift',['scope','removed','duplicate','marking','idle','remote'])
def test_invalid_current_identity_is_denied(monkeypatch,drift):
    monkeypatch.setattr('aos_api.extension_runtime.ui_current_principal.openfga_api_url',lambda:'https://example.test' if drift=='remote' else None)
    conn=Connection()
    if drift=='scope':conn.scope['org_id']='dev-org'
    if drift=='removed':conn.role_rows=[]
    if drift=='duplicate':conn.role_rows*=2
    if drift=='marking':conn.marking_rows=[]
    if drift=='idle':
        from psycopg.pq import TransactionStatus
        conn.info.transaction_status=TransactionStatus.IDLE
    with pytest.raises(RuntimeError if drift == 'idle' else RuntimeConflict):read(conn)
