import importlib
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "scripts"))


def test_second_window_chains_exact_v1_authority_and_policy8():
    window = importlib.import_module("a0v_l_product_window2")
    assert window._previous_ref("selection")["revision"] == 1
    assert window._previous_ref("control")["revision"] == 1
    assert window._previous_ref("binding")["revision"] == 14
    assert window.policy_profile().previous_policy_payload()["revision"] == 8
    assert window.authority_profile().STATE.name == "product-authority-v2"


def test_second_window_reuses_routes_and_advances_binding_cas_only():
    window = importlib.import_module("a0v_l_product_window2")
    enable = window.enable_profile()
    assert enable.EXPECTED_GROUP_REVISION == 37
    assert enable.EXPECTED_BINDING_REVISION == 0
    with pytest.raises(ValueError, match="unsupported"):
        window.run("enable", "expand")


def test_generic_enable_default_cas_is_unchanged():
    generic = importlib.import_module("a0v_event_complete_product_enable")
    assert generic.EXPECTED_BINDING_REVISION == 0


def test_policy9_retry_uses_fresh_state_and_zero_revision():
    retry = importlib.import_module("a0v_l_product_binding_retry").enable_profile()
    assert retry.STATE.name == "event-enable-v3"
    assert retry.PREFIX.endswith("-v3")
    assert retry.EXPECTED_BINDING_REVISION == 0
    assert retry.EXPECTED_GROUP_REVISION == 37
