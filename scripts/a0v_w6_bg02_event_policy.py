"""W6-A: activate BG-02 event chain for DS authority (c6812824/b59582cc).

Phases (all freeze intent first, then execute, receipt-first):
  facts   - read-only: DS authority refs (config/lock/generation/binding), case, schedules
  prepare - compose new event policy draft for DS (generation-h 20260924)
  approve - approval proposal for the policy put
  put     - canonical router dispatch ecommerce_growth_schedule_put
  bind    - automation_schedule_binding (cadence=event) + control binding for DS
  verify  - discovery probe: candidates >= 1 after next controlled run

Run AFTER W5 final automations are both GREEN (definition 8b1d0f7e enabled + first dispatch 12/12).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline"
STATE = BASE / "replacement-dq/w6-bg02-activation"
SCOPE = {"org_id": "org-org", "project_id": "dev-project"}
ACTOR = "a0v-ecommerce-growth-1.4-runtime-owner"
DS_ID = "c6812824-a0c3-4adc-9ebc-d56178ae135c"
DS_GENERATION = "b59582cc-2abf-472d-8f59-bfc8be1138c8"
DS_LOCK = "sha256:1b8468b86496b277a0ecd3a802379b3640e5ed1ec76e9ec420b9d15089013938"
CASE = "case-qyh-full-store-baseline-20260915"
POLICY = "product-event-qyh-full-store-generation-h-20260924"
PREFIX = "a0v-w6-bg02-ds-event-v1"
GROWTH_BACKEND = BASE / "bn-canonical-alias-registry/signed-bundles/solution.ecommerce.growth/1.10.2/backend"
SDK_ROOT = ROOT / "packages/aos-extension-sdk/python"

ENV = {
    "AOS_DOTENV_DISABLED": "1",
    "AOS_EXTENSION_RUNTIME_CREDENTIAL_FILE": str(BASE / "bm-runtime-credentials/runtime-host-identities.json"),
    "AOS_EXTENSION_RUNTIME_HOST_ENABLED": "0",
    "AOS_EXTENSION_OCI_CONTEXT": "colima-aos-extension",
    "AOS_BUNDLE_ROOT": str(BASE / "bn-canonical-alias-registry/signed-bundles"),
    "AOS_BUNDLE_TRUST_ROOTS_FILE": str(BASE / "bm-trust-root-rotation/signing/trust-roots.json"),
    "AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE": str(BASE / "bn-registration-credentials/registration-main-identity.json"),
}


def freeze(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    import stat
    if path.exists():
        raise ValueError(f"immutable intent already frozen: {path.name}")
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump(value, handle, ensure_ascii=False, default=str, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def load(name: str) -> dict:
    path = STATE / f"{name}-result.json"
    if not path.is_file() or path.stat().st_mode & 0o777 != 0o600:
        raise ValueError(f"private {name} result required")
    return json.loads(path.read_text())


def setup():
    os.environ.update(ENV)
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(ROOT / "services/aos-api"))
    sys.path.insert(0, str(ROOT / "scripts"))
    sys.path.insert(0, str(SDK_ROOT))
    if GROWTH_BACKEND.is_dir():
        sys.path.insert(0, str(GROWTH_BACKEND))
    from aos_api.asset_registry.control_wiring import build_runtime_control_plane
    from aos_api.ecommerce_growth_registration_connection import registration_connection
    plane = build_runtime_control_plane(registration_connect=registration_connection)
    return plane


@contextmanager
def _conn():
    from aos_api.extension_runtime.consumer_connection import consumer_connection
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
    with consumer_connection(runtime_worker_connection, SCOPE) as conn:
        yield conn


def facts(plane) -> dict:
    """Read-only: collect DS authority references needed by later phases."""
    with _conn() as conn:
        head = conn.execute("""SELECT i.current_revision, r.state, r.lock_hash, r.overlay_revision,
            (SELECT count(*) FROM bundle_composition c
              WHERE c.composition_pk=r.composition_pk) AS pkgs
            FROM bundle_installation i JOIN bundle_installation_revision r
            ON (i.org_id,i.project_id,i.installation_pk,i.current_revision)=
               (r.org_id,r.project_id,r.installation_pk,r.revision)
            WHERE i.org_id=%s AND i.project_id=%s AND i.installation_id=%s LIMIT 1""",
            (*SCOPE.values(), DS_ID)).fetchone()
        group = conn.execute("""SELECT cutover_group_id, max(revision) AS max_rev,
            min(cutover_group_revision) AS grp_rev, max(execution_epoch) AS epoch,
            count(*) AS ops
            FROM extension_operation_dispatch_binding
            WHERE org_id=%s AND project_id=%s AND installation_id=%s
            GROUP BY cutover_group_id""",
            (*SCOPE.values(), DS_ID)).fetchone()
        binding = conn.execute("""SELECT generation, revision, execution_epoch, enabled,
            observed_state, operation_fence, config_ref
            FROM extension_runtime_binding
            WHERE org_id=%s AND project_id=%s AND installation_id=%s
            ORDER BY revision DESC LIMIT 1""", (*SCOPE.values(), DS_ID)).fetchone()
        case = conn.execute("""SELECT case_id, current_revision, version, lifecycle
            FROM ecommerce_investigation_case_head
            WHERE org_id=%s AND project_id=%s AND case_id=%s""",
            (*SCOPE.values(), CASE)).fetchone()
        definition = conn.execute("""SELECT definition_id, state
            FROM pipeline_snapshot_schedule_definition_head
            WHERE org_id=%s AND project_id=%s AND definition_id='8b1d0f7e-3a6c-4b58-9d27-6f0e2a91c001'""",
            tuple(SCOPE.values())).fetchone()
    result = dict(dsHead=dict(head) if head else None,
                  dsBinding=dict(binding) if binding else None,
                  dsGroup=dict(group) if group else None,
                  case=dict(case) if case else None,
                  definition=dict(definition) if definition else None,
                  outcome="W6_FACTS_GREEN" if head and binding and case else "W6_FACTS_INCOMPLETE")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["facts", "prepare", "approve", "put", "bind", "verify"])
    args = parser.parse_args()
    plane = setup()
    if args.phase == "facts":
        facts(plane)
    else:
        raise SystemExit(f"phase {args.phase} not implemented yet - run facts first after W5 final GREEN")


if __name__ == "__main__":
    main()
