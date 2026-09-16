"""Retire the irrecoverable ungrouped analysis Run through canonical HTTP commands."""
from __future__ import annotations

import argparse
import json
import os
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


API = "http://127.0.0.1:18181"
RUN = "analysis-e5b19a5fe290ce1bf60d5038cb1d6cf6"
REQUIREMENT = "data-requirement-5af070de068be456d80b81d9b043ecd17c3d0749f47df63c1b9b27365812d206"
TASK = "task-19f4698041d34fd9bcda"
TASK_RUN = "run-6b3ca4f7c21347b684d9"
STATE = Path(".aos-recovery-20260916/state/z-retire-ungrouped-run")
PREFIX = "a0v-z-ungrouped-run-20260917-v1"


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise RuntimeError(f"existing {path.name} requires read-only reconciliation")
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    os.chmod(path, 0o600)


def _load(name: str) -> dict:
    path = STATE / name
    if not path.is_file() or path.stat().st_mode & 0o777 != 0o600:
        raise RuntimeError(f"private {name} required")
    return json.loads(path.read_text())


def _api(method: str, path: str, body: dict | None = None, headers: dict | None = None) -> dict:
    raw = None if body is None else json.dumps(body, ensure_ascii=False).encode()
    request = Request(API + path, data=raw, method=method, headers={
        "Authorization": "Bearer dev",
        "X-Org-Id": "org-org",
        "X-Project-Id": "dev-project",
        "Content-Type": "application/json",
        **(headers or {}),
    })
    try:
        with urlopen(request, timeout=45) as response:
            return json.loads(response.read())
    except HTTPError as exc:
        code = "HTTP_ERROR"
        try:
            payload = json.loads(exc.read())
            code = payload.get("code") or payload.get("detail", {}).get("code") or code
        except Exception:
            pass
        raise RuntimeError(f"canonical API returned {exc.code}:{code}") from exc


def _current() -> tuple[dict, dict]:
    from aos_api.tenant_scope import TenantScope
    _, runs, data, _ = _stores()
    scope = TenantScope("org-org", "dev-project")
    view = runs.get(scope, RUN)
    return (
        {"authority": view.authority.model_dump(mode="json", by_alias=True),
         "state": view.state.model_dump(mode="json", by_alias=True)},
        data.get_current(scope, REQUIREMENT).model_dump(mode="json", by_alias=True),
    )


def _stores():
    from a0v_formal_text_model_renewal import database_connect
    from aos_api.aip_business_investigation_compile_saga import BusinessInvestigationCompilationReceiptStore
    from aos_api.aip_business_investigation_runtime import BusinessInvestigationRuntimeBinder
    from aos_api.aip_task_store import AipTaskStore
    from aos_api.data_requirement_store import DataRequirementStore
    from aos_api.ecommerce_business_investigation_case import BusinessInvestigationCaseStore
    from aos_api.ecommerce_business_investigation_data_command import EcommerceBusinessInvestigationDataCommandService
    from aos_api.ecommerce_business_investigation_run import BusinessInvestigationRunStore
    base = database_connect("aos_meta_head")
    @contextmanager
    def factory(scope):
        with base(scope) as conn:
            conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)", scope.key)
            yield conn
    runs = BusinessInvestigationRunStore(factory)
    data = DataRequirementStore(factory)
    commands = EcommerceBusinessInvestigationDataCommandService(
        case_store=BusinessInvestigationCaseStore(factory), run_store=runs,
        receipt_store=BusinessInvestigationCompilationReceiptStore(factory),
        runtime_binder=BusinessInvestigationRuntimeBinder(AipTaskStore(factory)),
        data_store=data,
    )
    return factory, runs, data, commands


def audit() -> dict:
    from a0v_formal_text_model_renewal import database_connect
    run, requirement = _current()
    with database_connect("aos_meta_head")() as conn:
        delivery = conn.execute(
            """SELECT d.state,d.attempt,d.failure_code,d.completion_fulfillment_ref,
                      d.completion_analysis_ref
                 FROM data_requirement_outbox_delivery d
                 JOIN data_requirement_outbox o USING(org_id,project_id,outbox_id)
                WHERE d.org_id='org-org' AND d.project_id='dev-project'
                  AND o.requirement_id=%s""", (REQUIREMENT,),
        ).fetchall()
        fulfillment = conn.execute(
            """SELECT count(*) AS n FROM data_fulfillment_receipt
                WHERE org_id='org-org' AND project_id='dev-project' AND requirement_id=%s""",
            (REQUIREMENT,),
        ).fetchone()["n"]
        group = conn.execute(
            """SELECT count(*) AS n FROM pipeline_snapshot_group_member
                WHERE org_id='org-org' AND project_id='dev-project'
                  AND run_id='scr-bddff0a74c2a4365'"""
        ).fetchone()["n"]
        slot = conn.execute(
            """SELECT count(*) AS n FROM ecommerce_investigation_run_active_slot
                WHERE org_id='org-org' AND project_id='dev-project' AND run_id=%s""", (RUN,),
        ).fetchone()["n"]
    return dict(run=run, requirement=requirement, delivery=[dict(row) for row in delivery],
                fulfillmentCount=fulfillment, snapshotGroupMemberCount=group, activeSlotCount=slot)


