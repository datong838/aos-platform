import importlib
from pathlib import Path

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


def test_exact_versions_and_predecessor_are_frozen(reinstall):
    assert reinstall.VERSIONS == {
        "domain.ecommerce.core": "1.3.0",
        "platform.ecommerce.niushop": "1.22.0",
        "solution.ecommerce.growth": "1.8.0",
        "solution.ecommerce.operations-base": "1.2.0",
    }
    assert reinstall.PREDECESSOR["installationId"] == "97aeb2e7-59ba-40f6-89a3-fb0293bc0497"


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
