import copy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'scripts'))
import a0v_l_successor_cutover_verify as verify


def exact():
    operations = sorted(verify.ECOMMERCE_GROWTH_OPERATIONS)
    return {
        'installation': {'head': {'installation_id': verify.successor.L_ID, 'etag_version': 5,
            'state': 'active', 'lock_hash': verify.successor.LOCK},
            'bindings': [{'generation': verify.successor.L_GENERATION, 'revision': 6,
                'execution_epoch': 3, 'enabled': True, 'operation_fence': False,
                'desired_state': 'enabled', 'observed_state': 'ready',
                'config_ref': verify.successor.CONFIG}],
            'resources': [{'cleanup_state': 'pending', 'observed_release': False}] * 3,
            'operations': [{'status': 'succeeded'}] * 4, 'canaryInstallations': 0},
        'database': {'version': [{'version_num': 'a0v_073'}],
            'routes': [{'operation_id': op, 'handler_kind': 'extension',
                'installation_id': verify.successor.L_ID,
                'generation': verify.successor.L_GENERATION, 'execution_epoch': 3,
                'operation_fence': False, 'revision': 21, 'cutover_group_revision': 36}
                for op in operations], 'inflight': {'running': 0, 'unresolved': 0},
            'sourceSchedule': [{'id': 'sch-p02-qyh-controlled-20260913-v1', 'enabled': False}],
            'scheduleBindings': [{'enabled': False}], 'policyHeads': [{'enabled': False}],
            'postCutoverRuns': 0, 'negativeCanaryInstallations': 0},
        'cutoverHistory': {'observedStatus': 'resumed', 'rollbacks': [],
            'activationReceipts': {key: {} for key in ('prepare','pause','commit','validate','resume')}},
        'registration': {'receipt': {'receiptId': verify.cutover.RECEIPT,
            'contentHash': verify.cutover.RECEIPT_HASH}},
        'runtimeHost': {'businessWorkers': ['product-event', 'analysis-data-requirement'],
            'canaryTenantCount': 0, 'hostId': 'a0v-local-ecommerce-host-20260912',
            'intervalSeconds': 2, 'outcome': 'RUNTIME_HOST_ACTIVE', 'pid': 87185,
            'positiveTenant': 'org-org/dev-project', 'tenantCount': 1},
        'runtimeHostPidAlive': True}


@pytest.mark.parametrize('path,value', [
    (('installation','bindings',0,'revision'), 5),
    (('database','routes',0,'handler_kind'), 'legacy'),
    (('database','inflight','running'), 1),
    (('database','sourceSchedule',0,'enabled'), True),
    (('database','postCutoverRuns'), 1),
    (('cutoverHistory','observedStatus'), 'validated'),
    (('runtimeHostPidAlive',), False),
])
def test_final_state_drift_fails_closed(path, value):
    state = copy.deepcopy(exact())
    target = state
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValueError):
        verify.validate(state)


def test_exact_final_state_is_accepted():
    assert verify.validate(exact()) == exact()
