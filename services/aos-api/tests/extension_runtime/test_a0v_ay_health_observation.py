from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[4] / "scripts/a0v_ay_health_observation.py"


def test_ay_health_observer_is_exact_and_read_only():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'health.OPERATION = "fbd3b27a-d802-4ac3-8fd5-0549510e8455"' in source
    assert 'health.INSTALLATION_LABEL = "ay"' in source
    assert "health.ROUTE_REVISION = 126" in source
    assert "health.GROUP_REVISION = 153" in source
    assert "health.DEFINITION_REVISION = 79" in source
    assert 'health.OUTCOME = "AY_HEALTH_OBSERVATION_GREEN"' in source
    assert "run_definition" not in source
    assert "INSERT " not in source and "UPDATE " not in source and "DELETE " not in source
