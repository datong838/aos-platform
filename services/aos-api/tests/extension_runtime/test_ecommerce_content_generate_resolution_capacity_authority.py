from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest

from aos_api.aip_model_capacity_authority import canonical_hash as capacity_hash
from aos_api.aip_model_capacity_reservation import AipModelCapacityReservationGate
from aos_api.aip_model_runtime_contracts import ModelRouteRevision
from aos_api.aip_model_runtime_store import (
    canonical_hash as runtime_hash,
    evaluation_candidate_ref,
)
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.db import connect
from aos_api.ecommerce_growth_runtime_adapters import ContentGenerateHostService
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
NOW = datetime(2026, 9, 9, 8, tzinfo=UTC)


def asset(kind: str, identity: str, digest: str):
    return {
        "assetType": kind,
        "assetId": identity,
        "revision": 1,
        "contentHash": digest,
    }


def command_ref(kind: str, identity: str, digest: str):
    return InvestigationExactRef.model_validate(
        {
            "resourceType": kind,
            "resourceId": identity,
            "revision": 1,
            "contentHash": "sha256:" + digest,
        }
    )


def runtime_payload(content: dict):
    digest = runtime_hash(content)
    return {
        "tenant": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "revision": 1,
        "contentHash": digest,
        **content,
        "createdBy": "pytest",
        "createdAt": NOW.isoformat(),
    }


