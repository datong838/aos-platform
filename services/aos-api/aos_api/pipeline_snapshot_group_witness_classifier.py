"""Bounded read-only classification of one historical group; no write authority."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from uuid import UUID

from aos_api.pipeline_snapshot_group_canonical_witness import reconstruct_witness
from aos_api.tenant_scope import TenantScope


class GroupWitnessStatus(str, Enum):
    READY_CANDIDATE = "READY_CANDIDATE"
    MISSING_GROUP = "MISSING_GROUP"
    MISSING_INPUT = "MISSING_INPUT"
    HASH_DRIFT = "HASH_DRIFT"
    MEMBER_DRIFT = "MEMBER_DRIFT"


@dataclass(frozen=True)
class GroupWitnessClassification:
    group_id: UUID
    status: GroupWitnessStatus


def _single(row):
    return next(iter(row.values())) if isinstance(row, Mapping) else row[0]


def classify_rows(group_id: UUID, claim: Mapping | None, input_row: Mapping | None,
                  members: tuple[tuple[int, str], ...]) -> GroupWitnessStatus:
    """Classify already-read rows without returning source or authorization material."""
    if type(group_id) is not UUID or type(members) is not tuple:
        raise TypeError("exact historical group and bounded rows required")
    if claim is None:
        return GroupWitnessStatus.MISSING_GROUP
    if input_row is None:
        return GroupWitnessStatus.MISSING_INPUT
    if input_row["request_hash"] != claim["request_hash"]:
        return GroupWitnessStatus.HASH_DRIFT
    try:
        reconstruct_witness(claim["binding"], claim["request_hash"],
                            input_row["manifest"], input_row["manifest_hash"])
    except (ValueError, KeyError, TypeError):
        return GroupWitnessStatus.HASH_DRIFT
    binding = claim["binding"]
    manifest = input_row["manifest"]
    bound = binding.get("members")
    leaves = manifest.get("members")
    if (set(binding) != {"schemaVersion", "orgId", "projectId", "groupId", "actor", "members"}
            or binding.get("schemaVersion") != "aos.snapshot-group-claim/v1"
            or (binding.get("orgId"), binding.get("projectId"))
                != (claim.get("org_id"), claim.get("project_id"))
            or set(manifest) != {"members"}
            or binding.get("groupId") != str(group_id)
            or binding.get("actor") != claim["actor"]
            or type(bound) is not list or type(leaves) is not list
            or type(claim["member_count"]) is not int
            or not 1 <= claim["member_count"] <= 12
            or len(bound) != claim["member_count"]
            or len(leaves) != claim["member_count"]
            or len(members) != claim["member_count"]
            or len(members) > 12):
        return GroupWitnessStatus.MEMBER_DRIFT
    try:
        expected = tuple((ordinal, item["runId"]) for ordinal, item in enumerate(bound, 1))
        leaf_runs = tuple(item["runId"] for item in leaves)
    except (TypeError, KeyError):
        return GroupWitnessStatus.MEMBER_DRIFT
    if (members != expected or leaf_runs != tuple(run for _, run in expected)
            or len(set(leaf_runs)) != len(leaf_runs)):
        return GroupWitnessStatus.MEMBER_DRIFT
    return GroupWitnessStatus.READY_CANDIDATE


def classify_group(conn, scope: TenantScope, group_id: UUID) -> GroupWitnessClassification:
    if type(scope) is not TenantScope or type(group_id) is not UUID:
        raise TypeError("exact historical tenant and group required")
    identity = conn.execute("""SELECT current_user AS role,
        current_setting('aos.org_id',true) AS org_id,
        current_setting('aos.project_id',true) AS project_id""").fetchone()
    if (identity["role"], identity["org_id"], identity["project_id"]) != ("aos_runtime", *scope.key):
        raise PermissionError("READ_ONLY_TENANT_BOUNDARY_REQUIRED")
    if (_single(conn.execute("SHOW transaction_read_only").fetchone()) != "on"
            or _single(conn.execute("SHOW transaction_isolation").fetchone()) != "repeatable read"):
        raise ValueError("READ_ONLY_REPEATABLE_READ_REQUIRED")
    claim = conn.execute("""SELECT org_id,project_id,actor,member_count,binding,request_hash
        FROM public.pipeline_snapshot_group_claim
        WHERE org_id=%s AND project_id=%s AND group_id=%s""",
        (*scope.key, group_id)).fetchone()
    input_row = conn.execute("""SELECT manifest,manifest_hash,request_hash
        FROM public.pipeline_snapshot_group_input
        WHERE org_id=%s AND project_id=%s AND group_id=%s""",
        (*scope.key, group_id)).fetchone()
    member_rows = conn.execute("""SELECT ordinal,run_id
        FROM public.pipeline_snapshot_group_member
        WHERE org_id=%s AND project_id=%s AND group_id=%s
        ORDER BY ordinal LIMIT 13""", (*scope.key, group_id)).fetchall()
    members = tuple((row["ordinal"], row["run_id"]) for row in member_rows)
    return GroupWitnessClassification(group_id, classify_rows(group_id, claim, input_row, members))
