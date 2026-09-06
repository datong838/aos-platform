"""Immutable configuration authority in an explicitly ephemeral schema only."""
from pathlib import Path
from types import SimpleNamespace
import importlib.util

import psycopg
from psycopg import sql
import pytest

from test_lifecycle_pg import database, pytestmark
from test_configuration_target_pg import case


@pytest.fixture
def configuration_case(database):
    conn, _, schema = database
    args = case(conn)
    path = Path(__file__).resolve().parents[2] / 'alembic/versions/ar1_002_runtime_configuration.py'
    spec = importlib.util.spec_from_file_location('configuration_test_migration',path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.op = SimpleNamespace(execute=conn.execute)
    module.upgrade()
    # A named test-only authority, not a simulated production budget or membership.
    conn.execute('''CREATE TABLE test_configuration_refs
        (org_id text,project_id text,purpose text,ref_id text,revision bigint,hash text)''')
    conn.execute('''CREATE TABLE test_configuration_actors(org_id text,project_id text,actor text)''')
    conn.execute("INSERT INTO test_configuration_actors VALUES('org-org','dev-project','test-actor')")
    def ref(purpose):
        item = dict(authority='test.configuration',id=purpose,revision=1,hash='sha256:'+'a'*64)
        conn.execute("INSERT INTO test_configuration_refs VALUES('org-org','dev-project',%s,%s,1,%s)",
            (purpose,purpose,item['hash']))
        return item
    document = dict(schemaVersion=1,roleRefs=(ref('role'),),dataRefs=(ref('data'),),budgetRef=ref('budget'),policyRef=ref('policy'))
    conn.execute(sql.SQL('GRANT USAGE ON SCHEMA {} TO aos_runtime').format(sql.Identifier(schema)))
    conn.execute('GRANT SELECT,UPDATE ON bundle_installation,test_configuration_actors,test_configuration_refs TO aos_runtime')
    from aos_api.extension_runtime.configuration_authorization import ConfigurationAuthorization
    def permission(db, *, org_id, project_id, actor, **_):
        return db.execute('SELECT actor FROM test_configuration_actors WHERE org_id=%s AND project_id=%s AND actor=%s FOR SHARE',
                          (org_id,project_id,actor)).fetchone() is not None
    def reader(db, *, org_id, project_id, purpose, ref, **_):
        return db.execute('''SELECT ref_id FROM test_configuration_refs WHERE org_id=%s AND project_id=%s
            AND purpose=%s AND ref_id=%s AND revision=%s AND hash=%s FOR SHARE''',
            (org_id,project_id,purpose,ref.id,ref.revision,ref.hash)).fetchone() is not None
    authorize=ConfigurationAuthorization(permission=permission,readers={
        (purpose,'test.configuration'):reader for purpose in ('role','data','budget','policy')})
    conn.execute('SET ROLE aos_runtime')
    write_args = dict(org_id=args['org_id'],project_id=args['project_id'],installation_id=args['installation_id'],
        generation=args['configuration_target']['generation'],expected_installation_etag=1,expected_binding_revision=1,
        actor='test-actor',idempotency_key='first-config',configuration=document,authorize=authorize)
    return conn, write_args


def read_args(args, ref):
    return {key:args[key] for key in ('org_id','project_id','installation_id','generation','actor','authorize')} | {'ref':ref}


def test_configuration_history_replay_and_readback(configuration_case):
    from aos_api.extension_runtime.configuration_store import append_configuration, read_configuration
    conn, args = configuration_case
    with conn.transaction(): first = append_configuration(conn, **args)
    with conn.transaction(): assert append_configuration(conn, **args) == first
    with conn.transaction(): assert read_configuration(conn, **read_args(args, first)).budgetRef.id == 'budget'
    with conn.transaction(): second = append_configuration(conn,**{**args,'idempotency_key':'second-config'},previous_ref=first)
    assert second.configurationId == first.configurationId and second.revision == 2 and second.hash != first.hash
    with conn.transaction(): assert read_configuration(conn, **read_args(args, first)).schemaVersion == 1
    assert conn.execute('SELECT count(*) FROM extension_runtime_configuration').fetchone() == (2,)
    assert conn.execute('SELECT config_ref,enabled,execution_epoch FROM extension_runtime_binding').fetchone() == (None,False,1)


@pytest.mark.parametrize('mode',['closed','no_pointer','bad_pointer','unfenced','uninstalled','stopped','desired_enabled'])
def test_configuration_repair_only_stages_while_closed(configuration_case,mode):
    from psycopg.types.json import Jsonb
    from aos_api.extension_runtime.configuration_store import append_configuration
    conn,args=configuration_case
    with conn.transaction():first=append_configuration(conn,**args)
    pointer=None if mode=='no_pointer' else {} if mode=='bad_pointer' else first.model_dump(mode='json')
    conn.execute('''UPDATE extension_runtime_binding SET observed_state=%s,config_ref=%s,
        operation_fence=%s,desired_state=%s''',('stopped' if mode=='stopped' else 'unknown',Jsonb(pointer),
        mode!='unfenced','uninstalled' if mode=='uninstalled' else 'enabled' if mode=='desired_enabled' else 'disabled'))
    args={**args,'idempotency_key':'repair-configuration'}
    if mode=='closed':
        with conn.transaction():assert append_configuration(conn,**args,previous_ref=first).revision==2
    else:
        with pytest.raises(ValueError):
            with conn.transaction():append_configuration(conn,**args,previous_ref=first)
    assert conn.execute('SELECT enabled,observed_state FROM extension_runtime_binding').fetchone()==(False,'stopped' if mode=='stopped' else 'unknown')


@pytest.mark.parametrize('failure',['actor','role','data','budget','policy','async','scope','tenant','etag','binding','rollback','invalid','duplicate'])
def test_configuration_rejects_invalid_or_revoked_inputs(configuration_case,failure):
    from aos_api.extension_runtime.configuration_store import append_configuration
    conn, args = configuration_case
    if failure in {'actor','role','data','budget','policy'}:
        conn.execute('RESET ROLE')
        if failure == 'actor':conn.execute('DELETE FROM test_configuration_actors')
        else:conn.execute('DELETE FROM test_configuration_refs WHERE purpose=%s',(failure,))
        conn.execute('SET ROLE aos_runtime')
    elif failure == 'async':
        async def deferred(*args, **kwargs):return True
        args['authorize']=deferred
    elif failure == 'scope':conn.execute("SELECT set_config('aos.org_id','',false)")
    elif failure == 'tenant':args['org_id']='dev-org'
    elif failure == 'etag':args['expected_installation_etag']=2
    elif failure == 'binding':args['expected_binding_revision']=2
    elif failure == 'invalid':args['configuration']['secret']='forbidden-test-field'
    elif failure == 'duplicate':args['configuration']['roleRefs']*=2
    with pytest.raises((ValueError,PermissionError,LookupError,RuntimeError)):
        with conn.transaction():
            append_configuration(conn,**args)
            if failure=='rollback':raise RuntimeError('rollback')
    conn.execute('RESET ROLE')
    assert conn.execute('SELECT count(*) FROM extension_runtime_configuration').fetchone() == (0,)


@pytest.mark.parametrize('failure',['hash','version','revoked','branch','body','cross_generation'])
def test_configuration_exact_history_cannot_be_rebound(configuration_case,failure):
    from aos_api.extension_runtime.configuration_store import append_configuration,read_configuration
    conn,args=configuration_case
    with conn.transaction():first=append_configuration(conn,**args)
    if failure=='branch':
        with conn.transaction():append_configuration(conn,**{**args,'idempotency_key':'version-two'},previous_ref=first)
    if failure=='revoked':
        conn.execute('RESET ROLE');conn.execute('DELETE FROM test_configuration_refs');conn.execute('SET ROLE aos_runtime')
    with pytest.raises((ValueError,PermissionError,LookupError)):
        with conn.transaction():
            if failure=='branch':append_configuration(conn,**{**args,'idempotency_key':'bad-branch'},previous_ref=first)
            elif failure=='body':append_configuration(conn,**{**args,'configuration':{**args['configuration'],'roleRefs':()}})
            else:
                target=read_args(args,first)
                if failure=='hash':target['ref']=first.model_copy(update={'hash':'sha256:'+'b'*64})
                if failure=='version':target['ref']=first.model_copy(update={'revision':3})
                if failure=='cross_generation':
                    from uuid import uuid4
                    target['generation']=str(uuid4())
                read_configuration(conn,**target)


def test_configuration_runtime_cannot_mutate_or_truncate_history(configuration_case):
    from aos_api.extension_runtime.configuration_store import append_configuration
    conn,args=configuration_case
    with conn.transaction():append_configuration(conn,**args)
    for statement in ['UPDATE extension_runtime_configuration SET actor=actor','DELETE FROM extension_runtime_configuration',
                      'TRUNCATE extension_runtime_configuration','CREATE TABLE forbidden_config_runtime(id int)']:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):conn.execute(statement)
    conn.execute('RESET ROLE')
    for statement in ['UPDATE extension_runtime_configuration SET actor=actor','DELETE FROM extension_runtime_configuration','TRUNCATE extension_runtime_configuration']:
        with pytest.raises(psycopg.errors.RaiseException):conn.execute(statement)


