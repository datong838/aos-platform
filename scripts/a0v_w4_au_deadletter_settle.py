#!/usr/bin/env python3
"""W4 step 7: settle the AU-source dead-letter enable op via conservative disable.

The accepted enable op 7679fe93 (created 2026-09-22T17:09Z on installation
d2d3c478, the DQ-source successor) has no owner to execute it: its generation
b15f1733 leases were released when the predecessor chain moved on, and the live
scheduler never adopts an installation whose binding is fenced-disabled.

RuntimeDisableService.request is the sanctioned reconciliation channel: it
cancels every effect-free accepted configure/enable in the same transaction as
the disable fence (see disable_service.py L52-81 'cancelled_for_disable').

Dependent is deliberately None (evaluated 2026-09-23): the only resumed
activation 29f2f093 for this installation was already consumed by the prior
disable 24db7253 (lifecycle status 'detached'), and its cutover group 6a402d31
dispatch rows now point at the live successor (DR 89975129 / gen c78b2e2e).
Running EcommerceGrowthDisableDependent would match that stale activation and
die on the DB fence function's epoch-drift guard (binding epoch 7 vs target 4),
or worse re-fence live successor dispatch rows. dispatch convergence for this
installation is complete; there is nothing for the dependent to do.

The disable op itself is driven to 'succeeded' by the live Host's
RuntimeDisableConsumer (outbox kind='disable'): finish_disable's
after_runtime_disabled hook is a no-op without a lifecycle row, and the
GenerationDrainReader precondition holds (single failed attempt at epoch 3,
no pending attempts, no undelivered disable outbox events).

Phases:
  inspect - read-only facts (binding rev, etag, pending ops)
  disable - RuntimeDisableService.request(kind=disable, dependent=None) with
            fresh etag; pending enable 7679fe93 is cancelled in the same commit
  verify  - read-only: no non-terminal ops remain on the installation
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/replacement-dq/w4-au-deadletter-settle"
INSTALLATION = "d2d3c478-f9d9-4489-92b7-1de57f546452"
GENERATION = "b15f1733-89dd-4684-9475-9fba095a1d74"
ACTOR = "a0v-ecommerce-growth-1.4-runtime-owner"
KEY = "a0v-w4-au-deadletter-disable-20260923"
BASE = ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline"


def _configure():
    os.environ.update({
        "AOS_DOTENV_DISABLED": "1",
        "AOS_EXTENSION_RUNTIME_CREDENTIAL_FILE": str(BASE / "bm-runtime-credentials/runtime-host-identities.json"),
        "AOS_EXTENSION_RUNTIME_HOST_ENABLED": "0",
        "AOS_EXTENSION_OCI_CONTEXT": "colima-aos-extension",
        "AOS_BUNDLE_ROOT": str(BASE / "bn-canonical-alias-registry/signed-bundles"),
        "AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE": str(BASE / "bn-registration-credentials/registration-main-identity.json"),
    })
    sys.path.insert(0, str(ROOT / "services/aos-api"))


def _write(name, value):
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(STATE, 0o700)
    path = STATE / f"{name}.json"
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2, default=str)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def _service():
    """Assemble the sanctioned disable plane with dependent=None (see module doc).

    The EcommerceGrowthDisableDependent hook is deliberately omitted: the sole
    resumed activation for this installation was consumed by disable 24db7253
    and the group dispatch rows now serve the live successor DR 89975129.
    """
    import a0v_ecommerce_growth_1_4_activate as activation
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
    from aos_api.extension_runtime.disable_service import RuntimeDisableService
    from aos_api.extension_runtime.current_permission import CurrentControlPermission
    from aos_api.asset_registry.control_policy import DISABLE_RUNTIME_OPERATION
    store, lifecycle = activation._services(
        runtime_worker_connection, BASE / "bm-trust-root-rotation/signing/trust-roots.json")
    disable_service = RuntimeDisableService(
        installation_store=store,
        installation_reader=lifecycle._reader,
        check_current_permission=CurrentControlPermission(operation=DISABLE_RUNTIME_OPERATION),
        dependent=None,
    )
    return activation, disable_service


def _facts():
    from aos_api.extension_runtime.consumer_connection import consumer_connection
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
    with consumer_connection(runtime_worker_connection, dict(org_id="org-org", project_id="dev-project")) as conn:
        binding = conn.execute("""SELECT revision, generation::text, enabled, operation_fence,
            desired_state, observed_state FROM extension_runtime_binding
            WHERE org_id=%s AND project_id=%s AND installation_id=%s""",
            ("org-org", "dev-project", INSTALLATION)).fetchone()
        etag = conn.execute("""SELECT etag_version FROM bundle_installation
            WHERE org_id=%s AND project_id=%s AND installation_id=%s""",
            ("org-org", "dev-project", INSTALLATION)).fetchone()["etag_version"]
        pending = conn.execute("""SELECT operation_id::text, kind, phase, status FROM extension_runtime_operation
            WHERE org_id=%s AND project_id=%s AND installation_id=%s
            AND status NOT IN ('succeeded','failed','cancelled')""",
            ("org-org", "dev-project", INSTALLATION)).fetchall()
    return {"binding": dict(binding) if binding else None, "etag": etag,
            "pendingOps": [dict(r) for r in pending]}


def inspect():
    _configure()
    return {"outcome": "W4_AU_DEADLETTER_INSPECT", **_facts()}


def disable():
    _configure()
    facts = _facts()
    if facts["binding"] is None:
        raise RuntimeError("source installation binding unavailable")
    if not facts["pendingOps"]:
        return {"outcome": "W4_AU_DEADLETTER_ALREADY_SETTLED", "facts": facts}
    from aos_api.extension_runtime.disable_contracts import DisableTarget
    activation, disable_service = _service()
    receipt = disable_service.request(
        installation_id=INSTALLATION, org_id="org-org", project_id="dev-project",
        actor=ACTOR, roles=activation.ROLES, markings=activation.MARKINGS,
        idempotency_key=f"{KEY}-v1", if_match=f'"{facts["etag"]}"',
        target=DisableTarget(generation=GENERATION, bindingRevision=facts["binding"]["revision"]),
    )
    _write("disable", {"receipt": receipt.response_json, "factsBefore": facts})
    return {"outcome": "W4_AU_DEADLETTER_DISABLED", "receipt": receipt.response_json}


def verify():
    _configure()
    facts = _facts()
    settled = not facts["pendingOps"]
    return {"outcome": "W4_AU_DEADLETTER_VERIFY", "settled": settled, "facts": facts}


if __name__ == "__main__":
    _configure()
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("inspect", "disable", "verify"))
    print(json.dumps(globals()[parser.parse_args().phase](), ensure_ascii=False, sort_keys=True, default=str))
