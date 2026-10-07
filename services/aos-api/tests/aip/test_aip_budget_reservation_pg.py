"""Dedicated PostgreSQL proof for AR2-7 capability budget authority."""

import importlib.util
import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.rows import dict_row

from aos_api.aip_budget_reservation_contracts import BudgetExactRef, ReserveBudgetRequest
from aos_api.aip_budget_reservation_store import (
    AipBudgetReservationStore,
    BudgetReservationBlocked,
    BudgetReservationConflict,
    canonical_hash,
)
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import (
    ContentGenerateHostService,
    ReviewAdvanceHostService,
    TransactionBoundConnectFactory,
    _analysis_command_hash,
)
from aos_api.tenant_scope import TenantScope


pytestmark = pytest.mark.skipif(
    os.getenv("AOS_EXTENSION_PG_TEST") != "1",
    reason="dedicated PostgreSQL opt-in required",
)

PG = {
    "host": os.getenv("AOS_EXTENSION_PG_HOST", "127.0.0.1"),
    "port": int(os.getenv("AOS_EXTENSION_PG_PORT", "18432")),
    "user": os.getenv("AOS_EXTENSION_PG_USER", "postgres"),
    "dbname": os.getenv("AOS_EXTENSION_PG_DATABASE", "postgres"),
}
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def database():
    schema = "ar2_budget_" + uuid4().hex
    owner = psycopg.connect(**PG, autocommit=True, row_factory=dict_row)
    created_runtime = owner.execute(
        "SELECT 1 FROM pg_roles WHERE rolname='aos_runtime'"
    ).fetchone() is None
    if created_runtime:
        owner.execute("CREATE ROLE aos_runtime NOSUPERUSER NOBYPASSRLS NOLOGIN")
    owner.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    owner.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
    try:
        owner.execute(
            """CREATE TABLE aip_budget_revision(
            org_id text,project_id text,budget_id text,revision bigint,content_hash text,
            lifecycle text,daily_limit_minor bigint,monthly_limit_minor bigint,
            effective_from timestamptz,effective_until timestamptz,
            PRIMARY KEY(org_id,project_id,budget_id,revision))"""
        )
        owner.execute(
            """CREATE TABLE aip_model_price_snapshot_revision(
            org_id text,project_id text,model_price_snapshot_id text,revision bigint,
            content_hash text,lifecycle text,payload jsonb,
            PRIMARY KEY(org_id,project_id,model_price_snapshot_id,revision))"""
        )
        owner.execute(
            """CREATE TABLE aip_task(
            org_id text,project_id text,task_id text,task_type text,title text,description text,
            status text,priority integer,goal jsonb,selection_ref jsonb,policy_revision text,
            version bigint,created_by text,created_at timestamptz,
            PRIMARY KEY(org_id,project_id,task_id))"""
        )
        owner.execute(
            """CREATE TABLE aip_action_proposal(
            org_id text,project_id text,proposal_id text,action_type_id text,task_id text,
            action_type_snapshot jsonb,run_id text,object_ref jsonb,purpose text,risk_level text,
            policy_snapshot jsonb,payload jsonb,diff jsonb,evidence_refs jsonb,
            impact_preview_id text,impact_preview_revision bigint,impact_preview_hash text,
            action_binding_hash text,source_draft_id text,source_draft_revision bigint,
            source_draft_hash text,approval_policy_hash text,proposal_hash text,status text,
            expires_at timestamptz,created_by text,
            PRIMARY KEY(org_id,project_id,proposal_id))"""
        )
        owner.execute(
            """CREATE TABLE aip_action_draft(
            org_id text,project_id text,proposal_id text,proposal_hash text,snapshot jsonb,
            PRIMARY KEY(org_id,project_id,proposal_id))"""
        )
        owner.execute(
            """CREATE TABLE aip_action_approval_event(
            org_id text,project_id text,approval_event_id text,proposal_id text,
            proposal_version bigint,proposal_hash text,decision text,actor_id text,reason text,
            expires_at timestamptz,created_at timestamptz,action_binding_hash text,
            PRIMARY KEY(org_id,project_id,approval_event_id))"""
        )
        owner.execute(
            """CREATE TABLE aip_provider_instance_revision(
            org_id text,project_id text,provider_instance_id text,revision bigint,
            content_hash text,lifecycle text,
            PRIMARY KEY(org_id,project_id,provider_instance_id,revision))"""
        )
        owner.execute(
            """CREATE TABLE aip_usage_receipt(
            org_id text,project_id text,receipt_id text,provider text,provider_receipt_id text,
            lineage_id text,usage_kind text,quantity double precision,unit text,currency text,
            quality text,source_hash text,observed_at timestamptz,
            PRIMARY KEY(org_id,project_id,receipt_id))"""
        )
        spec = importlib.util.spec_from_file_location(
            "ar2_003_test", ROOT / "alembic/versions/ar2_003_ecommerce_budget_reservation.py"
        )
        migration = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(migration)
        migration.op = SimpleNamespace(execute=owner.execute)
        migration.upgrade()
        owner.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO aos_runtime").format(sql.Identifier(schema)))
        for table in (
            "aip_budget_revision",
            "aip_model_price_snapshot_revision",
            "aip_task",
            "aip_action_proposal",
            "aip_action_draft",
            "aip_action_approval_event",
            "aip_provider_instance_revision",
            "aip_usage_receipt",
        ):
            owner.execute(f"GRANT SELECT ON {table} TO aos_runtime")
        assert owner.execute(
            "SELECT NOT rolsuper AND NOT rolbypassrls AS safe FROM pg_roles WHERE rolname='aos_runtime'"
        ).fetchone()["safe"]
        yield SimpleNamespace(owner=owner, schema=schema, migration=migration)
    finally:
        owner.execute("RESET ROLE")
        if os.getenv('AOS_TEST_RETAIN_DATABASE') == '1':
            print('Retained isolated budget schema:',schema)
        else:
            owner.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
            if created_runtime:
                owner.execute("DROP ROLE aos_runtime")
        owner.close()


