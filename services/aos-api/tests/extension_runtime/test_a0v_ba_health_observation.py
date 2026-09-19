from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_ba_health_observation.py"


def test_ba_health_observer_is_read_only_and_fixed():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'health.INSTALLATION_ID = "9110f69b-bb31-4d17-98e8-6c5ed1d9234f"' in source
    assert 'health.OPERATION = "82172075-d9ed-428f-8d5e-f201320aba7f"' in source
    assert "health.ROUTE_REVISION = 129" in source
    assert "health.GROUP_REVISION = 156" in source
    assert "health.DEFINITION_REVISION = 82" in source
    assert "run_definition" not in source
