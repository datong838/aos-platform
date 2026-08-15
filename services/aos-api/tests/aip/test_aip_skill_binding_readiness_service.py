from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from aos_api.aip_agent_registry_contracts import (
    CapabilityReadiness,
    CreateSkillBindingRequest,
    OperationalBindingDependencies,
    SkillBinding,
    VersionedAssetRef,
)
from aos_api.aip_agent_registry_store import AipAgentRegistryTransitionBlocked
from aos_api.aip_contracts import ResourceRef, TenantContext
from aos_api.aip_skill_binding_readiness_service import (
    AipSkillBindingReadinessService,
)
from aos_api.tenant_scope import TenantScope
from pydantic import ValidationError

PRIMARY = TenantScope("org-org", "dev-project")
NOW = datetime(2026, 8, 15, 6, tzinfo=UTC)
HASHES = {
    name: char * 64
    for name, char in zip(
        [
            "skill",
            "gate",
            "route",
            "policy",
            "budget",
            "capability",
            "snapshot",
        ],
        "1234567",
    )
}


def ref(kind: str, asset_id: str, content_hash: str) -> VersionedAssetRef:
    return VersionedAssetRef(
        asset_type=kind,
        asset_id=asset_id,
        revision=1,
        content_hash=content_hash,
    )


def dependencies() -> OperationalBindingDependencies:
    return OperationalBindingDependencies(
        model_route_ref=ref("ModelRouteRevision", "route-1", HASHES["route"]),
        runtime_policy_ref=ref(
            "RuntimePolicyRevision", "policy-1", HASHES["policy"]
        ),
        eval_gate_ref=ref("EvalGateDecision", "gate-1", HASHES["gate"]),
        budget_policy_ref=ref(
            "BudgetPolicyRevision", "budget-1", HASHES["budget"]
        ),
    )


def binding() -> SkillBinding:
    return SkillBinding(
        tenant=TenantContext(org_id=PRIMARY.org_id, project_id=PRIMARY.project_id),
        binding_id="skill-binding-1",
        instance_id="content-officer-1",
        skill=ref("SkillTemplate", "content.plan", HASHES["skill"]),
        capability_binding_ids=["capability-binding-1"],
        budget_policy_ref=dependencies().budget_policy_ref,
        dependencies=dependencies(),
        status="provisioning",
        version=1,
        created_at=NOW,
        updated_at=NOW,
    )


class _Result:
    def __init__(self, *, one=None, many=None):
        self._one = one
        self._many = many

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._many if self._many is not None else []


class _Connection:
    def __init__(self, state):
        self.state = state

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, statement, _params):
        if "FROM aip_skill_template_revision" in statement:
            return _Result(one=self.state["skill"])
        if "FROM aip_publication_event" in statement:
            return _Result(one=self.state["publication"])
        if "FROM aip_release_gate_decision" in statement:
            return _Result(one=self.state["gate"])
        if "FROM aip_agent_instance" in statement:
            return _Result(one=self.state["instance"])
        if "FROM aip_capability_binding" in statement:
            return _Result(many=self.state["capabilities"])
        raise AssertionError(f"unexpected readiness query: {statement}")


