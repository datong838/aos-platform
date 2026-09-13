"""Only the recorded recovery generation may receive new configuration."""
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'scripts'))
import a0v_qyh_reboot_configuration as recovery


def snapshot():
    return dict(head=dict(installation_id=recovery.INSTALLATION, state='active', etag_version=5),
        bindings=[dict(generation=recovery.GENERATION, revision=1, execution_epoch=1,
            observed_state='ready', enabled=False, operation_fence=True)],
        resources=[dict(cleanup_state='pending', observed_release=False) for _ in range(3)],
        operations=[dict(status='succeeded')], schedules=[], businessRoutes=0)


def test_enable_requires_completed_configuration_phase():
    value = snapshot()
    recovery.validate_candidate(value, 'stage')
    recovery.validate_candidate(value, 'configure')
    with pytest.raises(ValueError): recovery.validate_candidate(value, 'enable')
    value['bindings'][0].update(revision=3, execution_epoch=2, observed_state='unknown')
    recovery.validate_candidate(value, 'enable')
    with pytest.raises(ValueError): recovery.validate_candidate(value, 'configure')


@pytest.mark.parametrize('field,value', [('generation','old-generation'),('revision',True),
    ('execution_epoch',True),('enabled',True),('operation_fence',False),('observed_state','unknown')])
def test_wrong_binding_blocks(field, value):
    target = snapshot(); target['bindings'][0][field] = value
    with pytest.raises(ValueError): recovery.validate_candidate(target, 'stage')


@pytest.mark.parametrize('section', ['head','resources','operations','schedules','businessRoutes'])
def test_unsafe_state_blocks(section):
    target = snapshot()
    if section == 'head': target['head']['installation_id'] = 'old-installation'
    elif section == 'resources': target['resources'][0]['observed_release'] = True
    elif section == 'operations': target['operations'][0]['status'] = 'running'
    elif section == 'schedules': target['schedules'] = [{'enabled':True}]
    else: target['businessRoutes'] = 1
    with pytest.raises(ValueError): recovery.validate_candidate(target, 'stage')
