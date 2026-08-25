"""W7-11 cumulative and fail-closed fault tests."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aos_api.ecommerce_workshop_media_cumulative import EcommerceWorkshopMediaCumulative
from aos_api.ecommerce_workshop_media_cumulative_contracts import (
    MediaCumulativeGateId,
    MediaCumulativeGateSet,
)


CUTOFF = datetime(2026, 8, 26, 2, 30, tzinfo=UTC)


def test_eleven_columns_keep_external_operational_gates_blocked() -> None:
    result = EcommerceWorkshopMediaCumulative().read(cutoff=CUTOFF)

    assert [item.gate_id for item in result.gates] == list(MediaCumulativeGateId)
    assert sum(item.status == "ready" for item in result.gates) == 8
    assert result.blocker_codes == [
        "MEDIA_OPERATIONAL_READY_RECEIPT_REQUIRED",
        "MEDIA_PRODUCTION_PROVIDER_ADAPTER_RECEIPT_REQUIRED",
        "MEDIA_PUBLISH_CANARY_RECEIPT_REQUIRED",
    ]
    assert result.overall_status == "blocked"
    assert result.external_effects_allowed is False
    assert result.release_allowed is False


def test_same_cutoff_rebuild_is_deterministic_after_restart() -> None:
    first = EcommerceWorkshopMediaCumulative().read(cutoff=CUTOFF)
    restarted = EcommerceWorkshopMediaCumulative().read(cutoff=CUTOFF)
    assert first.model_dump(mode="json", by_alias=True) == restarted.model_dump(mode="json", by_alias=True)


def test_missing_or_reordered_gate_fails_closed() -> None:
    raw = EcommerceWorkshopMediaCumulative().read(cutoff=CUTOFF).model_dump(mode="json", by_alias=True)
    raw["gates"] = raw["gates"][:-1]
    with pytest.raises(ValidationError):
        MediaCumulativeGateSet.model_validate(raw)

    raw = EcommerceWorkshopMediaCumulative().read(cutoff=CUTOFF).model_dump(mode="json", by_alias=True)
    raw["gates"][0], raw["gates"][1] = raw["gates"][1], raw["gates"][0]
    with pytest.raises(ValidationError):
        MediaCumulativeGateSet.model_validate(raw)


def test_stale_unknown_or_forged_external_effect_cannot_be_green() -> None:
    raw = EcommerceWorkshopMediaCumulative().read(cutoff=CUTOFF).model_dump(mode="json", by_alias=True)
    raw["gates"][7]["status"] = "stale"
    raw["gates"][7]["evidenceRef"] = None
    raw["gates"][7]["observedAt"] = None
    raw["gates"][7]["reasonCode"] = "MEDIA_FAULT_EVIDENCE_STALE"
    raw["blockerCodes"] = sorted(raw["blockerCodes"] + ["MEDIA_FAULT_EVIDENCE_STALE"])
    assert MediaCumulativeGateSet.model_validate(raw).overall_status == "blocked"

    raw["externalEffectsAllowed"] = True
    with pytest.raises(ValidationError):
        MediaCumulativeGateSet.model_validate(raw)


def test_operational_gate_cannot_be_marked_ready_with_engineering_evidence() -> None:
    raw = EcommerceWorkshopMediaCumulative().read(cutoff=CUTOFF).model_dump(mode="json", by_alias=True)
    raw["gates"][-1] = raw["gates"][0] | {"gateId": "operational_ready"}
    raw["blockerCodes"] = [code for code in raw["blockerCodes"] if code != "MEDIA_OPERATIONAL_READY_RECEIPT_REQUIRED"]
    with pytest.raises(ValidationError):
        MediaCumulativeGateSet.model_validate(raw)
