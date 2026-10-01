"""Isolated real PG/JWT/HTTP. Dispatch adapter is not a cross-UID IPC proof."""
import json
import os
import pytest
from aos_api import aip_budget_consumer_product as product
from aos_api.aip_budget_consumer_client import BudgetConsumerEndpoint
from aos_api.aip_budget_consumer_process import dispatch_consumer_request, decode_consumer_request
from tests.aip.test_budget_consumer_process import config as consumer_config
from tests.aip.test_budget_consumer_connection_pg import configured
from tests.aip.test_budget_cost_consumer_pg import approved
from tests.aip.test_budget_cost_issuer_pg import issuer_factory
from tests.aip.test_network_consumer_connection_pg import private_passfile
from tests.aip.test_network_consumer_signed_https_pg import https_signer
from tests.aip.test_network_consumer_boundary_pg import SCOPE
from tests.aip.test_budget_preview_inquiry_pg import http_client


@pytest.fixture
def setup(consumer_config, issuer_factory, https_signer, tmp_path, monkeypatch):
    maker, checker, proposal, saved, decision = approved(issuer_factory, https_signer)
    folder=tmp_path/'configuration-api'; folder.mkdir(mode=0o700)
    cfg=product.BudgetConsumerProductConfig(BudgetConsumerEndpoint(consumer_config.socket_path,
        os.geteuid(),os.geteuid()+1,os.getegid()),folder)
    calls=[]
    def transport(endpoint,method,request):
        calls.append((method,request))
        payload=request.model_dump(mode='json',by_alias=True)
        payload['bearerToken']=request.bearer_token.get_secret_value()
        decoded_method,decoded=decode_consumer_request(json.dumps(dict(schemaVersion=1,method=method,payload=payload)).encode())
        return dispatch_consumer_request(consumer_config,decoded_method,decoded)
    monkeypatch.setattr(product,'request_consumer',transport)
    body=product.BudgetConsumptionRequest(proposalHash=saved['proposalHash'],decisionId=decision['decisionId'])
    auth='Bearer '+https_signer[0](maker.subject)
    return cfg,maker,checker,proposal,saved,body,auth,calls,transport,consumer_config


def execute(setup, operation='configure', body=True):
    cfg,maker,_,_,saved,request,auth,*_=setup
    return product.budget_consumption_request(cfg,saved['proposalId'],request if body else None,
        maker,auth,operation=operation)


def test_http_configuration_has_separate_original_slot(setup,monkeypatch,http_client):
    cfg,_,_,_,saved,body,auth,calls,_,process=setup
    p=cfg.request_directory/'api.json'
    p.write_text(json.dumps(dict(schemaVersion=1,socketPath=str(cfg.endpoint.socket_path),
        apiUid=cfg.endpoint.api_uid,consumerUid=cfg.endpoint.consumer_uid,ipcGid=cfg.endpoint.ipc_gid,
        requestDirectory=str(cfg.request_directory))))
    p.chmod(0o600);monkeypatch.setenv('AOS_BUDGET_CONSUMER_API_CONFIG',str(p))
    headers={'Authorization':auth,'X-Org-Id':SCOPE.org_id,'X-Project-Id':SCOPE.project_id}
    root=f"/v1/aip/budgets/cost-proposals/{saved['proposalId']}"
    first=http_client.get(root+'/configuration-request',headers=headers)
    assert first.status_code==200 and first.json()=={'status':'not_attempted'}
    consumed=http_client.post(root+'/consumption-request',headers=headers,json=body.model_dump(mode='json',by_alias=True))
    assert consumed.status_code==200,consumed.text
    result=http_client.post(root+'/configuration-request',headers=headers,json=body.model_dump(mode='json',by_alias=True))
    assert result.status_code==200,result.text
    r=result.json();assert r['status']=='observed' and r['activationEligible'] is False
    assert r['receipt']['budgetRef']['assetId']==consumed.json()['receipt']['resourceId']
    assert r['receipt']['priceRef']['assetType']=='ModelPriceSnapshotRevision'
    assert r['receipt']['policyRef']['assetType']=='BudgetPolicyRevision'
    for method in ('get','post'):
        kw={'json':body.model_dump(mode='json',by_alias=True)} if method=='post' else {}
        response=getattr(http_client,method)(root+'/configuration-request',headers=headers,**kw)
        assert response.json()==r and response.headers['cache-control']=='no-store'
    writes=[request for method,request in calls if method=='execute_once']
    assert len(writes)==2 and {r.operation for r in writes}=={'consume','configure'}
    assert len({r.request_hash for r in writes})==2
    assert len(list(process.attempt_directory.iterdir()))==2
    assert all(auth.removeprefix('Bearer ') not in f.read_text() for f in cfg.request_directory.iterdir())


