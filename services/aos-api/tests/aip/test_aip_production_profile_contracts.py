"""Contract tests for W3-02 typed production profiles."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from aos_api.aip_production_profile_contracts import ProductionProfile


def _profile(module_id: str = "ecommerce.content-campaign") -> dict[str, object]:
    return {
        "schema": "aos.ecommerce-production-profile/v1",
        "moduleId": module_id,
        "profileRevision": 1,
        "brief": {
            "mode": "reference_only" if module_id == "ecommerce.task-cockpit" else "owned",
            "briefType": "campaign-content",
            "requiredFields": ["objective", "constraints"],
            "sourceResponsibilityPreserved": True,
        },
        "evidenceSelection": {
            "requiredFacts": ["product", "audience", "policy"],
            "requireProvenance": True,
            "requireFreshness": True,
            "requireNegativeEvidence": True,
        },
        "eval": {
            "gates": ["fact", "policy", "brand"],
            "failClosed": True,
            "sameRevisionRequired": True,
        },
        "responsibility": {
            "slots": [
                {
                    "slotId": "content.owner",
                    "responsibilityType": "maker",
                    "atomicSkillIds": ["copy.generate"],
                    "protected": False,
                    "mergeAllowed": True,
                    "returnStage": "prepare",
                },
                {
                    "slotId": "content.review",
                    "responsibilityType": "independent_review",
                    "atomicSkillIds": ["content.review"],
                    "protected": True,
                    "mergeAllowed": False,
                    "returnStage": "prepare",
                },
            ],
            "handoffRequired": True,
            "reassignmentRequiresCanonicalDecision": True,
        },
        "contributionProjection": {
            "showAtomicSkillAttribution": True,
            "showLogicRevision": True,
            "showCoworkerBinding": True,
            "showBlockers": True,
        },
    }


def test_profile_preserves_skill_logic_coworker_contribution_chain() -> None:
    profile = ProductionProfile.model_validate(_profile())

    assert profile.responsibility.slots[0].atomic_skill_ids == ["copy.generate"]
    assert profile.contribution_projection.show_logic_revision is True
    assert profile.contribution_projection.show_coworker_binding is True


def test_task_cockpit_is_reference_only_and_preserves_source_responsibility() -> None:
    profile = ProductionProfile.model_validate(_profile("ecommerce.task-cockpit"))
    assert profile.brief.mode.value == "reference_only"

    invalid = _profile("ecommerce.task-cockpit")
    invalid["brief"]["mode"] = "owned"  # type: ignore[index]
    with pytest.raises(ValidationError):
        ProductionProfile.model_validate(invalid)


def test_protected_review_cannot_merge_and_unknown_fields_fail_closed() -> None:
    invalid = _profile()
    invalid["responsibility"]["slots"][1]["mergeAllowed"] = True  # type: ignore[index]
    with pytest.raises(ValidationError):
        ProductionProfile.model_validate(invalid)

    unknown = _profile()
    unknown["runtimeAction"] = "start"
    with pytest.raises(ValidationError):
        ProductionProfile.model_validate(unknown)
