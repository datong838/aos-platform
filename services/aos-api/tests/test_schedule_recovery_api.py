from unittest.mock import Mock
from uuid import uuid4
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from aos_api.auth import Principal, require_principal
from aos_api.routers import wave_ext
from aos_api import qyh_cron_scheduler
from aos_api.ec_ingress_journal import IngressJournalConflict
from aos_api.errors import ApiError


@pytest.fixture
def api(monkeypatch):
    app=FastAPI()
    from fastapi.responses import JSONResponse
    @app.exception_handler(ApiError)
    async def error_handler(request,exc):
        return JSONResponse(status_code=exc.status_code,content={'code':exc.code,'message':exc.message})
    principal=Principal('tester','org-org','dev-project',roles=['data-owner'])
    app.dependency_overrides[require_principal]=lambda:principal
    app.include_router(wave_ext.router)
    execute=Mock(return_value={'id':'original','status':'succeeded'})
    monkeypatch.setattr(qyh_cron_scheduler,'execute_schedule',execute)
    return TestClient(app),principal,execute


def test_recovery_uses_principal_scope_and_original_run(api):
    client,principal,execute=api
    claim=str(uuid4())
    response=client.post('/v1/schedules/s/runs/original/recover',json={'claimId':claim})
    assert response.status_code==200
    assert execute.call_args.args[0].key==('org-org','dev-project')
    assert execute.call_args.args[1]=='s'
    assert execute.call_args.kwargs=={'trigger':'recovery','recovery_run_id':'original','recovery_claim_id':claim,'control_factory':None}


def test_viewer_cannot_start_recovery(api):
    client,principal,execute=api;principal.roles=['viewer']
    assert client.post('/v1/schedules/s/runs/original/recover',json={'claimId':str(uuid4())}).status_code==403
    execute.assert_not_called()


@pytest.mark.parametrize('body',[{'claimId':'bad'},{'claimId':str(uuid4()),'orgId':'other'},{}])
def test_invalid_recovery_body_has_no_effect(api,body):
    client,_,execute=api
    assert client.post('/v1/schedules/s/runs/original/recover',json=body).status_code==422
    execute.assert_not_called()


@pytest.mark.parametrize('error,status',[(IngressJournalConflict('private detail'),409),(RuntimeError('private detail'),503),(KeyError('private detail'),404)])
def test_errors_are_safe_and_not_success(api,error,status):
    client,_,execute=api;execute.side_effect=error
    response=client.post('/v1/schedules/s/runs/original/recover',json={'claimId':str(uuid4())})
    assert response.status_code==status
    assert 'private detail' not in response.text


def test_duplicate_recovery_is_not_reported_as_new_success(api):
    client,principal,execute=api
    principal.org_id='dev-org'
    execute.return_value={'id':'original','status':'duplicate'}
    response=client.post('/v1/schedules/s/runs/original/recover',json={'claimId':str(uuid4())})
    assert response.status_code==200 and response.json()['status']=='duplicate'
    assert execute.call_args.args[0].key==('dev-org','dev-project')


def test_recovery_passes_only_server_control_factory(api):
    from types import SimpleNamespace
    client, _, execute = api
    factory = object()
    client.app.state.extension_runtime_control_plane = SimpleNamespace(pipeline_control_factory=factory)
    response = client.post('/v1/schedules/s/runs/original/recover',json={'claimId':str(uuid4())})
    assert response.status_code == 200
    assert execute.call_args.kwargs['control_factory'] is factory


def test_manual_passes_same_server_factory(api, monkeypatch):
    from types import SimpleNamespace
    client, _, execute = api
    factory = object()
    client.app.state.extension_runtime_control_plane = SimpleNamespace(pipeline_control_factory=factory)
    monkeypatch.setattr(wave_ext, '_hydrate_data_os_scope', lambda *a: None)
    monkeypatch.setattr(wave_ext, '_persist_safe', lambda *a: None)
    monkeypatch.setitem(wave_ext._schedules, 's', dict(id='s',orgId='org-org',projectId='dev-project',enabled=True))
    response = client.post('/v1/schedules/s/run')
    assert response.status_code == 200
    assert execute.call_args.kwargs['control_factory'] is factory


@pytest.mark.parametrize('error,status', [(PermissionError('private detail'),403),(RuntimeError('private detail'),503)])
def test_manual_control_failures_are_readable_and_safe(api,monkeypatch,error,status):
    client, _, execute = api
    monkeypatch.setattr(wave_ext, '_hydrate_data_os_scope', lambda *a: None)
    monkeypatch.setattr(wave_ext, '_persist_safe', lambda *a: None)
    monkeypatch.setitem(wave_ext._schedules, 's', dict(id='s',orgId='org-org',projectId='dev-project',enabled=True))
    execute.side_effect = error
    response = client.post('/v1/schedules/s/run')
    assert response.status_code == status
    assert 'private detail' not in response.text