def runtime_connection(database):
    @contextmanager
    def connection(scope):
        conn = psycopg.connect(**PG, autocommit=False, row_factory=dict_row)
        try:
            conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(database.schema)))
            conn.execute("SET ROLE aos_runtime")
            conn.execute("SELECT set_config('aos.org_id',%s,false)", (scope.org_id,))
            conn.execute("SELECT set_config('aos.project_id',%s,false)", (scope.project_id,))
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    return connection


@contextmanager
def direct_runtime_connection(database, scope: TenantScope):
    """Open an autocommit runtime session for database-trigger rejection proofs."""
    conn = psycopg.connect(**PG, autocommit=True, row_factory=dict_row)
    try:
        conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(database.schema)))
        conn.execute("SET ROLE aos_runtime")
        conn.execute("SELECT set_config('aos.org_id',%s,false)", (scope.org_id,))
        conn.execute("SELECT set_config('aos.project_id',%s,false)", (scope.project_id,))
        yield conn
    finally:
        conn.close()


def seed(database, scope: TenantScope, *, task_id: str, upper: int = 400, now=None):
    now = now or datetime.now(UTC)
    owner = database.owner
    owner.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(database.schema)))
    budget_hash = "1" * 64
    price_content = {
        "priceSnapshotId": "price-1",
        "currency": "CNY",
        "inputTokenPrice": 0.0025,
        "outputTokenPrice": 0.005,
        "cachedTokenPrice": 0.001,
        "tokenUnit": 1000,
        "effectiveFrom": "2026-09-01T00:00:00+00:00",
        "effectiveUntil": "2026-10-31T00:00:00+00:00",
        "lifecycle": "active",
    }
    price_hash = canonical_hash(price_content)
    price_payload = {
        "tenant": {"orgId": scope.org_id, "projectId": scope.project_id},
        "revision": 1,
        "contentHash": price_hash,
        **price_content,
        "createdBy": "tester",
        "createdAt": "2026-09-08T02:00:00+00:00",
    }
    provider_hash = "3" * 64
    owner.execute(
        """INSERT INTO aip_budget_revision VALUES(%s,%s,'budget-1',1,%s,'active',
        500,900,%s,%s) ON CONFLICT DO NOTHING""",
        (*scope.key, budget_hash, now - timedelta(days=2), now + timedelta(days=40)),
    )
    owner.execute(
        """INSERT INTO aip_model_price_snapshot_revision VALUES(
        %s,%s,'price-1',1,%s,'active',%s::jsonb) ON CONFLICT DO NOTHING""",
        (
            *scope.key,
            price_hash,
            AipBudgetReservationStore._json(price_payload),
        ),
    )
    owner.execute(
        """INSERT INTO aip_provider_instance_revision VALUES(
        %s,%s,'provider-1',1,%s,'active') ON CONFLICT DO NOTHING""",
        (*scope.key, provider_hash),
    )
    owner.execute(
        """INSERT INTO aip_task VALUES(
        %s,%s,%s,'content','生成商城内容','依据经营方案生成内容','approved',50,
        '{}'::jsonb,NULL,NULL,1,'tester',%s)""",
        (*scope.key, task_id, now),
    )
    task_row = owner.execute(
        """SELECT task_id,task_type,title,description,status,priority,goal,selection_ref,
        policy_revision,version,created_by,created_at FROM aip_task
        WHERE org_id=%s AND project_id=%s AND task_id=%s""",
        (*scope.key, task_id),
    ).fetchone()
    approval_id = f"approval-{task_id}"
    proposal_id = f"proposal-{task_id}"
    action_binding_hash = "5" * 64
    proposal_expires_at = now + timedelta(days=7)
    action_type_snapshot = {"id": "ecommerce_growth_content_generate"}
    policy_snapshot = {"minimumApprovals": 1}
    approval_policy_hash = canonical_hash(policy_snapshot)
    proposal_payload = {"budgetUpperBoundMinor": upper}
    stable = {
        "tenantScope": {"orgId": scope.org_id, "projectId": scope.project_id},
        "createdBy": "tester",
        "actionType": action_type_snapshot,
        "taskId": task_id,
        "runId": None,
        "objectRef": None,
        "purpose": "receipt-first content generation",
        "riskLevel": "R1",
        "policy": policy_snapshot,
        "approvalPolicyHash": approval_policy_hash,
        "payload": proposal_payload,
        "diff": {},
        "evidenceRefs": [],
        "impactPreviewRef": None,
        "actionBindingHash": action_binding_hash,
        "sourceDraftRef": None,
        "expiresAt": proposal_expires_at.isoformat(),
    }
    proposal_hash = canonical_hash(stable)
    owner.execute(
        """INSERT INTO aip_action_proposal VALUES(
        %s,%s,%s,'ecommerce_growth_content_generate',%s,%s::jsonb,NULL,NULL,
        'receipt-first content generation','R1',%s::jsonb,%s::jsonb,'{}'::jsonb,'[]'::jsonb,
        NULL,NULL,NULL,%s,NULL,NULL,NULL,%s,%s,'approved',%s,%s)""",
        (
            *scope.key,
            proposal_id,
            task_id,
            AipBudgetReservationStore._json(action_type_snapshot),
            AipBudgetReservationStore._json(policy_snapshot),
            AipBudgetReservationStore._json(proposal_payload),
            action_binding_hash,
            approval_policy_hash,
            proposal_hash,
            proposal_expires_at,
            "tester",
        ),
    )
    owner.execute(
        """INSERT INTO aip_action_draft VALUES(%s,%s,%s,%s,%s::jsonb)""",
        (*scope.key, proposal_id, proposal_hash, AipBudgetReservationStore._json(stable)),
    )
    owner.execute(
        """INSERT INTO aip_action_approval_event VALUES(
        %s,%s,%s,%s,1,%s,'approved','reviewer','同意内部内容生成',%s,%s,%s)""",
        (
            *scope.key,
            approval_id,
            proposal_id,
            proposal_hash,
            now + timedelta(days=2),
            now,
            action_binding_hash,
        ),
    )
    approval_row = owner.execute(
        """SELECT approval_event_id,proposal_id,proposal_version,proposal_hash,decision,
        actor_id,reason,expires_at,created_at,action_binding_hash
        FROM aip_action_approval_event
        WHERE org_id=%s AND project_id=%s AND approval_event_id=%s""",
        (*scope.key, approval_id),
    ).fetchone()
    refs = {
        "task": BudgetExactRef(resourceType="Task", resourceId=task_id, revision=1,
            contentHash=canonical_hash(dict(task_row), prefixed=True)),
        "budget": BudgetExactRef(resourceType="BudgetRevision", resourceId="budget-1", revision=1,
            contentHash=f"sha256:{budget_hash}"),
        "price": BudgetExactRef(resourceType="ModelPriceSnapshotRevision", resourceId="price-1",
            revision=1, contentHash=f"sha256:{price_hash}"),
        "approval": BudgetExactRef(resourceType="ActionApprovalEvent", resourceId=approval_id,
            revision=1, contentHash=canonical_hash(dict(approval_row), prefixed=True)),
        "provider": BudgetExactRef(resourceType="ProviderInstanceRevision", resourceId="provider-1",
            revision=1, contentHash=f"sha256:{provider_hash}"),
    }
    request = ReserveBudgetRequest(
        operationId="ecommerce_growth_content_generate",
        invocationKey=f"invoke-{task_id}",
        taskRef=refs["task"], policyRef=refs["budget"], pricingRef=refs["price"],
        approvalRef=refs["approval"], currency="CNY", upperBoundMinor=upper,
    )
    return request, refs, now


