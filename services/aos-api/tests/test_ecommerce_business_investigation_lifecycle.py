"""BI-W4-06 Case lifecycle and Run control authority tests."""

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

from aos_api.ecommerce_business_investigation_case import (
    BusinessInvestigationCaseConflict,
    BusinessInvestigationCaseLifecycle,
    BusinessInvestigationCaseRevision,
    BusinessInvestigationCaseStore,
)
from aos_api.ecommerce_business_investigation_run import (
    BusinessInvestigationRunConflict,
    BusinessInvestigationRunControl,
    BusinessInvestigationRunRecord,
    BusinessInvestigationRunStore,
    BusinessInvestigationRunStateRevision,
)
from aos_api.tenant_scope import TenantScope
from tests.aip._migration_test_support import isolated_aip_migration_database


MIGRATION = Path(__file__).parents[1] / "alembic/versions/biw4_006_case_run_query_lifecycle_api.py"
SCOPE = TenantScope("org-org", "dev-project")
OTHER_SCOPE = TenantScope("dev-org", "dev-project")
NOW = datetime.now(UTC)
HASH_A = f"sha256:{'a' * 64}"


def ref(kind: str, identity: str, *, revision: int = 1, content_hash: str = HASH_A) -> dict:
    return {
        "resourceType": kind,
        "resourceId": identity,
        "revision": revision,
        "contentHash": content_hash,
    }


def draft_case(case_id: str = "case-1") -> BusinessInvestigationCaseRevision:
    payload = {
        "schemaVersion": "aos.ecommerce.business-investigation-case/v1",
        "tenant": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "caseId": case_id,
        "revision": 1,
        "version": 1,
        "contentHash": HASH_A,
        "lifecycle": "DRAFT",
        "analysisType": "initial_store_analysis",
        "title": "首次全店经营分析",
        "purposeCode": "business.investigation.initial",
        "channelRef": ref("ChannelRevision", "private-mall"),
        "businessEntityRef": ref("BusinessEntityRevision", "store-1"),
        "entityChannelBindingRef": ref("BusinessEntityChannelBindingRevision", "binding-1"),
        "investigationProfileRef": ref("InvestigationProfileRevision", "profile-1"),
        "scopeRef": ref("InvestigationScopeRevision", "scope-1"),
        "createdBy": "owner",
        "createdAt": NOW,
    }
    initial = BusinessInvestigationCaseRevision.model_validate(payload)
    payload["contentHash"] = initial.calculated_content_hash()
    return BusinessInvestigationCaseRevision.model_validate(payload)


def requested_run(active_case: BusinessInvestigationCaseRevision, run_id: str = "run-1") -> BusinessInvestigationRunRecord:
    payload = {
        "schemaVersion": "aos.ecommerce.business-investigation-run/v1",
        "tenant": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "runId": run_id,
        "version": 1,
        "contentHash": HASH_A,
        "caseRef": ref(
            "BusinessInvestigationCaseRevision",
            active_case.case_id,
            revision=active_case.revision,
            content_hash=active_case.content_hash,
        ),
        "analysisType": "initial_store_analysis",
        "triggerKind": "manual",
        "triggerKey": f"manual:{run_id}",
        "lifecycle": "PREPARING",
        "control": "RUNNING",
        "createdBy": "owner",
        "createdAt": NOW,
    }
    initial = BusinessInvestigationRunRecord.model_validate(payload)
    payload["contentHash"] = initial.calculated_content_hash()
    return BusinessInvestigationRunRecord.model_validate(payload)


def _migration():
    spec = util.spec_from_file_location("biw4_006", MIGRATION)
    assert spec and spec.loader
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_state_contract_is_strict_preparing_control_axis_only() -> None:
    initial = BusinessInvestigationRunStateRevision.model_validate(
        {
            "tenant": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
            "runId": "run-1",
            "version": 1,
            "lifecycle": "PREPARING",
            "control": "RUNNING",
            "eventSequence": 1,
            "contentHash": HASH_A,
            "createdBy": "owner",
            "createdAt": NOW,
        }
    )
    assert initial.control is BusinessInvestigationRunControl.RUNNING
    with pytest.raises(ValidationError):
        BusinessInvestigationRunStateRevision.model_validate(
            {**initial.model_dump(by_alias=True, mode="json"), "lifecycle": "WAITING_DATA"}
        )
    with pytest.raises(ValidationError):
        BusinessInvestigationRunStateRevision.model_validate(
            {**initial.model_dump(by_alias=True, mode="json"), "control": "UNKNOWN"}
        )


