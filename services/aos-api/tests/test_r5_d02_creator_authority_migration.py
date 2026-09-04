from pathlib import Path

from aos_api.ecommerce_workshop_creator_growth_store import authority_receipt_id


def test_receipt_id_is_stable_and_bound_to_tenant_identity_revision_and_hash() -> None:
    first = authority_receipt_id("org-org", "dev-project", "CreatorContractRevision", "collab-1", 1, "a" * 64)
    assert first == authority_receipt_id("org-org", "dev-project", "CreatorContractRevision", "collab-1", 1, "a" * 64)
    assert first.startswith("creator-authority-") and len(first) == 58
    assert first != authority_receipt_id("dev-org", "dev-project", "CreatorContractRevision", "collab-1", 1, "a" * 64)
    assert first != authority_receipt_id("org-org", "dev-project", "CreatorContractRevision", "collab-1", 2, "a" * 64)


def test_migration_adds_persistent_receipts_to_four_existing_canonical_tables() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "alembic/versions/r5_d02_001_creator_authority_receipts.py").read_text(encoding="utf-8")
    assert 'revision: str = "r5_d02_001"' in text
    assert 'down_revision: str | Sequence[str] | None = "aip_p5_001"' in text
    assert text.count("ADD COLUMN authority_receipt_id TEXT") == 1
    assert "ecommerce_creator_batch_preparation_revision" in text
    assert "ecommerce_creator_contract_revision" in text
    assert "ecommerce_creator_delivery_observation" in text
    assert "ecommerce_creator_relationship_revision" in text
    assert "SET NOT NULL" in text and "CREATE UNIQUE INDEX" in text
    assert "DROP COLUMN authority_receipt_id" in text
