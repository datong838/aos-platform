import importlib
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))


def test_q_window_uses_exact_policy12_and_route_revision():
    window = importlib.import_module("a0v_q_product_window")
    assert window.current.G_ID == window.current.Q_ID
    assert window.current.G_GENERATION == window.current.Q_GENERATION
    assert window.authority_profile().previous_reference("selection") is None
    assert window.authority_profile().previous_reference("control") is None
    binding = window.authority_profile().previous_reference("binding")
    assert binding["revision"] == 17
    assert binding["contentHash"] == "sha256:83758e3c663c6f4b06946c6d09c4b70abd338158ea6d9535ca7467f8ba0796ad"
    previous = window.policy_profile().previous_policy_payload()
    assert previous["revision"] == 11
    assert previous["contentHash"] == "sha256:225d22ed09f209b9b6444bbc896bf958049b90fee7889da8c607df5f22327de5"
    enable = window.enable_profile()
    assert enable.EXPECTED_GROUP_REVISION == 54
    assert enable.EXPECTED_BINDING_REVISION == 0


def test_q_preflight_pins_resumed_binding_revision():
    profile = importlib.import_module("a0v_q_product_preflight").load_profile()
    create = {"installationId": "wrong"}
    observed = {"lock_hash": "wrong"}
    binding = {"generation": "wrong", "config_ref": {}, "revision": 6}
    try:
        profile.require_current_head(create, observed, binding, True)
    except ValueError as error:
        assert "fixed resumed Q" in str(error)
    else:
        raise AssertionError("drifted Q target must fail closed")
