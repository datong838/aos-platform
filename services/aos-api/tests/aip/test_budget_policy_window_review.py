"""Unit metadata/read-boundary evidence only; no native, ACL or human approval."""
from contextlib import contextmanager
from copy import deepcopy

import pytest
from psycopg import IsolationLevel
from pydantic import ValidationError

from aos_api import aip_budget_policy_window_review as review
from aos_api.aip_budget_cost_basis import BudgetCostBasisProposal
from aos_api.aip_budget_store import canonical_hash
from aos_api.auth import Principal

HUMAN = '6f31cfdc-a26c-4f1f-ad6b-95a8559cc657'
TENANT = {'orgId': 'org-org', 'projectId': 'dev-project'}


def snapshot():
    tenant = deepcopy(TENANT)
    p = BudgetCostBasisProposal.model_validate(dict(schemaVersion=1, tenant=deepcopy(tenant),
        draftRevision=1, expectedHeadVersion=2, makerSubject='unit-machine', checkerSubject=HUMAN,
        target=dict(budgetId='unit-budget', revision=2, lifecycle='active', dailyLimitMinor=50,
            monthlyLimitMinor=500, alertThresholdPct=80, owner=HUMAN, overBudgetApprover=HUMAN,
            effectiveFrom='2026-10-01T00:00:00Z', effectiveUntil='2026-11-01T00:00:00Z'),
        basis=dict(kind='development_risk_proposal', provider=dict(assetType='ProviderInstanceRevision',
            assetId='unit-provider', revision=1, contentHash='a'*64), providerModelId='unit-model',
            perRequestRiskMinor=10, totalRiskMinor=100, maxRequests=10)))
    t = p.canonical_payload()['target']
    b = dict(**t, tenant=deepcopy(tenant), contentHash=canonical_hash(t), createdBy='unit-machine',
             createdAt='2026-10-01T00:01:00Z')
    digest = canonical_hash(dict(domain='aos.budget-cost-consume/v1', tenant=deepcopy(tenant),
        proposalId='unit-proposal', proposalHash=p.proposal_hash, decisionId='unit-decision'))
    receipt = dict(receiptId='budget-cost-consume-'+digest, requestHash=digest,
        createdBy='unit-machine', resultRef=dict(resourceType='BudgetRevision', resourceId='unit-budget',
            revision=2, contentHash=b['contentHash'], proposalId='unit-proposal',
            proposalHash=p.proposal_hash, decisionId='unit-decision', receiptId='budget-cost-consume-'+digest))
    provider = dict(tenant=deepcopy(tenant), ref=p.canonical_payload()['basis']['provider'], lifecycle='active')
    return dict(schemaVersion='aos.budget-policy-window.review-source/v1', tenant=deepcopy(tenant),
        evaluatedAt='2026-10-18T00:00:00Z', parent=dict(proposalId='unit-proposal',
            proposalHash=p.proposal_hash, proposal=p.canonical_payload(), decisionId='unit-decision',
            decision='approved', revoked=False), consumption=receipt, sourceBudget=b, currentBudget=deepcopy(b),
        currentBudgetHeadVersion=3, sourceProvider=provider, currentProvider=deepcopy(provider),
        state='observed', blockers=[], approvalVerified=False, activationEligible=False,
        nativeWriteAllowed=False, runtimeAdmissionAllowed=False, nativeParentVerification='not-performed')


def test_observation_exposes_shared_parent_caps_without_balance_or_authority():
    value = review.BudgetPolicyWindowReviewSource.model_validate(snapshot())
    assert value.parent.proposal.basis.total_risk_minor == 100
    assert value.parent.proposal.basis.max_requests == 10
    assert value.state == 'observed'
    body = value.model_dump(mode='json', by_alias=True)
    assert all(body[k] is False for k in ('approvalVerified','activationEligible','nativeWriteAllowed','runtimeAdmissionAllowed'))
    assert body['nativeParentVerification'] == 'not-performed'
    assert not {'remainingMinor','availableMinor','exposureMinor','requestedPolicyWindow'} & body.keys()


