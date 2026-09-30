"""Real subprocess entry, private files and isolated PG; not formal deployment."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from tests.aip.test_network_consumer_process import config
from tests.aip.test_network_consumer_config import config_file, count_receipts
from tests.aip.test_network_consumer_connection_pg import private_passfile, live_test_config


def invoke(*args):
    env = os.environ.copy()
    env['PYTHONPATH'] = str(Path(__file__).resolve().parents[2])
    return subprocess.run([sys.executable, '-m', 'aos_api.aip_network_consumer_cli', *args],
                          capture_output=True, text=True, env=env, timeout=20)


def arguments(path, mode='check'):
    return ['--mode', mode, '--config', str(path), '--preflight-org', 'org-org',
            '--preflight-project', 'dev-project']


def test_package_import_does_not_load_web_app():
    env = {**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[2])}
    result = subprocess.run([sys.executable, '-c',
        "import aos_api, aos_api.aip_network_consumer_cli, aos_api.aip_network_consumer_config, sys; "
        "assert 'aos_api.main' not in sys.modules"],
        env=env, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr


def test_existing_app_exports_are_compatible():
    from aos_api import app, create_app
    from aos_api.main import app as actual_app, create_app as actual_factory
    assert app is actual_app
    assert create_app is actual_factory


def test_help_is_explicit_and_no_default_start():
    result = invoke('--help')
    assert result.returncode == 0
    assert 'check' in result.stdout and 'serve' in result.stdout


@pytest.mark.parametrize('args', [[], ['--password', 'secret-sentinel'],
    ['--mode', 'secret-sentinel'], ['--mo', 'check']])
def test_bad_arguments_are_redacted(args):
    result = invoke(*args)
    assert result.returncode == 2
    assert result.stdout == ''
    assert result.stderr.strip() == 'CONSUMER_ENTRY_ARGUMENTS_INVALID'


def test_duplicate_option_rejected(config_file):
    path, _ = config_file
    result = invoke(*arguments(path), '--mode', 'serve')
    assert result.returncode == 2
    assert result.stderr.strip() == 'CONSUMER_ENTRY_ARGUMENTS_INVALID'


@pytest.mark.parametrize('mode', ['check', 'serve'])
def test_real_entry_readiness_and_bounded_idle(config_file, config, private_passfile, mode):
    path, data = config_file
    before = count_receipts()
    with live_test_config(private_passfile) as database:
        data['database'] = {'host': database.host, 'port': database.port,
                            'database': database.database, 'passfile': str(database.passfile)}
        path.write_text(json.dumps(data))
        result = invoke(*arguments(path, mode))
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload['businessAuthorized'] is False
    assert payload['mode'] == mode
    if mode == 'serve':
        assert payload['accepted'] == payload['processed'] == 0
    else:
        assert payload['ready'] is True
    assert not config.socket_path.exists()
    assert count_receipts() == before
    assert set(config.attempt_directory.iterdir()) == {path, config.database.passfile}


def test_occupied_path_is_preserved_and_redacted(config_file, config):
    path, _ = config_file
    config.socket_path.write_text('retain')
    result = invoke(*arguments(path, 'serve'))
    assert result.returncode == 1
    assert result.stderr.strip() == 'CONSUMER_ENTRY_BLOCKED'
    assert result.stdout == ''
    assert config.socket_path.read_text() == 'retain'
