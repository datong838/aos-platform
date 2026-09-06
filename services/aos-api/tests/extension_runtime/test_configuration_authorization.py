from types import SimpleNamespace
from uuid import uuid4

import pytest
from psycopg.pq import TransactionStatus

from aos_api.extension_runtime.configuration_contracts import ConfigurationDocument


class Connection:
    info = SimpleNamespace(transaction_status=TransactionStatus.INTRANS)
    def execute(self, query): return self
    def fetchone(self): return ('org-org', 'dev-project')


def setup_case():
    from aos_api.extension_runtime.configuration_authorization import ConfigurationAuthorization
    calls=[]
    def permission(conn, **kw): calls.append('actor'); return True
    def reader(conn, **kw): calls.append(kw['purpose']); return True
    readers={(purpose,'test.authority'):reader for purpose in ('role','data','budget','policy')}
    ref=dict(authority='test.authority',id='item',revision=1,hash='sha256:'+'a'*64)
    document=ConfigurationDocument(roleRefs=(ref,),dataRefs=(ref,),budgetRef=ref,policyRef=ref)
    args=dict(org_id='org-org',project_id='dev-project',installation_id=str(uuid4()),generation=str(uuid4()),actor='tester',configuration=document)
    return ConfigurationAuthorization,readers,permission,calls,args


def test_all_purposes_and_registration_snapshot():
    cls,readers,permission,calls,args=setup_case()
    checker=cls(permission=permission,readers=readers)
    readers.clear()
    assert checker(Connection(),**args) is True
    assert calls == ['actor','role','data','budget','policy']


@pytest.mark.parametrize('purpose',['role','data','budget','policy'])
def test_missing_reader_never_skipped(purpose):
    cls,readers,permission,calls,args=setup_case()
    del readers[(purpose,'test.authority')]
    with pytest.raises(PermissionError): cls(permission=permission,readers=readers)(Connection(),**args)


@pytest.mark.parametrize('value',[False,None,1,{},'yes'])
def test_non_boolean_reference_verdict_rejected(value):
    cls,readers,permission,calls,args=setup_case()
    readers[('budget','test.authority')]=lambda *a,**k:value
    with pytest.raises(PermissionError): cls(permission=permission,readers=readers)(Connection(),**args)


def test_permission_rechecked_without_reference_reads():
    cls,readers,permission,calls,args=setup_case()
    state=[True]
    checker=cls(permission=lambda *a,**k:state[0],readers=readers)
    assert checker(Connection(),**args) is True
    calls.clear();state[0]=False
    with pytest.raises(PermissionError):checker(Connection(),**args)
    assert calls == []


def test_async_reader_rejected():
    cls,readers,permission,calls,args=setup_case()
    async def reader(*a,**k):return True
    readers[('policy','test.authority')]=reader
    with pytest.raises(ValueError):cls(permission=permission,readers=readers)(Connection(),**args)


def test_scope_mismatch_rejected_before_callbacks():
    cls,readers,permission,calls,args=setup_case()
    args['org_id']='dev-org'
    with pytest.raises(PermissionError):cls(permission=permission,readers=readers)(Connection(),**args)
    assert calls == []


def test_forged_model_revalidated():
    cls,readers,permission,calls,args=setup_case()
    args['configuration']=args['configuration'].model_copy(update={'budgetRef':None})
    with pytest.raises(ValueError):cls(permission=permission,readers=readers)(Connection(),**args)
    assert calls == []


def test_reference_order_and_exact_context():
    cls,readers,permission,calls,args=setup_case()
    document=args['configuration']
    first=document.roleRefs[0]
    args['configuration']=document.model_copy(update={'roleRefs':(
        first.model_copy(update={'id':'z'}),first.model_copy(update={'id':'a'}))})
    connection=Connection()
    seen=[]
    def reader(conn,**kwargs):
        assert conn is connection
        assert all(kwargs[key]==args[key] for key in ('actor','org_id','project_id','installation_id','generation'))
        seen.append(kwargs['ref'].id)
        return True
    readers[('role','test.authority')]=reader
    assert cls(permission=permission,readers=readers)(connection,**args) is True
    assert seen==['a','z']


def test_only_policy_reader_receives_revalidated_configuration_document():
    cls,readers,permission,calls,args=setup_case()
    seen=[]
    def policy(conn,**kwargs):
        seen.append(kwargs['configuration'])
        return True
    readers[('policy','test.authority')]=policy
    assert cls(permission=permission,readers=readers)(Connection(),**args) is True
    assert seen == [args['configuration']]


@pytest.mark.parametrize('key',[('unknown','test.authority'),('role','*'),('role',''), 'role'])
def test_invalid_registration(key):
    cls,readers,permission,calls,args=setup_case()
    readers[key]=lambda *a,**k:True
    with pytest.raises(ValueError):cls(permission=permission,readers=readers)
