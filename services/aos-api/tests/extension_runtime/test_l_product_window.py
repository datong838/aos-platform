import importlib
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'scripts'))


def test_l_profile_pins_reinstalled_identity_and_natural_window():
    window = importlib.import_module('a0v_l_product_window')
    authority = window.authority_profile()
    policy = window.policy_profile()
    enable = window.enable_profile()
    assert enable.EXPECTED_GROUP_REVISION == 36
    assert authority.previous_reference('selection') is None
    assert authority.f is policy.f is enable.f is window.current
    assert 'successor-l/registration/product-authority' in str(authority.STATE)
    profile = window.preflight()
    assert profile.CURRENT_CREATE.parent.name == 'l'
    assert profile.CUTOVER_RESUME == window.current.STATE / 'cutover/resume-result.json'
    assert profile.AUTHORITY_WINDOW_MINUTES == 90


def test_l_policy_requires_exact_j_policy7(monkeypatch):
    window = importlib.import_module('a0v_l_product_window')
    policy = window.policy_profile()
    payload = {'revision': 7, 'contentHash': 'sha256:' + 'a' * 64}
    prior = SimpleNamespace(load=lambda phase:
        {'command': {'policy': payload}} if phase == 'prepare' else
        {'receiptRef': {'resourceId': policy.POLICY, 'revision': 6,
                        'contentHash': payload['contentHash']}})
    monkeypatch.setattr(window.predecessor, 'policy_profile', lambda: prior)
    with pytest.raises(ValueError, match='Policy7'):
        window.policy_profile().previous_policy_payload()


def test_generic_preflight_default_window_remains_fifteen_minutes():
    generic = importlib.import_module('a0v_p02_current_preflight')
    assert generic.AUTHORITY_WINDOW_MINUTES == 15
