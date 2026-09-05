from dataclasses import dataclass
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from aos_api.auth import Principal, require_principal
from aos_api.errors import register_exception_handlers
from aos_api.ecommerce_media_internal_workflow import (
    EcommerceMediaInternalWorkflow,
    MediaInternalWorkflowConflict,
)
from aos_api.ecommerce_media_internal_workflow_contracts import (
    MediaInternalWorkflowCommandRequest,
)
from aos_api.tenant_scope import TenantScope
from aos_api.routers import ecommerce_workshop

SCOPE = TenantScope("org-org", "dev-project")
OTHER = TenantScope("dev-org", "dev-project")


@dataclass
class Task:
    id: str


@dataclass
class Brief:
    brief_id: str
    task_id: str
    revision: int
    version: int
    content_hash: str
    spec: dict
    brief_type: str
    schema_ref: object


class Tasks:
    def __init__(self) -> None:
        self.created = 0

    def create_task(self, scope, actor, key, body):
        assert scope == SCOPE and actor == "operator"
        assert body.type == "ecommerce.workshop.media_internal_task"
        assert body.goal["externalEffectsAllowed"] is False
        self.created += 1
        return Task(f"media-task-{self.created}")


class Briefs:
    def __init__(self) -> None:
        self.items: dict[str, dict[int, Brief]] = {}
        self.receipts: dict[tuple[str, str], Brief] = {}

    def create_brief(self, scope, actor, key, body):
        replay = self.receipts.get(("create", key))
        if replay is not None:
            return replay
        brief_id = f"media-brief-{len(self.items) + 1}"
        value = Brief(brief_id, body.task_id, 1, 1, "a" * 64, body.spec, body.brief_type, body.schema_ref)
        self.items[brief_id] = {1: value}
        self.receipts[("create", key)] = value
        return value

    def revise_brief(self, scope, actor, brief_id, key, body):
        replay = self.receipts.get(("revise", key))
        if replay is not None:
            return replay
        history = self.items[brief_id]
        current = history[max(history)]
        if body.expected_version != current.version:
            raise ValueError("stale")
        revision = current.revision + 1
        value = Brief(brief_id, current.task_id, revision, current.version + 1, format(revision % 16, "x") * 64, body.spec, body.brief_type, body.schema_ref)
        history[revision] = value
        self.receipts[("revise", key)] = value
        return value

    def get_brief(self, scope, brief_id, revision=None):
        if scope != SCOPE or brief_id not in self.items:
            raise ValueError("not found")
        history = self.items[brief_id]
        return history[revision or max(history)]

    def list_briefs(self, scope):
        if scope != SCOPE:
            return type("BriefList", (), {"items": []})()
        return type("BriefList", (), {"items": [history[max(history)] for history in self.items.values()]})()


def request(command="create", **changes):
    payload = {
        "command": command,
        "mediaType": "short_video",
        "title": "栖月汇商品讲解短视频",
        "summary": "围绕正式商品资料准备一条商品讲解短视频",
        "details": {"businessObject": "栖月汇微商城商品", "objective": "讲清商品卖点"},
    }
    payload.update(changes)
    return MediaInternalWorkflowCommandRequest.model_validate(payload)


def revise(command, draft, **changes):
    return request(command, draftRef=draft, expectedVersion=draft.version, **changes)


def workflow():
    briefs = Briefs()
    service = EcommerceMediaInternalWorkflow(
        task_store=Tasks(), brief_store=briefs, receipt_reader=lambda *_: "receipt-media-1"
    )
    return service, briefs