def test_migration_freezes_rls_receipts_cas_and_no_runtime_direct_write() -> None:
    module = _migration()
    assert module.revision == "biw4_006" and module.down_revision == "biw4_005"
    statements: list[str] = []
    with patch.object(module.op, "execute", statements.append):
        module.upgrade()
    sql = "\n".join(statements)
    assert sql.count("ENABLE ROW LEVEL SECURITY") == 4
    assert sql.count("FORCE ROW LEVEL SECURITY") == 4
    assert "ecommerce_investigation_case_transition_biw4_006" in sql
    assert "ecommerce_investigation_run_control_biw4_006" in sql
    assert "RUN_PAUSED" in sql and "RUN_CANCELLED" in sql
    assert "DELETE FROM ecommerce_investigation_run_active_slot" in sql
    assert "GRANT INSERT" not in sql and "GRANT UPDATE" not in sql
    assert "NO_AIP_TASKRUN_CONTROL" in sql and "NO_EXTERNAL_EFFECT" in sql


def test_disposable_database_empty_upgrade_and_downgrade() -> None:
    with isolated_aip_migration_database("biw4_lifecycle_empty") as (config, _dsn):
        command.downgrade(config, "biw4_005")
        command.upgrade(config, "head")


def test_upgrade_backfills_preexisting_run_before_rls_enforcement() -> None:
    with isolated_aip_migration_database("biw4_lifecycle_backfill") as (config, dsn):
        command.downgrade(config, "biw4_005")
        with psycopg.connect(dsn) as conn:
            conn.execute(
                "INSERT INTO twa_workspace(org_id,project_id,name) VALUES('org-org','dev-project','BI-W4') ON CONFLICT DO NOTHING"
            )
            conn.execute(
                "INSERT INTO ecommerce_investigation_case_head(org_id,project_id,case_id,current_revision,version,lifecycle,analysis_type,channel_id,business_entity_id) VALUES('org-org','dev-project','case-existing',1,1,'ACTIVE','initial_store_analysis','private-mall','store-1')"
            )
            conn.execute(
                "INSERT INTO ecommerce_investigation_case_revision(org_id,project_id,case_id,revision,version,prior_revision,content_hash,lifecycle,analysis_type,channel_id,business_entity_id,entity_channel_binding_id,idempotency_key,request_hash,authority_data,created_by,created_at) VALUES('org-org','dev-project','case-existing',1,1,NULL,%s,'ACTIVE','initial_store_analysis','private-mall','store-1','binding-1','existing-case',%s,'{}','owner',NOW())",
                (HASH_A, HASH_A),
            )
            conn.execute(
                "INSERT INTO ecommerce_investigation_run(org_id,project_id,run_id,version,content_hash,case_id,case_revision,lifecycle,control,analysis_type,trigger_kind,trigger_key,current_event_sequence,authority_data,created_by,created_at) VALUES('org-org','dev-project','run-existing',1,%s,'case-existing',1,'PREPARING','RUNNING','initial_store_analysis','manual','manual:existing',1,'{}','owner',NOW())",
                (HASH_A,),
            )
            conn.commit()
        command.upgrade(config, "head")
        with psycopg.connect(dsn) as conn:
            row = conn.execute(
                "SELECT current_version,lifecycle,control FROM ecommerce_investigation_run_state_head WHERE run_id='run-existing'"
            ).fetchone()
            assert row == (1, "PREPARING", "RUNNING")


