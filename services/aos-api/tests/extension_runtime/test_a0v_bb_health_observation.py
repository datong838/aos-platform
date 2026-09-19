from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bb_health_observation.py"


def test_bb_health_observer_is_read_only_and_fixed():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'health.INSTALLATION_ID = "09752ccf-d51a-44b7-a5bf-62b5ab8ec5d6"' in source
    assert 'health.OPERATION = "c8577eb0-4670-4d37-a509-59dc22759562"' in source
    assert "health.ROUTE_REVISION = 132" in source
    assert "health.GROUP_REVISION = 159" in source
    assert "health.DEFINITION_REVISION = 85" in source
    assert "run_definition" not in source