def test_create_and_all_internal_preparation_commands_are_versioned_and_zero_effect():
    service, _ = workflow()
    current = service.execute(SCOPE, "operator", "media-create", request()).draft
    assert current.status == "draft"
    commands = [
        ("save_input", {"details": {"objective": "突出使用场景"}}, "draft"),
        ("attach_evidence", {"details": {"evidence": ["商品中心正式资料"]}}, "draft"),
        ("reassign", {"details": {"assignee": "内容官"}}, "draft"),
        ("prepare_batch", {"details": {"batch": {"quantity": 3}}}, "prepared"),
        ("prepare_sample", {"details": {"sample": {"durationSeconds": 15}}}, "prepared"),
        ("select_template", {"details": {"template": {"name": "商品讲解模板"}}}, "prepared"),
        ("prepare_live", {"details": {"liveControl": {"scene": "商品讲解"}}}, "prepared"),
        ("schedule", {"details": {"schedule": {"plannedAt": "2026-09-06T10:00:00+08:00"}}}, "scheduled"),
    ]
    for index, (command, changes, status) in enumerate(commands, start=1):
        current = service.execute(SCOPE, "operator", f"media-{index}", revise(command, current, **changes)).draft
        assert current.status == status
        assert current.details["lastCommand"] == command
    assert current.version == 9
    assert service.history(SCOPE, current.resource_id).count == 9
    result = service.list(SCOPE)
    assert result.count == 1 and result.items[0].resource_id == current.resource_id
    effects = service.execute(SCOPE, "operator", "media-pause", revise("pause", current)).side_effects
    assert effects.model_dump() == {
        "provider_invocation_count": 0,
        "external_generation_count": 0,
        "fee_charge_count": 0,
        "publication_count": 0,
        "business_mutation_count": 0,
    }


def test_pause_resume_and_return_rework_preserve_exact_state():
    service, _ = workflow()
    draft = service.execute(SCOPE, "operator", "create", request()).draft
    prepared = service.execute(SCOPE, "operator", "batch", revise("prepare_batch", draft, details={"batch": {"quantity": 2}})).draft
    paused = service.execute(SCOPE, "operator", "pause", revise("pause", prepared)).draft
    assert paused.status == "paused" and paused.details["pausedFromStatus"] == "prepared"
    resumed = service.execute(SCOPE, "operator", "resume", revise("resume", paused)).draft
    assert resumed.status == "prepared" and "pausedFromStatus" not in resumed.details
    returned = service.execute(SCOPE, "operator", "return", revise("return", resumed, details={"returnReason": "卖点证据需补充"})).draft
    assert returned.status == "returned"
    reworked = service.execute(SCOPE, "operator", "rework", revise("attach_evidence", returned, details={"evidence": ["补充质检报告"]})).draft
    assert reworked.status == "draft"


def test_stale_exact_ref_invalid_transition_and_missing_command_payload_fail_closed():
    service, briefs = workflow()
    created = service.execute(SCOPE, "operator", "create", request()).draft
    with pytest.raises(MediaInternalWorkflowConflict, match="stale"):
        service.execute(SCOPE, "operator", "stale", revise("save_input", created.model_copy(update={"content_hash": "f" * 64})))
    with pytest.raises(MediaInternalWorkflowConflict, match="not allowed"):
        service.execute(SCOPE, "operator", "resume", revise("resume", created))
    with pytest.raises(MediaInternalWorkflowConflict, match="evidence"):
        service.execute(SCOPE, "operator", "evidence", revise("attach_evidence", created, details={}))
    assert len(briefs.items[created.resource_id]) == 1


def test_idempotency_replay_and_tenant_isolation_are_explicit():
    service, _ = workflow()
    calls = iter([None, "receipt-media-1"])
    service._receipt_reader = lambda *_: next(calls)
    created = service.execute(SCOPE, "operator", "create", request())
    assert created.receipt.replay is False
    assert service.list(OTHER).count == 0
    with pytest.raises(MediaInternalWorkflowConflict):
        service.history(OTHER, created.draft.resource_id)


def test_revision_command_replay_returns_the_original_revision_without_creating_another_one():
    service, briefs = workflow()
    created = service.execute(SCOPE, "operator", "create-replay", request()).draft
    command = revise("prepare_sample", created, details={"sample": {"durationSeconds": 15}})
    first = service.execute(SCOPE, "operator", "sample-replay", command)
    replay = service.execute(SCOPE, "operator", "sample-replay", command)

    assert replay.receipt.replay is True
    assert replay.draft == first.draft
    assert service.history(SCOPE, created.resource_id).count == 2
    assert len(briefs.items[created.resource_id]) == 2


