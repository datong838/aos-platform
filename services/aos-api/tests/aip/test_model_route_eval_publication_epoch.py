"""Offline boundary/DDL protocol only; never native permission or lock evidence."""
from copy import deepcopy
from types import SimpleNamespace

import psycopg
import pytest

from aos_api import aip_model_route_eval_publication_epoch as epoch
from aos_api import aip_model_route_eval_owner as owner
from aos_api.tenant_scope import TenantScope

SCOPE=TenantScope('org-org','dev-project')


class Rows:
    def __init__(self,rows):self.rows=deepcopy(rows)
    def fetchone(self):return self.rows[0] if self.rows else None
    def fetchall(self):return self.rows


class ProfileFixture:
    def __init__(self):
        self.info=SimpleNamespace(dbname='unit_only')
        self.ctx=dict(database='unit_only',database_oid=100,role='aos_runtime',login='synthetic_reader',
            org_id='org-org',project_id='dev-project',isolation='serializable',readonly='off',pid=20,xid='30')
        self.profile=dict(owner_oid=200,function_oid=300,owner=epoch.OWNER,language='plpgsql',
            security_definer=True,config=['search_path=pg_catalog'],return_type=20,args='25 25 25',
            body_hash=epoch.FUNCTION_SHA256,volatility='v',parallel='u',strict=False,schema_create=False,edges=0,owned_functions=1,owned_relations=0,owned_schemas=0,
            owned_databases=0,function_acl=sorted([epoch.OWNER+':EXECUTE:false','aos_runtime:EXECUTE:false']),
            relation_acl=['public.aip_publication_epoch:SELECT:false'],
            column_acl=['public.aip_publication_epoch:epoch:UPDATE:false'],schema_acl=['public:USAGE:false'],
            database_acl=[],other_function_acl=[])
        self.profile.update({key:False for key in epoch.ROLE_FLAGS})
        self.table=dict(owner='aos_publication_epoch_owner',rls=True,force_rls=True,owner_edges=0,
            runtime_select=False,runtime_any_update=False,reader_table_update=False,
            reader_insert=False,reader_delete=False,reader_truncate=False)
        self.table.update({key:False for key in epoch.ROLE_FLAGS})
        self.policy=dict(name=epoch.POLICY,roles=[200],command='*',permissive=True,
            using=epoch.POLICY_EXPR,check=epoch.POLICY_EXPR)
        self.triggers=[dict(name='publication_epoch_'+name+'_a0v144',enabled='O',type=kind,args_count=0,
            qualification=None,function='aos_publication_epoch_'+name,owner='aos_publication_epoch_owner',
            language='plpgsql',security_definer=True,config=['search_path=pg_catalog, public, pg_temp'],
            args='',return_type=2279,body_hash=digest) for name,kind,digest in epoch.ORIGINAL_TRIGGERS]
        self.calls=[];self.boundaries=0;self.after={};self.value=1;self.error=None

    def execute(self,sql,params=()):
        text=' '.join(sql.split());assert text.startswith('SELECT ')
        self.calls.append((text,params))
        if 'AS epoch_reader_context' in text:
            self.boundaries+=1
            return Rows([{**self.ctx,**(self.after if self.boundaries>1 else {})}])
        if 'AS epoch_reader_profile' in text:return Rows([self.profile])
        if 'AS epoch_original_table' in text:return Rows([self.table])
        if 'AS epoch_reader_policy' in text:return Rows([self.policy])
        if 'AS epoch_original_trigger' in text:return Rows(self.triggers)
        if 'SELECT public.aos_model_route_eval_publication_epoch_lock' in text:
            if self.error:raise self.error
            return Rows([dict(epoch=self.value)])
        raise AssertionError(text)

    def commit(self):raise AssertionError('no commit')
    def rollback(self):raise AssertionError('no rollback')
    def close(self):raise AssertionError('no close')


def enable_protocol(monkeypatch):
    monkeypatch.setattr(owner,'_require_native_connection',lambda conn:None)


def test_lock_uses_fixed_original_epoch_and_same_caller(monkeypatch):
    enable_protocol(monkeypatch);conn=ProfileFixture()
    assert epoch.lock_eval_publication_epoch(conn,SCOPE,'publication')==1
    calls=[(s,p) for s,p in conn.calls if 'SELECT public.aos_model_route_eval_publication_epoch_lock' in s]
    assert len(calls)==1 and calls[0][1]==(*SCOPE.key,'publication')
    assert conn.boundaries==2


def test_fake_connection_rejected_before_sql():
    conn=ProfileFixture()
    with pytest.raises(ValueError):epoch.lock_eval_publication_epoch(conn,SCOPE,'publication')
    assert not conn.calls


