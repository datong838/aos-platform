"""Shared disk plugin scan helpers — schemes 97/98 · 对齐 20 §3.1."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from aos_api.aip_kv_store import get_payload, put_payload
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.plugin_disk")

_ID_RE = re.compile(r"^[a-z][a-z0-9-]{1,63}$")


def aos_plugins_root() -> Path:
    env = (os.environ.get("AOS_PLUGINS_ROOT") or "").strip()
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[3] / "plugins"


def subdomain_root(subdir: str) -> Path:
    return aos_plugins_root() / subdir


def read_manifest(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("manifest_fail path=%s err=%s", path, exc)
        return None
    if not isinstance(data, dict) or not data.get("id"):
        return None
    return data


def scan_disk(subdir: str) -> list[dict[str, Any]]:
    root = subdomain_root(subdir)
    if not root.is_dir():
        log.warning("plugins_subdir_missing path=%s", root)
        return []
    items: list[dict[str, Any]] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith("_"):
            continue
        man = read_manifest(child / "manifest.json")
        if man:
            row = dict(man)
            row["source"] = "disk"
            items.append(row)
    return items


def load_installed(kv_key: str, defaults: tuple[str, ...]) -> set[str]:
    stored = get_payload(kv_key) or {}
    raw = stored.get("installed")
    if not isinstance(raw, list):
        ids = set(defaults)
        put_payload(kv_key, {"installed": sorted(ids), "seeded": True})
        return ids
    ids = {str(x) for x in raw}
    if not ids and stored.get("seeded") is not True:
        ids = set(defaults)
        put_payload(kv_key, {"installed": sorted(ids), "seeded": True})
    return ids


def save_installed(kv_key: str, ids: set[str]) -> list[str]:
    ordered = sorted(ids)
    put_payload(kv_key, {"installed": ordered, "seeded": True})
    return ordered


def install(subdir: str, kv_key: str, plugin_id: str, defaults: tuple[str, ...] = ()) -> dict[str, Any]:
    pid = (plugin_id or "").strip()
    if not _ID_RE.match(pid):
        raise ValueError("invalid plugin id")
    by_id = {str(m["id"]): m for m in scan_disk(subdir)}
    if pid not in by_id:
        raise KeyError(pid)
    ids = load_installed(kv_key, defaults)
    ids.add(pid)
    save_installed(kv_key, ids)
    log.info("plugin_installed subdir=%s id=%s", subdir, pid)
    return {"id": pid, "installed": True}


def uninstall(
    subdir: str,
    kv_key: str,
    plugin_id: str,
    *,
    defaults: tuple[str, ...] = (),
    required: tuple[str, ...] = (),
) -> dict[str, Any]:
    pid = (plugin_id or "").strip()
    if pid in required:
        raise PermissionError("required plugin cannot be uninstalled")
    ids = load_installed(kv_key, defaults)
    ids.discard(pid)
    save_installed(kv_key, ids)
    log.info("plugin_uninstalled subdir=%s id=%s", subdir, pid)
    return {"id": pid, "installed": False}


def list_domain(
    subdir: str,
    kv_key: str,
    *,
    defaults: tuple[str, ...] = (),
    required: tuple[str, ...] = (),
    extra_fields: tuple[str, ...] = (),
) -> dict[str, Any]:
    by_id: dict[str, dict[str, Any]] = {}
    for man in scan_disk(subdir):
        by_id[str(man["id"])] = man
    installed = load_installed(kv_key, defaults)
    for auto in required or defaults:
        if auto in by_id:
            installed.add(auto)
    items: list[dict[str, Any]] = []
    for mid, man in sorted(by_id.items(), key=lambda x: x[0]):
        row: dict[str, Any] = {
            "id": mid,
            "version": man.get("version") or "0.1.0",
            "name": man.get("name") or mid,
            "nameZh": man.get("nameZh") or man.get("name") or mid,
            "description": man.get("description") or "",
            "runtime": man.get("runtime") or "stub",
            "capabilities": list(man.get("capabilities") or []),
            "author": man.get("author") or "aos",
            "configSchema": man.get("configSchema") or {},
            "source": man.get("source") or "disk",
            "installed": mid in installed,
            "required": mid in (required or defaults),
        }
        for f in extra_fields:
            if f in man:
                row[f] = man[f]
        items.append(row)
    return {
        "items": items,
        "pluginsRoot": str(subdomain_root(subdir)),
    }