def test_real_postgres_stores_preserve_replay_history_and_tenant_isolation():
    service = EcommerceMediaInternalWorkflow()
    key = f"media-pg-{uuid.uuid4().hex}"
    created = service.execute(SCOPE, "test:r5-m03", key, request())
    assert service.execute(SCOPE, "test:r5-m03", key, request()).draft == created.draft

    command = revise(
        "prepare_batch",
        created.draft,
        details={"batch": {"quantity": 2}},
    )
    prepared = service.execute(SCOPE, "test:r5-m03", f"{key}-batch", command)
    replay = service.execute(SCOPE, "test:r5-m03", f"{key}-batch", command)

    assert replay.receipt.replay is True
    assert replay.draft == prepared.draft
    assert service.history(SCOPE, created.draft.resource_id).count == 2
    assert any(item.resource_id == created.draft.resource_id for item in service.list(SCOPE).items)
    assert all(item.resource_id != created.draft.resource_id for item in service.list(OTHER).items)
    with pytest.raises(MediaInternalWorkflowConflict):
        service.history(OTHER, created.draft.resource_id)


def test_real_http_routes_are_principal_scoped_receipted_and_query_closed():
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(ecommerce_workshop.router)
    app.dependency_overrides[require_principal] = lambda: Principal(
        subject="test:r5-m03-http",
        org_id=SCOPE.org_id,
        project_id=SCOPE.project_id,
        roles=["operator"],
        markings=["public"],
    )
    app.dependency_overrides[
        ecommerce_workshop.get_ecommerce_workshop_catalog
    ] = lambda: type(
        "InstalledMediaCatalog",
        (),
        {"get_readiness": lambda self, **kwargs: object()},
    )()
    app.dependency_overrides[
        ecommerce_workshop.get_ecommerce_media_internal_workflow
    ] = lambda: EcommerceMediaInternalWorkflow()

    key = f"media-http-{uuid.uuid4().hex}"
    with TestClient(app, raise_server_exceptions=False) as client:
        created = client.post(
            "/v1/ecommerce-workshop/views/media-studio/workflow/commands",
            headers={"Idempotency-Key": key},
            json=request().model_dump(mode="json", by_alias=True),
        )
        assert created.status_code == 200
        payload = created.json()
        assert payload["tenant"] == {"orgId": "org-org", "projectId": "dev-project"}
        assert payload["receipt"]["operation"] == "task_brief.create"
        assert payload["sideEffects"] == {
            "providerInvocationCount": 0,
            "externalGenerationCount": 0,
            "feeChargeCount": 0,
            "publicationCount": 0,
            "businessMutationCount": 0,
        }

        exact_draft_ref = {
            key: payload["draft"][key]
            for key in ("resourceType", "resourceId", "revision", "contentHash")
        }
        prepared_request = request(
            "prepare_sample",
            draftRef=exact_draft_ref,
            expectedVersion=payload["draft"]["version"],
            details={"sample": {"durationSeconds": 15}},
        )
        prepared = client.post(
            "/v1/ecommerce-workshop/views/media-studio/workflow/commands",
            headers={"Idempotency-Key": f"{key}-sample"},
            json=prepared_request.model_dump(mode="json", by_alias=True),
        )
        assert prepared.status_code == 200
        assert prepared.json()["draft"]["status"] == "prepared"

        brief_id = payload["draft"]["resourceId"]
        history = client.get(
            f"/v1/ecommerce-workshop/views/media-studio/workflow/drafts/{brief_id}/history"
        )
        listed = client.get(
            "/v1/ecommerce-workshop/views/media-studio/workflow/drafts"
        )
        injected = client.get(
            "/v1/ecommerce-workshop/views/media-studio/workflow/drafts?orgId=dev-org"
        )
        missing_key = client.post(
            "/v1/ecommerce-workshop/views/media-studio/workflow/commands",
            json=request().model_dump(mode="json", by_alias=True),
        )

    assert history.status_code == 200 and history.json()["count"] == 2
    assert listed.status_code == 200
    assert any(item["resourceId"] == brief_id for item in listed.json()["items"])
    assert injected.status_code == 400
    assert missing_key.status_code == 400


def test_request_requires_complete_revision_contract_and_rejects_unknown_details():
    with pytest.raises(ValueError):
        request("pause")
    with pytest.raises(ValueError, match="unsupported"):
        request(details={"providerToken": "forbidden"})
    with pytest.raises(ValueError, match="evidence"):
        request(details={"evidence": [{"source": "商品中心", "sql": "select * from products"}]})
    with pytest.raises(ValueError, match="sensitive"):
        request(details={"template": {"providerParams": {"apiKey": "secret"}}})
