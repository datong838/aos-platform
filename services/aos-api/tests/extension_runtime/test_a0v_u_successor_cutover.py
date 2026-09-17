"""U registration and cutover keep the new exact generation and route epoch fixed."""

import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


SCRIPTS = Path(__file__).resolve().parents[4] / "scripts"
sys.path.insert(0, str(SCRIPTS))


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


business = load("a0v_u_successor_business")
cutover = load("a0v_u_successor_cutover")
verify = load("a0v_u_successor_cutover_verify")


def live_snapshot():
    return {
        "head": {
            "installation_id": business.U_ID,
            "etag_version": 5,
            "state": "active",
            "lock_hash": business.LOCK,
            "overlay_revision": "a0v-canonical-ecommerce-v1",
        },
        "bindings": [{
            "generation": business.U_GENERATION,
            "revision": 4,
            "execution_epoch": 3,
            "enabled": True,
            "operation_fence": False,
            "desired_state": "enabled",
            "observed_state": "ready",
            "config_ref": business.CONFIG,
        }],
        "resources": [{"cleanup_state": "pending", "observed_release": False} for _ in range(3)],
        "operations": [{"kind": kind, "status": "succeeded"} for kind in (
            "runtime-apply", "runtime-verify", "configure", "enable"
        )],
        "canaryInstallations": 0,
    }


def parent():
    from aos_api.asset_registry.canonical_json import canonical_sha256

    authority = {"schemaVersion": "test", "phase": "detach"}
    digest = canonical_sha256(authority)
    return {
        "receipt_id": business.DETACH,
        "phase": "detach",
        "org_id": "org-org",
        "project_id": "dev-project",
        "authority_data": authority,
        "content_hash": digest,
    }


def routes():
    from aos_api.ecommerce_growth_host_composition import ECOMMERCE_GROWTH_OPERATIONS

    return [{
        "operation_id": operation,
        "handler_kind": "legacy",
        "installation_id": None,
        "generation": None,
        "execution_epoch": None,
        "operation_fence": True,
        "revision": 35,
        "cutover_group_revision": 62,
    } for operation in sorted(ECOMMERCE_GROWTH_OPERATIONS)]


def build_request(monkeypatch):
    value = parent()
    monkeypatch.setattr(business, "DETACH_HASH", value["content_hash"])
    return business.request_from(
        live_snapshot(), value, routes(),
        {"installation_id": business.S_ID, "state": "uninstalled", "etag_version": 6},
    )


def test_registration_targets_exact_u_and_group_62(monkeypatch):
    request = build_request(monkeypatch)
    assert request.expectedGroupRevision == 62
    assert str(request.registration.installationRef.installation_id) == business.U_ID
    assert str(request.registration.generation) == business.U_GENERATION
    assert request.registration.bindingRevision == 4
    assert request.registration.executionEpoch == 3


@pytest.mark.parametrize("field,value", [
    ("revision", 34),
    ("cutover_group_revision", 61),
    ("operation_fence", False),
])
def test_registration_rejects_route_drift(monkeypatch, field, value):
    actual_parent = parent()
    monkeypatch.setattr(business, "DETACH_HASH", actual_parent["content_hash"])
    changed = routes()
    changed[0][field] = value
    with pytest.raises(ValueError, match="detached S route group"):
        business.request_from(
            live_snapshot(), actual_parent, changed,
            {"installation_id": business.S_ID, "state": "uninstalled", "etag_version": 6},
        )


def test_registration_rejects_released_u_resource(monkeypatch):
    actual_parent = parent()
    monkeypatch.setattr(business, "DETACH_HASH", actual_parent["content_hash"])
    snapshot = live_snapshot()
    snapshot["resources"][0] = {"cleanup_state": "released", "observed_release": True}
    with pytest.raises(ValueError, match="live U"):
        business.request_from(
            snapshot, actual_parent, routes(),
            {"installation_id": business.S_ID, "state": "uninstalled", "etag_version": 6},
        )


def test_cutover_target_uses_fresh_u_namespace(monkeypatch):
    request = build_request(monkeypatch)
    receipt = {"requestHash": request.request_hash(), "receiptId": "receipt-u", "contentHash": "sha256:" + "1" * 64}
    payload, policy = cutover.target({
        "outcome": "CURRENT_U_SUCCESSOR_REGISTERED",
        "request": request.model_dump(mode="json", by_alias=True),
        "receipt": receipt,
    })
    assert payload["expectedGroupRevision"] == 62
    assert payload["targetInstallationId"] == business.U_ID
    assert payload["targetRuntimeRevision"] == 4
    assert policy["externalEffectsAllowed"] is False
    assert policy["fallbackAllowed"] is False
    assert cutover.OPERATION == "8cfc486b-254b-58ce-8211-eac0ec015244"


def test_existing_phase_intent_blocks_resend(tmp_path, monkeypatch):
    monkeypatch.setattr(cutover, "STATE", tmp_path)
    (tmp_path / "prepare-intent.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="inspect history, never resend"):
        cutover.invoke("prepare", SimpleNamespace(ecommerce_growth_cutover_service=object()))


def test_final_verifier_rejects_route_revision_drift():
    source = Path(verify.__file__).read_text(encoding="utf-8")
    assert 'bindings[0]["revision"] != 6' in source
    assert 'row["revision"] != 36' in source
    assert 'row["cutover_group_revision"] != 63' in source
    assert 'database["inflight"] != {"running": 0, "unresolved": 0, "runtime_pending": 0}' in source
