"""Real PG transaction guard; lifecycle authorities are explicit test fixtures."""
from types import SimpleNamespace
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb
import pytest

from test_lifecycle_pg import database, pytestmark
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict, _digest
from aos_api.extension_runtime.replacement_enable_guard import require_predecessor_drained


def seeded(conn,case="valid"):
    installation,generation,operation=uuid4(),uuid4(),uuid4()
    scope=('org-org','dev-project')
    conn.execute('INSERT INTO bundle_installation(org_id,project_id,installation_id) VALUES(%s,%s,%s)',(*scope,installation))
    conn.execute('''INSERT INTO extension_runtime_binding(org_id,project_id,installation_id,generation,
        installation_revision,package_lock_ref,profile_ref,execution_epoch,desired_state,observed_state,enabled,operation_fence,revision)
        VALUES(%s,%s,%s,%s,7,%s,'internal-python-v1',3,'disabled','unknown',false,true,6)''',(*scope,installation,generation,Jsonb({'lockHash':'sha256:'+'a'*64})))
    conn.execute('''INSERT INTO extension_runtime_operation(org_id,project_id,operation_id,installation_id,kind,
        idempotency_key,request_hash,requested_by,expected_installation_etag,status,phase,deadline)
        VALUES(%s,%s,%s,%s,'disable','fixture-disable',%s,'fixture-actor',7,'succeeded','succeeded',now())''',(*scope,operation,installation,'sha256:'+'b'*64))
    payload=dict(installationId=str(installation),generation=str(generation),bindingRevision=6,executionEpoch=3,resourcesRetained=True)
    if case=='false_retained':payload['resourcesRetained']=1
    if case=='wrong_event_installation':payload['installationId']=str(uuid4())
    if case=='stale_event_revision':payload['bindingRevision']=5
    if case!='missing_event':
        conn.execute("""INSERT INTO extension_runtime_event(org_id,project_id,operation_id,sequence,event_id,type,payload,payload_hash)
            VALUES(%s,%s,%s,1,%s,'disabled_committed',%s,%s)""",(*scope,operation,uuid4(),Jsonb(payload),'sha256:'+'0'*64 if case=='bad_hash' else _digest(payload)))
    ref=SimpleNamespace(installation_id=str(installation),revision=7,lock_hash='sha256:'+'a'*64)
    return ref,payload


@pytest.mark.parametrize('case',['valid','missing_binding','enabled','unfenced','draining','wrong_revision','wrong_lock','wrong_epoch','missing_event','bad_hash','false_retained','running','tenant','multiple_bindings','wrong_event_installation','stale_event_revision'])
def test_only_exact_current_disabled_and_drained_predecessor_passes(database,case):
    conn,_,_=database;ref,payload=seeded(conn,case)
    if case=='multiple_bindings':
        conn.execute("""INSERT INTO extension_runtime_binding SELECT org_id,project_id,installation_id,%s,installation_revision,package_lock_ref,profile_ref,config_ref,execution_epoch,desired_state,observed_state,enabled,operation_fence,resource_handle_ref,revision FROM extension_runtime_binding""",(uuid4(),))
    if case=='missing_binding':conn.execute('DELETE FROM extension_runtime_binding')
    if case=='enabled':conn.execute("UPDATE extension_runtime_binding SET enabled=true,operation_fence=false,observed_state='ready',config_ref='{}'")
    if case=='unfenced':conn.execute('UPDATE extension_runtime_binding SET operation_fence=false')
    if case=='draining':conn.execute("UPDATE extension_runtime_binding SET observed_state='draining'")
    if case=='wrong_revision':conn.execute('UPDATE extension_runtime_binding SET installation_revision=8')
    if case=='wrong_lock':conn.execute("UPDATE extension_runtime_binding SET package_lock_ref='{}'")
    if case=='wrong_epoch':conn.execute('UPDATE extension_runtime_binding SET execution_epoch=4')
    if case=='running':conn.execute("UPDATE extension_runtime_operation SET status='running',phase='committing'")
    with conn.transaction():
        args=dict(org_id='dev-org' if case=='tenant' else 'org-org',project_id='dev-project',requested_ref=ref)
        if case=='valid':require_predecessor_drained(conn,**args)
        else:
            with pytest.raises(RuntimeConflict):require_predecessor_drained(conn,**args)


def test_predecessor_binding_lock_blocks_concurrent_reenable_until_commit(database):
    conn,_,schema=database;ref,_=seeded(conn)
    with psycopg.connect(host='127.0.0.1',port=18432,user='postgres',dbname='postgres',autocommit=True) as other:
        other.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(schema)))
        other.execute("SET lock_timeout='150ms'")
        with conn.transaction():
            require_predecessor_drained(conn,org_id='org-org',project_id='dev-project',requested_ref=ref)
            with pytest.raises(psycopg.errors.LockNotAvailable):
                other.execute('UPDATE extension_runtime_binding SET revision=revision+1')
        other.execute('UPDATE extension_runtime_binding SET revision=revision+1')
