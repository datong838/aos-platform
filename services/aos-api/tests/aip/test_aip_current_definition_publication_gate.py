from aos_api.aip_current_definition_publication_gate import (
    DefinitionRow, DefinitionWriteState, classify_definition_rows,
)
from aos_api.aip_solution_pack_publisher import AGENT_LOGIC_COUNTS, CAPABILITY_IDS, LOGIC_IDS


def _complete():
    return [
        DefinitionRow(kind, identifier, 1, "1.11.0", "sha256:" + "a" * 64)
        for kind, identifiers in (
            ("agent", AGENT_LOGIC_COUNTS),
            ("skill", [f"ecommerce.skill.{value}" for value in LOGIC_IDS]),
            ("capability", CAPABILITY_IDS),
        )
        for identifier in identifiers
    ]


def test_empty_is_only_write_candidate():
    assert classify_definition_rows([]) is DefinitionWriteState.EMPTY


def test_complete_is_read_only_not_new_write_candidate():
    assert classify_definition_rows(_complete()) is DefinitionWriteState.COMPLETE


def test_partial_is_frozen():
    assert classify_definition_rows(_complete()[:-1]) is DefinitionWriteState.FREEZE_PARTIAL_OR_CONFLICT


def test_duplicate_is_frozen():
    rows = _complete()
    assert classify_definition_rows(rows + rows[:1]) is DefinitionWriteState.FREEZE_PARTIAL_OR_CONFLICT


def test_wrong_source_or_revision_or_hash_is_frozen():
    rows = _complete()
    first = rows[0]
    for changed in (
        DefinitionRow(first.kind, first.asset_id, 1, "1.2.0", first.content_hash),
        DefinitionRow(first.kind, first.asset_id, 2, first.source_revision, first.content_hash),
        DefinitionRow(first.kind, first.asset_id, 1, first.source_revision, ""),
    ):
        assert classify_definition_rows([changed, *rows[1:]]) is DefinitionWriteState.FREEZE_PARTIAL_OR_CONFLICT
