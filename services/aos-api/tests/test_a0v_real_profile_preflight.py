"""Read-only real-profile gate must never echo launchd secrets or grant action."""

import importlib.util
import json
from pathlib import Path
import plistlib
import sys

import pytest


@pytest.fixture
def preflight():
    root = Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location(
        "a0v_real_profile_preflight_test", root / "scripts/a0v_real_profile_preflight.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _plist(**overrides):
    flags = dict(AOS_QYH_CRON_ENABLED="false",
                 AOS_SNAPSHOT_GROUP_WORKER_ENABLED="false",
                 AOS_EXTENSION_RUNTIME_HOST_ENABLED="0",
                 AOS_DB_MIGRATION_MODE="disabled",
                 AOS_DATABASE_URL="password=never-echo-this-secret")
    flags.update(overrides)
    return plistlib.dumps(dict(Label="com.aos.a0v-api-8080",
                              EnvironmentVariables=flags))


def test_quiesced_flags_are_still_not_a_profile_start_authorization(preflight):
    result = preflight.evaluate(_plist(), launchd_listing="", port_8080_open=False,
                                port_18181_open=False,
                                profile_listing="aos-extension Stopped aarch64",
                                container_policy_proven=False)
    assert result["verdict"] == "STOP"
    assert result["checks"]["container_policy_proven"] is False
    assert all(result["checks"][key] for key in ("cron_disabled", "snapshot_disabled",
        "host_disabled", "migration_disabled", "launchd_quiesced", "port_8080_free",
        "port_18181_free", "profile_stopped"))
    assert "never-echo-this-secret" not in json.dumps(result)
    assert "AOS_DATABASE_URL" not in json.dumps(result)


def test_missing_flag_and_keepalive_service_fail_closed_without_leaking(preflight):
    result = preflight.evaluate(_plist(AOS_QYH_CRON_ENABLED="true"),
        launchd_listing="123 0 com.aos.a0v-api-8080", port_8080_open=True,
        port_18181_open=False, profile_listing="aos-extension Stopped aarch64",
        container_policy_proven=False)
    assert result["verdict"] == "STOP"
    assert result["checks"]["cron_disabled"] is False
    assert result["checks"]["launchd_quiesced"] is False
    assert result["checks"]["port_8080_free"] is False
    assert "never-echo-this-secret" not in json.dumps(result)
    absent = plistlib.loads(_plist())
    del absent["EnvironmentVariables"]["AOS_DB_MIGRATION_MODE"]
    result = preflight.evaluate(plistlib.dumps(absent), launchd_listing="",
        port_8080_open=False, port_18181_open=False,
        profile_listing="aos-extension Stopped aarch64", container_policy_proven=False)
    assert result["checks"]["migration_disabled"] is False


def test_malformed_or_unknown_observations_stop(preflight):
    with pytest.raises(ValueError):
        preflight.evaluate(b"not-a-plist", launchd_listing="", port_8080_open=False,
            port_18181_open=False, profile_listing="aos-extension Stopped aarch64",
            container_policy_proven=False)
    result = preflight.evaluate(_plist(), launchd_listing="unexpected",
        port_8080_open=False, port_18181_open=False,
        profile_listing="default Stopped aarch64", container_policy_proven=False)
    assert result["verdict"] == "STOP"
    assert result["checks"]["profile_stopped"] is False
    wrong_label = plistlib.loads(_plist())
    wrong_label["Label"] = "unrelated-api"
    with pytest.raises(ValueError):
        preflight.evaluate(plistlib.dumps(wrong_label), launchd_listing="",
            port_8080_open=False, port_18181_open=False,
            profile_listing="aos-extension Stopped aarch64", container_policy_proven=False)


def test_observation_error_is_sanitized_at_cli(preflight, monkeypatch, tmp_path, capsys):
    config = tmp_path / "launcher.plist"
    config.write_bytes(_plist())
    monkeypatch.setattr(preflight, "_output",
                        lambda command: (_ for _ in ()).throw(RuntimeError("secret=hidden")))
    monkeypatch.setattr(sys, "argv", ["preflight", "--plist", str(config)])
    assert preflight.main() == 2
    output = capsys.readouterr().out
    assert '"verdict": "STOP"' in output
    assert "secret=hidden" not in output
    assert "never-echo-this-secret" not in output
