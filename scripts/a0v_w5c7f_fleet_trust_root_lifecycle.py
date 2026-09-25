"""Pure fleet key-window checks; a supplied root snapshot is not an authority."""

from __future__ import annotations

from datetime import datetime
import re

from a0v_w5c7e_fleet_signature_envelope import verify


_ROOT_FIELDS = {"schemaVersion", "snapshotRevision", "keys"}
_KEY_FIELDS = {"keyId", "publicKey", "notBefore", "notAfter", "revokedAt"}
_KEY_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z")
_NO_AUTHORITY = {"automaticAction": False, "topologyComplete": False,
                 "closureAuthorized": False}


def _aware_time(value):
    if type(value) is not str:
        raise ValueError("timestamp required")
    parsed = datetime.fromisoformat(value)
    if parsed.utcoffset() is None:
        raise ValueError("aware timestamp required")
    return parsed


def verify_with_lifecycle(envelope, *, root_snapshot, now,
                          minimum_snapshot_revision=0, minimum_fleet_revision=0):
    """Validate an injected key snapshot and signature; never assert fleet coverage."""
    try:
        if type(now) is not datetime or now.utcoffset() is None:
            raise ValueError("aware clock required")
        if (type(root_snapshot) is not dict or set(root_snapshot) != _ROOT_FIELDS
                or root_snapshot["schemaVersion"] != "aos.fleet-root-snapshot/v1"):
            raise ValueError("dedicated fleet root snapshot required")
        revision = root_snapshot["snapshotRevision"]
        if (type(revision) is not int or type(minimum_snapshot_revision) is not int
                or minimum_snapshot_revision < 0 or revision <= minimum_snapshot_revision):
            raise ValueError("monotonic root snapshot required")
        keys = root_snapshot["keys"]
        if type(keys) is not list or not 1 <= len(keys) <= 128:
            raise ValueError("bounded root entries required")
        if type(envelope) is not dict or type(envelope.get("keyId")) is not str:
            raise ValueError("fleet envelope key required")
        selected = None
        seen = set()
        for key in keys:
            if type(key) is not dict or set(key) != _KEY_FIELDS:
                raise ValueError("exact key entry required")
            key_id = key["keyId"]
            if type(key_id) is not str or _KEY_ID.fullmatch(key_id) is None or key_id in seen:
                raise ValueError("unique fleet key identity required")
            seen.add(key_id)
            public_key = key["publicKey"]
            if type(public_key) is not bytes or len(public_key) != 32:
                raise ValueError("Ed25519 public key required")
            start, end = _aware_time(key["notBefore"]), _aware_time(key["notAfter"])
            revoked = (None if key["revokedAt"] is None
                       else _aware_time(key["revokedAt"]))
            if not start < end:
                raise ValueError("valid key window required")
            if key_id == envelope["keyId"]:
                if not start <= now < end or (revoked is not None and now >= revoked):
                    raise ValueError("expired or revoked fleet key")
                selected = public_key
        if selected is None:
            raise ValueError("unknown fleet key")
        result = verify(
            envelope, fleet_trust_roots={"schemaVersion": "aos.fleet-trust-roots/v1",
                                         "keys": {envelope["keyId"]: selected}},
            now=now, minimum_revision=minimum_fleet_revision)
        if result["outcome"] != "SIGNATURE_VERIFIED_COVERAGE_UNTRUSTED":
            raise ValueError("fleet signature not verified")
        return {**_NO_AUTHORITY, "outcome": "ROOT_WINDOW_AND_SIGNATURE_VALID_UNTRUSTED",
                "reason": "ROOT_SOURCE_AND_FLEET_COVERAGE_UNPROVEN",
                "rootSnapshotRevision": revision,
                "fleetRevision": result["fleetRevision"]}
    except (KeyError, TypeError, ValueError, OverflowError):
        return {**_NO_AUTHORITY, "outcome": "FROZEN_FLEET_ROOT_LIFECYCLE",
                "reason": "INVALID_OR_UNTRUSTED_FLEET_ROOT_INPUT"}