def test_configuration_rls_and_content_hash_are_checked(configuration_case):
    from aos_api.extension_runtime.configuration_store import append_configuration,read_configuration
    conn,args=configuration_case
    with conn.transaction():first=append_configuration(conn,**args)
    for org in ('dev-org',''):
        conn.execute("SELECT set_config('aos.org_id',%s,false)",(org,))
        assert conn.execute('SELECT count(*) FROM extension_runtime_configuration').fetchone() == (0,)
    conn.execute("SELECT set_config('aos.org_id','org-org',false)")
    conn.execute('RESET ROLE')
    conn.execute('ALTER TABLE extension_runtime_configuration DISABLE TRIGGER immutable_history')
    conn.execute("UPDATE extension_runtime_configuration SET actor='tampered-test-actor'")
    conn.execute('SET ROLE aos_runtime')
    with pytest.raises(ValueError,match='hash'):
        with conn.transaction():read_configuration(conn,**read_args(args,first))


def test_configuration_replay_precedes_new_cas_but_rechecks_authority(configuration_case):
    from aos_api.extension_runtime.configuration_store import append_configuration
    conn,args=configuration_case
    with conn.transaction():first=append_configuration(conn,**args)
    conn.execute('UPDATE extension_runtime_binding SET revision=2')
    conn.execute('UPDATE bundle_installation SET etag_version=2')
    with conn.transaction():assert append_configuration(conn,**args) == first
    conn.execute('RESET ROLE');conn.execute('DELETE FROM test_configuration_actors');conn.execute('SET ROLE aos_runtime')
    with pytest.raises(PermissionError):
        with conn.transaction():append_configuration(conn,**args)


