"""W5c3j retains the exact prepare identity but uses one new verify key."""

import a0v_w5c3j_third_natural_verify as wave


def test_verify_configuration_restores_prepare_key():
    old = (wave.prepared.prior.STATE, wave.prepared.prior.KEYS,
           wave.prepared.prior.successor._load)
    with wave._configured():
        assert wave.prepared.prior.STATE == wave.prepared.STATE
        assert wave.prepared.prior.KEYS == {"prepare": wave.prepared.KEY,
                                            "verify": wave.KEY}
    assert (wave.prepared.prior.STATE, wave.prepared.prior.KEYS,
            wave.prepared.prior.successor._load) == old
