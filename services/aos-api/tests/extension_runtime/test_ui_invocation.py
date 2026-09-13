from types import SimpleNamespace
import pytest
from pydantic import ValidationError
from aos_api.extension_runtime.ui_invocation import RuntimeUiInvocationTarget, require_current_ui_invocation


def target(**changes):
    values=dict(installationId='11111111-1111-4111-8111-111111111111',generation='22222222-2222-4222-8222-222222222222',
                installationRevision=5,executionEpoch=3,bindingRevision=4,route='/workshop/analyst',resourceHash='sha256:'+'a'*64)
    return RuntimeUiInvocationTarget(**(values|changes))


def view():
    t=target()
    return SimpleNamespace(installationId=t.installationId,installationRevision=5,effectiveState='ready',
      binding=SimpleNamespace(generation=t.generation,installationRevision=5,executionEpoch=3,revision=4,enabled=True,operationFence=False),
      ui=SimpleNamespace(resourceHash=t.resourceHash,initialRoute=t.route,routeClaims=(t.route,),readOperationClaims=('read_summary',),commandOperationClaims=('create_case',)))


@pytest.mark.parametrize('change', ['fence','epoch','revision','generation','hash','route','disabled','operation','kind'])
def test_stale_or_undeclared_ui_invocation_is_denied(change):
    current=view(); kind='read'; operation='read_summary'
    if change=='fence':current.binding.operationFence=True
    if change=='epoch':current.binding.executionEpoch+=1
    if change=='revision':current.installationRevision+=1
    if change=='generation':current.binding.generation='33333333-3333-4333-8333-333333333333'
    if change=='hash':current.ui.resourceHash='sha256:'+'b'*64
    if change=='route':current.ui.routeClaims=('/other',)
    if change=='disabled':current.effectiveState='disabled'
    if change=='operation':operation='unlisted'
    if change=='kind':kind='command'
    with pytest.raises(PermissionError):require_current_ui_invocation(current=current,target=target(),kind=kind,operation_id=operation)


def test_current_declared_call_has_no_execution_result():
    assert require_current_ui_invocation(current=view(),target=target(),kind='read',operation_id='read_summary') is None


@pytest.mark.parametrize('changes',[{'executionEpoch':True},{'route':'/workshop/../admin'},{'bindingRevision':0},{'approved':True}])
def test_target_is_strict(changes):
    with pytest.raises(ValidationError):target(**changes)