def configuration_count(saved):
    from tests.aip.test_network_consumer_boundary_pg import isolated_owner
    with isolated_owner() as conn:
        return conn.execute("SELECT count(*) AS n FROM aip_model_governance_policy_receipt "
            "WHERE org_id=%s AND project_id=%s AND operation='budget_cost.configure' AND idempotency_key=%s",
            (*SCOPE.key,saved['proposalId'])).fetchone()['n']


@pytest.mark.parametrize('committed',[False,True])
def test_configuration_response_loss_never_resends(setup,monkeypatch,committed):
    from dataclasses import replace
    cfg,maker,_,_,saved,body,auth,calls,transport,_=setup
    assert execute(setup,'consume')['status']=='observed'
    attempts=[]
    def lost(endpoint,method,request):
        if method=='execute_once' and request.operation=='configure':
            attempts.append(1)
            if committed:transport(endpoint,method,request)
            raise OSError('injected response loss')
        return transport(endpoint,method,request)
    monkeypatch.setattr(product,'request_consumer',lost)
    result=execute(setup)
    assert result['status']==('observed' if committed else 'unresolved')
    monkeypatch.setattr(product,'request_consumer',transport)
    assert product.budget_consumption_request(replace(cfg),saved['proposalId'],body,maker,auth,operation='configure')==result
    assert execute(setup,body=False)==result
    assert attempts==[1] and configuration_count(saved)==int(committed)


def test_configure_commit_ack_loss_only_reconciles(setup,monkeypatch):
    from contextlib import contextmanager
    import aos_api.aip_budget_consumer_service as service
    assert execute(setup,'consume')['status']=='observed'
    original=service.connect_budget_consumer;writes=[]
    @contextmanager
    def lost(config,scope,*,read_only=False):
        with original(config,scope,read_only=read_only) as conn:yield conn
        if not read_only:
            writes.append(1)
            raise OSError('injected after real commit')
    monkeypatch.setattr(service,'connect_budget_consumer',lost)
    result=execute(setup)
    assert result['status']=='observed' and execute(setup)==result
    assert writes==[1] and configuration_count(setup[4])==1


def test_concurrent_configure_and_revoked_history(setup,issuer_factory,https_signer):
    from concurrent.futures import ThreadPoolExecutor
    from aos_api.aip_budget_cost_issuer import BudgetCostIssuer
    from tests.aip.test_budget_cost_issuer_pg import command
    _,maker,_,_,saved,_,_,calls,_,_=setup
    execute(setup,'consume')
    def run(_):
        try:return execute(setup)
        except product.BudgetProductBlocked as error:assert error.status_code==503
    with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(run,range(2)))
    result=execute(setup,body=False);assert result['status']=='observed'
    BudgetCostIssuer(issuer_factory).execute(command(https_signer[0],maker,saved,
        operation='revoke',decision=None,reason='withdraw after configuration'))
    assert execute(setup)==result and execute(setup,body=False)==result
    assert len([1 for m,r in calls if m=='execute_once' and r.operation=='configure'])==1
    assert configuration_count(saved)==1


def test_unconsumed_service_source_has_no_attempt_or_configuration(setup):
    from aos_api.aip_budget_consumer_service import BudgetConsumerRequest,consume_budget_once
    from aos_api.aip_budget_consumer_connection import BudgetConsumerBlocked
    _,_,_,_,saved,body,auth,_,_,process=setup
    request=BudgetConsumerRequest(schemaVersion=1,operation='configure',orgId=SCOPE.org_id,
        projectId=SCOPE.project_id,proposalId=saved['proposalId'],proposalHash=body.proposal_hash,
        decisionId=body.decision_id,bearerToken=auth.removeprefix('Bearer '))
    with pytest.raises(BudgetConsumerBlocked):
        consume_budget_once(request,process.database,process.attempt_directory)
    assert not list(process.attempt_directory.iterdir()) and configuration_count(saved)==0


@pytest.mark.parametrize('drift',['checker','expired','signature','tenant'])
def test_configure_rejects_identity_before_attempt(setup,https_signer,drift):
    from pydantic import SecretStr
    from aos_api.aip_budget_consumer_service import consume_budget_once,BudgetConsumerServiceBlocked
    from aos_api.aip_budget_consumer_connection import BudgetConsumerBlocked
    _,maker,checker,_,saved,_,_,calls,_,process=setup
    execute(setup,'consume')
    request=calls[-1][1].model_copy(update={'operation':'configure'})
    if drift=='tenant':changes={'org_id':'dev-org'}
    else:
        token=https_signer[0](checker.subject if drift=='checker' else maker.subject,
            changes={'exp':1} if drift=='expired' else {},wrong_key=drift=='signature')
        changes={'bearer_token':SecretStr(token)}
    before=set(process.attempt_directory.iterdir())
    with pytest.raises((BudgetConsumerServiceBlocked,BudgetConsumerBlocked)):
        consume_budget_once(request.model_copy(update=changes),process.database,process.attempt_directory)
    assert set(process.attempt_directory.iterdir())==before and configuration_count(saved)==0


