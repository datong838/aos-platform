"""BI-W8 migration structure checks."""

from importlib import util
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from alembic import command
import psycopg
from psycopg.rows import dict_row
import pytest

from aos_api.ecommerce_business_investigation_application import EcommerceBusinessInvestigationApplication
from aos_api.ecommerce_business_investigation_case import BusinessInvestigationCaseStore
from aos_api.ecommerce_business_investigation_run import BusinessInvestigationRunStore
from aos_api.ecommerce_business_investigation_schedule import (
    BusinessInvestigationScheduleStore,
    PutBusinessInvestigationSchedulePolicyRequest,
    TriggerBusinessInvestigationScheduleRequest,
)
from aos_api.tenant_scope import TenantScope
from test_ecommerce_business_investigation_lifecycle import draft_case
from tests.aip._migration_test_support import isolated_aip_migration_database

MIGRATION = Path(__file__).parents[1] / "alembic/versions/biw8_001_investigation_schedule_policy.py"


def _migration():
    spec = util.spec_from_file_location("biw8_001", MIGRATION)
    assert spec and spec.loader
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_schedule_migration_is_single_successor_rls_receipt_and_atomic_case_bind() -> None:
    module = _migration()
    assert module.revision == "biw8_001" and module.down_revision == "biw6_002"
    statements: list[str] = []
    with patch.object(module.op, "execute", statements.append):
        module.upgrade()
    sql = "\n".join(statements)
    assert sql.count("ENABLE ROW LEVEL SECURITY") == 3
    assert sql.count("FORCE ROW LEVEL SECURITY") == 3
    assert "ecommerce_investigation_schedule_policy_command_receipt" in sql
    assert "ecommerce_investigation_schedule_policy_put_biw8_001" in sql
    assert "INSERT INTO ecommerce_investigation_case_revision" in sql
    assert "UPDATE ecommerce_investigation_case_head" in sql
    assert "overlapPolicy'<>'skip" in sql
    assert "GRANT INSERT" not in sql and "GRANT UPDATE" not in sql


def test_schedule_downgrade_refuses_non_empty_authority() -> None:
    module = _migration()
    statements: list[str] = []
    with patch.object(module.op, "execute", statements.append):
        module.downgrade()
    assert "cannot downgrade biw8_001 with SchedulePolicy authority" in statements[0]


def test_disposable_database_empty_schedule_upgrade_and_downgrade() -> None:
    with isolated_aip_migration_database("biw8_schedule_empty") as (config, _dsn):
        command.downgrade(config, "biw6_002")
        command.upgrade(config, "head")


