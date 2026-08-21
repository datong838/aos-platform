from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[4]
    / "scripts/aip/audit_r12_ecommerce_logic_readiness_matrix.py"
)
SPEC = importlib.util.spec_from_file_location("audit_r12_logic_matrix", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

NOW = datetime(2026, 8, 21, 8, 0, tzinfo=timezone.utc)


def ref(asset_type: str, asset_id: str, revision: int = 1, content_hash: str = "hash"):
    return {
        "assetType": asset_type,
        "assetId": asset_id,
        "revision": revision,
        "contentHash": content_hash,
    }


def state(*, expiry: datetime | None = None, include_specialty: bool = True):
    expiry = expiry or NOW + timedelta(minutes=15)
    logics = [
        {"id": "D01", "agentId": "ecommerce.data_advisor", "capabilities": ["material.collect"]},
        {"id": "C01", "agentId": "ecommerce.content_officer", "capabilities": ["copy.generate"]},
    ]
    skills = []
    bindings = []
    capabilities = []
    graphs = {}
    publications = {}
    for short_id, agent_id, capability_id in (
        ("D01", "ecommerce.data_advisor", "material.collect"),
        ("C01", "ecommerce.content_officer", "copy.generate"),
    ):
        graph_id = f"ecommerce.logic.{short_id}"
        skill_id = f"ecommerce.skill.{short_id}"
        binding_id = f"{agent_id}.skill.{short_id}.r2"
        capability_binding_id = f"ecommerce.shared.{capability_id}.r1"
        graphs[graph_id] = {"revision": 1, "graph_hash": f"graph-{short_id}"}
        publications[graph_id] = {
            "graph_revision": 1,
            "graph_hash": f"graph-{short_id}",
        }
        skills.extend(
            [
                {"skillId": skill_id, "revision": 1, "lifecycle": "evaluated"},
                {
                    "skillId": skill_id,
                    "revision": 2,
                    "lifecycle": "published",
                    "canonicalLogicId": graph_id,
                    "logicRevisionRef": ref("LogicRevision", graph_id, 1, f"graph-{short_id}"),
                    "modelRouteRef": ref("ModelRouteRevision", "route"),
                    "runtimePolicyRef": ref("RuntimePolicyRevision", "policy"),
                    "releaseGateRef": ref("EvalGateDecision", f"gate-{short_id}"),
                    "requiredCapabilities": [capability_id],
                    "toolAllowlist": [],
                    "contentHash": f"skill-{short_id}",
                },
            ]
        )
        dependencies = {
            "modelRouteRef": ref("ModelRouteRevision", "route"),
            "runtimePolicyRef": ref("RuntimePolicyRevision", "policy"),
            "evalGateRef": ref("EvalGateDecision", f"gate-{short_id}"),
            "budgetPolicyRef": ref("BudgetPolicyRevision", "budget"),
        }
        bindings.append(
            {
                "bindingId": binding_id,
                "instanceId": f"{agent_id}.default",
                "skill": ref("SkillTemplate", skill_id, 2, f"skill-{short_id}"),
                "capabilityBindingIds": [capability_binding_id],
                "budgetPolicyRef": dependencies["budgetPolicyRef"],
                "dependencies": dependencies,
                "readiness": "available",
                "readinessExpiresAt": expiry.isoformat(),
                "status": "active",
                "version": 1,
            }
        )
        capabilities.append(
            {
                "bindingId": capability_binding_id,
                "capability": ref("CapabilityRevision", capability_id),
                "secretRef": "keychain://opaque-only",
                "dependencies": {
                    "providerRef": ref("ProviderInstanceRevision", "provider"),
                    **dependencies,
                },
                "operationalReadiness": "available",
                "readinessExpiresAt": expiry.isoformat(),
                "status": "active",
            }
        )
    if include_specialty:
        skills.append(
            {
                "skillId": "ecommerce.skill.V01",
                "revision": 2,
                "lifecycle": "published",
            }
        )
        bindings.append(
            {
                "bindingId": "ecommerce.content_officer.skill.V01.r2",
                "skill": ref("SkillTemplate", "ecommerce.skill.V01", 2, "specialty"),
            }
        )
    return {
        "catalog": {"logics": logics},
        "skills": skills,
        "runtime": {"skillBindings": bindings, "capabilityBindings": capabilities},
        "agents": [
            {"template": ref("AgentTemplate", "ecommerce.data_advisor"), "status": "active"},
            {"template": ref("AgentTemplate", "ecommerce.content_officer"), "status": "active"},
        ],
        "logic_graphs": graphs,
        "logic_publications": publications,
    }


def build(**overrides):
    payload = state()
    payload.update(overrides)
    return MODULE.build_matrix(**payload, now=NOW, expected_canonical_count=2)


def test_matrix_separates_canonical_revision_specialty_and_binding_counts():
    result = build()
    counts = result["countSemantics"]
    assert counts["canonicalLogicCount"] == 2
    assert counts["canonicalPublishedSkillCount"] == 2
    assert counts["specialtyPilotSkillIds"] == ["ecommerce.skill.V01"]
    assert counts["uniquePublishedSkillCount"] == 3
    assert counts["skillRevisionRowCount"] == 5
    assert counts["tenantSkillBindingRowCount"] == 3
    assert counts["canonicalSkillBindingCount"] == 2
    assert result["gates"]["staticAuthority37of37"] is True


def test_matrix_rejects_stored_available_after_ttl_expiry():
    payload = state(expiry=NOW - timedelta(seconds=1))
    result = MODULE.build_matrix(
        **payload, now=NOW, expected_canonical_count=2
    )
    assert result["gates"]["staticAuthority37of37"] is True
    assert result["gates"]["runtimeRunnable37of37"] is False
    assert all("STALE_READINESS_TTL" in row["blockers"] for row in result["rows"])
    assert any(
        blocker.startswith("STALE_READINESS_TTL:")
        for row in result["rows"]
        for blocker in row["blockers"]
    )


def test_matrix_fails_closed_on_exact_logic_and_capability_drift():
    payload = state()
    payload["skills"][1]["logicRevisionRef"]["contentHash"] = "drift"
    payload["runtime"]["skillBindings"][0]["capabilityBindingIds"] = []
    result = MODULE.build_matrix(
        **payload, now=NOW, expected_canonical_count=2
    )
    d01 = next(row for row in result["rows"] if row["logicId"] == "D01")
    assert "SKILL_EXACT_AUTHORITY_DRIFT" in d01["blockers"]
    assert "CAPABILITY_NOT_BOUND:material.collect" in d01["blockers"]
    assert d01["runnable"] is False


def test_matrix_never_renders_secret_reference_or_payload():
    result = build()
    rendered = str(result)
    assert "keychain://" not in rendered
    assert "secretRef" not in rendered
