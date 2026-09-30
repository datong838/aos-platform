"""Real disposable PG producer tests; no live Provider or activation."""
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import psycopg
import pytest

from aos_api.aip_budget_cost_basis import BudgetCostBasisProposal
from aos_api.aip_budget_cost_proposal_store import BudgetCostProposalStore
from aos_api.aip_budget_activation_store import BudgetActivationDenied, BudgetActivationConflict
from aos_api.db import connect
from tests.aip.test_aip_budget_activation_store_pg import setup_case, SCOPE
from tests.aip.test_budget_preview_inquiry_pg import http_client
from tests.aip.test_network_consumer_signed_https_pg import https_signer
from tests.aip.test_network_consumer_boundary_pg import isolated_owner


def case():
    maker,checker,other,target=setup_case()
    proposal=BudgetCostBasisProposal(schemaVersion=1,tenant={'orgId':SCOPE.org_id,'projectId':SCOPE.project_id},
        target=target,draftRevision=1,expectedHeadVersion=1,makerSubject=maker.subject,
        checkerSubject=checker.subject,basis=dict(kind='development_risk_proposal',
        provider=dict(assetType='ProviderInstanceRevision',assetId='candidate-only',revision=1,contentHash='a'*64),
        providerModelId='candidate-model',perRequestRiskMinor=10,totalRiskMinor=100,maxRequests=10))
    return maker,checker,other,proposal,'cost-'+uuid4().hex


def counts():
    with isolated_owner() as conn:
        return tuple(conn.execute('SELECT count(*) AS n FROM '+table).fetchone()['n'] for table in
            ('aip_budget_cost_proposal','aip_budget_cost_proposal_receipt','aip_budget_revision'))


def test_create_read_and_original_request_recovery_are_non_authorizing():
    maker,checker,other,p,key=case();store=BudgetCostProposalStore();before=counts()
    saved=store.create(maker,p,key)
    assert saved['status']=='proposed' and saved['sourceVerification']=='pending'
    assert saved['activationEligible'] is False and saved['proposalHash']==p.proposal_hash
    assert store.create(maker,p,key)==saved
    assert store.get(checker,saved['proposalId'])==saved
    with pytest.raises(BudgetActivationDenied):store.get(other,saved['proposalId'])
    assert counts()==(before[0]+1,before[1]+1,before[2])
    historical=counts()
    assert store.inquire(maker,p,key)==dict(status='observed',proposalId=saved['proposalId'],
        proposalHash=p.proposal_hash,activationEligible=False)
    assert store.inquire(maker,p,'unseen-'+key)=={'status':'unresolved'}
    changed=p.model_copy(deep=True);changed.basis.total_risk_minor=110
    assert store.inquire(maker,changed,key)=={'status':'conflict'}
    with pytest.raises(BudgetActivationConflict):store.create(maker,changed,key)
    assert counts()==historical


@pytest.mark.parametrize('change',['head','target','checker','actor','external'])
def test_invalid_current_sources_leave_no_partial_rows(change):
    maker,checker,other,p,key=case();store=BudgetCostProposalStore();before=counts()
    if change=='head':p.expected_head_version=2
    elif change=='target':p.target.daily_limit_minor=501
    elif change=='checker':p.checker_subject=other.subject
    elif change=='actor':maker=checker
    else:
        body=p.model_dump(mode='json',by_alias=True)
        body['basis']={'kind':'external_reconciliation_reference','statement':
            {'assetType':'BudgetUsageReconciliationRevision','assetId':'unverified','revision':1,'contentHash':'b'*64}}
        p=BudgetCostBasisProposal.model_validate(body)
    with pytest.raises(BudgetActivationDenied):store.create(maker,p,key)
    assert counts()==before


def test_member_revocation_and_cross_tenant_cannot_read_or_replay():
    from aos_api.auth import Principal
    maker,checker,_,p,key=case();store=BudgetCostProposalStore();saved=store.create(maker,p,key)
    with pytest.raises(BudgetActivationDenied):store.inquire(Principal(maker.subject,'dev-org',SCOPE.project_id,token_kind='oidc'),p,key)
    with connect(SCOPE) as conn:
        conn.execute('DELETE FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s',(*SCOPE.key,maker.subject));conn.commit()
    for call in (lambda:store.create(maker,p,key),lambda:store.inquire(maker,p,key),lambda:store.get(maker,saved['proposalId'])):
        with pytest.raises(BudgetActivationDenied):call()


@pytest.mark.parametrize('field',['accounts','currency','period'])
def test_canonical_reader_rejects_derived_field_tampering(field):
    _,_,_,p,_=case();body=p.canonical_payload()
    assert BudgetCostBasisProposal.from_canonical_payload(body).proposal_hash==p.proposal_hash
    body[field]='forged'
    with pytest.raises(ValueError):BudgetCostBasisProposal.from_canonical_payload(body)


