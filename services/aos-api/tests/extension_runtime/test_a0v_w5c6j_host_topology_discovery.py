"""Local/managed topology signals can only preserve no-effect status."""

import inspect

from a0v_w5c6j_host_topology_discovery import classify, observe


MANAGED = {"outcome": "MANAGED_HOST_DIRECTORY_READ_ONLY_GREEN_INCOMPLETE_TOPOLOGY"}


def _case(*, pids=None, known=0, remote=0, unknown=0, managed=MANAGED):
    return {"knownLauncherPids": [] if pids is None else pids,
            "managedDirectory": managed,
            "databaseSessions": {"knownLoginSessions": known,
                                 "remoteClientSessions": remote,
                                 "unknownClientSessions": unknown}}


def test_zero_local_signals_still_cannot_authorize_full_machine_topology():
    result = classify(_case())
    assert result["outcome"] == "LOCAL_AND_MANAGED_SIGNALS_ONLY_INCOMPLETE_TOPOLOGY"
    assert result["topologyComplete"] is False
    assert result["closureAuthorized"] is False
    assert result["automaticAction"] is False


def test_observed_process_or_remote_session_is_counted_but_never_authorizes():
    result = classify(_case(pids=[17302], known=2, remote=1, unknown=1))
    assert result["outcome"] == "OBSERVED_HOST_OR_SESSION_NO_CLOSURE"
    assert result["knownLauncherCount"] == 1
    assert result["remoteClientSessions"] == 1
    assert result["topologyComplete"] is False
    assert result["closureAuthorized"] is False


def test_missing_or_drifted_input_freezes():
    for value in (_case(managed={"outcome": "FROZEN"}),
                  _case(pids=[1, 1]), _case(known=0, remote=1),
                  {"knownLauncherPids": []}):
        result = classify(value)
        assert result["outcome"] == "FROZEN_HOST_TOPOLOGY_DISCOVERY"
        assert result["closureAuthorized"] is False


def test_observer_only_collects_counts_without_sensitive_output_or_writes():
    body = inspect.getsource(observe)
    assert '["ps", "-axo", "pid=,comm=,args="]' in body
    assert 'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY' in body
    assert 'FROM pg_stat_activity' in body
    assert 'SELECT count(*) AS known_login_sessions' in body
    assert 'query' not in body.lower()
    assert 'DELETE ' not in body and 'UPDATE ' not in body and 'INSERT ' not in body
