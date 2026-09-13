import importlib
import json
from pathlib import Path

import pytest


@pytest.fixture
def successor(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[4] / 'scripts'))
    return importlib.import_module('a0v_ecommerce_ui_signed_successor').load_successor()


def document():
    profile = importlib.import_module('build_ecommerce_ui_candidates')
    fixture = json.loads(profile.FIXTURE.read_bytes())
    sessions = {key:dict(registration='exact',heartbeat='alive',cleanup='released',contributionCount=count,heartbeatChecks=2048)
        for key,count in [('domain.ecommerce.core',1),('platform.ecommerce.niushop',2),('solution.ecommerce.growth',24)]}
    sessions['solution.ecommerce.growth']['readProbe'] = dict(method=profile.METHOD,
        fixtureHash='sha256:'+profile.FIXTURE_HASH,payloadHash=profile._hash(fixture['payload']),
        resultHash=profile._hash(fixture['expected']),caseCount=1,runCount=1,executionAllowed=False,evidence='qualification-fixture-only')
    return dict(runtimeSessions=sessions)


def test_fixed_signing_profile_preserves_current_members(successor):
    assert successor.EXPECTED_OLD_COUNT == 13 and successor.EXPECTED_NEW_COUNT == 14
    assert successor.VERSIONS['solution.ecommerce.growth'] == '1.8.0'
    assert successor.VERSIONS['platform.ecommerce.niushop'] == '1.5.0'
    assert 'niushop-1.5' in str(successor.OLD_ROOT)
    assert successor.NEW_ROOT != successor.OLD_ROOT
    assert successor.legacy()._builder().preflight()['operationCount'] == 13
    successor.require_sessions(document())


@pytest.mark.parametrize('drift',['missing-probe','result','cleanup','count','boolean'])
def test_incomplete_or_nonexact_actual_probe_rejected(successor,drift):
    value=document();session=value['runtimeSessions']['solution.ecommerce.growth']
    if drift=='missing-probe':session.pop('readProbe')
    if drift=='result':session['readProbe']['resultHash']='sha256:'+'0'*64
    if drift=='cleanup':session['cleanup']='unknown'
    if drift=='count':session['contributionCount']=23
    if drift=='boolean':session['readProbe']['executionAllowed']=0
    with pytest.raises(ValueError):successor.require_sessions(value)
