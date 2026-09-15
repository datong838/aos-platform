import importlib
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest


@pytest.fixture
def reinstall(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[4] / "scripts"))
    return importlib.import_module("a0v_ecommerce_current_reinstall")


def snapshot(*, state="active", etag=5, enabled=True, fenced=False, resources=True):
    bindings = [] if state in {"approved", "applied"} else [{
        "generation": "generation-a",
        "revision": 7,
        "enabled": enabled,
        "operation_fence": fenced,
    }]
    return {
        "head": {"state": state, "etag_version": etag},
        "bindings": bindings,
        "resources": ([{"cleanup_state": "released", "observed_release": True}] if resources else []),
        "canaryInstallations": 0,
    }


def predecessor_snapshot(reinstall):
    return {
        "head": {
            "installation_id": UUID(reinstall.PREDECESSOR["installationId"]),
            "etag_version": 5,
            "state": "active",
            "lock_hash": reinstall.PREDECESSOR["lockHash"],
            "overlay_revision": reinstall.PREDECESSOR["overlayRevision"],
        },
        "bindings": [{
            "generation": reinstall.PREDECESSOR_GENERATION,
            "revision": 5,
            "execution_epoch": 4,
            "enabled": False,
            "operation_fence": True,
            "desired_state": "enabled",
            "observed_state": "unknown",
        }],
        "operations": [{"status": "succeeded"}],
        "resources": [{"cleanup_state": "released", "observed_release": True}],
        "canaryInstallations": 0,
    }


def test_exact_versions_and_predecessor_are_frozen(reinstall):
    assert reinstall.VERSIONS == {
        "domain.ecommerce.core": "1.3.0",
        "platform.ecommerce.niushop": "1.23.0",
        "solution.ecommerce.growth": "1.8.0",
        "solution.ecommerce.operations-base": "1.2.0",
    }
    assert reinstall.PREDECESSOR["installationId"] == "97aeb2e7-59ba-40f6-89a3-fb0293bc0497"
    assert "signed-bundles-niushop-1.23-current" in str(reinstall.BUNDLE_ROOT)


def test_lifecycle_requires_exact_owner_phases(reinstall):
    assert reinstall.require_phase("prepare", snapshot(state="approved", etag=3)) == {
        "etag": 3, "kind": "runtime-apply"
    }
    assert reinstall.require_phase("verify", snapshot(state="applied", etag=4)) == {
        "etag": 4, "kind": "runtime-verify"
    }
    for state, etag in (("approved", 4), ("applied", 3), ("active", 5)):
        with pytest.raises(ValueError):
            reinstall.require_phase("prepare", snapshot(state=state, etag=etag))


def test_disable_and_uninstall_require_distinct_runtime_states(reinstall):
    command = reinstall.require_phase("disable", snapshot())
    assert command == {"etag": 5, "generation": "generation-a", "bindingRevision": 7}
    with pytest.raises(ValueError, match="enabled unfenced"):
        reinstall.require_phase("disable", snapshot(enabled=False, fenced=True))
    command = reinstall.require_phase(
        "uninstall", snapshot(enabled=False, fenced=True)
    )
    assert command["generation"] == "generation-a"
    with pytest.raises(ValueError, match="released resources"):
        reinstall.require_phase(
            "uninstall", snapshot(enabled=False, fenced=True, resources=False)
        )


def test_every_phase_fails_closed_on_canary_installation(reinstall):
    value = snapshot(state="approved", etag=3)
    value["canaryInstallations"] = 1
    with pytest.raises(ValueError, match="canary"):
        reinstall.require_phase("prepare", value)


def test_freeze_is_exclusive_and_private(reinstall, tmp_path):
    target = tmp_path / "intent.json"
    reinstall._freeze(target, {"command": "once"})
    assert target.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        reinstall._freeze(target, {"command": "twice"})


def test_matching_failed_intent_can_be_reused_without_replacement(reinstall, tmp_path):
    target = tmp_path / "intent.json"
    reinstall._freeze_or_match(target, {"command": "same"})
    first = target.read_bytes()
    reinstall._freeze_or_match(target, {"command": "same"})
    assert target.read_bytes() == first
    with pytest.raises(ValueError, match="differs"):
        reinstall._freeze_or_match(target, {"command": "changed"})


def test_predecessor_drain_requires_exact_restart_state(reinstall):
    value = predecessor_snapshot(reinstall)
    assert reinstall.require_predecessor_drain(value) == {
        "etag": 5,
        "generation": reinstall.PREDECESSOR_GENERATION,
        "bindingRevision": 5,
    }
    for field, changed in (
        ("desired_state", "disabled"),
        ("observed_state", "ready"),
        ("revision", 6),
        ("execution_epoch", 5),
        ("enabled", True),
        ("operation_fence", False),
    ):
        drifted = predecessor_snapshot(reinstall)
        drifted["bindings"][0][field] = changed
        with pytest.raises(ValueError, match="restart state"):
            reinstall.require_predecessor_drain(drifted)
    unresolved = predecessor_snapshot(reinstall)
    unresolved["operations"][0]["status"] = "accepted"
    with pytest.raises(ValueError, match="unresolved"):
        reinstall.require_predecessor_drain(unresolved)


