import importlib.util
from pathlib import Path
import pytest


@pytest.fixture
def diagnostic(monkeypatch):
    root = Path(__file__).resolve().parents[4]
    monkeypatch.syspath_prepend(str(root/'scripts'))
    path = root/'scripts/a0v_w5c9d_reboot_safe_host_diagnostic.py'
    spec = importlib.util.spec_from_file_location('w5c9d_diagnostic_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('time_outcome,expected_time', [
    ('STALLED_WAIT_24H', 'WAIT_24H'),
    ('STALLED_ELIGIBLE_REQUIRES_FRESH_AUTHORITY', 'ELIGIBLE_NO_AUTHORITY'),
])
def test_local_quiet_never_grants_closure(diagnostic, time_outcome, expected_time):
    baseline = {'outcome': time_outcome, 'automaticAction': False,
                'groupId': 'original', 'attemptId': 'original-attempt'}
    managed = {'outcome': 'MANAGED_HOST_DIRECTORY_READ_ONLY_GREEN_INCOMPLETE_TOPOLOGY',
               'automaticAction': False, 'closureAuthorized': False,
               'runningOriginalRuns': 12, 'releasedResourceLeases': 3}
    result = diagnostic.classify(baseline, managed, [])
    assert result['outcome'] == 'LOCAL_QUIET_NO_GLOBAL_AUTHORITY'
    assert result['timeGate'] == expected_time
    assert result['knownLocalHostCount'] == 0
    assert result['runningOriginalRuns'] == 12
    assert result['automaticAction'] is False
    assert result['closureAuthorized'] is False
    assert result['topologyComplete'] is False


@pytest.mark.parametrize('baseline,managed,pids', [
    ({'outcome': 'FROZEN_FEASIBILITY_BOUNDARY', 'automaticAction': False},
     {'outcome': 'MANAGED_HOST_DIRECTORY_READ_ONLY_GREEN_INCOMPLETE_TOPOLOGY'}, []),
    ({'outcome': 'STALLED_WAIT_24H', 'automaticAction': False},
     {'outcome': 'FROZEN_HOST_DIRECTORY_AUTHORITY'}, []),
    ({'outcome': 'STALLED_WAIT_24H', 'automaticAction': False},
     {'outcome': 'MANAGED_HOST_DIRECTORY_READ_ONLY_GREEN_INCOMPLETE_TOPOLOGY',
      'automaticAction': False, 'closureAuthorized': False,
      'runningOriginalRuns': 12, 'releasedResourceLeases': 3}, [123]),
    ({'outcome': 'STALLED_WAIT_24H', 'automaticAction': True},
     {'outcome': 'MANAGED_HOST_DIRECTORY_READ_ONLY_GREEN_INCOMPLETE_TOPOLOGY',
      'automaticAction': False, 'closureAuthorized': False,
      'runningOriginalRuns': 12, 'releasedResourceLeases': 3}, []),
])
def test_drift_is_frozen_and_never_grants(diagnostic, baseline, managed, pids):
    result = diagnostic.classify(baseline, managed, pids)
    assert result['outcome'] == 'FROZEN_LOCAL_HOST_DIAGNOSTIC'
    assert result['automaticAction'] is False
    assert result['closureAuthorized'] is False
    assert result['topologyComplete'] is False