def seed_usage(
    database,
    scope: TenantScope,
    *,
    receipt_id: str,
    quantity: float,
    reservation_id: str,
    provider_result_hash: str,
):
    database.owner.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(database.schema)))
    invocation_id = database.owner.execute(
        """SELECT invocation_id FROM aip_budget_reservation
        WHERE org_id=%s AND project_id=%s AND reservation_id=%s""",
        (*scope.key, reservation_id),
    ).fetchone()["invocation_id"]
    database.owner.execute(
        """INSERT INTO aip_usage_receipt VALUES(
        %s,%s,%s,'provider-1','provider-result-1',%s,'input_token',
        %s,'token',NULL,'measured',%s,%s)""",
        (
            *scope.key,
            receipt_id,
            str(invocation_id),
            quantity,
            provider_result_hash,
            datetime(2026, 9, 8, 3, tzinfo=UTC),
        ),
    )
    row = database.owner.execute(
        """SELECT receipt_id,provider,provider_receipt_id,lineage_id,usage_kind,
        quantity,unit,currency,quality,source_hash,observed_at FROM aip_usage_receipt
        WHERE org_id=%s AND project_id=%s AND receipt_id=%s""",
        (*scope.key, receipt_id),
    ).fetchone()
    return BudgetExactRef(
        resourceType="UsageReceipt", resourceId=receipt_id, revision=1,
        contentHash=canonical_hash(dict(row), prefixed=True),
    )


