"""Parser plugin registry — scheme 98 · 对齐 20 §3.1 / T05 §4.4."""
from __future__ import annotations

from typing import Any

from aos_api import plugin_disk

KEY = "parser_plugin_installs"
SUBDIR = "parsers"
DEFAULTS = (
    "parser-text",
    "parser-office-word",
    "parser-office-sheet",
    "parser-pdf-text",
    "parser-pdf-ocr",
)


def list_parser_plugins() -> dict[str, Any]:
    return plugin_disk.list_domain(
        SUBDIR,
        KEY,
        defaults=DEFAULTS,
        required=DEFAULTS,
        extra_fields=("formats", "healthPath"),
    )


def install_plugin(plugin_id: str) -> dict[str, Any]:
    return plugin_disk.install(SUBDIR, KEY, plugin_id, DEFAULTS)


def uninstall_plugin(plugin_id: str) -> dict[str, Any]:
    return plugin_disk.uninstall(
        SUBDIR, KEY, plugin_id, defaults=DEFAULTS, required=DEFAULTS
    )


def list_plugins_compat() -> list[dict[str, str]]:
    """兼容 file_parsers.list_plugins 旧形状。"""
    out: list[dict[str, str]] = []
    for it in list_parser_plugins().get("items") or []:
        if not it.get("installed"):
            continue
        formats = it.get("formats")
        if isinstance(formats, list):
            fmt = ",".join(str(x) for x in formats)
        else:
            fmt = str(formats or "")
        out.append(
            {
                "id": str(it["id"]),
                "formats": fmt,
                "note": str(it.get("runtime") or it.get("description") or ""),
            }
        )
    return out
