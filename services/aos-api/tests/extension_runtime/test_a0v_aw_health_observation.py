from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[4] / "scripts/a0v_aw_health_observation.py"


def test_aw_health_observer_is_exact_and_read_only():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'health.OPERATION = "a0c9eed6-ab85-41eb-94e0-7eea26551b64"' in source
    assert 'health.INSTALLATION_LABEL = "aw"' in source
    assert 'health.ROUTE_REVISION = 120' in source
    assert 'health.GROUP_REVISION = 147' in source
    assert 'health.DEFINITION_REVISION = 76' in source
    assert 'health.OUTCOME = "AW_HEALTH_OBSERVATION_GREEN"' in source
    assert "run_definition" not in source
    assert "INSERT " not in source and "UPDATE " not in source and "DELETE " not in source
