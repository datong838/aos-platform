from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_w6_006_price_disposition_is_append_only_rls_and_single_head():
    root = Path(__file__).parents[2]
    text = (root / "alembic/versions/w6_006_price_disposition.py").read_text()
    assert 'revision: str = "w6_006"' in text
    assert 'down_revision: str | Sequence[str] | None = "w6_005"' in text
    assert text.count("ENABLE ROW LEVEL SECURITY") == 1
    assert "FORCE ROW LEVEL SECURITY" in text
    assert "GRANT SELECT, INSERT" in text
    assert "UPDATE" not in text and "DELETE" not in text
    config = Config(str(root / "alembic.ini"))
    assert ScriptDirectory.from_config(config).get_heads() == ["w6_008"]
