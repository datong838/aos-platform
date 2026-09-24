"""The third successor must use a separate journal and command prefix."""

import a0v_w5c3h_third_clean_successor as wave


def test_exact_third_successor_configuration_restores():
    old = (wave.prior.STATE, wave.prior.PREFIX)
    with wave._configured():
        assert wave.prior.STATE == wave.STATE
        assert wave.prior.PREFIX == wave.PREFIX
    assert (wave.prior.STATE, wave.prior.PREFIX) == old
