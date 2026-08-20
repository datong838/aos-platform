from __future__ import annotations

from aos_api.aip_media_responsibility_capability_map import (
    LIVE_ADDON_CAPABILITY_ID,
    all_mapped_capability_ids,
    media_slot_ids,
    required_capability_ids_for_slot,
)


def test_media_map_covers_eight_slots_and_ten_capabilities() -> None:
    slots = media_slot_ids()
    assert len(slots) == 8
    assert "media.review" in slots
    mapped = all_mapped_capability_ids()
    assert LIVE_ADDON_CAPABILITY_ID in mapped
    # Ten catalog capabilities from 59-W7-01
    expected = {
        "strategy.plan",
        "material.collect",
        "performance.review",
        "copy.generate",
        "script.compose",
        "platform.adapt",
        "video.compose",
        "speech.synthesize",
        "content.review",
        "live.orchestrate",
    }
    assert expected <= mapped


def test_legacy_content_review_slot_alias() -> None:
    assert required_capability_ids_for_slot("content.review") == ("content.review",)
    assert "content.review" in required_capability_ids_for_slot("media.review")
    assert "performance.review" in required_capability_ids_for_slot("media.review")
