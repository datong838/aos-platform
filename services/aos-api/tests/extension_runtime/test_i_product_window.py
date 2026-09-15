import importlib
import pytest
from test_bootstrap_successor_business import profile


def test_i_profile_separates_original_state_and_exact_identity(profile):
    w=importlib.import_module('a0v_i_product_window')
    old=importlib.import_module('a0v_event_complete_product_enable')
    authority=w.authority_profile();policy=w.policy_profile();enable=w.enable_profile();source=w.source_profile()
    assert enable.EXPECTED_GROUP_REVISION==23 and old.EXPECTED_GROUP_REVISION==11
    assert source.POLICY_REVISION==6
    assert authority.previous_reference('selection') is None
    assert authority.previous_reference('control') is None
    assert authority.f is policy.f is enable.f is source.f is w.h
    assert 'successor-i/registration' in str(authority.STATE)
    assert authority.preflight_profile is source.preflight_profile is w.preflight
    p=w.preflight()
    assert p.CURRENT_CREATE.name=='create-result.json' and p.CURRENT_CREATE.parent.name=='i'
    assert p.CUTOVER_RESUME==w.h.STATE/'cutover/resume-result.json'


def test_i_policy_requires_exact_previous_receipt(profile,monkeypatch):
    w=importlib.import_module('a0v_i_product_window')
    from types import SimpleNamespace
    p=w.policy_profile();payload=dict(revision=5,contentHash='sha256:'+'a'*64)
    previous=SimpleNamespace(load=lambda phase:dict(command=dict(policy=payload)) if phase=='prepare' else dict(receiptRef=dict(resourceId=p.POLICY,revision=3,contentHash=payload['contentHash'])))
    monkeypatch.setattr(w.predecessor,'policy_profile',lambda:previous)
    with pytest.raises(ValueError,match='Policy5'):w.policy_profile().previous_policy_payload()
