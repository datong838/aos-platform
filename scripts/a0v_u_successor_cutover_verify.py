#!/usr/bin/env python3
"""Read-only exact verification of the U nine-route successor cutover."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/aos-api"))
sys.path.insert(0, str(ROOT / "scripts"))

import a0v_t_interruption_recovery as recovery
import a0v_u_successor_business as successor
import a0v_u_successor_cutover as cutover
from a0v_formal_text_model_renewal import database_connect
from aos_api.ecommerce_growth_host_composition import ECOMMERCE_GROWTH_OPERATIONS
from aos_api.tenant_scope import TenantScope


HOST_STATUS = ROOT.parent / ".aos-recovery-20260917/state/q-advisor-baseline/replacement-t/runtime-host-status.json"
EVIDENCE = ROOT / ".evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/sc4-5l6z-u-successor-cutover-final-state.json"


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def validate(value: dict) -> dict:
    installation = value["installation"]
    head, bindings = installation["head"], installation["bindings"]
    if (
        str(head["installation_id"]) != successor.U_ID
        or head["etag_version"] != 5
        or head["state"] != "active"
        or head["lock_hash"] != successor.LOCK
        or len(bindings) != 1
        or str(bindings[0]["generation"]) != successor.U_GENERATION
        or bindings[0]["revision"] != 6
        or bindings[0]["execution_epoch"] != 3
        or bindings[0]["enabled"] is not True
        or bindings[0]["operation_fence"] is not False
        or bindings[0]["desired_state"] != "enabled"
        or bindings[0]["observed_state"] != "ready"
        or bindings[0]["config_ref"] != successor.CONFIG
        or len(installation["resources"]) != 3
        or any(row["cleanup_state"] != "pending" or row["observed_release"] is not False for row in installation["resources"])
        or len(installation["operations"]) != 4
        or any(row["status"] != "succeeded" for row in installation["operations"])
        or installation["canaryInstallations"] != 0
    ):
        raise ValueError("exact live post-cutover U installation required")
    for label in ("s", "t"):
        old = value[label]
        if (
            old["head"]["state"] != "uninstalled"
            or old["head"]["etag_version"] != 6
            or any(row["cleanup_state"] != "released" or row["observed_release"] is not True for row in old["resources"])
        ):
            raise ValueError(f"exact retired {label.upper()} required")
    database = value["database"]
    routes = database["routes"]
    if (
        len(routes) != len(ECOMMERCE_GROWTH_OPERATIONS)
        or [row["operation_id"] for row in routes] != sorted(ECOMMERCE_GROWTH_OPERATIONS)
        or any(
            row["handler_kind"] != "extension"
            or str(row["installation_id"]) != successor.U_ID
            or str(row["generation"]) != successor.U_GENERATION
            or row["execution_epoch"] != 3
            or row["operation_fence"] is not False
            or row["revision"] != 36
            or row["cutover_group_revision"] != 63
            for row in routes
        )
        or database["inflight"] != {"running": 0, "unresolved": 0, "runtime_pending": 0}
        or database["negativeCanaryInstallations"] != 0
    ):
        raise ValueError("exact U route group and drained tenant required")
    history, registration = value["cutoverHistory"], value["registration"]
    registration_ref = history["activationReceipts"]["prepare"]["registrationReceiptRef"]
    if (
        history["observedStatus"] != "resumed"
        or history["rollbacks"] != []
        or set(history["activationReceipts"]) != {"prepare", "pause", "commit", "validate", "resume"}
        or registration["receipt"]["receiptId"] != registration_ref["resourceId"]
        or registration["receipt"]["contentHash"] != registration_ref["contentHash"]
    ):
        raise ValueError("exact U registration and resumed cutover history required")
    host = value["runtimeHost"]
    targets = host.get("liveTargets") or []
    if (
        host.get("outcome") != "RUNTIME_HOST_ACTIVE"
        or host.get("tenantCount") != 1
        or host.get("canaryTenantCount") != 0
        or value["runtimeHostPidAlive"] is not True
        or len(targets) != 1
        or targets[0].get("installationId") != successor.U_ID
        or targets[0].get("generation") != successor.U_GENERATION
        or targets[0].get("tenant") != ["org-org", "dev-project"]
    ):
        raise ValueError("exact single live U Runtime Host target required")
    return value


def observe() -> dict:
    profile = recovery.load_profile()
    installation = profile.observe_installation(successor.U_ID)
    s = profile.observe_installation(successor.S_ID)
    t = profile.observe_installation(recovery.T_ID)
    with database_connect("aos_meta_head")() as conn:
        routes = [
            dict(row)
            for row in conn.execute(
                """SELECT operation_id,handler_kind,installation_id,generation,
                          execution_epoch,operation_fence,revision,cutover_group_revision
                     FROM extension_operation_dispatch_binding
                    WHERE org_id='org-org' AND project_id='dev-project'
                      AND cutover_group_id=%s ORDER BY operation_id""",
                (successor.GROUP,),
            ).fetchall()
        ]
        inflight = dict(
            conn.execute(
                """SELECT
                  (SELECT count(*) FROM extension_runtime_execution_attempt
                    WHERE org_id='org-org' AND project_id='dev-project' AND state='running') running,
                  (SELECT count(*) FROM automation_occurrence_dispatch_attempt a
                    JOIN automation_occurrence o USING(org_id,project_id,occurrence_id)
                    WHERE a.org_id='org-org' AND a.project_id='dev-project'
                      AND a.status IN ('claimed','unknown')) unresolved,
                  (SELECT count(*) FROM extension_runtime_operation
                    WHERE org_id='org-org' AND project_id='dev-project'
                      AND status NOT IN ('succeeded','failed','cancelled')) runtime_pending"""
            ).fetchone()
        )
        canary = conn.execute(
            "SELECT count(*) AS n FROM bundle_installation WHERE org_id='dev-org' AND project_id='dev-project'"
        ).fetchone()["n"]
    host = json.loads(HOST_STATUS.read_text(encoding="utf-8"))
    value = {
        "outcome": "U_SUCCESSOR_NINE_ROUTE_CUTOVER_GREEN",
        "installation": installation,
        "s": s,
        "t": t,
        "database": {"routes": routes, "inflight": inflight, "negativeCanaryInstallations": canary},
        "registration": json.loads((successor.STATE / "register-result.json").read_text(encoding="utf-8")),
        "cutoverHistory": successor.setup().ecommerce_growth_cutover_service.read_activation_history(
            scope=TenantScope("org-org", "dev-project"),
            installation_id=successor.U_ID,
            idempotency_key=cutover.PREFIX + "-prepare",
            actor=successor.ACTOR,
        ),
        "runtimeHost": host,
        "runtimeHostPidAlive": _pid_alive(host["pid"]),
        "externalEffects": 0,
        "businessRunsResumed": 0,
    }
    return validate(value)


def main() -> None:
    value = observe()
    EVIDENCE.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