def test_bad_original_body_or_file_prevents_configuration_dispatch(setup):
    cfg,maker,_,_,saved,body,auth,calls,_,_=setup
    execute(setup,'consume');execute(setup)
    before=len(calls)
    with pytest.raises(product.BudgetProductBlocked):
        product.budget_consumption_request(cfg,saved['proposalId'],body.model_copy(update={'decision_id':'other'}),
            maker,auth,operation='configure')
    marker=next(cfg.request_directory.glob('budget-configuration-product-v1-*'))
    marker.write_text('{')
    with pytest.raises(product.BudgetProductBlocked):execute(setup,body=False)
    assert len(calls)==before and configuration_count(saved)==1


def test_configure_receipt_rejects_cross_operation_and_forged_refs(setup):
    import copy
    from aos_api.aip_budget_consumer_client import decode_consumer_response,BudgetConsumerClientBlocked
    from aos_api.aip_budget_consumer_service import validate_consumer_result,BudgetConsumerServiceBlocked
    consumed=execute(setup,'consume');result=execute(setup)
    request=next(r for m,r in setup[7] if m=='execute_once' and r.operation=='configure')
    assert decode_consumer_response(json.dumps({'schemaVersion':1,**result}).encode(),request)==result
    cases=[consumed]
    for key,field,value in [('priceRef','assetId','other'),('policyRef','revision',2),
                            ('budgetRef','assetType','Other'),('budgetRef','revision',True),
                            ('priceRef','contentHash','bad'),('policyRef','extra',True)]:
        mutated=copy.deepcopy(result);mutated['receipt'][key][field]=value;cases.append(mutated)
    mutated=copy.deepcopy(result);mutated['activationEligible']=True;cases.append(mutated)
    for result in cases:
        with pytest.raises(BudgetConsumerServiceBlocked):validate_consumer_result(result,request)
        with pytest.raises(BudgetConsumerClientBlocked):
            decode_consumer_response(json.dumps({'schemaVersion':1,**result}).encode(),request)


def test_preexisting_configure_attempt_only_reads(setup):
    from aos_api.aip_network_issuer_attempt import AttemptReceipt,_reserve_attempt_receipt
    from aos_api.aip_budget_consumer_service import consume_budget_once
    _,maker,_,_,saved,_,_,calls,_,process=setup
    execute(setup,'consume');request=calls[-1][1].model_copy(update={'operation':'configure'})
    _reserve_attempt_receipt(process.attempt_directory,AttemptReceipt(request.org_id,request.project_id,
        request.proposal_id,request.proposal_id,request.request_hash,maker.subject),namespace='budget-cost-configuration/v1')
    assert consume_budget_once(request,process.database,process.attempt_directory)=={'status':'unresolved'}
    assert configuration_count(saved)==0


def test_revoked_before_configuration_creates_no_new_slot(setup,issuer_factory,https_signer):
    from aos_api.aip_budget_cost_issuer import BudgetCostIssuer
    from tests.aip.test_budget_cost_issuer_pg import command
    cfg,maker,_,_,saved,_,_,calls,_,process=setup
    execute(setup,'consume')
    before=(set(cfg.request_directory.iterdir()),set(process.attempt_directory.iterdir()),len(calls))
    BudgetCostIssuer(issuer_factory).execute(command(https_signer[0],maker,saved,
        operation='revoke',decision=None,reason='withdraw before configuration'))
    with pytest.raises(product.BudgetProductBlocked) as error:execute(setup)
    assert error.value.status_code==409
    assert before==(set(cfg.request_directory.iterdir()),set(process.attempt_directory.iterdir()),len(calls))
    assert configuration_count(saved)==0


def test_unknown_operation_cannot_reach_dispatch(setup):
    from pydantic import ValidationError
    from aos_api.aip_budget_consumer_service import BudgetConsumerRequest
    with pytest.raises(product.BudgetProductBlocked):execute(setup,'activate_anything')
    assert not setup[7]
    with pytest.raises(ValidationError):
        BudgetConsumerRequest(schemaVersion=1,operation='activate_anything',orgId='org-org',projectId='dev-project',
            proposalId='p',proposalHash='a'*64,decisionId='d',bearerToken='aaa.bbb.ccc')
