from __future__ import annotations

import importlib.util
import os
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg import IsolationLevel
from psycopg.rows import dict_row
from pydantic import ValidationError

from aos_api.aip_budget_reservation_store import canonical_hash
from aos_api.automation_occurrence_store import AutomationOccurrenceStore
from aos_api.ecommerce_growth_cutover import (
    CutoverCommitRequest,
    CutoverExactRef,
    CutoverPrepareRequest,
    EcommerceGrowthCutoverBlocked,
    EcommerceGrowthCutoverConflict,
    EcommerceGrowthCutoverStore,
)
from aos_api.ecommerce_growth_host_composition import ECOMMERCE_GROWTH_OPERATIONS
from aos_api.tenant_scope import TenantScope


pytestmark = pytest.mark.skipif(
    os.getenv("AOS_EXTENSION_PG_TEST") != "1",
    reason="dedicated database opt-in required",
)

PG = {
    "host": os.getenv("AOS_EXTENSION_PG_HOST", "127.0.0.1"),
    "port": int(os.getenv("AOS_EXTENSION_PG_PORT", "18434")),
    "user": os.getenv("AOS_EXTENSION_PG_USER", "aos_test"),
    "dbname": os.getenv("AOS_EXTENSION_PG_DATABASE", "aos_test_admin"),
}


def _migration(root: Path, filename: str, owner, *, schema: str | None = None) -> None:
    spec = importlib.util.spec_from_file_location(filename, root / "alembic/versions" / filename)
    migration = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(migration)
    def execute(statement):
        if schema is not None:
            statement = statement.replace("public.", f"{schema}.")
        return owner.execute(statement)
    migration.op = SimpleNamespace(execute=execute)
    migration.upgrade()


@pytest.fixture
def database():
    schema = "ar2_cutover_" + uuid4().hex
    role = "ar2_cutover_" + uuid4().hex[:16]
    owner = psycopg.connect(**PG, autocommit=True, row_factory=dict_row)
    created_runtime = owner.execute("SELECT 1 FROM pg_roles WHERE rolname='aos_runtime'").fetchone() is None
    if created_runtime:
        owner.execute("CREATE ROLE aos_runtime NOSUPERUSER NOBYPASSRLS NOLOGIN")
    owner.execute(sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS NOINHERIT").format(sql.Identifier(role)))
    owner.execute(sql.SQL("GRANT aos_extension_maintainer TO {}").format(sql.Identifier(role)))
    owner.execute(sql.SQL("GRANT aos_runtime TO {}").format(sql.Identifier(role)))
    try:
        owner.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        owner.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
        owner.execute(
            """CREATE TABLE bundle_installation(
                 org_id text NOT NULL,project_id text NOT NULL,installation_id uuid NOT NULL,
                 etag_version bigint NOT NULL DEFAULT 1,
                 PRIMARY KEY(org_id,project_id,installation_id))"""
        )
        root = Path(__file__).resolve().parents[2]
        _migration(root, "ar1_001_extension_runtime_authority.py", owner)
        _migration(root, "ar1_004_runtime_execution_attempt.py", owner)
        _migration(root, "ar2_001_ecommerce_dispatch_authority.py", owner)
        _migration(root, "ar2_002_automation_occurrence.py", owner)
        owner.execute(
            """CREATE TABLE aip_action_proposal(
                 org_id text NOT NULL,project_id text NOT NULL,proposal_id text NOT NULL,
                 action_type_id text NOT NULL,action_type_snapshot jsonb NOT NULL,
                 task_id text,run_id text,object_ref jsonb,purpose text NOT NULL,risk_level text NOT NULL,
                 policy_snapshot jsonb NOT NULL,payload jsonb NOT NULL,diff jsonb NOT NULL,
                 evidence_refs jsonb NOT NULL,impact_preview_id text,impact_preview_revision bigint,
                 impact_preview_hash text,action_binding_hash text,source_draft_id text,
                 source_draft_revision bigint,source_draft_hash text,approval_policy_hash text,
                 proposal_hash text NOT NULL,status text NOT NULL,version bigint NOT NULL,
                 expires_at timestamptz NOT NULL,
                 created_by text NOT NULL,
                 PRIMARY KEY(org_id,project_id,proposal_id))"""
        )
        owner.execute(
            """CREATE TABLE aip_action_draft(
                 org_id text NOT NULL,project_id text NOT NULL,proposal_id text NOT NULL,
                 proposal_hash text NOT NULL,snapshot jsonb NOT NULL,
                 PRIMARY KEY(org_id,project_id,proposal_id))"""
        )
        owner.execute(
            """CREATE TABLE aip_action_approval_event(
                 org_id text NOT NULL,project_id text NOT NULL,approval_event_id text NOT NULL,
                 proposal_id text NOT NULL,proposal_version bigint NOT NULL,proposal_hash text NOT NULL,
                 decision text NOT NULL,actor_id text NOT NULL,reason text NOT NULL,
                 expires_at timestamptz,created_at timestamptz NOT NULL,action_binding_hash text,
                 PRIMARY KEY(org_id,project_id,approval_event_id))"""
        )
        for table in ("aip_action_proposal", "aip_action_draft", "aip_action_approval_event"):
            owner.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            owner.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
            owner.execute(
                f"""CREATE POLICY tenant_scope ON {table}
                  USING(org_id=current_setting('aos.org_id',true)
                    AND project_id=current_setting('aos.project_id',true))
                  WITH CHECK(org_id=current_setting('aos.org_id',true)
                    AND project_id=current_setting('aos.project_id',true))"""
            )
        _migration(root, "ar2_013_ecommerce_growth_cutover.py", owner, schema=schema)
        _migration(root, "ar2_014_ecommerce_growth_cutover_commit.py", owner, schema=schema)
        owner.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO aos_extension_maintainer").format(sql.Identifier(schema)))
        owner.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO aos_runtime").format(sql.Identifier(schema)))
        yield SimpleNamespace(owner=owner, schema=schema, role=role, root=root)
    finally:
        owner.execute("RESET ROLE")
        owner.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
        owner.execute(sql.SQL("REVOKE aos_extension_maintainer FROM {}").format(sql.Identifier(role)))
        owner.execute(sql.SQL("REVOKE aos_runtime FROM {}").format(sql.Identifier(role)))
        owner.execute(sql.SQL("DROP ROLE {} ").format(sql.Identifier(role)))
        if created_runtime:
            owner.execute("DROP ROLE aos_runtime")
        owner.close()


def _connection(
    database, *, shadow: bool = False, runtime: bool = False, serializable: bool = True
):
    @contextmanager
    def connect(scope):
        conn = psycopg.connect(**{**PG, "user": database.role}, autocommit=False, row_factory=dict_row)
        try:
            if serializable:
                conn.isolation_level = IsolationLevel.SERIALIZABLE
            conn.execute("SET ROLE aos_runtime" if runtime else "SET ROLE aos_extension_maintainer")
            conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(database.schema)))
            conn.execute("SELECT set_config('aos.org_id',%s,true)", (scope.org_id,))
            conn.execute("SELECT set_config('aos.project_id',%s,true)", (scope.project_id,))
            if shadow:
                conn.execute("CREATE TEMP TABLE extension_operation_dispatch_binding(operation_id text)")
                conn.execute("CREATE TEMP TABLE extension_dispatch_cutover_operation(idempotency_key text)")
            yield conn
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    return connect


