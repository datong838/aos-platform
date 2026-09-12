#!/usr/bin/env python3
"""Explicit approved-install/apply/verify commands for the isolated successor."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
RECOVERY = ROOT.parent / ".aos-recovery-20260912"
STATE = RECOVERY / "state/ecommerce-1.6-first-install.json"
TRUST_STATE = ROOT.parent / ".aos-recovery-20260910/state/a0v-canonical-ecommerce-first-install"


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--action", choices=("create", "apply", "verify", "observe"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    first = load("a0v_canonical_ecommerce_first_install")
    activation = load("a0v_ecommerce_growth_1_4_activate")
    connect = first.container_database_connect_factory(context="colima-aos-extension", container="aos-a0v-recovery-pg", database_name="aos_meta_head")
    store, lifecycle = activation._services(connect, TRUST_STATE / "signing/trust-roots.json")
    with connect() as conn:
        canary = conn.execute("SELECT count(*) AS n FROM bundle_installation WHERE org_id='dev-org' AND project_id='dev-project'").fetchone()["n"]
    if canary:
        raise ValueError("canary installation drift")
    old = store.get_installation(org_id="org-org", project_id="dev-project", installation_id=activation.INSTALLATION_ID)
    if old.state != "uninstalled":
        raise ValueError("previous invalid installation must be retired")
    if args.action == "create":
        result = first.create_approved_first_installation(connect_factory=connect, state_dir=TRUST_STATE,
            core_version="1.2.0", adapter_version="1.2.0", growth_version="1.6.0",
            idempotency_prefix="a0v-ecommerce-1.6-first-install-v1")
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    else:
        initial = json.loads(STATE.read_text())
        installation_id = initial["installationId"]
        record = store.get_installation(org_id="org-org", project_id="dev-project", installation_id=installation_id)
        result = {"installationId": installation_id, "state": record.state,
                  "revision": record.current_revision, "activeRevision": record.active_revision}
        with connect() as conn:
            operations = conn.execute("""SELECT operation_id,kind,status,phase,failure_code FROM extension_runtime_operation
                WHERE org_id='org-org' AND project_id='dev-project' AND installation_id=%s ORDER BY created_at""", (installation_id,)).fetchall()
            bindings = conn.execute("""SELECT generation,desired_state,observed_state,enabled,operation_fence FROM extension_runtime_binding
                WHERE org_id='org-org' AND project_id='dev-project' AND installation_id=%s""", (installation_id,)).fetchall()
        result.update(operations=[dict(row) for row in operations], bindings=[dict(row) for row in bindings])
        if args.action in {"apply", "verify"}:
            kind = "runtime-" + args.action
            if any(row["kind"] == kind for row in operations):
                raise ValueError("operation already exists; observe its result before further action")
            expected = "approved" if args.action == "apply" else "applied"
            if record.state != expected:
                raise ValueError("installation is not in expected predecessor state")
            activation._ensure_control_membership(connect)
            receipt = lifecycle.request_preparation(installation_id=installation_id, kind=kind,
                org_id="org-org", project_id="dev-project", actor=activation.ACTOR,
                roles=activation.ROLES, markings=activation.MARKINGS,
                idempotency_key="a0v-ecommerce-1.6-" + kind + "-v1", if_match=f'"{record.etag_version}"')
            result["receipt"] = receipt.response_json
    result["canaryInstallationCount"] = canary
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, default=str, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, default=str, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
