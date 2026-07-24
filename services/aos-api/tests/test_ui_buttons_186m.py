"""186m — button alignment markers (CSS class present in source)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3] / "apps" / "web" / "src"


def test_data_page_uses_bp_card_hit():
    text = (ROOT / "pages" / "DataPage.tsx").read_text(encoding="utf-8")
    assert 'className="bp-card-hit"' in text
    assert "all: \"unset\"" not in text and "all: 'unset'" not in text


def test_graph_health_has_ttl_button():
    text = (ROOT / "pages" / "s2" / "ontology.tsx").read_text(encoding="utf-8")
    assert "运行 TTL 归档" in text
    assert "/v1/ops/ttl/run" in text


def test_styles_define_bp_card_hit():
    css = (ROOT / "styles.css").read_text(encoding="utf-8")
    assert ".bp-card-hit" in css