def _seed(
    database, scope: TenantScope, *, complete: bool = True, ready: bool = True,
    pending_receipt: bool = True,
    approval_lifetime: timedelta = timedelta(hours=1),
):
    owner = database.owner
    owner.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(database.schema)))
    installation, generation, group = uuid4(), uuid4(), uuid4()
    owner.execute(
        "INSERT INTO bundle_installation(org_id,project_id,installation_id) VALUES(%s,%s,%s)",
        (*scope.key, installation),
    )
    owner.execute(
        """INSERT INTO extension_runtime_binding(
             org_id,project_id,installation_id,generation,installation_revision,package_lock_ref,
             profile_ref,config_ref,execution_epoch,desired_state,observed_state,enabled,
             operation_fence,revision)
           VALUES(%s,%s,%s,%s,2,'{}','internal-python-v1','{}',7,'enabled',%s,%s,false,13)""",
        (*scope.key, installation, generation, "ready" if ready else "unknown", ready),
    )
    operations = sorted(ECOMMERCE_GROWTH_OPERATIONS)
    if not complete:
        operations = operations[:-1]
    for operation_id in operations:
        owner.execute(
            """INSERT INTO extension_operation_dispatch_binding(
                 org_id,project_id,operation_id,handler_kind,operation_fence,revision,
                 cutover_group_id,cutover_group_revision,updated_by)
               VALUES(%s,%s,%s,'legacy',false,5,%s,11,'legacy-owner')""",
            (*scope.key, operation_id, group),
        )
    policy_ref = CutoverExactRef(
        resourceType="RuntimeCutoverPolicyRevision", resourceId="cutover-policy", revision=4,
        contentHash="sha256:" + "1" * 64,
    )
    payload = {
        "cutoverGroupId": str(group),
        "expectedGroupRevision": 11,
        "targetInstallationId": str(installation),
        "targetGeneration": str(generation),
        "targetExecutionEpoch": 7,
        "targetRuntimeRevision": 13,
        "operationIds": sorted(ECOMMERCE_GROWTH_OPERATIONS),
        "policyRef": policy_ref.model_dump(mode="json", by_alias=True),
    }
    now = datetime.now(timezone.utc)
    action_type = {"id": "ecommerce_growth_cutover", "revisionHash": "sha256:" + "3" * 64}
    policy = {"mode": "manual-reviewed"}
    expires_at = now + approval_lifetime
    stable = {
        "tenantScope": {"orgId": scope.org_id, "projectId": scope.project_id},
        "actionType": action_type,
        "taskId": None,
        "runId": None,
        "objectRef": None,
        "purpose": "切换经营参谋九项宿主入口",
        "riskLevel": "R3",
        "policy": policy,
        "payload": payload,
        "diff": {},
        "evidenceRefs": [],
        "approvalPolicyHash": "sha256:" + "4" * 64,
        "actionBindingHash": "sha256:" + "5" * 64,
        "impactPreviewRef": None,
        "sourceDraftRef": None,
        "expiresAt": expires_at.isoformat(),
        "createdBy": "operator",
    }
    proposal_hash = canonical_hash(stable)
    owner.execute(
        """INSERT INTO aip_action_proposal(
             org_id,project_id,proposal_id,action_type_id,action_type_snapshot,task_id,run_id,
             object_ref,purpose,risk_level,policy_snapshot,payload,diff,evidence_refs,
             action_binding_hash,approval_policy_hash,proposal_hash,status,version,expires_at,created_by)
           VALUES(%s,%s,'proposal-cutover','ecommerce_growth_cutover',%s,NULL,NULL,NULL,%s,'R3',
             %s,%s,'{}','[]',%s,%s,%s,'approved',3,%s,'operator')""",
        (*scope.key, psycopg.types.json.Jsonb(action_type), stable["purpose"],
         psycopg.types.json.Jsonb(policy), psycopg.types.json.Jsonb(payload),
         stable["actionBindingHash"], stable["approvalPolicyHash"], proposal_hash,
         expires_at),
    )
    owner.execute(
        """INSERT INTO aip_action_draft(org_id,project_id,proposal_id,proposal_hash,snapshot)
           VALUES(%s,%s,'proposal-cutover',%s,%s)""",
        (*scope.key, proposal_hash, psycopg.types.json.Jsonb(stable)),
    )
    owner.execute(
        """INSERT INTO aip_action_approval_event(
             org_id,project_id,approval_event_id,proposal_id,proposal_version,proposal_hash,
             decision,actor_id,reason,expires_at,created_at,action_binding_hash)
           VALUES(%s,%s,'approval-cutover','proposal-cutover',3,%s,
             'approved','reviewer','approved',%s,%s,%s)""",
        (*scope.key, proposal_hash, expires_at, now,
         stable["actionBindingHash"]),
    )
    approval = owner.execute(
        """SELECT approval_event_id,proposal_id,proposal_version,proposal_hash,decision,
                  actor_id,reason,expires_at,created_at,action_binding_hash
             FROM aip_action_approval_event WHERE org_id=%s AND project_id=%s""",
        scope.key,
    ).fetchone()
    approval_ref = CutoverExactRef(
        resourceType="ActionApprovalEvent", resourceId="approval-cutover", revision=3,
        contentHash=canonical_hash(dict(approval), prefixed=True),
    )
    request = CutoverPrepareRequest(
        cutoverOperationId=uuid4(), idempotencyKey="prepare-cutover-1",
        cutoverGroupId=group, expectedGroupRevision=11,
        targetInstallationId=installation, targetGeneration=generation,
        targetExecutionEpoch=7, targetRuntimeRevision=13,
        policyRef=policy_ref, approvalRef=approval_ref,
        checkpoint={"legacyEntry": "canonical-router", "version": 1},
        occurrenceWatermark=now,
        pendingTargetReceiptRefs=([{
            "resourceType": "CapabilityProviderReceipt", "resourceId": "provider-result-1",
            "revision": 1, "contentHash": "sha256:" + "2" * 64,
        }] if pending_receipt else []),
    )
    return request


