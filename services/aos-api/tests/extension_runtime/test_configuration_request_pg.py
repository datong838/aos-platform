"""Recovery reads and fencing are bound to the original accepted target."""
from datetime import timezone, timedelta
from uuid import uuid4

import pytest
from psycopg.types.json import Jsonb
from psycopg.rows import dict_row

from test_lifecycle_pg import database, pytestmark
from test_configuration_target_pg import case
from aos_api.extension_runtime.lifecycle_store import RuntimeOperationStore, RuntimeConflict, _digest
from aos_api.extension_runtime.binding_store import RuntimeBindingStore


@pytest.mark.parametrize('offset', [0, 8, -5])
def test_configuration_recovery_is_timezone_stable_and_fences_exact_target(database, offset):
    from aos_api.extension_runtime.configuration_request import load_configure_target
    conn, _, _ = database
    args = case(conn)
    args['deadline'] = args['deadline'].astimezone(timezone(timedelta(hours=offset)))
    ops = RuntimeOperationStore()
    with conn.transaction():
        op = ops.accept(conn, **args)
    original_factory = conn.row_factory
    if offset == 8: conn.row_factory = dict_row
    with conn.transaction():
        target = load_configure_target(conn, org_id=args['org_id'], project_id=args['project_id'],operation_id=op.operation_id)
        assert target.model_dump(mode='json') == args['configuration_target']
        ops.advance(conn,org_id=args['org_id'],project_id=args['project_id'],operation_id=op.operation_id,
            expected_revision=1,phase='validating')
        RuntimeBindingStore().fence(conn,org_id=args['org_id'],project_id=args['project_id'],
            installation_id=args['installation_id'],generation=target.generation,operation_id=op.operation_id,
            expected_operation_revision=2,expected_binding_revision=1)
    conn.row_factory = original_factory
    assert conn.execute('SELECT enabled,operation_fence,execution_epoch,revision,config_ref FROM extension_runtime_binding').fetchone() == (False,True,2,2,None)
    with pytest.raises(RuntimeConflict):
        with conn.transaction():
            RuntimeBindingStore().fence(conn,org_id=args['org_id'],project_id=args['project_id'],
                installation_id=args['installation_id'],generation=target.generation,operation_id=op.operation_id,
                expected_operation_revision=2,expected_binding_revision=1)


def test_configuration_cannot_fence_another_generation_with_same_revision(database):
    conn, _, _ = database
    args = case(conn)
    other = uuid4()
    conn.execute('''INSERT INTO extension_runtime_binding
        SELECT org_id,project_id,installation_id,%s,installation_revision,package_lock_ref,profile_ref,config_ref,
        execution_epoch,desired_state,observed_state,enabled,operation_fence,resource_handle_ref,revision
        FROM extension_runtime_binding''',(other,))
    with conn.transaction():
        op = RuntimeOperationStore().accept(conn, **args)
        RuntimeOperationStore().advance(conn,org_id=args['org_id'],project_id=args['project_id'],operation_id=op.operation_id,
            expected_revision=1,phase='validating')
    with pytest.raises(RuntimeConflict,match='target'):
        with conn.transaction():
            RuntimeBindingStore().fence(conn,org_id=args['org_id'],project_id=args['project_id'],
                installation_id=args['installation_id'],generation=other,operation_id=op.operation_id,
                expected_operation_revision=2,expected_binding_revision=1)
    assert conn.execute('SELECT sum(execution_epoch) FROM extension_runtime_binding').fetchone() == (2,)


@pytest.mark.parametrize('corruption', ['missing','payload_hash','rehashed_target','request_hash','actor','revision','kind','tenant','scope'])
def test_configuration_reader_rejects_unbound_or_corrupt_record(database, corruption):
    from aos_api.extension_runtime.configuration_request import load_configure_target
    conn, _, _ = database
    args = case(conn)
    with conn.transaction():
        op = RuntimeOperationStore().accept(conn, **args)
    # Test-only maintenance corrupts the ephemeral ledger, never application data.
    if corruption in {'missing','payload_hash','rehashed_target'}:
        conn.execute('ALTER TABLE extension_runtime_event DISABLE TRIGGER immutable_history')
        if corruption == 'missing':
            conn.execute('DELETE FROM extension_runtime_outbox')
            conn.execute('DELETE FROM extension_runtime_event')
        elif corruption == 'payload_hash': conn.execute("UPDATE extension_runtime_event SET payload_hash=%s",('sha256:'+'b'*64,))
        else:
            payload = {'kind':'configure','configurationTarget':args['configuration_target']}
            payload['configurationTarget']['configRef']['revision'] = 2
            conn.execute('UPDATE extension_runtime_event SET payload=%s,payload_hash=%s',(Jsonb(payload),_digest(payload)))
    elif corruption in {'request_hash','actor','revision','kind'}:
        field, value = {'request_hash':('request_hash','sha256:'+'b'*64),'actor':('requested_by','other-actor'),
            'revision':('expected_binding_revision',2),'kind':('kind','enable')}[corruption]
        from psycopg import sql
        conn.execute(sql.SQL('UPDATE extension_runtime_operation SET {}=%s WHERE operation_id=%s').format(sql.Identifier(field)),(value,op.operation_id))
    scope = dict(org_id=args['org_id'],project_id=args['project_id'])
    if corruption == 'tenant': scope['org_id']='dev-org'
    if corruption == 'scope': conn.execute("SELECT set_config('aos.org_id','',false)")
    with pytest.raises((RuntimeConflict, LookupError, PermissionError)):
        with conn.transaction():
            load_configure_target(conn,**scope,operation_id=op.operation_id)
