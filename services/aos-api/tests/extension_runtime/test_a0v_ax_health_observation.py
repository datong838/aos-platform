from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[4] / "scripts/a0v_ax_health_observation.py"


def test_ax_health_observer_is_exact_and_read_only():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'health.OPERATION = "0381b883-b37e-4559-900c-805265ab3891"' in source
    assert 'health.INSTALLATION_LABEL = "ax"' in source
    assert 'health.ROUTE_REVISION = 123' in source
    assert 'health.GROUP_REVISION = 150' in source
    assert 'health.DEFINITION_REVISION = 76' in source
    assert 'health.OUTCOME = "AX_HEALTH_OBSERVATION_GREEN"' in source
    assert "run_definition" not in source
    assert "INSERT " not in source and "UPDATE " not in source and "DELETE " not in source
