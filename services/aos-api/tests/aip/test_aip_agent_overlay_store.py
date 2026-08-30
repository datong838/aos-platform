"""Versioned AgentInstance prompt/tools overlay store (G8b)."""

from __future__ import annotations

import uuid

import pytest
from aos_api.aip_agent_overlay_store import AipAgentOverlayStore
from aos_api.aip_agent_registry_store import AipAgentRegistryConflict, AipAgentRegistryNotFound, AipAgentRegistryStore
from aos_api.tenant_scope import TenantScope

PRIMARY = TenantScope("org-org", "dev-project")
CANARY = TenantScope("dev-org", "dev-project")


@pytest.fixture()
def instance_id() -> str:
    """Reuse an existing ecommerce instance when present; else skip."""
    store = AipAgentRegistryStore()
    try:
        items = store.list_instances(PRIMARY, limit=5)
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"agent registry unavailable: {exc}")
    if not items:
        pytest.skip("no agent instances in org-org/dev-project")
    return items[0].instance_id


def test_overlay_empty_then_prompt_roundtrip(instance_id: str):
    overlay = AipAgentOverlayStore()
    marker = f"overlay-test-{uuid.uuid4().hex[:8]}"
    empty = overlay.get_prompt(PRIMARY, instance_id)
    assert empty["agent_id"] == instance_id
    assert isinstance(empty["prompt"], str)
    written = overlay.put_prompt(
        PRIMARY, instance_id, prompt=marker, actor="pytest-overlay", expected_revision=empty["revision"]
    )
    assert written["ok"] is True
    assert written["prompt"] == marker
    assert written["revision"] == empty["revision"] + 1
    assert len(written["content_hash"]) == 64
    with pytest.raises(AipAgentRegistryConflict):
        overlay.put_prompt(
            PRIMARY,
            instance_id,
            prompt=f"{marker}-stale",
            actor="pytest-overlay",
            expected_revision=empty["revision"],
        )
    reread = overlay.get_prompt(PRIMARY, instance_id)
    assert reread["prompt"] == marker
    agents = AipAgentRegistryStore()
    instance = agents.get_instance(PRIMARY, instance_id)
    assert instance.overlay.prompt_revision is not None


def test_overlay_tools_roundtrip(instance_id: str):
    overlay = AipAgentOverlayStore()
    items = [
        {
            "id": f"tool.{uuid.uuid4().hex[:6]}",
            "name": "Probe",
            "category": "tool",
            "enabled": True,
        }
    ]
    written = overlay.put_tools(
        PRIMARY, instance_id, items=items, actor="pytest-overlay"
    )
    assert written["items"] == items
    assert overlay.get_tools(PRIMARY, instance_id)["items"] == items


def test_overlay_guardrails_roundtrip(instance_id: str):
    overlay = AipAgentOverlayStore()
    items = [{"id": "no_fs_write", "name": "禁止写文件系统", "enabled": True}]
    written = overlay.put_guardrails(
        PRIMARY, instance_id, items=items, actor="pytest-overlay"
    )
    assert written["items"] == items
    assert overlay.get_guardrails(PRIMARY, instance_id)["items"] == items
    agents = AipAgentRegistryStore()
    instance = agents.get_instance(PRIMARY, instance_id)
    assert instance.overlay.policy_revision is not None


def test_overlay_missing_instance_404():
    overlay = AipAgentOverlayStore()
    with pytest.raises(AipAgentRegistryNotFound):
        overlay.get_prompt(PRIMARY, f"missing.{uuid.uuid4().hex}")


def test_overlay_tenant_isolation(instance_id: str):
    overlay = AipAgentOverlayStore()
    marker = f"primary-only-{uuid.uuid4().hex[:8]}"
    overlay.put_prompt(PRIMARY, instance_id, prompt=marker, actor="pytest-overlay")
    with pytest.raises(AipAgentRegistryNotFound):
        overlay.get_prompt(CANARY, instance_id)
