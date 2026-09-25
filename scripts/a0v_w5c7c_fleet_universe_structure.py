"""Pure fleet-inventory shape check; never establishes trusted fleet authority."""

from __future__ import annotations

from datetime import datetime, timedelta
import re


_FIELDS = {"schemaVersion", "controlPlaneId", "fleetRevision", "issuedAt",
           "expiresAt", "members"}
_MEMBER_FIELDS = {"machineId", "launchSurface", "hostId", "databaseRole",
                  "roleOid", "deploymentRevision"}
_IDENTITY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z")


def _text(value):
    return type(value) is str and _IDENTITY.fullmatch(value) is not None


def _time(value):
    if type(value) is not str:
        raise ValueError("timestamp required")
    parsed = datetime.fromisoformat(value)
    if parsed.utcoffset() is None:
        raise ValueError("aware timestamp required")
    return parsed


def classify(manifest, *, now):
    """Reject malformed/self-asserted manifests; valid shape is still untrusted."""
    base = {"automaticAction": False, "topologyComplete": False,
            "closureAuthorized": False}
    try:
        if type(now) is not datetime or now.utcoffset() is None:
            raise ValueError("aware reference time required")
        if type(manifest) is not dict or set(manifest) != _FIELDS:
            raise ValueError("exact manifest fields required")
        if (manifest["schemaVersion"] != "aos.fleet-universe-structure/v1"
                or not _text(manifest["controlPlaneId"])
                or type(manifest["fleetRevision"]) is not int
                or manifest["fleetRevision"] < 1):
            raise ValueError("exact manifest identity required")
        issued, expires = _time(manifest["issuedAt"]), _time(manifest["expiresAt"])
        if not issued <= now < expires or not issued < expires <= issued + timedelta(minutes=10):
            raise ValueError("bounded current manifest window required")
        members = manifest["members"]
        if type(members) is not list or not 1 <= len(members) <= 1024:
            raise ValueError("bounded nonempty members required")
        launches, hosts, roles, role_oids = set(), set(), set(), set()
        for member in members:
            if type(member) is not dict or set(member) != _MEMBER_FIELDS:
                raise ValueError("exact member fields required")
            if (any(not _text(member[name]) for name in _MEMBER_FIELDS - {"roleOid"})
                    or type(member["roleOid"]) is not int or member["roleOid"] < 1):
                raise ValueError("exact member identity required")
            launch = (member["machineId"], member["launchSurface"])
            if (launch in launches or member["hostId"] in hosts
                    or member["databaseRole"] in roles or member["roleOid"] in role_oids):
                raise ValueError("unique launch and Host identity required")
            launches.add(launch)
            hosts.add(member["hostId"])
            roles.add(member["databaseRole"])
            role_oids.add(member["roleOid"])
        return {**base, "outcome": "STRUCTURE_ONLY_UNTRUSTED",
                "reason": "NO_SIGNED_CONTROL_PLANE_COVERAGE_OR_LIVE_CUTOVER_PROOF",
                "memberCount": len(members)}
    except (KeyError, TypeError, ValueError, OverflowError):
        return {**base, "outcome": "FROZEN_FLEET_STRUCTURE",
                "reason": "INVALID_OR_SELF_ASSERTED_INPUT"}