def _commit_request(prepare_receipt):
    return CutoverCommitRequest(
        cutoverOperationId=prepare_receipt.cutover_operation_id,
        idempotencyKey="commit-cutover-1",
        prepareReceiptRef={
            "resourceType": "CutoverPrepareReceipt",
            "resourceId": str(prepare_receipt.receipt_id),
            "revision": 1,
            "contentHash": prepare_receipt.content_hash,
        },
    )


def test_prepare_freezes_exact_nine_rows_without_cutting_over(database):
    scope = TenantScope("org-org", "dev-project")
    request = _seed(database, scope)
    store = EcommerceGrowthCutoverStore(_connection(database), schema=database.schema)

    receipt = store.prepare_activation(scope, request, actor="runtime-owner")
    replay = store.prepare_activation(scope, request, actor="runtime-owner")

    assert receipt.replayed is False
    assert replay.replayed is True
    assert replay.receipt_id == receipt.receipt_id
    assert receipt.operation_ids == tuple(sorted(ECOMMERCE_GROWTH_OPERATIONS))
    assert {row["handlerKind"] for row in receipt.old_dispatch_snapshot} == {"legacy"}
    assert {row["handlerKind"] for row in receipt.new_dispatch_snapshot} == {"extension"}
    assert {row["cutoverGroupRevision"] for row in receipt.new_dispatch_snapshot} == {12}
    rows = database.owner.execute(
        """SELECT handler_kind,operation_fence,revision,cutover_group_revision
             FROM extension_operation_dispatch_binding
            WHERE org_id=%s AND project_id=%s ORDER BY operation_id""",
        scope.key,
    ).fetchall()
    assert rows == [
        {"handler_kind": "legacy", "operation_fence": False, "revision": 5,
         "cutover_group_revision": 11}
    ] * 9
    assert database.owner.execute(
        "SELECT count(*) AS n FROM extension_dispatch_cutover_event"
    ).fetchone()["n"] == 1
    assert database.owner.execute(
        "SELECT count(*) AS n FROM extension_dispatch_cutover_receipt"
    ).fetchone()["n"] == 1
    database.owner.execute(
        "UPDATE extension_dispatch_cutover_operation SET status='committing'"
    )
    assert store.prepare_activation(scope, request, actor="runtime-owner").receipt_id == receipt.receipt_id