def content_generate_command(request: ReserveBudgetRequest) -> dict[str, object]:
    extra = {
        "handoff": "HandoffReceipt",
        "brief": "TaskBriefRevision",
        "growth_plan": "GrowthPlanRevision",
        "agent_instance": "AgentInstanceRevision",
        "responsibility_plan": "ResponsibilityPlanRevision",
        "capability": "CapabilityRevision",
        "model_route": "ModelRouteRevision",
        "capacity_reservation": "CapacityReservation",
    }

    def ref(kind: str, identity: str, digit: str) -> dict[str, object]:
        return {
            "resourceType": kind,
            "resourceId": identity,
            "revision": 1,
            "contentHash": "sha256:" + digit * 64,
        }

    authorities = {
        name: ref(kind, name, format(index + 6, "x")[-1])
        for index, (name, kind) in enumerate(extra.items())
    }
    authorities.update(
        {
            "task": request.task_ref.model_dump(mode="json", by_alias=True),
            "budget": request.policy_ref.model_dump(mode="json", by_alias=True),
            "pricing": request.pricing_ref.model_dump(mode="json", by_alias=True),
            "approval": request.approval_ref.model_dump(mode="json", by_alias=True),
        }
    )
    command = {
        "operation": "content.generate",
        "authorityRefs": authorities,
        "sourceArtifactRefs": [
            ref("ArtifactRevision", f"artifact-{digit}", digit)
            for digit in ("a", "b", "c", "d")
        ],
        "factSourceRefs": [ref("EvidenceBundleRevision", "facts", "e")],
        "currency": "CNY",
        "upperBoundFen": request.upper_bound_minor,
        "maxInputTokens": 1000,
        "maxOutputTokens": 500,
        "idempotencyKey": request.invocation_key,
    }
    command["requestHash"] = _analysis_command_hash(command)
    return command


