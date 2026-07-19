"""Widget plugin registry — scheme 98 · 对齐 20 §3.1 / T08 §4."""
from __future__ import annotations

from typing import Any

from aos_api import plugin_disk

KEY = "widget_plugin_installs"
SUBDIR = "widgets"
DEFAULTS = ("filter-list", "object-table", "buddy-chip", "object-view")


def list_widget_plugins() -> dict[str, Any]:
    return plugin_disk.list_domain(
        SUBDIR,
        KEY,
        defaults=DEFAULTS,
        required=DEFAULTS,
        extra_fields=("canvasKind", "palette"),
    )


def install_plugin(plugin_id: str) -> dict[str, Any]:
    return plugin_disk.install(SUBDIR, KEY, plugin_id, DEFAULTS)


def uninstall_plugin(plugin_id: str) -> dict[str, Any]:
    return plugin_disk.uninstall(
        SUBDIR, KEY, plugin_id, defaults=DEFAULTS, required=DEFAULTS
    )


def palette_items() -> list[dict[str, Any]]:
    """Canvas 可挂调色板：已安装且 palette!=false 且有 canvasKind（含 stub）。"""
    items = []
    for it in list_widget_plugins().get("items") or []:
        if not it.get("installed"):
            continue
        if it.get("palette") is False:
            continue
        kind = it.get("canvasKind")
        if not kind:
            continue
        items.append(
            {
                "id": it["id"],
                "pluginId": it["id"],
                "kind": kind,
                "label": f"+ {it.get('nameZh') or it.get('name') or it['id']}",
                "nameZh": it.get("nameZh"),
                "runtime": it.get("runtime") or "inproc",
                "stub": kind == "stub" or (it.get("runtime") == "stub"),
            }
        )
    return items