def test_two_configuration_updates_cannot_fork_the_same_previous_revision(configuration_case):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from aos_api.extension_runtime.configuration_store import append_configuration
    from aos_api.extension_runtime.lifecycle_store import RuntimeRevisionConflict
    conn,args=configuration_case
    schema=conn.execute('SELECT current_schema()').fetchone()[0]
    with conn.transaction():first=append_configuration(conn,**args)
    barrier=Barrier(2)
    def update(index):
        with psycopg.connect(host='127.0.0.1',port=18432,user='postgres',dbname='postgres',autocommit=True) as other:
            other.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(schema)))
            other.execute('SET ROLE aos_runtime')
            other.execute("SELECT set_config('aos.org_id','org-org',false),set_config('aos.project_id','dev-project',false)")
            other.execute("SET statement_timeout='5s'")
            barrier.wait(timeout=5)
            try:
                with other.transaction():append_configuration(other,**{**args,'idempotency_key':f'competing-{index}'},previous_ref=first)
                return 'appended'
            except RuntimeRevisionConflict:return 'conflict'
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(update,range(2)))
    assert sorted(results)==['appended','conflict']
    assert conn.execute('SELECT count(*) FROM extension_runtime_configuration').fetchone() == (2,)


@pytest.mark.parametrize('invalid',['same_source_versions','source_large_revision','large_binding_revision','large_config_revision'])
def test_configuration_dto_rejects_ambiguous_or_out_of_range_references(invalid):
    from aos_api.extension_runtime.configuration_contracts import ConfigurationDocument,ConfigureTarget,ConfigurationRef
    from uuid import uuid4
    ref=dict(authority='test.configuration',id='source',revision=1,hash='sha256:'+'a'*64)
    with pytest.raises(ValueError):
        if invalid=='same_source_versions':
            ConfigurationDocument(roleRefs=(ref,{**ref,'revision':2}),dataRefs=(),budgetRef=ref,policyRef=ref)
        elif invalid=='source_large_revision':
            ConfigurationDocument(roleRefs=(),dataRefs=(),budgetRef={**ref,'revision':2**63},policyRef=ref)
        elif invalid=='large_config_revision':
            ConfigurationRef(configurationId=str(uuid4()),revision=2**63,hash=ref['hash'])
        else:
            ConfigureTarget(generation=str(uuid4()),bindingRevision=2**63,configRef=dict(configurationId=str(uuid4()),revision=1,hash=ref['hash']))


@pytest.mark.parametrize('purpose',['roleRefs','dataRefs','budgetRef','policyRef'])
def test_configuration_reference_authority_is_exact(configuration_case,purpose):
    from aos_api.extension_runtime.configuration_store import append_configuration
    conn,args=configuration_case
    document=args['configuration']
    target=document[purpose][0] if purpose.endswith('Refs') else document[purpose]
    target['authority']='another.test.authority'
    with pytest.raises(PermissionError):
        with conn.transaction():append_configuration(conn,**args)