def authority_state():
    deps = dependencies()
    parent = ref("SkillTemplate", "content.plan", HASHES["skill"])
    return {
        "skill": {
            "lifecycle": "published",
            "publication_tenant": {
                "orgId": PRIMARY.org_id,
                "projectId": PRIMARY.project_id,
            },
            "release_gate_ref": deps.eval_gate_ref.model_dump(
                mode="json", by_alias=True
            ),
            "publication_ref": ResourceRef(
                resource_type="PublicationEvent",
                resource_id="event-1",
                revision="publication-1",
                authority="postgresql",
            ).model_dump(mode="json", by_alias=True),
            "parent_ref": parent.model_dump(mode="json", by_alias=True),
            "model_route_ref": deps.model_route_ref.model_dump(
                mode="json", by_alias=True
            ),
            "runtime_policy_ref": deps.runtime_policy_ref.model_dump(
                mode="json", by_alias=True
            ),
            "required_capabilities": ["wiki.search"],
        },
        "publication": {
            "event_type": "published",
            "target_ref": {
                "assetId": parent.asset_id,
                "revision": str(parent.revision),
                "contentHash": parent.content_hash,
            },
        },
        "gate": {"status": "passed", "decision_hash": HASHES["gate"]},
        "instance": {"status": "active"},
        "capabilities": [
            {
                "binding_id": "capability-binding-1",
                "capability_ref": {
                    "assetType": "CapabilityRevision",
                    "assetId": "wiki.search",
                    "revision": 1,
                    "contentHash": HASHES["capability"],
                },
                "status": "active",
                "operational_readiness": "available",
                "allow_degraded": False,
                "dependency_snapshot_hash": HASHES["snapshot"],
                "readiness_expires_at": NOW + timedelta(minutes=30),
            }
        ],
    }


class _RouteAuthority:
    def __init__(self, ready=True):
        self.ready = ready

    def require_ready(self, *_args, **_kwargs):
        if not self.ready:
            raise AipAgentRegistryTransitionBlocked("route unavailable")


class _ModelStore:
    def get_policy(self, *_args):
        deps = dependencies()
        return SimpleNamespace(
            content_hash=deps.runtime_policy_ref.content_hash,
            budget_policy_ref=deps.budget_policy_ref,
        )


def service(state, *, route_ready=True):
    return AipSkillBindingReadinessService(
        connect_factory=lambda _scope: _Connection(state),
        route_authority=_RouteAuthority(route_ready),
        model_store=_ModelStore(),
    )


def test_exact_skill_chain_produces_available_deterministic_snapshot():
    state = authority_state()
    first = service(state).evaluate(PRIMARY, binding(), evaluated_at=NOW)
    second = service(state).evaluate(PRIMARY, binding(), evaluated_at=NOW)

    assert first.readiness is CapabilityReadiness.AVAILABLE
    assert first.reasons == []
    assert first.dependency_snapshot_hash == second.dependency_snapshot_hash
    assert first.expires_at == NOW + timedelta(minutes=15)


def test_any_publication_instance_capability_or_route_drift_fails_closed():
    state = authority_state()
    state["publication"] = {"event_type": "revoked", "target_ref": {}}
    state["instance"] = {"status": "suspended"}
    state["capabilities"][0]["operational_readiness"] = "blocked"
    state["capabilities"][0]["readiness_expires_at"] = NOW

    result = service(state, route_ready=False).evaluate(
        PRIMARY, binding(), evaluated_at=NOW
    )

    assert result.readiness is CapabilityReadiness.BLOCKED
    assert result.reasons == [
        "CAPABILITY_BINDING_NOT_ACTIVE",
        "CAPABILITY_HEALTH_STALE",
        "INSTANCE_NOT_ACTIVE",
        "MODEL_ROUTE_BLOCKED",
        "SKILL_PUBLICATION_REVOKED",
    ]


def test_skill_binding_contract_allows_only_provisioning_and_revision_budget_ref():
    payload = {
        "bindingId": "binding-1",
        "instanceId": "instance-1",
        "skill": ref("SkillTemplate", "skill-1", HASHES["skill"]),
        "capabilityBindingIds": [],
        "budgetPolicyRef": ref(
            "BudgetPolicyRevision", "budget-1", HASHES["budget"]
        ),
        "initialStatus": "active",
    }
    with pytest.raises(ValidationError, match="initialStatus"):
        CreateSkillBindingRequest.model_validate(payload)
    payload["initialStatus"] = "provisioning"
    payload["budgetPolicyRef"] = ref(
        "BudgetPolicy", "budget-1", HASHES["budget"]
    )
    with pytest.raises(ValidationError, match="BudgetPolicyRevision"):
        CreateSkillBindingRequest.model_validate(payload)
