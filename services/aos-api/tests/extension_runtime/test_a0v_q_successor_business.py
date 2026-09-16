import importlib
import json

import pytest


def snapshot(module):
    return {"head": {"installation_id": module.Q_ID, "etag_version": 5, "state": "active",
            "lock_hash": module.LOCK, "overlay_revision": "a0v-canonical-ecommerce-v1"},
        "bindings": [{"generation": module.Q_GENERATION, "revision": 4, "execution_epoch": 3,
            "enabled": True, "operation_fence": False, "desired_state": "enabled",
            "observed_state": "ready", "config_ref": module.CONFIG}],
        "resources": [{"cleanup_state": "pending", "observed_release": False} for _ in range(3)],
        "operations": [{"kind": kind, "status": "succeeded"} for kind in
            ("runtime-apply", "runtime-verify", "configure", "enable")],
        "canaryInstallations": 0}


def request_fixture(module, monkeypatch):
    from aos_api.asset_registry.canonical_json import canonical_sha256
    from aos_api.ecommerce_growth_host_composition import ECOMMERCE_GROWTH_OPERATIONS
    authority = {"exact": "p-detach"}
    digest = canonical_sha256(authority)
    monkeypatch.setattr(module, "DETACH_HASH", digest)
    parent = {"receipt_id": module.DETACH, "phase": "detach", "org_id": "org-org",
        "project_id": "dev-project", "authority_data": authority, "content_hash": digest}
    routes = [{"operation_id": operation, "handler_kind": "legacy", "installation_id": None,
        "generation": None, "execution_epoch": None, "operation_fence": True,
        "revision": 29, "cutover_group_revision": 53}
        for operation in sorted(ECOMMERCE_GROWTH_OPERATIONS)]
    request = module.request_from(snapshot(module), parent, routes,
        {"installation_id": module.P_ID, "state": "uninstalled", "etag_version": 6})
    return request, routes, parent


def test_q_successor_requires_exact_p_detach_and_group(monkeypatch):
    module = importlib.import_module("a0v_q_successor_business")
    request, routes, parent = request_fixture(module, monkeypatch)
    assert request.expectedGroupRevision == 53
    assert str(request.registration.installationRef.installation_id) == module.Q_ID
    routes[0]["cutover_group_revision"] = 52
    with pytest.raises(ValueError, match="detached P route group"):
        module.request_from(snapshot(module), parent, routes,
            {"installation_id": module.P_ID, "state": "uninstalled", "etag_version": 6})


def test_q_cutover_target_uses_registration_receipt(monkeypatch):
    successor = importlib.import_module("a0v_q_successor_business")
    cutover = importlib.import_module("a0v_q_successor_cutover")
    request, _routes, _parent = request_fixture(successor, monkeypatch)
    registration = {"outcome": "CURRENT_Q_SUCCESSOR_REGISTERED",
        "request": request.model_dump(mode="json", by_alias=True),
        "receipt": {"receiptId": "receipt", "contentHash": "sha256:" + "1" * 64,
                    "requestHash": request.request_hash()}}
    target, policy = cutover.target(registration)
    assert target["expectedGroupRevision"] == 53
    assert target["targetInstallationId"] == successor.Q_ID
    assert policy["externalEffectsAllowed"] is False


def test_q_cutover_existing_intent_never_resends(monkeypatch, tmp_path):
    cutover = importlib.import_module("a0v_q_successor_cutover")
    monkeypatch.setattr(cutover, "STATE", tmp_path)
    (tmp_path / "prepare-intent.json").write_text(json.dumps({"retained": True}))
    class Plane:
        ecommerce_growth_cutover_service = object()
    with pytest.raises(ValueError, match="never resend"):
        cutover.invoke("prepare", Plane())
