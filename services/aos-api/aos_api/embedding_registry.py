"""Embedding / Rerank plugin registry — scheme 98 · 对齐 20 §3.1 / T07 stub."""
from __future__ import annotations

from typing import Any

from aos_api import plugin_disk

KEY = "embedding_plugin_installs"
SUBDIR = "embeddings"
DEFAULTS: tuple[str, ...] = ()


def list_embedding_plugins() -> dict[str, Any]:
    return plugin_disk.list_domain(SUBDIR, KEY, defaults=DEFAULTS, required=())


def install_plugin(plugin_id: str) -> dict[str, Any]:
    return plugin_disk.install(SUBDIR, KEY, plugin_id, DEFAULTS)


def uninstall_plugin(plugin_id: str) -> dict[str, Any]:
    return plugin_disk.uninstall(SUBDIR, KEY, plugin_id, defaults=DEFAULTS, required=())
