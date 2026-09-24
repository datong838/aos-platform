#!/usr/bin/env python3
"""Approve one predecessor-free clean successor after formal failed-preparation retirement."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from a0v_formal_text_model_renewal import database_connect
import a0v_w5b_ds_settlement as ds
import a0v_w5c1_successor_approval as previous
import a0v_w5c3b_successor_lifecycle as preparation
import a0v_w5c3c_retire_failed_installation as retired

ROOT = Path(__file__).resolve().parents[1]
STATE = (ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/"
         "20260924-w5c3d-clean-successor")
PREFIX = "a0v-w5c3d-clean-successor-20260924-v1"


def _write(name, value):
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(STATE, 0o700)
    fd = os.open(STATE / (name + ".json"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as output:
        json.dump(value, output, ensure_ascii=False, default=str, indent=2)
        output.write("\n")
        output.flush()
        os.fsync(output.fileno())


def _load(name):
    path = STATE / (name + ".json")
    if not path.is_file() or path.stat().st_mode & 0o777 != 0o600:
        raise ValueError("W5C3D_PRIVATE_RESULT_REQUIRED")
    return json.loads(path.read_text())


def _facts():
    current = ds._current()
    former_id = previous._load("result")["installationId"]
    former = current.observe_installation(former_id)
    old = current.observe_installation(ds.DS_ID)
    host = preparation._host()
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        heads = conn.execute("""SELECT installation_id::text,active_revision
          FROM bundle_installation WHERE org_id=%s AND project_id=%s
          AND installation_id IN (%s,%s)""",
          (*ds.SCOPE.values(), ds.DS_ID, former_id)).fetchall()
        routes = conn.execute("""SELECT count(*) AS total,
          count(*) FILTER(WHERE handler_kind='legacy' AND operation_fence
            AND installation_id IS NULL) AS legacy
          FROM extension_operation_dispatch_binding WHERE org_id=%s AND project_id=%s
          AND cutover_group_id=%s""", (*ds.SCOPE.values(), previous.GROUP)).fetchone()
        schedules = conn.execute("""SELECT count(*) AS total,
          count(*) FILTER(WHERE enabled) AS enabled FROM meta_schedule
          WHERE org_id=%s AND project_id=%s AND pipeline_id IN
          (SELECT pipeline_id FROM pipeline_source_selection_revision WHERE org_id=%s
            AND project_id=%s AND installation_id=%s AND generation=%s)""",
          (*ds.SCOPE.values(), *ds.SCOPE.values(), ds.DS_ID, ds.GENERATION)).fetchone()
        commands = conn.execute("""SELECT count(*) AS n FROM bundle_installation_command
          WHERE org_id=%s AND project_id=%s AND idempotency_key LIKE %s""",
          (*ds.SCOPE.values(), PREFIX + "-%")).fetchone()["n"]
        attempts = conn.execute("""SELECT count(*) AS n FROM extension_runtime_execution_attempt
          WHERE org_id=%s AND project_id=%s AND installation_id IN (%s,%s)""",
          (*ds.SCOPE.values(), ds.DS_ID, former_id)).fetchone()["n"]
        budget = conn.execute("""SELECT r.revision,r.effective_until>clock_timestamp() AS valid
          FROM aip_model_governance_policy_head h JOIN aip_model_governance_policy_revision r
          ON (r.org_id,r.project_id,r.policy_id,r.revision)=
             (h.org_id,h.project_id,h.policy_id,h.current_revision)
          WHERE h.org_id=%s AND h.project_id=%s AND h.policy_id=%s""",
          (*ds.SCOPE.values(), "a0v-ecommerce-budget-policy-v1")).fetchone()
        counts = conn.execute("""SELECT
          (SELECT count(*) FROM pipeline_controlled_source_claim) AS claims,
          (SELECT count(*) FROM meta_schedule_run) AS runs""").fetchone()
    return {"formerId": former_id, "former": former, "old": old,
            "host": host, "heads": [dict(r) for r in heads],
            "routes": dict(routes), "schedules": dict(schedules),
            "commands": commands, "attempts": attempts,
            "budget": dict(budget) if budget else None, "counts": dict(counts)}


def _require(value, *, command_count):
    former = value["former"]
    operations = former["operations"]
    if (value["old"]["head"]["state"] != "uninstalled"
            or former["head"]["state"] != "uninstalled"
            or former["head"]["etag_version"] != 4
            or former["head"]["lock_hash"] != previous._load("result")["lockHash"]
            or len(value["heads"]) != 2
            or any(row["active_revision"] is not None for row in value["heads"])
            or former["bindings"] or len(operations) != 1
            or str(operations[0]["operation_id"]) != retired.OPERATION
            or operations[0]["status"] != "failed"
            or len(former["resources"]) != 3
            or any(r["cleanup_state"] != "released" or r["observed_release"] is not True
                   for r in former["resources"])
            or value["host"]["liveTargets"] != []
            or value["routes"] != {"total": 9, "legacy": 9}
            or value["schedules"] != {"total": 12, "enabled": 0}
            or value["commands"] != command_count or value["attempts"] != 0
            or former["canaryInstallations"] != 0
            or value["budget"] != {"revision": 13, "valid": True}):
        raise ValueError("W5C3D_CLEAN_SUCCESSOR_BASELINE_DRIFT")
    return value


def preflight():
    value = _require(_facts(), command_count=0)
    for bundle_id, version in previous.VERSIONS.items():
        signature = (previous.prior.canonical.BASE /
            "bn-canonical-alias-registry/signed-bundles" / bundle_id / version /
            "bundle.signature.json")
        if not signature.is_file():
            raise ValueError("W5C3D_SIGNED_BUNDLE_MISSING")
    trust = previous.prior.canonical.TRUST_STATE / "signing/trust-roots.json"
    if not trust.is_file() or trust.stat().st_mode & 0o777 != 0o600:
        raise ValueError("W5C3D_TRUST_ROOT_DRIFT")
    return {"outcome": "W5C3D_PREFLIGHT_GREEN", "formerId": value["formerId"],
            "versions": previous.VERSIONS, "hostPid": value["host"]["pid"],
            "counts": value["counts"], "predecessor": None}


def approve():
    if STATE.exists():
        raise ValueError("W5C3D_INTENT_EXISTS_RECONCILE_FIRST")
    before = preflight()
    _write("intent", {**before, "prefix": PREFIX, "resend": False})
    installer = previous.prior.replacement.load_profile()._load(
        "a0v_canonical_ecommerce_first_install")
    connect = installer.container_database_connect_factory(
        context="colima-aos-extension", container="aos-a0v-recovery-pg",
        database_name="aos_meta_head")
    result = installer.create_approved_first_installation(
        connect_factory=connect, state_dir=previous.prior.canonical.TRUST_STATE,
        core_version=previous.VERSIONS["domain.ecommerce.core"],
        adapter_version=previous.VERSIONS["platform.ecommerce.niushop"],
        growth_version=previous.VERSIONS["solution.ecommerce.growth"],
        operations_version=previous.VERSIONS["solution.ecommerce.operations-base"],
        idempotency_prefix=PREFIX, current_installation_ref=None)
    _write("result", result)
    return {"outcome": "W5C3D_APPROVAL_RETURNED", "installationId": result["installationId"],
            "lockHash": result["lockHash"], "installationState": result["installationState"]}


def audit():
    intent, result = _load("intent"), _load("result")
    baseline = _require(_facts(), command_count=4)
    new = ds._current().observe_installation(result["installationId"])
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        lock = conn.execute("""SELECT l.lock_payload->'currentInstallationRef' AS predecessor,
          l.lock_hash FROM bundle_installation i JOIN bundle_installation_revision r
          ON (r.org_id,r.project_id,r.installation_pk,r.revision)=
             (i.org_id,i.project_id,i.installation_pk,i.current_revision)
          JOIN bundle_composition_lock l
          ON (l.org_id,l.project_id,l.composition_pk,l.revision)=
             (r.org_id,r.project_id,r.composition_pk,r.lock_revision)
          WHERE i.org_id=%s AND i.project_id=%s AND i.installation_id=%s""",
          (*ds.SCOPE.values(), result["installationId"])).fetchone()
    if (result["installationState"] != "approved"
            or result["installationEtag"] != 3
            or result["moduleCount"] != 8
            or {r["bundleId"]: r["version"] for r in result["resolved"]} != previous.VERSIONS
            or new["head"]["state"] != "approved" or new["head"]["etag_version"] != 3
            or new["head"]["lock_hash"] != result["lockHash"]
            or new["bindings"] or new["operations"] or new["resources"]
            or new["canaryInstallations"] != 0
            or lock is None or lock["predecessor"] is not None
            or lock["lock_hash"] != result["lockHash"]
            or baseline["host"]["pid"] != intent["hostPid"]
            or baseline["counts"] != intent["counts"]):
        raise ValueError("W5C3D_CLEAN_SUCCESSOR_AUDIT_NOT_GREEN")
    return {"outcome": "W5C3D_CLEAN_SUCCESSOR_APPROVED_GREEN",
            "installationId": result["installationId"], "lockHash": result["lockHash"],
            "etag": 3, "predecessor": None, "hostPid": intent["hostPid"],
            "routesLegacy": 9, "schedulesEnabled": 0, "canary": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("preflight", "approve", "audit"))
    print(json.dumps(globals()[parser.parse_args().phase](), ensure_ascii=False, default=str))
