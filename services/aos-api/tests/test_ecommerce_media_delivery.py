from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from aos_api.auth import Principal, require_principal
from aos_api.ecommerce_media_delivery import (
    EcommerceMediaDelivery,
    MediaDeliveryConflict,
)
from aos_api.ecommerce_media_delivery_contracts import (
    MediaDeliveryExportRequest,
    MediaDeliveryPublishProposalRequest,
)
from aos_api.tenant_scope import TenantScope
from aos_api.errors import register_exception_handlers
from aos_api.routers import ecommerce_workshop


SCOPE = TenantScope("org-org", "dev-project")
OTHER = TenantScope("dev-org", "dev-project")
NOW = datetime(2026, 9, 5, 4, tzinfo=UTC)
HASH = "a" * 64
GATE_HASH = "b" * 64
PREVIEW_HASH = "c" * 64
BINDING_HASH = "d" * 64


def exact(resource_type: str, resource_id: str, revision: int, content_hash: str):
    return SimpleNamespace(
        resource_type=resource_type,
        resource_id=resource_id,
        revision=revision,
        content_hash=content_hash,
    )


class Briefs:
    def __init__(self) -> None:
        self.items = {
            1: SimpleNamespace(
                brief_id="brief-1",
                task_id="task-1",
                revision=1,
                version=1,
                content_hash=HASH,
                brief_type="media_internal_workflow",
                schema_ref=EcommerceMediaDelivery.media_schema_ref(),
                spec={
                    "mediaType": "planting_copy",
                    "title": "栖月汇种草任务",
                    "summary": "准备商品种草内容",
                    "details": {"mediaType": "planting_copy", "lastCommand": "create"},
                    "status": "draft",
                    "externalEffectsAllowed": False,
                },
            )
        }

    def get_brief(self, scope, brief_id, revision=None):
        if scope != SCOPE or brief_id != "brief-1":
            raise ValueError("not found")
        return self.items[revision or max(self.items)]


class Production:
    def __init__(self, *, issue_status="resolved") -> None:
        variant = exact("ArtifactRevision", "variant-1", 4, HASH)
        self.family = SimpleNamespace(
            family_id="family-1",
            version=3,
            current_revision=4,
            topology_status=SimpleNamespace(value="current"),
            members=[SimpleNamespace(artifact_ref=SimpleNamespace(artifact_id="variant-1", content_hash=HASH), family_revision=4)],
            candidate_groups=[SimpleNamespace(selected_ref=SimpleNamespace(artifact_id="variant-1", content_hash=HASH))],
        )
        self.gate = SimpleNamespace(
            gate_set_id="gate-1",
            content_hash=GATE_HASH,
            family_id="family-1",
            artifact_ref=SimpleNamespace(artifact_id="variant-1", content_hash=HASH),
            readiness=SimpleNamespace(value="ready"),
            eligible_for_approval=True,
        )
        self.issue = SimpleNamespace(
            issue_id="issue-1",
            version=2,
            status=SimpleNamespace(value=issue_status),
            severity=SimpleNamespace(value="warning"),
            artifact_ref=SimpleNamespace(artifact_id="variant-1", content_hash=HASH),
            return_stage="media.review",
        )
        self.decision = SimpleNamespace(decision_id="decision-1", issue_id="issue-1", issue_version=1)
        self.preview = SimpleNamespace(
            preview_id="preview-1",
            revision=2,
            content_hash=PREVIEW_HASH,
            task_id="task-1",
            brief_ref=exact("TaskBriefRevision", "brief-1", 1, HASH),
            lifecycle=SimpleNamespace(value="frozen"),
            readiness=SimpleNamespace(value="ready"),
            expires_at=NOW + timedelta(hours=2),
            action_binding_hash=BINDING_HASH,
        )
        self.variant = variant

    @staticmethod
    def _result(items):
        return SimpleNamespace(items=items)

    def list_artifact_families(self, scope): return self._result([self.family] if scope == SCOPE else [])
    def list_media_gate_sets(self, scope): return self._result([self.gate] if scope == SCOPE else [])
    def list_review_issues(self, scope): return self._result([self.issue] if scope == SCOPE else [])
    def list_return_decisions(self, scope): return self._result([self.decision] if scope == SCOPE else [])
    def list_impact_previews(self, scope): return self._result([self.preview] if scope == SCOPE else [])


class Actions:
    def __init__(self) -> None:
        self.calls = []
        self.bundle = None

    def create_proposal(self, principal, key, body):
        self.calls.append((principal, key, body))
        proposal = SimpleNamespace(
            id="proposal-1", version=1, proposal_hash="e" * 64,
            status=SimpleNamespace(value="pending"), payload=body.payload,
            impact_preview_ref=body.impact_preview_ref,
        )
        self.bundle = SimpleNamespace(proposal=proposal, approvals=[])
        return self.bundle

    def get_proposal(self, scope, proposal_id):
        assert scope == SCOPE and proposal_id == "proposal-1"
        return self.bundle


def service(*, issue_status="resolved"):
    actions = Actions()
    return EcommerceMediaDelivery(
        brief_store=Briefs(), production_store=Production(issue_status=issue_status),
        action_service=actions, action_store=actions, clock=lambda: NOW,
    ), actions


