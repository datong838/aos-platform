from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_w6_008_customer_contact_is_append_only_rls_and_single_head():
    root = Path(__file__).parents[2]
    text = (root / "alembic/versions/w6_008_customer_contact.py").read_text()
    assert 'revision: str = "w6_008"' in text
    assert 'down_revision: str | Sequence[str] | None = "w6_007"' in text
    assert "FORCE ROW LEVEL SECURITY" in text and "GRANT SELECT, INSERT" in text
    assert "ecommerce_customer_frequency_reservation_revision" in text
    assert "ecommerce_customer_frequency_reservation_window_idx" in text
    assert "GRANT SELECT, INSERT, UPDATE" not in text and "GRANT SELECT, INSERT, DELETE" not in text
    assert "raw_contact" not in text and "provider_payload" not in text
    config = Config(str(root / "alembic.ini"))
    assert ScriptDirectory.from_config(config).get_heads() == ["w6_008"]
