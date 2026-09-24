"""The recovered stage uses a distinct journal and key."""

import a0v_w5c3kr_config_stage_recovery as wave


def test_configuration_is_distinct_and_restored():
    old = (wave.prior.STATE, wave.prior.KEY)
    with wave._configured():
        assert wave.prior.STATE == wave.STATE
        assert wave.prior.KEY == wave.KEY
    assert (wave.prior.STATE, wave.prior.KEY) == old