def test_content_generate_host_persists_and_replays_no_provider_receipt(
    database, monkeypatch
):
    scope = TenantScope("org-org", "dev-project")
    request, _refs, _now = seed(database, scope, task_id="task-content-host")
    command = content_generate_command(request)
    monkeypatch.setattr(
        ReviewAdvanceHostService, "_revalidate_growth_plan",
        staticmethod(lambda **_: SimpleNamespace(sales_weapon_method=None)),
    )

    def store_for(transaction, bound_scope):
        return AipBudgetReservationStore(
            TransactionBoundConnectFactory(transaction, bound_scope),
            authority_schema=database.schema,
        )

    monkeypatch.setattr(
        ContentGenerateHostService,
        "_budget_store",
        staticmethod(store_for),
    )
    monkeypatch.setattr(
        ContentGenerateHostService,
        "_runtime_command_authority",
        staticmethod(lambda *_args: None),
    )
    with runtime_connection(database)(scope) as conn:
        transaction = HostTransaction(conn)
        service = ContentGenerateHostService()
        first = service.execute(
            transaction=transaction,
            scope=scope,
            dispatch_ref=object(),
            command=command,
            checked_at=None,
            occurred_at=None,
        )
        assert service.verify_receipt(
            transaction=transaction,
            scope=scope,
            dispatch=object(),
            command=command,
            receipt=first,
        ) == first
        replay = service.execute(
            transaction=transaction,
            scope=scope,
            dispatch_ref=object(),
            command=command,
            checked_at=None,
            occurred_at=None,
        )

    assert first["state"] == "FAILED_NO_EFFECT" and first["replayed"] is False
    assert replay == {**first, "replayed": True}
    reservation = database.owner.execute(
        """SELECT state,provider_request_receipt_ref,provider_receipt_ref,
                  usage_receipt_refs,actual_minor,reconciliation_evidence_ref
             FROM aip_budget_reservation
            WHERE org_id=%s AND project_id=%s AND invocation_key=%s""",
        (*scope.key, request.invocation_key),
    ).fetchone()
    invocation = database.owner.execute(
        """SELECT state FROM aip_capability_invocation
            WHERE org_id=%s AND project_id=%s AND invocation_key=%s""",
        (*scope.key, request.invocation_key),
    ).fetchone()
    buckets = database.owner.execute(
        """SELECT held_minor,submitted_minor,unknown_minor
             FROM aip_budget_bucket WHERE org_id=%s AND project_id=%s""",
        scope.key,
    ).fetchall()
    assert reservation == {
        "state": "released",
        "provider_request_receipt_ref": None,
        "provider_receipt_ref": None,
        "usage_receipt_refs": [],
        "actual_minor": None,
        "reconciliation_evidence_ref": None,
    }
    assert invocation == {"state": "failed"}
    assert len(buckets) == 3
    assert all(
        row["held_minor"] == row["submitted_minor"] == row["unknown_minor"] == 0
        for row in buckets
    )
    assert database.owner.execute(
        """SELECT count(*) AS total FROM aip_capability_provider_request_receipt
            WHERE org_id=%s AND project_id=%s""",
        scope.key,
    ).fetchone()["total"] == 0


def test_budget_store_ignores_same_name_temp_storage_shadow(database):
    scope = TenantScope("org-org", "dev-project")
    request, _refs, _now = seed(database, scope, task_id="task-storage-shadow")
    with runtime_connection(database)(scope) as conn:
        conn.execute("CREATE TEMP TABLE aip_budget_reservation(dummy text)")

        @contextmanager
        def bound_connection(_scope):
            yield conn

        store = AipBudgetReservationStore(
            bound_connection,
            authority_schema=database.schema,
        )
        held = store.reserve(scope, request, actor="tester")
    assert held.state == "held"