def reject() -> dict:
    intent_path = STATE / "reject-intent.json"
    run, requirement = _current()
    pending = run["state"].get("pendingRequirementRef")
    if (run["state"]["version"], run["state"]["lifecycle"], run["state"]["control"]) != (2, "WAITING_DATA", "RUNNING"):
        raise RuntimeError("exact WAITING_DATA Run v2 required")
    if pending is None or pending["resourceId"] != REQUIREMENT or pending["revision"] != 1:
        raise RuntimeError("exact pending Requirement r1 required")
    if (requirement["revision"], requirement["status"]) not in ((1, "requested"), (2, "rejected")):
        raise RuntimeError("requested or partially committed rejected Requirement required")
    body = {"decision": "reject", "reason":
        "原源 Run 缺少完整 snapshot group claim/input，无法证明十二源同一截止时点；Requirement 已过期，禁止补造旧组或重领 failed Outbox。"}
    intent = dict(operation="confirm-data-requirement", runId=RUN, expectedVersion=2,
                  idempotencyKey=PREFIX + "-reject-requirement", body=body)
    if intent_path.exists():
        if _load("reject-intent.json") != intent or not (STATE / "reject-http-405.json").is_file():
            raise RuntimeError("reject intent requires exact transport reconciliation")
        _, _, data, _ = _stores()
        from aos_api.tenant_scope import TenantScope
        saved = data.find_command_receipt(TenantScope("org-org", "dev-project"), "reject", intent["idempotencyKey"])
        if saved is not None and (saved.authority.revision != 2
                or saved.authority.status.value != "rejected"
                or saved.authority.blockers[0].required_action != body["reason"]):
            raise RuntimeError("reject command Receipt differs")
    else:
        _write(intent_path, intent)
    _, _, _, commands = _stores()
    from aos_api.ecommerce_business_investigation_data_command import ConfirmBusinessInvestigationDataRequirementCommand
    from aos_api.tenant_scope import TenantScope
    response = commands.confirm_requirement(
        TenantScope("org-org", "dev-project"), RUN,
        ConfirmBusinessInvestigationDataRequirementCommand.model_validate(body),
        expected_version=2, idempotency_key=intent["idempotencyKey"],
        actor="a0v-ecommerce-growth-1.4-runtime-owner", occurred_at=datetime.now(UTC),
    )
    result = response.model_dump(mode="json", by_alias=True)
    _write(STATE / "reject-result.json", result)
    return result


def cancel() -> dict:
    rejected = _load("reject-result.json")
    if (STATE / "cancel-intent.json").exists():
        raise RuntimeError("cancel intent already exists; reconcile without resending")
    run, requirement = _current()
    if (requirement["revision"], requirement["status"]) != (2, "rejected"):
        raise RuntimeError("formal rejected Requirement r2 required")
    if rejected["requirementRef"]["revision"] != 2 or rejected["runAuthority"]["version"] != 3:
        raise RuntimeError("reject Receipt differs")
    if (run["state"]["version"], run["state"]["lifecycle"], run["state"]["control"]) != (3, "PREPARING", "CANCELLED"):
        raise RuntimeError("exact cancelled Run v3 required")
    intent = dict(operation="verify-cancelled-run", runId=RUN, expectedVersion=3,
                  sourceIdempotencyKey=PREFIX + "-reject-requirement")
    _write(STATE / "cancel-intent.json", intent)
    result = {"outcome": "RUN_CANCELLED_BY_REJECT_SAGA", "authority": run["state"],
              "requirementRef": rejected["requirementRef"], "databaseWrites": 0}
    _write(STATE / "cancel-result.json", result)
    return result


def task_cancel() -> dict:
    from aos_api.aip_task_store import AipTaskStore
    from aos_api.tenant_scope import TenantScope
    _load("cancel-result.json")
    scope = TenantScope("org-org", "dev-project")
    current_audit = audit()
    if (current_audit["run"]["state"]["version"],
            current_audit["run"]["state"]["control"],
            current_audit["activeSlotCount"],
            current_audit["requirement"]["revision"],
            current_audit["requirement"]["status"]) != (3, "CANCELLED", 0, 2, "rejected"):
        raise RuntimeError("formal domain Run retirement required before TaskRun cancellation")
    factory, _, _, _ = _stores()
    tasks = AipTaskStore(factory)
    task_run = tasks.get_run(scope, TASK_RUN)
    task = tasks.get_task(scope, TASK)
    intent = dict(operation="cancel-aip-task-run", taskId=TASK, taskRunId=TASK_RUN,
                  expectedTaskVersion=5, expectedTaskRunVersion=3,
                  idempotencyKey=PREFIX + "-cancel-task-run",
                  reason="关联领域 Run 因原源缺失完整 snapshot group 已正式取消。")
    intent_path = STATE / "task-cancel-intent.json"
    result_path = STATE / "task-cancel-result.json"
    if intent_path.exists():
        if _load("task-cancel-intent.json") != intent:
            raise RuntimeError("TaskRun cancel intent differs")
        if result_path.exists():
            return _load("task-cancel-result.json")
    else:
        if (task_run.id, task_run.task_id, task_run.version, task_run.status.value,
                task.id, task.version, task.status.value) != (
                TASK_RUN, TASK, 3, "paused", TASK, 5, "paused"):
            raise RuntimeError("exact paused Task/TaskRun versions required")
        _write(intent_path, intent)
    response = tasks.cancel_run(
        scope, TASK_RUN, expected_run_version=3, expected_task_version=5,
        actor="a0v-ecommerce-growth-1.4-runtime-owner",
        idempotency_key=intent["idempotencyKey"], reason=intent["reason"],
    )
    result = response.model_dump(mode="json", by_alias=True)
    if result["run"]["status"] != "cancelled" or result["task"]["status"] != "cancelled":
        raise RuntimeError("canonical Task/TaskRun cancellation differs")
    _write(result_path, result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("audit", "reject", "cancel", "task-cancel"))
    phase = parser.parse_args().phase
    result = {"audit": audit, "reject": reject, "cancel": cancel, "task-cancel": task_cancel}[phase]()
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
