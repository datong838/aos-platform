"""Task Cockpit feedback is scoped, read-only, and never equates pending with Wiki."""

from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from aos_api.auth import Principal, require_principal
from aos_api.asset_registry.errors import AssetNotFoundError
from aos_api.ecommerce_workshop_feedback_read_contracts import (
    FeedbackBusinessItem, FeedbackReadEnvelope, FeedbackSegmentView,
)
from aos_api.ecommerce_workshop_feedback_read_model import FeedbackReadUnavailable
from aos_api.errors import register_exception_handlers
from aos_api.routers import ecommerce_workshop
from aos_api.tenant_scope import TenantScope


NOW = datetime(2026, 9, 27, 12, tzinfo=UTC)


def test_contract_rejects_candidate_status_without_third_receipt():
    segments = [
        FeedbackSegmentView(sequence=index, kind=kind, title="内容复盘", summary="待核对",
            state="pending", status_label="等待接收")
        for index, kind in enumerate((
            "daily_review", "improvement_observation", "memory_candidate"), start=1)
    ]
    with pytest.raises(ValidationError, match="third Receipt"):
        valid_ref = {"resourceType": "SourceRevision", "resourceId": "source-1",
            "revision": 1, "contentHash": "sha256:" + "a" * 64}
        FeedbackBusinessItem(title="内容复盘", created_at=NOW, segments=segments,
            effect_status="待观察", candidate_status="待治理",
            audit_details={"commandId": "x", "reviewReceiptRef": valid_ref,
                "artifactRef": valid_ref, "taskRef": valid_ref,
                "targetReceiptRefs": [None, None, None]})


class FakeFeedback:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.calls = []

    def read(self, scope, *, limit):
        self.calls.append((scope, limit))
        if self.fail:
            raise FeedbackReadUnavailable("private database detail")
        return FeedbackReadEnvelope(
            tenant={"orgId": scope.org_id, "projectId": scope.project_id},
            evaluated_at=NOW, data_cutoff=NOW, items=[], has_more=False,
        )


class FakeCatalog:
    def __init__(self, *, installed=True):
        self.installed = installed

    def get_readiness(self, **_kwargs):
        if not self.installed:
            raise AssetNotFoundError("not installed")
        return object()


def client(feedback, catalog=None):
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(ecommerce_workshop.router)
    app.dependency_overrides[require_principal] = lambda: Principal(
        subject="user:test", org_id="org-org", project_id="dev-project",
        roles=["operator"], markings=["public"],
    )
    app.dependency_overrides[ecommerce_workshop.get_ecommerce_workshop_feedback_read_model] = lambda: feedback
    app.dependency_overrides[ecommerce_workshop.get_ecommerce_workshop_catalog] = (
        lambda: catalog or FakeCatalog())
    return TestClient(app, raise_server_exceptions=False)


def test_get_requires_installed_cockpit_and_principal_scope():
    feedback = FakeFeedback()
    with client(feedback) as web:
        response = web.get("/v1/ecommerce-workshop/views/task-cockpit/feedback?limit=7")
        assert response.status_code == 200
        assert response.json()["items"] == []
        assert response.json()["tenant"] == {"orgId": "org-org", "projectId": "dev-project"}
        assert web.get("/v1/ecommerce-workshop/views/task-cockpit/feedback?orgId=dev-org").status_code == 400
        assert web.get("/v1/ecommerce-workshop/views/task-cockpit/feedback?limit=21").status_code == 400
    assert feedback.calls == [(TenantScope("org-org", "dev-project"), 7)]
    with client(FakeFeedback(), FakeCatalog(installed=False)) as web:
        assert web.get("/v1/ecommerce-workshop/views/task-cockpit/feedback").status_code == 404


def test_get_maps_authority_failure_without_leaking_details():
    with client(FakeFeedback(fail=True)) as web:
        response = web.get("/v1/ecommerce-workshop/views/task-cockpit/feedback")
    assert response.status_code == 503
    assert response.json()["code"] == "TASK_COCKPIT_FEEDBACK_UNAVAILABLE"
    assert "private database detail" not in response.text
