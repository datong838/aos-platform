"""Read-only classification of the current 6/37/10 definition write boundary."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable

from aos_api.aip_solution_pack_publisher import (
    AGENT_LOGIC_COUNTS, CAPABILITY_IDS, CURRENT_SIGNED_CANDIDATE_VERSION, LOGIC_IDS,
)


class DefinitionWriteState(StrEnum):
    EMPTY = "EMPTY"
    COMPLETE = "COMPLETE"
    FREEZE_PARTIAL_OR_CONFLICT = "FREEZE_PARTIAL_OR_CONFLICT"


@dataclass(frozen=True, slots=True)
class DefinitionRow:
    kind: str
    asset_id: str
    revision: int
    source_revision: str | None
    content_hash: str | None


_EXPECTED = {
    "agent": frozenset(AGENT_LOGIC_COUNTS),
    "skill": frozenset(f"ecommerce.skill.{logic_id}" for logic_id in LOGIC_IDS),
    "capability": frozenset(CAPABILITY_IDS),
}


def classify_definition_rows(rows: Iterable[DefinitionRow]) -> DefinitionWriteState:
    """No row may be mixed, repaired, or silently retried at this boundary."""
    items = tuple(rows)
    if not items:
        return DefinitionWriteState.EMPTY
    by_kind = {kind: set() for kind in _EXPECTED}
    for row in items:
        if row.kind not in _EXPECTED or row.asset_id not in _EXPECTED[row.kind] \
                or row.revision != 1 or row.source_revision != CURRENT_SIGNED_CANDIDATE_VERSION \
                or not row.content_hash or row.asset_id in by_kind[row.kind]:
            return DefinitionWriteState.FREEZE_PARTIAL_OR_CONFLICT
        by_kind[row.kind].add(row.asset_id)
    if all(by_kind[kind] == expected for kind, expected in _EXPECTED.items()):
        return DefinitionWriteState.COMPLETE
    return DefinitionWriteState.FREEZE_PARTIAL_OR_CONFLICT
