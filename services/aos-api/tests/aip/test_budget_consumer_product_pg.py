"""Real isolated HTTP/PG/JWT; transport substitution is not cross-UID proof."""
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
import json
import os

import pytest
from aos_api import aip_budget_consumer_product as product
from aos_api.aip_budget_consumer_client import BudgetConsumerEndpoint
from aos_api.aip_budget_consumer_process import dispatch_consumer_request
from aos_api.aip_budget_cost_issuer import BudgetCostIssuer
from tests.aip.test_budget_consumer_process import config as consumer_config
from tests.aip.test_budget_consumer_connection_pg import configured
from tests.aip.test_budget_cost_consumer_pg import approved, counts
from tests.aip.test_budget_cost_issuer_pg import issuer_factory, command
from tests.aip.test_network_consumer_connection_pg import private_passfile
from tests.aip.test_network_consumer_signed_https_pg import https_signer
from tests.aip.test_network_consumer_boundary_pg import SCOPE
from tests.aip.test_budget_preview_inquiry_pg import http_client


@pytest.fixture
def setup(consumer_config, issuer_factory, https_signer, tmp_path, monkeypatch):
    maker, checker, p, saved, decision = approved(issuer_factory, https_signer)
    directory = tmp_path/'consumer-api'; directory.mkdir(mode=0o700)
    config = product.BudgetConsumerProductConfig(BudgetConsumerEndpoint(consumer_config.socket_path,
        os.geteuid(), os.geteuid()+1, os.getegid()), directory)
    calls = []
    def transport(endpoint, method, request):
        calls.append((method, request.request_hash))
        return dispatch_consumer_request(consumer_config, method, request)
    monkeypatch.setattr(product, 'request_consumer', transport)
    body = product.BudgetConsumptionRequest(proposalHash=saved['proposalHash'], decisionId=decision['decisionId'])
    return config, maker, checker, p, saved, body, 'Bearer '+https_signer[0](maker.subject), calls, transport


def call(setup, body=True):
    config, maker, _, _, saved, request, auth, _, _ = setup
    return product.budget_consumption_request(config, saved['proposalId'], request if body else None, maker, auth)


def test_repeat_refresh_no_token_and_http(setup, monkeypatch, http_client):
    config, _, _, p, saved, body, auth, calls, _ = setup
    path = config.request_directory/'api.json'
    path.write_text(json.dumps(dict(schemaVersion=1, socketPath=str(config.endpoint.socket_path),
        apiUid=config.endpoint.api_uid, consumerUid=config.endpoint.consumer_uid, ipcGid=config.endpoint.ipc_gid,
        requestDirectory=str(config.request_directory))))
    path.chmod(0o600)
    monkeypatch.setenv('AOS_BUDGET_CONSUMER_API_CONFIG', str(path))
    url=f"/v1/aip/budgets/cost-proposals/{saved['proposalId']}/consumption-request"
    headers={'Authorization':auth,'X-Org-Id':SCOPE.org_id,'X-Project-Id':SCOPE.project_id}
    initial=http_client.get(url,headers=headers)
    assert initial.status_code==200 and initial.json()=={'status':'not_attempted'}
    response=http_client.post(url,headers=headers,json=body.model_dump(mode='json',by_alias=True))
    assert response.status_code==200, response.text
    assert response.json()['status']=='observed' and response.json()['activationEligible'] is False
    for recovered in (http_client.get(url,headers=headers),http_client.post(url,headers=headers,json=body.model_dump(mode='json',by_alias=True))):
        assert recovered.json()==response.json() and recovered.headers['cache-control']=='no-store'
    assert response.headers['cache-control']=='no-store'
    assert [m for m,_ in calls].count('execute_once')==1 and counts(p)==dict(active=1,receipts=1)
    assert all(auth.removeprefix('Bearer ') not in f.read_text() for f in config.request_directory.iterdir())


