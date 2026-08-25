from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_w6_004_creator_lifecycle_is_append_only_rls_and_single_head():
    root = Path(__file__).resolve().parents[2]
    migration = root / "alembic/versions/w6_004_creator_lifecycle.py"
    text = migration.read_text()
    assert 'revision: str = "w6_004"' in text
    assert 'down_revision: str | Sequence[str] | None = "w6_003"' in text
    assert text.count("ENABLE ROW LEVEL SECURITY") == 1
    assert text.count("FORCE ROW LEVEL SECURITY") == 1
    assert "GRANT SELECT, INSERT" in text
    assert "UPDATE" not in text and "DELETE" not in text
    assert "ecommerce_creator_batch_start_decision_revision" in text
    assert "ecommerce_creator_lane_observation" in text
    assert "ecommerce_creator_contract_revision" in text
    assert "ecommerce_creator_delivery_observation" in text
    assert "ecommerce_creator_relationship_revision" in text


def test_w6_004_is_the_only_alembic_head_without_applying_it():
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    assert ScriptDirectory.from_config(config).get_heads() == ["w6_004"]
