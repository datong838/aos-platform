"""Real event storage with named fake source/catalog/approval boundary rows."""
from datetime import datetime,timezone,timedelta
from types import SimpleNamespace
import pytest
from test_product_event_write_pg import stored,pair,body
from tests.test_ecommerce_product_event_policy import case as context_fixture
from aos_api.ecommerce_product_event_policy import ProductEventPolicyDraft
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.pipeline_source_selection_owner import PipelineSourceSelectionOwner
from aos_api.tenant_scope import TenantScope
from aos_api.aip_budget_reservation_store import canonical_hash
import aos_api.ecommerce_product_event_host_service as module


@pytest.fixture
def service_case(stored,monkeypatch):
    conn,binding=stored;p=binding.policy.authority_payload();c=binding.case.authority_payload()
    ctx,_=context_fixture()
    ctx.update(orgId=p['tenant']['orgId'],projectId=p['tenant']['projectId'],
        policyId=p['schedulePolicyId'],sourceSelectionRef=p['sourceSelectionRef'],
        objectTypes=tuple(p['objectTypes']),effectiveFrom=datetime.fromisoformat(p['effectiveFrom']),
        effectiveUntil=datetime.fromisoformat(p['effectiveUntil']))
    context=ProductEventPolicyDraft.model_validate(ctx)
    now=datetime.now(timezone.utc)
    approval=dict(approval_event_id='fixture-approval',proposal_id='fixture-proposal',proposal_version=1,
        proposal_hash='fixture-proposal-hash',decision='approved',actor_id='fixture-approver',reason='test only',
        expires_at=now+timedelta(days=1),created_at=now-timedelta(minutes=1),action_binding_hash='a'*64)
    proposal=dict(proposal_id='fixture-proposal',action_type_id='ecommerce_growth_schedule_put',
        payload=dict(caseId=c['caseId'],schedulePolicyId=p['schedulePolicyId'],expectedPolicyRevision=0,
            expectedCaseVersion=c['revision']-1,policyHash=canonical_hash(p,prefixed=True)),
        proposal_hash='fixture-proposal-hash',status='approved',action_binding_hash='a'*64,
        version=1,expires_at=now+timedelta(days=1))
    command=dict(idempotencyKey='host-event',expectedPolicyRevision=0,expectedCaseVersion=c['revision']-1,
        policy=p,caseAuthority=c,sourceContext=context.model_dump(by_alias=True,mode='json'),
        approvalRef=dict(resourceType='ActionApprovalEvent',resourceId='fixture-approval',revision=1,
            contentHash=canonical_hash(approval,prefixed=True)))
    # Test-only admin seed. No live approval is created or claimed.
    from psycopg.types.json import Jsonb
    conn.execute('RESET ROLE')
    conn.execute("INSERT INTO twa_workspace(org_id,project_id,name) VALUES('org-org','dev-project','fixture') ON CONFLICT DO NOTHING")
    conn.execute("""INSERT INTO aip_action_proposal(org_id,project_id,proposal_id,action_type_id,
        action_type_revision_hash,action_type_snapshot,purpose,risk_level,policy_snapshot,payload,proposal_hash,
        status,expires_at,idempotency_key,request_hash,created_by,action_binding_hash)
        VALUES('org-org','dev-project',%s,%s,'fixture','{}','fixture','R2','{}',%s,%s,'approved',%s,'fixture-proposal','fixture','fixture-maker',%s)""",
        (proposal['proposal_id'],proposal['action_type_id'],Jsonb(proposal['payload']),proposal['proposal_hash'],
         proposal['expires_at'],proposal['action_binding_hash']))
    conn.execute("""INSERT INTO aip_action_approval_event(org_id,project_id,approval_event_id,proposal_id,
        proposal_version,proposal_hash,decision,actor_id,reason,expires_at,created_at,action_binding_hash,idempotency_key,request_hash)
        VALUES('org-org','dev-project',%s,%s,1,%s,'approved',%s,%s,%s,%s,%s,'fixture-approval','fixture')""",
        (approval['approval_event_id'],approval['proposal_id'],approval['proposal_hash'],approval['actor_id'],
         approval['reason'],approval['expires_at'],approval['created_at'],approval['action_binding_hash']))
    conn.execute('SET LOCAL ROLE aos_runtime')
    class Connection:
        def execute(self,query,params=()):
            if 'FROM aip_action_approval_event' in query:return SimpleNamespace(fetchone=lambda:approval)
            if 'FROM aip_action_proposal' in query:return SimpleNamespace(fetchone=lambda:proposal)
            return conn.execute(query,params)
    def named_source(self,**kwargs):return kwargs['execute']()
    monkeypatch.setattr(module.ProductEventPolicyGuard,'run',named_source)
    monkeypatch.setattr(module.EcommerceInvestigationProfileCatalog,'read',lambda *_:(
        SimpleNamespace(exact_ref=SimpleNamespace(model_dump=lambda **kw:c['investigationProfileRef'])),
        SimpleNamespace(exact_ref=SimpleNamespace(model_dump=lambda **kw:c['scopeRef']))))
    service=module.ProductEventSchedulePutHostService(object.__new__(PipelineSourceSelectionOwner),actor='fixture-host')
    return conn,service,HostTransaction(Connection()),command,approval,proposal