@pytest.mark.parametrize('committed',[False,True])
def test_lost_response_and_reconstructed_product_never_resend(setup, monkeypatch, committed):
    cfg,maker,_,p,saved,body,auth,calls,transport=setup
    attempts=[]
    def lost(endpoint,method,request):
        if method=='execute_once':
            attempts.append(1)
            if committed:transport(endpoint,method,request)
            raise OSError('injected transport loss')
        return transport(endpoint,method,request)
    monkeypatch.setattr(product,'request_consumer',lost)
    result=call(setup)
    assert result['status']==('observed' if committed else 'unresolved')
    monkeypatch.setattr(product,'request_consumer',transport)
    assert product.budget_consumption_request(replace(cfg),saved['proposalId'],body,maker,auth)==result
    assert call(setup,False)==result
    assert attempts==[1] and counts(p)==dict(active=int(committed),receipts=int(committed))


def test_changed_body_and_corrupt_file_do_not_dispatch(setup):
    cfg,maker,_,p,saved,body,auth,calls,_=setup
    call(setup)
    with pytest.raises(product.BudgetProductBlocked):
        product.budget_consumption_request(cfg,saved['proposalId'],body.model_copy(update={'decision_id':'other'}),maker,auth)
    assert [m for m,_ in calls].count('execute_once')==1
    next(cfg.request_directory.iterdir()).write_text('{')
    n=len(calls)
    with pytest.raises(product.BudgetProductBlocked):call(setup,False)
    with pytest.raises(product.BudgetProductBlocked):call(setup)
    assert len(calls)==n and counts(p)==dict(active=1,receipts=1)


@pytest.mark.parametrize('index',[1,2])
def test_failed_fsync_keeps_slot_and_only_inquires(setup, monkeypatch, index):
    cfg,_,_,p,_,_,_,calls,_=setup
    original=os.fsync;seen=[]
    def fail(fd):
        seen.append(1)
        if len(seen)==index:raise OSError('isolated disk failure')
        return original(fd)
    monkeypatch.setattr(os,'fsync',fail)
    with pytest.raises(product.BudgetProductBlocked):call(setup)
    assert not calls and len(list(cfg.request_directory.iterdir()))==1
    monkeypatch.setattr(os,'fsync',original)
    assert call(setup)=={'status':'unresolved'}
    assert all(m=='inquiry' for m,_ in calls) and counts(p)==dict(active=0,receipts=0)


def test_checker_cannot_create_maker_request(setup,https_signer):
    cfg,_,checker,p,saved,body,_,calls,_=setup
    with pytest.raises(product.BudgetProductBlocked):
        product.budget_consumption_request(cfg,saved['proposalId'],body,checker,'Bearer '+https_signer[0](checker.subject))
    assert not list(cfg.request_directory.iterdir()) and not calls
    assert counts(p)==dict(active=0,receipts=0)


def test_revocation_preserves_existing_history(setup,issuer_factory,https_signer):
    _,maker,_,p,saved,_,_,calls,_=setup
    result=call(setup)
    BudgetCostIssuer(issuer_factory).execute(command(https_signer[0],maker,saved,operation='revoke',decision=None,reason='withdraw'))
    assert call(setup,False)==result and call(setup)==result
    assert [m for m,_ in calls].count('execute_once')==1
    assert counts(p)==dict(active=1,receipts=1)


def test_concurrent_product_request_dispatches_once(setup):
    def run(_):
        try:return call(setup)
        except product.BudgetProductBlocked as exc:assert exc.status_code==503
    with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(run,range(2)))
    assert call(setup,False)['status']=='observed'
    assert [m for m,_ in setup[-2]].count('execute_once')==1
    assert counts(setup[3])==dict(active=1,receipts=1)


def test_revocation_before_first_attempt_has_no_slot_or_dispatch(setup, issuer_factory, https_signer):
    cfg, maker, _, p, saved, _, _, calls, _ = setup
    BudgetCostIssuer(issuer_factory).execute(command(https_signer[0], maker, saved,
        operation='revoke', decision=None, reason='withdraw before consumption'))
    with pytest.raises(product.BudgetProductBlocked) as error:
        call(setup)
    assert error.value.status_code == 409
    assert not calls and not list(cfg.request_directory.iterdir())
    assert counts(p) == dict(active=0, receipts=0)
