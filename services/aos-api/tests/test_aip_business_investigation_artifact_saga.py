"""BI-W6-04 receipt-before-Step acceptance tests."""

from __future__ import annotations

import pytest

from aos_api.aip_business_investigation_artifact_saga import (
    BusinessInvestigationArtifactAcceptanceBlocked,
    BusinessInvestigationArtifactPublicationSaga,
)
from aos_api.ecommerce_business_investigation_artifact_publication import (
    ArtifactPublicationWrite,
    BusinessInvestigationArtifactPublisher,
)
from aos_api.tenant_scope import TenantScope
from tests.test_ecommerce_business_investigation_artifact_publication import (
    NOW,
    artifact,
    binding,
    gate,
    stage_attempt,
)


SCOPE = TenantScope("org-org", "dev-project")


class Authority:
    def __init__(self, drift: str | None = None) -> None:
        self.drift = drift

    def publish(self, scope, **kwargs):
        receipt = kwargs["receipt"]
        if self.drift == "binding":
            receipt = receipt.model_copy(
                update={"binding_ref": receipt.binding_ref.model_copy(update={"resource_id": "other-binding"})}
            )
        return ArtifactPublicationWrite(authority=receipt, replayed=False)


class Completer:
    def __init__(self) -> None:
        self.calls = 0
        self.args = None

    def complete_step(self, scope, step_run_id, worker_id, fence, actor):
        self.calls += 1
        self.args = (scope, step_run_id, worker_id, fence, actor)
        return "checkpoint-after-publication"


class DriftPublisher:
    def __init__(self) -> None:
        self._delegate = BusinessInvestigationArtifactPublisher(Authority())

    def publish(self, scope, **kwargs):
        write = self._delegate.publish(scope, **kwargs)
        receipt = write.authority.model_copy(
            update={
                "binding_ref": write.authority.binding_ref.model_copy(
                    update={"resource_id": "other-binding"}
                )
            }
        )
        return ArtifactPublicationWrite(authority=receipt, replayed=False)


def _execute(authority: Authority, completer: Completer):
    item = artifact()
    return BusinessInvestigationArtifactPublicationSaga(
        BusinessInvestigationArtifactPublisher(authority), completer
    ).execute(
        SCOPE,
        actor="analyst",
        worker_id="worker-1",
        fence=7,
        expected_head_revision=0,
        artifact=item,
        binding=binding(item),
        quality_gate=gate(item),
        stage_attempt=stage_attempt(),
        published_at=NOW,
    )


def test_saga_completes_canonical_step_only_after_exact_publication_receipt() -> None:
    completer = Completer()
    result = _execute(Authority(), completer)
    assert result.publication_transition_count == 1
    assert result.step_transition_count == 1
    assert result.external_effect_authorized is False
    assert result.checkpoint_id == "checkpoint-after-publication"
    assert result.publication_receipt_ref.receipt_id == result.publication_receipt_ref.resource_id
    assert completer.args == (SCOPE, "step-run-1", "worker-1", 7, "analyst")


def test_saga_rejects_receipt_drift_without_completing_step() -> None:
    completer = Completer()
    item = artifact()
    with pytest.raises(BusinessInvestigationArtifactAcceptanceBlocked) as raised:
        BusinessInvestigationArtifactPublicationSaga(DriftPublisher(), completer).execute(
            SCOPE,
            actor="analyst",
            worker_id="worker-1",
            fence=7,
            expected_head_revision=0,
            artifact=item,
            binding=binding(item),
            quality_gate=gate(item),
            stage_attempt=stage_attempt(),
            published_at=NOW,
        )
    assert raised.value.code == "RECEIPT_BINDING_DRIFTED"
    assert completer.calls == 0


@pytest.mark.parametrize(("worker", "fence"), [("", 1), ("worker-1", 0)])
def test_saga_rejects_invalid_step_ownership_before_publication(worker: str, fence: int) -> None:
    item = artifact()
    completer = Completer()
    authority = Authority()
    with pytest.raises(BusinessInvestigationArtifactAcceptanceBlocked):
        BusinessInvestigationArtifactPublicationSaga(
            BusinessInvestigationArtifactPublisher(authority), completer
        ).execute(
            SCOPE,
            actor="analyst",
            worker_id=worker,
            fence=fence,
            expected_head_revision=0,
            artifact=item,
            binding=binding(item),
            quality_gate=gate(item),
            stage_attempt=stage_attempt(),
            published_at=NOW,
        )
    assert completer.calls == 0