class Transaction:
    def __init__(self):
        self.policy = runtime_payload(
            {
                "policyId": "policy-1",
                "networkPolicyRef": asset("NetworkPolicyRevision", "network-1", "1" * 64),
                "egressPolicyRef": asset("EgressPolicyRevision", "egress-1", "2" * 64),
                "dataClassificationPolicyRef": asset(
                    "DataClassificationPolicyRevision", "classification-1", "3" * 64
                ),
                "quotaPolicyRef": asset("QuotaPolicyRevision", "quota-1", "4" * 64),
                "budgetPolicyRef": asset("BudgetPolicyRevision", "budget-policy-1", "5" * 64),
                "deadlineMs": 30_000,
                "maxAttempts": 1,
                "allowedFallbackReasons": [],
                "unknownUsageBehavior": "block",
                "unknownPriceBehavior": "block",
                "killSwitchEnabled": False,
                "lifecycle": "active",
            }
        )
        self.provider = runtime_payload(
            {
                "providerInstanceId": "provider-1",
                "pluginRef": asset("ProviderPluginRevision", "plugin-1", "6" * 64),
                "endpointProfile": {
                    "baseUrl": "https://provider.invalid",
                    "region": "cn",
                    "timeoutMs": 30_000,
                },
                "secretRef": "vault://aos/provider-1",
                "secretVersion": "1",
                "egressPolicyRef": asset("EgressPolicyRevision", "egress-1", "2" * 64),
                "dataClassificationPolicyRef": asset(
                    "DataClassificationPolicyRevision", "classification-1", "3" * 64
                ),
                "lifecycle": "active",
            }
        )
        self.model_gate_hash = "7" * 64
        self.price_hash = "8" * 64
        self.model = runtime_payload(
            {
                "registeredModelId": "model-1",
                "provider": asset(
                    "ProviderInstanceRevision", "provider-1", self.provider["contentHash"]
                ),
                "providerModelId": "model-text-1",
                "inputModalities": ["text"],
                "outputModalities": ["text"],
                "capabilities": ["capability-1"],
                "contextWindow": 32_000,
                "quotaPolicyRef": asset("QuotaPolicyRevision", "quota-1", "4" * 64),
                "budgetPolicyRef": asset("BudgetPolicyRevision", "budget-policy-1", "5" * 64),
                "priceSnapshotRef": asset(
                    "ModelPriceSnapshotRevision", "price-1", self.price_hash
                ),
                "evalGateRef": asset(
                    "EvalGateDecision", "model-gate-1", self.model_gate_hash
                ),
                "lifecycle": "active",
            }
        )
        self.route_gate_hash = "9" * 64
        self.route = runtime_payload(
            {
                "routeId": "route-1",
                "taskTypes": ["content_campaign"],
                "requiredInputModality": "text",
                "requiredOutputModality": "text",
                "requiredCapabilities": ["capability-1"],
                "candidates": [
                    {
                        "model": asset(
                            "RegisteredModelRevision", "model-1", self.model["contentHash"]
                        ),
                        "weight": 100,
                    }
                ],
                "strategy": "failover",
                "runtimePolicyRef": asset(
                    "RuntimePolicyRevision", "policy-1", self.policy["contentHash"]
                ),
                "evalGateRef": asset(
                    "EvalGateDecision", "route-gate-1", self.route_gate_hash
                ),
                "lifecycle": "active",
            }
        )
        self.route_model = ModelRouteRevision.model_validate(self.route)
        self.pool_refs = {
            "route": asset("ModelRouteRevision", "route-1", self.route["contentHash"]),
            "model": asset("RegisteredModelRevision", "model-1", self.model["contentHash"]),
            "provider": asset(
                "ProviderInstanceRevision", "provider-1", self.provider["contentHash"]
            ),
        }
        self.pool_content = {
            "poolId": "pool-1",
            "revision": 1,
            "routeRef": self.pool_refs["route"],
            "modelRef": self.pool_refs["model"],
            "providerRef": self.pool_refs["provider"],
            "maxConcurrency": 2,
            "maxTokenUnits": 16_000,
            "tokenUnitPerReservation": 8_000,
            "leaseSeconds": 300,
            "lifecycle": "active",
        }
        exact = tuple(
            value
            for name in ("route", "model", "provider")
            for value in (
                self.pool_refs[name]["assetId"],
                self.pool_refs[name]["revision"],
                self.pool_refs[name]["contentHash"],
            )
        )
        request_hash = AipModelCapacityReservationGate._request_hash(
            "agent-run-1", exact, "pool-1", 1, 8_000
        )
        self.capacity = {
            "reservation_id": "capacity-1",
            "pool_id": "pool-1",
            "pool_revision": 1,
            "agent_run_id": "agent-run-1",
            "request_hash": request_hash,
            "request_units": 1,
            "token_units": 8_000,
            "status": "reserved",
            "reservation_created_at": NOW - timedelta(minutes=5),
            "expires_at": NOW + timedelta(minutes=5),
            "current_revision": 1,
            "head_version": 1,
            "pool_content_hash": capacity_hash(self.pool_content),
            "route_ref": self.pool_refs["route"],
            "model_ref": self.pool_refs["model"],
            "provider_ref": self.pool_refs["provider"],
            "route_id": "route-1",
            "route_revision": 1,
            "route_hash": self.route["contentHash"],
            "model_id": "model-1",
            "model_revision": 1,
            "model_hash": self.model["contentHash"],
            "provider_id": "provider-1",
            "provider_revision": 1,
            "provider_hash": self.provider["contentHash"],
            "max_concurrency": 2,
            "max_token_units": 16_000,
            "token_unit_per_reservation": 8_000,
            "lease_seconds": 300,
            "pool_lifecycle": "active",
        }
        self.route_gate = self._gate(
            "route", evaluation_candidate_ref(self.route_model), self.route_gate_hash
        )
        model_object = self._model_object()
        self.model_gate = self._gate(
            "model", evaluation_candidate_ref(model_object), self.model_gate_hash
        )
        self.health = {
            "status": "healthy",
            "provider_ref": self.pool_refs["provider"],
            "observed_at": NOW - timedelta(minutes=1),
            "expires_at": NOW + timedelta(minutes=5),
        }
        self.run = {
            "agent_run_id": "agent-run-1",
            "task_id": "task-1",
            "instance_id": "agent-1",
            "instance_version": 1,
            "model_route_ref": self.pool_refs["route"],
            "policy_ref": asset(
                "RuntimePolicyRevision", "policy-1", self.policy["contentHash"]
            ),
            "status": "running",
            "version": 2,
        }

    def _model_object(self):
        from aos_api.aip_model_runtime_contracts import RegisteredModelRevision

        return RegisteredModelRevision.model_validate(self.model)

    @staticmethod
    def _gate(_name, expected, digest):
        kind = (
            "model_route"
            if expected.asset_type == "ModelRouteRevision"
            else "registered_model"
        )
        return {
            "target_ref": {
                "assetType": kind,
                "assetId": expected.asset_id,
                "revision": str(expected.revision),
                "contentHash": expected.content_hash,
            },
            "status": "passed",
            "decision_hash": digest,
            "invalidated_by": None,
            "decided_at": NOW - timedelta(minutes=5),
            "expires_at": NOW + timedelta(minutes=5),
        }

    def authorities(self):
        return {
            "capacity_reservation": command_ref(
                "CapacityReservation", "capacity-1", self.capacity["request_hash"]
            ),
            "model_route": command_ref(
                "ModelRouteRevision", "route-1", self.route["contentHash"]
            ),
            "pricing": command_ref(
                "ModelPriceSnapshotRevision", "price-1", self.price_hash
            ),
            "task": command_ref("Task", "task-1", "a" * 64),
            "agent_instance": command_ref("AgentInstanceRevision", "agent-1", "b" * 64),
        }

    def execute(self, query, _params=()):
        if "aip_model_capacity_reservation" in query:
            value = self.capacity
        elif "aip_registered_model_revision" in query:
            value = {
                "content_hash": self.model["contentHash"],
                "lifecycle": self.model["lifecycle"],
                "payload": self.model,
            }
        elif "aip_provider_instance_revision" in query:
            value = {
                "content_hash": self.provider["contentHash"],
                "lifecycle": self.provider["lifecycle"],
                "payload": self.provider,
            }
        elif "aip_runtime_policy_revision" in query:
            value = {
                "content_hash": self.policy["contentHash"],
                "lifecycle": self.policy["lifecycle"],
                "payload": self.policy,
            }
        elif "aip_release_gate_decision" in query:
            value = self.route_gate if _params[-1] == "route-gate-1" else self.model_gate
        elif "aip_provider_health_observation" in query:
            value = self.health
        elif "aip_agent_run" in query:
            value = self.run
        else:
            raise AssertionError(query)

        class Result:
            def fetchone(self):
                return value

        return Result()


