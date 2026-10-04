from __future__ import annotations

import importlib.util
import json
import os
import subprocess
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
from aos_api.asset_registry.installation_store import CommandResult, PostgresInstallationStore
from aos_api.automation_occurrence_store import AutomationOccurrenceStore
from aos_api.ecommerce_growth_cutover import (
    CutoverApprovalRefreshRequest,
    CutoverCommitRequest,
    CutoverExactRef,
    CutoverFinalizeRequest,
    CutoverPrepareRequest,
    CutoverRollbackRequest,
    EcommerceGrowthCutoverBlocked,
    EcommerceGrowthCutoverConflict,
    EcommerceGrowthCutoverStore,
)
from aos_api.ecommerce_growth_host_composition import ECOMMERCE_GROWTH_OPERATIONS
from aos_api.ecommerce_growth_canonical_router import IssuedDispatchRef
from aos_api.ecommerce_growth_host_ports import (
    EcommerceGrowthHostConflict,
    LockedEcommerceGrowthHostPort,
)
from aos_api.ecommerce_growth_lifecycle import (
    EcommerceGrowthDisableDependent,
    EcommerceGrowthLifecycleConflict,
)
from aos_api.extension_runtime.binding_store import RuntimeBindingStore
from aos_api.extension_runtime.disable_executor import RuntimeDisableExecutor
from aos_api.extension_runtime.lifecycle_store import RuntimeOperationStore
from aos_api.extension_runtime.oci_driver import CleanupOnlyOciDriver, OciDriver
from aos_api.extension_runtime.reconciler import ResourceJournal
from aos_api.extension_runtime.runtime_uninstall import (
    RuntimeUninstallCleanupExecutor,
    RuntimeUninstallGuard,
)
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


def _downgrade_ar2_016(database):
    spec = importlib.util.spec_from_file_location(
        "ar2_016_down",
        database.root / "alembic/versions/ar2_016_ecommerce_growth_cutover_rollback.py",
    )
    migration = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(migration)
    migration.op = SimpleNamespace(execute=database.owner.execute)
    migration.downgrade()


def _downgrade_ar2_018(database):
    spec = importlib.util.spec_from_file_location(
        "ar2_018_down",
        database.root / "alembic/versions/ar2_018_runtime_uninstall_authority.py",
    )
    migration = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(migration)
    migration.op = SimpleNamespace(execute=database.owner.execute)
    migration.downgrade()


