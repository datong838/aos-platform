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
