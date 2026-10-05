"""Restore gate invariants; mocks here never prove real restoration."""
import importlib.util
from pathlib import Path

import pytest

path = Path(__file__).resolve().parents[1] / 'a0v_current_142_restore_gate.py'
spec = importlib.util.spec_from_file_location('restore142', path)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def target():
    return {'Name': '/aos-daily142-probe', 'State': {'Running': True},
        'Image': 'sha256:local-image', 'Config': {'Labels': {'aos.restore-gate': '20261005-142'}},
        'HostConfig': {'NetworkMode': 'none', 'Privileged': False},
        'NetworkSettings': {'Ports': {'5432/tcp': None}},
        'Mounts': [{'Type': 'volume', 'Name': 'aos-daily142-probe-data',
                    'Destination': '/var/lib/postgresql/data'}]}


@pytest.mark.parametrize('change', ['source_volume', 'bind', 'ports', 'network', 'privileged', 'name', 'image'])
def test_isolated_destination_rejects_boundary_drift(change):
    item = target()
    if change == 'source_volume':
        item['Mounts'][0]['Name'] = 'aos-a0v-recovery-pg-data'
    elif change == 'bind':
        item['Mounts'].append({'Type': 'bind', 'Source': '/Users/ddt', 'Destination': '/host'})
    elif change == 'ports':
        item['NetworkSettings']['Ports']['5432/tcp'] = [{'HostPort': '18435'}]
    elif change == 'network':
        item['HostConfig']['NetworkMode'] = 'default'
    elif change == 'privileged':
        item['HostConfig']['Privileged'] = True
    elif change == 'name':
        item['Name'] = '/aos-a0v-recovery-pg'
    elif change == 'image':
        item['Image'] = 'sha256:other'
    with pytest.raises(gate.RestoreGateBlocked):
        gate.validate_destination(item, container='aos-daily142-probe',
            volume='aos-daily142-probe-data', image='sha256:local-image')


def test_restore_rejects_old_row_change_even_with_same_count():
    original = {'tables': {'history': {'count': 1, 'sha256': 'a'}}, 'metadata': {}}
    changed = {'tables': {'history': {'count': 1, 'sha256': 'b'}}, 'metadata': {}}
    with pytest.raises(gate.RestoreGateBlocked):
        gate.require_old_rows(original, changed)


def test_restore_rejects_missing_old_table():
    with pytest.raises(gate.RestoreGateBlocked):
        gate.require_old_rows({'tables': {'history': {'count': 0, 'sha256': 'a'}}, 'metadata': {}},
                              {'tables': {}, 'metadata': {}})


def test_metadata_only_allows_exact_two_additions_and_no_old_change():
    original = {'tables': {'meta_object_type': {'count': 1}},
                'metadata': {'meta_object_type': {'old': 'a'}}}
    for rows in ({'old': 'b', 'SourceLicenseRequest': 'new'},
                 {'old': 'a', 'SourceLicenseRequest': 'new', 'extra': 'new'}):
        with pytest.raises(gate.RestoreGateBlocked):
            gate.require_old_rows(original, {'tables': {'meta_object_type': {'count': len(rows)}},
                                            'metadata': {'meta_object_type': rows}})


def test_private_journal_never_overwrites(tmp_path):
    path = tmp_path / 'intent.json'
    gate.save(path, {'once': True})
    with pytest.raises(FileExistsError):
        gate.save(path, {'once': False})
    assert path.stat().st_mode & 0o777 == 0o600


def test_globals_preserves_original_grantor_and_only_skips_existing_bootstrap_create():
    data = b'CREATE ROLE aos_app;\nALTER ROLE aos_app WITH SUPERUSER;\nCREATE ROLE worker;\nGRANT worker TO issuer GRANTED BY aos_app;\n'
    restored = gate.prepare_globals(data, bootstrap='aos_app')
    assert restored == data.replace(b'CREATE ROLE aos_app;\n', b'', 1)


@pytest.mark.parametrize('data,bootstrap', [
    (b'CREATE ROLE worker;\n', 'aos_app'),
    (b'CREATE ROLE aos_app;\nCREATE ROLE aos_app;\n', 'aos_app'),
    (b'CREATE ROLE aos_app;\n', 'postgres'),
])
def test_globals_rejects_unproven_bootstrap(data, bootstrap):
    with pytest.raises(gate.RestoreGateBlocked):
        gate.prepare_globals(data, bootstrap=bootstrap)


def test_catalog_rejects_database_connect_privilege_widening():
    before = {key: [] for key in ('relations', 'acl', 'policies', 'functions', 'function_acl', 'roles', 'memberships')}
    before.update(sequences={}, database_permissions=[{'role': 'aos_runtime', 'connect': False}],
                  database_properties={}, database_settings=[])
    after = {**before, 'database_permissions': [{'role': 'aos_runtime', 'connect': True}]}
    with pytest.raises(gate.RestoreGateBlocked):
        gate.require_catalog_preserved(before, after)


def test_catalog_rejects_database_acl_grant_option_change():
    before = {key: [] for key in ('relations', 'acl', 'policies', 'functions', 'function_acl', 'roles', 'memberships')}
    before.update(sequences={}, database_permissions=[], database_settings=[],
                  database_properties={'acl': [{'grantee': 'reader', 'privilege_type': 'CONNECT', 'is_grantable': False}]})
    after = {**before, 'database_properties': {'acl': [{'grantee': 'reader', 'privilege_type': 'CONNECT', 'is_grantable': True}]}}
    with pytest.raises(gate.RestoreGateBlocked):
        gate.require_catalog_preserved(before, after)
