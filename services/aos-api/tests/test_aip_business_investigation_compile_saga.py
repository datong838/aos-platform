"""BI-W6-01 Run-to-AIP compilation Receipt saga tests."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from alembic import command
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
import pytest

from aos_api.aip_business_investigation_compile_saga import (
    BusinessInvestigationCompilationReceiptStore,
    BusinessInvestigationCompilationReceiptWrite,
    BusinessInvestigationCompileConflict,
    BusinessInvestigationCompileSaga,
)
from aos_api.aip_business_investigation_compiler import (
    BusinessInvestigationCompilation,
)
from aos_api.aip_contracts import TenantContext
from aos_api.ecommerce_business_investigation_run import (
    BusinessInvestigationRunRecord,
    BusinessInvestigationRunStateRevision,
    BusinessInvestigationRunView,
)
from aos_api.tenant_scope import TenantScope
from test_aip_business_investigation_compiler import compile_request, ref
from tests.aip._migration_test_support import isolated_aip_migration_database


SCOPE = TenantScope("org-org", "dev-project")
OTHER_SCOPE = TenantScope("dev-org", "dev-project")
NOW = datetime(2026, 8, 26, 13, 0, tzinfo=UTC)


def domain_ref(kind: str, identity: str, revision: int = 1, fill: str = "a") -> dict:
    return {
        "resourceType": kind,
        "resourceId": identity,
        "revision": revision,
        "contentHash": f"sha256:{fill * 64}",
    }


def run_view(**authority_changes) -> BusinessInvestigationRunView:
    authority_payload = {
        "tenant": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "runId": "run-1",
        "version": 1,
        "contentHash": "sha256:" + "0" * 64,
        "caseRef": domain_ref(
            "BusinessInvestigationCaseRevision", "case-1", revision=2, fill="c"
        ),
        "analysisType": "initial_store_analysis",
        "triggerKind": "manual",
        "triggerKey": "manual-1",
        "lifecycle": "PREPARING",
        "control": "RUNNING",
        "createdBy": "owner",
        "createdAt": NOW,
    }
    authority_payload.update(authority_changes)
    provisional = BusinessInvestigationRunRecord.model_validate(authority_payload)
    authority_payload["contentHash"] = provisional.calculated_content_hash()
    authority = BusinessInvestigationRunRecord.model_validate(authority_payload)
    state_payload = {
        "tenant": authority.tenant.model_dump(mode="json", by_alias=True),
        "runId": authority.run_id,
        "version": 1,
        "lifecycle": authority.lifecycle,
        "control": authority.control,
        "eventSequence": 1,
        "contentHash": "sha256:" + "0" * 64,
        "createdBy": authority.created_by,
        "createdAt": authority.created_at,
    }
    provisional_state = BusinessInvestigationRunStateRevision.model_validate(state_payload)
    state_payload["contentHash"] = provisional_state.calculated_content_hash()
    return BusinessInvestigationRunView(
        authority=authority,
        state=BusinessInvestigationRunStateRevision.model_validate(state_payload),
    )


def request_for(run: BusinessInvestigationRunView, **changes):
    request = compile_request()
    request.run_ref = request.run_ref.model_copy(
        update={
            "resource_id": run.authority.run_id,
            "revision": run.authority.version,
            "content_hash": run.authority.content_hash.removeprefix("sha256:"),
        }
    )
    request.case_ref = request.case_ref.model_copy(
        update={
            "resource_id": run.authority.case_ref.resource_id,
            "revision": run.authority.case_ref.revision,
            "content_hash": run.authority.case_ref.content_hash.removeprefix("sha256:"),
        }
    )
    request.task_brief_spec.run_ref = request.run_ref
    request.task_brief_spec.case_ref = request.case_ref
    for key, value in changes.items():
        setattr(request, key, value)
    return request


def compilation(request=None, **changes) -> BusinessInvestigationCompilation:
    request = request or compile_request()
    value = {
        "tenant": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "taskId": request.task_id,
        "caseRef": request.case_ref.model_dump(mode="json", by_alias=True),
        "runRef": request.run_ref.model_dump(mode="json", by_alias=True),
        "taskBriefRef": request.task_brief_ref.model_dump(mode="json", by_alias=True),
        "profileRef": request.profile.exact_ref.model_dump(mode="json", by_alias=True),
        "logicRef": request.profile.logic_ref.model_dump(mode="json", by_alias=True),
        "stageTemplateRef": request.profile.stage_template_ref.model_dump(mode="json", by_alias=True),
        "orderedSkillRefs": [
            item.model_dump(mode="json", by_alias=True)
            for item in request.profile.ordered_skill_refs
        ],
        "skillBindingSetRef": request.profile.skill_binding_set_ref.model_dump(mode="json", by_alias=True),
        "responsibilityPlanRef": request.profile.responsibility_plan_ref.model_dump(mode="json", by_alias=True),
        "productionContextRef": request.profile.production_context_ref.model_dump(mode="json", by_alias=True),
        "planRef": ref("PlanRevision", "plan-1", fill="f"),
        "normalizedStageIds": ["portrait", "diagnosis", "solution-design"],
        "stageCompilationHash": "1" * 64,
        "inputHash": "2" * 64,
        "compilationHash": "3" * 64,
        "runtimeAuthorized": False,
        "createdAt": NOW,
    }
    value.update(changes)
    return BusinessInvestigationCompilation.model_validate(value)


class FixedCompiler:
    def __init__(self, result=None):
        self.result = result
        self.calls = []

    def compile(self, scope, actor, key, request):
        self.calls.append((scope, actor, key, request))
        return self.result or compilation(request)


class MemoryReceipts:
    def __init__(self):
        self.by_command = {}
        self.record_calls = []

    def get(self, _scope, command_id):
        return self.by_command.get(command_id)

    def record(self, _scope, receipt):
        self.record_calls.append(receipt)
        existing = self.by_command.get(receipt.command_id)
        if existing is not None:
            if existing.request_hash != receipt.request_hash:
                raise BusinessInvestigationCompileConflict("conflict")
            return BusinessInvestigationCompilationReceiptWrite(existing, True)
        self.by_command[receipt.command_id] = receipt
        return BusinessInvestigationCompilationReceiptWrite(receipt, False)


def test_saga_derives_stable_ids_and_replays_without_second_compile() -> None:
    compiler = FixedCompiler()
    receipts = MemoryReceipts()
    saga = BusinessInvestigationCompileSaga(compiler, receipts)

    run = run_view()
    request = request_for(run)
    first = saga.execute(SCOPE, "owner", "trigger-1", run, request)
    second = saga.execute(SCOPE, "owner", "trigger-1", run, request)

    assert first.replayed is False
    assert second.replayed is True
    assert second.authority == first.authority
    assert first.authority.command_id.startswith("bi-compile-")
    assert first.authority.receipt_id.startswith("bi-compilation-receipt-")
    assert first.authority.request_hash.startswith("sha256:")
    assert first.authority.run_ref.content_hash.startswith("sha256:")
    assert not first.authority.plan_ref.content_hash.startswith("sha256:")
    assert first.authority.runtime_authorized is False
    assert len(compiler.calls) == 1
    assert compiler.calls[0][2] == first.authority.command_id


def test_same_command_different_request_hash_conflicts_before_compile() -> None:
    compiler = FixedCompiler()
    receipts = MemoryReceipts()
    saga = BusinessInvestigationCompileSaga(compiler, receipts)
    run = run_view()
    saga.execute(SCOPE, "owner", "trigger-1", run, request_for(run))
    changed = request_for(run, expected_task_version=2)

    with pytest.raises(BusinessInvestigationCompileConflict, match="request hash conflict"):
        saga.execute(SCOPE, "owner", "trigger-1", run_view(), changed)
    assert len(compiler.calls) == 1


def test_tenant_run_and_case_drift_fail_before_side_effect() -> None:
    cases = []
    run = run_view()
    cases.append((OTHER_SCOPE, run, request_for(run), "tenant"))
    wrong_run = request_for(run)
    wrong_run.run_ref = wrong_run.run_ref.model_copy(update={"resource_id": "run-other"})
    wrong_run.task_brief_spec.run_ref = wrong_run.run_ref
    cases.append((SCOPE, run, wrong_run, "Run exact ref"))
    wrong_case = request_for(run)
    wrong_case.case_ref = wrong_case.case_ref.model_copy(update={"resource_id": "case-other"})
    wrong_case.task_brief_spec.case_ref = wrong_case.case_ref
    cases.append((SCOPE, run, wrong_case, "Case exact ref"))

    for scope, run, request, message in cases:
        compiler = FixedCompiler()
        receipts = MemoryReceipts()
        with pytest.raises(BusinessInvestigationCompileConflict, match=message):
            BusinessInvestigationCompileSaga(compiler, receipts).execute(
                scope, "owner", "trigger-1", run, request
            )
        assert compiler.calls == []
        assert receipts.record_calls == []


def test_non_preparing_run_and_compilation_drift_fail_closed() -> None:
    run = run_view()
    run.state.control = "PAUSED"
    compiler = FixedCompiler()
    receipts = MemoryReceipts()
    with pytest.raises(BusinessInvestigationCompileConflict, match="PREPARING and RUNNING"):
        BusinessInvestigationCompileSaga(compiler, receipts).execute(
            SCOPE, "owner", "trigger-1", run, request_for(run)
        )
    assert compiler.calls == []

    run = run_view()
    request = request_for(run)
    compiler = FixedCompiler(compilation(request, taskId="task-drift"))
    with pytest.raises(BusinessInvestigationCompileConflict, match="task drifted"):
        BusinessInvestigationCompileSaga(compiler, MemoryReceipts()).execute(
            SCOPE, "owner", "trigger-1", run, request
        )
    assert len(compiler.calls) == 1


def test_migration_is_additive_tenant_scoped_immutable_and_fail_closed() -> None:
    migration = Path(__file__).parents[1] / "alembic" / "versions" / "biw6_001_investigation_compile_receipt.py"
    source = migration.read_text()
    assert 'down_revision: str | Sequence[str] | None = "biw4_007"' in source
    assert "ENABLE ROW LEVEL SECURITY" in source
    assert "FORCE ROW LEVEL SECURITY" in source
    assert "REVOKE INSERT,UPDATE,DELETE,TRUNCATE" in source
    assert "SECURITY DEFINER SET search_path=pg_catalog,public" in source
    assert "pg_advisory_xact_lock" in source
    assert "Compilation receipt command conflict" in source
    assert "Exact PREPARING RUNNING Run is required" in source
    assert "Exact canonical Plan is required" in source
    assert "cannot downgrade biw6_001 with compilation receipt authority" in source


def test_disposable_database_receipt_replay_isolation_immutability_and_restart() -> None:
    with isolated_aip_migration_database("biw6_compile_receipt") as (config, dsn):
        run = run_view()
        request = request_for(run)
        result = compilation(request)
        with psycopg.connect(dsn) as conn:
            conn.execute(
                "INSERT INTO twa_workspace(org_id,project_id,name) VALUES(%s,%s,'BI-W6') ON CONFLICT DO NOTHING",
                SCOPE.key,
            )
            conn.execute(
                """INSERT INTO ecommerce_investigation_case_head(
                org_id,project_id,case_id,current_revision,version,lifecycle,analysis_type,
                channel_id,business_entity_id)
                VALUES(%s,%s,'case-1',2,2,'ACTIVE','initial_store_analysis','private-mall','store-1')""",
                SCOPE.key,
            )
            conn.execute(
                """INSERT INTO ecommerce_investigation_case_revision(
                org_id,project_id,case_id,revision,version,prior_revision,content_hash,lifecycle,
                analysis_type,channel_id,business_entity_id,entity_channel_binding_id,
                idempotency_key,request_hash,authority_data,created_by,created_at)
                VALUES(%s,%s,'case-1',2,2,1,%s,'ACTIVE','initial_store_analysis',
                'private-mall','store-1','binding-store-1','case-seed',%s,'{}','owner',%s)""",
                (*SCOPE.key, run.authority.case_ref.content_hash, "sha256:" + "9" * 64, NOW),
            )
            payload = run.authority.model_dump(mode="json", by_alias=True)
            conn.execute(
                """INSERT INTO ecommerce_investigation_run(
                org_id,project_id,run_id,version,content_hash,case_id,case_revision,lifecycle,
                control,analysis_type,trigger_kind,trigger_key,current_event_sequence,
                authority_data,created_by,created_at)
                VALUES(%s,%s,%s,1,%s,'case-1',2,'PREPARING','RUNNING',
                'initial_store_analysis','manual','manual-1',1,%s,'owner',%s)""",
                (*SCOPE.key, run.authority.run_id, run.authority.content_hash, Jsonb(payload), NOW),
            )
            conn.execute(
                """INSERT INTO aip_task(org_id,project_id,task_id,task_type,title,status,
                idempotency_key,request_hash,created_by)
                VALUES(%s,%s,'task-1','business_investigation','BI task','planning',
                'task-seed',%s,'owner')""",
                (*SCOPE.key, "a" * 64),
            )
            conn.execute(
                """INSERT INTO aip_plan_revision(
                org_id,project_id,plan_revision_id,task_id,revision,content_hash,steps,
                idempotency_key,request_hash,created_by)
                VALUES(%s,%s,'plan-1','task-1',1,%s,'[]','plan-seed',%s,'owner')""",
                (*SCOPE.key, "f" * 64, "b" * 64),
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

        compiler = FixedCompiler(result)
        first = BusinessInvestigationCompileSaga(
            compiler, BusinessInvestigationCompilationReceiptStore(runtime_connect)
        ).execute(SCOPE, "owner", "trigger-db-1", run, request)
        assert first.replayed is False
        restarted_store = BusinessInvestigationCompilationReceiptStore(runtime_connect)
        second = BusinessInvestigationCompileSaga(compiler, restarted_store).execute(
            SCOPE, "owner", "trigger-db-1", run, request
        )
        assert second.replayed is True and second.authority == first.authority
        assert len(compiler.calls) == 1
        assert restarted_store.get(OTHER_SCOPE, first.authority.command_id) is None
        with pytest.raises(BusinessInvestigationCompileConflict):
            restarted_store.record(
                SCOPE,
                first.authority.model_copy(
                    update={"request_hash": "sha256:" + "8" * 64}
                ),
            )

        with psycopg.connect(dsn) as conn:
            conn.execute("SET LOCAL ROLE aos_runtime")
            conn.execute(
                "SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",
                SCOPE.key,
            )
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(
                    "UPDATE aip_business_investigation_compile_receipt SET task_id='drift'"
                )
        with psycopg.connect(dsn) as conn:
            with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState):
                conn.execute(
                    "UPDATE aip_business_investigation_compile_receipt SET task_id='drift'"
                )
        with pytest.raises(Exception, match="cannot downgrade biw6_001"):
            command.downgrade(config, "biw4_007")
