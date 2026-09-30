"""Real PG/JWT product recovery; transport adapter is NOT cross-UID proof."""
from dataclasses import replace
import json
import os
from concurrent.futures import ThreadPoolExecutor

import pytest

from aos_api import aip_budget_cost_product as product
from aos_api.aip_budget_cost_client import BudgetCostEndpoint
from aos_api.aip_budget_cost_process import dispatch_budget_request
from tests.aip.test_budget_cost_process import config as issuer_config
from tests.aip.test_budget_cost_connection_pg import configured
from tests.aip.test_budget_cost_issuer_pg import issuer_factory, prepared
from tests.aip.test_network_consumer_connection_pg import private_passfile
from tests.aip.test_network_consumer_signed_https_pg import https_signer
from tests.aip.test_network_consumer_boundary_pg import SCOPE, isolated_owner
from tests.aip.test_budget_preview_inquiry_pg import http_client


@pytest.fixture
def setup(issuer_config, https_signer, tmp_path, monkeypatch):
    sign, _ = https_signer
    _, checker, _, _, saved = prepared()
    folder = tmp_path/'api-requests'; folder.mkdir(mode=0o700)
    cfg = product.BudgetCostProductConfig(BudgetCostEndpoint(issuer_config.socket_path,
        os.geteuid(), os.geteuid()+1, os.getegid()), folder)
    calls = []
    def transport(endpoint, method, cmd):
        # Adapt transport only; FU performs real TLS JWT/current membership,
        # private DB login, schema checks, signing and immutable Receipt reads.
        calls.append((method, cmd.idempotency_key))
        return dispatch_budget_request(issuer_config, method, cmd)
    monkeypatch.setattr(product, 'request_budget', transport)
    body = product.BudgetCostReviewRequest(proposalHash=saved['proposalHash'], decision='approved')
    return cfg, checker, saved['proposalId'], body, 'Bearer '+sign(checker.subject), calls, transport


def call(setup, body=True, config=None):
    cfg, actor, proposal, request, auth, _, _ = setup
    return product.budget_cost_request(config or cfg, proposal, 'decide', request if body else None, actor, auth)


def count(proposal):
    with isolated_owner() as conn:
        return conn.execute('SELECT count(*) AS n FROM aip_budget_cost_decision WHERE proposal_id=%s',(proposal,)).fetchone()['n']


def test_reload_same_reference_never_resends_and_does_not_store_token(setup):
    cfg, actor, proposal, body, auth, calls, _ = setup
    assert call(setup, False)=={'status':'not_attempted'}
    result = call(setup)
    assert result['status']=='observed' and result['activationEligible'] is False
    assert [m for m,_ in calls]==['execute_once']  # FU already read the immutable Receipt.
    assert call(setup, False, replace(cfg))==result and call(setup)==result
    assert [m for m,_ in calls].count('execute_once')==1 and count(proposal)==1
    files = list(cfg.request_directory.iterdir()); assert len(files)==1
    saved = files[0].read_text()
    assert auth.removeprefix('Bearer ') not in saved and 'bearerToken' not in saved
    assert len({key for _,key in calls})==1


def test_changed_body_conflicts_in_stable_slot(setup):
    cfg, actor, proposal, body, auth, calls, _ = setup
    call(setup)
    with pytest.raises(product.BudgetProductBlocked) as error:
        product.budget_cost_request(cfg,proposal,'decide',body.model_copy(update={'decision':'rejected'}),actor,auth)
    assert error.value.status_code==409 and count(proposal)==1
    assert [m for m,_ in calls].count('execute_once')==1


@pytest.mark.parametrize('committed',[False,True])
def test_lost_dispatch_response_recovers_without_resending(setup, monkeypatch, committed):
    cfg, actor, proposal, body, auth, calls, transport = setup
    attempts = []
    def lost(endpoint, method, cmd):
        if method=='execute_once':
            attempts.append(1)
            if committed: transport(endpoint,method,cmd)
            raise OSError('isolated transport loss')
        return transport(endpoint,method,cmd)
    monkeypatch.setattr(product,'request_budget',lost)
    result=call(setup)
    assert result['status']==('observed' if committed else 'unresolved')
    monkeypatch.setattr(product,'request_budget',transport)
    assert call(setup,False)==result and call(setup)==result
    assert len(attempts)==1 and count(proposal)==int(committed)


@pytest.mark.parametrize('index',[1,2])
def test_fsync_failure_retains_slot_without_dispatch(setup, monkeypatch, index):
    cfg, _, proposal, _, _, calls, _ = setup
    original=os.fsync; fsyncs=[]
    def fail(fd):
        fsyncs.append(1)
        if len(fsyncs)==index: raise OSError('isolated disk error')
        return original(fd)
    monkeypatch.setattr(os,'fsync',fail)
    with pytest.raises(product.BudgetProductBlocked): call(setup)
    assert not calls and len(list(cfg.request_directory.iterdir()))==1
    monkeypatch.setattr(os,'fsync',original)
    assert call(setup)=={'status':'unresolved'}
    assert all(m=='inquiry' for m,_ in calls) and count(proposal)==0


