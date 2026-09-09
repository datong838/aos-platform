from copy import deepcopy
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from aos_api.aip_agent_registry_contracts import OperationalBindingDependencies, VersionedAssetRef
from aos_api.aip_binding_readiness_service import AipBindingReadinessService
from aos_api.aip_skill_binding_readiness_service import AipSkillBindingReadinessService
from aos_api.aip_skill_registry import AipSkillRegistry
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.db import connect
from aos_api.ecommerce_growth_runtime_adapters import ContentGenerateHostService
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
NOW = datetime(2026, 9, 9, 9, tzinfo=UTC)


def ref(kind, identity, digest):
    return VersionedAssetRef(
        assetType=kind, assetId=identity, revision=1, contentHash=digest
    )


class Transaction:
    def __init__(self):
        self.route_ref = ref("ModelRouteRevision", "route-1", "1" * 64)
        self.provider_ref = ref("ProviderInstanceRevision", "provider-1", "2" * 64)
        self.policy_ref = ref("RuntimePolicyRevision", "policy-1", "3" * 64)
        self.gate_ref = ref("EvalGateDecision", "gate-1", "4" * 64)
        self.budget_ref = ref("BudgetPolicyRevision", "budget-1", "5" * 64)
        self.capability_ref = ref("CapabilityRevision", "capability-1", "6" * 64)
        self.skill_ref = ref("SkillTemplate", "skill-1", "7" * 64)
        self.capability_row = {
            "binding_id": "cap-binding-1",
            "capability_ref": self.capability_ref.model_dump(mode="json", by_alias=True),
            "provider_ref": self.provider_ref.model_dump(mode="json", by_alias=True),
            "model_route_ref": self.route_ref.model_dump(mode="json", by_alias=True),
            "runtime_policy_ref": self.policy_ref.model_dump(mode="json", by_alias=True),
            "eval_gate_ref": self.gate_ref.model_dump(mode="json", by_alias=True),
            "eval_contract_ref": ref("EvalContractRevision", "eval-1", "8" * 64).model_dump(mode="json", by_alias=True),
            "license_evidence_refs": [],
            "data_dependency_refs": [],
            "tool_dependency_refs": [],
            "budget_policy_ref": self.budget_ref.model_dump(mode="json", by_alias=True),
            "allow_degraded": False,
            "status": "active",
            "health": "healthy",
            "version": 3,
            "operational_readiness": "available",
            "readiness_reasons": [],
            "observed_at": NOW - timedelta(minutes=2),
            "last_evaluated_at": NOW - timedelta(minutes=1),
            "readiness_expires_at": NOW + timedelta(minutes=10),
        }
        deps = OperationalBindingDependencies.model_validate(
            {
                key: value
                for key, value in self.capability_row.items()
                if key in {
                    "provider_ref", "model_route_ref", "runtime_policy_ref",
                    "eval_gate_ref", "eval_contract_ref", "license_evidence_refs",
                    "data_dependency_refs", "tool_dependency_refs", "budget_policy_ref",
                    "allow_degraded",
                }
            }
        )
        self.capability_row["dependency_snapshot_hash"] = AipBindingReadinessService.snapshot_hash(
            self.capability_ref, deps
        )
        self.capability_rows = [self.capability_row]
        self.skill_row = {
            "binding_id": "skill-binding-1",
            "instance_id": "agent-1",
            "skill_id": "skill-1",
            "skill_revision": 1,
            "capability_refs": ["cap-binding-1"],
            "budget_policy_ref": self.budget_ref.model_dump(mode="json", by_alias=True),
            "model_route_ref": self.route_ref.model_dump(mode="json", by_alias=True),
            "runtime_policy_ref": self.policy_ref.model_dump(mode="json", by_alias=True),
            "eval_gate_ref": self.gate_ref.model_dump(mode="json", by_alias=True),
            "status": "active",
            "version": 2,
            "readiness": "available",
            "readiness_reasons": [],
            "last_evaluated_at": NOW - timedelta(minutes=1),
            "readiness_expires_at": NOW + timedelta(minutes=10),
            "created_at": NOW - timedelta(days=1),
            "updated_at": NOW - timedelta(minutes=1),
            "skill_content_hash": self.skill_ref.content_hash,
            "skill_lifecycle": "published",
            "publication_tenant": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
            "skill_model_route_ref": self.route_ref.model_dump(mode="json", by_alias=True),
            "skill_runtime_policy_ref": self.policy_ref.model_dump(mode="json", by_alias=True),
            "skill_release_gate_ref": self.gate_ref.model_dump(mode="json", by_alias=True),
            "required_capabilities": ["capability-1"],
            "dependency_snapshot_hash": "0" * 64,
        }
        binding_row = {**self.skill_row, "content_hash": self.skill_row["skill_content_hash"]}
        binding = AipSkillRegistry._binding_from_row(SCOPE, binding_row)
        self.skill_row["dependency_snapshot_hash"] = AipSkillBindingReadinessService.snapshot_hash(
            binding, [self.capability_row]
        )

    def execute(self, query, _params=()):
        value = self.capability_rows if "aip_capability_binding" in query else self.skill_row

        class Result:
            def fetchone(inner):
                return value if isinstance(value, dict) else None

            def fetchall(inner):
                return value if isinstance(value, list) else []

        return Result()

    def inputs(self):
        route = SimpleNamespace(
            route_id="route-1", revision=1, content_hash="1" * 64,
            runtime_policy_ref=self.policy_ref, eval_gate_ref=self.gate_ref,
        )
        provider = SimpleNamespace(
            provider_instance_id="provider-1", revision=1, content_hash="2" * 64
        )
        policy = SimpleNamespace(budget_policy_ref=self.budget_ref)
        capability = SimpleNamespace(
            capability_id="capability-1", revision=1, content_hash="6" * 64
        )
        run = {"skill_binding_id": "skill-binding-1", "skill_ref": getattr(self, "run_skill_ref", self.skill_ref.model_dump(mode="json", by_alias=True))}
        authorities = {
            "agent_instance": InvestigationExactRef(resourceType="AgentInstanceRevision", resourceId="agent-1", revision=1, contentHash="sha256:" + "a" * 64),
            "capability": InvestigationExactRef(resourceType="CapabilityRevision", resourceId="capability-1", revision=1, contentHash="sha256:" + "6" * 64),
        }
        return authorities, route, provider, policy, run, capability


