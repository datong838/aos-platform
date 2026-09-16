"""A0-V-075 Run cancellation clears WAITING_DATA physical head fields."""
from contextlib import contextmanager
from datetime import UTC, datetime

import psycopg
from psycopg.rows import dict_row

from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.ecommerce_business_investigation_case import (
    BusinessInvestigationCaseLifecycle, BusinessInvestigationCaseStore,
)
from aos_api.ecommerce_business_investigation_run import (
    BusinessInvestigationRunControl, BusinessInvestigationRunStore,
)
from aos_api.tenant_scope import TenantScope
from test_ecommerce_business_investigation_lifecycle import draft_case, requested_run
from tests.aip._migration_test_support import isolated_aip_migration_database


SCOPE = TenantScope("org-org", "dev-project")
NOW = datetime.now(UTC)


def test_waiting_data_cancel_clears_pending_column_and_replays_once():
    with isolated_aip_migration_database(
        "a0v_075_run_cancel", migration_target="a0v_075"
    ) as (_config, dsn):
        with psycopg.connect(dsn) as conn:
            conn.execute(
                "INSERT INTO twa_workspace(org_id,project_id,name) VALUES(%s,%s,'A0V-075') ON CONFLICT DO NOTHING",
                SCOPE.key,
            )
            conn.execute(
                "INSERT INTO data_requirement_head(org_id,project_id,requirement_id,"
                "current_revision,current_content_hash,status,version,created_by) "
                "VALUES(%s,%s,'requirement-a0v-075',1,%s,'requested',1,'owner')",
                (*SCOPE.key, "d" * 64),
            )
            conn.execute(
                "INSERT INTO data_requirement_revision(org_id,project_id,requirement_id,revision,"
                "prior_revision,content_hash,status,operation,idempotency_key,request_hash,case_ref,"
                "run_ref,checkpoint_ref,payload,created_by) VALUES"
                "(%s,%s,'requirement-a0v-075',1,NULL,%s,'requested',"
                "'data_requirement.create','a0v-075-requirement',%s,'{}','{}','{}','{}','owner')",
                (*SCOPE.key, "d" * 64, "d" * 64),
            )
        @contextmanager
        def connect(scope):
            with psycopg.connect(dsn, row_factory=dict_row) as conn:
                conn.execute("SET LOCAL ROLE aos_runtime")
                conn.execute(
                    "SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",
                    scope.key,
                )
                yield conn
        cases = BusinessInvestigationCaseStore(connect)
        runs = BusinessInvestigationRunStore(connect)
        draft = draft_case("case-a0v-075")
        cases.create_draft(SCOPE, draft, idempotency_key="a0v-075-case")
        active = cases.transition(
            SCOPE, draft.case_id, BusinessInvestigationCaseLifecycle.ACTIVE,
            expected_version=1, idempotency_key="a0v-075-activate",
            actor="owner", occurred_at=NOW,
        ).authority
        run = requested_run(active, "run-a0v-075")
        runs.request(SCOPE, run, idempotency_key="a0v-075-run")
        requirement = InvestigationExactRef(
            resource_type="DataRequirementRevision", resource_id="requirement-a0v-075",
            revision=1, content_hash="sha256:" + "d" * 64,
        )
        waiting = runs.request_data(
            SCOPE, run.run_id, requirement, expected_version=1,
            idempotency_key="a0v-075-wait", actor="owner", occurred_at=NOW,
        )
        cancelled = runs.transition_control(
            SCOPE, run.run_id, BusinessInvestigationRunControl.CANCELLED,
            expected_version=waiting.authority.version,
            idempotency_key="a0v-075-cancel", actor="owner", occurred_at=NOW,
        )
        replay = runs.transition_control(
            SCOPE, run.run_id, BusinessInvestigationRunControl.CANCELLED,
            expected_version=waiting.authority.version,
            idempotency_key="a0v-075-cancel", actor="owner", occurred_at=NOW,
        )
        assert cancelled.authority.control is BusinessInvestigationRunControl.CANCELLED
        assert cancelled.authority.pending_requirement_ref is None
        assert replay.replayed and replay.authority == cancelled.authority
        with psycopg.connect(dsn, row_factory=dict_row) as conn:
            head = conn.execute(
                "SELECT pending_requirement_ref,uncertain_command FROM ecommerce_investigation_run_state_head WHERE run_id=%s",
                (run.run_id,),
            ).fetchone()
            assert head == {"pending_requirement_ref": None, "uncertain_command": None}
            assert conn.execute(
                "SELECT count(*) AS n FROM ecommerce_investigation_run_active_slot WHERE run_id=%s",
                (run.run_id,),
            ).fetchone()["n"] == 0
            assert conn.execute(
                "SELECT count(*) AS n FROM ecommerce_investigation_run_event WHERE run_id=%s",
                (run.run_id,),
            ).fetchone()["n"] == 3
