from importlib import util
from pathlib import Path
from unittest.mock import patch

import pytest

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_schedule_policy_control import (
    SchedulePolicyControlReceipt,
    SchedulePolicyControlStore,
)
from aos_api.tenant_scope import TenantScope


MIGRATION = Path(__file__).parents[1] / "alembic/versions/a0v_078_schedule_policy_control_receipt.py"
REPAIR_MIGRATION = Path(__file__).parents[1] / "alembic/versions/a0v_079_schedule_policy_control_case_hash.py"
APPROVAL_HASH_MIGRATION = Path(__file__).parents[1] / "alembic/versions/a0v_080_schedule_policy_control_approval_hash.py"
REQUEST_HASH_MIGRATION = Path(__file__).parents[1] / "alembic/versions/a0v_081_schedule_policy_control_request_hash.py"
SCHEDULE_CLOSURE_MIGRATION = Path(__file__).parents[1] / "alembic/versions/a0v_082_schedule_unaccepted_analysis_closure.py"
SCOPE = TenantScope("org-org", "dev-project")


def exact(kind, identity, digest):
    return InvestigationExactRef(
        resourceType=kind, resourceId=identity, revision=1,
        contentHash="sha256:" + digest * 64,
    ).model_dump(mode="json", by_alias=True)


def authority():
    body = {
        "schemaVersion": "aos.ecommerce.schedule-policy-control-receipt/v1",
        "tenant": {"orgId": "org-org", "projectId": "dev-project"},
        "policyRef": exact("SchedulePolicyRevision", "baseline-once", "a"),
        "caseRef": exact("BusinessInvestigationCaseRevision", "case-baseline", "b"),
        "approvalRef": exact("ActionApprovalEvent", "approval-1", "c"),
        "commandReceiptId": "command-receipt-1",
        "dispatch": {
            "installationId": "11111111-1111-4111-8111-111111111111",
            "generation": "22222222-2222-4222-8222-222222222222",
            "executionEpoch": 3,
        },
    }
    digest = canonical_sha256(body)
    return {
        **body,
        "receiptRef": exact("SchedulePolicyControlReceipt", "33333333-3333-4333-8333-333333333333", "d"),
        "contentHash": digest,
    } | {
        "receiptRef": {
            **exact("SchedulePolicyControlReceipt", "33333333-3333-4333-8333-333333333333", "d"),
            "contentHash": digest,
        }
    }


def test_receipt_requires_exact_hash_and_reference_kinds():
    value = SchedulePolicyControlReceipt.model_validate(authority())
    assert value.policy_ref.resource_id == "baseline-once"
    changed = authority()
    changed["contentHash"] = "sha256:" + "0" * 64
    changed["receiptRef"]["contentHash"] = changed["contentHash"]
    with pytest.raises(ValueError, match="content hash differs"):
        SchedulePolicyControlReceipt.model_validate(changed)


def test_store_calls_only_security_definer_and_reparses_authority():
    expected = authority()

    class Result:
        def fetchone(self): return {"authority": expected}

    class Connection:
        def execute(self, sql, params):
            assert "ecommerce_schedule_policy_control_put_a0v_078" in sql
            assert params[0].obj["idempotencyKey"] == "control-key"
            return Result()

    written = SchedulePolicyControlStore().put(
        HostTransaction(Connection()), SCOPE, idempotency_key="control-key",
        policy_ref=InvestigationExactRef.model_validate(expected["policyRef"]),
        case_ref=InvestigationExactRef.model_validate(expected["caseRef"]),
        approval_ref=InvestigationExactRef.model_validate(expected["approvalRef"]),
        installation_id=expected["dispatch"]["installationId"],
        generation=expected["dispatch"]["generation"], execution_epoch=3,
    )
    assert written.receipt_ref.resource_type == "SchedulePolicyControlReceipt"


