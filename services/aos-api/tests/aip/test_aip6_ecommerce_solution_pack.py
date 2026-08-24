from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import yaml

from aos_api.aip_agent_registry_store import AipAgentRegistryStore
from aos_api.aip_capability_registry import AipCapabilityRegistry
from aos_api.aip_solution_pack_publisher import (
    AIP_DEFINITION_SOURCE_VERSION,
    AGENT_LOGIC_COUNTS,
    CAPABILITY_IDS,
    COMPATIBILITY_CLASSIFICATIONS,
    SOLUTION_PACK_ID,
    SOLUTION_PACK_VERSION,
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
    compatibility = load(
        "content/logic/ecommerce-37-skill-compatibility-map.json"
    )
    capabilities = load("content/agents/ecommerce-capability-catalog.json")[
        "capabilities"
    ]
    assert manifest["metadata"]["id"] == SOLUTION_PACK_ID
    assert manifest["metadata"]["version"] == SOLUTION_PACK_VERSION
    assert tuple(manifest["spec"]["capabilities"]["provides"]) == CAPABILITY_IDS
    assert {item["id"] for item in agents} == set(AGENT_LOGIC_COUNTS)
    assert len(logics) == 37 == len({item["id"] for item in logics})
    assert compatibility["compatibilityMode"] == "retain_exact_legacy"
    assert compatibility["publicationStatus"] == "planned_not_published"
    assert [item["legacyLogicId"] for item in compatibility["entries"]] == [
        item["id"] for item in logics
    ]
    assert {
        item["classification"] for item in compatibility["entries"]
    } <= COMPATIBILITY_CLASSIFICATIONS
    assert tuple(item["id"] for item in capabilities) == CAPABILITY_IDS
    assert sum(len(item["logicIds"]) for item in agents) == 37
    assert "title.generate" in {
        alias for item in capabilities for alias in item["aliases"]
    }
    assert "production.coordination" not in {item["id"] for item in agents}
    assert not (BUNDLE / "content/agents/placeholder.json").exists()
    assert not (BUNDLE / "content/logic/placeholder.json").exists()
    assert (BUNDLE / "content/workshops/w03-customer-private-domain.json").is_file()
    templates = load(
        "content/workshops/ecommerce-analyst-query-templates.json"
    )["templates"]
    assert len(templates) == 6
    assert {item["roleId"] for item in templates} == set(AGENT_LOGIC_COUNTS)
    assert all(item["policy"] == "canonical-read-only" for item in templates)
    assert (BUNDLE / "content/logic/l05-commission-anomaly.json").is_file()
    assert (BUNDLE / "content/evals/w03-l05-dry-run-cases.json").is_file()


def test_solution_pack_rejects_manifest_version_drift_before_publication(tmp_path):
    copied = tmp_path / "ecommerce-growth"
    shutil.copytree(BUNDLE, copied)
    manifest_path = copied / "bundle.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["metadata"]["version"] = "1.2.0"
    manifest_path.write_text(
        yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    with pytest.raises(AipSolutionPackInvalid, match="identity or version"):
        AipSolutionPackPublisher().publish(copied, actor="pytest-version-drift")


def test_solution_pack_publisher_exactly_reads_back_6_37_10_and_is_idempotent():
    publisher = AipSolutionPackPublisher()
    first = publisher.publish(BUNDLE, actor="pytest-a6e")
    second = publisher.publish(BUNDLE, actor="pytest-a6e")
    assert first == second
    assert first.bundle_version == SOLUTION_PACK_VERSION
    assert (first.agent_count, first.skill_count, first.capability_count) == (6, 37, 10)

    agents = AipAgentRegistryStore()
    skills = AipSkillRegistry()
    capabilities = AipCapabilityRegistry()
    for ref in first.agent_refs:
        revision = agents.get_template(ref.asset_id, ref.revision)
        assert revision.source_ref.revision == AIP_DEFINITION_SOURCE_VERSION
        assert revision.content_hash == ref.content_hash
        assert revision.lifecycle.value == "published"
        assert revision.manifest["runtimeReadiness"] == "blocked"
    for ref in first.skill_refs:
        revision = skills.get_skill(ref.asset_id, ref.revision)
        assert revision.source_ref.revision == AIP_DEFINITION_SOURCE_VERSION
        assert revision.content_hash == ref.content_hash
        assert revision.lifecycle.value == "evaluated"
    for ref in first.capability_refs:
        revision = capabilities.get(ref.asset_id, ref.revision)
        assert revision.source_ref.revision == AIP_DEFINITION_SOURCE_VERSION
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


def test_solution_pack_rejects_compatibility_identity_drift_before_publication(
    tmp_path,
):
    candidate = tmp_path / "ecommerce-growth"
    shutil.copytree(BUNDLE, candidate)
    path = candidate / "content/logic/ecommerce-37-skill-compatibility-map.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["entries"][0]["legacySkillRef"] = "ecommerce.skill.renamed"
    path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(AipSolutionPackInvalid, match="entry for D01"):
        AipSolutionPackPublisher().publish(candidate, actor="pytest-compat-drift")


def test_legacy_release_without_s2_5_map_keeps_6_37_10_publication_contract(
    tmp_path,
):
    candidate = tmp_path / "ecommerce-growth"
    shutil.copytree(BUNDLE, candidate)
    (candidate / "content/logic/ecommerce-37-skill-compatibility-map.json").unlink()

    result = AipSolutionPackPublisher().publish(
        candidate, actor="pytest-legacy-release-compatibility"
    )

    assert (result.agent_count, result.skill_count, result.capability_count) == (
        6,
        37,
        10,
    )


def test_solution_pack_rejects_analyst_template_role_drift(tmp_path):
    candidate = tmp_path / "ecommerce-growth"
    shutil.copytree(BUNDLE, candidate)
    path = candidate / "content/workshops/ecommerce-analyst-query-templates.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["templates"][0]["roleId"] = "ecommerce.unknown"
    path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(AipSolutionPackInvalid, match="crosswalk"):
        AipSolutionPackPublisher().publish(candidate, actor="pytest-template-drift")
