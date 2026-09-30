"""Private file and actual read-only PG preflight, not business authorization."""
from dataclasses import replace
import json
import os
import pytest
from aos_api.aip_network_consumer_config import load_consumer_config, preflight_consumer, ConsumerConfigBlocked
from tests.aip.test_network_consumer_process import config
from tests.aip.test_network_consumer_connection_pg import private_passfile, live_test_config
from tests.aip.test_network_consumer_boundary_pg import isolated_owner, SCOPE


@pytest.fixture
def config_file(config):
    data = {'schemaVersion': 1, 'socketPath': str(config.socket_path),
            'apiUid': config.api_uid, 'consumerUid': config.consumer_uid, 'ipcGid': config.ipc_gid,
            'database': {'host': config.database.host, 'port': config.database.port,
                         'database': config.database.database, 'passfile': str(config.database.passfile)},
            'attemptDirectory': str(config.attempt_directory), 'maxConnections': 1, 'acceptTimeout': 0.2}
    path = config.attempt_directory / 'config.json'
    path.write_text(json.dumps(data))
    path.chmod(0o600)
    return path, data


def test_private_exact_config_loads_without_opening_listener(config_file, config):
    path, _ = config_file
    assert load_consumer_config(path) == config
    assert not config.socket_path.exists()


@pytest.mark.parametrize('changes', [{'schemaVersion': True}, {'password': 'secret-sentinel'},
    {'maxConnections': '1'}, {'consumerUid': True}, {'socketPath': 'relative'}, {'acceptTimeout': float('nan')}])
def test_untrusted_fields_rejected_and_redacted(config_file, changes):
    path, data = config_file
    path.write_text(json.dumps({**data, **changes}))
    with pytest.raises(ConsumerConfigBlocked) as error:
        load_consumer_config(path)
    assert 'secret-sentinel' not in str(error.value)


def test_duplicate_keys_rejected(config_file):
    path, data = config_file
    path.write_text('{"schemaVersion":1,' + json.dumps(data)[1:])
    with pytest.raises(ConsumerConfigBlocked):
        load_consumer_config(path)


def test_named_pipe_is_rejected_without_waiting_for_writer(config_file):
    path, _ = config_file
    fifo = path.with_name('input.fifo')
    os.mkfifo(fifo, 0o600)
    with pytest.raises(ConsumerConfigBlocked):
        load_consumer_config(fifo)


def test_file_and_parent_permissions_symlink_and_size_rejected(config_file):
    path, _ = config_file
    link = path.with_name('link.json')
    link.symlink_to(path)
    with pytest.raises(ConsumerConfigBlocked):
        load_consumer_config(link)
    path.chmod(0o644)
    with pytest.raises(ConsumerConfigBlocked):
        load_consumer_config(path)
    path.chmod(0o600)
    path.parent.chmod(0o750)
    with pytest.raises(ConsumerConfigBlocked):
        load_consumer_config(path)
    path.parent.chmod(0o700)
    path.write_bytes(b'x'*16385)
    with pytest.raises(ConsumerConfigBlocked):
        load_consumer_config(path)


def count_receipts():
    with isolated_owner() as conn:
        return conn.execute('SELECT count(*) AS n FROM aip_network_policy_receipt WHERE org_id=%s AND project_id=%s',
                            SCOPE.key).fetchone()['n']


def test_real_read_only_preflight_has_no_listener_or_receipt(config, private_passfile):
    before = count_receipts()
    with live_test_config(private_passfile) as database:
        actual = replace(config, database=database)
        assert preflight_consumer(actual, SCOPE) == {'ready': True, 'businessAuthorized': False}
    assert count_receipts() == before
    assert not config.socket_path.exists()
    assert list(config.attempt_directory.iterdir()) == [config.database.passfile]


def test_preflight_rejects_os_identity_and_occupied_path(config):
    bad = replace(config, consumer_uid=os.geteuid()+2)
    with pytest.raises(ConsumerConfigBlocked):
        preflight_consumer(bad, SCOPE)
    config.socket_path.write_text('retain')
    with pytest.raises(ConsumerConfigBlocked):
        preflight_consumer(config, SCOPE)
    assert config.socket_path.read_text() == 'retain'


def test_preflight_rejects_untyped_scope_before_connection(config):
    with pytest.raises(ConsumerConfigBlocked, match='CONSUMER_READ_ONLY_PREFLIGHT_BLOCKED'):
        preflight_consumer(config, {'org_id': 'org-org', 'project_id': 'dev-project'})
    assert not config.socket_path.exists()


@pytest.mark.parametrize('kind,arguments', [('claim', 'text,text,text,uuid'), ('finish', 'text,text,text,text,uuid')])
@pytest.mark.parametrize('drift', ['missing', 'invoker', 'public'])
def test_delivery_function_drift_blocks_readiness_without_effect(config, private_passfile, kind, arguments, drift):
    name = f'aip_{kind}_network_delivery_a0v_123'
    signature = f'public.{name}({arguments})'
    if drift == 'missing':
        apply = f'ALTER FUNCTION {signature} RENAME TO bg00fk_hidden_{kind}'
        restore = f'ALTER FUNCTION public.bg00fk_hidden_{kind}({arguments}) RENAME TO {name}'
    elif drift == 'invoker':
        apply = f'ALTER FUNCTION {signature} SECURITY INVOKER'
        restore = f'ALTER FUNCTION {signature} SECURITY DEFINER'
    else:
        apply = f'GRANT EXECUTE ON FUNCTION {signature} TO PUBLIC'
        restore = f'REVOKE EXECUTE ON FUNCTION {signature} FROM PUBLIC'
    before = count_receipts()
    with isolated_owner() as conn:
        conn.execute(apply)
    try:
        with live_test_config(private_passfile) as database:
            with pytest.raises(ConsumerConfigBlocked, match='CONSUMER_READ_ONLY_PREFLIGHT_BLOCKED'):
                preflight_consumer(replace(config, database=database), SCOPE)
        assert not config.socket_path.exists()
        assert count_receipts() == before
    finally:
        with isolated_owner() as conn:
            conn.execute(restore)