def test_prepare_is_tenant_scoped_and_idempotency_drift_rolls_back(database):
    positive = TenantScope("org-org", "dev-project")
    canary = TenantScope("dev-org", "dev-project")
    request = _seed(database, positive)
    _seed(database, canary)
    store = EcommerceGrowthCutoverStore(_connection(database), schema=database.schema)
    store.prepare_activation(positive, request, actor="runtime-owner")

    with _connection(database)(canary) as conn:
        assert conn.execute("SELECT count(*) AS n FROM extension_dispatch_cutover_operation").fetchone()["n"] == 0
    drifted = request.model_copy(update={"checkpoint": {"legacyEntry": "drifted"}})
    with pytest.raises(EcommerceGrowthCutoverConflict, match="idempotency payload drifted"):
        store.prepare_activation(positive, drifted, actor="runtime-owner")
    assert database.owner.execute(
        "SELECT count(*) AS n FROM extension_dispatch_cutover_operation"
    ).fetchone()["n"] == 1


@pytest.mark.parametrize("complete,ready", [(False, True), (True, False)])
def test_prepare_rejects_incomplete_group_or_unready_runtime(database, complete, ready):
    scope = TenantScope("org-org", "dev-project")
    request = _seed(database, scope, complete=complete, ready=ready)
    store = EcommerceGrowthCutoverStore(_connection(database), schema=database.schema)
    with pytest.raises(EcommerceGrowthCutoverBlocked if not complete else EcommerceGrowthCutoverConflict):
        store.prepare_activation(scope, request, actor="runtime-owner")
    assert database.owner.execute(
        "SELECT count(*) AS n FROM extension_dispatch_cutover_operation"
    ).fetchone()["n"] == 0


def test_prepare_rejects_approval_drift_and_history_is_immutable(database):
    scope = TenantScope("org-org", "dev-project")
    request = _seed(database, scope)
    database.owner.execute("UPDATE aip_action_proposal SET status='expired'")
    store = EcommerceGrowthCutoverStore(_connection(database), schema=database.schema)
    with pytest.raises(EcommerceGrowthCutoverBlocked, match="approval is not bound"):
        store.prepare_activation(scope, request, actor="runtime-owner")
    database.owner.execute("UPDATE aip_action_proposal SET status='approved'")
    receipt = store.prepare_activation(scope, request, actor="runtime-owner")
    with pytest.raises(psycopg.errors.RaiseException, match="history is immutable"):
        database.owner.execute(
            "UPDATE extension_dispatch_cutover_receipt SET content_hash=%s WHERE receipt_id=%s",
            ("sha256:" + "f" * 64, receipt.receipt_id),
        )


def test_nonempty_cutover_authority_blocks_downgrade(database):
    scope = TenantScope("org-org", "dev-project")
    request = _seed(database, scope)
    EcommerceGrowthCutoverStore(_connection(database), schema=database.schema).prepare_activation(
        scope, request, actor="runtime-owner"
    )
    spec = importlib.util.spec_from_file_location(
        "ar2_013_down", database.root / "alembic/versions/ar2_013_ecommerce_growth_cutover.py"
    )
    migration = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(migration)
    migration.op = SimpleNamespace(execute=database.owner.execute)
    with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState):
        migration.downgrade()


def test_prepare_requires_maintainer_and_ignores_temp_shadow(database):
    scope = TenantScope("org-org", "dev-project")
    request = _seed(database, scope)
    with pytest.raises(EcommerceGrowthCutoverBlocked, match="maintainer"):
        EcommerceGrowthCutoverStore(
            _connection(database, runtime=True), schema=database.schema
        ).prepare_activation(scope, request, actor="runtime-owner")
    with pytest.raises(EcommerceGrowthCutoverBlocked, match="maintainer"):
        EcommerceGrowthCutoverStore(
            _connection(database, serializable=False), schema=database.schema
        ).prepare_activation(scope, request, actor="runtime-owner")
    receipt = EcommerceGrowthCutoverStore(
        _connection(database, shadow=True), schema=database.schema
    ).prepare_activation(scope, request, actor="runtime-owner")
    assert receipt.status == "prepared"


def test_prepare_revalidates_strict_ints_and_stable_approval_payload(database):
    scope = TenantScope("org-org", "dev-project")
    request = _seed(database, scope)
    with pytest.raises(ValidationError):
        CutoverPrepareRequest.model_validate({
            **request.model_dump(mode="json", by_alias=True),
            "expectedGroupRevision": True,
        })
    bypassed = request.model_copy(update={"target_runtime_revision": True})
    with pytest.raises(ValidationError):
        EcommerceGrowthCutoverStore(
            _connection(database), schema=database.schema
        ).prepare_activation(scope, bypassed, actor="runtime-owner")
    database.owner.execute(
        "UPDATE aip_action_proposal SET payload=jsonb_set(payload,'{targetRuntimeRevision}','true')"
    )
    with pytest.raises(EcommerceGrowthCutoverBlocked, match="approval is not bound"):
        EcommerceGrowthCutoverStore(
            _connection(database), schema=database.schema
        ).prepare_activation(scope, request, actor="runtime-owner")


@pytest.mark.parametrize("mutation", [
    "authority_data=jsonb_set(authority_data,'{status}','\"committed\"')",
    "request_hash='sha256:'||repeat('f',64)",
    "created_at=created_at+interval '1 second'",
])
def test_replay_rejects_receipt_body_or_split_column_drift(database, mutation):
    scope = TenantScope("org-org", "dev-project")
    request = _seed(database, scope)
    store = EcommerceGrowthCutoverStore(_connection(database), schema=database.schema)
    store.prepare_activation(scope, request, actor="runtime-owner")
    database.owner.execute("ALTER TABLE extension_dispatch_cutover_receipt DISABLE TRIGGER immutable_history")
    database.owner.execute(f"UPDATE extension_dispatch_cutover_receipt SET {mutation}")
    database.owner.execute("ALTER TABLE extension_dispatch_cutover_receipt ENABLE TRIGGER immutable_history")
    with pytest.raises(EcommerceGrowthCutoverConflict, match="Receipt authority drifted"):
        store.prepare_activation(scope, request, actor="runtime-owner")


