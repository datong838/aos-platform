"""W5c3f targets only the second failed installation with a fresh key."""

import a0v_w5c3f_retire_failed_installation as wave


def test_exact_retarget_and_restore():
    old = (wave.prior.STATE, wave.prior.KEY, wave.prior.OPERATION,
           wave.prior.successor._load)
    with wave._configured():
        assert wave.prior.STATE == wave.STATE
        assert wave.prior.KEY == wave.KEY
        assert wave.prior.OPERATION == wave.OPERATION
        assert wave.prior.successor._load is wave.clean._load
    assert (wave.prior.STATE, wave.prior.KEY, wave.prior.OPERATION,
            wave.prior.successor._load) == old