def test_budget_get_rejects_tampered_invocation_owner(database):
    scope = TenantScope("org-org", "dev-project")
    request, _refs, _now = seed(database, scope, task_id="task-owner-tamper")
    store = AipBudgetReservationStore(
        runtime_connection(database), authority_schema=database.schema
    )
    held = store.reserve(scope, request, actor="tester")
    database.owner.execute("ALTER TABLE aip_capability_invocation DISABLE TRIGGER ALL")
    try:
        database.owner.execute(
            """UPDATE aip_capability_invocation SET state='submitted'
                WHERE org_id=%s AND project_id=%s AND invocation_id=%s""",
            (*scope.key, held.invocation_ref.resource_id),
        )
    finally:
        database.owner.execute("ALTER TABLE aip_capability_invocation ENABLE TRIGGER ALL")
    with pytest.raises(BudgetReservationConflict, match="Owner authority drifted"):
        store.get(scope, held.reservation_ref.resource_id)


def test_budget_get_rejects_raw_bool_ref_drift_after_release(database):
    scope = TenantScope("org-org", "dev-project")
    request, _refs, _now = seed(database, scope, task_id="task-ref-bool-tamper")
    store = AipBudgetReservationStore(
        runtime_connection(database), authority_schema=database.schema
    )
    held = store.reserve(scope, request, actor="tester")
    released = store.release_no_effect(
        scope, held.reservation_ref.resource_id, actor="tester"
    )
    database.owner.execute("ALTER TABLE aip_budget_reservation DISABLE TRIGGER ALL")
    try:
        database.owner.execute(
            """UPDATE aip_budget_reservation
                  SET task_ref=jsonb_set(task_ref,'{revision}','true'::jsonb)
                WHERE org_id=%s AND project_id=%s AND reservation_id=%s""",
            (*scope.key, released.reservation_ref.resource_id),
        )
    finally:
        database.owner.execute("ALTER TABLE aip_budget_reservation ENABLE TRIGGER ALL")
    with pytest.raises(BudgetReservationConflict, match="Owner authority drifted"):
        store.get(scope, released.reservation_ref.resource_id)


def test_rls_state_machine_unknown_reconcile_and_nonempty_downgrade(database):
    positive = TenantScope("org-org", "dev-project")
    canary = TenantScope("dev-org", "dev-project")
    request, refs, _ = seed(database, positive, task_id="task-1")
    store = AipBudgetReservationStore(
        runtime_connection(database), authority_schema=database.schema
    )
    held = store.reserve(positive, request, actor="tester")
    assert held.state == "held" and not held.replayed
    invocation = database.owner.execute(
        """SELECT * FROM aip_capability_invocation
        WHERE org_id=%s AND project_id=%s AND invocation_id=%s""",
        (*positive.key, held.invocation_ref.resource_id),
    ).fetchone()
    assert held.invocation_ref.content_hash == canonical_hash(
        store._invocation_payload(invocation, invocation["state"], invocation["revision"]),
        prefixed=True,
    )
    assert store.reserve(positive, request, actor="tester").replayed
    with direct_runtime_connection(database, positive) as conn:
        with pytest.raises(
            psycopg.errors.RaiseException,
            match="invalid budget reservation transition|state shape drifted",
        ):
            conn.execute(
                """UPDATE aip_budget_reservation SET state='settled',revision=revision+1,
                content_hash=%s,updated_at=clock_timestamp()
                WHERE org_id=%s AND project_id=%s AND reservation_id=%s""",
                ("8" * 64, *positive.key, held.reservation_ref.resource_id),
            )
        with pytest.raises(psycopg.errors.RaiseException, match="bucket authority drifted"):
            conn.execute(
                """UPDATE aip_budget_bucket SET limit_minor=limit_minor+1,
                version=version+1,updated_at=clock_timestamp()
                WHERE org_id=%s AND project_id=%s""",
                positive.key,
            )
    submitted = store.submit(
        positive, held.reservation_ref.resource_id, provider_ref=refs["provider"],
        provider_idempotency_hash="5" * 64, actor="tester"
    )
    assert submitted.state == "submitted"
    unknown = store.mark_unknown(positive, held.reservation_ref.resource_id, actor="tester")
    assert unknown.state == "unknown"
    with pytest.raises(BudgetReservationBlocked):
        store.release_no_effect(positive, held.reservation_ref.resource_id, actor="tester")
    released = store.release_no_effect(
        positive, held.reservation_ref.resource_id, actor="tester",
        provider_result_hash="6" * 64,
    )
    assert released.state == "released" and released.reconciliation_evidence_ref is not None
    assert store.release_no_effect(
        positive,
        held.reservation_ref.resource_id,
        actor="tester",
        provider_result_hash="6" * 64,
    ).replayed
    with pytest.raises(BudgetReservationConflict, match="replay drifted"):
        store.release_no_effect(
            positive,
            held.reservation_ref.resource_id,
            actor="tester",
            provider_result_hash="7" * 64,
        )
    with pytest.raises(Exception):
        store.get(canary, held.reservation_ref.resource_id)
    with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState):
        database.migration.downgrade()