def test_approval_lock_serializes_current_proposal_cutoff(database):
    scope = TenantScope("org-org", "dev-project")
    request = _seed(database, scope)
    with _connection(database)(scope) as locked:
        locked.execute(
            sql.SQL("SELECT {}.extension_dispatch_cutover_lock_approval_ar2_013(%s)").format(
                sql.Identifier(database.schema)
            ),
            (request.approval_ref.resource_id,),
        )
        contender = psycopg.connect(**PG, autocommit=False, row_factory=dict_row)
        try:
            contender.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(database.schema)))
            contender.execute("SET LOCAL statement_timeout='100ms'")
            with pytest.raises(psycopg.errors.QueryCanceled):
                contender.execute("UPDATE aip_action_proposal SET status='expired'")
        finally:
            contender.rollback()
            contender.close()


def test_approval_expiry_is_checked_after_waiting_for_proposal_lock(database):
    scope = TenantScope("org-org", "dev-project")
    request = _seed(database, scope, approval_lifetime=timedelta(milliseconds=250))
    blocker = psycopg.connect(**PG, autocommit=False, row_factory=dict_row)
    blocker.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(database.schema)))
    blocker.execute("SELECT 1 FROM aip_action_proposal FOR UPDATE")
    store = EcommerceGrowthCutoverStore(_connection(database), schema=database.schema)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(store.prepare_activation, scope, request, actor="runtime-owner")
        time.sleep(0.4)
        blocker.rollback()
        blocker.close()
        with pytest.raises(EcommerceGrowthCutoverBlocked, match="active exact"):
            future.result(timeout=5)


def _seed_pending_occurrence(database, scope, request):
    owner = database.owner
    now = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)
    occurrence_id = uuid4()
    owner.execute(
        """INSERT INTO automation_schedule_binding(
             org_id,project_id,policy_id,policy_revision,policy_hash,operation_id,
             installation_id,generation,execution_epoch,timezone,cadence,weekly_day,
             local_time,effective_from,approved,enabled)
           VALUES(%s,%s,'cutover-policy',1,%s,'ecommerce_growth_schedule_trigger',
             %s,%s,%s,'Asia/Shanghai','weekly',3,'20:00',%s,true,true)""",
        (*scope.key, "sha256:" + "9" * 64, request.target_installation_id,
         request.target_generation, request.target_execution_epoch, now - timedelta(days=1)),
    )
    owner.execute(
        """INSERT INTO automation_occurrence(
             org_id,project_id,occurrence_id,policy_id,policy_revision,policy_hash,operation_id,
             installation_id,generation,execution_epoch,scheduled_at,local_slot,
             trigger_source,status,deadline)
           VALUES(%s,%s,%s,'cutover-policy',1,%s,'ecommerce_growth_schedule_trigger',
             %s,%s,%s,%s,'2026-09-09T20:00+0800','schedule','pending',%s)""",
        (*scope.key, occurrence_id, "sha256:" + "9" * 64,
         request.target_installation_id, request.target_generation,
         request.target_execution_epoch, now, now + timedelta(days=1)),
    )
    return occurrence_id, now


def test_pause_then_commit_switches_exact_group_and_keeps_claim_gate_closed(database):
    scope = TenantScope("org-org", "dev-project")
    prepare_request = _seed(database, scope, pending_receipt=False)
    occurrence_id, now = _seed_pending_occurrence(database, scope, prepare_request)
    store = EcommerceGrowthCutoverStore(_connection(database), schema=database.schema)
    prepared = store.prepare_activation(scope, prepare_request, actor="runtime-owner")
    request = _commit_request(prepared)

    paused = store.begin_activation_commit(scope, request, actor="runtime-owner")
    paused_replay = store.begin_activation_commit(scope, request, actor="runtime-owner")
    assert paused.status == "draining" and paused.replayed is False
    assert paused_replay.receipt_id == paused.receipt_id and paused_replay.replayed is True
    assert paused.occurrence_watermark is not None
    assert database.owner.execute(
        "SELECT status FROM extension_dispatch_cutover_operation"
    ).fetchone()["status"] == "draining"
    assert database.owner.execute(
        "SELECT claim_paused FROM extension_dispatch_claim_gate"
    ).fetchone()["claim_paused"] is True
    assert database.owner.execute(
        "SELECT enabled,operation_fence,revision FROM extension_runtime_binding"
    ).fetchone() == {"enabled": False, "operation_fence": True, "revision": 14}

    committed = store.commit_activation(scope, request, actor="runtime-owner")
    replay = store.commit_activation(scope, request, actor="runtime-owner")
    assert committed.status == "committed" and committed.replayed is False
    assert replay.receipt_id == committed.receipt_id and replay.replayed is True
    rows = database.owner.execute(
        """SELECT handler_kind,installation_id,generation,execution_epoch,
                  operation_fence,revision,cutover_group_revision
             FROM extension_operation_dispatch_binding ORDER BY operation_id"""
    ).fetchall()
    assert len(rows) == 9
    assert all(
        row == {
            "handler_kind": "extension",
            "installation_id": prepare_request.target_installation_id,
            "generation": prepare_request.target_generation,
            "execution_epoch": 7,
            "operation_fence": False,
            "revision": 6,
            "cutover_group_revision": 12,
        }
        for row in rows
    )
    occurrence_store = AutomationOccurrenceStore(
        _connection(database, runtime=True), schema=database.schema
    )
    assert occurrence_store.claim_next(scope, owner="worker-paused", now=now) is None
    database.owner.execute("UPDATE extension_dispatch_claim_gate SET claim_paused=false,revision=2")
    database.owner.execute(
        "UPDATE extension_runtime_binding SET enabled=true,operation_fence=false,revision=revision+1"
    )
    claimed = occurrence_store.claim_next(scope, owner="worker-open", now=now)
    assert claimed is not None and claimed.occurrence_id == occurrence_id


