#!/usr/bin/env python3
"""Approve one DS direct successor without runtime or business effects."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from a0v_formal_text_model_renewal import database_connect
import a0v_w5b_ds_settlement as ds
import a0v_w5_ds_replacement_recovery as prior

ROOT = Path(__file__).resolve().parents[1]
STATE = (ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/"
         "20260924-w5c1-direct-successor")
PREFIX = "a0v-w5c1-ds-successor-20260924-v1"
VERSIONS = {
    "domain.ecommerce.core": "1.4.2",
    "platform.ecommerce.niushop": "1.23.2",
    "solution.ecommerce.growth": "1.10.2",
    "solution.ecommerce.operations-base": "1.2.2",
}
GROUP = "6a402d31-83ad-546c-807f-508c87498ce1"
DETACH_OPERATION = "a71ece36-0abd-486e-972e-8bf69628d2ca"
DETACH_HASH = "sha256:85f803080a8d348da90040540c5cc1d3fef48bbee857db3598265eaf0a37dd9c"
FINAL_DISABLE_OPERATION = "245d3953-44e8-4ec8-9fea-7dc178408c2c"


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
        raise ValueError("W5C1_PRIVATE_RESULT_REQUIRED")
    return json.loads(path.read_text())


def preflight():
    from a0v_ecommerce_current_reinstall import replacement_ref

    if prior.replacement.VERSIONS != VERSIONS:
        raise ValueError("W5C1_SIGNED_VERSION_BASELINE_DRIFT")
    for bundle_id, version in VERSIONS.items():
        signature = (prior.canonical.BASE / "bn-canonical-alias-registry/signed-bundles"
                     / bundle_id / version / "bundle.signature.json")
        if not signature.is_file():
            raise ValueError("W5C1_SIGNED_BUNDLE_UNAVAILABLE")
    trust = prior.canonical.TRUST_STATE / "signing/trust-roots.json"
    if not trust.is_file() or trust.stat().st_mode & 0o777 != 0o600:
        raise ValueError("W5C1_TRUST_ROOT_UNAVAILABLE")
    state = ds.snapshot()
    installation = state["installation"]
    predecessor = replacement_ref(installation)
    binding = installation["bindings"]
    if (predecessor != {"installationId": ds.DS_ID, "revision": 5,
                        "lockHash": ds.LOCK,
                        "overlayRevision": "a0v-canonical-ecommerce-v1"}
            or len(binding) != 1 or str(binding[0]["generation"]) != ds.GENERATION
            or (binding[0]["revision"], binding[0]["execution_epoch"]) != (13, 7)
            or binding[0]["config_ref"]["revision"] != 2
            or state["schedules"] != {"total": 12, "enabled": 0}
            or state["activeAttempts"] != 0 or state["canaryBindings"] != 0
            or state["oldDefinition"] is None
            or state["oldDefinition"]["state"] != "disabled"
            or state["newDefinition"] is not None):
        raise ValueError("W5C1_DS_PREDECESSOR_DRIFT")
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        rows = conn.execute("""SELECT handler_kind,installation_id,generation,
          execution_epoch,operation_fence,cutover_group_revision
          FROM extension_operation_dispatch_binding WHERE org_id=%s AND project_id=%s
          AND cutover_group_id=%s""", (*ds.SCOPE.values(), GROUP)).fetchall()
        receipt = conn.execute("""SELECT phase,content_hash FROM extension_dispatch_lifecycle_receipt
          WHERE org_id=%s AND project_id=%s AND runtime_operation_id=%s ORDER BY phase""",
          (*ds.SCOPE.values(), DETACH_OPERATION)).fetchall()
        old_operation = conn.execute("""SELECT status,phase FROM extension_runtime_operation
          WHERE org_id=%s AND project_id=%s AND operation_id=%s""",
          (*ds.SCOPE.values(), DETACH_OPERATION)).fetchone()
        final_disable = conn.execute("""SELECT status,phase FROM extension_runtime_operation
          WHERE org_id=%s AND project_id=%s AND operation_id=%s""",
          (*ds.SCOPE.values(), FINAL_DISABLE_OPERATION)).fetchone()
        gate = conn.execute("""SELECT count(*) AS n FROM extension_dispatch_claim_gate
          WHERE org_id=%s AND project_id=%s AND cutover_group_id=%s""",
          (*ds.SCOPE.values(), GROUP)).fetchone()["n"]
        commands = conn.execute("""SELECT count(*) AS n FROM bundle_installation_command
          WHERE org_id=%s AND project_id=%s AND idempotency_key LIKE %s""",
          (*ds.SCOPE.values(), PREFIX + "-%")).fetchone()["n"]
        canary = conn.execute("""SELECT count(*) AS n FROM bundle_installation
          WHERE org_id='dev-org' AND project_id='dev-project'""").fetchone()["n"]
    if (len(rows) != 9 or any(r["handler_kind"] != "legacy"
            or r["installation_id"] is not None or r["generation"] is not None
            or r["execution_epoch"] is not None or r["operation_fence"] is not True
            or r["cutover_group_revision"] != 365 for r in rows)
            or [r["phase"] for r in receipt] != ["detach", "fence"]
            or receipt[0]["content_hash"] != DETACH_HASH
            or old_operation is None or dict(old_operation) != {"status": "succeeded", "phase": "succeeded"}
            or final_disable is None or dict(final_disable) != {"status": "succeeded", "phase": "succeeded"}
            or gate != 0 or commands != 0 or canary != 0):
        raise ValueError("W5C1_DISPATCH_OR_RECEIPT_DRIFT")
    return {"outcome": "W5C1_PREFLIGHT_GREEN", "predecessor": predecessor,
            "versions": VERSIONS, "detachReceiptHash": receipt[0]["content_hash"],
            "commands": 0, "schedulesEnabled": 0, "activeAttempts": 0, "canary": 0}


def approve():
    if STATE.exists():
        raise ValueError("W5C1_EXISTING_INTENT_RECONCILE_FIRST")
    before = preflight()
    _write("intent", {**before, "prefix": PREFIX, "resend": False})
    from a0v_w5_definition_rebuild import _configure
    _configure()
    installer = prior.replacement.load_profile()._load("a0v_canonical_ecommerce_first_install")
    connect = installer.container_database_connect_factory(
        context="colima-aos-extension", container="aos-a0v-recovery-pg",
        database_name="aos_meta_head")
    result = installer.create_approved_first_installation(
        connect_factory=connect, state_dir=prior.canonical.TRUST_STATE,
        core_version=VERSIONS["domain.ecommerce.core"],
        adapter_version=VERSIONS["platform.ecommerce.niushop"],
        growth_version=VERSIONS["solution.ecommerce.growth"],
        operations_version=VERSIONS["solution.ecommerce.operations-base"],
        idempotency_prefix=PREFIX, current_installation_ref=before["predecessor"])
    _write("result", result)
    return {"outcome": "W5C1_APPROVAL_RETURNED", **result}


def audit():
    result = _load("result")
    intent = _load("intent")
    from a0v_ecommerce_current_reinstall import observe_installation
    installation = observe_installation(result["installationId"])
    before = ds.snapshot()
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        lock = conn.execute("""SELECT l.lock_payload->'currentInstallationRef' AS predecessor,
          l.lock_hash FROM bundle_installation i JOIN bundle_installation_revision r
          ON (r.org_id,r.project_id,r.installation_pk,r.revision)=
             (i.org_id,i.project_id,i.installation_pk,i.current_revision)
          JOIN bundle_composition_lock l ON (l.org_id,l.project_id,l.composition_pk,l.revision)=
             (r.org_id,r.project_id,r.composition_pk,r.lock_revision)
          WHERE i.org_id=%s AND i.project_id=%s AND i.installation_id=%s""",
          (*ds.SCOPE.values(), result["installationId"])).fetchone()
        commands = conn.execute("""SELECT count(*) AS n FROM bundle_installation_command
          WHERE org_id=%s AND project_id=%s AND idempotency_key LIKE %s""",
          (*ds.SCOPE.values(), PREFIX + "-%")).fetchone()["n"]
        routes = conn.execute("""SELECT count(*) AS total,
          count(*) FILTER(WHERE handler_kind='legacy' AND operation_fence
            AND installation_id IS NULL) AS legacy
          FROM extension_operation_dispatch_binding WHERE org_id=%s AND project_id=%s
          AND cutover_group_id=%s""", (*ds.SCOPE.values(), GROUP)).fetchone()
    if (result["installationState"] != "approved" or result["installationEtag"] != 3
            or installation["head"]["state"] != "approved"
            or installation["head"]["etag_version"] != 3
            or installation["bindings"] or installation["operations"] or installation["resources"]
            or len(result["resolved"]) != 4
            or {r["bundleId"]: r["version"] for r in result["resolved"]} != VERSIONS
            or result["moduleCount"] != 8
            or lock is None or lock["predecessor"] != intent["predecessor"]
            or lock["lock_hash"] != result["lockHash"] or commands != 4
            or dict(routes) != {"total": 9, "legacy": 9}
            or before["installation"]["head"]["state"] != "active"
            or before["installation"]["bindings"][0]["revision"] != 13
            or before["schedules"] != {"total": 12, "enabled": 0}
            or before["activeAttempts"] != 0 or before["canaryBindings"] != 0):
        raise ValueError("W5C1_APPROVAL_AUDIT_NOT_GREEN")
    return {"outcome": "W5C1_SUCCESSOR_APPROVED_GREEN",
            "installationId": result["installationId"], "lockHash": result["lockHash"],
            "etag": 3, "resolved": VERSIONS, "businessRuns": 0, "schedulesEnabled": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("preflight", "approve", "audit"))
    print(json.dumps(globals()[parser.parse_args().phase](), ensure_ascii=False, default=str))