@pytest.mark.parametrize('key', ['approvalVerified','activationEligible','nativeWriteAllowed','runtimeAdmissionAllowed'])
@pytest.mark.parametrize('value', [True, 0, 'false', None])
def test_no_permission_coercion(key, value):
    data = snapshot(); data[key] = value
    with pytest.raises(ValidationError): review.BudgetPolicyWindowReviewSource.model_validate(data)


@pytest.mark.parametrize('change', ['receipt','revoke','head','budget','provider','window','approval'])
def test_missing_and_changed_parent_facts_are_explicit_blockers(change):
    data = snapshot()
    if change=='receipt': data['consumption']=None
    elif change=='revoke': data['parent']['revoked']=True
    elif change=='head': data['currentBudgetHeadVersion']=4
    elif change=='budget': data['currentBudget']=None
    elif change=='provider': data['currentProvider']=None
    elif change=='window': data['evaluatedAt']='2026-11-01T00:00:00Z'
    else: data['parent']['decision']='missing';data['parent']['decisionId']=None;data['consumption']=None
    value = review.build_source(**data)
    assert value.state=='blocked' and value.blockers
    assert value.runtime_admission_allowed is False
    data['state']='observed';data['blockers']=[]
    with pytest.raises(ValidationError): review.BudgetPolicyWindowReviewSource.model_validate(data)


@pytest.mark.parametrize('change', ['receipt_hash','receipt_actor','receipt_result','proposal_hash','tenant','provider_tenant'])
def test_drift_cannot_be_presented_as_observed(change):
    data = snapshot()
    if change=='receipt_hash': data['consumption']['requestHash']='c'*64
    elif change=='receipt_actor': data['consumption']['createdBy']='other'
    elif change=='receipt_result': data['consumption']['resultRef']['revision']=9
    elif change=='proposal_hash': data['parent']['proposalHash']='d'*64
    elif change=='tenant': data['tenant']['orgId']='dev-org'
    else: data['sourceProvider']['tenant']={'orgId':'dev-org','projectId':'dev-project'}
    with pytest.raises(ValidationError): review.BudgetPolicyWindowReviewSource.model_validate(data)


def test_expired_original_decision_does_not_invalidate_consumed_parent_by_itself():
    # The original review store validates original decision timing. This DTO has
    # no new approval expiry check and grants no new approval of any kind.
    value=review.BudgetPolicyWindowReviewSource.model_validate(snapshot())
    assert value.state=='observed' and value.native_parent_verification=='not-performed'


@pytest.mark.parametrize('subject,org,kind', [('other','org-org','oidc'),(HUMAN,'dev-org','oidc'),(HUMAN,'org-org','dev')])
def test_wrong_identity_rejected_without_opening_connection(subject,org,kind):
    def forbidden(*a): raise AssertionError('connection opened')
    with pytest.raises(review.BudgetPolicyWindowReviewDenied):
        review.BudgetPolicyWindowReviewReader(forbidden).read(
            Principal(subject=subject,org_id=org,project_id='dev-project',token_kind=kind),'unit-proposal')


@pytest.mark.parametrize('ro,isolation', [(False,IsolationLevel.REPEATABLE_READ),(True,IsolationLevel.READ_COMMITTED),(True,IsolationLevel.SERIALIZABLE)])
def test_connection_properties_checked_before_first_sql(ro,isolation):
    class Conn:
        read_only=ro
        isolation_level=isolation
        def execute(self,*a): raise AssertionError('unsafe connection used')
    @contextmanager
    def factory(scope): yield Conn()
    with pytest.raises(review.BudgetPolicyWindowReviewUnavailable):
        review.BudgetPolicyWindowReviewReader(factory).read(
            Principal(subject=HUMAN,org_id='org-org',project_id='dev-project',token_kind='oidc'),'unit-proposal')