def test_commit_blocks_active_claim_then_preserves_unknown_without_replay(database):
    scope = TenantScope("org-org", "dev-project")
    prepare_request = _seed(database, scope, pending_receipt=False)
    occurrence_id, now = _seed_pending_occurrence(database, scope, prepare_request)
    store = EcommerceGrowthCutoverStore(_connection(database), schema=database.schema)
    prepared = store.prepare_activation(scope, prepare_request, actor="runtime-owner")
    request = _commit_request(prepared)
    attempt_id = uuid4()
    database.owner.execute(
        """UPDATE automation_occurrence SET status='claimed',claim_owner='old-worker',claim_until=%s
             WHERE occurrence_id=%s""",
        (now + timedelta(minutes=5), occurrence_id),
    )
    database.owner.execute(
        """INSERT INTO automation_occurrence_dispatch_attempt(
             org_id,project_id,attempt_id,occurrence_id,claim_owner,target_idempotency_key,
             status,claimed_at,claim_until)
           VALUES(%s,%s,%s,%s,'old-worker','old-target-key','claimed',%s,%s)""",
        (*scope.key, attempt_id, occurrence_id, now, now + timedelta(minutes=5)),
    )
    store.begin_activation_commit(scope, request, actor="runtime-owner")
    with pytest.raises(EcommerceGrowthCutoverBlocked, match="not drained"):
        store.commit_activation(scope, request, actor="runtime-owner")
    assert database.owner.execute(
        "SELECT count(*) AS n FROM extension_operation_dispatch_binding WHERE handler_kind='legacy'"
    ).fetchone()["n"] == 9
    database.owner.execute(
        """UPDATE automation_occurrence SET status='needs_attention',claim_owner=NULL,claim_until=NULL
             WHERE occurrence_id=%s""",
        (occurrence_id,),
    )
    database.owner.execute(
        """UPDATE automation_occurrence_dispatch_attempt
              SET status='unknown',resolved_at=%s WHERE attempt_id=%s""",
        (now + timedelta(minutes=1), attempt_id),
    )
    committed = store.commit_activation(scope, request, actor="runtime-owner")
    assert [item["attemptId"] for item in committed.unknown_attempts] == [str(attempt_id)]
    assert database.owner.execute(
        "SELECT status FROM automation_occurrence_dispatch_attempt WHERE attempt_id=%s",
        (attempt_id,),
    ).fetchone()["status"] == "unknown"


def test_commit_blocks_prepared_pending_receipt_and_dispatch_drift(database):
    scope = TenantScope("org-org", "dev-project")
    pending_request = _seed(database, scope)
    pending_store = EcommerceGrowthCutoverStore(_connection(database), schema=database.schema)
    pending_prepared = pending_store.prepare_activation(scope, pending_request, actor="runtime-owner")
    pending_commit = _commit_request(pending_prepared)
    pending_store.begin_activation_commit(scope, pending_commit, actor="runtime-owner")
    with pytest.raises(EcommerceGrowthCutoverBlocked, match="pending target Receipt"):
        pending_store.commit_activation(scope, pending_commit, actor="runtime-owner")
    assert database.owner.execute(
        "SELECT count(*) AS n FROM extension_operation_dispatch_binding WHERE handler_kind='extension'"
    ).fetchone()["n"] == 0


def test_commit_rolls_back_all_nine_when_one_dispatch_row_drifted(database):
    scope = TenantScope("org-org", "dev-project")
    prepare_request = _seed(database, scope, pending_receipt=False)
    store = EcommerceGrowthCutoverStore(_connection(database), schema=database.schema)
    prepared = store.prepare_activation(scope, prepare_request, actor="runtime-owner")
    request = _commit_request(prepared)
    store.begin_activation_commit(scope, request, actor="runtime-owner")
    database.owner.execute(
        """UPDATE extension_operation_dispatch_binding SET revision=revision+1
             WHERE operation_id=(SELECT min(operation_id) FROM extension_operation_dispatch_binding)"""
    )
    with pytest.raises(EcommerceGrowthCutoverConflict, match="dispatch group authority drifted"):
        store.commit_activation(scope, request, actor="runtime-owner")
    assert database.owner.execute(
        "SELECT count(*) AS n FROM extension_operation_dispatch_binding WHERE handler_kind='extension'"
    ).fetchone()["n"] == 0


