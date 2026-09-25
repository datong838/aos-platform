"""Isolated fleet signature check; a valid signature never grants topology authority."""

from __future__ import annotations

import base64
import binascii
import json
import re

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from a0v_w5c7c_fleet_universe_structure import classify


_DOMAIN = b"AOS-FLEET-UNIVERSE-SIGNATURE-V1\x00"
_KEY_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z")
_ENVELOPE_FIELDS = {"schemaVersion", "keyId", "manifest", "signature"}
_ROOT_FIELDS = {"schemaVersion", "keys"}
_NO_AUTHORITY = {"automaticAction": False, "topologyComplete": False,
                 "closureAuthorized": False}


def signature_message(key_id, manifest):
    """Canonical domain-separated bytes for isolated fleet signing fixtures."""
    if type(key_id) is not str or _KEY_ID.fullmatch(key_id) is None:
        raise ValueError("invalid fleet key ID")
    payload = {"keyId": key_id, "manifest": manifest,
               "schemaVersion": "aos.fleet-signature/v1"}
    return _DOMAIN + json.dumps(payload, sort_keys=True, separators=(",", ":"),
                                ensure_ascii=False, allow_nan=False).encode("utf-8")


def verify(envelope, *, fleet_trust_roots, now, minimum_revision=0):
    """Verify isolated signer identity only; always deny real fleet/closure authority."""
    try:
        if type(envelope) is not dict or set(envelope) != _ENVELOPE_FIELDS:
            raise ValueError("exact envelope required")
        if envelope["schemaVersion"] != "aos.fleet-signature/v1":
            raise ValueError("fleet signature schema required")
        if (type(fleet_trust_roots) is not dict
                or set(fleet_trust_roots) != _ROOT_FIELDS
                or fleet_trust_roots["schemaVersion"] != "aos.fleet-trust-roots/v1"
                or type(fleet_trust_roots["keys"]) is not dict):
            raise ValueError("dedicated fleet trust-root namespace required")
        key_id = envelope["keyId"]
        message = signature_message(key_id, envelope["manifest"])
        public_bytes = fleet_trust_roots["keys"].get(key_id)
        if type(public_bytes) is not bytes or len(public_bytes) != 32:
            raise ValueError("unknown fleet signing key")
        if type(minimum_revision) is not int or minimum_revision < 0:
            raise ValueError("valid revision floor required")
        structure = classify(envelope["manifest"], now=now)
        if structure["outcome"] != "STRUCTURE_ONLY_UNTRUSTED":
            raise ValueError("current fleet structure required")
        if envelope["manifest"]["fleetRevision"] <= minimum_revision:
            raise ValueError("fleet revision rollback or replay")
        encoded = envelope["signature"]
        if type(encoded) is not str or not encoded.isascii():
            raise ValueError("canonical signature required")
        signature = base64.b64decode(encoded, validate=True)
        if len(signature) != 64 or base64.b64encode(signature).decode("ascii") != encoded:
            raise ValueError("canonical Ed25519 signature required")
        Ed25519PublicKey.from_public_bytes(public_bytes).verify(signature, message)
        return {**_NO_AUTHORITY, "outcome": "SIGNATURE_VERIFIED_COVERAGE_UNTRUSTED",
                "reason": "NO_CONTROL_PLANE_COVERAGE_OR_LIVE_CUTOVER_PROOF",
                "fleetRevision": envelope["manifest"]["fleetRevision"]}
    except (binascii.Error, InvalidSignature, KeyError, TypeError, ValueError,
            UnicodeError, OverflowError):
        return {**_NO_AUTHORITY, "outcome": "FROZEN_FLEET_SIGNATURE",
                "reason": "INVALID_OR_UNTRUSTED_FLEET_SIGNING_INPUT"}
