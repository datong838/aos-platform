"""W5c3i uses the third installation and never inherits a verify key."""

import a0v_w5c3i_third_natural_prepare as wave


def test_exact_configuration_and_restore():
    old = (wave.prior.STATE, wave.prior.KEYS, wave.prior.successor._load,
           wave.third.prior.STATE)
    with wave._configured():
        assert wave.prior.STATE == wave.STATE
        assert wave.prior.KEYS["prepare"] == wave.KEY
        assert wave.prior.KEYS["verify"] == "w5c3i-verify-not-authorized"
        assert wave.prior.successor._load is wave.third.prior._load
        assert wave.third.prior.STATE == wave.third.STATE
    assert (wave.prior.STATE, wave.prior.KEYS, wave.prior.successor._load,
            wave.third.prior.STATE) == old