def test_same_bucket_concurrency_allows_only_one_reservation(database):
    scope = TenantScope("org-org", "dev-project")
    first, _, _ = seed(database, scope, task_id="task-a", upper=400)
    second, _, _ = seed(database, scope, task_id="task-b", upper=400)
    barrier = Barrier(2)

    def reserve(request):
        barrier.wait()
        try:
            AipBudgetReservationStore(
                runtime_connection(database), authority_schema=database.schema
            ).reserve(
                scope, request, actor="tester"
            )
            return "held"
        except BudgetReservationBlocked:
            return "blocked"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(reserve, (first, second)))
    assert sorted(outcomes) == ["blocked", "held"]


def test_same_invocation_concurrency_returns_one_exact_authority(database):
    scope = TenantScope("org-org", "dev-project")
    request, _, _ = seed(database, scope, task_id="task-same")
    barrier = Barrier(2)

    def reserve_same(_index):
        barrier.wait()
        return AipBudgetReservationStore(
            runtime_connection(database), authority_schema=database.schema
        ).reserve(
            scope, request, actor="tester"
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(reserve_same, range(2)))
    assert len({item.reservation_ref.resource_id for item in results}) == 1
    assert sorted(item.replayed for item in results) == [False, True]


def test_settlement_is_derived_from_exact_usage_and_is_unique(database):
    scope = TenantScope("org-org", "dev-project")
    request, refs, _ = seed(database, scope, task_id="task-settle")
    provider_result_hash = "9" * 64
    store = AipBudgetReservationStore(
        runtime_connection(database), authority_schema=database.schema
    )
    held = store.reserve(scope, request, actor="tester")
    store.submit(
        scope, held.reservation_ref.resource_id, provider_ref=refs["provider"],
        provider_idempotency_hash="8" * 64, actor="tester",
    )
    usage_ref = seed_usage(
        database,
        scope,
        receipt_id="usage-1",
        quantity=2000,
        reservation_id=held.reservation_ref.resource_id,
        provider_result_hash=provider_result_hash,
    )
    with pytest.raises(Exception, match="actual amount differs"):
        store.settle(
            scope, held.reservation_ref.resource_id, actual_minor=2,
            provider_result_hash=provider_result_hash, usage_receipt_refs=(usage_ref,),
            evidence_refs=(), actor="tester",
        )
    settled = store.settle(
        scope, held.reservation_ref.resource_id, actual_minor=1,
        provider_result_hash=provider_result_hash, usage_receipt_refs=(usage_ref,),
        evidence_refs=(), actor="tester",
    )
    assert settled.state == "settled" and settled.actual_minor == 1
    assert all(bucket.settled_minor == 1 for bucket in settled.buckets)
    assert store.settle(
        scope,
        held.reservation_ref.resource_id,
        actual_minor=1,
        provider_result_hash=provider_result_hash,
        usage_receipt_refs=(usage_ref,),
        evidence_refs=(),
        actor="tester",
    ).replayed
    with pytest.raises(BudgetReservationConflict, match="replay drifted"):
        store.settle(
            scope,
            held.reservation_ref.resource_id,
            actual_minor=1,
            provider_result_hash="a" * 64,
            usage_receipt_refs=(usage_ref,),
            evidence_refs=(),
            actor="tester",
        )


