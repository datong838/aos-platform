from datetime import datetime, timedelta, timezone
from pathlib import Path
import copy
import importlib
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'scripts'))
import a0v_l_natural_product_event as natural


def exact():
    operations = [
        'ecommerce_growth_analysis_advance','ecommerce_growth_case_put',
        'ecommerce_growth_content_generate','ecommerce_growth_content_review',
        'ecommerce_growth_data_fulfill','ecommerce_growth_event_control',
        'ecommerce_growth_investigation_describe','ecommerce_growth_review_advance',
        'ecommerce_growth_schedule_put','ecommerce_growth_schedule_trigger']
    return {'schedule': {'cron': '0 * * * *', 'pipeline_id': 'P02-product-qyh',
        'enabled': False, 'ingest': {'kind':'pipeline-live-v1','pipelineId':'P02-product-qyh'}},
        'policy': {'current_revision': 8, 'enabled': False},
        'binding': {'policy_revision': 8, 'installation_id': natural.current.L_ID,
            'generation': natural.current.L_GENERATION, 'execution_epoch': 3,
            'approved': True, 'enabled': True, 'revision': 1,
            'effective_until': datetime.now(timezone.utc) + timedelta(hours=1)},
        'routes': [{'operation_id': op, 'handler_kind':'extension',
            'installation_id':natural.current.L_ID,'generation':natural.current.L_GENERATION,
            'execution_epoch':3,'operation_fence':False,'cutover_group_revision':37}
            for op in operations], 'expectedOperations': operations,
        'inflight': {'running':0,'unresolved':0}, 'negativeCanaryDispatch':0,
        'runs': [], 'ingress': []}


@pytest.mark.parametrize('path,value', [
    (('schedule','cron'), '5 * * * *'), (('policy','enabled'), True),
    (('binding','generation'), 'bad'), (('routes',0,'cutover_group_revision'), 36),
    (('inflight','running'), 1), (('negativeCanaryDispatch',), 1),
])
def test_natural_window_drift_fails_closed(path, value):
    state = copy.deepcopy(exact())
    target = state
    for key in path[:-1]: target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValueError): natural.validate_ready(state)


def test_exact_natural_window_is_ready():
    state = exact()
    assert natural.validate_ready(state) is state


def test_observation_allows_visible_inflight_but_arm_does_not():
    state = exact()
    state['inflight']['running'] = 1
    assert natural.validate_ready(state, require_drained=False) is state
    with pytest.raises(ValueError): natural.validate_ready(state)


def test_natural_executor_has_no_manual_run_call():
    source = Path(natural.__file__).read_text()
    assert f'/v1/schedules/{{SCHEDULE}}/run' not in source
    assert "'manualRunAllowed': False" in source


def test_natural_api_adds_cron_without_losing_snapshot_worker(monkeypatch):
    launcher_module = importlib.import_module('a0v_l_natural_api')
    launcher = SimpleNamespace(API_FLAGS={
        'AOS_SNAPSHOT_GROUP_WORKER_ENABLED': 'true',
        'AOS_SNAPSHOT_GROUP_WORKER_TOPOLOGY': 'independent',
        'AOS_EXTENSION_RUNTIME_HOST_ENABLED': 'false',
    })
    monkeypatch.setattr(launcher_module, 'ORIGINAL_LAUNCHER', lambda: launcher)

    loaded = launcher_module.load_launcher()

    assert loaded is launcher
    assert loaded.API_FLAGS == {
        'AOS_SNAPSHOT_GROUP_WORKER_ENABLED': 'true',
        'AOS_SNAPSHOT_GROUP_WORKER_TOPOLOGY': 'independent',
        'AOS_EXTENSION_RUNTIME_HOST_ENABLED': 'false',
        'AOS_QYH_CRON_ENABLED': 'true',
    }
