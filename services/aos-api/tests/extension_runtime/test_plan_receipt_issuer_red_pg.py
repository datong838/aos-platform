"""Isolated RED for original Plan writers and the shared Receipt ACL.

These xfails are release blockers, not a replacement for formal issuer proof.
"""

import psycopg
import pytest

from aos_api.aip_production_contract_store import AipProductionContractStore
from aos_api.tenant_scope import TenantScope
from current_configuration_sources_case import _migration, source_case
from test_lifecycle_pg import database


SCOPE = TenantScope("org-org", "dev-project")
PLAN_OPERATIONS = (
    "responsibility_plan.create", "responsibility_plan.revise",
    "responsibility_plan.freeze", "bi_responsibility_plan.prepare",
    "bi_responsibility_plan.rebind", "bi_responsibility_plan.freeze",
)


@pytest.fixture
def receipt_case(source_case):
    conn, refs = source_case
    conn.execute("RESET ROLE")
    conn.execute("""CREATE TABLE aip_task(
        org_id text NOT NULL, project_id text NOT NULL, task_id text NOT NULL,
        PRIMARY KEY(org_id,project_id,task_id))""")
    _migration(conn, "w2_001_brief_evidence.py", "s3owd_original_receipt")
    conn.execute("SET ROLE aos_runtime")
    return conn, refs


@pytest.mark.parametrize("plan_id", (
    "unissued-generic-plan", "responsibility-plan-successor-unissued",
))
@pytest.mark.xfail(strict=True, reason="original runtime role can write Plan head directly")
def test_runtime_cannot_directly_issue_generic_or_successor_plan_head(source_case, plan_id):
    conn, _ = source_case
    conn.execute("RESET ROLE")
    try:
        conn.execute("SET SESSION AUTHORIZATION aos_runtime")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with conn.transaction():
                conn.execute("""INSERT INTO aip_responsibility_plan_head
                    (org_id,project_id,plan_id,current_revision,version)
                    VALUES(%s,%s,%s,1,1)""", (*SCOPE.key, plan_id))
    finally:
        conn.execute("RESET SESSION AUTHORIZATION")
        conn.execute("SET ROLE aos_runtime")


@pytest.mark.parametrize("operation", PLAN_OPERATIONS)
@pytest.mark.xfail(strict=True, reason="shared Receipt permits forged Plan operations")
def test_runtime_cannot_forge_original_plan_receipt(receipt_case, operation):
    conn, _ = receipt_case
    conn.execute("RESET ROLE")
    try:
        conn.execute("SET SESSION AUTHORIZATION aos_runtime")
        store = object.__new__(AipProductionContractStore)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with conn.transaction():
                store._receipt(conn, SCOPE, operation, "unissued-key", "a" * 64,
                               {"resourceType": "ResponsibilityPlanRevision",
                                "resourceId": "unissued-plan", "revision": 1,
                                "contentHash": "b" * 64}, "unissued-actor")
    finally:
        conn.execute("RESET SESSION AUTHORIZATION")
        conn.execute("SET ROLE aos_runtime")


def test_original_content_operation_keeps_shared_receipt_insert(receipt_case):
    conn, _ = receipt_case
    conn.execute("RESET ROLE")
    try:
        conn.execute("SET SESSION AUTHORIZATION aos_runtime")
        with conn.transaction():
            conn.execute("""INSERT INTO aip_production_contract_receipt
                (org_id,project_id,receipt_id,operation,idempotency_key,
                 request_hash,result_ref,created_by)
                VALUES(%s,%s,'content-receipt','content_draft.register',
                       'content-key',%s,%s::jsonb,'content-owner')""",
                (*SCOPE.key, "a" * 64, '{}'))
            assert conn.execute("""SELECT count(*) FROM aip_production_contract_receipt
                WHERE org_id=%s AND project_id=%s AND operation='content_draft.register'""",
                SCOPE.key).fetchone()[0] == 1
    finally:
        conn.execute("RESET SESSION AUTHORIZATION")
        conn.execute("SET ROLE aos_runtime")
