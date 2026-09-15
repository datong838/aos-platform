"""Receipt-first controls for one current QYH Product snapshot and event handoff."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
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
MAKER = "user:dev"
CHECKER = "a0v-ecommerce-growth-1.4-approval-checker"
CASE_ID = "case-qyh-full-store-baseline-20260915"
POLICY_ID = "product-event-qyh-full-store-baseline-20260915"
API = "http://127.0.0.1:18181"
OLD_REGISTRATION_INSTALLATION = "97aeb2e7-59ba-40f6-89a3-fb0293bc0497"
OLD_REGISTRATION_KEY = "a0v-qyh-reboot-operating-registration-v1"
REGISTRATION_GROUP_ID = "6a402d31-83ad-546c-807f-508c87498ce1"
CUTOVER_OPERATION_ID = "b5555da7-6d0e-52f8-a443-d39b8264f40c"
REGISTRATION_KEY = "a0v-qyh-niushop-1.23-generation-e-registration-v1"


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
    from a0v_product_controlled_api import load_launcher
    load_launcher().configure_environment()
    os.environ["AOS_EXTENSION_RUNTIME_HOST_ENABLED"] = "0"
    sys.path.insert(0, str(ROOT / "services/aos-api"))
    from aos_api.asset_registry.control_wiring import build_runtime_control_plane
    from aos_api.ecommerce_growth_registration_connection import registration_connection

    return preflight, build_runtime_control_plane(registration_connect=registration_connection)


@contextmanager
def _web_connection(scope):
    from aos_api.extension_runtime.runtime_connections import runtime_web_identity_connection
    from aos_api.tenant_scope import apply_transaction_scope
    with runtime_web_identity_connection() as conn:
        apply_transaction_scope(conn, scope)
        yield conn


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


def api(method: str, path: str, body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None) -> tuple[int, dict[str, Any]]:
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode()
    request_headers = {
        "Authorization": "Bearer dev", "X-Org-Id": "org-org", "X-Project-Id": "dev-project",
        "Content-Type": "application/json",
    }
    request_headers.update(headers or {})
    request = Request(API + path, data=data, method=method, headers=request_headers)
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


def _scope_and_connection():
    from aos_api.extension_runtime.consumer_connection import consumer_connection
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
    from aos_api.tenant_scope import TenantScope
    scope = TenantScope(**SCOPE)
    return scope, consumer_connection(runtime_worker_connection, SCOPE)


def configure_reviewer(_preflight, _plane) -> dict[str, Any]:
    intent = {"actor": MAKER, "subject": CHECKER, "role": "admin", "workspaceId": SCOPE["project_id"]}
    freeze_or_match(STATE / "reviewer-intent.json", intent)
    api("GET", "/v1/workspaces")
    _status, listed = api("GET", f"/v1/workspaces/{SCOPE['project_id']}/members")
    matches = [item for item in listed.get("items", []) if item.get("subject") == CHECKER]
    if matches:
        if len(matches) != 1 or matches[0].get("role") != "admin":
            raise ValueError("current ProductEvent checker membership differs")
        row, replayed = matches[0], True
    else:
        _status, row = api("POST", f"/v1/workspaces/{SCOPE['project_id']}/members",
                           {"subject": CHECKER, "role": "admin"})
        replayed = False
    return {"outcome": "CURRENT_PRODUCT_EVENT_REVIEWER_CONFIGURED", "member": row,
            "maker": MAKER, "executor": ACTOR, "replayed": replayed}


ACTION_TYPES = (
    {"id": "ecommerce_growth_schedule_put", "name": "保存电商商品事件策略", "objectType": "Case",
     "parameters": [], "requiredMarkings": [], "submissionCriteria": []},
    {"id": "ecommerce_growth_event_control", "name": "启用电商商品事件消费", "objectType": "Case",
     "parameters": [], "requiredMarkings": [], "submissionCriteria": []},
)


def configure_action_types(_preflight, _plane) -> dict[str, Any]:
    intent = {"actor": MAKER, "actionTypes": list(ACTION_TYPES)}
    freeze_or_match(STATE / "action-types-intent.json", intent)
    scope, connection = _scope_and_connection()
    del scope
    with connection as conn:
        rows = {row["id"]: dict(row) for row in conn.execute(
            "SELECT id,name,object_type,parameters,required_markings,submission_criteria FROM meta_action_type WHERE id=ANY(%s)",
            ([item["id"] for item in ACTION_TYPES],),
        ).fetchall()}
    created = []
    for expected in ACTION_TYPES:
        actual = rows.get(expected["id"])
        comparable = None if actual is None else {
            "id": actual["id"], "name": actual["name"], "objectType": actual["object_type"],
            "parameters": actual["parameters"], "requiredMarkings": actual["required_markings"],
            "submissionCriteria": actual["submission_criteria"],
        }
        if comparable is not None and comparable != expected:
            raise ValueError(f"current ActionType differs: {expected['id']}")
        if comparable is None:
            _status, comparable = api("POST", "/v1/actions/types", expected)
            created.append(expected["id"])
    return {"outcome": "CURRENT_PRODUCT_EVENT_ACTION_TYPES_CONFIGURED",
            "actionTypes": [item["id"] for item in ACTION_TYPES], "created": created}


CUTOVER_ACTION_TYPE = {
    "id": "ecommerce_growth_cutover", "name": "切换电商经营九项宿主入口",
    "objectType": "BundleInstallation", "parameters": [], "requiredMarkings": [],
    "submissionCriteria": [],
}


def configure_cutover_action_type(_preflight, _plane) -> dict[str, Any]:
    intent = {"actor": MAKER, "actionType": CUTOVER_ACTION_TYPE}
    freeze_or_match(STATE / "cutover-action-type-intent.json", intent)
    _scope, connection = _scope_and_connection()
    with connection as conn:
        actual = conn.execute(
            "SELECT id,name,object_type,parameters,required_markings,submission_criteria "
            "FROM meta_action_type WHERE id=%s", (CUTOVER_ACTION_TYPE["id"],)
        ).fetchone()
    comparable = None if actual is None else {
        "id": actual["id"], "name": actual["name"], "objectType": actual["object_type"],
        "parameters": actual["parameters"], "requiredMarkings": actual["required_markings"],
        "submissionCriteria": actual["submission_criteria"],
    }
    if comparable is not None and comparable != CUTOVER_ACTION_TYPE:
        raise ValueError("current cutover ActionType differs")
    if comparable is None:
        _status, comparable = api("POST", "/v1/actions/types", CUTOVER_ACTION_TYPE)
    return {"outcome": "CURRENT_PRODUCT_CUTOVER_ACTION_TYPE_CONFIGURED",
            "actionType": comparable, "created": actual is None}


def _current_registration_request(preflight):
    from aos_api.ecommerce_growth_registration_contracts import FirstDispatchRegistrationRequest
    current = preflight.run("preflight")
    if current.get("outcome") != "PRODUCT_CURRENT_PREFLIGHT_GREEN":
        raise ValueError("current E registration preflight required")
    ref = current["currentInstallationRef"]
    binding = current["runtimeBinding"]
    return FirstDispatchRegistrationRequest(
        schemaVersion="aos.ecommerce.first-dispatch-registration/v1",
        installationRef=ref, generation=str(binding["generation"]),
        bindingRevision=binding["revision"], executionEpoch=binding["execution_epoch"],
        configRef=binding["config_ref"], groupId=REGISTRATION_GROUP_ID,
        idempotencyKey=REGISTRATION_KEY,
    )


def withdraw_old_registration(_preflight, plane) -> dict[str, Any]:
    from aos_api.ecommerce_growth_registration_origin import RegistrationWithdrawalRequest
    from aos_api.tenant_scope import TenantScope
    scope = TenantScope(**SCOPE)
    service = plane.first_dispatch_registration_service
    status = service.registration_status(
        scope=scope, installation_id=OLD_REGISTRATION_INSTALLATION, actor=ACTOR)
    if status["state"] == "withdrawn":
        result = service.read_withdrawal_receipt(
            scope=scope, installation_id=OLD_REGISTRATION_INSTALLATION,
            idempotency_key=REGISTRATION_KEY + "-old-withdraw", actor=ACTOR)
        return {"outcome": "OLD_PRODUCT_REGISTRATION_WITHDRAWN", "status": status,
                "receipt": result, "replayed": True}
    if (status["state"] != "registered" or status["allowedActions"] != ["withdraw"]
            or status["executable"] is not False):
        raise ValueError("old registration is not pristine withdraw-only")
    origin = service.read_receipt(
        scope=scope, installation_id=OLD_REGISTRATION_INSTALLATION,
        idempotency_key=OLD_REGISTRATION_KEY, actor=ACTOR)
    if (status["registrationReceiptRef"]["resourceId"] != origin["receiptId"]
            or status["registrationReceiptRef"]["contentHash"] != origin["contentHash"]):
        raise ValueError("old registration origin differs")
    with _scope_and_connection()[1] as conn:
        rows = conn.execute(
            "SELECT operation_id,handler_kind,operation_fence,cutover_group_id,revision "
            "FROM extension_operation_dispatch_binding WHERE org_id=%s AND project_id=%s "
            "ORDER BY operation_id", scope.key).fetchall()
    if (len(rows) != 9 or any(row["handler_kind"] != "legacy" or row["operation_fence"] is not True
                              or row["revision"] != 1
                              or str(row["cutover_group_id"]) != origin["groupId"] for row in rows)):
        raise ValueError("old registration dispatch group differs")
    request = RegistrationWithdrawalRequest(
        registrationReceiptRef=status["registrationReceiptRef"],
        expectedInstallationEtag=status["expectedInstallationEtag"],
        idempotencyKey=REGISTRATION_KEY + "-old-withdraw")
    material = request.model_dump(mode="json", by_alias=True)
    freeze_or_match(STATE / "registration-withdraw-intent.json", material)
    result = service.withdraw(scope=scope, installation_id=OLD_REGISTRATION_INSTALLATION,
                              request=request, actor=ACTOR)
    return {"outcome": "OLD_PRODUCT_REGISTRATION_WITHDRAWN", "status": status,
            "origin": origin, "receipt": result, "replayed": result["replayed"]}


def register_current_e(preflight, plane) -> dict[str, Any]:
    from aos_api.tenant_scope import TenantScope
    scope = TenantScope(**SCOPE)
    service = plane.first_dispatch_registration_service
    request = _current_registration_request(preflight)
    material = request.model_dump(mode="json", by_alias=True)
    freeze_or_match(STATE / "registration-register-intent.json", material)
    status = service.registration_status(
        scope=scope, installation_id=request.installationRef.installation_id, actor=ACTOR)
    if status["state"] == "registered":
        result = service.read_receipt(scope=scope,
            installation_id=request.installationRef.installation_id,
            idempotency_key=REGISTRATION_KEY, actor=ACTOR)
        if result["requestHash"] != request.request_hash():
            raise ValueError("current E registration replay differs")
        replayed = True
    elif status["state"] == "unregistered":
        result = service.register(scope=scope, request=request, actor=ACTOR)
        replayed = result["replayed"]
    else:
        raise ValueError("current E registration state differs")
    return {"outcome": "CURRENT_E_FIRST_DISPATCH_REGISTERED", "request": material,
            "receipt": result, "replayed": replayed}


def _cutover_policy_ref() -> dict[str, Any]:
    from aos_api.asset_registry.canonical_json import canonical_sha256
    policy = {
        "schemaVersion": "aos.runtime-cutover-policy/v1",
        "policyId": "qyh-niushop-1.23-generation-e-activation", "revision": 1,
        "tenant": {"orgId": SCOPE["org_id"], "projectId": SCOPE["project_id"]},
        "targetInstallationId": _current_registration_result()["request"]["installationRef"]["installationId"],
        "externalEffectsAllowed": False, "fallbackAllowed": False,
        "checkpoint": {"legacyEntry": "canonical-router", "version": 1},
    }
    freeze_or_match(STATE / "cutover-policy.json", policy)
    return {"resourceType": "RuntimeCutoverPolicyRevision", "resourceId": policy["policyId"],
            "revision": policy["revision"], "contentHash": canonical_sha256(policy)}


def _current_registration_result() -> dict[str, Any]:
    result = load_result("registration-register")
    if result.get("outcome") != "CURRENT_E_FIRST_DISPATCH_REGISTERED":
        raise ValueError("current E registration result required")
    return result


def _registration_receipt_ref() -> dict[str, Any]:
    receipt = _current_registration_result()["receipt"]
    return {"resourceType": "FirstDispatchRegistrationReceipt", "resourceId": receipt["receiptId"],
            "revision": 1, "contentHash": receipt["contentHash"]}


def _cutover_target() -> dict[str, Any]:
    registered = _current_registration_result()
    request = registered["request"]
    return {
        "cutoverGroupId": request["groupId"], "expectedGroupRevision": 1,
        "targetInstallationId": request["installationRef"]["installationId"],
        "targetGeneration": request["generation"],
        "targetExecutionEpoch": request["executionEpoch"],
        "targetRuntimeRevision": request["bindingRevision"],
        "operationIds": _growth_operations(), "policyRef": _cutover_policy_ref(),
        "registrationReceiptRef": _registration_receipt_ref(),
    }


def _growth_operations() -> list[str]:
    from aos_api.ecommerce_growth_host_composition import ECOMMERCE_GROWTH_OPERATIONS
    return sorted(ECOMMERCE_GROWTH_OPERATIONS)


def approve_cutover(_preflight, _plane) -> dict[str, Any]:
    payload = _cutover_target()
    frozen = {"maker": MAKER, "checker": CHECKER, "executor": ACTOR, "payload": payload}
    freeze_or_match(STATE / "cutover-approval-intent.json", frozen)
    bundle, ref = _approve("ecommerce_growth_cutover", payload,
                           "a0v-qyh-niushop-1.23-generation-e-cutover-v1")
    return {"outcome": "CURRENT_E_CUTOVER_APPROVED", "proposalId": bundle.proposal.id,
            "approvalRef": ref, "payload": payload}


def cutover_prepare(_preflight, plane) -> dict[str, Any]:
    from aos_api.ecommerce_growth_cutover import CutoverPrepareRequest
    from aos_api.tenant_scope import TenantScope
    target = load_result("cutover-approval")["payload"]
    request = CutoverPrepareRequest(
        cutoverOperationId=CUTOVER_OPERATION_ID,
        idempotencyKey="a0v-qyh-niushop-1.23-generation-e-cutover-prepare-v1",
        approvalRef=load_result("cutover-approval")["approvalRef"],
        checkpoint={"legacyEntry": "canonical-router", "version": 1},
        occurrenceWatermark=None, pendingTargetReceiptRefs=[], **target)
    material = request.model_dump(mode="json", by_alias=True)
    freeze_or_match(STATE / "cutover-prepare-intent.json", material)
    receipt = plane.ecommerce_growth_cutover_service.prepare_activation(
        TenantScope(**SCOPE), request, actor=ACTOR)
    return {"outcome": "CURRENT_E_CUTOVER_PREPARED",
            "receipt": receipt.model_dump(mode="json", by_alias=True)}


def _cutover_commit_request():
    from aos_api.ecommerce_growth_cutover import CutoverCommitRequest
    prepared = load_result("cutover-prepare")["receipt"]
    return CutoverCommitRequest(
        cutoverOperationId=CUTOVER_OPERATION_ID,
        idempotencyKey="a0v-qyh-niushop-1.23-generation-e-cutover-commit-v1",
        prepareReceiptRef={"resourceType": "CutoverPrepareReceipt",
            "resourceId": prepared["receiptId"], "revision": 1,
            "contentHash": prepared["contentHash"]})


def cutover_pause(_preflight, plane) -> dict[str, Any]:
    from aos_api.tenant_scope import TenantScope
    request = _cutover_commit_request()
    material = request.model_dump(mode="json", by_alias=True)
    freeze_or_match(STATE / "cutover-pause-intent.json", material)
    receipt = plane.ecommerce_growth_cutover_service.begin_activation_commit(
        TenantScope(**SCOPE), request, actor=ACTOR)
    return {"outcome": "CURRENT_E_CUTOVER_CLAIMS_PAUSED",
            "receipt": receipt.model_dump(mode="json", by_alias=True)}


def cutover_commit(_preflight, plane) -> dict[str, Any]:
    from aos_api.tenant_scope import TenantScope
    request = _cutover_commit_request()
    material = request.model_dump(mode="json", by_alias=True)
    freeze_or_match(STATE / "cutover-commit-intent.json", material)
    receipt = plane.ecommerce_growth_cutover_service.commit_activation(
        TenantScope(**SCOPE), request, actor=ACTOR)
    return {"outcome": "CURRENT_E_CUTOVER_COMMITTED",
            "receipt": receipt.model_dump(mode="json", by_alias=True)}


def _cutover_finalize_request():
    from aos_api.ecommerce_growth_cutover import CutoverFinalizeRequest
    committed = load_result("cutover-commit")["receipt"]
    return CutoverFinalizeRequest(
        cutoverOperationId=CUTOVER_OPERATION_ID,
        idempotencyKey="a0v-qyh-niushop-1.23-generation-e-cutover-finalize-v1",
        commitReceiptRef={"resourceType": "CutoverCommitReceipt",
            "resourceId": committed["receiptId"], "revision": 1,
            "contentHash": committed["contentHash"]})


def cutover_validate(_preflight, plane) -> dict[str, Any]:
    from aos_api.tenant_scope import TenantScope
    request = _cutover_finalize_request()
    material = request.model_dump(mode="json", by_alias=True)
    freeze_or_match(STATE / "cutover-validate-intent.json", material)
    receipt = plane.ecommerce_growth_cutover_service.validate_activation(
        TenantScope(**SCOPE), request, actor=ACTOR)
    return {"outcome": "CURRENT_E_CUTOVER_VALIDATED",
            "receipt": receipt.model_dump(mode="json", by_alias=True)}


def cutover_resume(_preflight, plane) -> dict[str, Any]:
    from aos_api.ecommerce_growth_cutover import CutoverExactRef
    from aos_api.tenant_scope import TenantScope
    request = _cutover_finalize_request()
    validated = load_result("cutover-validate")["receipt"]
    validation_ref = CutoverExactRef(
        resourceType="CutoverValidateReceipt", resourceId=validated["receiptId"],
        revision=1, contentHash=validated["contentHash"])
    material = {"request": request.model_dump(mode="json", by_alias=True),
                "validateReceiptRef": validation_ref.model_dump(mode="json", by_alias=True)}
    freeze_or_match(STATE / "cutover-resume-intent.json", material)
    receipt = plane.ecommerce_growth_cutover_service.resume_activation(
        TenantScope(**SCOPE), request, validate_receipt_ref=validation_ref, actor=ACTOR)
    return {"outcome": "CURRENT_E_CUTOVER_RESUMED",
            "receipt": receipt.model_dump(mode="json", by_alias=True)}


def observe_cutover(_preflight, plane) -> dict[str, Any]:
    from aos_api.tenant_scope import TenantScope
    scope = TenantScope(**SCOPE)
    with _scope_and_connection()[1] as conn:
        rows = [dict(row) for row in conn.execute(
            "SELECT operation_id,handler_kind,installation_id,generation,execution_epoch,"
            "operation_fence,revision,cutover_group_id,cutover_group_revision "
            "FROM extension_operation_dispatch_binding WHERE org_id=%s AND project_id=%s "
            "ORDER BY operation_id", scope.key).fetchall()]
        canary = conn.execute(
            "SELECT count(*) AS n FROM extension_dispatch_cutover_operation "
            "WHERE org_id='dev-org' AND project_id='dev-project'").fetchone()["n"]
    expected = _cutover_target()
    if (len(rows) != 9 or [row["operation_id"] for row in rows] != expected["operationIds"]
            or any(row["handler_kind"] != "extension" or row["operation_fence"] is not False
                   or str(row["installation_id"]) != expected["targetInstallationId"]
                   or str(row["generation"]) != expected["targetGeneration"]
                   or row["execution_epoch"] != expected["targetExecutionEpoch"] for row in rows)):
        raise ValueError("current E cutover dispatch readback differs")
    if canary != 0:
        raise ValueError("cutover canary tenant was written")
    return {"outcome": "CURRENT_E_CUTOVER_OBSERVED", "dispatch": rows,
            "canaryCutoverOperations": canary}


def configure_brief(_preflight, _plane) -> dict[str, Any]:
    executed = load_result("execute")
    run = executed["run"]["body"]
    run_id = run.get("id") or run.get("runId")
    if executed.get("outcome") != "CURRENT_PRODUCT_SNAPSHOT_SUCCEEDED" or not run_id:
        raise ValueError("succeeded Product snapshot Run required for business brief")
    task_intent = {"type": "ecommerce.investigation", "title": "栖月汇全店基线与商品尖刀验证",
                   "description": "经营参谋依据真实商城数据识别商品结构、变化和数据缺口。", "priority": 80,
                   "goal": {"analysisType": "initial_store_analysis", "platform": "niushop", "shopId": "1",
                            "externalEffectsAllowed": False}}
    freeze_or_match(STATE / "business-task-intent.json", task_intent)
    _status, task = api("POST", "/v1/aip/tasks", task_intent,
                        {"Idempotency-Key": "a0v-qyh-product-event-business-task-20260915-v1"})
    intent = {
        "taskId": task["id"],
        "briefType": "ecommerce.business-investigation.initial-store-analysis",
        "schemaRef": {"resourceType": "Schema", "resourceId": "EcommerceBusinessInvestigationBrief.v1",
                      "revision": "1", "authority": "aos-ecommerce-growth"},
        "spec": {
            "businessQuestion": "基于栖月汇当前全店与商品真实数据，识别商品结构、在售与下架变化，并列出继续形成经营建议所需的数据缺口。",
            "analysisType": "initial_store_analysis", "platform": "niushop", "shopId": "1",
            "sourceRefs": [
                {"resourceType": "PipelineRun", "resourceId": run_id, "authority": "pipeline-runtime"},
                {"resourceType": "Dataset", "resourceId": "ri.aos.main.dataset.P02-product-qyh",
                 "authority": "dataset-runtime"},
            ],
            "constraints": {"upstreamReadOnly": True, "externalEffectsAllowed": False,
                            "missingDataOutcome": "WAITING_DATA"},
            "requestedOutputs": ["source-backed-findings", "data-requirements", "growth-plan-candidates"],
        },
    }
    freeze_or_match(STATE / "brief-v2-intent.json", intent)
    _status, created = api("POST", "/v1/aip/production-contracts/task-briefs", intent,
                           {"Idempotency-Key": "a0v-qyh-product-event-brief-create-20260915-v2"})
    brief_id = created["briefId"]
    _status, frozen = api("POST", f"/v1/aip/production-contracts/task-briefs/{brief_id}/freeze",
                          {"expectedVersion": created["version"]},
                          {"Idempotency-Key": "a0v-qyh-product-event-brief-freeze-20260915-v2"})
    if frozen.get("lifecycle") != "frozen":
        raise ValueError("frozen ProductEvent business brief required")
    return {"outcome": "CURRENT_PRODUCT_EVENT_BRIEF_FROZEN", "task": task, "brief": frozen}


def _runtime_target(preflight, conn):
    from aos_api.ecommerce_growth_canonical_router import ExpectedRuntimeTarget
    create = json.loads(preflight.CURRENT_CREATE.read_text(encoding="utf-8"))
    row = conn.execute("""SELECT generation,execution_epoch FROM extension_runtime_binding
        WHERE org_id=%s AND project_id=%s AND installation_id=%s AND enabled=true AND operation_fence=false""",
        (SCOPE["org_id"], SCOPE["project_id"], create["installationId"])).fetchone()
    if row is None:
        raise ValueError("current executable E runtime required")
    return ExpectedRuntimeTarget(create["installationId"], str(row["generation"]), row["execution_epoch"])


def configure_case(preflight, plane) -> dict[str, Any]:
    from aos_api.auth import Principal
    from aos_api.ecommerce_business_investigation_case import BusinessInvestigationCaseLifecycle, BusinessInvestigationCaseStore
    from aos_api.ecommerce_growth_canonical_router import EcommerceGrowthCanonicalRouter
    from aos_api.ecommerce_growth_host_composition import build_scoped_ecommerce_growth_registry
    from aos_api.ecommerce_growth_host_ports import HostTransaction
    from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
    from aos_api.ecommerce_business_investigation_case_selection import (
        PostgresCanonicalShopSelectionSource, CatalogCanonicalProfileSelectionSource)
    from aos_api.ecommerce_business_investigation_aip_composition import PostgresAipProductionCompositionSource
    from aos_api.tenant_scope import TenantScope
    scope = TenantScope(**SCOPE)
    brief = load_result("brief")["brief"]
    with _scope_and_connection()[1] as conn:
        factory = TransactionBoundConnectFactory(HostTransaction(conn), scope)
        shop = PostgresCanonicalShopSelectionSource(factory).read(scope)
        profile = CatalogCanonicalProfileSelectionSource(
            composition_source=PostgresAipProductionCompositionSource(factory)).read(scope, "initial_store_analysis")
        if shop is None or profile is None:
            raise ValueError("current canonical Case selection required")
        target = _runtime_target(preflight, conn)
    request = {"caseId": CASE_ID, "analysisType": "initial_store_analysis",
               "title": "栖月汇全店基线与商品尖刀验证", "purposeCode": "initial_store_analysis",
               "channelRef": shop.channel_ref.model_dump(by_alias=True, mode="json"),
               "businessEntityRef": shop.business_entity_ref.model_dump(by_alias=True, mode="json"),
               "entityChannelBindingRef": shop.entity_channel_binding_ref.model_dump(by_alias=True, mode="json"),
               "investigationProfileRef": profile.investigation_profile_ref.model_dump(by_alias=True, mode="json"),
               "scopeRef": profile.scope_ref.model_dump(by_alias=True, mode="json"), "schedulePolicyRef": None}
    brief_hash = brief["contentHash"]
    if not brief_hash.startswith("sha256:"):
        brief_hash = "sha256:" + brief_hash
    command = {"idempotencyKey": "a0v-qyh-product-event-case-create-20260915-v1", "case": request,
               "taskBriefRef": {"resourceType": "TaskBriefRevision", "resourceId": brief["briefId"],
                                "revision": brief["revision"], "contentHash": brief_hash, "receiptId": None}}
    freeze_or_match(STATE / "case-intent.json", command)
    principal = Principal(subject=MAKER, org_id=scope.org_id, project_id=scope.project_id, roles=["owner"])
    router = EcommerceGrowthCanonicalRouter(build_scoped_ecommerce_growth_registry(principal, plane.pipeline_control_factory))
    created = router.dispatch(scope=scope, operation_id="ecommerce_growth_case_put", command=command,
                              expected_runtime=target)
    authority = created["authority"]
    if authority["lifecycle"] == "DRAFT":
        changed = BusinessInvestigationCaseStore(_web_connection).transition(scope, CASE_ID, BusinessInvestigationCaseLifecycle.ACTIVE,
            expected_version=authority["version"], idempotency_key="a0v-qyh-product-event-case-activate-20260915-v1",
            actor=MAKER, occurred_at=datetime.now(timezone.utc))
        authority = changed.authority.model_dump(by_alias=True, mode="json")
    if authority["lifecycle"] != "ACTIVE":
        raise ValueError("active ProductEvent Case required")
    return {"outcome": "CURRENT_PRODUCT_EVENT_CASE_ACTIVE", "authority": authority,
            "createReplayed": created["replayed"]}


def refresh_event_authority(preflight, plane) -> dict[str, Any]:
    from aos_api.pipeline_runtime_control_contracts import PipelineRuntimeControlDraft, PipelineSourceSelectionDraft
    from aos_api.pipeline_schedule_control_owner import PipelineScheduleControlOwner
    from aos_api.tenant_scope import TenantScope
    prepared = preflight.run("preflight")
    if prepared.get("outcome") != "PRODUCT_CURRENT_PREFLIGHT_GREEN":
        raise ValueError("fresh Product preflight required")
    scope = TenantScope(**SCOPE)
    service = plane.pipeline_control_factory.build(scope)
    with _scope_and_connection()[1] as conn:
        prior_selection = service.selections.read_current(conn, scope=scope, installation_id=prepared["currentInstallationRef"]["installationId"], pipeline_id=PIPELINE)
        prior_control = service.controls.read_current(conn, scope=scope, installation_id=prepared["currentInstallationRef"]["installationId"], pipeline_id=PIPELINE)
        prior_binding = PipelineScheduleControlOwner(controls=service.controls).read_latest(conn, scope=scope, schedule_id=SCHEDULE)
    if any(value is None for value in (prior_selection, prior_control, prior_binding)):
        raise ValueError("current Product authority chain required")
    draft = prepared["draft"]
    intent = {"actor": ACTOR, "selectionPreviousRef": prior_selection.ref.model_dump(by_alias=True, mode="json"),
              "controlPreviousRef": prior_control.ref.model_dump(by_alias=True, mode="json"),
              "bindingPreviousRef": prior_binding.ref.model_dump(by_alias=True, mode="json"), "draft": draft}
    freeze_or_match(STATE / "event-refresh-intent.json", intent)
    selection = service.approve_selection(draft=PipelineSourceSelectionDraft.model_validate(draft), actor=ACTOR,
        idempotency_key="a0v-p02-e-event-selection-20260915-v3", previous_ref=intent["selectionPreviousRef"])
    control_draft = {**draft, "schemaVersion": "aos.pipeline-runtime-control-draft/v1",
                     "sourceSelectionRef": selection.model_dump(by_alias=True, mode="json")}
    control = service.approve_control(draft=PipelineRuntimeControlDraft.model_validate(control_draft), actor=ACTOR,
        idempotency_key="a0v-p02-e-event-control-20260915-v3", previous_ref=intent["controlPreviousRef"])
    binding = service.bind_schedule(pipeline_id=PIPELINE, schedule_id=SCHEDULE, control_ref=control,
        actor=ACTOR, idempotency_key="a0v-p02-e-event-binding-20260915-v3", previous_ref=intent["bindingPreviousRef"])
    return {"outcome": "CURRENT_PRODUCT_EVENT_AUTHORITY_REFRESHED", "draft": draft,
            "selectionRef": selection.model_dump(by_alias=True, mode="json"),
            "controlRef": control.model_dump(by_alias=True, mode="json"),
            "bindingRef": binding.model_dump(by_alias=True, mode="json"), "runtimeBinding": prepared["runtimeBinding"]}


def _approval_ref(bundle) -> dict[str, Any]:
    from aos_api.aip_budget_reservation_store import canonical_hash
    approved = [item for item in bundle.approvals if item.decision.value == "approved"]
    if len(approved) != 1:
        raise ValueError("one independent approval required")
    event = approved[0]
    row = {"approval_event_id": event.id, "proposal_id": event.proposal_id,
           "proposal_version": event.proposal_version, "proposal_hash": event.proposal_hash,
           "decision": event.decision.value, "actor_id": event.actor.actor_id, "reason": event.reason,
           "expires_at": event.expires_at, "created_at": event.created_at,
           "action_binding_hash": event.action_binding_hash}
    return {"resourceType": "ActionApprovalEvent", "resourceId": event.id,
            "revision": event.proposal_version, "contentHash": canonical_hash(row, prefixed=True), "receiptId": None}


def _approve(action_type: str, payload: dict[str, Any], key: str):
    from aos_api.aip_action_models import CreateActionProposalRequest, DecideActionProposalRequest
    from aos_api.aip_action_service import AipActionService
    from aos_api.aip_action_store import AipActionStore
    from aos_api.aip_contracts import ApprovalDecision
    from aos_api.auth import Principal
    service = AipActionService(AipActionStore(_web_connection))
    maker = Principal(subject=MAKER, org_id=SCOPE["org_id"], project_id=SCOPE["project_id"], roles=["owner"])
    checker = Principal(subject=CHECKER, org_id=SCOPE["org_id"], project_id=SCOPE["project_id"], roles=["admin"])
    expiry = datetime.now(timezone.utc) + timedelta(minutes=45)
    proposal = service.create_proposal(maker, key + ":proposal", CreateActionProposalRequest(
        actionTypeId=action_type, purpose="栖月汇真实商品事件首链内部配置", payload=payload, expiresAt=expiry))
    reviewed = service.decide(checker, proposal.proposal.id, key + ":approval", DecideActionProposalRequest(
        expectedProposalVersion=proposal.proposal.version, expectedProposalHash=proposal.proposal.proposal_hash,
        decision=ApprovalDecision.APPROVED, reason="当前租户真实首链内部配置独立复核",
        approvalExpiresAt=datetime.now(timezone.utc) + timedelta(minutes=30)))
    if reviewed.proposal.status.value != "approved":
        raise ValueError("current ProductEvent proposal approval required")
    return reviewed, _approval_ref(reviewed)


def _event_binding_material():
    from aos_api.ecommerce_business_investigation_case import BusinessInvestigationCaseStore
    from aos_api.tenant_scope import TenantScope
    from ecommerce_growth.ecommerce_business_investigation_case import BusinessInvestigationCase, canonical_hash
    from ecommerce_growth.ecommerce_product_event_binding import prepare_event_case_binding
    from ecommerce_growth.ecommerce_product_event_schedule import ProductEventSchedulePolicy
    refresh = load_result("event-refresh")
    scope = TenantScope(**SCOPE)
    case = BusinessInvestigationCaseStore(_web_connection).get(scope, CASE_ID)
    case_raw = case.model_dump(by_alias=True, mode="json")
    current = BusinessInvestigationCase.from_authority(case_raw)
    start = datetime.fromisoformat(refresh["draft"]["notBefore"])
    end = datetime.fromisoformat(refresh["draft"]["expiresAt"])
    raw = {"schemaVersion": "aos.ecommerce.product-event-schedule-policy/v1", "tenant": {"orgId": scope.org_id, "projectId": scope.project_id},
           "schedulePolicyId": POLICY_ID, "revision": 1, "priorRef": None,
           "caseRef": {"resourceType": "BusinessInvestigationCaseRevision", "resourceId": case.case_id,
                       "revision": case.revision, "contentHash": case.content_hash, "receiptId": None},
           "sourceSelectionRef": refresh["selectionRef"], "methodRef": case_raw["investigationProfileRef"],
           "platform": "niushop", "shopId": "1", "objectTypes": ["Product"],
           "effectiveFrom": start.isoformat(), "effectiveUntil": end.isoformat(),
           "maxSourceAgeSeconds": 3600, "recoveryWindowSeconds": 900,
           "createdBy": ACTOR, "createdAt": start.isoformat()}
    raw["contentHash"] = canonical_hash(raw)
    policy = ProductEventSchedulePolicy.from_authority(raw)
    return prepare_event_case_binding(current, policy)


def approve_schedule(_preflight, _plane) -> dict[str, Any]:
    from aos_api.aip_budget_reservation_store import canonical_hash
    binding = _event_binding_material(); policy = binding.policy.authority_payload(); case = load_result("case")["authority"]
    payload = {"caseId": CASE_ID, "schedulePolicyId": POLICY_ID, "expectedPolicyRevision": 0,
               "expectedCaseVersion": case["version"], "policyHash": canonical_hash(policy, prefixed=True)}
    freeze_or_match(STATE / "schedule-approval-intent.json", {"maker": MAKER, "checker": CHECKER, "payload": payload})
    bundle, ref = _approve("ecommerce_growth_schedule_put", payload, "a0v-qyh-product-event-schedule-20260915-v1")
    return {"outcome": "CURRENT_PRODUCT_EVENT_SCHEDULE_APPROVED", "proposalId": bundle.proposal.id, "approvalRef": ref}


def put_policy(preflight, plane) -> dict[str, Any]:
    from aos_api.auth import Principal
    from aos_api.ecommerce_growth_canonical_router import EcommerceGrowthCanonicalRouter
    from aos_api.ecommerce_growth_host_composition import build_scoped_ecommerce_growth_registry
    from aos_api.tenant_scope import TenantScope
    binding = _event_binding_material(); scope = TenantScope(**SCOPE)
    command = {"idempotencyKey": "a0v-qyh-product-event-policy-put-20260915-v1", "expectedPolicyRevision": 0,
               "expectedCaseVersion": load_result("case")["authority"]["version"],
               "policy": {k: v for k, v in binding.policy.authority_payload().items() if k != "tenant"},
               "caseAuthority": {k: v for k, v in binding.case.authority_payload().items() if k != "tenant"},
               "approvalRef": load_result("schedule-approval")["approvalRef"]}
    freeze_or_match(STATE / "policy-intent.json", command)
    principal = Principal(subject=ACTOR, org_id=scope.org_id, project_id=scope.project_id, roles=["admin"])
    router = EcommerceGrowthCanonicalRouter(build_scoped_ecommerce_growth_registry(principal, plane.pipeline_control_factory))
    with _scope_and_connection()[1] as conn: target = _runtime_target(preflight, conn)
    result = router.dispatch(scope=scope, operation_id="ecommerce_growth_schedule_put", command=command, expected_runtime=target)
    return {"outcome": "CURRENT_PRODUCT_EVENT_POLICY_SAVED", **result}


def approve_event_control(_preflight, _plane) -> dict[str, Any]:
    policy_ref = load_result("policy")["receiptRef"]
    intent = {"schemaVersion": "aos.ecommerce.product-event-control-command/v1",
              "idempotencyKey": "a0v-qyh-product-event-enable-20260915-v1", "policyRef": policy_ref,
              "expectedBindingRevision": 0, "intent": "enable"}
    payload = {"caseId": CASE_ID, "schedulePolicyId": POLICY_ID, "controlIntent": intent}
    freeze_or_match(STATE / "control-approval-intent.json", {"maker": MAKER, "checker": CHECKER, "payload": payload})
    bundle, ref = _approve("ecommerce_growth_event_control", payload, "a0v-qyh-product-event-control-20260915-v1")
    return {"outcome": "CURRENT_PRODUCT_EVENT_CONTROL_APPROVED", "proposalId": bundle.proposal.id,
            "approvalRef": ref, "controlIntent": intent}


def enable_event(preflight, plane) -> dict[str, Any]:
    from aos_api.auth import Principal
    from aos_api.ecommerce_growth_canonical_router import EcommerceGrowthCanonicalRouter
    from aos_api.ecommerce_growth_host_composition import build_scoped_ecommerce_growth_registry
    from aos_api.tenant_scope import TenantScope
    approved = load_result("control-approval")
    command = {**approved["controlIntent"], "approvalRef": approved["approvalRef"]}
    freeze_or_match(STATE / "event-enable-intent.json", command)
    scope = TenantScope(**SCOPE); principal = Principal(subject=ACTOR, org_id=scope.org_id, project_id=scope.project_id, roles=["admin"])
    router = EcommerceGrowthCanonicalRouter(build_scoped_ecommerce_growth_registry(principal, plane.pipeline_control_factory))
    with _scope_and_connection()[1] as conn: target = _runtime_target(preflight, conn)
    result = router.dispatch(scope=scope, operation_id="ecommerce_growth_event_control", command=command, expected_runtime=target)
    return {"outcome": "CURRENT_PRODUCT_EVENT_ENABLED", **result}


def observe_event(_preflight, _plane) -> dict[str, Any]:
    scope, connection = _scope_and_connection()
    with connection as conn:
        counts = {}
        for name, table in (("policies", "ecommerce_investigation_schedule_policy_head"),
                            ("bindings", "automation_schedule_binding"),
                            ("occurrences", "automation_occurrence"),
                            ("cases", "ecommerce_investigation_case_head"),
                            ("runs", "ecommerce_investigation_run_head"),
                            ("dataRequirements", "ecommerce_analysis_data_requirement_head")):
            counts[name] = conn.execute(f"SELECT count(*) AS n FROM {table} WHERE org_id=%s AND project_id=%s", scope.key).fetchone()["n"]
        canary = {}
        for name, table in (("policies", "ecommerce_investigation_schedule_policy_head"),
                            ("bindings", "automation_schedule_binding"), ("occurrences", "automation_occurrence"),
                            ("cases", "ecommerce_investigation_case_head"), ("runs", "ecommerce_investigation_run_head")):
            canary[name] = conn.execute(f"SELECT count(*) AS n FROM {table} WHERE org_id='dev-org' AND project_id='dev-project'").fetchone()["n"]
    return {"outcome": "CURRENT_PRODUCT_EVENT_CHAIN_OBSERVED", "observedAt": datetime.now(timezone.utc).isoformat(),
            "counts": counts, "canary": canary}


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
    parser.add_argument("action", choices=("prepare", "selection", "control", "binding", "execute", "observe",
        "reviewer", "action-types", "brief", "cutover-action-type", "registration-withdraw",
        "registration-register", "cutover-approval", "cutover-prepare", "cutover-pause",
        "cutover-commit", "cutover-validate", "cutover-resume", "cutover-observe", "case",
        "event-refresh", "schedule-approval", "policy", "control-approval", "event-enable",
        "event-observe"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("immutable output exists; inspect before retry")
    preflight, plane = setup()
    action = {"prepare": lambda: prepare(preflight), "selection": lambda: approve_selection(preflight,plane),
              "control": lambda: approve_control(preflight,plane), "binding": lambda: bind_schedule(preflight,plane),
              "execute": lambda: execute_once(preflight,plane), "observe": lambda: observe(preflight,plane),
              "reviewer": lambda: configure_reviewer(preflight,plane),
              "action-types": lambda: configure_action_types(preflight,plane),
              "brief": lambda: configure_brief(preflight,plane),
              "cutover-action-type": lambda: configure_cutover_action_type(preflight,plane),
              "registration-withdraw": lambda: withdraw_old_registration(preflight,plane),
              "registration-register": lambda: register_current_e(preflight,plane),
              "cutover-approval": lambda: approve_cutover(preflight,plane),
              "cutover-prepare": lambda: cutover_prepare(preflight,plane),
              "cutover-pause": lambda: cutover_pause(preflight,plane),
              "cutover-commit": lambda: cutover_commit(preflight,plane),
              "cutover-validate": lambda: cutover_validate(preflight,plane),
              "cutover-resume": lambda: cutover_resume(preflight,plane),
              "cutover-observe": lambda: observe_cutover(preflight,plane),
              "case": lambda: configure_case(preflight,plane),
              "event-refresh": lambda: refresh_event_authority(preflight,plane),
              "schedule-approval": lambda: approve_schedule(preflight,plane),
              "policy": lambda: put_policy(preflight,plane),
              "control-approval": lambda: approve_event_control(preflight,plane),
              "event-enable": lambda: enable_event(preflight,plane),
              "event-observe": lambda: observe_event(preflight,plane)}[args.action]
    result = action()
    freeze(args.output, result)
    canonical = STATE / f"{args.action}-result.json"
    if canonical != args.output:
        freeze(canonical, result)
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))


if __name__ == "__main__":
    os.environ.setdefault("AOS_DOTENV_DISABLED", "1")
    main()
