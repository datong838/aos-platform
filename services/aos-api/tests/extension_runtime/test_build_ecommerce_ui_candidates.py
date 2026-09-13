import importlib
import importlib.util
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
import json

import pytest


@pytest.fixture
def profile(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[4] / 'scripts'))
    return importlib.import_module('build_ecommerce_ui_candidates')


def test_fixed_profile_preserves_base_and_adds_only_read_operation(profile):
    builder = profile.load_builder()
    result = builder.preflight()
    assert result['operationCount'] == 13 and result['moduleCount'] == 8
    assert {x['id']:x['version'] for x in result['bundles']} == {
        'domain.ecommerce.core':'1.3.0','platform.ecommerce.niushop':'1.5.0',
        'solution.ecommerce.growth':'1.8.0','solution.ecommerce.operations-base':'1.2.0'}
    original = importlib.import_module('build_ecommerce_runtime_candidates')
    assert original.EXPECTED_RUNTIME_OPERATION_COUNT == 12
    assert original.preflight()['operationCount'] == 12


def test_fixture_drift_refused_before_qualification(profile, monkeypatch):
    monkeypatch.setattr(profile,'FIXTURE_HASH','bad')
    with pytest.raises(RuntimeError,match='fixture drifted'):
        profile.load_builder()


@pytest.mark.parametrize('bad',[False,True])
def test_probe_after_heartbeats_in_same_session_and_always_cleanup(profile, monkeypatch, tmp_path, bad):
    from aos_api.extension_runtime import session_supervisor
    builder = profile.load_builder()
    fixture = json.loads(profile.FIXTURE.read_bytes())
    events = []
    class Session:
        async def check_health(self):
            events.append('heartbeat')
        async def invoke(self,method,payload):
            assert events.count('heartbeat') == 2048
            assert method == profile.METHOD and payload == fixture['payload']
            events.append('invoke')
            return {} if bad else fixture['expected']
    @asynccontextmanager
    async def opened(*args,**kwargs):
        try:
            yield Session()
        finally:
            events.append('released')
    monkeypatch.setattr(session_supervisor,'open_session',opened)
    args = dict(driver=SimpleNamespace(context='isolated'),image_id='sha256:'+'a'*64,
        contributions=[dict(kind='api',operationId=profile.METHOD,method='POST',path='/read',mode='exclusive')],
        journal_root=tmp_path)
    if bad:
        with pytest.raises(RuntimeError,match='projection differs'):
            builder._qualify_session(**args)
    else:
        result = builder._qualify_session(**args)
        assert result['readProbe']['caseCount'] == 1 and result['cleanup'] == 'released'
        assert result['readProbe']['executionAllowed'] is False
    assert events[-2:] == ['invoke','released']
    states = [json.loads(line)['state'] for line in next(tmp_path.glob('*.jsonl')).read_text().splitlines()]
    assert states[-1] == ('failed_requires_observation' if bad else 'released')
