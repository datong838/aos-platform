import a0v_w5c3s_cutover_approval_recovery as wave


def test_recovery_temporarily_scopes_owner_to_head():
    old_state, old_key, old_connect = wave.prior.STATE, wave.prior.KEY, wave.aip._web_connection
    with wave._configured():
        assert wave.prior.STATE == wave.STATE
        assert wave.prior.KEY == wave.KEY
        assert wave.aip._web_connection is wave.recovery.head_action_connection
    assert wave.prior.STATE == old_state
    assert wave.prior.KEY == old_key
    assert wave.aip._web_connection is old_connect
