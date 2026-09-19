from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_be_health_observation.py"


def test_be_health_observer_is_read_only_and_fixed():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'health.INSTALLATION_ID = "1a0f801f-d8f3-43af-a31e-5c9fc8161d6d"' in source
    assert 'health.OPERATION = "93f6b1cd-27bc-4614-8147-143cc95bfcfc"' in source
    assert "health.ROUTE_REVISION = 141" in source
    assert "health.GROUP_REVISION = 168" in source
    assert "health.DEFINITION_REVISION = 94" in source
    assert "run_definition" not in source