def test_final_disable_uses_distinct_intent_and_idempotency_key(
    reinstall, monkeypatch, tmp_path
):
    calls = []

    class Service:
        def request(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(response_json={"operationId": "operation-final"}, replayed=False)

    monkeypatch.setattr(reinstall, "STATE", tmp_path)
    monkeypatch.setattr(reinstall, "_initial", lambda label: {"installationId": "installation-a"})
    monkeypatch.setattr(reinstall, "observe_installation", lambda installation_id: snapshot())
    monkeypatch.setattr(
        reinstall,
        "_setup_runtime_plane",
        lambda: (
            SimpleNamespace(ACTOR="actor", ROLES={"admin"}, MARKINGS=set()),
            object(),
            object(),
            Service(),
            object(),
        ),
    )
    result = reinstall.disable("a", suffix="disable-final")
    assert result["receipt"]["operationId"] == "operation-final"
    assert (tmp_path / "a/disable-final-intent.json").is_file()
    assert len(calls) == 1
    assert calls[0]["idempotency_key"] == "a0v-current-ecommerce-a-disable-final-20260915"


def test_stale_enable_cancel_requires_one_exact_expired_operation(reinstall):
    value = snapshot(enabled=False, fenced=True)
    value["bindings"][0].update({
        "execution_epoch": 2,
        "desired_state": "disabled",
        "observed_state": "unknown",
        "revision": 3,
        "config_ref": {"configurationId": "configuration-a"},
    })
    value["operations"] = [{
        "operation_id": "operation-a",
        "kind": "enable",
        "status": "accepted",
        "phase": "accepted",
        "deadline_expired": True,
    }]
    assert reinstall.require_stale_enable_cancel(
        value, expected_operation_id="operation-a"
    )["bindingRevision"] == 3
    for field, changed in (
        ("operation_id", "operation-b"),
        ("kind", "configure"),
        ("status", "running"),
        ("phase", "validating"),
        ("deadline_expired", False),
    ):
        drifted = {**value, "operations": [{**value["operations"][0], field: changed}]}
        with pytest.raises(ValueError, match="exact expired enable"):
            reinstall.require_stale_enable_cancel(
                drifted, expected_operation_id="operation-a"
            )


def test_unowned_recovery_cancel_requires_released_runtime(reinstall):
    value = snapshot(enabled=False, fenced=True)
    value["bindings"][0].update({
        "execution_epoch": 3,
        "desired_state": "disabled",
        "observed_state": "unknown",
        "revision": 5,
        "config_ref": {"configurationId": "configuration-a"},
    })
    value["operations"] = [{
        "operation_id": "operation-recovery",
        "kind": "enable",
        "status": "accepted",
        "phase": "accepted",
        "deadline_expired": False,
    }]
    result = reinstall.require_unowned_recovery_cancel(
        value, expected_operation_id="operation-recovery"
    )
    assert result["bindingRevision"] == 5
    live = {**value, "resources": [{"cleanup_state": "leased", "observed_release": False}]}
    with pytest.raises(ValueError, match="released resources"):
        reinstall.require_unowned_recovery_cancel(
            live, expected_operation_id="operation-recovery"
        )


def test_released_owner_settlement_requires_cleanup_and_no_pending_operation(reinstall):
    value = snapshot(enabled=False, fenced=True)
    value["bindings"][0].update({
        "desired_state": "enabled",
        "observed_state": "unknown",
        "config_ref": {"configurationId": "configuration-c"},
    })
    value["operations"] = [{"status": "succeeded"}]
    assert reinstall.require_released_owner_settlement(value) == {
        "etag": 5,
        "generation": "generation-a",
        "bindingRevision": 7,
    }
    unresolved = {**value, "operations": [{"status": "accepted"}]}
    with pytest.raises(ValueError, match="unresolved"):
        reinstall.require_released_owner_settlement(unresolved)
    live = {**value, "resources": [{"cleanup_state": "pending", "observed_release": False}]}
    with pytest.raises(ValueError, match="resources"):
        reinstall.require_released_owner_settlement(live)


def test_replacement_requires_exact_drained_predecessor(reinstall):
    value = predecessor_snapshot(reinstall)
    value["head"].update({
        "installation_id": UUID("00000000-0000-0000-0000-00000000000a"),
        "lock_hash": "sha256:" + "b" * 64,
        "overlay_revision": "overlay-a",
    })
    value["bindings"][0].update({
        "desired_state": "disabled",
        "revision": 7,
        "execution_epoch": 4,
    })
    assert reinstall.replacement_ref(value) == {
        "installationId": "00000000-0000-0000-0000-00000000000a",
        "revision": 5,
        "lockHash": "sha256:" + "b" * 64,
        "overlayRevision": "overlay-a",
    }
    value["operations"][0]["status"] = "accepted"
    with pytest.raises(ValueError, match="unresolved"):
        reinstall.replacement_ref(value)


def test_installation_e_is_an_allowed_exact_label(reinstall, monkeypatch, tmp_path):
    monkeypatch.setattr(reinstall, "STATE", tmp_path)
    (tmp_path / "e").mkdir()
    (tmp_path / "e/create-result.json").write_text(
        '{"installationId":"installation-e"}', encoding="utf-8"
    )
    assert reinstall._initial("e") == {"installationId": "installation-e"}
    with pytest.raises(ValueError, match="exact install label"):
        reinstall._initial("f")


def test_replacement_installations_use_the_immediate_drained_generation(reinstall):
    assert reinstall.replacement_predecessor_label("b") == "a"
    assert reinstall.replacement_predecessor_label("d") == "c"
    assert reinstall.replacement_predecessor_label("e") == "d"
    with pytest.raises(ValueError, match="replacement install label"):
        reinstall.replacement_predecessor_label("c")
