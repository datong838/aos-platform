"""Known-launcher counting and registration-role advisory remain fail closed."""

import a0v_w5c5c_host_role_topology as wave


BASE = {"outcome": "STALLED_WAIT_24H", "automaticAction": False}
ROLE = {"flags": {"rolcanlogin": True, "rolsuper": False,
                  "rolbypassrls": False, "rolcreaterole": False,
                  "rolcreatedb": False, "rolreplication": False,
                  "rolinherit": False},
        "memberships": ["aos_extension_maintainer", "aos_runtime"],
        "adminOptions": 0}


def test_precise_python_launcher_count_ignores_shell_and_inline_text():
    rows = "\n".join((
        "10 /bin/zsh /bin/zsh -lc python scripts/a0v_ecommerce_runtime_host.py",
        "11 python3.11 python3.11 -c 'scripts/a0v_ecommerce_runtime_host.py'",
        "12 python3.11 python3.11 -u scripts/a0v_ecommerce_runtime_host.py --serve",
        "13 python3.11 python3.11 " + wave.ABS_HOST_SCRIPT + " --serve",
    ))
    assert wave.known_host_pids(rows) == [12, 13]
    assert wave.known_host_pids("10 /bin/zsh /bin/zsh -lc " + wave.HOST_SCRIPT) == []


def test_zero_known_launcher_is_advisory_not_complete():
    result = wave.classify(BASE, [], ROLE)
    assert result["knownHostCount"] == 0
    assert result["automaticAction"] is False
    assert result["topologyComplete"] is False
    assert result["registrationConnectionVerified"] is False


def test_one_or_two_hosts_and_role_drift_freeze():
    for pids in ([12], [12, 13], [12, 12], [0], None):
        assert wave.classify(BASE, pids, ROLE)["outcome"] == "FROZEN_HOST_ROLE_TOPOLOGY"
    for role in ({**ROLE, "memberships": ["aos_runtime"]},
                 {**ROLE, "flags": {**ROLE["flags"], "rolsuper": True}},
                 {**ROLE, "adminOptions": 1}, None):
        assert wave.classify(BASE, [], role)["outcome"] == "FROZEN_HOST_ROLE_TOPOLOGY"


def test_underlying_preflight_drift_freezes():
    assert wave.classify({"outcome": "FROZEN_REAL_CLOSURE_PREFLIGHT"}, [], ROLE)[
        "outcome"] == "FROZEN_HOST_ROLE_TOPOLOGY"