def test_immutable_tables_forced_rls_and_single_concurrent_receipt():
    maker,_,_,p,key=case();before=counts()
    def create():
        try:return BudgetCostProposalStore().create(maker,p,key)
        except psycopg.errors.SerializationFailure:return None
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:create(),range(2)))
    assert any(results)
    assert len({r['proposalId'] for r in results if r})==1
    assert counts()==(before[0]+1,before[1]+1,before[2])
    assert BudgetCostProposalStore().inquire(maker,p,key)['status']=='observed'
    for table in ('aip_budget_cost_proposal','aip_budget_cost_proposal_receipt'):
        with isolated_owner() as conn:
            row=conn.execute('SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid=%s::regclass',(table,)).fetchone()
            assert row=={'relrowsecurity':True,'relforcerowsecurity':True}
        with pytest.raises(psycopg.Error):
            with connect(SCOPE) as conn:conn.execute('DELETE FROM '+table)
        with isolated_owner() as conn:
            with pytest.raises(psycopg.Error):conn.execute('TRUNCATE '+table+' CASCADE')
    with connect(SCOPE.__class__('dev-org','dev-project')) as conn:
        assert conn.execute('SELECT count(*) AS n FROM aip_budget_cost_proposal').fetchone()['n']==0


def test_receipt_failure_rolls_back_proposal():
    maker,_,_,p,key=case();before=counts()
    # Isolated DB only: a real trigger failure after the proposal insert.
    with isolated_owner() as conn:
        conn.execute("CREATE FUNCTION public.test_cost_receipt_failure() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'injected receipt failure'; END $$")
        conn.execute('CREATE TRIGGER test_cost_receipt_failure BEFORE INSERT ON aip_budget_cost_proposal_receipt FOR EACH ROW EXECUTE FUNCTION public.test_cost_receipt_failure()');conn.commit()
    try:
        with pytest.raises(psycopg.Error):BudgetCostProposalStore().create(maker,p,key)
        assert counts()==before
    finally:
        with isolated_owner() as conn:
            conn.execute('DROP TRIGGER test_cost_receipt_failure ON aip_budget_cost_proposal_receipt');conn.execute('DROP FUNCTION public.test_cost_receipt_failure()');conn.commit()


def test_signed_http_producer_checker_read_and_inquiry(http_client,https_signer):
    sign,fetched=https_signer
    maker,checker,_,p,key=case()
    headers={'Authorization':'Bearer '+sign(maker.subject),'X-Org-Id':SCOPE.org_id,'X-Project-Id':SCOPE.project_id,'Idempotency-Key':key}
    body=p.model_dump(mode='json',by_alias=True);url='/v1/aip/budgets/cost-proposals'
    saved=http_client.post(url,json=body,headers=headers)
    assert saved.status_code==201,saved.text
    result=saved.json();before=counts()
    read=http_client.get(url+'/'+result['proposalId'],headers={**headers,'Authorization':'Bearer '+sign(checker.subject)})
    inquiry=http_client.post(url+'/inquiry',json=body,headers=headers)
    assert read.status_code==200 and read.json()==result
    assert inquiry.status_code==200 and inquiry.json()['status']=='observed'
    assert counts()==before and fetched
    for r in (saved,read,inquiry):assert r.headers['cache-control']=='no-store'
    assert http_client.post(url,json=body,headers={**headers,'Authorization':'Bearer dev'}).status_code==401


@pytest.mark.parametrize('column,value',[('status','approved'),('source_verification','verified'),('activation_eligible',True)])
def test_database_cannot_promote_proposal_to_authority(column,value):
    from psycopg import sql
    from psycopg.types.json import Jsonb
    maker,_,_,p,key=case();saved=BudgetCostProposalStore().create(maker,p,key);before=counts()
    with connect(SCOPE) as conn:
        row=dict(conn.execute('SELECT * FROM aip_budget_cost_proposal WHERE proposal_id=%s',(saved['proposalId'],)).fetchone())
    row.update(proposal_id='invalid-'+uuid4().hex);row[column]=value;row['payload']=Jsonb(row['payload'])
    with pytest.raises(psycopg.errors.CheckViolation):
        with connect(SCOPE) as conn:
            conn.execute(sql.SQL('INSERT INTO aip_budget_cost_proposal ({}) VALUES ({})').format(
                sql.SQL(',').join(map(sql.Identifier,row)),sql.SQL(',').join(sql.Placeholder() for _ in row)),list(row.values()))
    assert counts()==before


def test_read_failure_is_503_not_missing(http_client,https_signer,monkeypatch):
    from contextlib import contextmanager
    from aos_api import aip_budget_cost_proposal_store as module
    sign,_=https_signer;maker,_,_,p,key=case()
    @contextmanager
    def unavailable(_scope):
        raise psycopg.OperationalError('test-only unavailable')
        yield
    monkeypatch.setattr(module,'connect_read_only',unavailable)
    response=http_client.post('/v1/aip/budgets/cost-proposals/inquiry',
        json=p.model_dump(mode='json',by_alias=True),headers={'Authorization':'Bearer '+sign(maker.subject),
        'X-Org-Id':SCOPE.org_id,'X-Project-Id':SCOPE.project_id,'Idempotency-Key':key})
    assert response.status_code==503 and 'unresolved' not in response.text
