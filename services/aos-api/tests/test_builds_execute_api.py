"""Manual execution must not bypass disabled state or retry after uncertainty."""
from __future__ import annotations

import pytest
from aos_api.phase5_pipeline_engine import get_engine
from aos_api.routers import wave_ext
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope('dev-org', 'dev-project')


@pytest.fixture
def configured(client, auth_headers):
    pid = 'manual-execution-contract'
    r = client.post('/v1/pipelines', headers=auth_headers,
                    json={'id': pid, 'sourceId': 'configured-file', 'name': 'Configured pipeline'})
    assert r.status_code == 200
    return pid


def test_missing_pipeline_is_not_executed(client, auth_headers):
    assert client.post('/v1/pipelines/missing-execution-pipeline/execute', headers=auth_headers).status_code == 404


def test_metadata_without_runtime_is_rejected_without_a_build(client, auth_headers, configured):
    r = client.post(f'/v1/pipelines/{configured}/execute', headers=auth_headers, json={'mode':'full'})
    assert r.status_code == 409
    assert r.json()['code'] == 'PIPELINE_EXECUTION_NOT_ENABLED'
    assert wave_ext._pipelines[configured]['lastBuild'] is None


@pytest.mark.parametrize('mode', ['disabled', 'demo'])
def test_non_live_owner_never_calls_executor(client, auth_headers, configured, monkeypatch, mode):
    eng = get_engine()
    eng.create_pipeline(SCOPE, id=configured, name='disabled owner', execution_mode=mode)
    calls=[]
    monkeypatch.setattr(eng, 'execute_pipeline_once', lambda *a, **k: calls.append(1))
    r = client.post(f'/v1/pipelines/{configured}/execute', headers=auth_headers)
    assert r.status_code == 409
    assert calls == []
    assert wave_ext._pipelines[configured]['lastBuild'] is None


def test_cold_saved_graph_stays_disabled_at_execute(client, auth_headers):
    pid='manual-cold-disabled-graph'
    assert client.put(f'/v1/pipelines/{pid}/graph',headers=auth_headers,
                      json={'name':'Cold graph','nodes':[],'edges':[]}).status_code == 200
    get_engine().reset(scope=SCOPE,purge_persisted=False)
    r=client.post(f'/v1/pipelines/{pid}/execute',headers=auth_headers)
    assert r.status_code == 409
    assert r.json()['code']=='PIPELINE_EXECUTION_NOT_ENABLED'


@pytest.mark.parametrize('ok', [True,False])
def test_live_delegate_preserves_result_without_inline_writes(client,auth_headers,configured,monkeypatch,ok):
    eng=get_engine()
    eng.create_pipeline(SCOPE,id=configured,name='Controlled live owner',execution_mode='live')
    calls=[]
    def run(scope,pid):
        calls.append((scope,pid))
        return {'ok':ok,'rows_written':3 if ok else 0,'duration_ms':8,'error_code':'' if ok else 'SOURCE_UNAVAILABLE','error_message':''}
    monkeypatch.setattr(eng,'execute_pipeline_once',run)
    r=client.post(f'/v1/pipelines/{configured}/execute',headers=auth_headers)
    assert r.status_code==200
    assert r.json()['status']==('succeeded' if ok else 'failed')
    assert r.json()['rowsWritten']==(3 if ok else 0)
    assert calls==[(SCOPE,configured)]
    assert wave_ext._pipelines[configured]['lastBuild'] is None


def test_unknown_delegate_result_never_falls_back_or_leaks(client,auth_headers,configured,monkeypatch):
    eng=get_engine()
    eng.create_pipeline(SCOPE,id=configured,name='Controlled live owner',execution_mode='live')
    calls=[]
    def unknown(*args,**kwargs):
        calls.append(1)
        raise RuntimeError('fixture-private-provider-detail')
    monkeypatch.setattr(eng,'execute_pipeline_once',unknown)
    r=client.post(f'/v1/pipelines/{configured}/execute',headers=auth_headers,json={'mode':'full'})
    assert r.status_code==503
    assert r.json()['code']=='PIPELINE_EXECUTION_UNCERTAIN'
    assert 'fixture-private-provider-detail' not in r.text
    assert calls==[1]
    assert wave_ext._pipelines[configured]['lastBuild'] is None


def test_retired_runtime_rejected(client,auth_headers,configured,monkeypatch):
    eng=get_engine()
    eng.create_pipeline(SCOPE,id=configured,name='Controlled live owner',execution_mode='live')
    wave_ext._pipelines[configured]['status']='decommissioned'
    calls=[]
    monkeypatch.setattr(eng,'execute_pipeline_once',lambda *args,**kw:calls.append(1))
    r=client.post(f'/v1/pipelines/{configured}/execute',headers=auth_headers)
    assert r.status_code==409
    assert calls==[]


def test_missing_build_logs_remain_not_found(client,auth_headers):
    assert client.get('/v1/builds/missing-build/logs',headers=auth_headers).status_code==404