def test_source_revalidates_mutated_nested_proposal():
    value=review.BudgetPolicyWindowReviewSource.model_validate(snapshot())
    value.parent.proposal.basis.total_risk_minor=0
    with pytest.raises(ValidationError): review.build_source(**value.model_dump(mode='python',by_alias=True))


class Cursor:
    def __init__(self, row): self.row=row
    def fetchone(self): return self.row
    def fetchall(self): return [] if self.row is None else [self.row]


class SnapshotConnection:
    """Deterministic unit SELECT fixture, deliberately not PostgreSQL evidence."""
    read_only=True
    isolation_level=IsolationLevel.REPEATABLE_READ
    def __init__(self):
        from datetime import datetime, timedelta
        self.data=snapshot();self.queries=[];self.server_role='aos_runtime';self.server_ro='on'
        self.members={'unit-machine':'owner',HUMAN:'owner'};self.missing=set();self.failure=None
        parent=self.data['parent'];self.proposal=BudgetCostBasisProposal.from_canonical_payload(parent['proposal'])
        p=self.proposal;created=datetime.fromisoformat('2026-10-01T00:01:00+00:00')
        self.cost_row=dict(payload=p.canonical_payload(),proposal_hash=p.proposal_hash,
            maker_subject=p.maker_subject,checker_subject=p.checker_subject,budget_id=p.target.budget_id,
            status='proposed',source_verification='pending',activation_eligible=False,
            created_at=created,expires_at=created+timedelta(minutes=30),proposal_id=parent['proposalId'])
        self.decision=dict(proposal_hash=p.proposal_hash,actor_subject=HUMAN,expires_at=self.cost_row['expires_at'],
            decision='approved',created_at=created+timedelta(seconds=1),source_ref=p.basis.provider.model_dump(mode='json',by_alias=True),
            decision_id=parent['decisionId'])
    def execute(self, sql, params=None):
        from datetime import datetime
        assert sql.strip().upper().startswith('SELECT '), sql
        assert 'FOR SHARE' not in sql.upper() and 'FOR UPDATE' not in sql.upper()
        self.queries.append((sql,params))
        if self.failure and self.failure in sql: raise RuntimeError('unit-private-database-detail')
        if 'current_user AS role' in sql:
            return Cursor(dict(role=self.server_role,org_id='org-org',project_id='dev-project',ro=self.server_ro,isolation='repeatable read'))
        if 'FROM meta_membership' in sql:return Cursor({'role':self.members[params[2]]} if params[2] in self.members else None)
        if 'FROM aip_budget_cost_proposal_receipt' in sql:return Cursor(dict(request_hash=self.proposal.proposal_hash,proposal_id='unit-proposal'))
        if 'FROM aip_budget_cost_proposal ' in sql:return Cursor(self.cost_row)
        if 'FROM aip_budget_cost_decision ' in sql:return Cursor(self.decision)
        if 'FROM aip_budget_cost_revocation ' in sql:return Cursor(None)
        if 'FROM public.aip_budget_receipt ' in sql:
            assert params==('org-org','dev-project','budget_revision.activate_cost','unit-proposal')
            r=self.data['consumption']
            return Cursor(None if 'receipt' in self.missing else dict(receipt_id=r['receiptId'],request_hash=r['requestHash'],result_ref=r['resultRef'],created_by=r['createdBy']))
        if 'FROM aip_budget_head ' in sql:return Cursor({'current_revision':2})
        if 'FROM public.aip_budget_head ' in sql:return Cursor({'current_revision':2,'version':3})
        if 'FROM aip_budget_revision ' in sql:return Cursor(None if 'budget' in self.missing else {'payload':self.data['sourceBudget']})
        if 'FROM aip_provider_instance_head ' in sql:return Cursor(None if 'provider' in self.missing else {'current_revision':1})
        if 'FROM aip_provider_instance_revision ' in sql:
            if 'provider' in self.missing:return Cursor(None)
            def ref(kind):return dict(assetType=kind,assetId='unit-reference',revision=1,contentHash='b'*64)
            return Cursor({'payload':dict(tenant=TENANT,providerInstanceId='unit-provider',revision=1,contentHash='a'*64,
                pluginRef=ref('ProviderPluginRevision'),endpointProfile=dict(baseUrl='https://unit.invalid',region='unit',timeoutMs=1000),
                secretRef='secret://unit-only',secretVersion='unit',egressPolicyRef=ref('EgressPolicyRevision'),
                dataClassificationPolicyRef=ref('DataClassificationPolicyRevision'),lifecycle='active',
                createdBy='unit-machine',createdAt='2026-10-01T00:00:00Z')})
        if sql=='SELECT clock_timestamp() AS now':return Cursor({'now':datetime.fromisoformat('2026-10-18T00:00:00+00:00')})
        raise AssertionError(sql)
    def commit(self):raise AssertionError('readonly reader tried to commit')