def execute(data):
    _,service,transaction,command,_,_=data
    return service.execute(transaction=transaction,scope=TenantScope('org-org','dev-project'),
        dispatch_ref=None,command=command,checked_at=datetime.now(timezone.utc),occurred_at=None)


def test_service_writes_and_verifies_original_receipt(service_case):
    data=service_case;result=execute(data)
    assert result['replayed'] is False
    assert execute(data)['replayed'] is True
    assert data[1].verify_receipt(transaction=data[2],scope=TenantScope('org-org','dev-project'),
        dispatch=None,command=data[3],receipt=result)==result
    assert data[0].execute('SELECT enabled FROM ecommerce_investigation_schedule_policy_head').fetchone()['enabled'] is False


@pytest.mark.parametrize('change',['hash','expired','future','version','method','envelope'])
def test_guard_failure_never_writes(service_case,change):
    conn,_,_,command,approval,proposal=service_case
    if change=='hash':proposal['payload']['policyHash']='sha256:'+'b'*64
    elif change=='expired':proposal['expires_at']=datetime.now(timezone.utc)-timedelta(seconds=1)
    elif change=='future':
        approval['created_at']=datetime.now(timezone.utc)+timedelta(hours=1)
        command['approvalRef']['contentHash']=canonical_hash(approval,prefixed=True)
    elif change=='version':proposal['version']=2
    elif change=='method':command['policy']['methodRef']['contentHash']='sha256:'+'b'*64
    else:command['actor']='self-reported'
    with pytest.raises(ValueError),conn.transaction():execute(service_case)
    assert conn.execute('SELECT count(*) AS n FROM ecommerce_investigation_schedule_policy_head').fetchone()['n']==0


def test_owner_denial_prevents_any_case_write(service_case,monkeypatch):
    def denied(*a,**kw):raise PermissionError('named source rejection')
    monkeypatch.setattr(module.ProductEventPolicyGuard,'run',denied)
    with pytest.raises(PermissionError):execute(service_case)
    assert service_case[0].execute('SELECT count(*) AS n FROM ecommerce_investigation_schedule_policy_head').fetchone()['n']==0


def test_approval_expiry_during_save_rolls_back(service_case,monkeypatch):
    original=module.ProductEventPolicyStore.put
    def slow_save(self,**kwargs):
        result=original(self,**kwargs)
        service_case[5]['expires_at']=datetime.now(timezone.utc)-timedelta(seconds=1)
        return result
    monkeypatch.setattr(module.ProductEventPolicyStore,'put',slow_save)
    with pytest.raises(ValueError),service_case[0].transaction():execute(service_case)
    assert service_case[0].execute('SELECT count(*) AS n FROM ecommerce_investigation_schedule_policy_head').fetchone()['n']==0


def test_current_catalog_method_change_rejected(service_case,monkeypatch):
    class Ref:
        def model_dump(self,**kw):return {'resourceId':'different-current-method'}
    monkeypatch.setattr(module.EcommerceInvestigationProfileCatalog,'read',lambda *_:(
        SimpleNamespace(exact_ref=Ref()),SimpleNamespace(exact_ref=Ref())))
    with pytest.raises(ValueError,match='method drifted'),service_case[0].transaction():execute(service_case)


def test_actual_approval_tables_and_lock_permissions(service_case):
    conn,service,_,command,_,_=service_case
    assert not conn.execute("SELECT has_table_privilege(current_user,'ecommerce_investigation_case_head','UPDATE') AS allowed").fetchone()['allowed']
    conn.execute('RESET ROLE')
    conn.execute('REVOKE UPDATE ON aip_action_approval_event FROM aos_runtime')
    conn.execute('SET LOCAL ROLE aos_runtime')
    assert not conn.execute("SELECT has_table_privilege(current_user,'aip_action_approval_event','UPDATE') AS allowed").fetchone()['allowed']
    actual=(conn,service,HostTransaction(conn),command,None,None)
    assert execute(actual)['replayed'] is False


def test_lock_denies_other_tenant_and_missing_identity(service_case):
    import psycopg
    conn,_,_,command,_,_=service_case
    args=(command['caseAuthority']['caseId'],command['policy']['schedulePolicyId'],'fixture-approval')
    with pytest.raises(psycopg.errors.CheckViolation),conn.transaction():
        conn.execute("SELECT set_config('aos.org_id','other-tenant',true)")
        conn.execute('SELECT ecommerce_product_event_lock_a0v_041(%s,%s,%s)',args)
    with pytest.raises(psycopg.errors.InsufficientPrivilege),conn.transaction():
        conn.execute("SELECT set_config('aos.project_id','',true)")
        conn.execute('SELECT ecommerce_product_event_lock_a0v_041(%s,%s,%s)',args)
