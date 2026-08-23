from contextlib import contextmanager
from datetime import UTC, datetime

import pytest

from aos_api.ecommerce_operation_case_contracts import (
    AggregationPolicyRevision,
    AutomationKillDecisionRevision,
    OperationCaseRevision,
    SlaPolicyRevision,
)
from aos_api.ecommerce_operation_case_store import (
    OperationAuthorityConflict,
    OperationAuthorityIdempotencyConflict,
    OperationAuthorityStore,
)
from aos_api.tenant_scope import TenantScope


NOW = datetime(2026, 8, 24, tzinfo=UTC)
HASH = "a" * 64
SCOPE = TenantScope(org_id="org-org", project_id="dev-project")


class Cursor:
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row


class Connection:
    def __init__(self, rows=()):
        self.rows = list(rows)
        self.calls = []
        self.commits = 0

    def execute(self, sql, params=None):
        self.calls.append((" ".join(sql.split()), params))
        row = self.rows.pop(0) if sql.lstrip().startswith("SELECT") else None
        return Cursor(row)

    def commit(self):
        self.commits += 1


def factory(connection):
    @contextmanager
    def connect(scope):
        assert scope == SCOPE
        yield connection

    return connect


def policy() -> AggregationPolicyRevision:
    return AggregationPolicyRevision.model_validate(
        {
            "tenant": {"orgId": "org-org", "projectId": "dev-project"},
            "policyId": "policy-1",
            "revision": 1,
            "version": 1,
            "lifecycle": "active",
            "ruleHash": HASH,
            "effectiveFrom": NOW,
            "contentHash": HASH,
            "actor": "user:operator",
            "createdAt": NOW,
        }
    )


def operation_case(*, original_org="org-org") -> OperationCaseRevision:
    return OperationCaseRevision.model_validate(
        {
            "tenant": {"orgId": "org-org", "projectId": "dev-project"},
            "caseId": "case-1",
            "revision": 1,
            "version": 1,
            "status": "open",
            "aggregationPolicyRef": {
                "resourceId": "policy-1",
                "revision": 1,
                "contentHash": HASH,
            },
            "memberRefs": [
                {
                    "tenant": {"orgId": original_org, "projectId": "dev-project"},
                    "resourceType": "Order",
                    "resourceId": "order-1",
                    "contentHash": HASH,
                    "sourceUpdatedAt": NOW,
                }
            ],
            "contentHash": HASH,
            "actor": "user:operator",
            "createdAt": NOW,
        }
    )


def test_publish_policy_creates_head_revision_and_receipt() -> None:
    connection = Connection(rows=[None, None])
    store = OperationAuthorityStore(factory(connection))
    ref = store.publish_policy(SCOPE, "user:operator", "key-1", policy(), expected_version=0)
    assert ref.resource_id == "policy-1"
    assert connection.commits == 1
    sql = "\n".join(call[0] for call in connection.calls)
    assert "INSERT INTO ecommerce_operation_aggregation_policy_head" in sql
    assert "INSERT INTO ecommerce_operation_authority_receipt" in sql
    assert all("org-org" not in statement for statement, _ in connection.calls)


def test_same_idempotency_key_with_different_payload_fails_closed() -> None:
    connection = Connection(rows=[{"request_hash": "b" * 64, "result_ref": {}}])
    store = OperationAuthorityStore(factory(connection))
    with pytest.raises(OperationAuthorityIdempotencyConflict):
        store.publish_policy(SCOPE, "user:operator", "key-1", policy(), expected_version=0)


def test_stale_expected_version_fails_closed() -> None:
    connection = Connection(rows=[None, {"current_revision": 1, "version": 1}])
    store = OperationAuthorityStore(factory(connection))
    with pytest.raises(OperationAuthorityConflict):
        store.publish_policy(SCOPE, "user:operator", "key-2", policy(), expected_version=0)


def test_case_rejects_cross_tenant_original_before_database_access() -> None:
    connection = Connection()
    store = OperationAuthorityStore(factory(connection))
    with pytest.raises(OperationAuthorityConflict, match="tenant"):
        store.create_case(SCOPE, "user:operator", "key-3", operation_case(original_org="dev-org"))
    assert connection.calls == []


def test_append_kill_is_receipt_first_and_append_only() -> None:
    item = AutomationKillDecisionRevision.model_validate(
        {
            "tenant": {"orgId": "org-org", "projectId": "dev-project"},
            "decisionId": "kill-1",
            "revision": 1,
            "state": "active",
            "scopeHash": HASH,
            "checkpoints": ["proposal", "lease", "executor"],
            "reason": "contain automation",
            "contentHash": HASH,
            "actor": "user:operator",
            "createdAt": NOW,
        }
    )
    connection = Connection(rows=[None])
    store = OperationAuthorityStore(factory(connection))
    ref = store.append_kill(SCOPE, "user:operator", "kill-key", item)
    assert ref.resource_id == "kill-1"
    sql = "\n".join(call[0] for call in connection.calls)
    assert "INSERT INTO ecommerce_operation_kill_decision_revision" in sql
    assert "UPDATE ecommerce_operation_kill_decision_revision" not in sql
    assert "INSERT INTO ecommerce_operation_authority_receipt" in sql


def test_publish_sla_policy_uses_versioned_head() -> None:
    item = SlaPolicyRevision.model_validate(
        {
            "tenant": {"orgId": "org-org", "projectId": "dev-project"},
            "policyId": "sla-1",
            "revision": 1,
            "version": 1,
            "lifecycle": "active",
            "responseSeconds": 300,
            "resolutionSeconds": 3600,
            "effectiveFrom": NOW,
            "contentHash": HASH,
            "actor": "user:operator",
            "createdAt": NOW,
        }
    )
    connection = Connection(rows=[None, None])
    store = OperationAuthorityStore(factory(connection))
    ref = store.publish_sla_policy(
        SCOPE, "user:operator", "sla-key", item, expected_version=0
    )
    assert ref.resource_id == "sla-1"
    sql = "\n".join(call[0] for call in connection.calls)
    assert "INSERT INTO ecommerce_operation_sla_policy_head" in sql
    assert "INSERT INTO ecommerce_operation_sla_policy_revision" in sql
