from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bc_health_observation.py"


def test_bc_health_observer_is_read_only_and_fixed():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'health.INSTALLATION_ID = "3b895c30-34ca-4710-b978-02645d49c83a"' in source
    assert 'health.OPERATION = "1af66cab-bc7b-4499-97db-194c52181e0d"' in source
    assert "health.ROUTE_REVISION = 135" in source
    assert "health.GROUP_REVISION = 162" in source
    assert "health.DEFINITION_REVISION = 88" in source
    assert "run_definition" not in source
