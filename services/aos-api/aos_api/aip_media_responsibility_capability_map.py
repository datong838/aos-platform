"""Media responsibility slot → Capability ID map (59-W7-01 / 59 §8.4).

Read-only authority for W-L4. Not a second lifecycle store — canonical IDs only.
"""
from __future__ import annotations

from typing import Mapping

# Eight professional media responsibility slots (live.orchestrate is optional add-on).
MEDIA_RESPONSIBILITY_CAPABILITY_MAP: Mapping[str, tuple[str, ...]] = {
    "media.producer": ("strategy.plan", "material.collect", "performance.review"),
    "media.director": ("strategy.plan", "copy.generate", "script.compose"),
    "media.screenwriter": ("copy.generate", "script.compose"),
    "media.art": ("material.collect", "strategy.plan", "platform.adapt"),
    "media.storyboard": ("script.compose", "video.compose"),
    "media.capture": ("material.collect", "speech.synthesize", "video.compose"),
    "media.post": ("speech.synthesize", "video.compose", "platform.adapt"),
    "media.review": ("content.review", "performance.review"),
}

LIVE_ADDON_CAPABILITY_ID = "live.orchestrate"

# Legacy template slot id keeps working as an alias of media.review's primary capability.
LEGACY_SLOT_ALIASES: Mapping[str, str] = {
    "content.review": "media.review",
}


def required_capability_ids_for_slot(slot_id: str) -> tuple[str, ...]:
    """Return required Capability IDs for a media (or legacy) responsibility slot."""
    canonical = LEGACY_SLOT_ALIASES.get(slot_id, slot_id)
    if canonical not in MEDIA_RESPONSIBILITY_CAPABILITY_MAP:
        raise KeyError(f"unknown media responsibility slot: {slot_id}")
    if slot_id == "content.review":
        return ("content.review",)
    return MEDIA_RESPONSIBILITY_CAPABILITY_MAP[canonical]


def media_slot_ids() -> tuple[str, ...]:
    return tuple(MEDIA_RESPONSIBILITY_CAPABILITY_MAP.keys())


def all_mapped_capability_ids() -> frozenset[str]:
    ids: set[str] = {LIVE_ADDON_CAPABILITY_ID}
    for caps in MEDIA_RESPONSIBILITY_CAPABILITY_MAP.values():
        ids.update(caps)
    return frozenset(ids)
