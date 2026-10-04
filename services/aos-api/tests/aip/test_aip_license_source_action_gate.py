"""Source issuance must enter its dedicated Owner approval command."""
import pytest

from aos_api.aip_action_policy import classify_action_risk
from aos_api.aip_contracts import ActionRiskLevel
from aos_api.aip_policy_activation_action import (
    PolicyActivationActionTypeReserved, require_generic_action_type_mutable,
)
from aos_api.aip_action_models import CreateActionProposalRequest, CreateActionDraftRequest, ReviseActionDraftRequest
from aos_api.aip_action_service import AipActionService
from aos_api.aip_action_store import AipActionStore, AipActionTransitionBlocked
from aos_api.auth import Principal
from aos_api.errors import ApiError
from aos_api.tenant_scope import TenantScope

ACTION='aip_issue_source_license'

@pytest.mark.parametrize('hint',[None,ActionRiskLevel.R0])
def test_source_issuance_requires_independent_approval_and_dedicated_consumer(hint):
    risk=classify_action_risk(ACTION,{'id':ACTION}, {},hint)
    assert risk.floor is ActionRiskLevel.R2
    assert risk.approval_policy['makerChecker'] is True
    assert risk.approval_policy['minimumApprovals']==1
    assert risk.approval_policy['executionAllowed'] is False
    assert risk.approval_policy['draftOnly'] is False
    assert risk.approval_policy['sourceLicenseIssuanceOnly'] is True


def test_source_action_cannot_be_registered_by_generic_editor_or_seed():
    with pytest.raises(PolicyActivationActionTypeReserved):
        require_generic_action_type_mutable(ACTION)
    require_generic_action_type_mutable(ACTION+'_v2')
    require_generic_action_type_mutable('ordinary-work-order')


@pytest.mark.parametrize('method,model',[
    ('create_proposal',CreateActionProposalRequest),
    ('create_draft',CreateActionDraftRequest),
    ('revise_draft',ReviseActionDraftRequest),
])
def test_generic_producer_rejects_source_before_schema_or_store(monkeypatch,method,model):
    class UnexpectedStore:
        def __getattr__(self,name):
            raise AssertionError('generic store must not be accessed')
    def unexpected(*args,**kwargs):
        raise AssertionError('generic schema must not be accessed')
    monkeypatch.setattr('aos_api.aip_action_service.ensure_action_schema',unexpected)
    data={'actionTypeId':ACTION,'purpose':'source license'}
    if method=='revise_draft':
        data.update(expectedRevision=1,expectedContentHash='a'*64)
    body=model.model_validate(data)
    service=AipActionService(UnexpectedStore())
    principal=Principal(subject='owner',org_id='org-org',project_id='dev-project')
    with pytest.raises(ApiError) as exc:
        if method=='revise_draft':
            service.revise_draft(principal,'draft','key',body)
        else:
            getattr(service,method)(principal,'key',body)
    assert exc.value.code=='AIP_SOURCE_LICENSE_PRODUCER_REQUIRED'
    assert exc.value.status_code==403


@pytest.mark.parametrize('body_id,snapshot_id',[(ACTION,ACTION),(ACTION,'ordinary'),('ordinary',ACTION)])
def test_direct_store_request_and_proposal_cannot_spoof_source_identity(body_id,snapshot_id):
    def unexpected(*args):
        raise AssertionError('no database connection allowed')
    store=AipActionStore(unexpected)
    scope=TenantScope('org-org','dev-project')
    body=CreateActionProposalRequest.model_validate({'actionTypeId':body_id,'purpose':'source'})
    snapshot={'id':snapshot_id}
    risk=classify_action_risk(body_id,snapshot,{},None)
    with pytest.raises(AipActionTransitionBlocked,match='SOURCE_LICENSE_PRODUCER_REQUIRED'):
        store._internal_request_binding(None,scope,'owner',body,snapshot,risk)
    row={'action_type_id':body_id,'action_type_snapshot':snapshot,'payload':{}}
    for checker in (False,True):
        with pytest.raises(AipActionTransitionBlocked,match='SOURCE_LICENSE_PRODUCER_REQUIRED'):
            store._internal_proposal_guard(None,scope,'owner',row,checker=checker)


def test_direct_create_rejects_before_opening_transaction():
    def unexpected(*args):
        raise AssertionError('no database connection allowed')
    store=AipActionStore(unexpected)
    body=CreateActionProposalRequest.model_validate({'actionTypeId':ACTION,'purpose':'source'})
    risk=classify_action_risk(ACTION,{'id':ACTION},{},None)
    with pytest.raises(AipActionTransitionBlocked,match='SOURCE_LICENSE_PRODUCER_REQUIRED'):
        store.create_proposal(TenantScope('org-org','dev-project'),'owner','key',body,{'id':ACTION},risk)

@pytest.mark.parametrize('endpoint',['create','update'])
def test_actual_editor_rejects_source_before_schema(monkeypatch,endpoint):
    from aos_api.routers import actions
    def unexpected(*args,**kwargs):
        raise AssertionError('schema must not be touched')
    monkeypatch.setattr(actions,'ensure_action_schema',unexpected)
    body=actions.ActionTypeIn(id=ACTION,name='source license',objectType='WorkOrder')
    principal=Principal(subject='owner',org_id='org-org',project_id='dev-project')
    with pytest.raises(ApiError) as exc:
        if endpoint=='create':
            actions.create_action_type(body,principal)
        else:
            actions.update_action_type(ACTION,body,principal)
    assert exc.value.status_code==403
    assert exc.value.code=='AIP_POLICY_ACTION_TYPE_RESERVED'

@pytest.mark.parametrize('force',[False,True])
def test_actual_seed_rejects_source_before_connection(monkeypatch,force):
    from aos_api import action_template_registry
    def unexpected():
        raise AssertionError('no database connection allowed')
    monkeypatch.setattr(action_template_registry,'connect',unexpected)
    with pytest.raises(PolicyActivationActionTypeReserved):
        action_template_registry.upsert_action_type({'id':ACTION},force=force)

@pytest.mark.parametrize('hint',[ActionRiskLevel.R3,ActionRiskLevel.R4])
def test_source_client_risk_hint_can_raise_but_never_enable_generic_execution(hint):
    risk=classify_action_risk(ACTION,{'id':ACTION},{},hint)
    assert risk.level is hint
    assert risk.floor is ActionRiskLevel.R2
    assert risk.approval_policy['minimumApprovals']==2
    assert risk.approval_policy['executionAllowed'] is False
