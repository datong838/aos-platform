from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "scripts"))

import a0v_l_natural_product_event as base
import a0v_l_natural_product_event2 as second


def test_second_natural_window_uses_separate_state_and_policy9():
    original = (base.STATE, base.POLICY_REVISION, base.EXPECTED_BINDING_REVISION)
    try:
        second.configure()
        assert base.STATE.name == "natural-product-event-v2"
        assert base.POLICY_REVISION == 9
        assert base.EXPECTED_BINDING_REVISION == 1
    finally:
        base.STATE, base.POLICY_REVISION, base.EXPECTED_BINDING_REVISION = original


def test_second_natural_executor_has_no_manual_run_call():
    source = Path(second.__file__).read_text()
    assert "/run" not in source
