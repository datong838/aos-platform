"""186m — button alignment markers (CSS class present in source)."""
from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3] / "apps" / "web" / "src"
CSS_IMPORT = re.compile(r'@import\s+(?:url\()?\s*["\']([^"\']+)["\']')


def _read_local_css_graph(path: Path, seen: set[Path] | None = None) -> str:
    """Read a CSS facade and its local imports in declared order."""
    resolved = path.resolve()
    visited = seen if seen is not None else set()
    if resolved in visited:
        return ""
    visited.add(resolved)
    text = resolved.read_text(encoding="utf-8")
    imported = []
    for reference in CSS_IMPORT.findall(text):
        if "://" in reference:
            continue
        imported.append(_read_local_css_graph(resolved.parent / reference, visited))
    return "\n".join([text, *imported])


def test_data_page_uses_bp_card_hit():
    text = (ROOT / "pages" / "DataPage.tsx").read_text(encoding="utf-8")
    assert 'className="bp-card-hit"' in text
    assert "all: \"unset\"" not in text and "all: 'unset'" not in text


def test_graph_health_has_ttl_button():
    text = (ROOT / "pages" / "s2" / "ontology.tsx").read_text(encoding="utf-8")
    assert "运行 TTL 归档" in text
    assert "/v1/ops/ttl/run" in text


def test_styles_define_bp_card_hit():
    css = _read_local_css_graph(ROOT / "styles.css")
    assert ".bp-card-hit" in css