@pytest.mark.parametrize('scope,identifier',[(TenantScope('dev-org','dev-project'),'publication'),
    (SCOPE,''),(SCOPE,' x'),(SCOPE,'x '),(SCOPE,'x'*201),(SCOPE,True)])
def test_scope_and_identifier_fail_before_sql(monkeypatch,scope,identifier):
    enable_protocol(monkeypatch);conn=ProfileFixture()
    with pytest.raises(ValueError):epoch.lock_eval_publication_epoch(conn,scope,identifier)
    assert not conn.calls


@pytest.mark.parametrize('field,value',[
    ('owner','wrong'),('owner_oid',True),('function_oid',0),('language','sql'),('security_definer',False),
    ('config',['search_path=public']),('return_type',25),('args','25 25'),('body_hash','0'*64),
    ('edges',1),('owned_functions',2),('owned_relations',1),('owned_schemas',1),('owned_databases',1),
    ('function_acl',['PUBLIC:EXECUTE:false']),('relation_acl',['public.aip_publication_epoch:UPDATE:false']),
    ('column_acl',['public.aip_publication_epoch:epoch:UPDATE:true']),('schema_acl',['public:CREATE:false']),
    ('database_acl',['unit_only:CREATE:false']),('other_function_acl',['public.other:EXECUTE:false']),
    *[(flag,True) for flag in ('rolcanlogin','rolinherit','rolsuper','rolcreatedb','rolcreaterole','rolreplication','rolbypassrls')],
])
def test_reader_profile_drift_prevents_lock(monkeypatch,field,value):
    enable_protocol(monkeypatch);conn=ProfileFixture();conn.profile[field]=value
    with pytest.raises(ValueError):epoch.lock_eval_publication_epoch(conn,SCOPE,'publication')
    assert not any('SELECT public.aos_model_route_eval_publication_epoch_lock' in s for s,p in conn.calls)


@pytest.mark.parametrize('target,field,value',[
    ('table','owner','wrong'),('table','owner_edges',1),('table','rls',False),('table','force_rls',False),
    ('table','runtime_select',True),('table','runtime_any_update',True),('table','reader_table_update',True),
    ('table','reader_insert',True),('table','reader_delete',True),('table','reader_truncate',True),
    ('table','rolsuper',True),('policy','roles',[0]),('policy','using','true'),('policy','check','true'),
    ('policy','command','r'),('policy','permissive',False),
])
def test_original_table_or_policy_drift_prevents_lock(monkeypatch,target,field,value):
    enable_protocol(monkeypatch);conn=ProfileFixture();getattr(conn,target)[field]=value
    with pytest.raises(ValueError):epoch.lock_eval_publication_epoch(conn,SCOPE,'publication')


@pytest.mark.parametrize('field,value',[('enabled','D'),('type',0),('qualification','true'),
    ('args_count',1),('owner','wrong'),('function','other'),('language','sql'),('security_definer',False),
    ('config',['search_path=public']),('args','25'),('return_type',20),('body_hash','0'*64)])
def test_original_trigger_drift_prevents_lock(monkeypatch,field,value):
    enable_protocol(monkeypatch);conn=ProfileFixture();conn.triggers[0][field]=value
    with pytest.raises(ValueError):epoch.lock_eval_publication_epoch(conn,SCOPE,'publication')


@pytest.mark.parametrize('value',[True,0,-1,'1',None])
def test_epoch_must_be_existing_positive_native_integer(monkeypatch,value):
    enable_protocol(monkeypatch);conn=ProfileFixture();conn.value=value
    with pytest.raises(ValueError):epoch.lock_eval_publication_epoch(conn,SCOPE,'publication')


def test_serialization_failure_is_not_retried_or_repaired(monkeypatch):
    enable_protocol(monkeypatch);conn=ProfileFixture();error=psycopg.errors.SerializationFailure('synthetic');conn.error=error
    with pytest.raises(psycopg.errors.SerializationFailure) as caught:epoch.lock_eval_publication_epoch(conn,SCOPE,'publication')
    assert caught.value is error
    assert sum('SELECT public.aos_model_route_eval_publication_epoch_lock' in s for s,p in conn.calls)==1


@pytest.mark.parametrize('change',[dict(pid=21),dict(xid='31'),dict(login='another'),dict(database_oid=101)])
def test_changed_native_caller_rejected_after_lock(monkeypatch,change):
    enable_protocol(monkeypatch);conn=ProfileFixture();conn.after=change
    with pytest.raises(ValueError):epoch.lock_eval_publication_epoch(conn,SCOPE,'publication')