def reader_case(conn):
    opens=[];closes=[]
    @contextmanager
    def connect(scope):
        opens.append(scope.key)
        try:yield conn
        finally:closes.append(scope.key)
    principal=Principal(subject=HUMAN,org_id='org-org',project_id='dev-project',token_kind='oidc')
    return review.BudgetPolicyWindowReviewReader(connect),principal,opens,closes


def test_all_owner_reads_use_one_checked_readonly_connection_and_project_no_secrets():
    conn=SnapshotConnection();reader,principal,opens,closes=reader_case(conn)
    value=reader.read(principal,'unit-proposal')
    assert opens==closes==[('org-org','dev-project')]
    assert value.state=='observed' and not value.blockers
    body=value.model_dump_json(by_alias=True)
    assert 'secretRef' not in body and 'endpointProfile' not in body and 'unit.invalid' not in body
    assert not {'reserve','consume','propose','decide'} & {sql.split()[0].lower() for sql,_ in conn.queries}
    assert conn.queries[0][0].startswith('SELECT current_user AS role')
    assert any('aip_budget_cost_proposal ' in q for q,_ in conn.queries)
    assert any('aip_provider_instance_revision ' in q for q,_ in conn.queries)


@pytest.mark.parametrize('missing', ['receipt','budget','provider'])
def test_missing_owner_facts_never_default_to_zero_or_admission(missing):
    conn=SnapshotConnection();conn.missing.add(missing)
    reader,principal,_,_=reader_case(conn);value=reader.read(principal,'unit-proposal')
    assert value.state=='blocked' and value.blockers
    assert value.runtime_admission_allowed is value.native_write_allowed is False


@pytest.mark.parametrize('change', ['role','server-ro','checker-member','maker-member','acl','receipt-drift','decision-drift'])
def test_real_server_identity_membership_acl_and_drift_fail_closed_without_fallback(change):
    conn=SnapshotConnection()
    if change=='role':conn.server_role='postgres'
    elif change=='server-ro':conn.server_ro='off'
    elif change=='checker-member':conn.members.pop(HUMAN)
    elif change=='maker-member':conn.members.pop('unit-machine')
    elif change=='acl':conn.failure='aip_budget_receipt'
    elif change=='receipt-drift':conn.data['consumption']['requestHash']='f'*64
    else:conn.decision['proposal_hash']='e'*64
    reader,principal,opens,closes=reader_case(conn)
    with pytest.raises(review.BudgetPolicyWindowReviewUnavailable,match='^WINDOW_REVIEW_SOURCE_UNAVAILABLE$'):
        reader.read(principal,'unit-proposal')
    assert opens==closes==[('org-org','dev-project')]
    if change in {'role','server-ro'}:assert len(conn.queries)==1


@pytest.mark.parametrize('revision', [True, 1.0, '1', 0, 9_007_199_254_740_992])
def test_provider_observation_keeps_exact_safe_reference_revision(revision):
    data=snapshot();data['sourceProvider']['ref']['revision']=revision
    with pytest.raises(ValidationError):review.BudgetPolicyWindowReviewSource.model_validate(data)
