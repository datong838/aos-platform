import importlib
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError

import pytest


@pytest.fixture
def control(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[4] / "scripts"))
    return importlib.import_module("a0v_qyh_current_product_event_first_chain")


def test_scope_and_business_route_are_fixed(control):
    assert control.SCOPE == {"org_id": "org-org", "project_id": "dev-project"}
    assert control.PIPELINE == "P02-product-qyh"
    assert control.SCHEDULE == "sch-p02-qyh-controlled-20260913-v1"
    assert control.ACTOR == "a0v-ecommerce-growth-1.4-runtime-owner"
    assert str(control.STATE).endswith("p02-e-first-chain-r2")
    assert str(control.PREVIOUS_STATE).endswith("p02-e-first-chain")
    assert control.OLD_REGISTRATION_INSTALLATION == "97aeb2e7-59ba-40f6-89a3-fb0293bc0497"
    assert control.REGISTRATION_GROUP_ID == "6a402d31-83ad-546c-807f-508c87498ce1"
    assert control.CUTOVER_OPERATION_ID == "b5555da7-6d0e-52f8-a443-d39b8264f40c"
    assert control.MAKER != control.CHECKER != control.ACTOR
    assert len({control.ACTOR, control.CHECKER, control.CUTOVER_CHECKER}) == 3


def test_cutover_control_action_is_installation_scoped(control):
    assert control.CUTOVER_ACTION_TYPE == {
        "id": "ecommerce_growth_cutover", "name": "切换电商经营九项宿主入口",
        "objectType": "BundleInstallation", "parameters": [], "requiredMarkings": [],
        "submissionCriteria": [],
    }


def test_cutover_target_binds_registration_policy_and_exact_operations(control, monkeypatch):
    registration = {
        "outcome": "CURRENT_E_FIRST_DISPATCH_REGISTERED",
        "request": {
            "installationRef": {"installationId": "11111111-1111-4111-8111-111111111111"},
            "groupId": control.REGISTRATION_GROUP_ID,
            "generation": "22222222-2222-4222-8222-222222222222",
            "executionEpoch": 3, "bindingRevision": 4,
        },
        "receipt": {"receiptId": "33333333-3333-4333-8333-333333333333",
                    "contentHash": "sha256:" + "a" * 64},
    }
    monkeypatch.setattr(control, "_current_registration_result", lambda: registration)
    monkeypatch.setattr(control, "_cutover_policy_ref", lambda: {
        "resourceType": "RuntimeCutoverPolicyRevision", "resourceId": "policy", "revision": 1,
        "contentHash": "sha256:" + "b" * 64})
    monkeypatch.setattr(control, "_growth_operations", lambda: [f"operation-{n}" for n in range(9)])
    target = control._cutover_target()
    assert target["expectedGroupRevision"] == 1
    assert target["targetInstallationId"] == registration["request"]["installationRef"]["installationId"]
    assert target["targetRuntimeRevision"] == 4
    assert target["operationIds"] == [f"operation-{n}" for n in range(9)]
    assert target["registrationReceiptRef"]["resourceId"] == registration["receipt"]["receiptId"]
    assert target["policyRef"]["resourceId"] == "policy"


def test_private_freeze_is_exclusive(control, tmp_path):
    target = tmp_path / "result.json"
    control.freeze(target, {"outcome": "once"})
    assert target.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        control.freeze(target, {"outcome": "twice"})
    control.freeze_or_match(target, {"outcome": "once"})
    with pytest.raises(ValueError, match="intent differs"):
        control.freeze_or_match(target, {"outcome": "changed"})


def test_cutover_prepare_prefers_immutable_refresh_approval(control, monkeypatch, tmp_path):
    monkeypatch.setattr(control, "STATE", tmp_path)
    control.freeze(tmp_path / "cutover-approval-result.json", {"approvalRef": {"resourceId": "expired"}})
    assert control.current_cutover_approval_result()["approvalRef"]["resourceId"] == "expired"
    control.freeze(tmp_path / "cutover-approval-refresh-result.json", {"approvalRef": {"resourceId": "current"}})
    assert control.current_cutover_approval_result()["approvalRef"]["resourceId"] == "current"
    control.freeze(tmp_path / "cutover-prepare-result.json", {"receipt": {"receiptId": "failed"}})
    assert control.current_cutover_prepare_result()["receipt"]["receiptId"] == "failed"
    control.freeze(tmp_path / "cutover-prepare-refresh-result.json", {"receipt": {"receiptId": "current"}})
    assert control.current_cutover_prepare_result()["receipt"]["receiptId"] == "current"


def test_canonical_and_relative_output_resolve_to_one_file(control, tmp_path):
    canonical = tmp_path / "state" / "result.json"
    relative = tmp_path / "state" / ".." / "state" / "result.json"
    assert canonical.resolve() == relative.resolve()


