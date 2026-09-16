import importlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

import pytest


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


def test_q_natural_window_requires_policy12_group55():
    module = importlib.import_module("a0v_q_natural_product_event")
    from aos_api.ecommerce_growth_host_composition import ECOMMERCE_GROWTH_OPERATIONS
    operations = sorted(set(ECOMMERCE_GROWTH_OPERATIONS) | {"ecommerce_growth_event_control"})
    value = {"schedule": {"cron": "0 * * * *", "pipeline_id": "P02-product-qyh",
            "ingest": {"kind": "pipeline-live-v1", "pipelineId": "P02-product-qyh"}},
        "policy": {"current_revision": 12, "enabled": False},
        "binding": {"policy_revision": 12, "installation_id": module.current.Q_ID,
            "generation": module.current.Q_GENERATION, "execution_epoch": 3, "approved": True,
            "enabled": True, "revision": 1,
            "effective_until": datetime.now(timezone.utc) + timedelta(minutes=30)},
        "routes": [{"operation_id": operation, "handler_kind": "extension",
            "installation_id": module.current.Q_ID, "generation": module.current.Q_GENERATION,
            "execution_epoch": 3, "operation_fence": False, "cutover_group_revision": 55}
            for operation in operations],
        "expectedOperations": operations, "inflight": {"running": 0, "unresolved": 0},
        "negativeCanaryDispatch": 0}
    assert module.validate_ready(value)["policy"]["current_revision"] == 12
    value["routes"][0]["cutover_group_revision"] = 54
    with pytest.raises(ValueError, match="exact Q"):
        module.validate_ready(value)
