"""Pure rollout gap classifier; self-attested readiness never grants authority."""

from __future__ import annotations


_GATES = (
    ("controlPlaneSigned", "CONTROL_PLANE_SIGNATURE_UNPROVEN"),
    ("rootProvenanceVerified", "FLEET_ROOT_PROVENANCE_UNPROVEN"),
    ("assetDeploymentCoveringAllMachines", "FLEET_ASSET_DEPLOYMENT_COVERAGE_UNPROVEN"),
    ("allLaunchSurfacesManaged", "UNMANAGED_LAUNCH_SURFACE_NOT_EXCLUDED"),
    ("oldCredentialsRevoked", "OLD_HOST_RESTART_AUTHORITY_NOT_REVOKED"),
    ("perNodeStopAckComplete", "PER_NODE_STOP_ACK_INCOMPLETE"),
    ("dbMigrationVerified", "REAL_DB_FENCE_MIGRATION_UNVERIFIED"),
    ("allWorkerTransactionalFencesVerified", "WORKER_TRANSACTION_FENCE_UNVERIFIED"),
    ("freshOwnerPlanAndKeyVerified", "FRESH_OWNER_CLOSURE_PLAN_KEY_UNVERIFIED"),
)
_FIELDS = {name for name, _ in _GATES} | {"physicalSecondHostCount"}
_NO_AUTHORITY = {"automaticAction": False, "topologyComplete": False,
                 "closureAuthorized": False}


def classify(evidence):
    """Explain rejected gates without ever interpreting caller booleans as proof."""
    if (type(evidence) is not dict or set(evidence) != _FIELDS
            or any(type(evidence[name]) is not bool for name, _ in _GATES)
            or type(evidence["physicalSecondHostCount"]) is not int
            or evidence["physicalSecondHostCount"] < 0):
        return {**_NO_AUTHORITY, "outcome": "FROZEN_ROLLOUT_EVIDENCE",
                "reason": "INVALID_OR_EXTRA_SELF_ASSERTED_INPUT"}
    missing = [reason for name, reason in _GATES if not evidence[name]]
    if evidence["physicalSecondHostCount"] != 0:
        missing.append("PHYSICAL_SECOND_HOST_NOT_ZERO")
    if missing:
        return {**_NO_AUTHORITY, "outcome": "ROLLOUT_REJECTED_UNPROVEN_GATES",
                "missingGates": missing}
    return {**_NO_AUTHORITY, "outcome": "SELF_ASSERTED_READY_NO_AUTHORITY",
            "reason": "NO_INDEPENDENT_CONTROL_PLANE_OR_LIVE_OWNER_PROOF"}
