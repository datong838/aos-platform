"""W7-01 signed-installable media template contract tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from aos_api.aip_media_production_templates import (
    MediaResponsibilityTemplate,
    MediaStageTemplate,
    MediaTemplateProfile,
)


REPO_ROOT = Path(__file__).resolve().parents[4]
TEMPLATE_ROOT = (
    REPO_ROOT
    / "bundles/candidates/ecommerce/solution.ecommerce.growth/1.4.0/content"
    / "media-production-templates"
)


def _payload(name: str) -> dict[str, object]:
    return json.loads((TEMPLATE_ROOT / name).read_text(encoding="utf-8"))


def test_three_profiles_preserve_eight_responsibilities_and_ten_capabilities() -> None:
    all_capabilities: set[str] = set()
    for profile in MediaTemplateProfile:
        name = profile.value.lower()
        responsibility = MediaResponsibilityTemplate.model_validate(
            _payload(f"{name}.responsibility.json")
        )
        stage = MediaStageTemplate.model_validate(_payload(f"{name}.stage.json"))

        assert responsibility.profile is profile
        assert stage.profile is profile
        assert len(responsibility.slots) == 8
        assert stage.responsibility_template_id == responsibility.template_id
        assert responsibility.slots[-1].slot_id == "media.review"
        assert responsibility.slots[-1].protected is True
        all_capabilities.update(stage.required_capability_ids)
        all_capabilities.update(responsibility.addon_capability_ids)

    assert all_capabilities == {
        "material.collect",
        "strategy.plan",
        "copy.generate",
        "script.compose",
        "speech.synthesize",
        "video.compose",
        "content.review",
        "live.orchestrate",
        "platform.adapt",
        "performance.review",
    }


def test_live_capability_is_full_only_and_governance_stays_outside_eight_slots() -> None:
    for profile in MediaTemplateProfile:
        name = profile.value.lower()
        responsibility = MediaResponsibilityTemplate.model_validate(
            _payload(f"{name}.responsibility.json")
        )
        stage = MediaStageTemplate.model_validate(_payload(f"{name}.stage.json"))
        live = [item for item in stage.stages if item.live_stage]
        if profile is MediaTemplateProfile.FULL:
            assert responsibility.addon_capability_ids == ["live.orchestrate"]
            assert len(live) == 1
        else:
            assert responsibility.addon_capability_ids == []
            assert live == []
        assert {
            "external_publication_approval",
            "receipt_reconciliation",
        } <= set(responsibility.governance_responsibility_types)
        assert all(
            item.responsibility_type
            not in responsibility.governance_responsibility_types
            for item in responsibility.slots
        )


def test_mapping_drift_live_leak_cycle_and_unknown_field_fail_closed() -> None:
    responsibility = _payload("standard.responsibility.json")
    responsibility["slots"][0]["requiredCapabilityIds"] = ["strategy.plan"]  # type: ignore[index]
    with pytest.raises(ValidationError, match="mapping drifted"):
        MediaResponsibilityTemplate.model_validate(responsibility)

    stage = _payload("standard.stage.json")
    stage["stages"][0]["requiredCapabilityIds"].append("live.orchestrate")  # type: ignore[index]
    stage["requiredCapabilityIds"].append("live.orchestrate")  # type: ignore[index]
    with pytest.raises(ValidationError, match="forbidden outside FULL"):
        MediaStageTemplate.model_validate(stage)

    cyclic = _payload("lite.stage.json")
    cyclic["stages"][0]["dependsOn"] = ["review"]  # type: ignore[index]
    with pytest.raises(ValidationError, match="acyclic"):
        MediaStageTemplate.model_validate(cyclic)

    unknown = _payload("lite.responsibility.json")
    unknown["fixedAgentCount"] = 8
    with pytest.raises(ValidationError):
        MediaResponsibilityTemplate.model_validate(unknown)
