from __future__ import annotations

import importlib.util
from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "alembic/versions/w3_014_production_context_profile.py"
)


def test_w3_014_adds_nullable_exact_profile_provenance_without_rewriting_history() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "w3_014"' in text
    assert 'down_revision: str | Sequence[str] | None = "w4_001"' in text
    assert "ADD COLUMN production_profile_ref JSONB" in text
    assert "production_profile_ref IS NULL" in text
    assert "UPDATE aip_production_context_revision" not in text
    assert "DELETE FROM aip_production_context_revision" not in text


def test_w3_014_module_loads() -> None:
    spec = importlib.util.spec_from_file_location("w3_014", MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.revision == "w3_014"
    assert module.down_revision == "w4_001"