def test_migration_is_single_successor_immutable_rls_and_exact_approval_bound():
    spec = util.spec_from_file_location("a0v_078", MIGRATION)
    assert spec and spec.loader
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.revision == "a0v_078" and module.down_revision == "a0v_077"
    statements = []
    with patch.object(module.op, "execute", statements.append):
        module.upgrade()
    sql = "\n".join(statements)
    assert "ecommerce_schedule_policy_control_receipt" in sql
    assert "BEFORE UPDATE OR DELETE" in sql
    assert "FORCE ROW LEVEL SECURITY" in sql
    assert "ecommerce_growth_schedule_put" in sql
    assert "aip_action_approval_event" in sql
    assert "expectedPolicyRevision" in sql and "expectedCaseVersion" in sql
    with pytest.raises(RuntimeError, match="must be retained"):
        module.downgrade()


def test_repair_migration_reads_case_hash_from_current_revision():
    spec = util.spec_from_file_location("a0v_079", REPAIR_MIGRATION)
    assert spec and spec.loader
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.revision == "a0v_079" and module.down_revision == "a0v_078"
    statements = []
    with patch.object(module.op, "execute", statements.append):
        module.upgrade()
    sql = "\n".join(statements)
    assert "CREATE OR REPLACE FUNCTION public.ecommerce_schedule_policy_control_put_a0v_078" in sql
    assert "JOIN public.ecommerce_investigation_case_revision r" in sql
    assert "r.revision=h.current_revision" in sql
    assert "SELECT current_revision,content_hash INTO v_case_head FROM public.ecommerce_investigation_case_head" not in sql
    with pytest.raises(RuntimeError, match="must be retained"):
        module.downgrade()


def test_approval_hash_repair_matches_application_datetime_profile():
    spec = util.spec_from_file_location("a0v_080", APPROVAL_HASH_MIGRATION)
    assert spec and spec.loader
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.revision == "a0v_080" and module.down_revision == "a0v_079"
    statements = []
    with patch.object(module.op, "execute", statements.append):
        module.upgrade()
    sql = "\n".join(statements)
    assert "CREATE OR REPLACE FUNCTION public.ecommerce_schedule_policy_control_put_a0v_078" in sql
    assert "AT TIME ZONE 'UTC'" in sql
    assert "YYYY-MM-DD HH24:MI:SS" in sql
    assert "||'+00:00'" in sql
    assert "'expires_at',v_approval.expires_at" not in sql
    assert "'created_at',v_approval.created_at" not in sql


def test_request_hash_repair_compares_approved_put_projection():
    spec = util.spec_from_file_location("a0v_081", REQUEST_HASH_MIGRATION)
    assert spec and spec.loader
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.revision == "a0v_081" and module.down_revision == "a0v_080"
    statements = []
    with patch.object(module.op, "execute", statements.append):
        module.upgrade()
    sql = "\n".join(statements)
    assert "v_command.policy_authority-" in sql
    assert "'schemaVersion','tenant','revision','version','priorRef','contentHash','createdBy','createdAt'" in sql
    assert "v_proposal.payload->>'policyHash' IS DISTINCT FROM v_policy->>'contentHash'" not in sql


def test_schedule_closure_requires_exact_control_and_proves_no_target_acceptance():
    spec = util.spec_from_file_location("a0v_082", SCHEDULE_CLOSURE_MIGRATION)
    assert spec and spec.loader
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.revision == "a0v_082" and module.down_revision == "a0v_081"
    statements = []
    with patch.object(module.op, "execute", statements.append):
        module.upgrade()
    sql = "\n".join(statements)
    assert "ecommerce_unaccepted_schedule_analysis_close_a0v_082" in sql
    assert "trigger_source<>'schedule'" in sql
    assert "operation_id<>'ecommerce_growth_schedule_trigger'" in sql
    assert "ecommerce_schedule_policy_control_receipt" in sql
    assert "ecommerce_growth_runtime_command_receipt" in sql
    assert "ecommerce_investigation_run" in sql
    assert "status='cancelled'" in sql and "status='closed_unaccepted'" in sql
    with pytest.raises(RuntimeError, match="must be retained"):
        module.downgrade()