def test_case_run_lifecycle_idempotency_rls_restart_and_slot_release() -> None:
    with isolated_aip_migration_database("biw4_lifecycle_authority") as (config, dsn):
        with psycopg.connect(dsn) as conn:
            conn.execute(
                "INSERT INTO twa_workspace(org_id,project_id,name) VALUES('org-org','dev-project','BI-W4') ON CONFLICT DO NOTHING"
            )
            conn.execute(
                "INSERT INTO twa_workspace(org_id,project_id,name) VALUES('dev-org','dev-project','canary') ON CONFLICT DO NOTHING"
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
        draft = draft_case()
        cases.create_draft(SCOPE, draft, idempotency_key="case-create")
        active = cases.transition(
            SCOPE,
            draft.case_id,
            BusinessInvestigationCaseLifecycle.ACTIVE,
            expected_version=1,
            idempotency_key="case-activate",
            actor="owner",
            occurred_at=NOW,
        )
        replay = cases.transition(
            SCOPE,
            draft.case_id,
            BusinessInvestigationCaseLifecycle.ACTIVE,
            expected_version=1,
            idempotency_key="case-activate",
            actor="owner",
            occurred_at=NOW,
        )
        assert active.authority.lifecycle is BusinessInvestigationCaseLifecycle.ACTIVE
        assert replay.replayed and replay.authority == active.authority
        assert cases.list(SCOPE, business_entity_id="store-1") == [active.authority]
        assert cases.list(OTHER_SCOPE) == []
        with pytest.raises(BusinessInvestigationCaseConflict, match="expected version"):
            cases.transition(
                SCOPE,
                draft.case_id,
                BusinessInvestigationCaseLifecycle.ARCHIVED,
                expected_version=1,
                idempotency_key="stale-case",
                actor="owner",
                occurred_at=NOW,
            )

        run = requested_run(active.authority)
        runs.request(SCOPE, run, idempotency_key="run-create")
        view = runs.get(SCOPE, run.run_id)
        assert view.state.version == 1 and view.state.control is BusinessInvestigationRunControl.RUNNING
        assert runs.list_for_case(SCOPE, draft.case_id)[0].authority == run
        assert runs.list_for_case(OTHER_SCOPE, draft.case_id) == []

        paused = runs.transition_control(
            SCOPE,
            run.run_id,
            BusinessInvestigationRunControl.PAUSED,
            expected_version=1,
            idempotency_key="run-pause",
            actor="owner",
            occurred_at=NOW,
        )
        paused_replay = runs.transition_control(
            SCOPE,
            run.run_id,
            BusinessInvestigationRunControl.PAUSED,
            expected_version=1,
            idempotency_key="run-pause",
            actor="owner",
            occurred_at=NOW,
        )
        assert paused.authority.control is BusinessInvestigationRunControl.PAUSED
        assert paused_replay.replayed and paused_replay.authority == paused.authority
        resumed = runs.transition_control(
            SCOPE,
            run.run_id,
            BusinessInvestigationRunControl.RUNNING,
            expected_version=2,
            idempotency_key="run-resume",
            actor="owner",
            occurred_at=NOW,
        )
        cancelled = runs.transition_control(
            SCOPE,
            run.run_id,
            BusinessInvestigationRunControl.CANCELLED,
            expected_version=3,
            idempotency_key="run-cancel",
            actor="owner",
            occurred_at=NOW,
        )
        assert resumed.authority.control is BusinessInvestigationRunControl.RUNNING
        assert cancelled.authority.control is BusinessInvestigationRunControl.CANCELLED
        with pytest.raises(BusinessInvestigationRunConflict, match="expected version"):
            runs.transition_control(
                SCOPE,
                run.run_id,
                BusinessInvestigationRunControl.PAUSED,
                expected_version=3,
                idempotency_key="stale-run",
                actor="owner",
                occurred_at=NOW,
            )

        second = requested_run(active.authority, "run-2")
        assert runs.request(SCOPE, second, idempotency_key="run-create-2").authority == second
        with runtime_connect(SCOPE) as conn:
            assert conn.execute(
                "SELECT count(*) AS n FROM ecommerce_investigation_run_active_slot WHERE run_id='run-1'"
            ).fetchone()["n"] == 0
            assert conn.execute(
                "SELECT count(*) AS n FROM ecommerce_investigation_run_event WHERE run_id='run-1'"
            ).fetchone()["n"] == 4
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute("UPDATE ecommerce_investigation_run_state_head SET control='PAUSED'")

        restarted_runs = BusinessInvestigationRunStore(runtime_connect)
        assert restarted_runs.get(SCOPE, run.run_id).state == cancelled.authority
        with pytest.raises(Exception):
            command.downgrade(config, "biw4_005")
