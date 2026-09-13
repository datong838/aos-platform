"""Reboot recovery refuses stale targets and never replaces a command intent."""
import importlib.util
from pathlib import Path
from copy import deepcopy
import pytest

spec = importlib.util.spec_from_file_location('reboot_guard', Path(__file__).resolve().parents[4] / 'scripts/a0v_qyh_reboot_recovery.py')
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)


def snapshot():
    return dict(head=dict(state='active', etag_version=5, installation_id=recovery.PARENT['installationId']),
        bindings=[dict(generation=recovery.GENERATION, revision=5, execution_epoch=4,
            enabled=False, operation_fence=True, observed_state='unknown')],
        resources=[dict(cleanup_state='released', observed_release=True) for _ in range(3)],
        operations=[dict(status='succeeded')], businessRoutes=0,
        schedules=[dict(enabled=False, unstopped=0)])


def test_fresh_and_formally_drained_targets():
    value = snapshot()
    recovery.validate_parent(value)
    with pytest.raises(ValueError): recovery.validate_parent(value, drained=True)
    value['bindings'][0].update(revision=7, execution_epoch=5)
    recovery.validate_parent(value, drained=True)
    with pytest.raises(ValueError): recovery.validate_parent(value)


@pytest.mark.parametrize('section,field,value', [
    ('head','installation_id','other'), ('head','etag_version',6), ('head','state','applied'),
    ('bindings','generation','other'), ('bindings','revision',6), ('bindings','execution_epoch',5),
    ('bindings','enabled',True), ('bindings','operation_fence',False), ('bindings','observed_state','ready'),
    ('resources','cleanup_state','pending'), ('resources','observed_release',False),
    ('operations','status','running'), ('schedules','enabled',True), ('schedules','unstopped',1),
])
def test_drift_blocks_recovery(section, field, value):
    target = deepcopy(snapshot())
    row = target[section] if section == 'head' else target[section][0]
    row[field] = value
    with pytest.raises(ValueError): recovery.validate_parent(target)


def test_business_routes_and_missing_resources_block():
    target = snapshot(); target['businessRoutes'] = 1
    with pytest.raises(ValueError): recovery.validate_parent(target)
    target = snapshot(); target['resources'].pop()
    with pytest.raises(ValueError): recovery.validate_parent(target)


def test_existing_intent_cannot_be_overwritten(tmp_path):
    path = tmp_path / 'intent.json'
    recovery.freeze(path, {'target':'original'})
    original = path.read_bytes()
    with pytest.raises(FileExistsError): recovery.freeze(path, {'target':'replacement'})
    assert path.read_bytes() == original
