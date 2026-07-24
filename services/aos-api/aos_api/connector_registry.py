"""Connector plugin registry — scheme 97 · 对齐 20 §3.1 / T05 §3."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from aos_api.aip_kv_store import get_payload, put_payload
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.connector_registry")

KEY_INSTALLS = "connector_plugin_installs"

_ID_RE = re.compile(r"^[a-z][a-z0-9-]{1,63}$")

# T05 必做 · 默认已装（兼容旧 sources type=file/jdbc）
DEFAULT_INSTALLED = ("file-local", "file-object-store", "jdbc-mysql")

# 旧 UI / API 别名 → 插件 id
TYPE_ALIASES = {
    "file": "file-local",
    "jdbc": "jdbc-mysql",
    "mysql": "jdbc-mysql",
}


def plugins_root() -> Path:
    env = (os.environ.get("AOS_PLUGINS_ROOT") or "").strip()
    if env:
        return Path(env) / "connectors"
    return Path(__file__).resolve().parents[3] / "plugins" / "connectors"


def _read_manifest(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("connector_manifest_fail path=%s err=%s", path, exc)
        return None
    if not isinstance(data, dict) or not data.get("id"):
        return None
    return data


def _scan_disk() -> list[dict[str, Any]]:
    root = plugins_root()
    if not root.is_dir():
        log.warning("connector_plugins_root_missing path=%s", root)
        return []
    items: list[dict[str, Any]] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith("_"):
            continue
        man = _read_manifest(child / "manifest.json")
        if man:
            row = dict(man)
            row["source"] = "disk"
            items.append(row)
    return items


def _installed_ids() -> set[str]:
    stored = get_payload(KEY_INSTALLS) or {}
    raw = stored.get("installed")
    if not isinstance(raw, list):
        return set(DEFAULT_INSTALLED)
    ids = {str(x) for x in raw}
    # 首次空表：种子必做
    if not ids and stored.get("seeded") is not True:
        ids = set(DEFAULT_INSTALLED)
        put_payload(KEY_INSTALLS, {"installed": sorted(ids), "seeded": True})
    return ids


def _save_installed(ids: set[str]) -> list[str]:
    ordered = sorted(ids)
    put_payload(KEY_INSTALLS, {"installed": ordered, "seeded": True})
    return ordered


def normalize_type(raw: str) -> str:
    t = (raw or "").strip()
    if not t:
        return "file-local"
    return TYPE_ALIASES.get(t, t)


def resolve_plugin_id(raw: str) -> str | None:
    """返回已扫描到的插件 id；未知返回 None。"""
    pid = normalize_type(raw)
    by_id = {str(m["id"]): m for m in _scan_disk()}
    if pid in by_id:
        return pid
    return None


def list_connector_plugins() -> dict[str, Any]:
    by_id: dict[str, dict[str, Any]] = {}
    for man in _scan_disk():
        by_id[str(man["id"])] = man
    installed = _installed_ids()
    # 必做始终视为已装（防误卸光验收底线）
    for auto in DEFAULT_INSTALLED:
        if auto in by_id:
            installed.add(auto)
    items: list[dict[str, Any]] = []
    for mid, man in sorted(by_id.items(), key=lambda x: x[0]):
        items.append(
            {
                "id": mid,
                "version": man.get("version") or "0.1.0",
                "name": man.get("name") or mid,
                "nameZh": man.get("nameZh") or man.get("name") or mid,
                "description": man.get("description") or "",
                "kind": man.get("kind") or "source",
                "runtime": man.get("runtime") or "stub",
                "capabilities": list(man.get("capabilities") or []),
                "healthPath": man.get("healthPath") or None,
                "author": man.get("author") or "aos",
                "configSchema": man.get("configSchema") or {},
                "source": man.get("source") or "disk",
                "installed": mid in installed,
                "required": mid in DEFAULT_INSTALLED,
            }
        )
    return {
        "items": items,
        "aliases": dict(TYPE_ALIASES),
        "pluginsRoot": str(plugins_root()),
    }


def install_plugin(plugin_id: str) -> dict[str, Any]:
    pid = (plugin_id or "").strip()
    if not _ID_RE.match(pid):
        raise ValueError("invalid plugin id")
    by_id = {str(m["id"]): m for m in _scan_disk()}
    if pid not in by_id:
        raise KeyError(pid)
    ids = _installed_ids()
    ids.add(pid)
    _save_installed(ids)
    log.info("connector_plugin_installed id=%s", pid)
    return {"id": pid, "installed": True}


def uninstall_plugin(plugin_id: str) -> dict[str, Any]:
    pid = (plugin_id or "").strip()
    if pid in DEFAULT_INSTALLED:
        raise PermissionError("required connector cannot be uninstalled")
    ids = _installed_ids()
    ids.discard(pid)
    _save_installed(ids)
    log.info("connector_plugin_uninstalled id=%s", pid)
    return {"id": pid, "installed": False}


def assert_type_installed(raw_type: str) -> str:
    """校验并可返回归一化插件 id；失败抛 ValueError / KeyError。"""
    pid = resolve_plugin_id(raw_type)
    if not pid:
        raise KeyError(f"unknown connector plugin: {raw_type}")
    installed = _installed_ids()
    for auto in DEFAULT_INSTALLED:
        installed.add(auto)
    if pid not in installed:
        raise PermissionError(f"connector plugin not installed: {pid}")
    return pid
