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
    assert execute.call_args.kwargs=={'trigger':'recovery','recovery_run_id':'original','recovery_claim_id':claim}


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
