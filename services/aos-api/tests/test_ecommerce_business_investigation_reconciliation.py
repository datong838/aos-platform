"""BI-W4-07 WAITING_DATA, UNKNOWN and RECONCILING authority tests."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from importlib import util
from pathlib import Path
from unittest.mock import patch

from alembic import command
import psycopg
from psycopg.rows import dict_row
import pytest
from pydantic import ValidationError

from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.ecommerce_business_investigation_case import (
    BusinessInvestigationCaseLifecycle,
    BusinessInvestigationCaseStore,
)
from aos_api.ecommerce_business_investigation_run import (
    BusinessInvestigationRunConflict,
    BusinessInvestigationRunControl,
    BusinessInvestigationRunLifecycle,
    BusinessInvestigationRunNotFound,
    BusinessInvestigationRunStateRevision,
    BusinessInvestigationRunStore,
    BusinessInvestigationUncertainCommand,
)
from aos_api.tenant_scope import TenantScope
from tests.aip._migration_test_support import isolated_aip_migration_database
from tests.test_ecommerce_business_investigation_lifecycle import draft_case, requested_run


MIGRATION = Path(__file__).parents[1] / "alembic/versions/biw4_007_run_waiting_unknown_reconcile_state_machine.py"
SCOPE = TenantScope("org-org", "dev-project")
OTHER_SCOPE = TenantScope("dev-org", "dev-project")
NOW = datetime.now(UTC)
HASH_A = f"sha256:{'a' * 64}"


def requirement_ref(identity: str = "requirement-1") -> InvestigationExactRef:
    return InvestigationExactRef.model_validate(
        {
            "resourceType": "DataRequirementRevision",
            "resourceId": identity,
            "revision": 1,
            "contentHash": HASH_A,
        }
    )


def uncertain() -> BusinessInvestigationUncertainCommand:
    return BusinessInvestigationUncertainCommand(
        command_id="command-1",
        operation="data.requirement.fulfill",
        request_hash=HASH_A,
    )


def _migration():
    spec = util.spec_from_file_location("biw4_007", MIGRATION)
    assert spec and spec.loader
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_state_contract_requires_exact_requirement_and_uncertain_command() -> None:
    base = {
        "tenant": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "runId": "run-1",
        "version": 2,
        "priorRef": {
            "resourceType": "BusinessInvestigationRunStateRevision",
            "resourceId": "run-1",
            "revision": 1,
            "contentHash": HASH_A,
        },
        "eventSequence": 2,
        "contentHash": HASH_A,
        "createdBy": "owner",
        "createdAt": NOW,
    }
    waiting = BusinessInvestigationRunStateRevision.model_validate(
        {
            **base,
            "lifecycle": "WAITING_DATA",
            "control": "RUNNING",
            "pendingRequirementRef": requirement_ref().model_dump(by_alias=True, mode="json"),
        }
    )
    assert waiting.lifecycle is BusinessInvestigationRunLifecycle.WAITING_DATA
    unknown = BusinessInvestigationRunStateRevision.model_validate(
        {
            **base,
            "lifecycle": "PREPARING",
            "control": "UNKNOWN",
            "uncertainCommand": uncertain().model_dump(by_alias=True, mode="json"),
        }
    )
    assert unknown.control is BusinessInvestigationRunControl.UNKNOWN
    with pytest.raises(ValidationError):
        BusinessInvestigationRunStateRevision.model_validate(
            {**base, "lifecycle": "WAITING_DATA", "control": "RUNNING"}
        )
    with pytest.raises(ValidationError):
        BusinessInvestigationRunStateRevision.model_validate(
            {**base, "lifecycle": "PREPARING", "control": "UNKNOWN"}
        )


def test_migration_freezes_receipt_rls_and_no_reconcile_success() -> None:
    module = _migration()
    assert module.revision == "biw4_007" and module.down_revision == "biw4_006"
    statements: list[str] = []
    with patch.object(module.op, "execute", statements.append):
        module.upgrade()
    sql = "\n".join(statements)
    assert "RUN_WAITING_DATA" in sql and "RUN_UNKNOWN" in sql and "RUN_RECONCILING" in sql
    assert "ENABLE ROW LEVEL SECURITY" in sql and "FORCE ROW LEVEL SECURITY" in sql
    assert "GRANT INSERT" not in sql and "GRANT UPDATE" not in sql
    assert "NO_RETRY" in sql and "NO_RECONCILE_SUCCESS" in sql
    assert "RECONCILING','RUNNING" not in sql


def test_disposable_database_empty_upgrade_and_downgrade() -> None:
    with isolated_aip_migration_database("biw4_reconcile_empty") as (config, _dsn):
        command.downgrade(config, "biw4_006")
        command.upgrade(config, "head")
        command.downgrade(config, "biw4_006")
        command.upgrade(config, "head")


def test_waiting_unknown_reconciling_replay_isolation_and_illegal_transitions() -> None:
    with isolated_aip_migration_database("biw4_reconcile_authority") as (config, dsn):
        with psycopg.connect(dsn) as conn:
            conn.execute(
                "INSERT INTO twa_workspace(org_id,project_id,name) VALUES('org-org','dev-project','BI-W4') ON CONFLICT DO NOTHING"
            )
            conn.execute(
                "INSERT INTO twa_workspace(org_id,project_id,name) VALUES('dev-org','dev-project','canary') ON CONFLICT DO NOTHING"
            )
            conn.execute(
                "INSERT INTO data_requirement_head(org_id,project_id,requirement_id,current_revision,current_content_hash,status,version,created_by) VALUES('org-org','dev-project','requirement-1',1,%s,'requested',1,'owner')",
                ("a" * 64,),
            )
            conn.execute(
                "INSERT INTO data_requirement_revision(org_id,project_id,requirement_id,revision,prior_revision,content_hash,status,operation,idempotency_key,request_hash,case_ref,run_ref,checkpoint_ref,payload,created_by) VALUES('org-org','dev-project','requirement-1',1,NULL,%s,'requested','data_requirement.create','seed-requirement',%s,'{}','{}','{}','{}','owner')",
                ("a" * 64, "a" * 64),
            )
            conn.commit()

        @contextmanager
        def runtime_connect(scope):
            with psycopg.connect(dsn, row_factory=dict_row) as conn:
                conn.execute("SET LOCAL ROLE aos_runtime")
                conn.execute("SELECT set_config('aos.org_id',%s,true)", (scope.org_id,))
                conn.execute("SELECT set_config('aos.project_id',%s,true)", (scope.project_id,))
                yield conn

        cases = BusinessInvestigationCaseStore(runtime_connect)
        runs = BusinessInvestigationRunStore(runtime_connect)
        case = draft_case("case-reconcile")
        cases.create_draft(SCOPE, case, idempotency_key="case-create")
        active = cases.transition(
            SCOPE,
            case.case_id,
            BusinessInvestigationCaseLifecycle.ACTIVE,
            expected_version=1,
            idempotency_key="case-active",
            actor="owner",
            occurred_at=NOW,
        ).authority
        run = requested_run(active, "run-reconcile")
        runs.request(SCOPE, run, idempotency_key="run-create")

        with pytest.raises(BusinessInvestigationRunConflict):
            runs.request_data(
                SCOPE,
                run.run_id,
                requirement_ref("requirement-missing"),
                expected_version=1,
                idempotency_key="missing-requirement",
                actor="owner",
                occurred_at=NOW,
            )
        waiting = runs.request_data(
            SCOPE,
            run.run_id,
            requirement_ref(),
            expected_version=1,
            idempotency_key="request-data",
            actor="owner",
            occurred_at=NOW,
        )
        replay = runs.request_data(
            SCOPE,
            run.run_id,
            requirement_ref(),
            expected_version=1,
            idempotency_key="request-data",
            actor="owner",
            occurred_at=NOW,
        )
        assert waiting.authority.lifecycle is BusinessInvestigationRunLifecycle.WAITING_DATA
        assert replay.replayed and replay.authority == waiting.authority
        with pytest.raises(BusinessInvestigationRunConflict, match="idempotency"):
            runs.request_data(
                SCOPE,
                run.run_id,
                requirement_ref("requirement-other"),
                expected_version=1,
                idempotency_key="request-data",
                actor="owner",
                occurred_at=NOW,
            )
        with pytest.raises(BusinessInvestigationRunConflict):
            runs.request_data(
                SCOPE,
                run.run_id,
                requirement_ref("requirement-2"),
                expected_version=2,
                idempotency_key="request-data-twice",
                actor="owner",
                occurred_at=NOW,
            )

        unknown = runs.mark_unknown(
            SCOPE,
            run.run_id,
            uncertain(),
            expected_version=2,
            idempotency_key="mark-unknown",
            actor="owner",
            occurred_at=NOW,
        )
        unknown_replay = runs.mark_unknown(
            SCOPE,
            run.run_id,
            uncertain(),
            expected_version=2,
            idempotency_key="mark-unknown",
            actor="owner",
            occurred_at=NOW,
        )
        assert unknown.authority.control is BusinessInvestigationRunControl.UNKNOWN
        assert unknown_replay.replayed and unknown_replay.authority == unknown.authority
        with pytest.raises(BusinessInvestigationRunConflict):
            runs.transition_control(
                SCOPE,
                run.run_id,
                BusinessInvestigationRunControl.PAUSED,
                expected_version=3,
                idempotency_key="pause-unknown",
                actor="owner",
                occurred_at=NOW,
            )

        reconciling = runs.begin_reconcile(
            SCOPE,
            run.run_id,
            expected_version=3,
            idempotency_key="begin-reconcile",
            actor="owner",
            occurred_at=NOW,
        )
        reconcile_replay = runs.begin_reconcile(
            SCOPE,
            run.run_id,
            expected_version=3,
            idempotency_key="begin-reconcile",
            actor="owner",
            occurred_at=NOW,
        )
        assert reconciling.authority.control is BusinessInvestigationRunControl.RECONCILING
        assert reconcile_replay.replayed and reconcile_replay.authority == reconciling.authority
        with pytest.raises(BusinessInvestigationRunNotFound):
            runs.get(OTHER_SCOPE, run.run_id)
        with runtime_connect(SCOPE) as conn:
            assert conn.execute(
                "SELECT count(*) AS n FROM ecommerce_investigation_run_event WHERE run_id=%s",
                (run.run_id,),
            ).fetchone()["n"] == 4
            assert conn.execute(
                "SELECT count(*) AS n FROM ecommerce_investigation_run_active_slot WHERE run_id=%s",
                (run.run_id,),
            ).fetchone()["n"] == 1
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(
                    "UPDATE ecommerce_investigation_run_state_head SET control='RUNNING' WHERE run_id=%s",
                    (run.run_id,),
                )
        assert BusinessInvestigationRunStore(runtime_connect).get(
            SCOPE, run.run_id
        ).state == reconciling.authority
        with pytest.raises(Exception, match="cannot downgrade biw4_007"):
            command.downgrade(config, "biw4_006")
