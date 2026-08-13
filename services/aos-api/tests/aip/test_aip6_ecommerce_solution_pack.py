from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import yaml

from aos_api.aip_agent_registry_store import AipAgentRegistryStore
from aos_api.aip_capability_registry import AipCapabilityRegistry
from aos_api.aip_solution_pack_publisher import (
    AGENT_LOGIC_COUNTS,
    CAPABILITY_IDS,
    AipSolutionPackInvalid,
    AipSolutionPackPublisher,
)
from aos_api.aip_skill_registry import AipSkillRegistry
from aos_api.db import connect

REPO_ROOT = Path(__file__).resolve().parents[4]
BUNDLE = REPO_ROOT / "bundles/solutions/ecommerce-growth"


def load(relative_path: str):
    return json.loads((BUNDLE / relative_path).read_text(encoding="utf-8"))


def test_ecommerce_solution_pack_contains_exact_w0a_catalog_and_keeps_d3_assets():
    manifest = yaml.safe_load((BUNDLE / "bundle.yaml").read_text(encoding="utf-8"))
    agents = load("content/agents/ecommerce-six-coworkers.json")["agents"]
    logics = load("content/logic/ecommerce-37-logic-catalog.json")["logics"]
    capabilities = load("content/agents/ecommerce-capability-catalog.json")[
        "capabilities"
    ]
    assert manifest["metadata"]["version"] == "1.2.0"
    assert tuple(manifest["spec"]["capabilities"]["provides"]) == CAPABILITY_IDS
    assert {item["id"] for item in agents} == set(AGENT_LOGIC_COUNTS)
    assert len(logics) == 37 == len({item["id"] for item in logics})
    assert tuple(item["id"] for item in capabilities) == CAPABILITY_IDS
    assert sum(len(item["logicIds"]) for item in agents) == 37
    assert "title.generate" in {
        alias for item in capabilities for alias in item["aliases"]
    }
    assert "production.coordination" not in {item["id"] for item in agents}
    assert not (BUNDLE / "content/agents/placeholder.json").exists()
    assert not (BUNDLE / "content/logic/placeholder.json").exists()
    assert (BUNDLE / "content/workshops/w03-customer-private-domain.json").is_file()
    assert (BUNDLE / "content/logic/l05-commission-anomaly.json").is_file()
    assert (BUNDLE / "content/evals/w03-l05-dry-run-cases.json").is_file()


def test_solution_pack_publisher_exactly_reads_back_6_37_10_and_is_idempotent():
    publisher = AipSolutionPackPublisher()
    first = publisher.publish(BUNDLE, actor="pytest-a6e")
    second = publisher.publish(BUNDLE, actor="pytest-a6e")
    assert first == second
    assert (first.agent_count, first.skill_count, first.capability_count) == (6, 37, 10)

    agents = AipAgentRegistryStore()
    skills = AipSkillRegistry()
    capabilities = AipCapabilityRegistry()
    for ref in first.agent_refs:
        revision = agents.get_template(ref.asset_id, ref.revision)
        assert revision.content_hash == ref.content_hash
        assert revision.lifecycle.value == "published"
        assert revision.manifest["runtimeReadiness"] == "blocked"
    for ref in first.skill_refs:
        revision = skills.get_skill(ref.asset_id, ref.revision)
        assert revision.content_hash == ref.content_hash
        assert revision.lifecycle.value == "evaluated"
    for ref in first.capability_refs:
        revision = capabilities.get(ref.asset_id, ref.revision)
        assert revision.content_hash == ref.content_hash
        assert revision.lifecycle.value == "published"
        assert revision.readiness.value == "blocked"
    assert capabilities.resolve_alias("title.generate").capability_id == "copy.generate"


def test_solution_pack_publication_does_not_create_tenant_runtime_rows():
    tables = (
        "aip_agent_instance",
        "aip_skill_binding",
        "aip_capability_binding",
        "aip_agent_run",
        "aip_handoff_envelope",
    )
    with connect() as conn:
        before = {
            table: conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"]
            for table in tables
        }
    AipSolutionPackPublisher().publish(BUNDLE, actor="pytest-zero-side-effect")
    with connect() as conn:
        after = {
            table: conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"]
            for table in tables
        }
    assert after == before


def test_solution_pack_rejects_crosswalk_drift_before_any_publication(tmp_path):
    candidate = tmp_path / "ecommerce-growth"
    shutil.copytree(BUNDLE, candidate)
    catalog_path = candidate / "content/logic/ecommerce-37-logic-catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog["logics"][0]["capabilities"] = ["unknown.capability"]
    catalog_path.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    with pytest.raises(AipSolutionPackInvalid, match="unknown capability"):
        AipSolutionPackPublisher().publish(candidate, actor="pytest-invalid")