def _downgrade_ar2_017(database):
    _downgrade_ar2_018(database)
    spec = importlib.util.spec_from_file_location(
        "ar2_017_down",
        database.root / "alembic/versions/ar2_017_ecommerce_growth_disable_detach.py",
    )
    migration = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(migration)
    migration.op = SimpleNamespace(execute=database.owner.execute)
    migration.downgrade()


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
    owner.execute(sql.SQL("GRANT aos_app TO {}").format(sql.Identifier(role)))
    try:
        owner.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        owner.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
        owner.execute(
            """CREATE TABLE bundle_installation(
                 org_id text NOT NULL,project_id text NOT NULL,installation_id uuid NOT NULL,
                 installation_pk uuid NOT NULL DEFAULT gen_random_uuid(),
                 current_revision bigint NOT NULL DEFAULT 1,
                 active_revision bigint DEFAULT 1,previous_active_revision bigint,
                 etag_version bigint NOT NULL DEFAULT 1,
                 PRIMARY KEY(org_id,project_id,installation_pk),
                 UNIQUE(org_id,project_id,installation_id))"""
        )
        owner.execute(
            """CREATE TABLE bundle_installation_revision(
                 org_id text NOT NULL,project_id text NOT NULL,installation_pk uuid NOT NULL,
                 revision bigint NOT NULL,state text NOT NULL,
                 PRIMARY KEY(org_id,project_id,installation_pk,revision),
                 FOREIGN KEY(org_id,project_id,installation_pk)
                   REFERENCES bundle_installation(org_id,project_id,installation_pk))"""
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
            owner.execute(f"GRANT SELECT ON {table} TO aos_runtime")
        _migration(root, "ar2_013_ecommerce_growth_cutover.py", owner, schema=schema)
        _migration(root, "ar2_014_ecommerce_growth_cutover_commit.py", owner, schema=schema)
        _migration(root, "a0v_051_cutover_approval_version.py", owner, schema=schema)
        _migration(root, "a0v_052_cutover_optional_source_ref.py", owner, schema=schema)
        _migration(root, "a0v_053_cutover_approval_refresh.py", owner, schema=schema)
        _migration(root, "ar2_015_ecommerce_growth_cutover_finalize.py", owner, schema=schema)
        _migration(root, "ar2_016_ecommerce_growth_cutover_rollback.py", owner, schema=schema)
        _migration(root, "ar2_017_ecommerce_growth_disable_detach.py", owner, schema=schema)
        _migration(root, "ar2_018_runtime_uninstall_authority.py", owner, schema=schema)
        _migration(root, "a0v_092_retired_dispatch_read_lock.py", owner, schema=schema)
        owner.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO aos_extension_maintainer").format(sql.Identifier(schema)))
        owner.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO aos_runtime").format(sql.Identifier(schema)))
        owner.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO aos_app").format(sql.Identifier(schema)))
        owner.execute(
            sql.SQL("GRANT SELECT,INSERT,UPDATE ON {},{} TO aos_app").format(
                sql.Identifier(schema, "bundle_installation"),
                sql.Identifier(schema, "bundle_installation_revision"),
            )
        )
        owner.execute(
            sql.SQL("GRANT SELECT,UPDATE ON {}.bundle_installation TO aos_runtime").format(
                sql.Identifier(schema)
            )
        )
        yield SimpleNamespace(owner=owner, schema=schema, role=role, root=root)
    finally:
        owner.execute("RESET ROLE")
        owner.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
        owner.execute(sql.SQL("REVOKE aos_extension_maintainer FROM {}").format(sql.Identifier(role)))
        owner.execute(sql.SQL("REVOKE aos_runtime FROM {}").format(sql.Identifier(role)))
        owner.execute(sql.SQL("REVOKE aos_app FROM {}").format(sql.Identifier(role)))
        owner.execute(sql.SQL("DROP ROLE {} ").format(sql.Identifier(role)))
        if created_runtime:
            owner.execute("DROP ROLE aos_runtime")
        owner.close()


def _connection(
    database, *, shadow: bool = False, runtime: bool = False, app: bool = False,
    serializable: bool = True
):
    @contextmanager
    def connect(scope):
        conn = psycopg.connect(**{**PG, "user": database.role}, autocommit=False, row_factory=dict_row)
        try:
            if serializable:
                conn.isolation_level = IsolationLevel.SERIALIZABLE
            role = "aos_app" if app else ("aos_runtime" if runtime else "aos_extension_maintainer")
            conn.execute("SET ROLE " + role)
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


def _idle_runtime_connection(database):
    @contextmanager
    def connect():
        conn = psycopg.connect(
            **{**PG, "user": database.role}, autocommit=False, row_factory=dict_row
        )
        try:
            conn.execute("SET ROLE aos_runtime")
            conn.execute(
                sql.SQL("SET search_path TO {}").format(sql.Identifier(database.schema))
            )
            conn.commit()
            yield conn
        finally:
            conn.close()

    return connect


def _seed(
    database, scope: TenantScope, *, complete: bool = True, ready: bool = True,
    pending_receipt: bool = True,
    approval_lifetime: timedelta = timedelta(hours=1),
    suffix: str = "",
    existing_group=None,
    expected_group_revision: int = 11,
    target_execution_epoch: int = 7,
    target_runtime_revision: int = 13,
    target_installation_id=None,
    target_generation=None,
    registration_ref=None,
):
    owner = database.owner
    owner.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(database.schema)))
    if (target_installation_id is None) != (target_generation is None):
        raise ValueError("target installation and generation must be supplied together")
    installation = target_installation_id or uuid4()
    generation = target_generation or uuid4()
    group = existing_group or uuid4()
    if target_installation_id is None:
        owner.execute(
            "INSERT INTO bundle_installation(org_id,project_id,installation_id) VALUES(%s,%s,%s)",
            (*scope.key, installation),
        )
        owner.execute(
            """INSERT INTO bundle_installation_revision(org_id,project_id,installation_pk,revision,state)
               SELECT org_id,project_id,installation_pk,1,'active' FROM bundle_installation
               WHERE org_id=%s AND project_id=%s AND installation_id=%s""",
            (*scope.key, installation),
        )
        owner.execute(
            """INSERT INTO extension_runtime_binding(
                 org_id,project_id,installation_id,generation,installation_revision,package_lock_ref,
                 profile_ref,config_ref,execution_epoch,desired_state,observed_state,enabled,
                 operation_fence,revision)
               VALUES(%s,%s,%s,%s,2,'{}','internal-python-v1','{}',%s,'enabled',%s,%s,false,%s)""",
            (*scope.key, installation, generation, target_execution_epoch,
             "ready" if ready else "unknown", ready, target_runtime_revision),
        )
    else:
        bound = owner.execute(
            """SELECT execution_epoch,revision,enabled,operation_fence,observed_state
                 FROM extension_runtime_binding
                WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s""",
            (*scope.key, installation, generation),
        ).fetchone()
        assert bound == {
            "execution_epoch": target_execution_epoch,
            "revision": target_runtime_revision,
            "enabled": ready,
            "operation_fence": not ready,
            "observed_state": "ready" if ready else "unknown",
        }
    operations = sorted(ECOMMERCE_GROWTH_OPERATIONS)
    if not complete:
        operations = operations[:-1]
    if existing_group is None:
        for operation_id in operations:
            owner.execute(
                """INSERT INTO extension_operation_dispatch_binding(
                     org_id,project_id,operation_id,handler_kind,operation_fence,revision,
                     cutover_group_id,cutover_group_revision,updated_by)
                   VALUES(%s,%s,%s,'legacy',%s,%s,%s,%s,'legacy-owner')""",
                (*scope.key, operation_id, registration_ref is not None,
                 1 if registration_ref is not None else 5, group, expected_group_revision),
            )
    policy_ref = CutoverExactRef(
        resourceType="RuntimeCutoverPolicyRevision", resourceId="cutover-policy", revision=4,
        contentHash="sha256:" + "1" * 64,
    )
    payload = {
        "cutoverGroupId": str(group),
        "expectedGroupRevision": expected_group_revision,
        "targetInstallationId": str(installation),
        "targetGeneration": str(generation),
        "targetExecutionEpoch": target_execution_epoch,
        "targetRuntimeRevision": target_runtime_revision,
        "operationIds": sorted(ECOMMERCE_GROWTH_OPERATIONS),
        "policyRef": policy_ref.model_dump(mode="json", by_alias=True),
    }
    if registration_ref is not None:
        payload["registrationReceiptRef"] = registration_ref.model_dump(mode="json")
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
           VALUES(%s,%s,%s,'ecommerce_growth_cutover',%s,NULL,NULL,NULL,%s,'R3',
             %s,%s,'{}','[]',%s,%s,%s,'approved',4,%s,'operator')""",
        (*scope.key, f"proposal-cutover{suffix}", psycopg.types.json.Jsonb(action_type), stable["purpose"],
         psycopg.types.json.Jsonb(policy), psycopg.types.json.Jsonb(payload),
         stable["actionBindingHash"], stable["approvalPolicyHash"], proposal_hash,
         expires_at),
    )
    owner.execute(
        """INSERT INTO aip_action_draft(org_id,project_id,proposal_id,proposal_hash,snapshot)
           VALUES(%s,%s,%s,%s,%s)""",
        (*scope.key, f"proposal-cutover{suffix}", proposal_hash,
         psycopg.types.json.Jsonb(stable)),
    )
    owner.execute(
        """INSERT INTO aip_action_approval_event(
             org_id,project_id,approval_event_id,proposal_id,proposal_version,proposal_hash,
             decision,actor_id,reason,expires_at,created_at,action_binding_hash)
           VALUES(%s,%s,%s,%s,3,%s,
             'approved','reviewer','approved',%s,%s,%s)""",
        (*scope.key, f"approval-cutover{suffix}", f"proposal-cutover{suffix}",
         proposal_hash, expires_at, now,
         stable["actionBindingHash"]),
    )
    approval = owner.execute(
        """SELECT approval_event_id,proposal_id,proposal_version,proposal_hash,decision,
                  actor_id,reason,expires_at,created_at,action_binding_hash
             FROM aip_action_approval_event WHERE org_id=%s AND project_id=%s
              AND approval_event_id=%s""",
        (*scope.key, f"approval-cutover{suffix}"),
    ).fetchone()
    approval_ref = CutoverExactRef(
        resourceType="ActionApprovalEvent", resourceId=f"approval-cutover{suffix}", revision=3,
        contentHash=canonical_hash(dict(approval), prefixed=True),
    )
    request = CutoverPrepareRequest(
        cutoverOperationId=uuid4(), idempotencyKey=f"prepare-cutover-1{suffix}",
        cutoverGroupId=group, expectedGroupRevision=expected_group_revision,
        targetInstallationId=installation, targetGeneration=generation,
        targetExecutionEpoch=target_execution_epoch,
        targetRuntimeRevision=target_runtime_revision,
        policyRef=policy_ref, approvalRef=approval_ref,
        registrationReceiptRef=registration_ref,
        checkpoint={"legacyEntry": "canonical-router", "version": 1},
        occurrenceWatermark=now,
        pendingTargetReceiptRefs=([{
            "resourceType": "CapabilityProviderReceipt", "resourceId": "provider-result-1",
            "revision": 1, "contentHash": "sha256:" + "2" * 64,
        }] if pending_receipt else []),
    )
    return request


def _commit_request(prepare_receipt, *, suffix: str = ""):
    return CutoverCommitRequest(
        cutoverOperationId=prepare_receipt.cutover_operation_id,
        idempotencyKey=f"commit-cutover-1{suffix}",
        prepareReceiptRef={
            "resourceType": "CutoverPrepareReceipt",
            "resourceId": str(prepare_receipt.receipt_id),
            "revision": 1,
            "contentHash": prepare_receipt.content_hash,
        },
    )


def _finalize_request(commit_receipt, *, suffix: str = ""):
    return CutoverFinalizeRequest(
        cutoverOperationId=commit_receipt.cutover_operation_id,
        idempotencyKey=f"finalize-cutover-1{suffix}",
        commitReceiptRef={
            "resourceType": "CutoverCommitReceipt",
            "resourceId": str(commit_receipt.receipt_id),
            "revision": 1,
            "contentHash": commit_receipt.content_hash,
        },
    )


def _validate_ref(receipt):
    return CutoverExactRef(
        resourceType="CutoverValidateReceipt",
        resourceId=str(receipt.receipt_id),
        revision=1,
        contentHash=receipt.content_hash,
    )


def _rollback_request(database, scope, prepare_receipt, commit_receipt):
    owner = database.owner
    rollback_operation_id = uuid4()
    commit_ref = {
        "resourceType": "CutoverCommitReceipt",
        "resourceId": str(commit_receipt.receipt_id),
        "revision": 1,
        "contentHash": commit_receipt.content_hash,
    }
    payload = {
        "activationOperationId": str(prepare_receipt.cutover_operation_id),
        "commitReceiptRef": commit_ref,
        "cutoverGroupId": str(prepare_receipt.cutover_group_id),
        "expectedGroupRevision": prepare_receipt.target_group_revision,
        "targetInstallationId": str(prepare_receipt.target_installation_id),
        "targetGeneration": str(prepare_receipt.target_generation),
        "targetExecutionEpoch": prepare_receipt.target_execution_epoch,
        "operationIds": list(prepare_receipt.operation_ids),
    }
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=1)
    action_type = {
        "id": "ecommerce_growth_cutover_rollback",
        "revisionHash": "sha256:" + "a" * 64,
    }
    policy = {"mode": "manual-reviewed-rollback"}
    stable = {
        "tenantScope": {"orgId": scope.org_id, "projectId": scope.project_id},
        "actionType": action_type,
        "taskId": None,
        "runId": None,
        "objectRef": None,
        "purpose": "验证失败后回滚经营参谋九项宿主入口",
        "riskLevel": "R3",
        "policy": policy,
        "payload": payload,
        "diff": {},
        "evidenceRefs": [],
        "approvalPolicyHash": "sha256:" + "b" * 64,
        "actionBindingHash": "sha256:" + "c" * 64,
        "impactPreviewRef": None,
        "sourceDraftRef": None,
        "expiresAt": expires_at.isoformat(),
        "createdBy": "rollback-operator",
    }
    proposal_hash = canonical_hash(stable)
    owner.execute(
        """INSERT INTO aip_action_proposal(
             org_id,project_id,proposal_id,action_type_id,action_type_snapshot,task_id,run_id,
             object_ref,purpose,risk_level,policy_snapshot,payload,diff,evidence_refs,
             action_binding_hash,approval_policy_hash,proposal_hash,status,version,expires_at,created_by)
           VALUES(%s,%s,'proposal-rollback','ecommerce_growth_cutover_rollback',%s,NULL,NULL,NULL,
             %s,'R3',%s,%s,'{}','[]',%s,%s,%s,'approved',1,%s,'rollback-operator')""",
        (*scope.key, psycopg.types.json.Jsonb(action_type), stable["purpose"],
         psycopg.types.json.Jsonb(policy), psycopg.types.json.Jsonb(payload),
         stable["actionBindingHash"], stable["approvalPolicyHash"], proposal_hash,
         expires_at),
    )
    owner.execute(
        """INSERT INTO aip_action_draft(org_id,project_id,proposal_id,proposal_hash,snapshot)
           VALUES(%s,%s,'proposal-rollback',%s,%s)""",
        (*scope.key, proposal_hash, psycopg.types.json.Jsonb(stable)),
    )
    owner.execute(
        """INSERT INTO aip_action_approval_event(
             org_id,project_id,approval_event_id,proposal_id,proposal_version,proposal_hash,
             decision,actor_id,reason,expires_at,created_at,action_binding_hash)
           VALUES(%s,%s,'approval-rollback','proposal-rollback',1,%s,'approved',
             'rollback-reviewer','approved rollback',%s,%s,%s)""",
        (*scope.key, proposal_hash, expires_at, now, stable["actionBindingHash"]),
    )
    approval = owner.execute(
        """SELECT approval_event_id,proposal_id,proposal_version,proposal_hash,decision,
                  actor_id,reason,expires_at,created_at,action_binding_hash
             FROM aip_action_approval_event
            WHERE org_id=%s AND project_id=%s AND approval_event_id='approval-rollback'""",
        scope.key,
    ).fetchone()
    return CutoverRollbackRequest(
        rollbackOperationId=rollback_operation_id,
        idempotencyKey="rollback-cutover-1",
        activationOperationId=prepare_receipt.cutover_operation_id,
        commitReceiptRef=commit_ref,
        approvalRef={
            "resourceType": "ActionApprovalEvent",
            "resourceId": "approval-rollback",
            "revision": 1,
            "contentHash": canonical_hash(dict(approval), prefixed=True),
        },
        failureReason="D5C structural validation failed",
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


@pytest.mark.parametrize("post_commit", [False, True])
def test_expired_inflight_approval_can_refresh_once_without_rewriting_prepare(
    database, post_commit,
):
    scope = TenantScope("org-org", "dev-project")
    prepare_request = _seed(database, scope, pending_receipt=False)
    store = EcommerceGrowthCutoverStore(_connection(database), schema=database.schema)
    prepared = store.prepare_activation(scope, prepare_request, actor="runtime-owner")
    commit_request = _commit_request(prepared)
    store.begin_activation_commit(scope, commit_request, actor="runtime-owner")
    if post_commit:
        store.commit_activation(scope, commit_request, actor="runtime-owner")
    database.owner.execute("UPDATE aip_action_approval_event SET expires_at=NOW()-interval '1 second'")
    database.owner.execute(
        "INSERT INTO aip_action_proposal SELECT org_id,project_id,'proposal-refresh',action_type_id,"
        "action_type_snapshot,task_id,run_id,object_ref,purpose,risk_level,policy_snapshot,payload,diff,"
        "evidence_refs,impact_preview_id,impact_preview_revision,impact_preview_hash,action_binding_hash,"
        "source_draft_id,source_draft_revision,source_draft_hash,approval_policy_hash,proposal_hash,status,"
        "version,expires_at,created_by FROM aip_action_proposal"
    )
    database.owner.execute(
        "INSERT INTO aip_action_draft SELECT org_id,project_id,'proposal-refresh',proposal_hash,snapshot "
        "FROM aip_action_draft"
    )
    database.owner.execute(
        "INSERT INTO aip_action_approval_event SELECT org_id,project_id,'approval-refresh',"
        "'proposal-refresh',proposal_version,proposal_hash,decision,'refresh-reviewer',reason,"
        "NOW()+interval '20 minutes',NOW(),action_binding_hash FROM aip_action_approval_event"
    )
    approval = database.owner.execute(
        "SELECT approval_event_id,proposal_id,proposal_version,proposal_hash,decision,actor_id,reason,"
        "expires_at,created_at,action_binding_hash FROM aip_action_approval_event "
        "WHERE approval_event_id='approval-refresh'"
    ).fetchone()
    refresh = CutoverApprovalRefreshRequest(
        cutoverOperationId=prepared.cutover_operation_id,
        idempotencyKey="refresh-cutover-approval-1",
        prepareReceiptRef={"resourceType": "CutoverPrepareReceipt",
            "resourceId": str(prepared.receipt_id), "revision": 1,
            "contentHash": prepared.content_hash},
        approvalRef={"resourceType": "ActionApprovalEvent", "resourceId": "approval-refresh",
            "revision": approval["proposal_version"],
            "contentHash": canonical_hash(dict(approval), prefixed=True)},
    )
    if post_commit:
        database.owner.execute(
            "UPDATE extension_dispatch_claim_gate SET claim_paused=false"
        )
        with pytest.raises(EcommerceGrowthCutoverConflict, match="claim gate finalization drifted"):
            store.refresh_activation_approval(scope, refresh, actor="runtime-owner")
        database.owner.execute(
            "UPDATE extension_dispatch_claim_gate SET claim_paused=true"
        )
    receipt = store.refresh_activation_approval(scope, refresh, actor="runtime-owner")
    assert receipt.replayed is False
    assert store.refresh_activation_approval(scope, refresh, actor="runtime-owner").replayed is True
    assert store.commit_activation(scope, commit_request, actor="runtime-owner").status == "committed"
    if post_commit:
        committed = store.commit_activation(scope, commit_request, actor="runtime-owner")
        assert store.validate_activation(
            scope, _finalize_request(committed), actor="runtime-owner"
        ).status == "validated"
    assert database.owner.execute(
        "SELECT count(*) AS n FROM extension_dispatch_cutover_approval_refresh_receipt"
    ).fetchone()["n"] == 1


def test_commit_function_rejects_nonempty_source_draft_ref_drift(database):
    scope = TenantScope("org-org", "dev-project")
    prepare_request = _seed(database, scope, pending_receipt=False)
    store = EcommerceGrowthCutoverStore(_connection(database), schema=database.schema)
    prepared = store.prepare_activation(scope, prepare_request, actor="runtime-owner")
    request = _commit_request(prepared)
    store.begin_activation_commit(scope, request, actor="runtime-owner")
    database.owner.execute(
        "UPDATE aip_action_draft SET snapshot=jsonb_set(snapshot,'{sourceDraftRef}',"
        "'{\"resourceType\":\"ActionDraftRevision\",\"resourceId\":\"drift\","
        "\"revision\":1,\"contentHash\":\"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\"}')"
    )
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
    _downgrade_ar2_017(database)
    _downgrade_ar2_016(database)
    finalize_spec = importlib.util.spec_from_file_location(
        "ar2_015_empty_down",
        database.root / "alembic/versions/ar2_015_ecommerce_growth_cutover_finalize.py",
    )
    finalize_migration = importlib.util.module_from_spec(finalize_spec)
    assert finalize_spec.loader is not None
    finalize_spec.loader.exec_module(finalize_migration)
    finalize_migration.op = SimpleNamespace(execute=database.owner.execute)
    finalize_migration.downgrade()
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


def test_validate_then_resume_opens_runtime_and_claim_atomically(database):
    scope = TenantScope("org-org", "dev-project")
    prepare_request = _seed(database, scope, pending_receipt=False)
    occurrence_id, now = _seed_pending_occurrence(database, scope, prepare_request)
    store = EcommerceGrowthCutoverStore(_connection(database), schema=database.schema)
    prepared = store.prepare_activation(scope, prepare_request, actor="runtime-owner")
    commit_request = _commit_request(prepared)
    store.begin_activation_commit(scope, commit_request, actor="runtime-owner")
    committed = store.commit_activation(scope, commit_request, actor="runtime-owner")
    request = _finalize_request(committed)

    validated = store.validate_activation(scope, request, actor="runtime-owner")
    validated_replay = store.validate_activation(scope, request, actor="runtime-owner")
    assert validated.status == "validated" and validated.claim_paused is True
    assert validated_replay.receipt_id == validated.receipt_id
    assert validated_replay.replayed is True

    resumed = store.resume_activation(
        scope, request, validate_receipt_ref=_validate_ref(validated), actor="runtime-owner"
    )
    replay = store.resume_activation(
        scope, request, validate_receipt_ref=_validate_ref(validated), actor="runtime-owner"
    )
    assert resumed.status == "resumed" and resumed.claim_paused is False
    assert replay.receipt_id == resumed.receipt_id and replay.replayed is True
    assert database.owner.execute(
        "SELECT status FROM extension_dispatch_cutover_operation"
    ).fetchone()["status"] == "resumed"
    assert database.owner.execute(
        "SELECT enabled,operation_fence,revision FROM extension_runtime_binding"
    ).fetchone() == {"enabled": True, "operation_fence": False, "revision": 15}
    assert database.owner.execute(
        "SELECT claim_paused,revision FROM extension_dispatch_claim_gate"
    ).fetchone() == {"claim_paused": False, "revision": 2}
    claimed = AutomationOccurrenceStore(
        _connection(database, runtime=True), schema=database.schema
    ).claim_next(scope, owner="worker-resumed", now=now)
    assert claimed is not None and claimed.occurrence_id == occurrence_id


@pytest.mark.parametrize("drift", ["dispatch", "runtime", "gate"])
def test_validate_rejects_committed_authority_drift(database, drift):
    scope = TenantScope("org-org", "dev-project")
    prepare_request = _seed(database, scope, pending_receipt=False)
    store = EcommerceGrowthCutoverStore(_connection(database), schema=database.schema)
    prepared = store.prepare_activation(scope, prepare_request, actor="runtime-owner")
    commit_request = _commit_request(prepared)
    store.begin_activation_commit(scope, commit_request, actor="runtime-owner")
    committed = store.commit_activation(scope, commit_request, actor="runtime-owner")
    if drift == "dispatch":
        database.owner.execute(
            """UPDATE extension_operation_dispatch_binding SET revision=revision+1
                 WHERE operation_id=(SELECT min(operation_id) FROM extension_operation_dispatch_binding)"""
        )
    elif drift == "runtime":
        database.owner.execute("UPDATE extension_runtime_binding SET revision=revision+1")
    else:
        database.owner.execute("UPDATE extension_dispatch_claim_gate SET revision=revision+1")
    with pytest.raises(EcommerceGrowthCutoverConflict, match="authority drifted|state drifted|gate finalization drifted"):
        store.validate_activation(scope, _finalize_request(committed), actor="runtime-owner")


def test_direct_resume_without_receipt_rolls_back_every_entry(database):
    scope = TenantScope("org-org", "dev-project")
    prepare_request = _seed(database, scope, pending_receipt=False)
    store = EcommerceGrowthCutoverStore(_connection(database), schema=database.schema)
    prepared = store.prepare_activation(scope, prepare_request, actor="runtime-owner")
    commit_request = _commit_request(prepared)
    store.begin_activation_commit(scope, commit_request, actor="runtime-owner")
    committed = store.commit_activation(scope, commit_request, actor="runtime-owner")
    request = _finalize_request(committed)
    store.validate_activation(scope, request, actor="runtime-owner")
    with _connection(database)(scope) as conn:
        conn.execute(
            sql.SQL("SELECT {}.extension_dispatch_cutover_resume_ar2_015(%s,%s)").format(
                sql.Identifier(database.schema)
            ),
            (request.cutover_operation_id, "runtime-owner"),
        )
        with pytest.raises(psycopg.errors.CheckViolation, match="resume Receipt"):
            conn.commit()
        conn.rollback()
    assert database.owner.execute(
        "SELECT status FROM extension_dispatch_cutover_operation"
    ).fetchone()["status"] == "validated"
    assert database.owner.execute(
        "SELECT enabled,operation_fence FROM extension_runtime_binding"
    ).fetchone() == {"enabled": False, "operation_fence": True}
    assert database.owner.execute(
        "SELECT claim_paused FROM extension_dispatch_claim_gate"
    ).fetchone()["claim_paused"] is True


def test_finalize_rejects_commit_receipt_reference_drift(database):
    scope = TenantScope("org-org", "dev-project")
    prepare_request = _seed(database, scope, pending_receipt=False)
    store = EcommerceGrowthCutoverStore(_connection(database), schema=database.schema)
    prepared = store.prepare_activation(scope, prepare_request, actor="runtime-owner")
    commit_request = _commit_request(prepared)
    store.begin_activation_commit(scope, commit_request, actor="runtime-owner")
    committed = store.commit_activation(scope, commit_request, actor="runtime-owner")
    request = _finalize_request(committed).model_copy(update={
        "commit_receipt_ref": CutoverExactRef(
            resourceType="CutoverCommitReceipt", resourceId=str(committed.receipt_id),
            revision=1, contentHash="sha256:" + "f" * 64,
        )
    })
    with pytest.raises(EcommerceGrowthCutoverConflict, match="commit Receipt reference drifted"):
        store.validate_activation(scope, request, actor="runtime-owner")


def test_ar2_015_empty_and_nonempty_downgrade_guards(database):
    spec = importlib.util.spec_from_file_location(
        "ar2_015_down",
        database.root / "alembic/versions/ar2_015_ecommerce_growth_cutover_finalize.py",
    )
    migration = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(migration)
    migration.op = SimpleNamespace(execute=database.owner.execute)
    scope = TenantScope("org-org", "dev-project")
    prepare_request = _seed(database, scope, pending_receipt=False)
    store = EcommerceGrowthCutoverStore(_connection(database), schema=database.schema)
    prepared = store.prepare_activation(scope, prepare_request, actor="runtime-owner")
    commit_request = _commit_request(prepared)
    store.begin_activation_commit(scope, commit_request, actor="runtime-owner")
    committed = store.commit_activation(scope, commit_request, actor="runtime-owner")
    store.validate_activation(scope, _finalize_request(committed), actor="runtime-owner")
    _downgrade_ar2_017(database)
    _downgrade_ar2_016(database)
    with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState):
        migration.downgrade()


def test_validation_window_rollback_fences_then_restores_exact_legacy_group(database):
    scope = TenantScope("org-org", "dev-project")
    prepare_request = _seed(database, scope, pending_receipt=False)
    store = EcommerceGrowthCutoverStore(_connection(database), schema=database.schema)
    prepared = store.prepare_activation(scope, prepare_request, actor="runtime-owner")
    commit_request = _commit_request(prepared)
    store.begin_activation_commit(scope, commit_request, actor="runtime-owner")
    committed = store.commit_activation(scope, commit_request, actor="runtime-owner")
    request = _rollback_request(database, scope, prepared, committed)

    fenced = store.prepare_validation_rollback(scope, request, actor="rollback-owner")
    fenced_replay = store.prepare_validation_rollback(scope, request, actor="rollback-owner")
    assert fenced.status == "draining" and fenced.phase == "fence"
    assert fenced_replay.receipt_id == fenced.receipt_id and fenced_replay.replayed is True
    fenced_rows = database.owner.execute(
        """SELECT handler_kind,operation_fence,revision,cutover_group_revision
             FROM extension_operation_dispatch_binding ORDER BY operation_id"""
    ).fetchall()
    assert all(row == {
        "handler_kind": "extension", "operation_fence": True,
        "revision": 7, "cutover_group_revision": 13,
    } for row in fenced_rows)
    assert database.owner.execute(
        "SELECT cutover_operation_id,claim_paused,revision FROM extension_dispatch_claim_gate"
    ).fetchone() == {
        "cutover_operation_id": request.rollback_operation_id,
        "claim_paused": True,
        "revision": 2,
    }

    rolled = store.commit_validation_rollback(scope, request, actor="rollback-owner")
    replay = store.commit_validation_rollback(scope, request, actor="rollback-owner")
    assert rolled.status == "rolled_back" and rolled.phase == "rollback"
    assert rolled.drain_receipt_ref is not None
    assert replay.receipt_id == rolled.receipt_id and replay.replayed is True
    rows = database.owner.execute(
        """SELECT handler_kind,installation_id,generation,execution_epoch,
                  operation_fence,revision,cutover_group_revision
             FROM extension_operation_dispatch_binding ORDER BY operation_id"""
    ).fetchall()
    assert all(row == {
        "handler_kind": "legacy", "installation_id": None, "generation": None,
        "execution_epoch": None, "operation_fence": False,
        "revision": 8, "cutover_group_revision": 14,
    } for row in rows)
    assert database.owner.execute(
        "SELECT count(*) AS n FROM extension_dispatch_claim_gate"
    ).fetchone()["n"] == 0
    assert database.owner.execute(
        "SELECT enabled,operation_fence,revision FROM extension_runtime_binding"
    ).fetchone() == {"enabled": False, "operation_fence": True, "revision": 14}
    states = database.owner.execute(
        "SELECT kind,status FROM extension_dispatch_cutover_operation ORDER BY kind"
    ).fetchall()
    assert states == [
        {"kind": "activate", "status": "committed"},
        {"kind": "rollback", "status": "rolled_back"},
    ]


@pytest.mark.parametrize("drift", ["dispatch", "runtime", "gate", "approval"])
def test_rollback_fence_rejects_current_authority_drift(database, drift):
    scope = TenantScope("org-org", "dev-project")
    prepare_request = _seed(database, scope, pending_receipt=False)
    store = EcommerceGrowthCutoverStore(_connection(database), schema=database.schema)
    prepared = store.prepare_activation(scope, prepare_request, actor="runtime-owner")
    commit_request = _commit_request(prepared)
    store.begin_activation_commit(scope, commit_request, actor="runtime-owner")
    committed = store.commit_activation(scope, commit_request, actor="runtime-owner")
    request = _rollback_request(database, scope, prepared, committed)
    if drift == "dispatch":
        database.owner.execute(
            """UPDATE extension_operation_dispatch_binding SET revision=revision+1
                 WHERE operation_id=(SELECT min(operation_id) FROM extension_operation_dispatch_binding)"""
        )
    elif drift == "runtime":
        database.owner.execute("UPDATE extension_runtime_binding SET revision=revision+1")
    elif drift == "gate":
        database.owner.execute("UPDATE extension_dispatch_claim_gate SET revision=revision+1")
    else:
        database.owner.execute(
            "UPDATE aip_action_proposal SET status='expired' WHERE proposal_id='proposal-rollback'"
        )
    with pytest.raises(
        (EcommerceGrowthCutoverBlocked, EcommerceGrowthCutoverConflict),
        match="drifted|not bound",
    ):
        store.prepare_validation_rollback(scope, request, actor="rollback-owner")
    assert database.owner.execute(
        "SELECT count(*) AS n FROM extension_dispatch_cutover_operation WHERE kind='rollback'"
    ).fetchone()["n"] == 0


def test_rollback_is_closed_after_resume(database):
    scope = TenantScope("org-org", "dev-project")
    prepare_request = _seed(database, scope, pending_receipt=False)
    store = EcommerceGrowthCutoverStore(_connection(database), schema=database.schema)
    prepared = store.prepare_activation(scope, prepare_request, actor="runtime-owner")
    commit_request = _commit_request(prepared)
    store.begin_activation_commit(scope, commit_request, actor="runtime-owner")
    committed = store.commit_activation(scope, commit_request, actor="runtime-owner")
    finalize_request = _finalize_request(committed)
    validated = store.validate_activation(scope, finalize_request, actor="runtime-owner")
    store.resume_activation(
        scope,
        finalize_request,
        validate_receipt_ref=_validate_ref(validated),
        actor="runtime-owner",
    )
    request = _rollback_request(database, scope, prepared, committed)
    with pytest.raises(EcommerceGrowthCutoverBlocked, match="outside validation rollback window"):
        store.prepare_validation_rollback(scope, request, actor="rollback-owner")


def test_rollback_commit_rechecks_approval_and_running_attempt(database):
    scope = TenantScope("org-org", "dev-project")
    prepare_request = _seed(database, scope, pending_receipt=False)
    store = EcommerceGrowthCutoverStore(_connection(database), schema=database.schema)
    prepared = store.prepare_activation(scope, prepare_request, actor="runtime-owner")
    commit_request = _commit_request(prepared)
    store.begin_activation_commit(scope, commit_request, actor="runtime-owner")
    committed = store.commit_activation(scope, commit_request, actor="runtime-owner")
    request = _rollback_request(database, scope, prepared, committed)
    store.prepare_validation_rollback(scope, request, actor="rollback-owner")
    database.owner.execute(
        "UPDATE aip_action_proposal SET status='expired' WHERE proposal_id='proposal-rollback'"
    )
    with pytest.raises(EcommerceGrowthCutoverBlocked, match="approval is not bound"):
        store.commit_validation_rollback(scope, request, actor="rollback-owner")
    database.owner.execute(
        "UPDATE aip_action_proposal SET status='approved' WHERE proposal_id='proposal-rollback'"
    )
    attempt_id = uuid4()
    now = datetime.now(timezone.utc)
    database.owner.execute("SELECT set_config('aos.org_id',%s,false)", (scope.org_id,))
    database.owner.execute("SELECT set_config('aos.project_id',%s,false)", (scope.project_id,))
    database.owner.execute(
        "ALTER TABLE extension_runtime_execution_attempt DISABLE TRIGGER attempt_insert_guard"
    )
    database.owner.execute(
        """INSERT INTO extension_runtime_execution_attempt(
             org_id,project_id,attempt_id,installation_id,generation,execution_epoch,
             operation_kind,operation_key,idempotency_key,request_hash,owner_token_hash,
             state,lease_until)
           VALUES(%s,%s,%s,%s,%s,%s,'signed_read','rollback-read','rollback-running',%s,%s,
             'running',%s)""",
        (*scope.key, attempt_id, prepare_request.target_installation_id,
         prepare_request.target_generation, prepare_request.target_execution_epoch,
         "sha256:" + "7" * 64, "sha256:" + "8" * 64, now + timedelta(minutes=5)),
    )
    database.owner.execute(
        "ALTER TABLE extension_runtime_execution_attempt ENABLE TRIGGER attempt_insert_guard"
    )
    with pytest.raises(EcommerceGrowthCutoverBlocked, match="not drained"):
        store.commit_validation_rollback(scope, request, actor="rollback-owner")
    database.owner.execute(
        """UPDATE extension_runtime_execution_attempt
              SET state='abandoned',revision=2,completed_at=%s WHERE attempt_id=%s""",
        (now + timedelta(minutes=1), attempt_id),
    )
    assert store.commit_validation_rollback(
        scope, request, actor="rollback-owner"
    ).status == "rolled_back"


def test_direct_rollback_without_receipts_rolls_back_every_entry(database):
    scope = TenantScope("org-org", "dev-project")
    prepare_request = _seed(database, scope, pending_receipt=False)
    store = EcommerceGrowthCutoverStore(_connection(database), schema=database.schema)
    prepared = store.prepare_activation(scope, prepare_request, actor="runtime-owner")
    commit_request = _commit_request(prepared)
    store.begin_activation_commit(scope, commit_request, actor="runtime-owner")
    committed = store.commit_activation(scope, commit_request, actor="runtime-owner")
    request = _rollback_request(database, scope, prepared, committed)
    store.prepare_validation_rollback(scope, request, actor="rollback-owner")
    with _connection(database, runtime=True)(scope) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                sql.SQL("SELECT {}.extension_dispatch_cutover_rollback_ar2_016(%s,%s)").format(
                    sql.Identifier(database.schema)
                ),
                (request.rollback_operation_id, "runtime"),
            )
        conn.rollback()
    with _connection(database)(scope) as conn:
        conn.execute(
            sql.SQL("SELECT {}.extension_dispatch_cutover_rollback_ar2_016(%s,%s)").format(
                sql.Identifier(database.schema)
            ),
            (request.rollback_operation_id, "rollback-owner"),
        )
        with pytest.raises(psycopg.errors.CheckViolation, match="rollback Receipt"):
            conn.commit()
        conn.rollback()
    assert database.owner.execute(
        "SELECT status FROM extension_dispatch_cutover_operation WHERE kind='rollback'"
    ).fetchone()["status"] == "draining"
    assert database.owner.execute(
        """SELECT count(*) AS n FROM extension_operation_dispatch_binding
             WHERE handler_kind='extension' AND operation_fence"""
    ).fetchone()["n"] == 9
    assert database.owner.execute(
        "SELECT count(*) AS n FROM extension_dispatch_claim_gate"
    ).fetchone()["n"] == 1


def test_rollback_receipt_tamper_is_rejected(database):
    scope = TenantScope("org-org", "dev-project")
    prepare_request = _seed(database, scope, pending_receipt=False)
    store = EcommerceGrowthCutoverStore(_connection(database), schema=database.schema)
    prepared = store.prepare_activation(scope, prepare_request, actor="runtime-owner")
    commit_request = _commit_request(prepared)
    store.begin_activation_commit(scope, commit_request, actor="runtime-owner")
    committed = store.commit_activation(scope, commit_request, actor="runtime-owner")
    request = _rollback_request(database, scope, prepared, committed)
    store.prepare_validation_rollback(scope, request, actor="rollback-owner")
    database.owner.execute(
        "ALTER TABLE extension_dispatch_cutover_receipt DISABLE TRIGGER immutable_history"
    )
    database.owner.execute(
        """UPDATE extension_dispatch_cutover_receipt
              SET authority_data=jsonb_set(authority_data,'{failureReason}','\"tampered\"')
            WHERE phase='fence'"""
    )
    database.owner.execute(
        "ALTER TABLE extension_dispatch_cutover_receipt ENABLE TRIGGER immutable_history"
    )
    with pytest.raises(EcommerceGrowthCutoverConflict, match="fence Receipt authority drifted"):
        store.commit_validation_rollback(scope, request, actor="rollback-owner")


def test_rollback_preserves_unknown_attempt_for_reconciliation(database):
    scope = TenantScope("org-org", "dev-project")
    prepare_request = _seed(database, scope, pending_receipt=False)
    occurrence_id, now = _seed_pending_occurrence(database, scope, prepare_request)
    attempt_id = uuid4()
    database.owner.execute(
        """UPDATE automation_occurrence SET status='needs_attention'
             WHERE occurrence_id=%s""",
        (occurrence_id,),
    )
    database.owner.execute(
        """INSERT INTO automation_occurrence_dispatch_attempt(
             org_id,project_id,attempt_id,occurrence_id,claim_owner,target_idempotency_key,
             status,claimed_at,claim_until,resolved_at)
           VALUES(%s,%s,%s,%s,'old-worker','unknown-target','unknown',%s,%s,%s)""",
        (*scope.key, attempt_id, occurrence_id, now, now + timedelta(minutes=5), now),
    )
    store = EcommerceGrowthCutoverStore(_connection(database), schema=database.schema)
    prepared = store.prepare_activation(scope, prepare_request, actor="runtime-owner")
    commit_request = _commit_request(prepared)
    store.begin_activation_commit(scope, commit_request, actor="runtime-owner")
    committed = store.commit_activation(scope, commit_request, actor="runtime-owner")
    request = _rollback_request(database, scope, prepared, committed)
    store.prepare_validation_rollback(scope, request, actor="rollback-owner")
    rolled = store.commit_validation_rollback(scope, request, actor="rollback-owner")
    assert [item["attemptId"] for item in rolled.unknown_attempts] == [str(attempt_id)]
    assert database.owner.execute(
        "SELECT status FROM automation_occurrence_dispatch_attempt WHERE attempt_id=%s",
        (attempt_id,),
    ).fetchone()["status"] == "unknown"


def test_ar2_016_empty_downgrade_removes_rollback_authority(database):
    _downgrade_ar2_017(database)
    _downgrade_ar2_016(database)
    assert database.owner.execute(
        """SELECT count(*) AS n FROM information_schema.columns
             WHERE table_schema=current_schema()
               AND table_name='extension_dispatch_cutover_operation'
               AND column_name='parent_cutover_operation_id'"""
    ).fetchone()["n"] == 0


def test_ar2_016_nonempty_rollback_authority_blocks_downgrade(database):
    scope = TenantScope("org-org", "dev-project")
    prepare_request = _seed(database, scope, pending_receipt=False)
    store = EcommerceGrowthCutoverStore(_connection(database), schema=database.schema)
    prepared = store.prepare_activation(scope, prepare_request, actor="runtime-owner")
    commit_request = _commit_request(prepared)
    store.begin_activation_commit(scope, commit_request, actor="runtime-owner")
    committed = store.commit_activation(scope, commit_request, actor="runtime-owner")
    request = _rollback_request(database, scope, prepared, committed)
    store.prepare_validation_rollback(scope, request, actor="rollback-owner")
    _downgrade_ar2_017(database)
    with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState):
        _downgrade_ar2_016(database)


def _resumed_activation(database, scope):
    prepare_request = _seed(database, scope, pending_receipt=False)
    store = EcommerceGrowthCutoverStore(_connection(database), schema=database.schema)
    prepared = store.prepare_activation(scope, prepare_request, actor="runtime-owner")
    commit_request = _commit_request(prepared)
    store.begin_activation_commit(scope, commit_request, actor="runtime-owner")
    committed = store.commit_activation(scope, commit_request, actor="runtime-owner")
    finalize_request = _finalize_request(committed)
    validated = store.validate_activation(scope, finalize_request, actor="runtime-owner")
    store.resume_activation(
        scope,
        finalize_request,
        validate_receipt_ref=_validate_ref(validated),
        actor="runtime-owner",
    )
    return prepare_request, prepared


def _begin_runtime_disable(database, scope, prepare_request):
    with _connection(database, runtime=True)(scope) as conn:
        accepted = RuntimeOperationStore().accept(
            conn,
            org_id=scope.org_id,
            project_id=scope.project_id,
            installation_id=prepare_request.target_installation_id,
            kind="disable",
            idempotency_key="d6-disable",
            requested_by="runtime-owner",
            expected_installation_etag=1,
            deadline=datetime.now(timezone.utc) + timedelta(minutes=5),
            binding_target={
                "generation": str(prepare_request.target_generation),
                "bindingRevision": 15,
            },
        )
        fenced = RuntimeBindingStore().fence(
            conn,
            org_id=scope.org_id,
            project_id=scope.project_id,
            installation_id=prepare_request.target_installation_id,
            generation=prepare_request.target_generation,
            operation_id=accepted.operation_id,
            expected_operation_revision=accepted.revision,
            expected_binding_revision=15,
        )
        lifecycle = EcommerceGrowthDisableDependent(schema=database.schema)
        receipt = lifecycle.after_runtime_fenced(
            conn,
            org_id=scope.org_id,
            project_id=scope.project_id,
            runtime_operation_id=accepted.operation_id,
        )
        conn.commit()
    assert receipt is not None and receipt.status == "fenced"
    return accepted.operation_id, fenced.revision


def _complete_runtime_disable(database, scope, operation_id, revision):
    with _connection(database, runtime=True)(scope) as conn:
        operations = RuntimeOperationStore()
        for phase in ("draining", "committing"):
            revision = operations.advance(
                conn,
                org_id=scope.org_id,
                project_id=scope.project_id,
                operation_id=operation_id,
                expected_revision=revision,
                phase=phase,
            ).revision
        conn.execute(
            """UPDATE extension_runtime_binding
                  SET desired_state='disabled',observed_state='unknown',revision=revision+1"""
        )
        conn.execute(
            """UPDATE extension_runtime_operation SET revision=revision+1
                 WHERE org_id=%s AND project_id=%s AND operation_id=%s""",
            (*scope.key, operation_id),
        )
        revision += 1
        operations._event(
            conn,
            *scope.key,
            operation_id,
            revision,
            "disabled_committed",
            {"resourcesRetained": True},
        )
        result = operations.advance(
            conn,
            org_id=scope.org_id,
            project_id=scope.project_id,
            operation_id=operation_id,
            expected_revision=revision,
            phase="succeeded",
        )
        conn.commit()
    return result


def _seed_owned_runtime_resource(
    database,
    scope,
    prepare_request,
    *,
    package_hash="sha256:" + "a" * 64,
    created_container_id="b" * 64,
):
    with _connection(database, runtime=True)(scope) as conn:
        operation = RuntimeOperationStore().accept(
            conn,
            org_id=scope.org_id,
            project_id=scope.project_id,
            installation_id=prepare_request.target_installation_id,
            kind="runtime-apply",
            idempotency_key="d6-owned-resource",
            requested_by="runtime-owner",
            expected_installation_etag=1,
            deadline=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
        journal = ResourceJournal()
        intent = journal.prepare(
            conn,
            org_id=scope.org_id,
            project_id=scope.project_id,
            operation_id=operation.operation_id,
            generation=prepare_request.target_generation,
            package_id="ecommerce-growth",
            package_hash=package_hash,
            engine_context="colima-aos-extension",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        if created_container_id is not None:
            claimed = journal.claim_create(
                conn,
                org_id=scope.org_id,
                project_id=scope.project_id,
                resource_id=intent.resource_id,
            )
            journal.record_created(
                conn,
                org_id=scope.org_id,
                project_id=scope.project_id,
                intent=claimed,
                container_id=created_container_id,
            )
        conn.commit()
    return intent


def _record_owned_runtime_container(database, scope, intent, container_id):
    with _connection(database, runtime=True)(scope) as conn:
        journal = ResourceJournal()
        claimed = journal.claim_create(
            conn,
            org_id=scope.org_id,
            project_id=scope.project_id,
            resource_id=intent.resource_id,
        )
        journal.record_created(
            conn,
            org_id=scope.org_id,
            project_id=scope.project_id,
            intent=claimed,
            container_id=container_id,
        )
        conn.commit()


def _detach_and_release_existing_runtime(
    database, scope, prepare_request, *, intent=None, cleanup_driver=None
):
    intent = intent or _seed_owned_runtime_resource(database, scope, prepare_request)
    operation_id, revision = _begin_runtime_disable(database, scope, prepare_request)
    _complete_runtime_disable(database, scope, operation_id, revision)
    with _connection(database, runtime=True)(scope) as conn:
        EcommerceGrowthDisableDependent(schema=database.schema).after_runtime_disabled(
            conn,
            org_id=scope.org_id,
            project_id=scope.project_id,
            runtime_operation_id=operation_id,
        )
        conn.commit()

    if cleanup_driver is None:
        class Driver:
            context = "colima-aos-extension"

            @staticmethod
            def require_isolation():
                return None

            @staticmethod
            def remove_owned(name, owner, *, expected_container_id):
                assert (name, owner) == (intent.identity.name, intent.identity.owner)
                assert expected_container_id == "b" * 64
                return True

        cleanup_driver = Driver()

    state = RuntimeUninstallCleanupExecutor(
        connect=_idle_runtime_connection(database), driver=cleanup_driver
    ).run_one(
        org_id=scope.org_id,
        project_id=scope.project_id,
        installation_id=prepare_request.target_installation_id,
        generation=prepare_request.target_generation,
        resource_id=intent.resource_id,
    )
    assert state == "released"
    return intent


def _detach_and_release_runtime(database, scope):
    prepare_request, _ = _resumed_activation(database, scope)
    _detach_and_release_existing_runtime(database, scope, prepare_request)
    return prepare_request


def _append_minimal_uninstalled_revision(conn, scope, installation_id, current_revision):
    row = conn.execute(
        """SELECT installation_pk FROM bundle_installation
           WHERE org_id=%s AND project_id=%s AND installation_id=%s""",
        (*scope.key, installation_id),
    ).fetchone()
    assert row is not None
    conn.execute(
        """INSERT INTO bundle_installation_revision(
             org_id,project_id,installation_pk,revision,state)
           VALUES(%s,%s,%s,%s,'uninstalled')""",
        (*scope.key, row["installation_pk"], current_revision + 1),
    )
    conn.execute(
        """UPDATE bundle_installation SET current_revision=%s,etag_version=%s,
             active_revision=previous_active_revision
           WHERE org_id=%s AND project_id=%s AND installation_id=%s""",
        (current_revision + 1, current_revision + 1, *scope.key, installation_id),
    )


def test_resumed_disable_fences_then_detaches_exact_dispatch_group(database):
    scope = TenantScope("org-org", "dev-project")
    prepare_request, _ = _resumed_activation(database, scope)
    operation_id, revision = _begin_runtime_disable(database, scope, prepare_request)
    assert database.owner.execute(
        """SELECT count(*) AS n FROM extension_operation_dispatch_binding
             WHERE handler_kind='extension' AND operation_fence
               AND revision=7 AND cutover_group_revision=13"""
    ).fetchone()["n"] == 9
    assert database.owner.execute(
        "SELECT claim_paused,revision FROM extension_dispatch_claim_gate"
    ).fetchone() == {"claim_paused": True, "revision": 3}

    _complete_runtime_disable(database, scope, operation_id, revision)
    with _connection(database, runtime=True)(scope) as conn:
        dependent = EcommerceGrowthDisableDependent(schema=database.schema)
        detached = dependent.after_runtime_disabled(
            conn,
            org_id=scope.org_id,
            project_id=scope.project_id,
            runtime_operation_id=operation_id,
        )
        replay = dependent.after_runtime_disabled(
            conn,
            org_id=scope.org_id,
            project_id=scope.project_id,
            runtime_operation_id=operation_id,
        )
        conn.commit()
    assert detached is not None and detached.status == "detached"
    assert replay is not None and replay.receipt_id == detached.receipt_id
    assert replay.replayed is True
    rows = database.owner.execute(
        """SELECT handler_kind,installation_id,generation,execution_epoch,
                  operation_fence,revision,cutover_group_revision
             FROM extension_operation_dispatch_binding ORDER BY operation_id"""
    ).fetchall()
    assert all(
        row
        == {
            "handler_kind": "legacy",
            "installation_id": None,
            "generation": None,
            "execution_epoch": None,
            "operation_fence": False,
            "revision": 8,
            "cutover_group_revision": 14,
        }
        for row in rows
    )
    assert database.owner.execute(
        "SELECT count(*) AS n FROM extension_dispatch_claim_gate"
    ).fetchone()["n"] == 0


def test_disable_executor_wires_exact_ecommerce_dependent_across_two_transactions(
    database,
):
    scope = TenantScope("org-org", "dev-project")
    prepare_request, _ = _resumed_activation(database, scope)
    with _connection(database, runtime=True)(scope) as conn:
        accepted = RuntimeOperationStore().accept(
            conn,
            org_id=scope.org_id,
            project_id=scope.project_id,
            installation_id=prepare_request.target_installation_id,
            kind="disable",
            idempotency_key="d6-executor-disable",
            requested_by="runtime-owner",
            expected_installation_etag=1,
            deadline=datetime.now(timezone.utc) + timedelta(minutes=5),
            binding_target={
                "generation": str(prepare_request.target_generation),
                "bindingRevision": 15,
            },
        )
        conn.commit()

    class InstallationLock:
        @staticmethod
        def lock_for_transition_in_transaction(conn, **_):
            return object()

    executor = RuntimeDisableExecutor(
        connect=_idle_runtime_connection(database),
        installation_store=InstallationLock(),
        check_current_permission=lambda **_: True,
        check_drained=lambda *_args, **_kwargs: True,
        dependent=EcommerceGrowthDisableDependent(schema=database.schema),
    )
    result = executor.execute(
        org_id=scope.org_id,
        project_id=scope.project_id,
        operation_id=accepted.operation_id,
        expected_revision=accepted.revision,
    )
    assert result.status == "succeeded" and result.phase == "succeeded"
    assert database.owner.execute(
        """SELECT count(*) AS n FROM extension_dispatch_lifecycle_receipt
             WHERE runtime_operation_id=%s""",
        (accepted.operation_id,),
    ).fetchone()["n"] == 2
    assert database.owner.execute(
        "SELECT status FROM extension_dispatch_lifecycle_operation"
    ).fetchone()["status"] == "detached"
    assert database.owner.execute(
        """SELECT count(*) AS n FROM extension_operation_dispatch_binding
             WHERE handler_kind='legacy' AND NOT operation_fence
               AND revision=8 AND cutover_group_revision=14"""
    ).fetchone()["n"] == 9


@pytest.mark.parametrize("failure_phase", ["fence", "detach"])
def test_disable_executor_rolls_back_the_exact_failing_dependent_transaction(
    database, failure_phase
):
    scope = TenantScope("org-org", "dev-project")
    prepare_request, _ = _resumed_activation(database, scope)
    with _connection(database, runtime=True)(scope) as conn:
        accepted = RuntimeOperationStore().accept(
            conn,
            org_id=scope.org_id,
            project_id=scope.project_id,
            installation_id=prepare_request.target_installation_id,
            kind="disable",
            idempotency_key=f"d6-{failure_phase}-rollback",
            requested_by="runtime-owner",
            expected_installation_etag=1,
            deadline=datetime.now(timezone.utc) + timedelta(minutes=5),
            binding_target={
                "generation": str(prepare_request.target_generation),
                "bindingRevision": 15,
            },
        )
        conn.commit()

    concrete = EcommerceGrowthDisableDependent(schema=database.schema)

    class FailingDependent:
        def after_runtime_fenced(self, conn, **kwargs):
            result = concrete.after_runtime_fenced(conn, **kwargs)
            if failure_phase == "fence":
                raise RuntimeError("fence hook rollback")
            return result

        def after_runtime_disabled(self, conn, **kwargs):
            result = concrete.after_runtime_disabled(conn, **kwargs)
            if failure_phase == "detach":
                raise RuntimeError("detach hook rollback")
            return result

    class InstallationLock:
        @staticmethod
        def lock_for_transition_in_transaction(conn, **_):
            return object()

    executor = RuntimeDisableExecutor(
        connect=_idle_runtime_connection(database),
        installation_store=InstallationLock(),
        check_current_permission=lambda **_: True,
        check_drained=lambda *_args, **_kwargs: True,
        dependent=FailingDependent(),
    )
    with pytest.raises(RuntimeError, match=f"{failure_phase} hook rollback"):
        executor.execute(
            org_id=scope.org_id,
            project_id=scope.project_id,
            operation_id=accepted.operation_id,
            expected_revision=accepted.revision,
        )
    operation = database.owner.execute(
        "SELECT status,phase FROM extension_runtime_operation WHERE operation_id=%s",
        (accepted.operation_id,),
    ).fetchone()
    binding = database.owner.execute(
        "SELECT enabled,operation_fence,observed_state FROM extension_runtime_binding"
    ).fetchone()
    lifecycle_count = database.owner.execute(
        "SELECT count(*) AS n FROM extension_dispatch_lifecycle_operation"
    ).fetchone()["n"]
    if failure_phase == "fence":
        assert operation == {"status": "accepted", "phase": "accepted"}
        assert binding == {
            "enabled": True,
            "operation_fence": False,
            "observed_state": "ready",
        }
        assert lifecycle_count == 0
    else:
        assert operation == {"status": "running", "phase": "fencing"}
        assert binding == {
            "enabled": False,
            "operation_fence": True,
            "observed_state": "draining",
        }
        assert lifecycle_count == 1
        assert database.owner.execute(
            "SELECT status FROM extension_dispatch_lifecycle_operation"
        ).fetchone()["status"] == "fenced"


def test_direct_disable_detach_without_receipt_rolls_back(database):
    scope = TenantScope("org-org", "dev-project")
    prepare_request, _ = _resumed_activation(database, scope)
    operation_id, revision = _begin_runtime_disable(database, scope, prepare_request)
    _complete_runtime_disable(database, scope, operation_id, revision)
    with _connection(database, runtime=True)(scope) as conn:
        conn.execute(
            sql.SQL("SELECT {}.extension_dispatch_lifecycle_detach_ar2_017(%s,%s)").format(
                sql.Identifier(database.schema)
            ),
            (operation_id, "runtime-owner"),
        )
        with pytest.raises(psycopg.errors.CheckViolation, match="detach Receipt"):
            conn.commit()
        conn.rollback()
    assert database.owner.execute(
        "SELECT status FROM extension_dispatch_lifecycle_operation"
    ).fetchone()["status"] == "fenced"
    assert database.owner.execute(
        """SELECT count(*) AS n FROM extension_operation_dispatch_binding
             WHERE handler_kind='extension' AND operation_fence"""
    ).fetchone()["n"] == 9


def test_ar2_017_empty_and_nonempty_downgrade_guards(database):
    _downgrade_ar2_017(database)
    assert database.owner.execute(
        "SELECT to_regclass('extension_dispatch_lifecycle_operation') AS relation"
    ).fetchone()["relation"] is None


def test_disable_lifecycle_receipt_tamper_is_rejected(database):
    scope = TenantScope("org-org", "dev-project")
    prepare_request, _ = _resumed_activation(database, scope)
    operation_id, _ = _begin_runtime_disable(database, scope, prepare_request)
    database.owner.execute(
        "ALTER TABLE extension_dispatch_lifecycle_receipt DISABLE TRIGGER immutable_history"
    )
    database.owner.execute(
        """UPDATE extension_dispatch_lifecycle_receipt
              SET authority_data=jsonb_set(authority_data,'{requestedBy}','\"tampered\"')
            WHERE runtime_operation_id=%s AND phase='fence'""",
        (operation_id,),
    )
    database.owner.execute(
        "ALTER TABLE extension_dispatch_lifecycle_receipt ENABLE TRIGGER immutable_history"
    )
    with _connection(database, runtime=True)(scope) as conn:
        with pytest.raises(
            EcommerceGrowthLifecycleConflict, match="Receipt authority drifted"
        ):
            EcommerceGrowthDisableDependent(schema=database.schema).after_runtime_fenced(
                conn,
                org_id=scope.org_id,
                project_id=scope.project_id,
                runtime_operation_id=operation_id,
            )


def test_disable_lifecycle_preserves_unknown_attempt_for_reconciliation(database):
    scope = TenantScope("org-org", "dev-project")
    prepare_request, _ = _resumed_activation(database, scope)
    occurrence_id, now = _seed_pending_occurrence(database, scope, prepare_request)
    attempt_id = uuid4()
    database.owner.execute(
        "UPDATE automation_occurrence SET status='needs_attention' WHERE occurrence_id=%s",
        (occurrence_id,),
    )
    database.owner.execute(
        """INSERT INTO automation_occurrence_dispatch_attempt(
             org_id,project_id,attempt_id,occurrence_id,claim_owner,target_idempotency_key,
             status,claimed_at,claim_until,resolved_at)
           VALUES(%s,%s,%s,%s,'old-worker','unknown-disable-target','unknown',%s,%s,%s)""",
        (*scope.key, attempt_id, occurrence_id, now, now + timedelta(minutes=5), now),
    )
    operation_id, revision = _begin_runtime_disable(database, scope, prepare_request)
    _complete_runtime_disable(database, scope, operation_id, revision)
    with _connection(database, runtime=True)(scope) as conn:
        receipt = EcommerceGrowthDisableDependent(
            schema=database.schema
        ).after_runtime_disabled(
            conn,
            org_id=scope.org_id,
            project_id=scope.project_id,
            runtime_operation_id=operation_id,
        )
        conn.commit()
    assert receipt is not None
    assert [item["attemptId"] for item in receipt.unknown_attempts] == [str(attempt_id)]
    assert database.owner.execute(
        "SELECT status FROM automation_occurrence_dispatch_attempt WHERE attempt_id=%s",
        (attempt_id,),
    ).fetchone()["status"] == "unknown"


def test_disable_lifecycle_is_noop_without_resumed_activation(database):
    scope = TenantScope("org-org", "dev-project")
    prepare_request = _seed(database, scope, pending_receipt=False)
    with _connection(database, runtime=True)(scope) as conn:
        accepted = RuntimeOperationStore().accept(
            conn,
            org_id=scope.org_id,
            project_id=scope.project_id,
            installation_id=prepare_request.target_installation_id,
            kind="disable",
            idempotency_key="d6-unrelated-disable",
            requested_by="runtime-owner",
            expected_installation_etag=1,
            deadline=datetime.now(timezone.utc) + timedelta(minutes=5),
            binding_target={
                "generation": str(prepare_request.target_generation),
                "bindingRevision": 13,
            },
        )
        RuntimeBindingStore().fence(
            conn,
            org_id=scope.org_id,
            project_id=scope.project_id,
            installation_id=prepare_request.target_installation_id,
            generation=prepare_request.target_generation,
            operation_id=accepted.operation_id,
            expected_operation_revision=accepted.revision,
            expected_binding_revision=13,
        )
        assert EcommerceGrowthDisableDependent(
            schema=database.schema
        ).after_runtime_fenced(
            conn,
            org_id=scope.org_id,
            project_id=scope.project_id,
            runtime_operation_id=accepted.operation_id,
        ) is None
        conn.commit()
    assert database.owner.execute(
        "SELECT count(*) AS n FROM extension_dispatch_lifecycle_operation"
    ).fetchone()["n"] == 0


def test_ar2_017_nonempty_lifecycle_authority_blocks_downgrade(database):
    scope = TenantScope("org-org", "dev-project")
    prepare_request, _ = _resumed_activation(database, scope)
    _begin_runtime_disable(database, scope, prepare_request)
    with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState):
        _downgrade_ar2_017(database)


@pytest.mark.parametrize("removed", [True, False])
def test_runtime_uninstall_cleanup_is_one_shot_after_exact_detach(database, removed):
    scope = TenantScope("org-org", "dev-project")
    prepare_request, _ = _resumed_activation(database, scope)
    intent = _seed_owned_runtime_resource(database, scope, prepare_request)
    operation_id, revision = _begin_runtime_disable(database, scope, prepare_request)
    _complete_runtime_disable(database, scope, operation_id, revision)
    with _connection(database, runtime=True)(scope) as conn:
        EcommerceGrowthDisableDependent(schema=database.schema).after_runtime_disabled(
            conn,
            org_id=scope.org_id,
            project_id=scope.project_id,
            runtime_operation_id=operation_id,
        )
        conn.commit()

    class Driver:
        context = "colima-aos-extension"

        def __init__(self):
            self.calls = 0

        def require_isolation(self):
            return None

        def remove_owned(self, name, owner, *, expected_container_id):
            self.calls += 1
            assert (name, owner) == (intent.identity.name, intent.identity.owner)
            assert expected_container_id == "b" * 64
            return removed

    driver = Driver()
    executor = RuntimeUninstallCleanupExecutor(
        connect=_idle_runtime_connection(database), driver=driver
    )
    first = executor.run_one(
        org_id=scope.org_id,
        project_id=scope.project_id,
        installation_id=prepare_request.target_installation_id,
        generation=prepare_request.target_generation,
        resource_id=intent.resource_id,
    )
    second = executor.run_one(
        org_id=scope.org_id,
        project_id=scope.project_id,
        installation_id=prepare_request.target_installation_id,
        generation=prepare_request.target_generation,
        resource_id=intent.resource_id,
    )
    assert first == ("released" if removed else "uncertain")
    assert second == first
    assert driver.calls == 1
    assert database.owner.execute(
        """SELECT cleanup_state,observed_release
             FROM extension_runtime_resource_lease WHERE resource_id=%s""",
        (intent.resource_id,),
    ).fetchone() == {
        "cleanup_state": first,
        "observed_release": removed,
    }


def test_runtime_uninstall_cleanup_rejects_before_disable_detach(database):
    scope = TenantScope("org-org", "dev-project")
    prepare_request, _ = _resumed_activation(database, scope)
    intent = _seed_owned_runtime_resource(database, scope, prepare_request)

    class Driver:
        context = "colima-aos-extension"

        @staticmethod
        def require_isolation():
            raise AssertionError("unauthorized cleanup touched OCI")

        @staticmethod
        def remove_owned(*_args, **_kwargs):
            raise AssertionError("unauthorized cleanup touched OCI")

    executor = RuntimeUninstallCleanupExecutor(
        connect=_idle_runtime_connection(database), driver=Driver()
    )
    with pytest.raises(ValueError, match="runtime is not disabled"):
        executor.run_one(
            org_id=scope.org_id,
            project_id=scope.project_id,
            installation_id=prepare_request.target_installation_id,
            generation=prepare_request.target_generation,
            resource_id=intent.resource_id,
        )
    assert database.owner.execute(
        """SELECT cleanup_state,observed_release
             FROM extension_runtime_resource_lease WHERE resource_id=%s""",
        (intent.resource_id,),
    ).fetchone() == {"cleanup_state": "pending", "observed_release": False}


def test_runtime_uninstall_guard_commits_exact_terminal_authority(database):
    scope = TenantScope("org-org", "dev-project")
    request = _detach_and_release_runtime(database, scope)
    with _connection(database, app=True)(scope) as conn:
        receipt = RuntimeUninstallGuard().before_uninstall(
            conn,
            org_id=scope.org_id,
            project_id=scope.project_id,
            installation_id=request.target_installation_id,
            expected_installation_revision=1,
            actor="asset-operator",
        )
        assert receipt["authorityData"]["releasedResourceCount"] == 1
        assert receipt["authorityData"]["legacyDispatchCount"] == 9
        terminal_binding_revision = receipt["authorityData"]["bindingToRevision"]
        _append_minimal_uninstalled_revision(
            conn, scope, request.target_installation_id, 1
        )
        conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
        conn.commit()
    assert database.owner.execute(
        """SELECT desired_state,observed_state,enabled,operation_fence,revision
             FROM extension_runtime_binding WHERE org_id=%s AND project_id=%s
               AND installation_id=%s AND generation=%s""",
        (*scope.key, request.target_installation_id, request.target_generation),
    ).fetchone() == {
        "desired_state": "uninstalled",
        "observed_state": "stopped",
        "enabled": False,
        "operation_fence": True,
        "revision": terminal_binding_revision,
    }


def test_reinstall_uses_new_authority_and_preserves_old_audit_history(database):
    scope = TenantScope("org-org", "dev-project")
    old_request, _ = _resumed_activation(database, scope)
    old_dispatch = database.owner.execute(
        """SELECT operation_id,handler_kind,revision,installation_id,generation,
                  execution_epoch,cutover_group_id,cutover_group_revision
             FROM extension_operation_dispatch_binding
            WHERE org_id=%s AND project_id=%s AND operation_id=%s""",
        (*scope.key, "ecommerce_growth_analysis_advance"),
    ).fetchone()
    old_dispatch_ref = IssuedDispatchRef(
        org_id=scope.org_id,
        project_id=scope.project_id,
        operation_id=old_dispatch["operation_id"],
        handler_kind=old_dispatch["handler_kind"],
        dispatch_revision=old_dispatch["revision"],
        installation_id=str(old_dispatch["installation_id"]),
        generation=str(old_dispatch["generation"]),
        execution_epoch=old_dispatch["execution_epoch"],
        cutover_group_id=str(old_dispatch["cutover_group_id"]),
        cutover_group_revision=old_dispatch["cutover_group_revision"],
    )
    old_validate = database.owner.execute(
        """SELECT receipt_id,content_hash FROM extension_dispatch_cutover_receipt
            WHERE org_id=%s AND project_id=%s AND cutover_operation_id=%s
              AND phase='validate'""",
        (*scope.key, old_request.cutover_operation_id),
    ).fetchone()
    old_validate_ref = CutoverExactRef(
        resourceType="CutoverValidateReceipt",
        resourceId=str(old_validate["receipt_id"]),
        revision=1,
        contentHash=old_validate["content_hash"],
    )

    old_intent = _detach_and_release_existing_runtime(database, scope, old_request)
    with _connection(database, app=True)(scope) as conn:
        uninstall_receipt = RuntimeUninstallGuard().before_uninstall(
            conn,
            org_id=scope.org_id,
            project_id=scope.project_id,
            installation_id=old_request.target_installation_id,
            expected_installation_revision=1,
            actor="asset-operator",
        )
        _append_minimal_uninstalled_revision(
            conn, scope, old_request.target_installation_id, 1
        )
        conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
        conn.commit()

    legacy_group_revision = database.owner.execute(
        """SELECT min(cutover_group_revision) AS revision
             FROM extension_operation_dispatch_binding
            WHERE org_id=%s AND project_id=%s AND cutover_group_id=%s
              AND handler_kind='legacy'""",
        (*scope.key, old_request.cutover_group_id),
    ).fetchone()["revision"]
    new_request = _seed(
        database,
        scope,
        pending_receipt=False,
        suffix="-reinstall",
        existing_group=old_request.cutover_group_id,
        expected_group_revision=legacy_group_revision,
        target_execution_epoch=1,
        target_runtime_revision=13,
    )
    new_intent = _seed_owned_runtime_resource(database, scope, new_request)
    assert new_request.target_installation_id != old_request.target_installation_id
    assert new_request.target_generation != old_request.target_generation
    assert new_request.target_execution_epoch != old_request.target_execution_epoch
    package_hashes = database.owner.execute(
        """SELECT resource_id,package_hash FROM extension_runtime_resource_lease
            WHERE org_id=%s AND project_id=%s AND resource_id IN (%s,%s)""",
        (*scope.key, old_intent.resource_id, new_intent.resource_id),
    ).fetchall()
    assert len(package_hashes) == 2
    assert {row["package_hash"] for row in package_hashes} == {
        "sha256:" + "a" * 64
    }

    store = EcommerceGrowthCutoverStore(_connection(database), schema=database.schema)
    stale_approval_request = new_request.model_copy(
        update={
            "cutover_operation_id": uuid4(),
            "idempotency_key": "prepare-cutover-old-approval",
            "approval_ref": old_request.approval_ref,
        }
    )
    with pytest.raises(
        EcommerceGrowthCutoverBlocked, match="approval is not bound to this exact group"
    ):
        store.prepare_activation(scope, stale_approval_request, actor="runtime-owner")

    prepared = store.prepare_activation(scope, new_request, actor="runtime-owner")
    commit_request = _commit_request(prepared, suffix="-reinstall")
    store.begin_activation_commit(scope, commit_request, actor="runtime-owner")
    committed = store.commit_activation(scope, commit_request, actor="runtime-owner")
    finalize_request = _finalize_request(committed, suffix="-reinstall")
    validated = store.validate_activation(scope, finalize_request, actor="runtime-owner")
    with pytest.raises(
        EcommerceGrowthCutoverConflict, match="validate Receipt reference drifted"
    ):
        store.resume_activation(
            scope,
            finalize_request,
            validate_receipt_ref=old_validate_ref,
            actor="runtime-owner",
        )
    store.resume_activation(
        scope,
        finalize_request,
        validate_receipt_ref=_validate_ref(validated),
        actor="runtime-owner",
    )

    current_dispatch = database.owner.execute(
        """SELECT handler_kind,installation_id,generation,execution_epoch,
                  operation_fence,cutover_group_id,cutover_group_revision
             FROM extension_operation_dispatch_binding
            WHERE org_id=%s AND project_id=%s
            ORDER BY operation_id""",
        scope.key,
    ).fetchall()
    assert len(current_dispatch) == len(ECOMMERCE_GROWTH_OPERATIONS)
    assert all(
        row["handler_kind"] == "extension"
        and row["installation_id"] == new_request.target_installation_id
        and row["generation"] == new_request.target_generation
        and row["execution_epoch"] == new_request.target_execution_epoch
        and row["operation_fence"] is False
        and row["cutover_group_id"] == old_request.cutover_group_id
        and row["cutover_group_revision"] > old_dispatch_ref.cutover_group_revision
        for row in current_dispatch
    )
    _migration(database.root, "a0v_028_dispatch_read_lock.py", database.owner, schema=database.schema)
    with psycopg.connect(
        **{**PG, "user": database.role}, autocommit=False, row_factory=dict_row
    ) as conn:
        conn.isolation_level = IsolationLevel.SERIALIZABLE
        conn.execute(
            sql.SQL("SET search_path TO {}").format(sql.Identifier(database.schema))
        )
        conn.execute("SELECT set_config('aos.org_id',%s,true)", (scope.org_id,))
        conn.execute("SELECT set_config('aos.project_id',%s,true)", (scope.project_id,))
        with pytest.raises(
            EcommerceGrowthHostConflict, match="exact dispatch authority drifted"
        ):
            conn.execute("SET LOCAL ROLE aos_runtime")
            class SchemaLockConnection:
                def execute(self, query, params=()):
                    return conn.execute(query.replace(
                        "public.extension_dispatch_lock_group_a0v_028",
                        database.schema + ".extension_dispatch_lock_group_a0v_028",
                    ), params)
            LockedEcommerceGrowthHostPort._lock_and_revalidate(
                SchemaLockConnection(), scope, old_dispatch_ref
            )

    same_key_operations = database.owner.execute(
        """SELECT installation_id,operation_id FROM extension_runtime_operation
            WHERE org_id=%s AND project_id=%s AND kind='runtime-apply'
              AND idempotency_key='d6-owned-resource'
            ORDER BY installation_id""",
        scope.key,
    ).fetchall()
    assert len(same_key_operations) == 2
    assert len({row["installation_id"] for row in same_key_operations}) == 2
    assert len({row["operation_id"] for row in same_key_operations}) == 2
    assert database.owner.execute(
        """SELECT count(*) AS n FROM extension_runtime_uninstall_receipt
            WHERE org_id=%s AND project_id=%s AND installation_id=%s
              AND receipt_id=%s""",
        (*scope.key, old_request.target_installation_id,
         uninstall_receipt["receiptId"]),
    ).fetchone()["n"] == 1


@pytest.mark.skipif(
    os.getenv("AOS_EXTENSION_OCI_TEST") != "1",
    reason="explicit isolated OCI environment required",
)
def test_same_digest_reinstall_observes_exact_physical_oci_release(
    database, tmp_path
):
    scope = TenantScope("org-org", "dev-project")
    context = "colima-aos-extension"
    driver = OciDriver(context=context)
    cleanup_driver = CleanupOnlyOciDriver(driver)
    driver.require_isolation()
    image_dir = tmp_path / "same-digest-runtime"
    image_dir.mkdir()
    (image_dir / "runner.py").write_text(
        "import time\ntime.sleep(300)\n", encoding="utf-8"
    )
    (image_dir / "Dockerfile").write_text(
        "FROM python:3.11-alpine\nCOPY runner.py /aos/runner.py\n",
        encoding="utf-8",
    )
    image_id = subprocess.check_output(
        [
            "docker", "--context", context, "build", "--network=none",
            "--pull=false", "-q", str(image_dir),
        ],
        text=True,
        timeout=60,
    ).strip()
    assert image_id.startswith("sha256:") and len(image_id) == 71
    created: list[tuple[str, str, str]] = []

    def create_and_observe(request):
        intent = _seed_owned_runtime_resource(
            database,
            scope,
            request,
            package_hash=image_id,
            created_container_id=None,
        )
        container_id = driver.create_session(
            image_id, intent.identity.name, intent.identity.owner
        )
        created.append((intent.identity.name, intent.identity.owner, container_id))
        subprocess.run(
            ["docker", "--context", context, "start", container_id],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
        observed = subprocess.check_output(
            [
                "docker", "--context", context, "inspect", "--format",
                "{{.Id}}|{{index .Config.Labels \"aos.extension.owner\"}}|"
                "{{.State.Running}}|{{.Config.User}}|{{.HostConfig.NetworkMode}}|"
                "{{.HostConfig.ReadonlyRootfs}}|{{json .HostConfig.SecurityOpt}}",
                intent.identity.name,
            ],
            text=True,
            timeout=15,
        ).strip().split("|", 6)
        assert observed[:6] == [
            container_id,
            intent.identity.owner,
            "true",
            "65534:65534",
            "none",
            "true",
        ]
        security_options = json.loads(observed[6])
        assert "no-new-privileges" in security_options
        assert any(item.startswith("seccomp=") for item in security_options)
        _record_owned_runtime_container(
            database, scope, intent, container_id
        )
        return intent, container_id

    def assert_absent(name):
        result = subprocess.run(
            ["docker", "--context", context, "inspect", name],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode != 0 and "no such" in result.stderr.lower()

    try:
        old_request, _ = _resumed_activation(database, scope)
        old_intent, old_container_id = create_and_observe(old_request)
        _detach_and_release_existing_runtime(
            database,
            scope,
            old_request,
            intent=old_intent,
            cleanup_driver=cleanup_driver,
        )
        assert_absent(old_intent.identity.name)
        assert database.owner.execute(
            """SELECT package_hash,container_id,cleanup_state,observed_release
                FROM extension_runtime_resource_lease WHERE resource_id=%s""",
            (old_intent.resource_id,),
        ).fetchone() == {
            "package_hash": image_id,
            "container_id": old_container_id,
            "cleanup_state": "released",
            "observed_release": True,
        }
        with _connection(database, app=True)(scope) as conn:
            RuntimeUninstallGuard().before_uninstall(
                conn,
                org_id=scope.org_id,
                project_id=scope.project_id,
                installation_id=old_request.target_installation_id,
                expected_installation_revision=1,
                actor="asset-operator",
            )
            _append_minimal_uninstalled_revision(
                conn, scope, old_request.target_installation_id, 1
            )
            conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
            conn.commit()

        legacy_group_revision = database.owner.execute(
            """SELECT min(cutover_group_revision) AS revision
                FROM extension_operation_dispatch_binding
                WHERE org_id=%s AND project_id=%s AND cutover_group_id=%s
                  AND handler_kind='legacy'""",
            (*scope.key, old_request.cutover_group_id),
        ).fetchone()["revision"]
        new_request = _seed(
            database,
            scope,
            pending_receipt=False,
            suffix="-oci-reinstall",
            existing_group=old_request.cutover_group_id,
            expected_group_revision=legacy_group_revision,
            target_execution_epoch=1,
            target_runtime_revision=13,
        )
        new_intent, new_container_id = create_and_observe(new_request)
        assert new_container_id != old_container_id
        prepared = EcommerceGrowthCutoverStore(
            _connection(database), schema=database.schema
        ).prepare_activation(scope, new_request, actor="runtime-owner")
        store = EcommerceGrowthCutoverStore(
            _connection(database), schema=database.schema
        )
        commit_request = _commit_request(prepared, suffix="-oci-reinstall")
        store.begin_activation_commit(scope, commit_request, actor="runtime-owner")
        committed = store.commit_activation(
            scope, commit_request, actor="runtime-owner"
        )
        finalize_request = _finalize_request(
            committed, suffix="-oci-reinstall"
        )
        validated = store.validate_activation(
            scope, finalize_request, actor="runtime-owner"
        )
        store.resume_activation(
            scope,
            finalize_request,
            validate_receipt_ref=_validate_ref(validated),
            actor="runtime-owner",
        )
        assert database.owner.execute(
            """SELECT count(*) AS n FROM extension_operation_dispatch_binding
                WHERE org_id=%s AND project_id=%s AND handler_kind='extension'
                  AND installation_id=%s AND generation=%s
                  AND execution_epoch=%s AND NOT operation_fence""",
            (*scope.key, new_request.target_installation_id,
             new_request.target_generation, new_request.target_execution_epoch),
        ).fetchone()["n"] == len(ECOMMERCE_GROWTH_OPERATIONS)
        _detach_and_release_existing_runtime(
            database,
            scope,
            new_request,
            intent=new_intent,
            cleanup_driver=cleanup_driver,
        )
        assert_absent(new_intent.identity.name)
        assert database.owner.execute(
            """SELECT package_hash,container_id,cleanup_state,observed_release
                FROM extension_runtime_resource_lease WHERE resource_id=%s""",
            (new_intent.resource_id,),
        ).fetchone() == {
            "package_hash": image_id,
            "container_id": new_container_id,
            "cleanup_state": "released",
            "observed_release": True,
        }
    finally:
        for name, owner, container_id in created:
            try:
                driver.remove_owned(
                    name, owner, expected_container_id=container_id
                )
            except (RuntimeError, subprocess.SubprocessError):
                pass
        subprocess.run(
            ["docker", "--context", context, "image", "rm", image_id],
            capture_output=True,
            text=True,
            timeout=15,
        )
    assert database.owner.execute(
        """SELECT count(*) AS n FROM extension_dispatch_lifecycle_receipt receipt
            JOIN extension_runtime_operation operation
              ON operation.org_id=receipt.org_id
             AND operation.project_id=receipt.project_id
             AND operation.operation_id=receipt.runtime_operation_id
            WHERE receipt.org_id=%s AND receipt.project_id=%s
              AND operation.installation_id=%s""",
        (*scope.key, old_request.target_installation_id),
    ).fetchone()["n"] == 2
    assert database.owner.execute(
        """SELECT count(*) AS n FROM bundle_installation_revision r
            JOIN bundle_installation i USING(org_id,project_id,installation_pk)
            WHERE i.org_id=%s AND i.project_id=%s AND i.installation_id=%s
              AND r.state='uninstalled'""",
        (*scope.key, old_request.target_installation_id),
    ).fetchone()["n"] == 1


def test_runtime_uninstall_guard_rejects_unreleased_resource(database):
    scope = TenantScope("org-org", "dev-project")
    request, _ = _resumed_activation(database, scope)
    _seed_owned_runtime_resource(database, scope, request)
    operation_id, revision = _begin_runtime_disable(database, scope, request)
    _complete_runtime_disable(database, scope, operation_id, revision)
    with _connection(database, runtime=True)(scope) as conn:
        EcommerceGrowthDisableDependent(schema=database.schema).after_runtime_disabled(
            conn,
            org_id=scope.org_id,
            project_id=scope.project_id,
            runtime_operation_id=operation_id,
        )
        conn.commit()
    with pytest.raises(
        psycopg.errors.ObjectNotInPrerequisiteState,
        match="resources are not confirmed released",
    ):
        with _connection(database, app=True)(scope) as conn:
            RuntimeUninstallGuard().before_uninstall(
                conn,
                org_id=scope.org_id,
                project_id=scope.project_id,
                installation_id=request.target_installation_id,
                expected_installation_revision=1,
                actor="asset-operator",
            )


def test_runtime_uninstall_guard_requires_same_transaction_installation_revision(database):
    scope = TenantScope("org-org", "dev-project")
    request = _detach_and_release_runtime(database, scope)
    with pytest.raises(
        psycopg.errors.CheckViolation,
        match="matching terminal installation Receipt",
    ):
        with _connection(database, app=True)(scope) as conn:
            RuntimeUninstallGuard().before_uninstall(
                conn,
                org_id=scope.org_id,
                project_id=scope.project_id,
                installation_id=request.target_installation_id,
                expected_installation_revision=1,
                actor="asset-operator",
            )
            conn.execute("SET CONSTRAINTS ALL IMMEDIATE")


def test_runtime_uninstall_guard_is_noop_without_runtime_binding(database):
    scope = TenantScope("org-org", "dev-project")
    installation_id = uuid4()
    database.owner.execute(
        "INSERT INTO bundle_installation(org_id,project_id,installation_id) VALUES(%s,%s,%s)",
        (*scope.key, installation_id),
    )
    database.owner.execute(
        """INSERT INTO bundle_installation_revision(org_id,project_id,installation_pk,revision,state)
           SELECT org_id,project_id,installation_pk,1,'active' FROM bundle_installation
           WHERE org_id=%s AND project_id=%s AND installation_id=%s""",
        (*scope.key, installation_id),
    )
    with _connection(database, app=True)(scope) as conn:
        assert RuntimeUninstallGuard().before_uninstall(
            conn,
            org_id=scope.org_id,
            project_id=scope.project_id,
            installation_id=installation_id,
            expected_installation_revision=1,
            actor="asset-operator",
        ) is None
        conn.rollback()


def test_runtime_role_cannot_call_application_uninstall_command(database):
    scope = TenantScope("org-org", "dev-project")
    request = _detach_and_release_runtime(database, scope)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with _connection(database, runtime=True)(scope) as conn:
            conn.execute(
                "SELECT * FROM extension_runtime_uninstall_commit_ar2_018(%s,1,'runtime')",
                (request.target_installation_id,),
            )


def test_dedicated_noninheriting_installation_command_role(database):
    scope = TenantScope("org-org", "dev-project")
    request = _detach_and_release_runtime(database, scope)
    role = "ar2_install_command_" + uuid4().hex[:12]
    owner = database.owner
    owner.execute("""CREATE TABLE bundle_installation_command(
        org_id text NOT NULL, project_id text NOT NULL, operation text NOT NULL,
        idempotency_key text NOT NULL, subject text NOT NULL, request_hash text NOT NULL,
        status_code smallint NOT NULL, response_json jsonb NOT NULL,
        response_etag text, created_at timestamptz NOT NULL DEFAULT now(),
        PRIMARY KEY(org_id,project_id,operation,idempotency_key))""")
    owner.execute("ALTER TABLE bundle_installation_command ENABLE ROW LEVEL SECURITY")
    owner.execute("ALTER TABLE bundle_installation_command FORCE ROW LEVEL SECURITY")
    owner.execute("""CREATE POLICY tenant_scope ON bundle_installation_command
        USING(org_id=current_setting('aos.org_id',true)
          AND project_id=current_setting('aos.project_id',true))
        WITH CHECK(org_id=current_setting('aos.org_id',true)
          AND project_id=current_setting('aos.project_id',true))""")
    owner.execute(sql.SQL("CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS").format(sql.Identifier(role)))
    try:
        owner.execute(sql.SQL("GRANT aos_app TO {} WITH INHERIT FALSE, SET FALSE").format(sql.Identifier(role)))
        with psycopg.connect(**{**PG, "user": role}, row_factory=dict_row) as conn:
            rights = conn.execute(
                "SELECT pg_has_role(session_user,'aos_app','MEMBER') AS member, "
                "pg_has_role(session_user,'aos_app','USAGE') AS usage, "
                "pg_has_role(session_user,'aos_app','SET') AS can_set"
            ).fetchone()
            assert rights == {"member": True, "usage": False, "can_set": False}
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute("SET ROLE aos_app")

        # A hidden schema may surface as UndefinedTable before table ACL is
        # evaluated; both are the intended no-grant denial.
        with pytest.raises((psycopg.errors.InsufficientPrivilege, psycopg.errors.UndefinedTable)):
            with psycopg.connect(**{**PG, "user": role}, row_factory=dict_row) as conn:
                conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(database.schema)))
                conn.execute("SELECT set_config('aos.org_id',%s,true)", (scope.org_id,))
                conn.execute("SELECT set_config('aos.project_id',%s,true)", (scope.project_id,))
                RuntimeUninstallGuard().before_uninstall(
                    conn, org_id=scope.org_id, project_id=scope.project_id,
                    installation_id=request.target_installation_id,
                    expected_installation_revision=1, actor="asset-operator",
                )

        owner.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(
            sql.Identifier(database.schema), sql.Identifier(role)))
        owner.execute(sql.SQL("GRANT SELECT ON {} TO {}").format(
            sql.Identifier(database.schema, "bundle_installation"), sql.Identifier(role)))
        owner.execute(sql.SQL(
            "GRANT UPDATE (current_revision,etag_version,active_revision) ON {} TO {}"
        ).format(sql.Identifier(database.schema, "bundle_installation"), sql.Identifier(role)))
        owner.execute(sql.SQL("GRANT SELECT,INSERT ON {} TO {}").format(
            sql.Identifier(database.schema, "bundle_installation_revision"), sql.Identifier(role)))
        owner.execute(sql.SQL("GRANT SELECT ON {} TO {}").format(
            sql.Identifier(database.schema, "extension_runtime_uninstall_receipt"), sql.Identifier(role)))
        owner.execute(sql.SQL("GRANT SELECT,INSERT ON {} TO {}").format(
            sql.Identifier(database.schema, "bundle_installation_command"), sql.Identifier(role)))
        owner.execute(sql.SQL("GRANT EXECUTE ON FUNCTION {}(uuid,bigint,text) TO {}").format(
            sql.Identifier(database.schema, "extension_runtime_uninstall_commit_ar2_018"),
            sql.Identifier(role)))
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with psycopg.connect(**{**PG, "user": role}, row_factory=dict_row) as conn:
                conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(database.schema)))
                conn.execute("SELECT set_config('aos.org_id',%s,true)", (scope.org_id,))
                conn.execute("SELECT set_config('aos.project_id',%s,true)", (scope.project_id,))
                conn.execute(
                    "UPDATE extension_runtime_binding SET enabled=false "
                    "WHERE org_id=%s AND project_id=%s AND installation_id=%s",
                    (*scope.key, request.target_installation_id),
                )
        with pytest.raises(psycopg.errors.SerializationFailure, match="current active installation authority"):
            with psycopg.connect(**{**PG, "user": role}, row_factory=dict_row) as conn:
                conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(database.schema)))
                conn.execute("SELECT set_config('aos.org_id',%s,true)", ("dev-org",))
                conn.execute("SELECT set_config('aos.project_id',%s,true)", (scope.project_id,))
                RuntimeUninstallGuard().before_uninstall(
                    conn, org_id=scope.org_id, project_id=scope.project_id,
                    installation_id=request.target_installation_id,
                    expected_installation_revision=1, actor="asset-operator",
                )
        @contextmanager
        def dedicated_connect():
            with psycopg.connect(**{**PG, "user": role}, row_factory=dict_row) as conn:
                conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(database.schema)))
                yield conn

        store = PostgresInstallationStore(dedicated_connect)
        command = dict(
            org_id=scope.org_id, project_id=scope.project_id,
            operation="bundle_installations.uninstall",
            idempotency_key="b57-dedicated-terminal", subject="asset-operator",
            request_hash="sha256:" + "a" * 64,
        )

        def terminal_handler(conn):
            terminal = RuntimeUninstallGuard().before_uninstall(
                conn, org_id=scope.org_id, project_id=scope.project_id,
                installation_id=request.target_installation_id,
                expected_installation_revision=1, actor="asset-operator",
            )
            assert terminal["authorityData"]["releasedResourceCount"] == 1
            _append_minimal_uninstalled_revision(
                conn, scope, request.target_installation_id, 1,
            )
            conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
            return CommandResult(200, {"state": "uninstalled"}, '"2"')

        def force_rollback(conn):
            RuntimeUninstallGuard().before_uninstall(
                conn, org_id=scope.org_id, project_id=scope.project_id,
                installation_id=request.target_installation_id,
                expected_installation_revision=1, actor="asset-operator",
            )
            raise RuntimeError("test-only forced command rollback")

        with pytest.raises(RuntimeError, match="forced command rollback"):
            store.execute_idempotent(**{**command, "idempotency_key": "b57-rollback"},
                                     handler=force_rollback)
        assert owner.execute(
            "SELECT count(*) AS n FROM extension_runtime_uninstall_receipt "
            "WHERE org_id=%s AND project_id=%s AND installation_id=%s",
            (*scope.key, request.target_installation_id),
        ).fetchone()["n"] == 0
        assert owner.execute(
            "SELECT count(*) AS n FROM bundle_installation_command "
            "WHERE org_id=%s AND project_id=%s",
            scope.key,
        ).fetchone()["n"] == 0

        first = store.execute_idempotent(**command, handler=terminal_handler)
        assert first.replayed is False and first.response_json == {"state": "uninstalled"}
        replay = store.execute_idempotent(**command,
            handler=lambda conn: pytest.fail("terminal handler was replayed"))
        assert replay.replayed is True and replay.response_json == first.response_json
        assert owner.execute(
            "SELECT count(*) AS n FROM extension_runtime_uninstall_receipt "
            "WHERE org_id=%s AND project_id=%s AND installation_id=%s",
            (*scope.key, request.target_installation_id),
        ).fetchone()["n"] == 1
        assert owner.execute(
            "SELECT count(*) AS n FROM bundle_installation_command "
            "WHERE org_id=%s AND project_id=%s AND operation=%s AND idempotency_key=%s",
            (*scope.key, command["operation"], command["idempotency_key"]),
        ).fetchone()["n"] == 1
    finally:
        owner.execute(sql.SQL("DROP OWNED BY {}").format(sql.Identifier(role)))
        owner.execute(sql.SQL("REVOKE aos_app FROM {}").format(sql.Identifier(role)))
        owner.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))


def test_direct_runtime_uninstall_binding_without_receipt_is_rejected(database):
    scope = TenantScope("org-org", "dev-project")
    request = _detach_and_release_runtime(database, scope)
    owner = database.owner
    owner.execute("SELECT set_config('aos.org_id',%s,false)", (scope.org_id,))
    owner.execute("SELECT set_config('aos.project_id',%s,false)", (scope.project_id,))
    with pytest.raises(
        psycopg.errors.CheckViolation,
        match="matching terminal installation Receipt",
    ):
        owner.execute(
            """UPDATE extension_runtime_binding SET desired_state='uninstalled',
                 observed_state='stopped',revision=revision+1
               WHERE org_id=%s AND project_id=%s AND installation_id=%s
                 AND generation=%s""",
            (*scope.key, request.target_installation_id, request.target_generation),
        )
