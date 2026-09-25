"""Injected fleet root rotation/revocation checks never establish authority."""

import base64
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from a0v_w5c7e_fleet_signature_envelope import signature_message
from a0v_w5c7f_fleet_trust_root_lifecycle import verify_with_lifecycle


NOW = datetime(2026, 9, 25, 6, 0, tzinfo=timezone.utc)


def _fixture(key_id="fleet-new"):
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    manifest = {
        "schemaVersion": "aos.fleet-universe-structure/v1",
        "controlPlaneId": "isolated-example",
        "fleetRevision": 3,
        "issuedAt": (NOW - timedelta(minutes=1)).isoformat(),
        "expiresAt": (NOW + timedelta(minutes=1)).isoformat(),
        "members": [{"machineId": "machine-1", "launchSurface": "launchd",
                     "hostId": "host-1", "databaseRole": "role_1", "roleOid": 41,
                     "deploymentRevision": "isolated-1"}],
    }
    envelope = {"schemaVersion": "aos.fleet-signature/v1", "keyId": key_id,
                "manifest": manifest,
                "signature": base64.b64encode(private.sign(
                    signature_message(key_id, manifest))).decode("ascii")}
    root = {"keyId": key_id, "publicKey": public,
            "notBefore": (NOW - timedelta(days=1)).isoformat(),
            "notAfter": (NOW + timedelta(days=1)).isoformat(), "revokedAt": None}
    snapshot = {"schemaVersion": "aos.fleet-root-snapshot/v1",
                "snapshotRevision": 2, "keys": [root]}
    return envelope, snapshot


def _frozen(envelope, snapshot, **kwargs):
    assert verify_with_lifecycle(envelope, root_snapshot=snapshot, now=NOW,
                                 **kwargs) == {
        "automaticAction": False, "topologyComplete": False,
        "closureAuthorized": False, "outcome": "FROZEN_FLEET_ROOT_LIFECYCLE",
        "reason": "INVALID_OR_UNTRUSTED_FLEET_ROOT_INPUT"}


def test_valid_injected_root_window_and_signature_still_no_authority():
    envelope, snapshot = _fixture()
    original = deepcopy((envelope, snapshot))
    assert verify_with_lifecycle(envelope, root_snapshot=snapshot, now=NOW,
                                 minimum_snapshot_revision=1,
                                 minimum_fleet_revision=2) == {
        "automaticAction": False, "topologyComplete": False,
        "closureAuthorized": False,
        "outcome": "ROOT_WINDOW_AND_SIGNATURE_VALID_UNTRUSTED",
        "reason": "ROOT_SOURCE_AND_FLEET_COVERAGE_UNPROVEN",
        "rootSnapshotRevision": 2, "fleetRevision": 3}
    assert (envelope, snapshot) == original


def test_rotation_overlap_accepts_exact_old_or_new_key_but_never_authorizes():
    old_envelope, old_snapshot = _fixture("fleet-old")
    new_envelope, new_snapshot = _fixture("fleet-new")
    snapshot = deepcopy(new_snapshot)
    snapshot["keys"].insert(0, old_snapshot["keys"][0])
    for envelope in (old_envelope, new_envelope):
        result = verify_with_lifecycle(envelope, root_snapshot=snapshot, now=NOW)
        assert result["outcome"] == "ROOT_WINDOW_AND_SIGNATURE_VALID_UNTRUSTED"
        assert result["closureAuthorized"] is False
    snapshot["keys"][0]["revokedAt"] = NOW.isoformat()
    _frozen(old_envelope, snapshot)
    assert verify_with_lifecycle(new_envelope, root_snapshot=snapshot,
                                 now=NOW)["outcome"] == "ROOT_WINDOW_AND_SIGNATURE_VALID_UNTRUSTED"


@pytest.mark.parametrize("change", [
    lambda e, s: s.update(schemaVersion="aos.bundle-roots/v1"),
    lambda e, s: s.update(snapshotRevision=True),
    lambda e, s: s.update(keys=[]),
    lambda e, s: s["keys"].append(deepcopy(s["keys"][0])),
    lambda e, s: s["keys"][0].update(publicKey=b"short"),
    lambda e, s: s["keys"][0].update(notBefore=(NOW + timedelta(seconds=1)).isoformat()),
    lambda e, s: s["keys"][0].update(notAfter=NOW.isoformat()),
    lambda e, s: s["keys"][0].update(revokedAt=NOW.isoformat()),
    lambda e, s: s["keys"][0].update(revokedAt=(NOW - timedelta(days=1)).isoformat()),
    lambda e, s: s["keys"][0].update(revokedAt="2026-09-25T06:00:00"),
    lambda e, s: s["keys"][0].update(keyId="other-key"),
    lambda e, s: s["keys"][0].update(extra="self-asserted"),
    lambda e, s: e.update(signature="not-base64!"),
    lambda e, s: e["manifest"].update(topologyComplete=True),
])
def test_invalid_revoked_expired_duplicate_or_tampered_input_freezes(change):
    envelope, snapshot = _fixture()
    change(envelope, snapshot)
    _frozen(envelope, snapshot)


@pytest.mark.parametrize("floor", [2, 3, -1, True])
def test_root_snapshot_replay_or_bad_floor_freezes(floor):
    envelope, snapshot = _fixture()
    _frozen(envelope, snapshot, minimum_snapshot_revision=floor)


def test_fleet_revision_replay_and_naive_clock_freeze():
    envelope, snapshot = _fixture()
    _frozen(envelope, snapshot, minimum_fleet_revision=3)
    result = verify_with_lifecycle(envelope, root_snapshot=snapshot,
                                   now=NOW.replace(tzinfo=None))
    assert result["outcome"] == "FROZEN_FLEET_ROOT_LIFECYCLE"
    assert result["closureAuthorized"] is False
