"""Action Type template plugin registry — scheme 99 · 对齐 20 §3.1."""
from __future__ import annotations

import json
from typing import Any

from aos_api import plugin_disk
from aos_api.db import connect
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.action_template_registry")

KEY = "action_plugin_installs"
SUBDIR = "actions"
DEFAULTS = ("close-work-order", "update-wiki-card")
REQUIRED = DEFAULTS


def list_action_plugins() -> dict[str, Any]:
    body = plugin_disk.list_domain(
        SUBDIR,
        KEY,
        defaults=DEFAULTS,
        required=REQUIRED,
        extra_fields=(
            "actionTypeId",
            "objectType",
            "parameters",
            "requiredMarkings",
            "submissionCriteria",
        ),
    )
    for it in body.get("items") or []:
        if not it.get("actionTypeId"):
            it["actionTypeId"] = it["id"]
    return body


def _template_from_manifest(man: dict[str, Any]) -> dict[str, Any]:
    action_type_id = str(man.get("actionTypeId") or man.get("id") or "")
    return {
        "id": action_type_id,
        "name": str(man.get("nameZh") or man.get("name") or action_type_id),
        "objectType": str(man.get("objectType") or "WorkOrder"),
        "parameters": list(man.get("parameters") or []),
        "requiredMarkings": list(man.get("requiredMarkings") or ["public"]),
        "submissionCriteria": list(man.get("submissionCriteria") or []),
        "pluginId": str(man.get("id") or ""),
    }


def upsert_action_type(tpl: dict[str, Any], *, force: bool = False) -> None:
    """将插件模板写入 DB。默认不覆盖已有自定义 name/parameters（仅补空 criteria）。"""
    with connect() as conn:
        if force:
            conn.execute(
                """
                INSERT INTO meta_action_type
                  (id, name, object_type, parameters, required_markings, submission_criteria)
                VALUES (%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb)
                ON CONFLICT (id) DO UPDATE SET
                  name = EXCLUDED.name,
                  object_type = EXCLUDED.object_type,
                  parameters = EXCLUDED.parameters,
                  required_markings = EXCLUDED.required_markings,
                  submission_criteria = EXCLUDED.submission_criteria
                """,
                (
                    tpl["id"],
                    tpl["name"],
                    tpl["objectType"],
                    json.dumps(tpl["parameters"]),
                    json.dumps(tpl["requiredMarkings"]),
                    json.dumps(tpl["submissionCriteria"]),
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO meta_action_type
                  (id, name, object_type, parameters, required_markings, submission_criteria)
                VALUES (%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb)
                ON CONFLICT (id) DO UPDATE SET
                  submission_criteria = CASE
                    WHEN meta_action_type.submission_criteria IS NULL
                      OR meta_action_type.submission_criteria = '[]'::jsonb
                    THEN EXCLUDED.submission_criteria
                    ELSE meta_action_type.submission_criteria
                  END
                """,
                (
                    tpl["id"],
                    tpl["name"],
                    tpl["objectType"],
                    json.dumps(tpl["parameters"]),
                    json.dumps(tpl["requiredMarkings"]),
                    json.dumps(tpl["submissionCriteria"]),
                ),
            )
        conn.commit()


def seed_installed_action_types() -> list[str]:
    """将已安装 Action 插件模板 upsert 进 meta_action_type（不覆盖用户改过的字段）。"""
    body = list_action_plugins()
    seeded: list[str] = []
    by_id = {str(m["id"]): m for m in plugin_disk.scan_disk(SUBDIR)}
    for it in body.get("items") or []:
        if not it.get("installed"):
            continue
        man = by_id.get(str(it["id"]))
        if not man:
            continue
        tpl = _template_from_manifest(man)
        if not tpl["id"]:
            continue
        upsert_action_type(tpl, force=False)
        seeded.append(tpl["id"])
    log.info("action_templates_seeded count=%s ids=%s", len(seeded), seeded)
    return seeded


def install_plugin(plugin_id: str) -> dict[str, Any]:
    result = plugin_disk.install(SUBDIR, KEY, plugin_id, DEFAULTS)
    by_id = {str(m["id"]): m for m in plugin_disk.scan_disk(SUBDIR)}
    man = by_id.get(plugin_id)
    if man:
        upsert_action_type(_template_from_manifest(man), force=True)
        result["actionTypeId"] = man.get("actionTypeId") or man.get("id")
    return result


def uninstall_plugin(plugin_id: str) -> dict[str, Any]:
    """仅卸安装态；不删 DB 中已有 Action Type（防破坏 Draft）。"""
    return plugin_disk.uninstall(
        SUBDIR, KEY, plugin_id, defaults=DEFAULTS, required=REQUIRED
    )
