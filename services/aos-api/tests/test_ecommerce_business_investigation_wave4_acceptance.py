"""BI-W4-09 cumulative Case/Run authority acceptance tests."""

from __future__ import annotations

from contextlib import contextmanager
from importlib import util
from pathlib import Path

from alembic import command
import psycopg
from psycopg.rows import dict_row
import pytest

from aos_api.ecommerce_business_investigation_case import (
    BusinessInvestigationCaseConflict,
    BusinessInvestigationCaseLifecycle,
    BusinessInvestigationCaseRevision,
    BusinessInvestigationCaseStore,
)
from aos_api.ecommerce_business_investigation_projection import (
    BusinessInvestigationProjectionBuilder,
    BusinessInvestigationProjectionNotFound,
    CanonicalBusinessInvestigationProjectionReader,
)
from aos_api.ecommerce_business_investigation_run import BusinessInvestigationRunStore
from aos_api.tenant_scope import TenantScope
from tests.aip._migration_test_support import isolated_aip_migration_database
from test_ecommerce_business_investigation_lifecycle import NOW, draft_case, requested_run


VERSIONS = Path(__file__).parents[1] / "alembic/versions"
SCOPE = TenantScope("org-org", "dev-project")
OTHER_SCOPE = TenantScope("dev-org", "dev-project")
MIGRATIONS = (
    ("biw4_001", "biw3_006", "biw4_001_business_investigation_case.py"),
    ("biw4_002", "biw4_001", "biw4_002_business_investigation_run.py"),
    ("biw4_003", "biw4_002", "biw4_003_run_active_trigger_guard.py"),
    ("biw4_004", "biw4_003", "biw4_004_investigation_artifact_revisions.py"),
    ("biw4_005", "biw4_004", "biw4_005_artifact_cutoff_selection_binding.py"),
    ("biw4_006", "biw4_005", "biw4_006_case_run_query_lifecycle_api.py"),
    ("biw4_007", "biw4_006", "biw4_007_run_waiting_unknown_reconcile_state_machine.py"),
)


def _load_migration(revision: str, filename: str):
    spec = util.spec_from_file_location(revision, VERSIONS / filename)
    assert spec and spec.loader
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _changed_case(draft: BusinessInvestigationCaseRevision) -> BusinessInvestigationCaseRevision:
    payload = draft.model_dump(by_alias=True, mode="json")
    payload["title"] = "同幂等键下不允许替换的经营分析"
    candidate = BusinessInvestigationCaseRevision.model_validate(payload)
    payload["contentHash"] = candidate.calculated_content_hash()
    return BusinessInvestigationCaseRevision.model_validate(payload)


def test_biw4_migrations_are_one_guarded_tenant_authority_chain() -> None:
    combined_sql = []
    for revision, down_revision, filename in MIGRATIONS:
        module = _load_migration(revision, filename)
        source = (VERSIONS / filename).read_text(encoding="utf-8")
        assert module.revision == revision
        assert module.down_revision == down_revision
        assert "org_id" in source and "project_id" in source
        assert "cannot downgrade" in source
        assert "aos_runtime" in source
        combined_sql.append(source)

    sql = "\n".join(combined_sql)
    for table in (
        "ecommerce_investigation_case_revision",
        "ecommerce_investigation_run",
        "ecommerce_investigation_run_active_slot",
        "ecommerce_investigation_artifact_head",
        "ecommerce_investigation_artifact_binding",
        "ecommerce_investigation_run_state_head",
        "ecommerce_investigation_run_state_transition_receipt",
    ):
        assert table in sql
    assert sql.count("ENABLE ROW LEVEL SECURITY") >= 7
    assert sql.count("FORCE ROW LEVEL SECURITY") >= 7
    assert "REVOKE INSERT,UPDATE,DELETE,TRUNCATE" in sql
    assert "SECURITY DEFINER" in sql