def validate(transaction):
    authorities, route, provider, policy, run, capability = transaction.inputs()
    ContentGenerateHostService._binding_authority(
        transaction, SCOPE, authorities, route=route, provider=provider,
        policy=policy, run=run, capability=capability, checked_at=NOW,
    )


def test_binding_authority_accepts_exact_current_chain():
    validate(Transaction())


def test_binding_owner_query_matches_migrated_postgres_schema():
    transaction = Transaction()
    authorities, route, provider, policy, run, capability = transaction.inputs()
    run["skill_binding_id"] = "missing-skill-binding"
    with connect(SCOPE) as connection:
        with pytest.raises(ValueError, match="authority is missing"):
            ContentGenerateHostService._binding_authority(
                connection, SCOPE, authorities, route=route, provider=provider,
                policy=policy, run=run, capability=capability, checked_at=NOW,
            )


@pytest.mark.parametrize("drift", (
    "skill_status", "skill_version_bool", "skill_expired", "skill_hash",
    "run_skill_bool", "run_skill_whitespace", "skill_route", "skill_route_bool", "required_uncovered",
    "cap_missing", "cap_status", "cap_version_bool", "cap_route_bool",
    "cap_future", "cap_expired", "cap_hash", "cap_route", "capability_ref",
    "other_cap_blocked",
))
def test_binding_authority_rejects_drift(drift):
    transaction = Transaction()
    if drift == "skill_status": transaction.skill_row["status"] = "suspended"
    elif drift == "skill_version_bool": transaction.skill_row["version"] = True
    elif drift == "skill_expired": transaction.skill_row["readiness_expires_at"] = NOW
    elif drift == "skill_hash": transaction.skill_row["dependency_snapshot_hash"] = "f" * 64
    elif drift == "run_skill_bool":
        transaction.run_skill_ref = transaction.skill_ref.model_dump(mode="json", by_alias=True)
        transaction.run_skill_ref["revision"] = True
    elif drift == "run_skill_whitespace":
        transaction.run_skill_ref = transaction.skill_ref.model_dump(mode="json", by_alias=True)
        transaction.run_skill_ref["assetId"] = " skill-1 "
    elif drift == "skill_route": transaction.skill_row["model_route_ref"] = ref("ModelRouteRevision", "other", "1" * 64).model_dump(mode="json", by_alias=True)
    elif drift == "skill_route_bool": transaction.skill_row["model_route_ref"]["revision"] = True
    elif drift == "required_uncovered": transaction.skill_row["required_capabilities"].append("capability-2")
    elif drift == "cap_missing": transaction.skill_row["capability_refs"] = ["missing"]
    elif drift == "cap_status": transaction.capability_row["status"] = "suspended"
    elif drift == "cap_version_bool": transaction.capability_row["version"] = True
    elif drift == "cap_route_bool": transaction.capability_row["model_route_ref"]["revision"] = True
    elif drift == "cap_future": transaction.capability_row["observed_at"] = NOW + timedelta(minutes=1)
    elif drift == "cap_expired": transaction.capability_row["readiness_expires_at"] = NOW
    elif drift == "cap_hash": transaction.capability_row["dependency_snapshot_hash"] = "f" * 64
    elif drift == "cap_route": transaction.capability_row["model_route_ref"] = ref("ModelRouteRevision", "other", "1" * 64).model_dump(mode="json", by_alias=True)
    elif drift == "capability_ref": transaction.capability_row["capability_ref"] = ref("CapabilityRevision", "other", "6" * 64).model_dump(mode="json", by_alias=True)
    elif drift == "other_cap_blocked":
        other = deepcopy(transaction.capability_row)
        other["binding_id"] = "cap-binding-2"
        other["capability_ref"] = ref("CapabilityRevision", "capability-2", "9" * 64).model_dump(mode="json", by_alias=True)
        transaction.capability_rows.append(other)
        transaction.skill_row["capability_refs"].append("cap-binding-2")
        transaction.skill_row["required_capabilities"].append("capability-2")
        binding_row = {**transaction.skill_row, "content_hash": transaction.skill_row["skill_content_hash"]}
        binding = AipSkillRegistry._binding_from_row(SCOPE, binding_row)
        transaction.skill_row["dependency_snapshot_hash"] = AipSkillBindingReadinessService.snapshot_hash(binding, transaction.capability_rows)
        other["operational_readiness"] = "blocked"
    with pytest.raises(ValueError, match="content generate"):
        validate(transaction)