def test_installer_adds_only_new_bridge_privileges_and_no_original_fact_mutation():
    sql=[];epoch.install_eval_publication_epoch_reader(sql.append)
    combined='\n'.join(sql)
    assert 'CREATE OR REPLACE' not in combined
    assert 'CREATE TABLE' not in combined
    assert 'GRANT SELECT,UPDATE(epoch) ON public.aip_publication_epoch TO '+epoch.OWNER in combined
    assert 'GRANT EXECUTE ON FUNCTION '+epoch.SIGNATURE+' TO aos_runtime' in combined
    assert 'ALTER FUNCTION public.aos_publication_epoch_lock' not in combined
    assert 'ALTER ROLE aos_publication_epoch_owner' not in combined
    function=next(s for s in sql if s.startswith('CREATE FUNCTION '))
    body=function.split('AS $$',1)[1].rsplit('$$',1)[0]
    assert body==epoch.FUNCTION_BODY and 'FOR SHARE' in body
    assert not any(word in body for word in ('INSERT INTO','UPDATE public.','DELETE FROM','COMMIT','ROLLBACK'))


def test_pinned_trigger_bodies_equal_original_migration_not_reimplemented():
    from pathlib import Path
    from types import SimpleNamespace
    from hashlib import sha256
    import re,runpy
    path=Path(__file__).resolve().parents[2]/'alembic/versions/a0v_144_binding_evaluator_boundary.py'
    original=runpy.run_path(str(path));statements=[]
    original['_publication_epoch_boundary'].__globals__['op']=SimpleNamespace(execute=statements.append)
    original['_publication_epoch_boundary']()
    bodies={}
    for sql in statements:
        match=re.search(r'CREATE FUNCTION public\.(aos_publication_epoch_(?:touch|bump))\(\).*?AS \$\$(.*?)\$\$',sql,re.S)
        if match:bodies[match[1]]=sha256(match[2].encode()).hexdigest()
    assert bodies=={'aos_publication_epoch_'+name:digest for name,kind,digest in epoch.ORIGINAL_TRIGGERS}


def test_catalog_drift_after_lock_is_rejected_without_second_lock(monkeypatch):
    enable_protocol(monkeypatch);conn=ProfileFixture();original=conn.execute;count=0
    def changing(sql,params=()):
        nonlocal count
        if 'AS epoch_reader_profile' in sql:
            count+=1
            if count==2:conn.profile['body_hash']='0'*64
        return original(sql,params)
    conn.execute=changing
    with pytest.raises(ValueError):epoch.lock_eval_publication_epoch(conn,SCOPE,'publication')
    assert sum('SELECT public.aos_model_route_eval_publication_epoch_lock' in s for s,p in conn.calls)==1


@pytest.mark.parametrize('field,value',[('schema_create',True),('volatility','s'),('parallel','s'),('strict',True)])
def test_effective_schema_create_and_function_attribute_drift(monkeypatch,field,value):
    enable_protocol(monkeypatch);conn=ProfileFixture()
    conn.profile.update(schema_create=False,volatility='v',parallel='u',strict=False)
    conn.profile[field]=value
    with pytest.raises(ValueError):epoch.lock_eval_publication_epoch(conn,SCOPE,'publication')


def test_missing_epoch_result_is_rejected_without_fallback_or_initialization(monkeypatch):
    enable_protocol(monkeypatch);conn=ProfileFixture();original=conn.execute
    def missing(sql,params=()):
        if 'SELECT public.aos_model_route_eval_publication_epoch_lock' in sql:
            conn.calls.append((' '.join(sql.split()),params));return Rows([])
        return original(sql,params)
    conn.execute=missing
    with pytest.raises(ValueError):epoch.lock_eval_publication_epoch(conn,SCOPE,'publication')
    assert sum('SELECT public.aos_model_route_eval_publication_epoch_lock' in s for s,p in conn.calls)==1


def test_original_trigger_real_postgres_canonical_config_is_accepted(monkeypatch):
    enable_protocol(monkeypatch);conn=ProfileFixture()
    for trigger in conn.triggers:trigger['config']=['search_path=pg_catalog, public, pg_temp']
    assert epoch.lock_eval_publication_epoch(conn,SCOPE,'publication')==1


@pytest.mark.parametrize('config',[['search_path=pg_catalog,public,pg_temp'],
    ['search_path=public, pg_catalog, pg_temp'],['search_path=pg_catalog, public']])
def test_original_trigger_noncanonical_or_changed_path_still_rejected(monkeypatch,config):
    enable_protocol(monkeypatch);conn=ProfileFixture();conn.triggers[0]['config']=config
    with pytest.raises(ValueError):epoch.lock_eval_publication_epoch(conn,SCOPE,'publication')
