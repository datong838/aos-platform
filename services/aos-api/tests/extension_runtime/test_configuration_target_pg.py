"""Configuration request identity, only the opt-in ephemeral database."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from psycopg import sql
from psycopg.rows import dict_row

from test_lifecycle_pg import database, seed, pytestmark
from aos_api.extension_runtime.lifecycle_store import RuntimeOperationStore, RuntimeConflict


def case(conn):
    installation, _ = seed(conn)
    generation = uuid4()
    conn.execute("""INSERT INTO extension_runtime_binding
        (org_id,project_id,installation_id,generation,installation_revision,package_lock_ref,
         profile_ref,desired_state,observed_state)
        VALUES('org-org','dev-project',%s,%s,1,'{}','internal-python-v1','disabled','ready')""",
        (installation, generation))
    conn.execute("SELECT set_config('aos.org_id','org-org',false),set_config('aos.project_id','dev-project',false)")
    return dict(org_id='org-org', project_id='dev-project', installation_id=installation,
        kind='configure', idempotency_key='configure-exact', requested_by='test-actor',
        expected_installation_etag=1, deadline=datetime.now(timezone.utc)+timedelta(minutes=1),
        configuration_target=dict(generation=str(generation), bindingRevision=1,
            configRef=dict(configurationId=str(uuid4()), revision=1, hash='sha256:'+'a'*64)))


@pytest.mark.parametrize('row_factory', [None, dict_row])
def test_configuration_request_is_immutable_exact_and_replayable(database, row_factory):
    conn, role, schema = database
    args = case(conn)
    conn.execute(sql.SQL('SET ROLE {}').format(sql.Identifier(role)))
    original_factory = conn.row_factory
    if row_factory is not None: conn.row_factory = row_factory
    with conn.transaction():
        result = RuntimeOperationStore().accept(conn, **args)
    conn.row_factory = original_factory
    assert conn.execute('SELECT expected_binding_revision FROM extension_runtime_operation WHERE operation_id=%s',
        (result.operation_id,)).fetchone() == (1,)
    payload = conn.execute('SELECT payload FROM extension_runtime_event WHERE operation_id=%s',
        (result.operation_id,)).fetchone()[0]
    assert payload == {'kind':'configure', 'configurationTarget':args['configuration_target']}
    assert conn.execute('SELECT count(*) FROM extension_runtime_outbox').fetchone() == (1,)
    conn.execute('UPDATE extension_runtime_binding SET revision=revision+1')
    conn.execute('UPDATE bundle_installation SET etag_version=2')
    with conn.transaction():
        replay = RuntimeOperationStore().accept(conn, **args)
    assert replay.replayed and replay.operation_id == result.operation_id
    # Acceptance is not permission or activation, and does not invent a config.
    assert conn.execute('SELECT enabled,operation_fence,config_ref,execution_epoch FROM extension_runtime_binding').fetchone() == (False, True, None, 1)


@pytest.mark.parametrize('change', ['generation','bindingRevision','configurationId','revision','hash'])
def test_same_key_with_another_configuration_target_is_rejected(database, change):
    conn, _, _ = database
    args = case(conn)
    with conn.transaction():
        RuntimeOperationStore().accept(conn, **args)
    target = args['configuration_target']
    if change == 'generation': target[change] = str(uuid4())
    elif change == 'bindingRevision': target[change] = 2
    elif change == 'configurationId': target['configRef'][change] = str(uuid4())
    elif change == 'revision': target['configRef'][change] = 2
    else: target['configRef'][change] = 'sha256:'+'b'*64
    with pytest.raises(RuntimeConflict, match='another request'):
        with conn.transaction():
            RuntimeOperationStore().accept(conn, **args)
    assert conn.execute('SELECT count(*) FROM extension_runtime_event').fetchone() == (1,)


@pytest.mark.parametrize('change', ['missing','generation','bindingRevision','bool','secret','hash','extra',
                                   'scope','tenant','expired','rollback','wrong_kind'])
def test_invalid_configuration_request_leaves_no_partial_state(database, change):
    conn, role, _ = database
    args = case(conn)
    target = args['configuration_target']
    if change == 'missing': args.pop('configuration_target')
    elif change == 'generation': target['generation'] = str(uuid4())
    elif change == 'bindingRevision': target['bindingRevision'] = 2
    elif change == 'bool': target['configRef']['revision'] = True
    elif change == 'secret': target['configRef']['secret'] = 'test-forbidden-field'
    elif change == 'hash': target['configRef']['hash'] = 'unverified'
    elif change == 'extra': target['enabled'] = True
    elif change == 'scope': conn.execute("SELECT set_config('aos.org_id','',false)")
    elif change == 'tenant':
        conn.execute("SELECT set_config('aos.org_id','dev-org',false)")
        args['org_id'] = 'dev-org'
    elif change == 'expired': args['deadline'] = datetime.now(timezone.utc)-timedelta(seconds=1)
    elif change == 'wrong_kind': args['kind'] = 'runtime-apply'
    conn.execute(sql.SQL('SET ROLE {}').format(sql.Identifier(role)))
    with pytest.raises((ValueError, LookupError, PermissionError, RuntimeError)):
        with conn.transaction():
            RuntimeOperationStore().accept(conn, **args)
            if change == 'rollback': raise RuntimeError('rollback')
    conn.execute('RESET ROLE')
    assert conn.execute('SELECT count(*) FROM extension_runtime_event').fetchone() == (0,)
    assert conn.execute("SELECT count(*) FROM extension_runtime_operation WHERE kind='configure'").fetchone() == (0,)


@pytest.mark.parametrize('change', ['outer','nested','constructed'])
def test_invalid_model_instances_cannot_bypass_configuration_validation(database, change):
    from aos_api.extension_runtime.configuration_contracts import ConfigureTarget, ConfigurationRef
    conn, _, _ = database
    args = case(conn)
    target = ConfigureTarget.model_validate(args['configuration_target'])
    if change == 'outer': target = target.model_copy(update={'bindingRevision':True})
    elif change == 'nested':
        target = target.model_copy(update={'configRef':target.configRef.model_copy(update={'hash':'invalid'})})
    else:
        target = target.model_copy(update={'configRef':ConfigurationRef.model_construct(configurationId='invalid',revision=1,hash='invalid')})
    args['configuration_target'] = target
    with pytest.raises(ValueError):
        with conn.transaction():
            RuntimeOperationStore().accept(conn, **args)
    assert conn.execute('SELECT count(*) FROM extension_runtime_event').fetchone() == (0,)