def test_disposable_database_atomic_policy_trigger_overlap_rls_and_nonempty_guard() -> None:
    scope = TenantScope("org-org", "dev-project")
    with isolated_aip_migration_database("biw8_schedule_authority") as (config, dsn):
        with psycopg.connect(dsn) as conn:
            conn.execute(
                "INSERT INTO twa_workspace(org_id,project_id,name) VALUES('org-org','dev-project','BI-W8') ON CONFLICT DO NOTHING"
            )
            conn.execute(
                "INSERT INTO twa_workspace(org_id,project_id,name) VALUES('dev-org','dev-project','canary') ON CONFLICT DO NOTHING"
            )
            conn.commit()

        @contextmanager
        def runtime_connect(tenant_scope):
            with psycopg.connect(dsn, row_factory=dict_row) as conn:
                conn.execute("SET LOCAL ROLE aos_runtime")
                conn.execute("SELECT set_config('aos.org_id',%s,true)", (tenant_scope.org_id,))
                conn.execute("SELECT set_config('aos.project_id',%s,true)", (tenant_scope.project_id,))
                yield conn

        cases = BusinessInvestigationCaseStore(runtime_connect)
        runs = BusinessInvestigationRunStore(runtime_connect)
        schedules = BusinessInvestigationScheduleStore(runtime_connect)
        application = EcommerceBusinessInvestigationApplication(
            case_store=cases, run_store=runs, schedule_store=schedules
        )
        draft = draft_case()
        cases.create_draft(scope, draft, idempotency_key="case-create")
        active = cases.transition(
            scope,
            draft.case_id,
            draft.lifecycle.ACTIVE,
            expected_version=1,
            idempotency_key="case-active",
            actor="owner",
            occurred_at=datetime(2026, 8, 27, tzinfo=UTC),
        ).authority
        request = PutBusinessInvestigationSchedulePolicyRequest.model_validate(
            {
                "schedulePolicyId": "schedule-1",
                "caseRef": {
                    "resourceType": "BusinessInvestigationCaseRevision",
                    "resourceId": active.case_id,
                    "revision": active.revision,
                    "contentHash": active.content_hash,
                },
                "analysisType": "initial_store_analysis",
                "policyKind": "initial_checkup",
                "cadence": "once",
                "enabled": True,
            }
        )
        written = application.put_schedule_policy(
            scope,
            active.case_id,
            request,
            expected_policy_revision=0,
            expected_case_version=2,
            idempotency_key="schedule-create",
            actor="owner",
            occurred_at=datetime(2026, 8, 27, 1, tzinfo=UTC),
        )
        replayed = application.put_schedule_policy(
            scope,
            active.case_id,
            request,
            expected_policy_revision=0,
            expected_case_version=2,
            idempotency_key="schedule-create",
            actor="owner",
            occurred_at=datetime(2026, 8, 27, 2, tzinfo=UTC),
        )
        assert replayed.replayed is True
        assert replayed.authority == written.authority
        assert replayed.case_authority == written.case_authority
        with pytest.raises(Exception, match="idempotency conflict"):
            application.put_schedule_policy(
                scope,
                active.case_id,
                request.model_copy(update={"enabled": False}),
                expected_policy_revision=0,
                expected_case_version=2,
                idempotency_key="schedule-create",
                actor="owner",
                occurred_at=datetime(2026, 8, 27, 2, tzinfo=UTC),
            )
        update_request = request.model_copy(
            update={
                "case_ref": request.case_ref.model_copy(
                    update={
                        "revision": written.case_authority.revision,
                        "content_hash": written.case_authority.content_hash,
                    }
                )
            }
        )
        written = application.put_schedule_policy(
            scope,
            active.case_id,
            update_request,
            expected_policy_revision=1,
            expected_case_version=3,
            idempotency_key="schedule-update",
            actor="owner",
            occurred_at=datetime(2026, 8, 27, 3, tzinfo=UTC),
        )
        assert written.authority.revision == 2
        assert written.case_authority.revision == 4
        update_replay = application.put_schedule_policy(
            scope,
            active.case_id,
            update_request,
            expected_policy_revision=1,
            expected_case_version=3,
            idempotency_key="schedule-update",
            actor="owner",
            occurred_at=datetime(2026, 8, 27, 4, tzinfo=UTC),
        )
        assert update_replay.replayed is True and update_replay.authority == written.authority
        trigger = TriggerBusinessInvestigationScheduleRequest.model_validate(
            {
                "runId": "scheduled-run-1",
                "schedulePolicyRef": {
                    "resourceType": "SchedulePolicyRevision",
                    "resourceId": written.authority.schedule_policy_id,
                    "revision": written.authority.revision,
                    "contentHash": written.authority.content_hash,
                },
                "scheduledAt": "2026-08-28T01:00:00Z",
            }
        )
        created = application.trigger_schedule_policy(
            scope,
            "schedule-1",
            trigger,
            expected_policy_revision=2,
            idempotency_key="trigger-1",
            actor="owner",
            occurred_at=datetime(2026, 8, 28, 1, tzinfo=UTC),
        )
        assert created.outcome == "CREATED"
        trigger_replay = application.trigger_schedule_policy(
            scope,
            "schedule-1",
            trigger,
            expected_policy_revision=2,
            idempotency_key="trigger-1",
            actor="owner",
            occurred_at=datetime(2026, 8, 28, 2, tzinfo=UTC),
        )
        assert trigger_replay.replayed is True
        assert trigger_replay.run.authority.run_id == created.run.authority.run_id
        overlap = application.trigger_schedule_policy(
            scope,
            "schedule-1",
            trigger.model_copy(
                update={
                    "run_id": "scheduled-run-2",
                    "scheduled_at": datetime(2026, 8, 29, 1, tzinfo=UTC),
                }
            ),
            expected_policy_revision=2,
            idempotency_key="trigger-2",
            actor="owner",
            occurred_at=datetime(2026, 8, 29, 1, tzinfo=UTC),
        )
        assert overlap.outcome == "SKIPPED_OVERLAP"
        with psycopg.connect(dsn) as conn:
            assert conn.execute(
                "SELECT count(*) FROM ecommerce_investigation_schedule_policy_revision"
            ).fetchone()[0] == 2
            assert conn.execute(
                "SELECT count(*) FROM ecommerce_investigation_run_trigger_receipt WHERE outcome='SKIPPED_OVERLAP'"
            ).fetchone()[0] == 1
            conn.execute("SET LOCAL ROLE aos_runtime")
            conn.execute("SELECT set_config('aos.org_id','dev-org',true)")
            conn.execute("SELECT set_config('aos.project_id','dev-project',true)")
            assert conn.execute(
                "SELECT count(*) FROM ecommerce_investigation_schedule_policy_head"
            ).fetchone()[0] == 0
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(
                    "INSERT INTO ecommerce_investigation_schedule_policy_head(org_id,project_id,schedule_policy_id,current_revision,case_id,analysis_type,enabled,content_hash,authority_data,updated_at) VALUES('dev-org','dev-project','x',1,'x','initial_store_analysis',false,%s,'{}',NOW())",
                    ("sha256:" + "a" * 64,),
                )
        with pytest.raises(Exception, match="cannot downgrade biw8_001"):
            command.downgrade(config, "biw6_002")
