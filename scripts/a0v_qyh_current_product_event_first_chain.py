"""Receipt-first controls for one current QYH Product snapshot and event handoff."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib
import json
import os
from pathlib import Path
import sys
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
PREVIOUS_STATE = ROOT.parent / ".aos-recovery-20260915/state/niushop-1.23-current-package/business/p02-e-first-chain"
STATE = ROOT.parent / ".aos-recovery-20260915/state/niushop-1.23-current-package/business/p02-e-first-chain-r2"
SCOPE = {"org_id": "org-org", "project_id": "dev-project"}
PIPELINE = "P02-product-qyh"
SCHEDULE = "sch-p02-qyh-controlled-20260913-v1"
ACTOR = "a0v-ecommerce-growth-1.4-runtime-owner"
API = "http://127.0.0.1:18181"


def freeze(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with os.fdopen(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "w") as handle:
        json.dump(value, handle, ensure_ascii=False, default=str, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def freeze_or_match(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != value:
            raise ValueError("immutable intent differs")
        return
    freeze(path, value)


def load_result(name: str) -> dict[str, Any]:
    path = STATE / f"{name}-result.json"
    if not path.is_file() or path.stat().st_mode & 0o777 != 0o600:
        raise ValueError(f"private {name} result required")
    return json.loads(path.read_text(encoding="utf-8"))


def load_previous_result(name: str) -> dict[str, Any]:
    path = PREVIOUS_STATE / f"{name}-result.json"
    if not path.is_file() or path.stat().st_mode & 0o777 != 0o600:
        raise ValueError(f"private previous {name} result required")
    return json.loads(path.read_text(encoding="utf-8"))


def setup():
    sys.path.insert(0, str(ROOT / "scripts"))
    preflight = importlib.import_module("a0v_p02_current_preflight")
    from a0v_ecommerce_runtime_host import DEFAULT_CREDENTIALS, _configure_environment

    _configure_environment(
        DEFAULT_CREDENTIALS,
        bundle_root=preflight.BUNDLE_ROOT,
        trust_roots_file=preflight.TRUST_ROOTS,
    )
    os.environ["AOS_EXTENSION_RUNTIME_HOST_ENABLED"] = "0"
    sys.path.insert(0, str(ROOT / "services/aos-api"))
    from aos_api.asset_registry.control_wiring import build_runtime_control_plane

    return preflight, build_runtime_control_plane()


def prepare(preflight) -> dict[str, Any]:
    result = preflight.run("preflight")
    if result.get("outcome") != "PRODUCT_CURRENT_PREFLIGHT_GREEN":
        raise ValueError("current Product preflight required")
    return result


def approve_selection(preflight, plane) -> dict[str, Any]:
    prepared = load_result("prepare")
    draft = prepared["draft"]
    previous = load_previous_result("selection")["ref"]
    intent = {"actor": ACTOR, "idempotencyKey": "a0v-p02-e-selection-20260915-v2",
              "draft": draft, "previousRef": previous}
    freeze_or_match(STATE / "selection-intent.json", intent)
    from aos_api.pipeline_runtime_control_contracts import PipelineSourceSelectionDraft
    from aos_api.tenant_scope import TenantScope

    ref = plane.pipeline_control_factory.build(TenantScope(**SCOPE)).approve_selection(
        draft=PipelineSourceSelectionDraft.model_validate_json(json.dumps(draft)), actor=ACTOR,
        idempotency_key=intent["idempotencyKey"], previous_ref=previous,
    )
    return {"outcome": "CURRENT_PRODUCT_SELECTION_APPROVED", "ref": ref.model_dump(mode="json", by_alias=True)}


def approve_control(preflight, plane) -> dict[str, Any]:
    prepared = load_result("prepare")
    selection = load_result("selection")["ref"]
    draft = {**prepared["draft"], "schemaVersion": "aos.pipeline-runtime-control-draft/v1",
             "sourceSelectionRef": selection}
    previous = load_previous_result("control")["ref"]
    intent = {"actor": ACTOR, "idempotencyKey": "a0v-p02-e-control-20260915-v2",
              "draft": draft, "previousRef": previous}
    freeze_or_match(STATE / "control-intent.json", intent)
    from aos_api.pipeline_runtime_control_contracts import PipelineRuntimeControlDraft
    from aos_api.tenant_scope import TenantScope

    ref = plane.pipeline_control_factory.build(TenantScope(**SCOPE)).approve_control(
        draft=PipelineRuntimeControlDraft.model_validate_json(json.dumps(draft)), actor=ACTOR,
        idempotency_key=intent["idempotencyKey"], previous_ref=previous,
    )
    return {"outcome": "CURRENT_PRODUCT_CONTROL_APPROVED", "ref": ref.model_dump(mode="json", by_alias=True)}


def bind_schedule(preflight, plane) -> dict[str, Any]:
    from aos_api.extension_runtime.consumer_connection import consumer_connection
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
    from aos_api.pipeline_schedule_control_owner import PipelineScheduleControlOwner
    from aos_api.tenant_scope import TenantScope

    scope = TenantScope(**SCOPE)
    service = plane.pipeline_control_factory.build(scope)
    with consumer_connection(runtime_worker_connection, SCOPE) as conn:
        schedule = conn.execute(
            "SELECT pipeline_id,enabled,ingest FROM meta_schedule WHERE org_id=%s AND project_id=%s AND id=%s",
            (*scope.key, SCHEDULE),
        ).fetchone()
        if schedule is None or schedule["pipeline_id"] != PIPELINE or schedule["enabled"] is not False:
            raise ValueError("exact disabled Product schedule required")
        if schedule["ingest"] != {"kind": "pipeline-live-v1", "pipelineId": PIPELINE}:
            raise ValueError("exact live Product schedule required")
        active = conn.execute(
            "SELECT count(*) AS n FROM meta_schedule_run WHERE org_id=%s AND project_id=%s AND schedule_id=%s AND (status='running' OR executor_stopped IS NOT TRUE)",
            (*scope.key, SCHEDULE),
        ).fetchone()["n"]
        if active != 0:
            raise ValueError("Product schedule has an unstopped run")
        previous = PipelineScheduleControlOwner(controls=service.controls).read_latest(
            conn, scope=scope, schedule_id=SCHEDULE
        )
    if previous is None:
        raise ValueError("historical Product schedule binding required")
    expected_previous = load_previous_result("binding")["ref"]
    if previous.ref.model_dump(mode="json", by_alias=True) != expected_previous:
        raise ValueError("previous Product schedule binding differs")
    control = load_result("control")["ref"]
    intent = {"actor": ACTOR, "idempotencyKey": "a0v-p02-e-schedule-binding-20260915-v2",
              "scheduleId": SCHEDULE, "controlRef": control,
              "previousRef": expected_previous}
    freeze_or_match(STATE / "binding-intent.json", intent)
    ref = service.bind_schedule(
        pipeline_id=PIPELINE, schedule_id=SCHEDULE, control_ref=control, actor=ACTOR,
        idempotency_key=intent["idempotencyKey"], previous_ref=intent["previousRef"],
    )
    return {"outcome": "CURRENT_PRODUCT_SCHEDULE_BOUND", "ref": ref.model_dump(mode="json", by_alias=True)}


def api(method: str, path: str, body: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode()
    request = Request(API + path, data=data, method=method, headers={
        "Authorization": "Bearer dev", "X-Org-Id": "org-org", "X-Project-Id": "dev-project",
        "Content-Type": "application/json",
    })
    try:
        with urlopen(request, timeout=45) as response:
            return response.status, json.loads(response.read())
    except HTTPError as error:
        safe_code = "HTTP_ERROR"
        try:
            payload = json.loads(error.read())
            detail = payload.get("detail") if type(payload) is dict else None
            candidate = payload.get("code") if type(payload) is dict else None
            if candidate is None and type(detail) is dict:
                candidate = detail.get("code")
            if type(candidate) is str and candidate.isidentifier():
                safe_code = candidate
        except (json.JSONDecodeError, OSError, TypeError):
            pass
        raise RuntimeError(f"controlled API returned {error.code}:{safe_code}") from error


def execute_once(preflight, plane) -> dict[str, Any]:
    expected_control = load_result("control")["ref"]
    expected_binding = load_result("binding")["ref"]
    snapshot = observe(preflight, plane)
    current = snapshot["current"]
    if (current["schedule"]["enabled"] is not False
            or current["binding"]["ref"] != expected_binding
            or current["binding"]["controlRef"] != expected_control):
        raise ValueError("current disabled schedule binding differs")
    intent = {"scheduleId": SCHEDULE, "bindingRef": expected_binding,
              "controlRef": expected_control, "maxSourceCalls": 1}
    freeze_or_match(STATE / "execute-intent.json", intent)
    enable_status, enabled = api("PATCH", f"/v1/schedules/{SCHEDULE}", {"enabled": True})
    try:
        run_status, run = api("POST", f"/v1/schedules/{SCHEDULE}/run", {})
    finally:
        disable_status, disabled = api("PATCH", f"/v1/schedules/{SCHEDULE}", {"enabled": False})
    run_outcome = "CURRENT_PRODUCT_SNAPSHOT_SUCCEEDED" if run.get("status") == "succeeded" else "CURRENT_PRODUCT_SNAPSHOT_FAILED"
    return {"outcome": run_outcome, "enable": {"status": enable_status, "body": enabled},
            "run": {"status": run_status, "body": run}, "disable": {"status": disable_status, "body": disabled}}


def observe(preflight, plane) -> dict[str, Any]:
    from aos_api.extension_runtime.consumer_connection import consumer_connection
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
    from aos_api.pipeline_schedule_control_owner import PipelineScheduleControlOwner
    from aos_api.pipeline_source_selection_store import decode_selection_row
    from aos_api.pipeline_runtime_control_owner import decode_control_row
    from aos_api.tenant_scope import TenantScope

    scope = TenantScope(**SCOPE)
    services = plane.pipeline_control_factory.build(scope)
    with consumer_connection(runtime_worker_connection, SCOPE) as conn:
        selection_row = conn.execute("SELECT * FROM pipeline_source_selection_revision WHERE org_id=%s AND project_id=%s AND installation_id=%s AND pipeline_id=%s ORDER BY revision DESC LIMIT 1",
            (*scope.key, json.loads(preflight.CURRENT_CREATE.read_text())["installationId"], PIPELINE)).fetchone()
        control_row = conn.execute("SELECT * FROM pipeline_runtime_control_revision WHERE org_id=%s AND project_id=%s AND installation_id=%s AND pipeline_id=%s ORDER BY revision DESC LIMIT 1",
            (*scope.key, json.loads(preflight.CURRENT_CREATE.read_text())["installationId"], PIPELINE)).fetchone()
        binding = PipelineScheduleControlOwner(controls=services.controls).read_latest(conn, scope=scope, schedule_id=SCHEDULE)
        schedule = conn.execute("SELECT id,pipeline_id,enabled,last_run FROM meta_schedule WHERE org_id=%s AND project_id=%s AND id=%s",(*scope.key,SCHEDULE)).fetchone()
        run = conn.execute("SELECT * FROM meta_schedule_run WHERE org_id=%s AND project_id=%s AND schedule_id=%s ORDER BY started_at DESC LIMIT 1",(*scope.key,SCHEDULE)).fetchone()
        stages = None
        if run is not None:
            stages = {}
            for label, table in (("command", "ecommerce_ingress_command"),
                                 ("derived", "ecommerce_ingress_derived_command"),
                                 ("dataset", "ecommerce_ingress_dataset_receipt"),
                                 ("recoveryClaim", "ecommerce_ingress_recovery_claim")):
                stages[label] = conn.execute(
                    f"SELECT count(*) AS n FROM {table} WHERE org_id=%s AND project_id=%s AND run_id=%s",
                    (*scope.key, run["id"]),
                ).fetchone()["n"]
        canary = conn.execute("SELECT count(*) AS n FROM pipeline_controlled_source_claim WHERE org_id='dev-org' AND project_id='dev-project'").fetchone()["n"]
        result = {"schedule": dict(schedule) if schedule else None, "run": dict(run) if run else None,
                  "ingressStageCounts": stages,
                  "selectionRef": decode_selection_row(selection_row).ref.model_dump(mode="json",by_alias=True) if selection_row else None,
                  "controlRef": decode_control_row(control_row).ref.model_dump(mode="json",by_alias=True) if control_row else None,
                  "binding": None if binding is None else {"ref": binding.ref.model_dump(mode="json",by_alias=True),
                      "controlRef": binding.control_ref.model_dump(mode="json",by_alias=True),
                      "installationId": binding.installation_id, "generation": binding.generation}}
    return {"outcome": "CURRENT_PRODUCT_CHAIN_OBSERVED", "observedAt": datetime.now(timezone.utc).isoformat(),
            "current": result, "canaryClaims": canary}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "selection", "control", "binding", "execute", "observe"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("immutable output exists; inspect before retry")
    preflight, plane = setup()
    action = {"prepare": lambda: prepare(preflight), "selection": lambda: approve_selection(preflight,plane),
              "control": lambda: approve_control(preflight,plane), "binding": lambda: bind_schedule(preflight,plane),
              "execute": lambda: execute_once(preflight,plane), "observe": lambda: observe(preflight,plane)}[args.action]
    result = action()
    freeze(args.output, result)
    canonical = STATE / f"{args.action}-result.json"
    if canonical != args.output:
        freeze(canonical, result)
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))


if __name__ == "__main__":
    os.environ.setdefault("AOS_DOTENV_DISABLED", "1")
    main()
