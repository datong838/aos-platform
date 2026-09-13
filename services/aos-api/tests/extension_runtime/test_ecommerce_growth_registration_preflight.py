from copy import deepcopy
from uuid import UUID

import pytest

from aos_api.ecommerce_growth_registration_contracts import FirstDispatchRegistrationRequest
from aos_api.ecommerce_growth_registration_preflight import require_registration_runtime, registration_preflight
from aos_api.tenant_scope import TenantScope
from test_ecommerce_growth_registration_contracts import payload


def binding():
    request=payload()
    return dict(generation=UUID(request['generation']),revision=4,execution_epoch=3,
        installation_revision=5,config_ref=request['configRef'],enabled=True,
        operation_fence=False,desired_state='enabled',observed_state='ready')


def check(value):
    return require_registration_runtime(value,FirstDispatchRegistrationRequest.model_validate(payload()))


def test_exact_current_binding_and_no_mutation():
    value=binding();before=deepcopy(value)
    assert check(value) is None
    assert value==before


@pytest.mark.parametrize('key,value', [('generation',UUID('55555555-5555-4555-8555-555555555555')),
    ('revision',5),('revision',True),('revision','4'),('execution_epoch',4),
    ('installation_revision',6),('enabled',False),('enabled',1),('operation_fence',True),
    ('operation_fence',0),('desired_state','disabled'),('observed_state','unknown'),
    ('config_ref',None)])
def test_drift_is_fail_closed(key,value):
    data=binding();data[key]=value
    with pytest.raises(ValueError,match='REGISTRATION_RUNTIME_TARGET_INVALID'):check(data)


def test_configuration_revision_or_hash_change_is_not_current():
    for key,value in [('revision',2),('hash','sha256:'+'9'*64)]:
        data=binding();data['config_ref'][key]=value
        with pytest.raises(ValueError,match='REGISTRATION_RUNTIME_TARGET_INVALID'):check(data)


@pytest.mark.parametrize('value',[None,[],{}])
def test_absent_binding_rejected(value):
    with pytest.raises(ValueError,match='REGISTRATION_RUNTIME_TARGET_INVALID'):check(value)


def test_arbitrary_dependency_cannot_be_a_current_authority():
    with pytest.raises(TypeError):
        registration_preflight(None,scope=TenantScope('org-a','workspace-a'),
            request=FirstDispatchRegistrationRequest.model_validate(payload()),actor='actor',
            installation_store=object(),configuration_authorize=lambda **kwargs:True)


def test_draining_identity_does_not_grant_registration_readiness():
    from aos_api.ecommerce_growth_registration_preflight import require_registration_runtime_identity
    data=binding();data.update(revision=5,enabled=False,operation_fence=True)
    request=FirstDispatchRegistrationRequest.model_validate(payload())
    require_registration_runtime_identity(data,request)
    with pytest.raises(ValueError):require_registration_runtime(data,request)
    data['execution_epoch']=4
    with pytest.raises(ValueError):require_registration_runtime_identity(data,request)


@pytest.mark.parametrize('drift',[None,'config','generation','epoch','installation','denied'])
def test_current_assets_keep_identity_and_configuration_checks_during_drain(monkeypatch,drift):
    from datetime import datetime,timezone
    from types import SimpleNamespace
    from psycopg.pq import TransactionStatus
    from aos_api.asset_registry.installation_store import PostgresInstallationStore
    from aos_api.extension_runtime.configuration_authorization import CurrentFourSourceConfigurationAuthorization
    from aos_api.ecommerce_growth_registration_preflight import validate_current_registration_assets,validate_current_registration_target
    request=FirstDispatchRegistrationRequest.model_validate(payload());data=binding()
    data.update(revision=5,enabled=False,operation_fence=True)
    if drift=='config':data['config_ref']={**data['config_ref'],'revision':2}
    elif drift=='generation':data['generation']=UUID('55555555-5555-4555-8555-555555555555')
    elif drift=='epoch':data['execution_epoch']=4
    elif drift=='installation':data['installation_revision']=6
    scope=TenantScope('org-a','project-a');seen=[]
    class Connection:
        info=SimpleNamespace(transaction_status=TransactionStatus.INTRANS)
        def execute(self,query,params=()):
            if 'current_setting' in query:return SimpleNamespace(fetchone=lambda:dict(org_id=scope.org_id,project_id=scope.project_id))
            assert 'FROM extension_runtime_binding' in query and 'FOR SHARE' in query
            return SimpleNamespace(fetchall=lambda:[data])
    store=object.__new__(PostgresInstallationStore)
    monkeypatch.setattr(store,'lock_for_transition_in_transaction',lambda *a,**k:SimpleNamespace(record=SimpleNamespace(state='active')))
    monkeypatch.setattr(store,'load_active_baseline_in_transaction',lambda *a,**k:SimpleNamespace(lock=SimpleNamespace(payload=SimpleNamespace(resolved=[SimpleNamespace(id='solution.ecommerce.growth')]))))
    monkeypatch.setattr(store,'read_control_clock_in_transaction',lambda *a:datetime.now(timezone.utc))
    def authorize(*a,**kw):
        seen.append(kw)
        if drift=='denied':raise PermissionError('configuration denied')
    monkeypatch.setattr('aos_api.ecommerce_growth_registration_preflight.read_configuration',authorize)
    kwargs=dict(scope=scope,request=request,actor='actor',installation_store=store,
        configuration_authorize=object.__new__(CurrentFourSourceConfigurationAuthorization))
    if drift is None:
        result=validate_current_registration_assets(Connection(),**kwargs)
        assert result['runtimeStateValidated'] is False and result['executable'] is False
        assert len(seen)==1 and seen[0]['ref']==request.configRef
    else:
        with pytest.raises((ValueError,PermissionError)):validate_current_registration_assets(Connection(),**kwargs)
    with pytest.raises(ValueError):validate_current_registration_target(Connection(),**kwargs)
