from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[4] / "scripts/a0v_av_health_observation.py"


def test_av_health_observer_is_exact_and_read_only():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'TARGET_DELTA = 12' in source
    assert '"AV_HEALTH_OBSERVATION_GREEN"' in source
    assert 'BINDING_REVISION = 6' in source and 'EXECUTION_EPOCH = 3' in source
    assert 'ROUTE_REVISION = 117' in source and 'GROUP_REVISION = 144' in source
    assert 'facts["attempts"]' in source and 'facts["canary"] != 0' in source
    assert 'DEFINITION_REVISION = 73' in source
    assert '"store_receipts": 0' in source and '"projection_pending": 0' in source
    assert "run_definition" not in source
    assert "INSERT " not in source and "UPDATE " not in source and "DELETE " not in source