def test_previous_result_must_be_private(control, monkeypatch, tmp_path):
    monkeypatch.setattr(control, "PREVIOUS_STATE", tmp_path)
    target = tmp_path / "selection-result.json"
    target.write_text('{"ref":{"revision":1}}', encoding="utf-8")
    target.chmod(0o644)
    with pytest.raises(ValueError, match="private previous selection"):
        control.load_previous_result("selection")
    target.chmod(0o600)
    assert control.load_previous_result("selection")["ref"]["revision"] == 1


def test_api_error_keeps_only_safe_code(control, monkeypatch):
    error = HTTPError("http://local", 403, "forbidden", {}, BytesIO(
        b'{"detail":{"code":"SCHEDULE_CONTROL_FORBIDDEN","message":"hidden"}}'
    ))
    monkeypatch.setattr(control, "urlopen", lambda *_a, **_k: (_ for _ in ()).throw(error))
    with pytest.raises(RuntimeError, match="403:SCHEDULE_CONTROL_FORBIDDEN") as caught:
        control.api("POST", "/v1/schedules/s/run", {})
    assert "hidden" not in str(caught.value)


def test_execute_refuses_historical_or_enabled_schedule(control, monkeypatch, tmp_path):
    monkeypatch.setattr(control, "STATE", tmp_path)
    for name, value in (("control", {"ref": {"resourceType": "PipelineRuntimeControlRevision", "resourceId": "pipeline-control-current", "revision": 1, "contentHash": "sha256:current"}}),
                        ("binding", {"ref": {"resourceType": "PipelineScheduleControlBinding", "resourceId": "schedule-control-current", "revision": 2, "contentHash": "sha256:binding"}})):
        control.freeze(tmp_path / f"{name}-result.json", value)
    monkeypatch.setattr(control, "observe", lambda *_: {"current": {"schedule": {"enabled": True},
        "binding": {"ref": {"resourceType": "PipelineScheduleControlBinding", "resourceId": "schedule-control-old", "revision": 1, "contentHash": "sha256:old"},
                    "controlRef": {"resourceType": "PipelineRuntimeControlRevision", "resourceId": "pipeline-control-old", "revision": 1, "contentHash": "sha256:old"}}}})
    monkeypatch.setattr(control, "api", lambda *_a, **_k: pytest.fail("no API call allowed"))
    with pytest.raises(ValueError, match="binding differs"):
        control.execute_once(object(), object())


def test_execute_enables_runs_once_and_disables(control, monkeypatch, tmp_path):
    monkeypatch.setattr(control, "STATE", tmp_path)
    current_control = {"resourceType": "PipelineRuntimeControlRevision", "resourceId": "pipeline-control-current", "revision": 1, "contentHash": "sha256:current"}
    current_binding = {"resourceType": "PipelineScheduleControlBinding", "resourceId": "schedule-control-current", "revision": 2, "contentHash": "sha256:binding"}
    control.freeze(tmp_path / "control-result.json", {"ref": current_control})
    control.freeze(tmp_path / "binding-result.json", {"ref": current_binding})
    monkeypatch.setattr(control, "observe", lambda *_: {"current": {"schedule": {"enabled": False},
        "binding": {"ref": current_binding, "controlRef": current_control}}})
    calls=[]
    def api(method,path,body=None):
        calls.append((method,path,body)); return 200,{"status":"succeeded"}
    monkeypatch.setattr(control,"api",api)
    result=control.execute_once(object(),object())
    assert result["outcome"]=="CURRENT_PRODUCT_SNAPSHOT_SUCCEEDED"
    assert calls==[("PATCH",f"/v1/schedules/{control.SCHEDULE}",{"enabled":True}),
                   ("POST",f"/v1/schedules/{control.SCHEDULE}/run",{}),
                   ("PATCH",f"/v1/schedules/{control.SCHEDULE}",{"enabled":False})]


def test_execute_reports_known_failed_run_without_claiming_success(control, monkeypatch, tmp_path):
    monkeypatch.setattr(control, "STATE", tmp_path)
    current_control = {"resourceType": "PipelineRuntimeControlRevision", "resourceId": "pipeline-control-current", "revision": 1, "contentHash": "sha256:current"}
    current_binding = {"resourceType": "PipelineScheduleControlBinding", "resourceId": "schedule-control-current", "revision": 2, "contentHash": "sha256:binding"}
    control.freeze(tmp_path / "control-result.json", {"ref": current_control})
    control.freeze(tmp_path / "binding-result.json", {"ref": current_binding})
    monkeypatch.setattr(control, "observe", lambda *_: {"current": {"schedule": {"enabled": False},
        "binding": {"ref": current_binding, "controlRef": current_control}}})
    replies = iter(((200, {"enabled": True}),
                    (200, {"status": "failed", "result": {"error_code": "PIPELINE_EXECUTOR_FAILED"}}),
                    (200, {"enabled": False})))
    monkeypatch.setattr(control, "api", lambda *_a, **_k: next(replies))
    result = control.execute_once(object(), object())
    assert result["outcome"] == "CURRENT_PRODUCT_SNAPSHOT_FAILED"
    assert result["run"]["body"]["result"]["error_code"] == "PIPELINE_EXECUTOR_FAILED"