def test_usage_approval_price_and_runtime_privileges_fail_closed(database):
    scope = TenantScope("org-org", "dev-project")
    canary = TenantScope("dev-org", "dev-project")
    first, first_refs, _ = seed(database, scope, task_id="task-bind-a", upper=200)
    second, second_refs, _ = seed(database, scope, task_id="task-bind-b", upper=200)
    store = AipBudgetReservationStore(
        runtime_connection(database), authority_schema=database.schema
    )

    wrong_approval = second.model_copy(update={"approval_ref": first_refs["approval"]})
    with pytest.raises(BudgetReservationBlocked, match="approval must bind"):
        store.reserve(scope, wrong_approval, actor="tester")

    database.owner.execute(
        """UPDATE aip_action_proposal
        SET payload=jsonb_set(payload,'{budgetUpperBoundMinor}','300'::jsonb)
        WHERE org_id=%s AND project_id=%s AND proposal_id=%s""",
        (*scope.key, "proposal-task-bind-a"),
    )
    with pytest.raises(BudgetReservationBlocked, match="approval must bind"):
        store.reserve(scope, first, actor="tester")
    database.owner.execute(
        """UPDATE aip_action_proposal
        SET payload=jsonb_set(payload,'{budgetUpperBoundMinor}','200'::jsonb)
        WHERE org_id=%s AND project_id=%s AND proposal_id=%s""",
        (*scope.key, "proposal-task-bind-a"),
    )

    database.owner.execute(
        """UPDATE aip_model_price_snapshot_revision
        SET payload=jsonb_set(payload,'{inputTokenPrice}','0.003'::jsonb)
        WHERE org_id=%s AND project_id=%s AND model_price_snapshot_id='price-1'""",
        scope.key,
    )
    with pytest.raises(BudgetReservationBlocked, match="ModelPriceSnapshotRevision"):
        store.reserve(scope, first, actor="tester")
    database.owner.execute(
        """UPDATE aip_model_price_snapshot_revision
        SET payload=jsonb_set(payload,'{inputTokenPrice}','0.0025'::jsonb)
        WHERE org_id=%s AND project_id=%s AND model_price_snapshot_id='price-1'""",
        scope.key,
    )

    held_first = store.reserve(scope, first, actor="tester")
    held_second = store.reserve(scope, second, actor="tester")
    for held, refs in ((held_first, first_refs), (held_second, second_refs)):
        store.submit(
            scope,
            held.reservation_ref.resource_id,
            provider_ref=refs["provider"],
            provider_idempotency_hash="b" * 64,
            actor="tester",
        )
    usage_first = seed_usage(
        database,
        scope,
        receipt_id="usage-crosswire",
        quantity=1000,
        reservation_id=held_first.reservation_ref.resource_id,
        provider_result_hash="c" * 64,
    )
    with pytest.raises(BudgetReservationBlocked, match="bound to this invocation"):
        store.settle(
            scope,
            held_second.reservation_ref.resource_id,
            actual_minor=0,
            provider_result_hash="c" * 64,
            usage_receipt_refs=(usage_first,),
            evidence_refs=(),
            actor="tester",
        )

    no_scope = psycopg.connect(**PG, autocommit=True, row_factory=dict_row)
    try:
        no_scope.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(database.schema)))
        no_scope.execute("SET ROLE aos_runtime")
        assert no_scope.execute("SELECT count(*) AS n FROM aip_budget_reservation").fetchone()["n"] == 0
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            no_scope.execute("TRUNCATE aip_budget_reservation_event")
    finally:
        no_scope.close()
    with direct_runtime_connection(database, canary) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                """INSERT INTO aip_budget_reservation_event(
                org_id,project_id,event_id,reservation_id,sequence,to_state,actor,event_hash)
                VALUES(%s,%s,%s,%s,99,'held','tester',%s)""",
                (*scope.key, uuid4(), held_first.reservation_ref.resource_id, "d" * 71),
            )
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                "DELETE FROM aip_budget_reservation_event WHERE org_id=%s AND project_id=%s",
                scope.key,
            )


def test_empty_migration_can_downgrade(database):
    database.migration.downgrade()
    assert database.owner.execute(
        "SELECT to_regclass('aip_budget_reservation') IS NULL AS gone"
    ).fetchone()["gone"]
