"""BI-W3-01 read-only observation session and plan authority tests."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from importlib import util
from pathlib import Path
from unittest.mock import patch

import psycopg
import pytest
from alembic import command
from psycopg.rows import dict_row
from pydantic import ValidationError

from aos_api.business_investigation_observation_contracts import (
    ObservationPlanRevisionRecord,
    ObservationSessionLeaseRecord,
)
from aos_api.business_investigation_observation_store import (
    BusinessInvestigationObservationConflict,
    BusinessInvestigationObservationStore,
)
from aos_api.tenant_scope import TenantScope
from tests.aip._migration_test_support import isolated_aip_migration_database


MIGRATION = Path(__file__).parents[1] / "alembic/versions/biw3_001_observation_session_plan.py"
SCOPE = TenantScope(org_id="org-org", project_id="dev-project")
OTHER_SCOPE = TenantScope(org_id="dev-org", project_id="dev-project")
NOW = datetime.now(UTC)
HASH_A = f"sha256:{'a' * 64}"
HASH_B = f"sha256:{'b' * 64}"
HASH_C = f"sha256:{'c' * 64}"


def ref(resource_type: str, resource_id: str, *, revision: int = 1, content_hash: str = HASH_A):
    return {
        "resourceType": resource_type,
        "resourceId": resource_id,
        "revision": revision,
        "contentHash": content_hash,
    }


def lease_payload(**changes):
    value = {
        "schemaVersion": "aos.business-investigation.observation-session-lease/v1",
        "tenant": {"orgId": "org-org", "projectId": "dev-project"},
        "leaseId": "lease-1",
        "revision": 1,
        "stateVersion": 1,
        "contentHash": HASH_A,
        "platform": "niushop",
        "channelRef": ref("ChannelRevision", "channel-1"),
        "entityRef": ref("BusinessEntityRevision", "shop-1"),
        "requirementRef": ref("DataRequirementRevision", "requirement-1"),
        "purposeCode": "investigation_read",
        "scope": "read-only-observation",
        "sessionHandleRef": ref("ObservationSessionHandleRef", "session-handle-1"),
        "allowedDomains": ["admin.example.test"],
        "allowedRoutePatterns": ["/orders/**", "/dashboard"],
        "allowedReadActions": ["navigate", "wait", "scroll", "filter", "open-detail", "read"],
        "exportAuthorizationRef": None,
        "operatorRef": "operator-1",
        "humanAssisted": True,
        "issuedAt": NOW,
        "expiresAt": NOW + timedelta(minutes=45),
        "status": "active",
        "idempotencyKey": "lease-issue-1",
        "requestHash": HASH_B,
        "createdBy": "operator-1",
        "revokedAt": None,
        "revocationReason": None,
    }
    value.update(changes)
    return value


def plan_payload(**changes):
    value = {
        "schemaVersion": "aos.business-investigation.observation-plan/v1",
        "tenant": {"orgId": "org-org", "projectId": "dev-project"},
        "planId": "plan-1",
        "revision": 1,
        "priorRef": None,
        "contentHash": HASH_B,
        "leaseRef": ref("ObservationSessionLeaseRevision", "lease-1"),
        "requirementRef": ref("DataRequirementRevision", "requirement-1"),
        "goal": "读取订单页面的经营事实",
        "requiredFacts": ["Order.paidAmount", "Order.paidAt"],
        "pageInventory": [
            {"domain": "admin.example.test", "routePattern": "/orders/**"}
        ],
        "steps": [
            {
                "stepId": "step-1",
                "action": "navigate",
                "domain": "admin.example.test",
                "routePattern": "/orders/**",
                "expectedSemanticFields": ["Order.paidAmount"],
            },
            {
                "stepId": "step-2",
                "action": "read",
                "domain": "admin.example.test",
                "routePattern": "/orders/**",
                "expectedSemanticFields": ["Order.paidAmount", "Order.paidAt"],
            },
        ],
        "paginationPolicy": {"mode": "bounded", "maxPages": 10, "virtualList": True},
        "networkPolicy": {"timeoutSeconds": 20, "maxAttempts": 2, "backoffSeconds": 2},
        "evidencePolicy": {"screenshot": True, "dom": True, "export": False},
        "prohibitedControls": [
            "save", "submit", "delete", "list", "publish", "ship", "reprice",
            "contact", "sign", "settle", "batch", "permission-config",
        ],
        "stopConditions": ["permission-denied", "captcha", "route-drift", "lease-expired"],
        "humanTakeoverPoints": ["login-required", "captcha"],
        "idempotencyKey": "plan-create-1",
        "requestHash": HASH_A,
        "createdBy": "operator-1",
        "createdAt": NOW + timedelta(minutes=1),
    }
    value.update(changes)
    return value


def _load_migration():
    spec = util.spec_from_file_location("biw3_001", MIGRATION)
    assert spec and spec.loader
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_contracts_are_strict_read_only_secret_free_and_exact() -> None:
    lease = ObservationSessionLeaseRecord.model_validate(lease_payload())
    assert lease.scope == "read-only-observation" and lease.status.value == "active"

    for changes, match in (
        ({"scope": "authorized-action"}, "scope"),
        ({"expiresAt": NOW + timedelta(hours=3)}, "two hours"),
        ({"allowedDomains": ["https://admin.example.test/orders?token=x"]}, "domain"),
        ({"allowedRoutePatterns": ["/orders?token=x"]}, "route"),
        ({"allowedReadActions": ["navigate", "publish"]}, "allowedReadActions"),
        ({"cookie": "secret"}, "Extra inputs"),
    ):
        with pytest.raises(ValidationError, match=match):
            ObservationSessionLeaseRecord.model_validate(lease_payload(**changes))

    with pytest.raises(ValidationError, match="export authorization"):
        ObservationSessionLeaseRecord.model_validate(
            lease_payload(allowedReadActions=["navigate", "export"])
        )


def test_plan_is_bounded_by_exact_active_lease_and_allowlists() -> None:
    lease = ObservationSessionLeaseRecord.model_validate(lease_payload())
    plan = ObservationPlanRevisionRecord.model_validate(plan_payload())
    plan.validate_against_lease(lease)

    bad_route = ObservationPlanRevisionRecord.model_validate(
        plan_payload(steps=[{**plan_payload()["steps"][0], "routePattern": "/settings"}])
    )
    with pytest.raises(ValueError, match="route allowlist"):
        bad_route.validate_against_lease(lease)

    export_plan = plan_payload(
        steps=[{**plan_payload()["steps"][0], "action": "export"}],
        evidencePolicy={"screenshot": True, "dom": True, "export": True},
    )
    with pytest.raises(ValueError, match="action allowlist"):
        ObservationPlanRevisionRecord.model_validate(export_plan).validate_against_lease(lease)

    with pytest.raises(ValidationError, match="prohibitedControls"):
        ObservationPlanRevisionRecord.model_validate(
            plan_payload(prohibitedControls=["save"])
        )


def test_migration_is_tenant_scoped_function_only_and_non_destructive() -> None:
    module = _load_migration()
    assert module.revision == "biw3_001" and module.down_revision == "biw2_004"
    statements: list[str] = []
    with patch.object(module.op, "execute", statements.append):
        module.upgrade()
    sql = "\n".join(statements)
    assert "business_investigation_observation_session_lease" in sql
    assert "business_investigation_observation_plan_head" in sql
    assert "business_investigation_observation_plan_revision" in sql
    assert sql.count("ENABLE ROW LEVEL SECURITY") == 3
    assert sql.count("FORCE ROW LEVEL SECURITY") == 3
    assert "SECURITY DEFINER" in sql
    assert "read-only-observation" in sql
    assert "DataRequirementRevision" in sql
    assert "prohibitedControls" in sql and "permission-config" in sql
    assert "pageInventory" in sql and "allowedRoutePatterns" in sql
    assert "sessionPayload" in sql
    assert "GRANT EXECUTE ON FUNCTION" in sql
    assert "GRANT INSERT ON business_investigation" not in sql


def test_store_uses_controlled_functions_and_validates_before_sql() -> None:
    class Cursor:
        def __init__(self, row): self.row = row
        def fetchone(self): return self.row

    class Connection:
        def __init__(self): self.calls = []; self.commits = 0
        def execute(self, sql, params=None):
            self.calls.append((" ".join(sql.split()), params))
            payload = params[-1].obj if hasattr(params[-1], "obj") else params[-1]
            return Cursor({"authority_data": payload, "replayed": False})
        def commit(self): self.commits += 1

    connection = Connection()

    @contextmanager
    def connect(scope):
        assert scope == SCOPE
        yield connection

    store = BusinessInvestigationObservationStore(connect)
    lease = store.issue_lease(SCOPE, ObservationSessionLeaseRecord.model_validate(lease_payload()))
    plan = store.publish_plan(
        SCOPE,
        ObservationPlanRevisionRecord.model_validate(plan_payload()),
        expected_version=0,
    )
    assert not lease.replayed and not plan.replayed and connection.commits == 2
    assert "observation_lease_issue_biw3_001" in connection.calls[0][0]
    assert "observation_plan_publish_biw3_001" in connection.calls[1][0]


def test_disposable_database_cas_revoke_isolation_and_downgrade() -> None:
    with isolated_aip_migration_database("biw3_observation_session_plan") as (config, dsn):
        command.downgrade(config, "biw2_004")
        command.upgrade(config, "head")
        with psycopg.connect(dsn) as conn:
            for org in ("org-org", "dev-org"):
                conn.execute(
                    "INSERT INTO data_requirement_head(org_id,project_id,requirement_id,current_revision,current_content_hash,status,version,created_by) VALUES(%s,'dev-project','requirement-1',1,%s,'accepted',1,'pytest')",
                    (org, "a" * 64),
                )
                conn.execute(
                    "INSERT INTO data_requirement_revision(org_id,project_id,requirement_id,revision,content_hash,status,operation,idempotency_key,request_hash,case_ref,run_ref,checkpoint_ref,payload,created_by) VALUES(%s,'dev-project','requirement-1',1,%s,'accepted','request','seed',%s,'{}','{}','{}','{}','pytest')",
                    (org, "a" * 64, "b" * 64),
                )
            conn.commit()

        @contextmanager
        def runtime_connect(scope):
            with psycopg.connect(dsn, row_factory=dict_row) as conn:
                conn.execute("SET LOCAL ROLE aos_runtime")
                conn.execute(
                    "SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",
                    scope.key,
                )
                yield conn

        store = BusinessInvestigationObservationStore(runtime_connect)
        issued = store.issue_lease(SCOPE, ObservationSessionLeaseRecord.model_validate(lease_payload()))
        replayed = store.issue_lease(SCOPE, ObservationSessionLeaseRecord.model_validate(lease_payload()))
        assert not issued.replayed and replayed.replayed
        with pytest.raises(BusinessInvestigationObservationConflict):
            store.issue_lease(
                SCOPE,
                ObservationSessionLeaseRecord.model_validate(
                    lease_payload(requestHash=f"sha256:{'c' * 64}")
                ),
            )

        published = store.publish_plan(
            SCOPE,
            ObservationPlanRevisionRecord.model_validate(plan_payload()),
            expected_version=0,
        )
        assert not published.replayed
        revised_payload = plan_payload(
            revision=2,
            priorRef=ref("ObservationPlanRevision", "plan-1", content_hash=HASH_B),
            contentHash=HASH_C,
            idempotencyKey="plan-revise-1",
            requestHash=HASH_C,
        )
        revised = store.publish_plan(
            SCOPE,
            ObservationPlanRevisionRecord.model_validate(revised_payload),
            expected_version=1,
        )
        assert revised.authority.revision == 2
        with pytest.raises(BusinessInvestigationObservationConflict):
            store.publish_plan(
                SCOPE,
                ObservationPlanRevisionRecord.model_validate(
                    plan_payload(
                        revision=3,
                        priorRef=ref("ObservationPlanRevision", "plan-1", revision=2, content_hash=HASH_C),
                        contentHash=HASH_A,
                        idempotencyKey="plan-stale",
                        requestHash=HASH_C,
                    )
                ),
                expected_version=1,
            )
        revoked = store.revoke_lease(
            SCOPE, "lease-1", expected_state_version=1, idempotency_key="revoke-1", reason="operator-request"
        )
        assert revoked.status.value == "revoked" and revoked.state_version == 2
        with pytest.raises(BusinessInvestigationObservationConflict):
            store.publish_plan(
                SCOPE,
                ObservationPlanRevisionRecord.model_validate(
                    plan_payload(planId="plan-2", idempotencyKey="plan-create-2")
                ),
                expected_version=0,
            )

        expiring_lease = ObservationSessionLeaseRecord.model_validate(
            lease_payload(leaseId="lease-expired", idempotencyKey="lease-expired")
        )
        store.issue_lease(SCOPE, expiring_lease)
        with psycopg.connect(dsn) as conn:
            conn.execute(
                "UPDATE business_investigation_observation_session_lease SET expires_at=NOW()-INTERVAL '1 second' WHERE org_id='org-org' AND project_id='dev-project' AND lease_id='lease-expired'"
            )
            conn.commit()
        with pytest.raises(BusinessInvestigationObservationConflict):
            store.publish_plan(
                SCOPE,
                ObservationPlanRevisionRecord.model_validate(
                    plan_payload(
                        planId="plan-expired",
                        leaseRef=ref("ObservationSessionLeaseRevision", "lease-expired"),
                        idempotencyKey="plan-expired",
                    )
                ),
                expected_version=0,
            )

        other_lease = ObservationSessionLeaseRecord.model_validate(
            lease_payload(
                tenant={"orgId": "dev-org", "projectId": "dev-project"},
                leaseId="lease-other",
                idempotencyKey="lease-other",
            )
        )
        assert not store.issue_lease(OTHER_SCOPE, other_lease).replayed

        with psycopg.connect(dsn) as conn:
            conn.execute("SET LOCAL ROLE aos_runtime")
            conn.execute("SELECT set_config('aos.org_id','org-org',true)")
            conn.execute("SELECT set_config('aos.project_id','dev-project',true)")
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(
                    "INSERT INTO business_investigation_observation_plan_head(org_id,project_id,plan_id,current_revision,current_content_hash,version) VALUES('org-org','dev-project','direct',1,%s,1)",
                    (HASH_A,),
                )

        with pytest.raises(Exception, match="cannot downgrade biw3_001"):
            command.downgrade(config, "biw2_004")
