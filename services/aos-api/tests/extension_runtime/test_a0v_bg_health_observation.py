from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bg_health_observation.py"


def test_bg_health_observation_is_read_only_and_exact():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'health.OPERATION = "9918bfc6-2b42-4472-a4dd-238c98f05684"' in source
    assert 'health.INSTALLATION_ID = "c52ab6db-176e-4374-9aa9-113f1ed79b5f"' not in source
    assert 'health.INSTALLATION_ID = "c52ab6db-176e-4378-ac88-2ee1bfc58487"' in source
    assert 'health.ROUTE_REVISION = 147' in source
    assert 'health.GROUP_REVISION = 174' in source
    assert 'health.DEFINITION_REVISION = 100' in source
    assert "run_definition" not in source
