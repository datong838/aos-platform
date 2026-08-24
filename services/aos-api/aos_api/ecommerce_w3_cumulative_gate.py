"""Fail-closed W3 same-release cumulative evidence gate.

The gate evaluates evidence metadata only.  It never starts a task, applies a
migration, flushes a queue, or performs a domain write.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from hashlib import sha256
import json
import re
from typing import Mapping, Sequence


REAL_TENANT = "org-org/dev-project"
ISOLATION_CANARY = "dev-org/dev-project"


class W3CumulativeAxis(StrEnum):
    CONTRACT = "contract"
    STORE = "store"
    API_SDK = "api_sdk"
    WEB = "web"
    BROWSER = "browser"
    SECURITY_TENANT = "security_tenant"
    RECOVERY_REPLAY = "recovery_replay"


class W3CumulativeGateError(ValueError):
    """Raised when cumulative evidence cannot be treated as one green pack."""


@dataclass(frozen=True, slots=True)
class W3ReleaseIdentity:
    git_commit: str
    app_revision: str
    schema_hash: str
    openapi_hash: str
    sdk_hash: str
    web_build_hash: str
    bundle_hash: str
    migration_head: str
    route_hash: str
    cutoff: datetime

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[0-9a-f]{7,40}", self.git_commit):
            raise W3CumulativeGateError("git_commit must be an exact Git revision")
        for name in (
            "schema_hash",
            "openapi_hash",
            "sdk_hash",
            "web_build_hash",
            "bundle_hash",
            "route_hash",
        ):
            if not re.fullmatch(r"sha256:[0-9a-f]{64}", getattr(self, name)):
                raise W3CumulativeGateError(f"{name} must be an exact sha256 ref")
        if not self.app_revision.strip() or not self.migration_head.strip():
            raise W3CumulativeGateError("app_revision and migration_head are required")
        if self.cutoff.utcoffset() is None:
            raise W3CumulativeGateError("release cutoff must include a timezone")

    @property
    def identity_id(self) -> str:
        payload = {
            "appRevision": self.app_revision,
            "bundleHash": self.bundle_hash,
            "cutoff": self.cutoff.isoformat(),
            "gitCommit": self.git_commit,
            "migrationHead": self.migration_head,
            "openapiHash": self.openapi_hash,
            "routeHash": self.route_hash,
            "schemaHash": self.schema_hash,
            "sdkHash": self.sdk_hash,
            "webBuildHash": self.web_build_hash,
        }
        digest = sha256(
            json.dumps(payload, ensure_ascii=True, sort_keys=True).encode("utf-8")
        ).hexdigest()
        return f"w3:{digest}"


@dataclass(frozen=True, slots=True)
class W3AxisEvidence:
    axis: W3CumulativeAxis
    release_identity_id: str
    status: str
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class W3CumulativeEvidencePack:
    release_identity: W3ReleaseIdentity
    axes: tuple[W3AxisEvidence, ...]
    delivery_receipts: Mapping[str, str]
    authority_owners: Mapping[str, str]
    positive_tenant: str
    isolation_tenant: str
    release_applied: bool
    migration_applied: bool
    release_authorization_ref: str | None = None
    external_effect_count: int = 0


@dataclass(frozen=True, slots=True)
class W3CumulativeGateResult:
    status: str
    release_identity_id: str
    axis_count: int
    receipt_count: int
    next_wave_allowed: bool
    operational_release_green: bool


_REQUIRED_RECEIPTS = {"W3-10", "W3-11", "W3-12", "W3-13"}
_REQUIRED_OWNERS = {
    "public_orchestration": "aip.canonical",
    "content_campaign": "workshop.content_campaign",
    "unified_operations": "workshop.operation_case",
    "analyst": "workshop.analyst",
}


def _require_exact_mapping(
    actual: Mapping[str, str], expected: Mapping[str, str], name: str
) -> None:
    if dict(actual) != dict(expected):
        raise W3CumulativeGateError(f"{name} must match the canonical mapping")
    if any(not value.strip() for value in actual.values()):
        raise W3CumulativeGateError(f"{name} values must be non-blank")


def evaluate_w3_cumulative_gate(
    pack: W3CumulativeEvidencePack,
) -> W3CumulativeGateResult:
    """Evaluate a W3 pack without causing an external or domain side effect."""

    if pack.positive_tenant != REAL_TENANT:
        raise W3CumulativeGateError("positive evidence must use the real tenant")
    if pack.isolation_tenant != ISOLATION_CANARY:
        raise W3CumulativeGateError("negative evidence must use the isolation canary")
    if pack.positive_tenant == pack.isolation_tenant:
        raise W3CumulativeGateError("positive and isolation tenants must differ")
    if pack.external_effect_count != 0:
        raise W3CumulativeGateError("the evidence gate must not perform external effects")

    _require_exact_mapping(
        pack.authority_owners, _REQUIRED_OWNERS, "authority_owners"
    )
    if len(set(pack.authority_owners.values())) != len(pack.authority_owners):
        raise W3CumulativeGateError("each authority must retain one distinct owner")

    if set(pack.delivery_receipts) != _REQUIRED_RECEIPTS:
        raise W3CumulativeGateError("all four exact W3 delivery receipts are required")
    if any(not ref.strip() for ref in pack.delivery_receipts.values()):
        raise W3CumulativeGateError("delivery receipt refs must be non-blank")

    expected_axes = set(W3CumulativeAxis)
    actual_axes = [item.axis for item in pack.axes]
    if len(actual_axes) != len(set(actual_axes)) or set(actual_axes) != expected_axes:
        raise W3CumulativeGateError("all seven cumulative axes are required exactly once")

    identity_id = pack.release_identity.identity_id
    for item in pack.axes:
        if item.release_identity_id != identity_id:
            raise W3CumulativeGateError("cross-release evidence cannot be merged")
        if item.status != "GREEN":
            raise W3CumulativeGateError(f"axis {item.axis.value} is not GREEN")
        if not item.evidence_refs or any(not ref.strip() for ref in item.evidence_refs):
            raise W3CumulativeGateError(
                f"axis {item.axis.value} requires exact evidence refs"
            )

    operational_green = pack.release_applied and pack.migration_applied
    if operational_green and not (
        pack.release_authorization_ref and pack.release_authorization_ref.strip()
    ):
        raise W3CumulativeGateError(
            "an operational release claim requires an exact authorization ref"
        )
    if pack.release_applied != pack.migration_applied:
        raise W3CumulativeGateError(
            "release and migration state must not be combined into a partial green"
        )

    return W3CumulativeGateResult(
        status=(
            "CUMULATIVE_RUNTIME_GREEN"
            if operational_green
            else "CUMULATIVE_CODE_BROWSER_GREEN_NO_RELEASE"
        ),
        release_identity_id=identity_id,
        axis_count=len(pack.axes),
        receipt_count=len(pack.delivery_receipts),
        next_wave_allowed=True,
        operational_release_green=operational_green,
    )


def ordered_axis_values() -> Sequence[str]:
    return tuple(axis.value for axis in W3CumulativeAxis)


__all__ = [
    "ISOLATION_CANARY",
    "REAL_TENANT",
    "W3AxisEvidence",
    "W3CumulativeAxis",
    "W3CumulativeEvidencePack",
    "W3CumulativeGateError",
    "W3CumulativeGateResult",
    "W3ReleaseIdentity",
    "evaluate_w3_cumulative_gate",
    "ordered_axis_values",
]
