import asyncio
import importlib
import json
import os
from pathlib import Path
import subprocess
import pytest

ROOT=Path(__file__).resolve().parents[4]


@pytest.fixture
def profile(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    return importlib.import_module('build_ecommerce_event_candidates')


def test_exact_candidate_profile_and_preserved_previous(profile):
    result=profile.load_builder().preflight()
    assert result['operationCount']==15
    versions={x['id']:x['version'] for x in result['bundles']}
    assert versions['domain.ecommerce.core']=='1.4.0'
    assert versions['solution.ecommerce.growth']=='1.10.0'
    assert profile.previous_builder().EXPECTED_RUNTIME_OPERATION_COUNT==14


def test_frozen_core_can_execute_without_author_source_imports(profile):
    script="""import json
from ecommerce_core import register,handle
p=json.loads(input())
assert any(c['operationId']=='ecommerce_core_product_event_windows' for c in register(None)['contributions'])
print(json.dumps(handle('ecommerce_core_product_event_windows',p,None)))
"""
    result=subprocess.run([str(ROOT/'services/aos-api/.venv/bin/python'),'-c',script],
        input=json.dumps(profile.PAYLOAD),text=True,capture_output=True,check=True,cwd='/tmp',
        env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONPATH':str(ROOT/'bundles/candidates/ecommerce/domain.ecommerce.core/1.4.0/backend')})
    value=json.loads(result.stdout)
    assert value['requestHash']==profile.digest(profile.PAYLOAD)
    assert value['events'][0]['deadline']=='2026-09-16T00:11:00+00:00'


def test_probe_rejects_registered_but_wrong_computation(profile):
    class Session:
        async def invoke(self,*args):return {'registered':True}
    with pytest.raises(ValueError,match='computation differs'):asyncio.run(profile.probe(Session()))


def test_qualification_routes_mixed_ui_contributions_without_api_fields(profile,monkeypatch):
    from types import SimpleNamespace
    builder=profile.previous_builder()
    calls=[]
    builder._qualify_session=lambda **kwargs:calls.append(kwargs) or {'ok':True}
    monkeypatch.setattr(profile,'previous_builder',lambda:builder)
    current=profile.load_builder()
    claims=[SimpleNamespace(kind='navigation'),SimpleNamespace(kind='api',operation_id='analyst_workspace_view_v1')]
    assert current._qualify_session(contributions=claims)=={'ok':True}
    assert 'probe' not in calls[0]
    current._qualify_session(contributions=[SimpleNamespace(kind='api',operation_id=profile.METHOD)])
    assert calls[1]['probe'] is profile.probe
