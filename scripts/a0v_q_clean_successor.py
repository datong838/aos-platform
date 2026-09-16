"""Create and activate clean Q only after the exact P terminal state."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from uuid import UUID

import a0v_o_recovery as recovery
import a0v_ecommerce_transaction_reinstall as transaction


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT.parent / ".aos-recovery-20260917/state/q-clean-successor"
Q_DIR = STATE / "q"
P_ID = "9950e057-5cb4-4849-a499-35837d8d0fb6"
P_GENERATION = "df883b18-0170-410b-8424-442c7cdd60b4"
P_RUNTIME_OPERATION = "92809daf-2988-421f-a2f5-dece5bdb75e3"
P_DETACH = "b2297c08-f8a2-45c3-9f5c-60a66040a1c8"
P_DETACH_HASH = "sha256:19b589d3468a3f56cc02452531cf868111391beb4b04556fda38862350ec8de4"
GROUP = "6a402d31-83ad-546c-807f-508c87498ce1"
SCHEDULE = "sch-p02-qyh-controlled-20260913-v1"
PREFIX = "a0v-qyh-clean-generation-q-20260917"
ACTIONS = ("preflight", "create-q", "prepare-q", "verify-q", "stage-q",
           "configure-q", "enable-q", "observe")


def profile():
    current = recovery.current()
    current.STATE = STATE

    def initial(label: str):
        if label != "q":
            raise ValueError("only fixed Q label is allowed")
        value = json.loads((Q_DIR / "create-result.json").read_text(encoding="utf-8"))
        identity = value.get("installationId")
        if not isinstance(identity, str) or str(UUID(identity)) != identity:
            raise ValueError("canonical Q installation required")
        return value

    current._initial = initial
    return current


def _database_snapshot() -> dict:
    from a0v_formal_text_model_renewal import database_connect
    from aos_api.ecommerce_growth_host_composition import ECOMMERCE_GROWTH_OPERATIONS
    with database_connect("aos_meta_head")() as conn:
        routes = [dict(row) for row in conn.execute("""SELECT operation_id,handler_kind,
          installation_id::text,generation::text,execution_epoch,operation_fence,revision,
          cutover_group_revision FROM extension_operation_dispatch_binding
          WHERE org_id='org-org' AND project_id='dev-project' AND cutover_group_id=%s
          ORDER BY operation_id""", (GROUP,)).fetchall()]
        detach = conn.execute("""SELECT receipt_id::text,phase,content_hash,authority_data
          FROM extension_dispatch_lifecycle_receipt WHERE org_id='org-org' AND project_id='dev-project'
          AND runtime_operation_id=%s AND phase='detach'""", (P_RUNTIME_OPERATION,)).fetchone()
        schedule = conn.execute("""SELECT enabled,last_run FROM meta_schedule
          WHERE org_id='org-org' AND project_id='dev-project' AND id=%s""", (SCHEDULE,)).fetchone()
        safety = dict(conn.execute("""SELECT
          (SELECT count(*) FROM extension_runtime_execution_attempt WHERE org_id='org-org'
            AND project_id='dev-project' AND state='running') running,
          (SELECT count(*) FROM automation_occurrence_dispatch_attempt a JOIN automation_occurrence o
            USING(org_id,project_id,occurrence_id) WHERE a.org_id='org-org' AND a.project_id='dev-project'
            AND a.status IN ('claimed','unknown')) unresolved,
          (SELECT count(*) FROM bundle_installation WHERE org_id='dev-org'
            AND project_id='dev-project') canary""").fetchone())
    snapshot = {"routes": routes, "detach": None if detach is None else dict(detach),
                "schedule": None if schedule is None else dict(schedule), "safety": safety}
    return _validate_database_snapshot(snapshot, set(ECOMMERCE_GROWTH_OPERATIONS))


def _validate_database_snapshot(snapshot: dict, operations: set[str]) -> dict:
    from aos_api.asset_registry.canonical_json import canonical_sha256
    detach = snapshot["detach"]
    if (detach is None or detach["receipt_id"] != P_DETACH or detach["phase"] != "detach"
            or detach["content_hash"] != P_DETACH_HASH
            or canonical_sha256(detach["authority_data"]) != P_DETACH_HASH):
        raise ValueError("exact P detach Receipt required")
    routes = snapshot["routes"]
    if (len(routes) != len(operations) or {row["operation_id"] for row in routes} != operations
            or any(row["handler_kind"] != "legacy" or row["installation_id"] is not None
                   or row["generation"] is not None or row["execution_epoch"] is not None
                   or row["operation_fence"] is not True or row["revision"] != 29
                   or row["cutover_group_revision"] != 53 for row in routes)):
        raise ValueError("exact detached P route group required")
    schedule = snapshot["schedule"]
    if schedule is None or schedule["enabled"] is not False or not schedule["last_run"]:
        raise ValueError("disabled source schedule with authoritative cursor required")
    if snapshot["safety"] != {"running": 0, "unresolved": 0, "canary": 0}:
        raise ValueError("drained tenant and empty canary required")
    return snapshot


def _require_p_terminal(current) -> dict:
    snapshot = current.observe_installation(P_ID)
    head, bindings = snapshot["head"], snapshot["bindings"]
    if (str(head["installation_id"]) != P_ID or head["state"] != "uninstalled"
            or head["etag_version"] != 6 or len(bindings) != 1
            or str(bindings[0]["generation"]) != P_GENERATION
            or (bindings[0]["revision"], bindings[0]["execution_epoch"]) != (10, 5)
            or bindings[0]["enabled"] is not False or bindings[0]["operation_fence"] is not True
            or bindings[0]["desired_state"] != "uninstalled"
            or bindings[0]["observed_state"] != "stopped"
            or len(snapshot["resources"]) != 3
            or any(row["cleanup_state"] != "released" or row["observed_release"] is not True
                   for row in snapshot["resources"])
            or any(row["status"] not in {"succeeded", "failed", "cancelled"}
                   for row in snapshot["operations"])
            or snapshot["canaryInstallations"] != 0):
        raise ValueError("exact terminal P installation required")
    return snapshot


def preflight(current) -> dict:
    p = _require_p_terminal(current)
    database = _database_snapshot()
    return {"outcome": "Q_CLEAN_SUCCESSOR_PREFLIGHT_GREEN", "p": p,
            "database": database, "externalEffects": 0}


def create_q(current) -> dict:
    p = _require_p_terminal(current)
    database = _database_snapshot()
    if Q_DIR.exists():
        raise ValueError("Q intent/result exists; inspect without resending")
    helper = current._load("a0v_ecommerce_growth_1_5_registry_successor")
    installer = current._load("a0v_canonical_ecommerce_first_install")
    Q_DIR.mkdir(parents=True, exist_ok=False, mode=0o700)
    backup = helper._database_backup(context=helper.DOCKER_CONTEXT,
        container=helper.DATABASE_CONTAINER, state_dir=Q_DIR)
    current._freeze(Q_DIR / "create-intent.json", {"label": "q", "predecessor": None,
        "terminalInstallationId": P_ID, "terminalEtag": p["head"]["etag_version"],
        "detachReceipt": {"receiptId": P_DETACH, "contentHash": P_DETACH_HASH},
        "versions": transaction.VERSIONS, "backup": backup, "database": database})
    connect = installer.container_database_connect_factory(context=helper.DOCKER_CONTEXT,
        container=helper.DATABASE_CONTAINER, database_name=helper.DATABASE_NAME)
    result = installer.create_approved_first_installation(connect_factory=connect,
        state_dir=current.TRUST_STATE,
        core_version=transaction.VERSIONS["domain.ecommerce.core"],
        adapter_version=transaction.VERSIONS["platform.ecommerce.niushop"],
        growth_version=transaction.VERSIONS["solution.ecommerce.growth"],
        idempotency_prefix=PREFIX)
    if result["installationState"] != "approved":
        raise ValueError("Q clean approved installation required")
    current._freeze(Q_DIR / "create-result.json", result)
    return {"outcome": "Q_CLEAN_INSTALLATION_APPROVED", **result}


def run(action: str) -> dict:
    if action not in ACTIONS:
        raise ValueError("unsupported Q clean successor action")
    current = profile()
    if action == "preflight":
        return preflight(current)
    if action == "create-q":
        return create_q(current)
    if action == "observe":
        result = {"p": _require_p_terminal(current), "database": _database_snapshot()}
        if (Q_DIR / "create-result.json").exists():
            result["q"] = current.observe_installation(current._initial("q")["installationId"])
        return {"outcome": "Q_CLEAN_SUCCESSOR_OBSERVED", **result}
    _require_p_terminal(current)
    _database_snapshot()
    phase, label = action.split("-")
    if label != "q":
        raise ValueError("only Q lifecycle may continue")
    if phase in {"prepare", "verify"}:
        return current.lifecycle(label, phase)
    return current.configure(label, phase)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=ACTIONS)
    args = parser.parse_args()
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    result_path = STATE / f"{args.action}-result.json"
    if result_path.exists():
        raise ValueError("immutable action result exists; inspect without resending")
    result = run(args.action)
    profile()._freeze(result_path, result)
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))


if __name__ == "__main__":
    main()
