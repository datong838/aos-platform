from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_w6_007_customer_lifecycle_is_append_only_rls_and_single_head():
    root = Path(__file__).parents[2]
    text = (root / "alembic/versions/w6_007_customer_lifecycle.py").read_text()
    assert 'revision: str = "w6_007"' in text
    assert 'down_revision: str | Sequence[str] | None = "w6_006"' in text
    assert "FORCE ROW LEVEL SECURITY" in text and "GRANT SELECT, INSERT" in text
    assert "GRANT SELECT, INSERT, UPDATE" not in text and "GRANT SELECT, INSERT, DELETE" not in text
    config = Config(str(root / "alembic.ini"))
    assert ScriptDirectory.from_config(config).get_heads() == ["w6_009"]
