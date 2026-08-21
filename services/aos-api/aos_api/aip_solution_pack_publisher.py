"""Publish strict AIP-6 definitions from a non-executable SolutionPack."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from aos_api.aip_agent_registry_contracts import (
    PublishAgentTemplateRequest,
    PublishCapabilityRevisionRequest,
    PublishSkillTemplateRequest,
    VersionedAssetRef,
)
from aos_api.aip_agent_registry_store import AipAgentRegistryStore
from aos_api.aip_capability_registry import AipCapabilityRegistry
from aos_api.aip_contracts import ResourceRef
from aos_api.aip_skill_registry import AipSkillRegistry

CAPABILITY_IDS = (
    "material.collect",
    "strategy.plan",
    "copy.generate",
    "script.compose",
    "speech.synthesize",
    "video.compose",
    "content.review",
    "live.orchestrate",
    "platform.adapt",
    "performance.review",
)
AGENT_LOGIC_COUNTS = {
    "ecommerce.data_advisor": 6,
    "ecommerce.content_officer": 8,
    "ecommerce.shopping_advisor": 6,
    "ecommerce.customer_service": 6,
    "ecommerce.private_domain_manager": 5,
    "ecommerce.campaign_planner": 6,
}
LOGIC_IDS = (
    *(f"D{i:02d}" for i in range(1, 7)),
    *(f"C{i:02d}" for i in range(1, 9)),
    *(f"G{i:02d}" for i in range(1, 7)),
    *(f"S{i:02d}" for i in range(1, 7)),
    *(f"P{i:02d}" for i in range(1, 6)),
    *(f"A{i:02d}" for i in range(1, 7)),
)
SOLUTION_PACK_ID = "solution.ecommerce.growth"
SOLUTION_PACK_VERSION = "1.3.0"
AIP_DEFINITION_SOURCE_VERSION = "1.2.0"


@dataclass(frozen=True, slots=True)
class SolutionPackPublication:
    bundle_id: str
    bundle_version: str
    agent_count: int
    skill_count: int
    capability_count: int
    agent_refs: tuple[VersionedAssetRef, ...]
    skill_refs: tuple[VersionedAssetRef, ...]
    capability_refs: tuple[VersionedAssetRef, ...]


class AipSolutionPackInvalid(ValueError):
    pass


class AipSolutionPackPublisher:
    def __init__(
        self,
        *,
        agent_store: AipAgentRegistryStore | None = None,
        skill_store: AipSkillRegistry | None = None,
        capability_store: AipCapabilityRegistry | None = None,
    ) -> None:
        self._agents = agent_store or AipAgentRegistryStore()
        self._skills = skill_store or AipSkillRegistry()
        self._capabilities = capability_store or AipCapabilityRegistry()

    def publish(self, bundle_dir: Path, *, actor: str) -> SolutionPackPublication:
        if not actor.strip():
            raise ValueError("actor is required")
        root = bundle_dir.resolve(strict=True)
        manifest = self._yaml(root / "bundle.yaml")
        metadata = manifest.get("metadata")
        if not isinstance(metadata, dict):
            raise AipSolutionPackInvalid("bundle metadata is required")
        bundle_id = metadata.get("id")
        bundle_version = metadata.get("version")
        if bundle_id != SOLUTION_PACK_ID or bundle_version != SOLUTION_PACK_VERSION:
            raise AipSolutionPackInvalid("unsupported solution pack identity or version")

        agent_document = self._json(root / "content/agents/ecommerce-six-coworkers.json")
        logic_document = self._json(root / "content/logic/ecommerce-37-logic-catalog.json")
        capability_document = self._json(root / "content/agents/ecommerce-capability-catalog.json")
        schema_path = root / "content/schemas/aip6-contribution-schemas.json"
        policy_path = root / "content/policies/aip6-runtime-policies.json"
        schema_document = self._json(schema_path)
        policy_document = self._json(policy_path)
        analyst_templates = self._json(
            root / "content/workshops/ecommerce-analyst-query-templates.json"
        )
        agents = self._list(agent_document, "agents")
        logics = self._list(logic_document, "logics")
        capabilities = self._list(capability_document, "capabilities")
        self._validate(agents, logics, capabilities, manifest)
        self._validate_analyst_templates(analyst_templates, agents)
        schema_names = schema_document.get("schemas")
        if (
            not isinstance(schema_names, list)
            or len(schema_names) != len(set(schema_names))
            or any(not isinstance(item, str) or not item.strip() for item in schema_names)
        ):
            raise AipSolutionPackInvalid("schema names must be unique non-empty strings")
        referenced_schemas = {
            name
            for item in capabilities
            for name in (item["inputSchema"], item["outputSchema"])
        } | {"EffectReviewRef"}
        if not referenced_schemas <= set(schema_names):
            raise AipSolutionPackInvalid("capability references an unknown schema")

        source = ResourceRef(
            resource_type="SolutionPack",
            resource_id=bundle_id,
            revision=AIP_DEFINITION_SOURCE_VERSION,
            authority="asset-registry",
        )
        schema_hash = self._file_hash(schema_path)
        policy_hash = self._file_hash(policy_path)
        policy_artifacts = self._list(policy_document, "artifacts")
        policy_types = [item.get("assetType") for item in policy_artifacts]
        required_policy_types = {
            "MemoryPolicy",
            "HandoffPolicy",
            "EffectReviewSchema",
            "LicensePolicy",
            "ReadinessPolicy",
            "ResponsibilityPolicy",
        }
        if set(policy_types) != required_policy_types or len(policy_types) != len(
            required_policy_types
        ):
            raise AipSolutionPackInvalid("runtime policy artifact types are incomplete")
        policy_refs = {
            item["assetType"]: self._asset(
                item["assetType"], item["id"], policy_hash
            )
            for item in policy_artifacts
        }
        schema_contract = schema_document.get("contract")
        if not isinstance(schema_contract, dict):
            raise AipSolutionPackInvalid("schema contract must be an object")

        capability_refs = []
        for item in capabilities:
            capability_payload = dict(
                capability_id=item["id"],
                revision=1,
                display_name=item["displayName"],
                lifecycle="published",
                aliases=item["aliases"],
                input_schema_ref=self._asset(
                    "SchemaRevision", item["inputSchema"], schema_hash
                ),
                output_schema_ref=self._asset(
                    "SchemaRevision", item["outputSchema"], schema_hash
                ),
                risk_level=item["risk"],
                required_data_refs=[],
                required_tool_refs=[],
                required_capability_refs=[],
                memory_policy_ref=policy_refs["MemoryPolicy"],
                handoff_policy_ref=policy_refs["HandoffPolicy"],
                effect_review_schema_ref=self._asset(
                    "SchemaRevision", "EffectReviewRef", schema_hash
                ),
                license_policy_ref=policy_refs["LicensePolicy"],
                readiness_policy_ref=policy_refs["ReadinessPolicy"],
                readiness=capability_document["readiness"],
                readiness_reasons=capability_document["readinessReasons"],
                source_ref=source,
                source_license=metadata["license"],
            )
            request = PublishCapabilityRevisionRequest(
                **capability_payload,
                content_hash=self._hash(capability_payload),
            )
            revision = self._capabilities.publish(request, actor=actor)
            capability_refs.append(
                self._asset(
                    "CapabilityRevision",
                    revision.capability_id,
                    revision.content_hash,
                )
            )

        agent_refs = []
        for item in agents:
            agent_manifest = {
                **item,
                "runtimeReadiness": agent_document["runtimeReadiness"],
                "blockers": agent_document["blockers"],
            }
            agent_payload = dict(
                template_id=item["id"],
                revision=1,
                display_name=item["displayName"],
                role_key=item["roleKey"],
                lifecycle="published",
                source_ref=source,
                source_license=metadata["license"],
                manifest=agent_manifest,
            )
            request = PublishAgentTemplateRequest(
                **agent_payload,
                content_hash=self._hash(agent_payload),
            )
            revision = self._agents.publish_template(request, actor=actor)
            agent_refs.append(
                self._asset(
                    "AgentTemplate", revision.template_id, revision.content_hash
                )
            )

        skill_refs = []
        for item in logics:
            skill_payload = dict(
                skill_id=f"ecommerce.skill.{item['id']}",
                revision=1,
                canonical_logic_id=f"ecommerce.logic.{item['id']}",
                lifecycle=logic_document["lifecycle"],
                input_schema=schema_contract,
                output_schema=schema_contract,
                tool_allowlist=[],
                required_capabilities=item["capabilities"],
                risk_level=item["risk"],
                memory_policy_ref=policy_refs["MemoryPolicy"],
                handoff_policy_ref=policy_refs["HandoffPolicy"],
                source_ref=source,
                source_license=metadata["license"],
            )
            request = PublishSkillTemplateRequest(
                **skill_payload,
                content_hash=self._hash(skill_payload),
            )
            revision = self._skills.publish_skill(request, actor=actor)
            skill_refs.append(
                self._asset("SkillTemplate", revision.skill_id, revision.content_hash)
            )

        return SolutionPackPublication(
            bundle_id=bundle_id,
            bundle_version=bundle_version,
            agent_count=len(agent_refs),
            skill_count=len(skill_refs),
            capability_count=len(capability_refs),
            agent_refs=tuple(agent_refs),
            skill_refs=tuple(skill_refs),
            capability_refs=tuple(capability_refs),
        )

    @classmethod
    def _validate(
        cls,
        agents: list[dict[str, Any]],
        logics: list[dict[str, Any]],
        capabilities: list[dict[str, Any]],
        manifest: dict[str, Any],
    ) -> None:
        cls._require_keys(
            agents,
            {"id", "displayName", "roleKey", "logicIds", "responsibility"},
            "agent",
        )
        cls._require_keys(
            logics,
            {"id", "name", "agentId", "capabilities", "risk"},
            "logic",
        )
        cls._require_keys(
            capabilities,
            {"id", "displayName", "inputSchema", "outputSchema", "risk", "aliases"},
            "capability",
        )
        agent_ids = [item.get("id") for item in agents]
        logic_ids = [item.get("id") for item in logics]
        capability_ids = [item.get("id") for item in capabilities]
        if len(agent_ids) != 6 or len(set(agent_ids)) != 6:
            raise AipSolutionPackInvalid("exactly six unique agents are required")
        if set(agent_ids) != set(AGENT_LOGIC_COUNTS):
            raise AipSolutionPackInvalid("agent ids differ from the W0A catalog")
        if len(logic_ids) != 37 or len(set(logic_ids)) != 37:
            raise AipSolutionPackInvalid("exactly 37 unique logic ids are required")
        if set(logic_ids) != set(LOGIC_IDS):
            raise AipSolutionPackInvalid("logic ids differ from the W0A crosswalk")
        if tuple(capability_ids) != CAPABILITY_IDS:
            raise AipSolutionPackInvalid("capability ids differ from the W0A catalog")
        aliases = [alias for item in capabilities for alias in item.get("aliases", [])]
        if len(aliases) != len(set(aliases)) or set(aliases) & set(CAPABILITY_IDS):
            raise AipSolutionPackInvalid("capability aliases collide")
        if "title.generate" not in aliases or "production.coordination" in agent_ids:
            raise AipSolutionPackInvalid("W0A alias or coordinator ownership drifted")
        by_agent = {agent_id: set() for agent_id in agent_ids}
        for item in logics:
            agent_id = item.get("agentId")
            if agent_id not in by_agent:
                raise AipSolutionPackInvalid("logic references an unknown agent")
            by_agent[agent_id].add(item["id"])
            if not set(item.get("capabilities", [])) <= set(CAPABILITY_IDS):
                raise AipSolutionPackInvalid("logic references an unknown capability")
        for item in agents:
            if set(item.get("logicIds", [])) != by_agent[item["id"]]:
                raise AipSolutionPackInvalid("agent logic crosswalk is incomplete")
            if len(by_agent[item["id"]]) != AGENT_LOGIC_COUNTS[item["id"]]:
                raise AipSolutionPackInvalid("agent logic count differs from W0A")
        provided = manifest.get("spec", {}).get("capabilities", {}).get("provides")
        if tuple(provided or ()) != CAPABILITY_IDS:
            raise AipSolutionPackInvalid("bundle capability provides list drifted")

    @staticmethod
    def _validate_analyst_templates(
        document: dict[str, Any], agents: list[dict[str, Any]]
    ) -> None:
        if set(document) != {"schemaVersion", "bundleRef", "templates"}:
            raise AipSolutionPackInvalid("analyst template document fields drifted")
        if document.get("schemaVersion") != 1:
            raise AipSolutionPackInvalid("analyst template schema is unsupported")
        if document.get("bundleRef") != (
            f"bundle://aos/{SOLUTION_PACK_ID}@{SOLUTION_PACK_VERSION}"
        ):
            raise AipSolutionPackInvalid("analyst template bundle reference drifted")
        templates = document.get("templates")
        if not isinstance(templates, list) or len(templates) != 6:
            raise AipSolutionPackInvalid("exactly six analyst role templates are required")
        if any(not isinstance(item, dict) for item in templates):
            raise AipSolutionPackInvalid("analyst template must be an object")
        agent_logic = {item["id"]: set(item["logicIds"]) for item in agents}
        roles = [item.get("roleId") for item in templates]
        ids = [item.get("templateId") for item in templates]
        if set(roles) != set(agent_logic) or len(set(roles)) != 6:
            raise AipSolutionPackInvalid("analyst role template crosswalk drifted")
        if len(set(ids)) != 6:
            raise AipSolutionPackInvalid("analyst template ids must be unique")
        for item in templates:
            if item.get("policy") != "canonical-read-only":
                raise AipSolutionPackInvalid("analyst template must be read-only")
            if item.get("queryKind") != "semantic":
                raise AipSolutionPackInvalid("analyst template query kind is unsupported")
            if set(item.get("requiredLogicIds") or ()) != agent_logic[item["roleId"]]:
                raise AipSolutionPackInvalid("analyst template Logic crosswalk drifted")
            required_types = item.get("requiredObjectTypes") or ()
            if item.get("defaultObjectType") not in required_types:
                raise AipSolutionPackInvalid("analyst template default type drifted")

    @staticmethod
    def _require_keys(
        items: list[dict[str, Any]], expected: set[str], label: str
    ) -> None:
        for item in items:
            if set(item) != expected:
                raise AipSolutionPackInvalid(f"{label} fields differ from the frozen contract")
            if any(
                not isinstance(item[key], str) or not item[key].strip()
                for key in expected
                if key not in {"logicIds", "capabilities", "aliases"}
            ):
                raise AipSolutionPackInvalid(f"{label} string fields must be non-empty")
            for key in expected & {"logicIds", "capabilities", "aliases"}:
                if not isinstance(item[key], list) or any(
                    not isinstance(value, str) or not value.strip()
                    for value in item[key]
                ):
                    raise AipSolutionPackInvalid(f"{label} {key} must contain strings")

    @staticmethod
    def _asset(kind: str, identifier: str, content_hash: str) -> VersionedAssetRef:
        return VersionedAssetRef(
            asset_type=kind,
            asset_id=identifier,
            revision=1,
            content_hash=content_hash,
        )

    @staticmethod
    def _list(document: dict[str, Any], key: str) -> list[dict[str, Any]]:
        value = document.get(key)
        if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
            raise AipSolutionPackInvalid(f"{key} must be a list of objects")
        return value

    @staticmethod
    def _json(path: Path) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AipSolutionPackInvalid(f"invalid JSON artifact: {path.name}") from exc
        if not isinstance(value, dict):
            raise AipSolutionPackInvalid(f"artifact must be an object: {path.name}")
        return value

    @staticmethod
    def _yaml(path: Path) -> dict[str, Any]:
        try:
            value = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise AipSolutionPackInvalid("invalid bundle manifest") from exc
        if not isinstance(value, dict):
            raise AipSolutionPackInvalid("bundle manifest must be an object")
        return value

    @classmethod
    def _hash(cls, value: Any) -> str:
        def normalize(item: Any) -> Any:
            if hasattr(item, "model_dump"):
                return normalize(item.model_dump(mode="json", by_alias=True))
            if isinstance(item, dict):
                return {key: normalize(child) for key, child in item.items()}
            if isinstance(item, (list, tuple)):
                return [normalize(child) for child in item]
            return item

        payload = json.dumps(
            normalize(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _file_hash(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()
