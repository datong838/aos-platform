import importlib
from pathlib import Path

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


def test_private_freeze_is_exclusive(control, tmp_path):
    target = tmp_path / "result.json"
    control.freeze(target, {"outcome": "once"})
    assert target.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        control.freeze(target, {"outcome": "twice"})
    control.freeze_or_match(target, {"outcome": "once"})
    with pytest.raises(ValueError, match="intent differs"):
        control.freeze_or_match(target, {"outcome": "changed"})


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