def test_pause_receipt_tamper_and_runtime_function_call_are_rejected(database):
    scope = TenantScope("org-org", "dev-project")
    prepare_request = _seed(database, scope, pending_receipt=False)
    store = EcommerceGrowthCutoverStore(_connection(database), schema=database.schema)
    prepared = store.prepare_activation(scope, prepare_request, actor="runtime-owner")
    request = _commit_request(prepared)
    store.begin_activation_commit(scope, request, actor="runtime-owner")
    with _connection(database, runtime=True)(scope) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                sql.SQL("SELECT {}.extension_dispatch_cutover_commit_ar2_014(%s,%s)").format(
                    sql.Identifier(database.schema)
                ),
                (request.cutover_operation_id, "runtime"),
            )
        conn.rollback()
    database.owner.execute("ALTER TABLE extension_dispatch_cutover_receipt DISABLE TRIGGER immutable_history")
    database.owner.execute(
        """UPDATE extension_dispatch_cutover_receipt
              SET authority_data=jsonb_set(authority_data,'{claimPaused}','false')
            WHERE phase='pause'"""
    )
    database.owner.execute("ALTER TABLE extension_dispatch_cutover_receipt ENABLE TRIGGER immutable_history")
    with pytest.raises(EcommerceGrowthCutoverConflict, match="pause Receipt authority drifted"):
        store.begin_activation_commit(scope, request, actor="runtime-owner")


def test_commit_function_itself_rejects_current_approval_drift(database):
    scope = TenantScope("org-org", "dev-project")
    prepare_request = _seed(database, scope, pending_receipt=False)
    store = EcommerceGrowthCutoverStore(_connection(database), schema=database.schema)
    prepared = store.prepare_activation(scope, prepare_request, actor="runtime-owner")
    request = _commit_request(prepared)
    store.begin_activation_commit(scope, request, actor="runtime-owner")
    database.owner.execute("UPDATE aip_action_proposal SET status='expired'")
    with _connection(database)(scope) as conn:
        with pytest.raises(psycopg.Error, match="approval is not bound"):
            conn.execute(
                sql.SQL("SELECT {}.extension_dispatch_cutover_commit_ar2_014(%s,%s)").format(
                    sql.Identifier(database.schema)
                ),
                (request.cutover_operation_id, "runtime-owner"),
            )
        conn.rollback()
    assert database.owner.execute(
        "SELECT count(*) AS n FROM extension_operation_dispatch_binding WHERE handler_kind='legacy'"
    ).fetchone()["n"] == 9


def test_commit_blocks_running_runtime_attempt_until_terminal(database):
    scope = TenantScope("org-org", "dev-project")
    prepare_request = _seed(database, scope, pending_receipt=False)
    store = EcommerceGrowthCutoverStore(_connection(database), schema=database.schema)
    prepared = store.prepare_activation(scope, prepare_request, actor="runtime-owner")
    request = _commit_request(prepared)
    attempt_id = uuid4()
    now = datetime.now(timezone.utc)
    database.owner.execute("SELECT set_config('aos.org_id',%s,false)", (scope.org_id,))
    database.owner.execute("SELECT set_config('aos.project_id',%s,false)", (scope.project_id,))
    database.owner.execute(
        """INSERT INTO extension_runtime_execution_attempt(
             org_id,project_id,attempt_id,installation_id,generation,execution_epoch,
             operation_kind,operation_key,idempotency_key,request_hash,owner_token_hash,
             state,lease_until)
           VALUES(%s,%s,%s,%s,%s,%s,'signed_read','cutover-read','running-key',%s,%s,
             'running',%s)""",
        (*scope.key, attempt_id, prepare_request.target_installation_id,
         prepare_request.target_generation, prepare_request.target_execution_epoch,
         "sha256:" + "7" * 64, "sha256:" + "8" * 64, now + timedelta(minutes=5)),
    )
    store.begin_activation_commit(scope, request, actor="runtime-owner")
    with pytest.raises(EcommerceGrowthCutoverBlocked, match="not drained"):
        store.commit_activation(scope, request, actor="runtime-owner")
    database.owner.execute(
        """UPDATE extension_runtime_execution_attempt
              SET state='abandoned',revision=2,completed_at=%s WHERE attempt_id=%s""",
        (now + timedelta(minutes=1), attempt_id),
    )
    assert store.commit_activation(scope, request, actor="runtime-owner").status == "committed"


def test_pause_waits_for_concurrent_runtime_attempt_then_commit_blocks(database):
    scope = TenantScope("org-org", "dev-project")
    prepare_request = _seed(database, scope, pending_receipt=False)
    store = EcommerceGrowthCutoverStore(_connection(database), schema=database.schema)
    prepared = store.prepare_activation(scope, prepare_request, actor="runtime-owner")
    request = _commit_request(prepared)
    attempt_id = uuid4()
    now = datetime.now(timezone.utc)
    blocker = psycopg.connect(**PG, autocommit=False, row_factory=dict_row)
    blocker.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(database.schema)))
    blocker.execute("SELECT set_config('aos.org_id',%s,false)", (scope.org_id,))
    blocker.execute("SELECT set_config('aos.project_id',%s,false)", (scope.project_id,))
    blocker.execute(
        """INSERT INTO extension_runtime_execution_attempt(
             org_id,project_id,attempt_id,installation_id,generation,execution_epoch,
             operation_kind,operation_key,idempotency_key,request_hash,owner_token_hash,
             state,lease_until)
           VALUES(%s,%s,%s,%s,%s,%s,'signed_read','concurrent-cutover-read',
             'concurrent-running-key',%s,%s,'running',%s)""",
        (*scope.key, attempt_id, prepare_request.target_installation_id,
         prepare_request.target_generation, prepare_request.target_execution_epoch,
         "sha256:" + "5" * 64, "sha256:" + "6" * 64, now + timedelta(minutes=5)),
    )
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                store.begin_activation_commit, scope, request, actor="runtime-owner"
            )
            time.sleep(0.2)
            assert future.done() is False
            blocker.commit()
            assert future.result(timeout=5).status == "draining"
    finally:
        blocker.rollback()
        blocker.close()
    with pytest.raises(EcommerceGrowthCutoverBlocked, match="not drained"):
        store.commit_activation(scope, request, actor="runtime-owner")
    assert database.owner.execute(
        "SELECT count(*) AS n FROM extension_operation_dispatch_binding WHERE handler_kind='legacy'"
    ).fetchone()["n"] == 9


