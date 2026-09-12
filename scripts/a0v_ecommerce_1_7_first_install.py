#!/usr/bin/env python3
"""Explicit approved-install/apply/verify commands for the isolated successor."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
RECOVERY = ROOT.parent / ".aos-recovery-20260912"
STATE = RECOVERY / "state/ecommerce-1.7-first-install.json"
TRUST_STATE = ROOT.parent / ".aos-recovery-20260910/state/a0v-canonical-ecommerce-first-install"


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def installation_target(*, after_config_recovery=False, after_sleep_recovery=False, niushop_1_4=False):
    flags = (after_config_recovery, after_sleep_recovery, niushop_1_4)
    if any(type(flag) is not bool for flag in flags) or sum(flags) > 1:
        raise ValueError('one exact installation profile required')
    if niushop_1_4:
        return (RECOVERY / 'state/niushop-1.4-first-install.json', 'a0v-niushop-1.4',
                '1.4.0', 'a0fd8e25-cb6f-49e5-aa77-7faddae12099')
    if after_sleep_recovery:
        return (RECOVERY / 'state/ecommerce-1.7-sleep-recovered-first-install.json',
                'a0v-ecommerce-1.7-sleep-recovered', '1.3.0', 'af1992e8-89c2-406a-816d-01e61d7bf982')
    if after_config_recovery:
        return (RECOVERY / 'state/ecommerce-1.7-recovered-first-install.json',
                'a0v-ecommerce-1.7-recovered', '1.3.0', 'e42e042b-1fe7-4cfa-bb83-469ff256081d')
    return STATE, 'a0v-ecommerce-1.7', '1.3.0', None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--action", choices=("create", "apply", "verify", "observe"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    group=parser.add_mutually_exclusive_group()
    group.add_argument("--after-config-recovery", action="store_true")
    group.add_argument("--after-sleep-recovery", action="store_true")
    group.add_argument("--niushop-1-4", action="store_true")
    args = parser.parse_args()
    state_path, key_prefix, adapter_version, predecessor_id = installation_target(
        after_config_recovery=args.after_config_recovery,
        after_sleep_recovery=args.after_sleep_recovery, niushop_1_4=args.niushop_1_4)
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
    predecessor = store.get_installation(org_id="org-org", project_id="dev-project", installation_id="efc4e640-1b15-403f-9d06-4c6d1a5330a7")
    if predecessor.state != "uninstalled" or predecessor.active_revision is not None:
        raise ValueError("1.6 reinstall must be formally retired first")
    if predecessor_id is not None:
        retired=store.get_installation(org_id="org-org",project_id="dev-project",installation_id=predecessor_id)
        if retired.state!="uninstalled" or retired.active_revision is not None:
            raise ValueError("selected predecessor must be formally uninstalled")
    if args.action == "create":
        result = first.create_approved_first_installation(connect_factory=connect, state_dir=TRUST_STATE,
            core_version="1.3.0", adapter_version=adapter_version, growth_version="1.7.0",
            idempotency_prefix=key_prefix + "-first-install-v1")
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    else:
        initial = json.loads(state_path.read_text())
        installation_id = initial["installationId"]
        record = store.get_installation(org_id="org-org", project_id="dev-project", installation_id=installation_id)
        result = {"installationId": installation_id, "state": record.state,
                  "revision": record.current_revision, "activeRevision": record.active_revision}
        with connect() as conn:
            operations = conn.execute("""SELECT operation_id,kind,status,phase,failure_code,expected_installation_etag FROM extension_runtime_operation
                WHERE org_id='org-org' AND project_id='dev-project' AND installation_id=%s ORDER BY created_at""", (installation_id,)).fetchall()
            bindings = conn.execute("""SELECT generation,desired_state,observed_state,enabled,operation_fence FROM extension_runtime_binding
                WHERE org_id='org-org' AND project_id='dev-project' AND installation_id=%s""", (installation_id,)).fetchall()
        result.update(operations=[dict(row) for row in operations], bindings=[dict(row) for row in bindings])
        if args.action in {"apply", "verify"}:
            kind = "runtime-" + args.action
            prior = [row for row in operations if row["kind"] == kind]
            recovered = any(event.evidence is not None and event.evidence.type == "preparation_reset"
                            for event in record.events)
            if prior and (not recovered or any(row["expected_installation_etag"] >= record.etag_version for row in prior)):
                raise ValueError("operation already exists; observe its result before further action")
            expected = "approved" if args.action == "apply" else "applied"
            if record.state != expected:
                raise ValueError("installation is not in expected predecessor state")
            activation._ensure_control_membership(connect)
            receipt = lifecycle.request_preparation(installation_id=installation_id, kind=kind,
                org_id="org-org", project_id="dev-project", actor=activation.ACTOR,
                roles=activation.ROLES, markings=activation.MARKINGS,
                idempotency_key=key_prefix + "-" + kind + (f"-after-reset-r{record.etag_version}" if recovered else "-v1"),
                if_match=f'"{record.etag_version}"')
            result["receipt"] = receipt.response_json
    result["canaryInstallationCount"] = canary
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, default=str, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, default=str, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
