"""Protected registration handshake stays read-only and advisory."""

import a0v_w5c5d_registration_handshake as wave


def valid():
    return {"targetDatabase": wave.TARGET_DB,
            "connectorDatabase": wave.TARGET_DB,
            "sessionUser": wave.ROLE, "currentUser": wave.ROLE,
            "roleAfterScope": "aos_runtime",
            "definition": {"revision": 4, "state": "disabled",
                           "content_hash": wave.boundary.HASH},
            "groupCount": 1, "closureReceipts": 0}


def test_exact_handshake_never_authorizes_closure():
    result = wave.classify(valid())
    assert result["outcome"] == "REGISTRATION_CONNECTOR_READ_ONLY_HANDSHAKE_GREEN"
    assert result["automaticAction"] is False
    assert result["closureAuthorized"] is False
    assert result["topologyComplete"] is False


def test_role_database_or_group_drift_freezes():
    for key, wrong in (("targetDatabase", "other"), ("connectorDatabase", "other"),
                       ("sessionUser", "aos_runtime"), ("currentUser", "aos_runtime"),
                       ("roleAfterScope", wave.ROLE), ("groupCount", 0),
                       ("closureReceipts", 1)):
        value = {**valid(), key: wrong}
        assert wave.classify(value)["outcome"] == "FROZEN_REGISTRATION_HANDSHAKE"


def test_definition_drift_or_missing_value_freezes():
    value = valid()
    value["definition"] = {**value["definition"], "state": "enabled"}
    assert wave.classify(value)["outcome"] == "FROZEN_REGISTRATION_HANDSHAKE"
    assert wave.classify({})["outcome"] == "FROZEN_REGISTRATION_HANDSHAKE"


def test_implementation_has_no_closure_call_or_database_write():
    import inspect
    source = inspect.getsource(wave.observe)
    assert "SET TRANSACTION READ ONLY" in source
    assert "pipeline_snapshot_stalled_group_close_a0v_091" not in source
    assert "StalledSnapshotGroupClosureService" not in source
    assert "INSERT INTO" not in source and "UPDATE " not in source and "DELETE FROM" not in source