def test_disposable_database_closes_receipt_cas_restart_rls_and_rollback_gates() -> None:
    with isolated_aip_migration_database("biw4_cumulative_acceptance") as (config, dsn):
        with psycopg.connect(dsn) as conn:
            conn.execute(
                """INSERT INTO twa_workspace(org_id,project_id,name)
                   VALUES(%s,%s,'BI-W4-09') ON CONFLICT DO NOTHING""",
                SCOPE.key,
            )
            conn.execute(
                """INSERT INTO twa_workspace(org_id,project_id,name)
                   VALUES(%s,%s,'isolation-canary') ON CONFLICT DO NOTHING""",
                OTHER_SCOPE.key,
            )
            conn.commit()

        @contextmanager
        def runtime_connect(scope: TenantScope):
            with psycopg.connect(dsn, row_factory=dict_row) as conn:
                conn.execute("SET LOCAL ROLE aos_runtime")
                conn.execute(
                    "SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",
                    scope.key,
                )
                yield conn

        cases = BusinessInvestigationCaseStore(runtime_connect)
        draft = draft_case("case-w4-acceptance")
        created = cases.create_draft(SCOPE, draft, idempotency_key="case-create")
        assert not created.replayed
        assert BusinessInvestigationCaseStore(runtime_connect).create_draft(
            SCOPE, draft, idempotency_key="case-create"
        ).replayed
        with pytest.raises(BusinessInvestigationCaseConflict):
            cases.create_draft(
                SCOPE,
                _changed_case(draft),
                idempotency_key="case-create",
            )

        active = cases.transition(
            SCOPE,
            draft.case_id,
            BusinessInvestigationCaseLifecycle.ACTIVE,
            expected_version=1,
            idempotency_key="case-activate",
            actor="owner",
            occurred_at=NOW,
        )
        assert cases.transition(
            SCOPE,
            draft.case_id,
            BusinessInvestigationCaseLifecycle.ACTIVE,
            expected_version=1,
            idempotency_key="case-activate",
            actor="owner",
            occurred_at=NOW,
        ).replayed
        with pytest.raises(BusinessInvestigationCaseConflict, match="expected version"):
            cases.transition(
                SCOPE,
                draft.case_id,
                BusinessInvestigationCaseLifecycle.ARCHIVED,
                expected_version=1,
                idempotency_key="case-stale",
                actor="owner",
                occurred_at=NOW,
            )

        run = requested_run(active.authority, "run-w4-acceptance")
        runs = BusinessInvestigationRunStore(runtime_connect)
        assert not runs.request(SCOPE, run, idempotency_key="run-create").replayed
        assert BusinessInvestigationRunStore(runtime_connect).request(
            SCOPE, run, idempotency_key="run-create"
        ).replayed

        first = BusinessInvestigationProjectionBuilder(
            CanonicalBusinessInvestigationProjectionReader(runtime_connect)
        ).build(SCOPE, run.run_id, observed_at=NOW)
        restarted = BusinessInvestigationProjectionBuilder(
            CanonicalBusinessInvestigationProjectionReader(runtime_connect)
        ).build(SCOPE, run.run_id, observed_at=NOW)
        assert restarted.projection_hash == first.projection_hash
        assert restarted.source_watermark == first.source_watermark
        assert BusinessInvestigationCaseStore(runtime_connect).list(OTHER_SCOPE) == []
        assert BusinessInvestigationRunStore(runtime_connect).list_for_case(
            OTHER_SCOPE, draft.case_id
        ) == []
        with pytest.raises(BusinessInvestigationProjectionNotFound):
            CanonicalBusinessInvestigationProjectionReader(runtime_connect).read(
                OTHER_SCOPE, run.run_id
            )

        with runtime_connect(SCOPE) as conn:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(
                    "UPDATE ecommerce_investigation_run SET control='PAUSED' WHERE run_id=%s",
                    (run.run_id,),
                )
            conn.rollback()

        with pytest.raises(Exception, match="cannot downgrade biw4_006"):
            command.downgrade(config, "biw4_005")
        assert BusinessInvestigationRunStore(runtime_connect).get(SCOPE, run.run_id).authority == run
