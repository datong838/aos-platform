"""The W5c3e wrapper must isolate its identity, key, and private intent."""

import a0v_w5c3e_natural_prepare as wave


def test_configuration_is_exact_and_restored():
    old_state, old_keys, old_load = (
        wave.prior.STATE, wave.prior.KEYS, wave.prior.successor._load)
    with wave._configured():
        assert wave.prior.STATE == wave.STATE
        assert wave.prior.KEYS["prepare"] == wave.KEY
        assert wave.prior.KEYS["verify"] == "w5c3e-verify-not-authorized"
        assert wave.prior.successor._load is wave.clean._load
    assert wave.prior.STATE == old_state
    assert wave.prior.KEYS is old_keys
    assert wave.prior.successor._load is old_load
