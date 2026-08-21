"""Tenant-scoped versioned AgentInstance prompt/tools/guardrails overlay authority."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from aos_api.aip_agent_registry_store import (
    AipAgentRegistryConflict,
    AipAgentRegistryNotFound,
    AipAgentRegistryStore,
)
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope, apply_transaction_scope

ConnectFactory = Callable[..., AbstractContextManager[Any]]


@dataclass(frozen=True, slots=True)
class OverlaySnapshot:
    instance_id: str
    revision: int | None
    prompt: str
    tools: list[dict[str, Any]]
    guardrails: list[dict[str, Any]]
    content_hash: str | None


class AipAgentOverlayStore:
    def __init__(
        self,
        *,
        connect_factory: ConnectFactory | None = None,
        agents: AipAgentRegistryStore | None = None,
    ) -> None:
        self._connect_factory = connect_factory or db_connect
        self._agents = agents or AipAgentRegistryStore(connect_factory=self._connect_factory)

    def get_prompt(self, scope: TenantScope, instance_id: str) -> dict[str, Any]:
        snap = self._read(scope, instance_id)
        return {"agent_id": instance_id, "prompt": snap.prompt}

    def put_prompt(
        self, scope: TenantScope, instance_id: str, *, prompt: str, actor: str
    ) -> dict[str, Any]:
        cleaned = str(prompt or "")
        if len(cleaned) > 8000:
            raise ValueError("prompt exceeds 8000 characters")
        snap = self._write(
            scope, instance_id, prompt=cleaned, tools=None, guardrails=None, actor=actor
        )
        return {"ok": True, "agent_id": instance_id, "prompt": snap.prompt}

    def get_tools(self, scope: TenantScope, instance_id: str) -> dict[str, Any]:
        snap = self._read(scope, instance_id)
        return {"agent_id": instance_id, "items": snap.tools}

    def put_tools(
        self,
        scope: TenantScope,
        instance_id: str,
        *,
        items: list[dict[str, Any]],
        actor: str,
    ) -> dict[str, Any]:
        normalized = _normalize_tools(items)
        snap = self._write(
            scope, instance_id, prompt=None, tools=normalized, guardrails=None, actor=actor
        )
        return {"agent_id": instance_id, "items": snap.tools}

    def get_guardrails(self, scope: TenantScope, instance_id: str) -> dict[str, Any]:
        snap = self._read(scope, instance_id)
        return {"agent_id": instance_id, "items": snap.guardrails}

    def put_guardrails(
        self,
        scope: TenantScope,
        instance_id: str,
        *,
        items: list[dict[str, Any]],
        actor: str,
    ) -> dict[str, Any]:
        normalized = _normalize_guardrails(items)
        snap = self._write(
            scope, instance_id, prompt=None, tools=None, guardrails=normalized, actor=actor
        )
        return {"agent_id": instance_id, "items": snap.guardrails}

    def _require_instance(self, scope: TenantScope, instance_id: str) -> None:
        try:
            self._agents.get_instance(scope, instance_id)
        except AipAgentRegistryNotFound:
            raise
        except Exception as exc:  # pragma: no cover - store shapes vary in unit fixtures
            if "not found" in str(exc).lower():
                raise AipAgentRegistryNotFound("agent instance not found") from exc
            raise

    def _read(self, scope: TenantScope, instance_id: str) -> OverlaySnapshot:
        checked = instance_id.strip()
        if not checked:
            raise AipAgentRegistryNotFound("agent instance not found")
        self._require_instance(scope, checked)
        with self._connect_factory() as conn:
            apply_transaction_scope(conn, scope)
            row = conn.execute(
                """
                SELECT revision, prompt, tools_json, guardrails_json, content_hash
                  FROM aip_agent_instance_overlay_revision
                 WHERE org_id=%s AND project_id=%s AND instance_id=%s
                 ORDER BY revision DESC
                 LIMIT 1
                """,
                (*scope.key, checked),
            ).fetchone()
            if row is None:
                return OverlaySnapshot(
                    instance_id=checked,
                    revision=None,
                    prompt="",
                    tools=[],
                    guardrails=[],
                    content_hash=None,
                )
            return OverlaySnapshot(
                instance_id=checked,
                revision=int(row["revision"]),
                prompt=str(row["prompt"] or ""),
                tools=_as_list(row["tools_json"]),
                guardrails=_as_list(row.get("guardrails_json")),
                content_hash=str(row["content_hash"]),
            )

    def _write(
        self,
        scope: TenantScope,
        instance_id: str,
        *,
        prompt: str | None,
        tools: list[dict[str, Any]] | None,
        guardrails: list[dict[str, Any]] | None,
        actor: str,
    ) -> OverlaySnapshot:
        checked = instance_id.strip()
        if not checked or not actor.strip():
            raise ValueError("instance_id and actor are required")
        self._require_instance(scope, checked)
        with self._connect_factory() as conn:
            apply_transaction_scope(conn, scope)
            current = conn.execute(
                """
                SELECT revision, prompt, tools_json, guardrails_json
                  FROM aip_agent_instance_overlay_revision
                 WHERE org_id=%s AND project_id=%s AND instance_id=%s
                 ORDER BY revision DESC
                 LIMIT 1
                """,
                (*scope.key, checked),
            ).fetchone()
            next_revision = int(current["revision"]) + 1 if current else 1
            next_prompt = (
                prompt
                if prompt is not None
                else (str(current["prompt"]) if current else "")
            )
            if tools is not None:
                next_tools = tools
            elif current is None:
                next_tools = []
            else:
                next_tools = _as_list(current["tools_json"])
            if guardrails is not None:
                next_guardrails = guardrails
            elif current is None:
                next_guardrails = []
            else:
                next_guardrails = _as_list(current.get("guardrails_json"))
            payload = {
                "prompt": next_prompt,
                "tools": next_tools,
                "guardrails": next_guardrails,
            }
            content_hash = hashlib.sha256(
                json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            occurred = datetime.now(UTC)
            conn.execute(
                """
                INSERT INTO aip_agent_instance_overlay_revision
                  (org_id, project_id, instance_id, revision, prompt, tools_json,
                   guardrails_json, content_hash, created_by, created_at)
                VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s)
                """,
                (
                    *scope.key,
                    checked,
                    next_revision,
                    next_prompt,
                    json.dumps(next_tools, ensure_ascii=False),
                    json.dumps(next_guardrails, ensure_ascii=False),
                    content_hash,
                    actor.strip(),
                    occurred,
                ),
            )
            row = conn.execute(
                """
                SELECT overlay, version FROM aip_agent_instance
                 WHERE org_id=%s AND project_id=%s AND instance_id=%s
                 FOR UPDATE
                """,
                (*scope.key, checked),
            ).fetchone()
            if row is None:
                raise AipAgentRegistryNotFound("agent instance not found")
            overlay = row["overlay"]
            if isinstance(overlay, str):
                overlay = json.loads(overlay)
            overlay = dict(overlay or {})
            overlay["promptRevision"] = str(next_revision)
            overlay["policyRevision"] = str(next_revision)
            updated = conn.execute(
                """
                UPDATE aip_agent_instance
                   SET overlay=%s::jsonb, version=%s, updated_at=%s
                 WHERE org_id=%s AND project_id=%s AND instance_id=%s AND version=%s
                """,
                (
                    json.dumps(overlay, ensure_ascii=False),
                    int(row["version"]) + 1,
                    occurred,
                    *scope.key,
                    checked,
                    int(row["version"]),
                ),
            )
            if getattr(updated, "rowcount", 1) == 0:
                raise AipAgentRegistryConflict("agent instance overlay version conflict")
            conn.commit()
            return OverlaySnapshot(
                instance_id=checked,
                revision=next_revision,
                prompt=next_prompt,
                tools=next_tools,
                guardrails=next_guardrails,
                content_hash=content_hash,
            )


def _as_list(raw: Any) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if isinstance(raw, str):
        raw = json.loads(raw)
    return list(raw or [])


def _normalize_tools(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in items or []:
        tool_id = str(raw.get("id") or "").strip()
        if not tool_id or tool_id in seen:
            continue
        seen.add(tool_id)
        out.append(
            {
                "id": tool_id,
                "name": str(raw.get("name") or tool_id),
                "category": str(raw.get("category") or "tool"),
                "enabled": bool(raw.get("enabled", True)),
            }
        )
    return out


def _normalize_guardrails(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in items or []:
        rule_id = str(raw.get("id") or "").strip()
        if not rule_id or rule_id in seen:
            continue
        seen.add(rule_id)
        out.append(
            {
                "id": rule_id,
                "name": str(raw.get("name") or rule_id),
                "enabled": bool(raw.get("enabled", True)),
            }
        )
    return out
