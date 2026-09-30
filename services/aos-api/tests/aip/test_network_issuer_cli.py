"""Real CLI subprocess, temporary PG and idle listener; not deployed business proof."""
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest

from tests.aip.test_network_issuer_config import config_file, config, consumer_config, counts
from tests.aip.test_network_issuer_timeouts_pg import live_issuer, private_passfile


def invoke(*args):
    env = {**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[2])}
    return subprocess.run([sys.executable, '-m', 'aos_api.aip_network_issuer_cli', *args],
                          env=env, capture_output=True, text=True, timeout=20)


def arguments(path, mode='check'):
    return ['--mode', mode, '--config', str(path), '--preflight-org', 'org-org', '--preflight-project', 'dev-project']


def test_import_does_not_load_main():
    env = {**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[2])}
    result = subprocess.run([sys.executable, '-c',
        "import aos_api.aip_network_issuer_cli, aos_api.aip_network_issuer_config, sys; assert 'aos_api.main' not in sys.modules"],
        env=env, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('args', [[], ['--password', 'secret-sentinel'], ['--mode', 'secret-sentinel'], ['--mo', 'check']])
def test_arguments_are_required_and_redacted(args):
    result = invoke(*args)
    assert result.returncode == 2
    assert result.stdout == '' and result.stderr.strip() == 'ISSUER_ENTRY_ARGUMENTS_INVALID'


def test_duplicate_option_rejected(config_file):
    result = invoke(*arguments(config_file[0]), '--mode', 'serve')
    assert result.returncode == 2 and result.stderr.strip() == 'ISSUER_ENTRY_ARGUMENTS_INVALID'


@pytest.mark.parametrize('mode', ['check', 'serve'])
def test_real_child_readiness_and_idle_no_effect(config_file, config, private_passfile, mode):
    path, data = config_file
    before = counts()
    with live_issuer(private_passfile) as database:
        data['database'] = dict(host=database.host, port=database.port, database=database.database, passfile=str(database.passfile))
        path.write_text(json.dumps(data))
        result = invoke(*arguments(path, mode))
    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response['mode'] == mode and response['businessAuthorized'] is False
    if mode == 'check': assert response['ready'] is True
    else: assert response['accepted'] == response['processed'] == 0
    assert not config.socket_path.exists()
    assert counts() == before
    assert set(config.attempt_directory.iterdir()) == {path, config.database.passfile}


def test_scope_mismatch_and_occupied_socket_redacted(config_file, config):
    args = arguments(config_file[0]); args[-1] = 'other-project'
    result = invoke(*args)
    assert result.returncode == 1 and result.stderr.strip() == 'ISSUER_ENTRY_BLOCKED'
    config.socket_path.write_text('retain')
    result = invoke(*arguments(config_file[0], 'serve'))
    assert result.returncode == 1 and result.stdout == ''
    assert config.socket_path.read_text() == 'retain'
