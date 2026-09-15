import importlib
from types import SimpleNamespace as N
import pytest
from test_bootstrap_successor_business import profile


@pytest.mark.parametrize('fault',['prefix','revision','dependencies','status','target'])
def test_refresh_refuses_other_or_changed_bindings(profile,fault):
    m=importlib.import_module('a0v_i_current_binding_refresh')
    deps=object();request=N(binding_id='a0v-model-successor-r3-d01-test',binding=N(capability='cap'))
    cap=N(binding_id=request.binding_id,capability='cap',dependencies=deps,status='active')
    skill=N(binding_id='a0v-model-successor-r3-skill-d01',skill=N(revision=3),status='active',capability_binding_ids=[cap.binding_id])
    m.require_current(cap,skill,request,deps)
    if fault=='prefix':request.binding_id='a0v-firstchain-d01-test'
    if fault=='revision':skill.skill.revision=2
    if fault=='dependencies':cap.dependencies=object()
    if fault=='status':cap.status='suspended'
    if fault=='target':skill.capability_binding_ids=['other']
    with pytest.raises(ValueError):m.require_current(cap,skill,request,deps)


def test_unknown_refresh_intent_is_read_only(profile,monkeypatch,tmp_path):
    m=importlib.import_module('a0v_i_current_binding_refresh');monkeypatch.setattr(m,'STATE',tmp_path)
    (tmp_path/'intent.json').write_text('{}')
    monkeypatch.setattr(m.h,'setup',lambda:pytest.fail('cannot repeat unknown refresh'))
    with pytest.raises(ValueError,match='receipt inspection'):m.run()
