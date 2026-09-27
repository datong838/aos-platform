"""No current DB writes: exercise durable intent and readback failure gates."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from aos_api.aip_current_definition_publication_gate import DefinitionRow
from aos_api.aip_solution_pack_publisher import AGENT_LOGIC_COUNTS, CAPABILITY_IDS, LOGIC_IDS


SCRIPT = Path(__file__).resolve().parents[4] / "scripts/a0v_current_aip_definition_publish.py"
SPEC = importlib.util.spec_from_file_location("current_definition_writer_under_test", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
writer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(writer)


def _publication():
    def refs(identifiers):
        return tuple(SimpleNamespace(asset_id=identifier, revision=1, content_hash="sha256:" + "a" * 64)
                     for identifier in identifiers)
    return SimpleNamespace(
        agent_refs=refs(AGENT_LOGIC_COUNTS),
        skill_refs=refs(f"ecommerce.skill.{value}" for value in LOGIC_IDS),
        capability_refs=refs(CAPABILITY_IDS),
    )


def _rows():
    return [
        DefinitionRow(kind, ref.asset_id, ref.revision, "1.11.0", ref.content_hash)
        for kind, refs in (
            ("agent", _publication().agent_refs),
            ("skill", _publication().skill_refs),
            ("capability", _publication().capability_refs),
        )
        for ref in refs
    ]


def test_intent_is_durable_and_second_attempt_freezes(tmp_path):
    path = tmp_path / writer.INTENT_NAME
    writer._write_intent(path, {"intentId": "one", "database": "aos_current_preview_20260927"})
    assert path.read_text().count("one") == 1
    with pytest.raises(writer.PublicationBlocked, match="INTENT_ALREADY_EXISTS_FREEZE"):
        writer._write_intent(path, {"intentId": "two"})
    assert "two" not in path.read_text()


def test_exact_readback_accepts_only_matching_53(monkeypatch):
    monkeypatch.setattr(writer, "_definition_rows", lambda _parameters: _rows())
    writer._exact_readback({}, _publication())
    monkeypatch.setattr(writer, "_definition_rows", lambda _parameters: _rows()[:-1])
    with pytest.raises(writer.PublicationBlocked, match="INCOMPLETE"):
        writer._exact_readback({}, _publication())


def test_exact_readback_rejects_different_hash(monkeypatch):
    rows = _rows()
    first = rows[0]
    rows[0] = DefinitionRow(first.kind, first.asset_id, first.revision, first.source_revision,
                            "sha256:" + "b" * 64)
    monkeypatch.setattr(writer, "_definition_rows", lambda _parameters: rows)
    with pytest.raises(writer.PublicationBlocked, match="HASH_DRIFT"):
        writer._exact_readback({}, _publication())
