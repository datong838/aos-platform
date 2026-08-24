from __future__ import annotations

import importlib.util
from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "alembic/versions/w3_015_production_start_context.py"
)


def test_w3_015_adds_nullable_context_provenance_without_rewriting_history() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "w3_015"' in text
    assert 'down_revision: str | Sequence[str] | None = "w3_014"' in text
    assert text.count("ADD COLUMN production_context_ref JSONB") == 2
    assert "production_context_ref IS NULL" in text
    assert "UPDATE aip_impact_preview_revision" not in text
    assert "UPDATE aip_production_start_decision" not in text


def test_w3_015_module_loads() -> None:
    spec = importlib.util.spec_from_file_location("w3_015", MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.revision == "w3_015"
    assert module.down_revision == "w3_014"