@pytest.mark.parametrize('kind',['broken','hash','permissions','symlink','fifo'])
def test_corrupt_or_unsafe_saved_request_is_not_absence(setup, kind):
    cfg, _, proposal, _, _, calls, _ = setup
    call(setup); before=len(calls); path=next(cfg.request_directory.iterdir())
    if kind=='broken':path.write_text('{')
    elif kind=='hash':
        data=json.loads(path.read_text()); data['requestHash']='wrong';path.write_text(json.dumps(data))
    elif kind=='permissions':path.chmod(0o644)
    else:
        path.unlink()
        if kind=='symlink':path.symlink_to(cfg.request_directory/'missing')
        else:os.mkfifo(path,0o600)
    with pytest.raises(product.BudgetProductBlocked):call(setup,False)
    with pytest.raises(product.BudgetProductBlocked):call(setup)
    assert len(calls)==before and count(proposal)==1


def test_concurrent_same_request_one_dispatch(setup):
    def run(_):
        try:return call(setup)
        except product.BudgetProductBlocked as exc:assert exc.status_code==503
    with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(run,range(2)))
    assert call(setup,False)['status']=='observed'
    assert [m for m,_ in setup[5]].count('execute_once')==1 and count(setup[2])==1


def test_http_safe_reference_and_explicit_private_config(setup, tmp_path, monkeypatch, http_client):
    cfg, actor, proposal, body, auth, calls, _=setup
    folder=tmp_path/'config';folder.mkdir(mode=0o700);path=folder/'api.json'
    data=dict(schemaVersion=1,socketPath=str(cfg.endpoint.socket_path),apiUid=cfg.endpoint.api_uid,
        issuerUid=cfg.endpoint.issuer_uid,ipcGid=cfg.endpoint.ipc_gid,requestDirectory=str(cfg.request_directory))
    path.write_text(json.dumps(data));path.chmod(0o600)
    monkeypatch.setenv('AOS_BUDGET_COST_API_CONFIG',str(path))
    url=f'/v1/aip/budgets/cost-proposals/{proposal}/review-requests/decide'
    headers={'Authorization':auth,'X-Org-Id':SCOPE.org_id,'X-Project-Id':SCOPE.project_id}
    initial=http_client.get(url,headers=headers)
    assert initial.status_code==200 and initial.json()=={'status':'not_attempted'}
    response=http_client.post(url,headers=headers,json=body.model_dump(mode='json',by_alias=True))
    assert response.status_code==200, response.text
    recovered=http_client.get(url,headers=headers)
    assert recovered.json()==response.json() and count(proposal)==1
    assert all(r.headers['cache-control']=='no-store' for r in (initial,response,recovered))
    assert 'request' not in recovered.json() and 'reason' not in recovered.json()
    data['database']='forbidden';path.write_text(json.dumps(data))
    assert http_client.get(url,headers=headers).status_code==503
    monkeypatch.delenv('AOS_BUDGET_COST_API_CONFIG')
    assert http_client.get(url,headers=headers).status_code==503
    assert [m for m,_ in calls].count('execute_once')==1


def test_original_maker_revocation_survives_refresh(setup, https_signer):
    from aos_api.aip_budget_cost_client import decode_budget_response
    cfg=setup[0];sign,_=https_signer
    maker,checker,_,_,saved=prepared();proposal=saved['proposalId']
    approve=product.BudgetCostReviewRequest(proposalHash=saved['proposalHash'],decision='approved')
    result=product.budget_cost_request(cfg,proposal,'decide',approve,checker,'Bearer '+sign(checker.subject))
    assert result['status']=='observed'
    body=product.BudgetCostReviewRequest(proposalHash=saved['proposalHash'],reason='withdraw exact approval')
    auth='Bearer '+sign(maker.subject)
    revoked=product.budget_cost_request(cfg,proposal,'revoke',body,maker,auth)
    assert revoked['status']=='observed'
    assert product.budget_cost_request(replace(cfg),proposal,'revoke',None,maker,auth)==revoked
    assert product.budget_cost_request(cfg,proposal,'revoke',body,maker,auth)==revoked
    cmd=product._command(maker,proposal,'revoke',body,auth)
    assert decode_budget_response(json.dumps(dict(schemaVersion=1,**revoked)).encode(),cmd)==revoked
    assert revoked['result']['decisionId']==result['result']['decisionId']


def test_identity_mismatch_rejected_before_file_or_transport(setup, https_signer):
    cfg,actor,proposal,body,_,calls,_=setup;sign,_=https_signer
    with pytest.raises(product.BudgetProductBlocked) as error:
        product.budget_cost_request(cfg,proposal,'decide',body,actor,'Bearer '+sign('different-subject'))
    assert error.value.status_code==403
    assert not list(cfg.request_directory.iterdir()) and not calls
