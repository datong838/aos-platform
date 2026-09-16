import importlib

import pytest


def test_p_failed_window_containment_has_fixed_order_and_exact_policy():
    module = importlib.import_module("a0v_p_failed_window_containment")
    assert module.ACTIONS == ("approve-disable", "disable", "approve-fence", "fence")
    receipt = {
        "resourceType": "SchedulePolicyRevision",
        "resourceId": module.policy_profile().POLICY,
        "revision": 11,
        "contentHash": "sha256:" + "1" * 64,
    }
    payload = module.disable_payload(receipt)
    assert payload["controlIntent"]["expectedBindingRevision"] == 1
    assert payload["controlIntent"]["intent"] == "disable"
    assert payload["controlIntent"]["policyRef"] == receipt


def test_p_failed_window_containment_rejects_other_policy_revision():
    module = importlib.import_module("a0v_p_failed_window_containment")
    with pytest.raises(ValueError, match="Policy11"):
        module.disable_payload({
            "resourceType": "SchedulePolicyRevision",
            "resourceId": module.policy_profile().POLICY,
            "revision": 10,
        })
