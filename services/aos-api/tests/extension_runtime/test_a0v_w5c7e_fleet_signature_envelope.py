"""Isolated signer identity is not Runtime Host fleet or closure authority."""

import base64
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from a0v_w5c7e_fleet_signature_envelope import signature_message, verify


NOW = datetime(2026, 9, 25, 6, 0, tzinfo=timezone.utc)


def _fixture():
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    manifest = {
        "schemaVersion": "aos.fleet-universe-structure/v1",
        "controlPlaneId": "isolated-example",
        "fleetRevision": 2,
        "issuedAt": (NOW - timedelta(minutes=1)).isoformat(),
        "expiresAt": (NOW + timedelta(minutes=1)).isoformat(),
        "members": [{"machineId": "machine-1", "launchSurface": "launchd",
                     "hostId": "host-1", "databaseRole": "role_1", "roleOid": 41,
                     "deploymentRevision": "isolated-1"}],
    }
    key_id = "fleet-isolated-1"
    envelope = {"schemaVersion": "aos.fleet-signature/v1", "keyId": key_id,
                "manifest": manifest,
                "signature": base64.b64encode(private.sign(
                    signature_message(key_id, manifest))).decode("ascii")}
    roots = {"schemaVersion": "aos.fleet-trust-roots/v1", "keys": {key_id: public}}
    return envelope, roots


def _frozen(envelope, roots, **kwargs):
    result = verify(envelope, fleet_trust_roots=roots, now=NOW, **kwargs)
    assert result == {"automaticAction": False, "topologyComplete": False,
                      "closureAuthorized": False, "outcome": "FROZEN_FLEET_SIGNATURE",
                      "reason": "INVALID_OR_UNTRUSTED_FLEET_SIGNING_INPUT"}


def test_valid_isolated_signature_is_still_no_authority_and_does_not_mutate_inputs():
    envelope, roots = _fixture()
    original_envelope, original_roots = deepcopy(envelope), deepcopy(roots)
    assert verify(envelope, fleet_trust_roots=roots, now=NOW, minimum_revision=1) == {
        "automaticAction": False, "topologyComplete": False,
        "closureAuthorized": False, "outcome": "SIGNATURE_VERIFIED_COVERAGE_UNTRUSTED",
        "reason": "NO_CONTROL_PLANE_COVERAGE_OR_LIVE_CUTOVER_PROOF",
        "fleetRevision": 2}
    assert envelope == original_envelope and roots == original_roots


@pytest.mark.parametrize("change", [
    lambda e, r: e["manifest"]["members"][0].update(machineId="machine-2"),
    lambda e, r: e.update(keyId="fleet-isolated-2"),
    lambda e, r: e.update(signature="not-base64!"),
    lambda e, r: e.update(signature=base64.b64encode(b"short").decode("ascii")),
    lambda e, r: e.update(signature=e["signature"] + "="),
    lambda e, r: e.update(schemaVersion="aos.bundle-signature/v1"),
    lambda e, r: e.update(topologyComplete=True),
    lambda e, r: e["manifest"].update(closureAuthorized=True),
    lambda e, r: e["manifest"].update(expiresAt=(NOW - timedelta(seconds=1)).isoformat()),
    lambda e, r: r.update(schemaVersion="aos.bundle-trust-roots/v1"),
    lambda e, r: r["keys"].clear(),
    lambda e, r: r["keys"].update({e["keyId"]: b"short"}),
    lambda e, r: r["keys"].update({e["keyId"]: Ed25519PrivateKey.generate()
                                   .public_key().public_bytes(
                                       encoding=serialization.Encoding.Raw,
                                       format=serialization.PublicFormat.Raw)}),
])
def test_tamper_wrong_key_namespace_expiry_or_self_authority_freezes(change):
    envelope, roots = _fixture()
    change(envelope, roots)
    _frozen(envelope, roots)


@pytest.mark.parametrize("floor", [2, 3, -1, True])
def test_replay_or_invalid_revision_floor_freezes(floor):
    envelope, roots = _fixture()
    _frozen(envelope, roots, minimum_revision=floor)


def test_naive_reference_clock_freezes():
    envelope, roots = _fixture()
    result = verify(envelope, fleet_trust_roots=roots, now=NOW.replace(tzinfo=None))
    assert result["outcome"] == "FROZEN_FLEET_SIGNATURE"
    assert result["closureAuthorized"] is False


def test_no_production_file_network_or_database_imports():
    import a0v_w5c7e_fleet_signature_envelope as module
    from pathlib import Path

    source = Path(module.__file__).read_text(encoding="utf-8")
    assert "AOS_BUNDLE_TRUST_ROOTS_FILE" not in source
    assert "psycopg" not in source and "requests" not in source
