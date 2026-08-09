from __future__ import annotations

import importlib.util
from pathlib import Path


MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "alembic/versions/o1r1_001_authoritative_outbox_contract.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("o1r1_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_o1r1_migration_extends_o1a0_without_rewriting_history() -> None:
    migration = _load_migration()
    assert migration.revision == "o1r1_001"
    assert migration.down_revision == "d5e1_001"


def test_o1r1_migration_freezes_authoritative_event_contract() -> None:
    source = MIGRATION_PATH.read_text(encoding="utf-8")
    for contract in (
        "projection_input_revision_seq",
        "legacy_post_projection",
        "authoritative_store",
        "event_key",
        "payload_hash",
        "authority_tx_id",
        "REFERENCES twa_workspace(org_id, project_id)",
    ):
        assert contract in source
