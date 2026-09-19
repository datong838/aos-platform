from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[4] / "scripts/a0v_av_health_observation.py"


def test_av_health_observer_is_exact_and_read_only():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'TARGET_DELTA = 12' in source
    assert '"AV_HEALTH_OBSERVATION_GREEN"' in source
    assert '!= (6, 3)' in source
    assert 'revision=117' in source and 'cutover_group_revision=144' in source
    assert 'facts["attempts"]' in source and 'facts["canary"] != 0' in source
    assert '{"revision": 73, "state": "disabled"}' in source
    assert '"store_receipts": 0' in source and '"projection_pending": 0' in source
    assert "run_definition" not in source
    assert "INSERT " not in source and "UPDATE " not in source and "DELETE " not in source