def draft_ref():
    return {"resourceType": "TaskBriefRevision", "resourceId": "brief-1", "revision": 1, "contentHash": HASH}


def selection():
    return {
        "familyId": "family-1", "familyVersion": 3,
        "variantRef": {"resourceType": "ArtifactRevision", "resourceId": "variant-1", "revision": 4, "contentHash": HASH},
        "gateSetRef": {"resourceType": "MediaGateSetDecision", "resourceId": "gate-1", "revision": 1, "contentHash": GATE_HASH},
        "impactPreviewRef": {"resourceType": "ImpactPreviewRevision", "resourceId": "preview-1", "revision": 2, "contentHash": PREVIEW_HASH},
    }


def test_workspace_composes_existing_versions_review_and_publish_authority() -> None:
    delivery, _ = service()
    result = delivery.workspace(SCOPE, "brief-1")

    assert result.current_draft.resource_id == "brief-1"
    assert result.history_count == 1
    assert result.candidates[0].family_id == "family-1"
    assert result.candidates[0].review_issues[0].status == "resolved"
    assert result.candidates[0].return_decision_count == 1
    assert result.candidates[0].publish_ready is True
    assert result.external_effects_allowed is False


def test_export_is_deterministic_and_does_not_create_an_artifact_or_side_effect() -> None:
    delivery, actions = service()
    body = MediaDeliveryExportRequest(draftRef=draft_ref(), expectedVersion=1, selection=selection())

    first = delivery.export(SCOPE, body)
    second = delivery.export(SCOPE, body)

    assert first.content == second.content
    assert first.content_hash == second.content_hash
    assert first.file_name == "media-brief-1-r1.json"
    assert first.side_effects.model_dump() == {
        "provider_invocation_count": 0, "external_generation_count": 0,
        "fee_charge_count": 0, "publication_count": 0, "business_mutation_count": 0,
    }
    assert actions.calls == []


def test_publish_proposal_uses_exact_existing_authorities_and_reads_back_same_proposal() -> None:
    delivery, actions = service()
    principal = Principal(subject="operator", org_id="org-org", project_id="dev-project", roles=("admin",))
    body = MediaDeliveryPublishProposalRequest(
        draftRef=draft_ref(), expectedVersion=1, selection=selection(),
        purpose="栖月汇种草内容发布审批",
    )

    result = delivery.create_publish_proposal(principal, "publish-1", body)

    assert result.proposal.proposal_id == "proposal-1"
    assert result.proposal.status == "pending"
    assert actions.calls[0][2].action_type_id == "content.publish"
    assert actions.calls[0][2].payload == {"publishCandidate": {
        "familyId": "family-1", "familyVersion": 3,
        "selectedVariantRef": {"artifactId": "variant-1", "contentHash": HASH},
        "gateSetRef": {"gateSetId": "gate-1", "contentHash": GATE_HASH},
    }}
    assert result.side_effects.publication_count == 0


def test_stale_exact_ref_open_issue_and_cross_tenant_fail_closed() -> None:
    delivery, _ = service(issue_status="open")
    stale = selection()
    stale["familyVersion"] = 2
    body = MediaDeliveryPublishProposalRequest(
        draftRef=draft_ref(), expectedVersion=1, selection=stale,
        purpose="栖月汇种草内容发布审批",
    )
    principal = Principal(subject="operator", org_id="org-org", project_id="dev-project", roles=("admin",))

    with pytest.raises(MediaDeliveryConflict):
        delivery.create_publish_proposal(principal, "publish-stale", body)
    with pytest.raises(MediaDeliveryConflict):
        delivery.workspace(OTHER, "brief-1")


def test_http_routes_take_tenant_from_principal_and_reject_query_or_path_injection() -> None:
    delivery, _ = service()
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(ecommerce_workshop.router)
    app.dependency_overrides[require_principal] = lambda: Principal(
        subject="operator", org_id="org-org", project_id="dev-project",
        roles=["admin"], markings=["public"],
    )
    app.dependency_overrides[ecommerce_workshop.get_ecommerce_workshop_catalog] = lambda: type(
        "InstalledMediaCatalog", (), {"get_readiness": lambda self, **kwargs: object()}
    )()
    app.dependency_overrides[ecommerce_workshop.get_ecommerce_media_delivery] = lambda: delivery
    export_body = MediaDeliveryExportRequest(
        draftRef=draft_ref(), expectedVersion=1, selection=selection()
    ).model_dump(mode="json", by_alias=True)
    with TestClient(app, raise_server_exceptions=False) as client:
        workspace = client.get("/v1/ecommerce-workshop/views/media-studio/workflow/drafts/brief-1/delivery")
        injected = client.get("/v1/ecommerce-workshop/views/media-studio/workflow/drafts/brief-1/delivery?orgId=dev-org")
        exported = client.post("/v1/ecommerce-workshop/views/media-studio/workflow/drafts/brief-1/exports", json=export_body)
        mismatched = client.post("/v1/ecommerce-workshop/views/media-studio/workflow/drafts/brief-other/exports", json=export_body)

    assert workspace.status_code == 200
    assert workspace.json()["tenant"] == {"orgId": "org-org", "projectId": "dev-project"}
    assert injected.status_code == 400
    assert exported.status_code == 200 and exported.json()["sideEffects"]["publicationCount"] == 0
    assert mismatched.status_code == 409
