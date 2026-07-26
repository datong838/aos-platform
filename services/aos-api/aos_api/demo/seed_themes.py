"""Seed themes — Phase 1 Workshop backend.

3 theme presets: light / dark / high-contrast.
Idempotent: delete by org_id then insert.
"""
from __future__ import annotations

import json

from aos_api.db import connect
from aos_api.logging_facade import get_logger
from aos_api.themes import ensure_schema

log = get_logger("aos-api.demo.seed_themes")

_DEFAULT_ORG = "dev-org"
_DEFAULT_PROJECT = "dev-project"

_THEMES = [
    {
        "id": "theme-light",
        "name": "浅色",
        "mode": "light",
        "isPreset": True,
        "description": "默认浅色主题",
        "tokens": {
            "colorPrimary": "#1677ff",
            "colorBgBase": "#ffffff",
            "colorTextBase": "#000000",
            "colorBorder": "#d9d9d9",
            "colorSuccess": "#52c41a",
            "colorWarning": "#faad14",
            "colorError": "#ff4d4f",
        },
    },
    {
        "id": "theme-dark",
        "name": "暗色",
        "mode": "dark",
        "isPreset": True,
        "description": "暗色主题",
        "tokens": {
            "colorPrimary": "#1668dc",
            "colorBgBase": "#141414",
            "colorTextBase": "#ffffff",
            "colorBorder": "#434343",
            "colorSuccess": "#49aa19",
            "colorWarning": "#d89614",
            "colorError": "#dc4446",
        },
    },
    {
        "id": "theme-high-contrast",
        "name": "高对比度",
        "mode": "high-contrast",
        "isPreset": True,
        "description": "无障碍高对比度主题",
        "tokens": {
            "colorPrimary": "#0066cc",
            "colorBgBase": "#000000",
            "colorTextBase": "#ffffff",
            "colorBorder": "#ffffff",
            "colorSuccess": "#00ff00",
            "colorWarning": "#ffff00",
            "colorError": "#ff0000",
        },
    },
]


def seed_themes() -> int:
    """Idempotently seed 3 theme presets. Returns count."""
    ensure_schema()
    with connect() as conn:
        conn.execute(
            "DELETE FROM theme WHERE org_id=%s AND project_id=%s",
            (_DEFAULT_ORG, _DEFAULT_PROJECT),
        )
        for t in _THEMES:
            conn.execute(
                """
                INSERT INTO theme (
                    id, name, mode, is_preset, tokens, description, org_id, project_id
                ) VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s,%s)
                ON CONFLICT (id) DO UPDATE SET
                    name=EXCLUDED.name, mode=EXCLUDED.mode,
                    is_preset=EXCLUDED.is_preset, tokens=EXCLUDED.tokens,
                    description=EXCLUDED.description, updated_at=NOW()
                """,
                (
                    t["id"],
                    t["name"],
                    t["mode"],
                    t["isPreset"],
                    json.dumps(t["tokens"]),
                    t["description"],
                    _DEFAULT_ORG,
                    _DEFAULT_PROJECT,
                ),
            )
        conn.commit()
    log.info("seed_themes_done count=%s", len(_THEMES))
    return len(_THEMES)
