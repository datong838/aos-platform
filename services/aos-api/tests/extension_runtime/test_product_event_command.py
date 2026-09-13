from dataclasses import replace
import pytest
from test_product_event_binding import pair,body
from ecommerce_growth.ecommerce_product_event_binding import prepare_event_case_binding
from ecommerce_growth.ecommerce_product_event_command import build_event_policy_command
from ecommerce_growth.sdk_ports import ExactRef
from aos_extension_sdk import DispatchRef
from aos_api.ecommerce_growth_host_ports import _reject_authority_overrides


def dispatch():
    return DispatchRef('org-org','dev-project','ecommerce_growth_schedule_put','extension',1,
        '11111111-1111-4111-8111-111111111111','22222222-2222-4222-8222-222222222222',1,
        '33333333-3333-4333-8333-333333333333',1)


def test_wire_keeps_hash_and_passes_existing_authority_override_guard(pair):
    binding=prepare_event_case_binding(*pair)
    approval=ExactRef('ActionApprovalEvent','approval',1,'sha256:'+'a'*64,None)
    command=build_event_policy_command(binding,dispatch_ref=dispatch(),approval_ref=approval,idempotency_key='save-event')
    _reject_authority_overrides(command)
    assert 'tenant' not in command['policy'] and 'tenant' not in command['caseAuthority']
    assert command['policy']['contentHash']==binding.policy.content_hash
    assert command['caseAuthority']['contentHash']==binding.case.content_hash
    assert command['expectedCaseVersion']==binding.case.revision-1
    assert 'sourceContext' not in command


@pytest.mark.parametrize('change',['tenant','operation','legacy'])
def test_wrong_dispatch_rejected(pair,change):
    binding=prepare_event_case_binding(*pair);ref=dispatch()
    ref=replace(ref,**({'org_id':'other'} if change=='tenant' else {'operation_id':'ecommerce_growth_case_put'}
        if change=='operation' else {'handler_kind':'legacy','installation_id':None,'generation':None,'execution_epoch':None}))
    with pytest.raises(ValueError):build_event_policy_command(binding,dispatch_ref=ref,
        approval_ref=ExactRef('ActionApprovalEvent','approval',1,'sha256:'+'a'*64,None),idempotency_key='key')


def test_host_restores_only_its_tenant(pair):
    from aos_api.ecommerce_product_event_host_service import _parse
    from aos_api.tenant_scope import TenantScope
    binding=prepare_event_case_binding(*pair)
    command=build_event_policy_command(binding,dispatch_ref=dispatch(),
        approval_ref=ExactRef('ActionApprovalEvent','approval',1,'sha256:'+'a'*64,None),idempotency_key='key')
    restored,_=_parse(command,TenantScope('org-org','dev-project'))
    assert restored['policy']==binding.policy.authority_payload()
    assert restored['caseAuthority']==binding.case.authority_payload()
    with pytest.raises(ValueError):_parse(command,TenantScope('dev-org','dev-project'))
    command['policy']['tenant']={'orgId':'org-org','projectId':'dev-project'}
    with pytest.raises(ValueError):_parse(command,TenantScope('org-org','dev-project'))
