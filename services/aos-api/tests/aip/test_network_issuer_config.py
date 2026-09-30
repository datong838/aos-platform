"""Private files and isolated read-only PG preflight, not business authorization."""
from dataclasses import replace
import json
import os
import pytest
from psycopg import sql

from aos_api.tenant_scope import TenantScope
from aos_api.aip_network_issuer_config import load_issuer_config, preflight_issuer, IssuerConfigBlocked
from tests.aip.test_network_issuer_process import config, consumer_config
from tests.aip.test_network_issuer_timeouts_pg import live_issuer, private_passfile
from tests.aip.test_network_consumer_boundary_pg import isolated_owner, SCOPE


@pytest.fixture
def config_file(config):
    data = dict(schemaVersion=1, socketPath=str(config.socket_path), apiUid=config.api_uid,
        issuerUid=config.issuer_uid, ipcGid=config.ipc_gid,
        database=dict(host=config.database.host, port=config.database.port,
                      database=config.database.database, passfile=str(config.database.passfile)),
        scope=dict(orgId=config.scope.org_id, projectId=config.scope.project_id),
        attemptDirectory=str(config.attempt_directory), maxConnections=1, acceptTimeout=0.2)
    path = config.attempt_directory/'config.json'
    path.write_text(json.dumps(data)); path.chmod(0o600)
    return path, data


def counts():
    with isolated_owner() as conn:
        return tuple(conn.execute(sql.SQL('SELECT count(*) AS n FROM {} WHERE org_id=%s AND project_id=%s').format(
            sql.Identifier(table)), SCOPE.key).fetchone()['n'] for table in
            ('aip_action_proposal', 'aip_action_approval_event', 'aip_network_policy_receipt'))


def test_exact_private_config_without_listener(config_file, config):
    assert load_issuer_config(config_file[0]) == config
    assert not config.socket_path.exists()


@pytest.mark.parametrize('change', [{'schemaVersion': True}, {'password': 'secret-sentinel'},
    {'issuerUid': True}, {'maxConnections': '1'}, {'socketPath': 'relative'},
    {'scope': {'orgId': 'org-org', 'projectId': 'dev-project', 'role': 'owner'}}])
def test_invalid_fields(config_file, change):
    path, data = config_file
    path.write_text(json.dumps({**data, **change}))
    with pytest.raises(IssuerConfigBlocked) as error: load_issuer_config(path)
    assert str(error.value) == 'ISSUER_PRIVATE_CONFIG_INVALID'


def test_file_permissions_fifo_and_duplicate_rejected(config_file):
    path, data = config_file
    path.chmod(0o644)
    with pytest.raises(IssuerConfigBlocked): load_issuer_config(path)
    path.chmod(0o600)
    path.write_text('{"schemaVersion":1,'+json.dumps(data)[1:])
    with pytest.raises(IssuerConfigBlocked): load_issuer_config(path)
    fifo = path.with_name('fifo')
    os.mkfifo(fifo, 0o600)
    with pytest.raises(IssuerConfigBlocked): load_issuer_config(fifo)


def test_real_read_only_preflight_no_business_writes(config, private_passfile):
    before = counts()
    with live_issuer(private_passfile) as database:
        assert preflight_issuer(replace(config, database=database), SCOPE) == {'ready': True, 'businessAuthorized': False}
    assert counts() == before
    assert not config.socket_path.exists()
    assert list(config.attempt_directory.iterdir()) == [config.database.passfile]


def test_scope_and_occupied_path_rejected_before_db(config):
    with pytest.raises(IssuerConfigBlocked): preflight_issuer(config, TenantScope('other-org', 'dev-project'))
    config.socket_path.write_text('retain')
    with pytest.raises(IssuerConfigBlocked): preflight_issuer(config, SCOPE)
    assert config.socket_path.read_text() == 'retain'


def test_disabled_guard_rejected_in_real_pg(config, private_passfile):
    with live_issuer(private_passfile) as database:
        with isolated_owner() as admin:
            admin.execute('ALTER TABLE aip_action_approval_event DISABLE TRIGGER aip_network_approval_event_guard_a0v_118')
            admin.commit()
            try:
                with pytest.raises(IssuerConfigBlocked): preflight_issuer(replace(config, database=database), SCOPE)
            finally:
                admin.execute('ALTER TABLE aip_action_approval_event ENABLE TRIGGER aip_network_approval_event_guard_a0v_118')
                admin.commit()
