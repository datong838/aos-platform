import importlib.util
from pathlib import Path
from types import SimpleNamespace
import pytest

ROOT=Path(__file__).resolve().parents[4]

def module():
    spec=importlib.util.spec_from_file_location('replacement_commands',ROOT/'scripts/a0v_niushop_1_5_replacement.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

@pytest.mark.parametrize('case',['valid','wrong_installation','wrong_generation','already_disabled','multiple_bindings','wrong_state','unknown_action'])
def test_fixed_disable_target_rejects_scope_or_phase_drift(case):
    m=module();record=SimpleNamespace(installation_id=m.PREDECESSOR['installationId'],state='active',etag_version=7)
    bindings=[dict(generation='275e1941-2e87-4a75-aa3c-e0508be9e2ce',revision=4,enabled=True,operation_fence=False)]
    if case=='wrong_installation':record.installation_id='eda57424-b8cb-401e-a6f7-94220cb4f9ef'
    if case=='wrong_generation':bindings[0]['generation']='00000000-0000-0000-0000-000000000000'
    if case=='already_disabled':bindings[0]['enabled']=False
    if case=='multiple_bindings':bindings.append(dict(bindings[0]))
    if case=='wrong_state':record.state='uninstalled'
    action='unknown' if case=='unknown_action' else 'disable-parent'
    if case=='valid':assert m.command_target(action,record,bindings)['target']['bindingRevision']==4
    else:
        with pytest.raises(ValueError):m.command_target(action,record,bindings)


@pytest.mark.parametrize('action,state,etag',[('prepare','approved',3),('verify','applied',4)])
@pytest.mark.parametrize('case',['valid','parent','wrong_state','wrong_revision','binding_present'])
def test_preparation_cannot_target_parent_or_wrong_phase(action,state,etag,case):
    m=module();record=SimpleNamespace(installation_id=m.REPLACEMENT,state=state,etag_version=etag)
    bindings=[]
    if case=='parent':record.installation_id=m.PREDECESSOR['installationId']
    if case=='wrong_state':record.state='active'
    if case=='wrong_revision':record.etag_version+=1
    if case=='binding_present':bindings=[{}]
    if case=='valid':assert m.command_target(action,record,bindings)['installationId']==m.REPLACEMENT
    else:
        with pytest.raises(ValueError):m.command_target(action,record,bindings)


def test_durable_intent_refuses_second_write_after_unknown_outcome(tmp_path):
    import json
    m=module();path=tmp_path/'command.json';original={'installationId':m.REPLACEMENT,'etag':3}
    m.freeze_command(path,original)
    with pytest.raises(FileExistsError):m.freeze_command(path,{'etag':4})
    assert json.loads(path.read_text())==original
    assert path.stat().st_mode & 0o777==0o600


def test_unknown_owner_outcome_is_not_resent(monkeypatch,tmp_path):
    from unittest.mock import Mock
    m=module();monkeypatch.setattr(m,'STATE',tmp_path)
    monkeypatch.setattr(m,'observe',lambda:dict(installations={m.REPLACEMENT:dict(
        record=dict(installation_id=m.REPLACEMENT,state='approved',etag_version=3),bindings=[])}))
    actor=SimpleNamespace(ACTOR='existing-owner',ROLES=frozenset({'admin'}),MARKINGS=frozenset())
    monkeypatch.setattr(m,'load',lambda name:actor)
    owner=Mock(side_effect=RuntimeError('outcome unknown'))
    plane=SimpleNamespace(lifecycle_service=SimpleNamespace(request_preparation=owner))
    with pytest.raises(RuntimeError,match='outcome unknown'):m.request_command(plane,'prepare')
    with pytest.raises(FileExistsError):m.request_command(plane,'prepare')
    assert owner.call_count==1
    assert owner.call_args.kwargs['installation_id']==m.REPLACEMENT
    assert owner.call_args.kwargs['kind']=='runtime-apply'
    assert owner.call_args.kwargs['if_match']=='"3"'


@pytest.mark.parametrize('case',['valid','still_enabled','wrong_revision','wrong_generation','not_unknown'])
def test_recovered_disable_requires_exact_fenced_generation(case):
    m=module();r=SimpleNamespace(installation_id=m.PREDECESSOR['installationId'],state='active',etag_version=7)
    b=dict(generation=m.PARENT_GENERATION,revision=5,enabled=False,operation_fence=True,observed_state='unknown')
    if case=='still_enabled':b['enabled']=True
    if case=='wrong_revision':b['revision']=4
    if case=='wrong_generation':b['generation']='wrong'
    if case=='not_unknown':b['observed_state']='ready'
    if case=='valid':assert m.command_target('disable-parent-recovered',r,[b])['target']['bindingRevision']==5
    else:
        with pytest.raises(ValueError):m.command_target('disable-parent-recovered',r,[b])


@pytest.mark.parametrize('case',['unknown_outcome','different_failure','resource_pending','no_resources'])
def test_recovery_refuses_unproven_terminal_or_resource_state(monkeypatch,tmp_path,case):
    m=module();monkeypatch.setattr(m,'STATE',tmp_path)
    prior=dict(operation_id=m.STALE_DISABLE,status='failed',failure_code='DISABLE_TARGET_STALE')
    resources=[dict(cleanup_state='released',observed_release=True)]
    if case=='unknown_outcome':prior['status']='accepted'
    if case=='different_failure':prior['failure_code']='OTHER'
    if case=='resource_pending':resources[0]['observed_release']=False
    if case=='no_resources':resources=[]
    state=dict(record=dict(installation_id=m.PREDECESSOR['installationId'],state='active',etag_version=7),
        bindings=[dict(generation=m.PARENT_GENERATION,revision=5,enabled=False,operation_fence=True,observed_state='unknown')],
        operations=[prior],resources=resources)
    monkeypatch.setattr(m,'observe',lambda:dict(installations={m.PREDECESSOR['installationId']:state}))
    with pytest.raises(ValueError):m.request_command(SimpleNamespace(),'disable-parent-recovered')
    assert not list(tmp_path.iterdir())
