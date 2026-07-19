"""186m — blueprint button class alignment (static file asserts)."""
from __future__ import annotations

from pathlib import Path

import pytest

WEB = Path(__file__).resolve().parents[3] / "apps" / "web" / "src" / "pages"


def _read(rel: str) -> str:
    p = WEB / rel
    assert p.is_file(), f"missing {p}"
    return p.read_text(encoding="utf-8")


def test_data_page_no_toolbar_nav_link_return():
    text = _read("DataPage.tsx")
    assert 'className="nav-link" onClick={() => setSourceView("list")}' not in text
    assert 'className="btn-nav" onClick={() => setSourceView("list")}' in text
    assert 'className="btn-primary" onClick={() => void createSource()}' in text


def test_canvas_save_layout_primary():
    text = _read("CanvasPage.tsx")
    assert 'className="btn-primary" disabled={!dirty} onClick={() => void saveLayout()}' in text


def test_media_upload_primary():
    text = _read("s2/data.tsx")
    assert 'className="btn-primary" onClick={() => void uploadAndParse()}' in text


def test_graph_health_refresh_not_primary():
    text = _read("s2/ontology.tsx")
    # GraphHealth reload should be secondary btn
    assert 'className="btn" onClick={() => reload()}' in text
    assert '重新扫描' in text


def test_schedule_save_primary():
    text = _read("s2/dataSchedules.tsx")
    assert 'className="btn-primary" onClick={() => void saveSch()}' in text