def test_resolution_capacity_accepts_exact_current_tuple():
    transaction = Transaction()
    ContentGenerateHostService._resolution_capacity_authority(
        transaction,
        SCOPE,
        transaction.authorities(),
        route=transaction.route_model,
        checked_at=NOW,
        max_input_tokens=4_000,
        max_output_tokens=2_000,
    )


def test_resolution_capacity_owner_query_matches_migrated_postgres_schema():
    transaction = Transaction()
    authorities = transaction.authorities()
    authorities["capacity_reservation"] = command_ref(
        "CapacityReservation", "missing-capacity", "f" * 64
    )
    with connect(SCOPE) as connection:
        with pytest.raises(ValueError, match="authority is missing"):
            ContentGenerateHostService._resolution_capacity_authority(
                connection,
                SCOPE,
                authorities,
                route=transaction.route_model,
                checked_at=NOW,
                max_input_tokens=4_000,
                max_output_tokens=2_000,
            )


@pytest.mark.parametrize(
    "drift",
    (
        "capacity_ref",
        "capacity_status",
        "capacity_future",
        "capacity_expiry",
        "capacity_request_hash",
        "capacity_tokens",
        "pool_head",
        "pool_hash",
        "pool_ref_bool",
        "model_payload",
        "model_price",
        "provider_payload",
        "policy_kill",
        "route_gate",
        "model_gate",
        "health",
        "health_future",
        "run_task",
        "run_agent",
        "run_route",
    ),
)
def test_resolution_capacity_rejects_drift(drift):
    transaction = Transaction()
    authorities = transaction.authorities()
    if drift == "capacity_ref":
        authorities["capacity_reservation"] = command_ref(
            "CapacityReservation", "capacity-1", "f" * 64
        )
    elif drift == "capacity_status":
        transaction.capacity["status"] = "consumed"
    elif drift == "capacity_future":
        transaction.capacity["reservation_created_at"] = NOW + timedelta(minutes=1)
    elif drift == "capacity_expiry":
        transaction.capacity["expires_at"] = NOW
    elif drift == "capacity_request_hash":
        transaction.capacity["request_hash"] = "f" * 64
    elif drift == "capacity_tokens":
        transaction.capacity["token_units"] = 5_000
    elif drift == "pool_head":
        transaction.capacity["current_revision"] = 2
    elif drift == "pool_hash":
        transaction.capacity["pool_content_hash"] = "f" * 64
    elif drift == "pool_ref_bool":
        transaction.capacity["model_ref"] = deepcopy(transaction.capacity["model_ref"])
        transaction.capacity["model_ref"]["revision"] = True
    elif drift == "model_payload":
        transaction.model["contextWindow"] = 64_000
    elif drift == "model_price":
        transaction.model["priceSnapshotRef"] = asset(
            "ModelPriceSnapshotRevision", "other", transaction.price_hash
        )
        transaction.model["contentHash"] = runtime_hash(
            {
                key: value
                for key, value in transaction.model.items()
                if key not in {"tenant", "revision", "contentHash", "createdBy", "createdAt"}
            }
        )
    elif drift == "provider_payload":
        transaction.provider["endpointProfile"]["region"] = "us"
    elif drift == "policy_kill":
        transaction.policy["killSwitchEnabled"] = True
        transaction.policy["contentHash"] = runtime_hash(
            {
                key: value
                for key, value in transaction.policy.items()
                if key not in {"tenant", "revision", "contentHash", "createdBy", "createdAt"}
            }
        )
    elif drift == "route_gate":
        transaction.route_gate["status"] = "failed"
    elif drift == "model_gate":
        transaction.model_gate["invalidated_by"] = "drift"
    elif drift == "health":
        transaction.health["status"] = "degraded"
    elif drift == "health_future":
        transaction.health["observed_at"] = NOW + timedelta(minutes=1)
        transaction.health["expires_at"] = NOW + timedelta(minutes=5)
    elif drift == "run_task":
        transaction.run["task_id"] = "other"
    elif drift == "run_agent":
        transaction.run["instance_version"] = True
    elif drift == "run_route":
        transaction.run["model_route_ref"] = deepcopy(transaction.run["model_route_ref"])
        transaction.run["model_route_ref"]["revision"] = True
    with pytest.raises(ValueError, match="content generate"):
        ContentGenerateHostService._resolution_capacity_authority(
            transaction,
            SCOPE,
            authorities,
            route=transaction.route_model,
            checked_at=NOW,
            max_input_tokens=4_000,
            max_output_tokens=2_000,
        )
