"""Separate source HTTP contracts; fixture principals are not real OIDC evidence."""
from urllib.parse import quote
from copy import deepcopy

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from aos_api.auth import Principal, require_principal
from aos_api.errors import register_exception_handlers
from aos_api.routers import aip_budgets as router
from aos_api.aip_budget_policy_window_review import BudgetPolicyWindowReviewDenied, BudgetPolicyWindowReviewUnavailable
from test_budget_policy_window_review import snapshot, HUMAN

PATH='/v1/aip/budgets/cost-proposals/unit-proposal/policy-window-source'


def app():
    value=FastAPI();register_exception_handlers(value);value.include_router(router.router);return value


def client_case(*,subject=HUMAN,org='org-org',project='dev-project',kind='oidc',error=None,body=None):
    instance=app();calls=[]
    principal=Principal(subject=subject,org_id=org,project_id=project,token_kind=kind)
    class FixtureReader:
        def read(self,observed,proposal_id):
            calls.append((observed,proposal_id))
            if error:raise error('unit-private-error-detail')
            return deepcopy(body if body is not None else snapshot())
    instance.dependency_overrides[require_principal]=lambda:principal
    instance.dependency_overrides[router.get_budget_policy_window_review_reader]=lambda:FixtureReader()
    return TestClient(instance),calls,principal


def test_missing_token_is_genuine_auth_refusal_without_reader_override():
    with TestClient(app()) as client:r=client.get(PATH)
    assert r.status_code==401


def test_typed_source_get_passes_exact_original_principal_and_never_grants_authority():
    client,calls,principal=client_case()
    with client:r=client.get(PATH)
    assert r.status_code==200,r.text
    assert r.headers['cache-control']=='no-store'
    assert calls==[(principal,'unit-proposal')] and calls[0][0] is principal
    value=r.json();assert value['schemaVersion']=='aos.budget-policy-window.review-source/v1'
    assert all(value[k] is False for k in ['approvalVerified','activationEligible','nativeWriteAllowed','runtimeAdmissionAllowed'])
    assert value['nativeParentVerification']=='not-performed'
    assert value['parent']['proposal']['basis']['totalRiskMinor']==100


@pytest.mark.parametrize('values',[{'subject':'other'},{'org':'dev-org'},{'project':'other'},
    {'kind':'dev'},{'kind':'unit-fixture'}])
def test_actor_and_tenant_denied_before_read(values):
    client,calls,_=client_case(**values)
    with client:r=client.get(PATH)
    assert r.status_code==403 and not calls


@pytest.mark.parametrize('suffix',['?x=1','?orgId=org-org','?approvalVerified=true'])
def test_extra_query_denied_before_read(suffix):
    client,calls,_=client_case()
    with client:r=client.get(PATH+suffix)
    assert r.status_code==400 and not calls


@pytest.mark.parametrize('body',[b'{}',b'x',b' '*32])
def test_get_body_denied_before_read(body):
    client,calls,_=client_case()
    with client:r=client.request('GET',PATH,content=body)
    assert r.status_code==400 and not calls


@pytest.mark.parametrize('proposal_id',[' leading','trailing ','bad\x00id','a'*161])
def test_bad_id_not_trimmed_or_accepted_before_read(proposal_id):
    client,calls,_=client_case();path='/v1/aip/budgets/cost-proposals/'+quote(proposal_id,safe='')+'/policy-window-source'
    with client:r=client.get(path)
    assert r.status_code==400 and not calls


@pytest.mark.parametrize('error,status,code',[(BudgetPolicyWindowReviewDenied,403,'BUDGET_POLICY_WINDOW_SOURCE_FORBIDDEN'),
    (BudgetPolicyWindowReviewUnavailable,503,'BUDGET_POLICY_WINDOW_SOURCE_UNAVAILABLE')])
def test_reader_errors_return_fixed_public_error_without_private_detail(error,status,code):
    client,calls,_=client_case(error=error)
    with client:r=client.get(PATH)
    assert r.status_code==status and len(calls)==1
    assert r.json()['code']==code and 'unit-private-error-detail' not in r.text


def test_no_new_write_method_is_registered():
    client,calls,_=client_case()
    with client:r=client.post(PATH,json={'decision':'approved'})
    assert r.status_code==405 and not calls


def test_existing_cost_review_still_calls_original_cost_store(monkeypatch):
    seen=[]
    class ExistingStore:
        def review(self,principal,proposal_id):seen.append((principal,proposal_id));return {'legacy':True}
    monkeypatch.setattr(router,'_COST_PROPOSALS',ExistingStore())
    client,calls,principal=client_case()
    with client:r=client.get('/v1/aip/budgets/cost-proposals/unit-proposal/review')
    assert r.status_code==200 and r.json()=={'legacy':True}
    assert seen==[(principal,'unit-proposal')] and not calls


def test_original_readonly_management_wrapper_still_denies_existing_budget_writes(monkeypatch):
    from pathlib import Path
    import importlib
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[4]/'scripts'))
    ReadOnlyManagementApp=importlib.import_module('a0v_qyh_restored_http').ReadOnlyManagementApp
    fixture,calls,_=client_case()
    with TestClient(ReadOnlyManagementApp(fixture.app)) as client:
        read=client.get(PATH)
        denied=client.post('/v1/aip/budgets',json={'activationEligible':True})
    assert read.status_code==200
    assert denied.status_code==405 and len(calls)==1


def test_response_contract_never_serializes_an_injected_permission_grant():
    bad=snapshot();bad['activationEligible']=True
    fixture,calls,_=client_case(body=bad)
    with TestClient(fixture.app,raise_server_exceptions=False) as client:r=client.get(PATH)
    assert r.status_code==500 and len(calls)==1
    assert 'activationEligible' not in r.text