def test_ar2_014_nonempty_gate_blocks_downgrade(database):
    scope = TenantScope("org-org", "dev-project")
    prepare_request = _seed(database, scope, pending_receipt=False)
    store = EcommerceGrowthCutoverStore(_connection(database), schema=database.schema)
    prepared = store.prepare_activation(scope, prepare_request, actor="runtime-owner")
    store.begin_activation_commit(scope, _commit_request(prepared), actor="runtime-owner")
    spec = importlib.util.spec_from_file_location(
        "ar2_014_down",
        database.root / "alembic/versions/ar2_014_ecommerce_growth_cutover_commit.py",
    )
    migration = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(migration)
    migration.op = SimpleNamespace(execute=database.owner.execute)
    with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState):
        migration.downgrade()


def test_ar2_014_empty_downgrade_restores_prior_constraints(database):
    spec = importlib.util.spec_from_file_location(
        "ar2_014_empty_down",
        database.root / "alembic/versions/ar2_014_ecommerce_growth_cutover_commit.py",
    )
    migration = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(migration)
    migration.op = SimpleNamespace(execute=database.owner.execute)
    migration.downgrade()
    assert database.owner.execute(
        "SELECT to_regclass('extension_dispatch_claim_gate') AS relation"
    ).fetchone()["relation"] is None
    definition = database.owner.execute(
        """SELECT pg_get_constraintdef(oid) AS definition FROM pg_constraint
             WHERE conrelid='extension_dispatch_cutover_event'::regclass
               AND conname='extension_dispatch_cutover_event_event_type_check'"""
    ).fetchone()["definition"]
    assert "CUTOVER_CLAIMS_PAUSED" not in definition


def test_direct_pause_or_commit_without_phase_receipt_rolls_back(database):
    scope = TenantScope("org-org", "dev-project")
    prepare_request = _seed(database, scope, pending_receipt=False)
    store = EcommerceGrowthCutoverStore(_connection(database), schema=database.schema)
    prepared = store.prepare_activation(scope, prepare_request, actor="runtime-owner")
    request = _commit_request(prepared)
    with _connection(database)(scope) as conn:
        conn.execute(
            sql.SQL("SELECT {}.extension_dispatch_cutover_pause_claims_ar2_014(%s,%s)").format(
                sql.Identifier(database.schema)
            ),
            (request.cutover_operation_id, "runtime-owner"),
        )
        with pytest.raises(psycopg.errors.CheckViolation, match="pause Receipt"):
            conn.commit()
        conn.rollback()
    assert database.owner.execute(
        "SELECT status FROM extension_dispatch_cutover_operation"
    ).fetchone()["status"] == "prepared"
    assert database.owner.execute(
        "SELECT count(*) AS n FROM extension_dispatch_claim_gate"
    ).fetchone()["n"] == 0

    store.begin_activation_commit(scope, request, actor="runtime-owner")
    with _connection(database)(scope) as conn:
        conn.execute(
            sql.SQL("SELECT {}.extension_dispatch_cutover_commit_ar2_014(%s,%s)").format(
                sql.Identifier(database.schema)
            ),
            (request.cutover_operation_id, "runtime-owner"),
        )
        with pytest.raises(psycopg.errors.CheckViolation, match="commit Receipt"):
            conn.commit()
        conn.rollback()
    assert database.owner.execute(
        "SELECT status FROM extension_dispatch_cutover_operation"
    ).fetchone()["status"] == "draining"
    assert database.owner.execute(
        "SELECT count(*) AS n FROM extension_operation_dispatch_binding WHERE handler_kind='legacy'"
    ).fetchone()["n"] == 9


def test_pause_event_hash_drift_is_rejected_on_replay(database):
    scope = TenantScope("org-org", "dev-project")
    prepare_request = _seed(database, scope, pending_receipt=False)
    store = EcommerceGrowthCutoverStore(_connection(database), schema=database.schema)
    prepared = store.prepare_activation(scope, prepare_request, actor="runtime-owner")
    request = _commit_request(prepared)
    store.begin_activation_commit(scope, request, actor="runtime-owner")
    database.owner.execute("ALTER TABLE extension_dispatch_cutover_event DISABLE TRIGGER immutable_history")
    database.owner.execute(
        """UPDATE extension_dispatch_cutover_event SET payload_hash=%s
             WHERE event_type='CUTOVER_CLAIMS_PAUSED'""",
        ("sha256:" + "f" * 64,),
    )
    database.owner.execute("ALTER TABLE extension_dispatch_cutover_event ENABLE TRIGGER immutable_history")
    with pytest.raises(EcommerceGrowthCutoverConflict, match="pause Receipt authority drifted"):
        store.begin_activation_commit(scope, request, actor="runtime-owner")
