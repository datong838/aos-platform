"""AR2-7D atomic analysis data-resume Run authority tests."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from importlib import util
from pathlib import Path
from unittest.mock import patch

from alembic import command
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
import pytest

from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.ecommerce_business_investigation_case import (
    BusinessInvestigationCaseLifecycle,
    BusinessInvestigationCaseStore,
)
from aos_api.ecommerce_business_investigation_run import (
    BusinessInvestigationRunConflict,
    BusinessInvestigationRunLifecycle,
    BusinessInvestigationRunNotFound,
    BusinessInvestigationRunStore,
    _canonical_hash,
)
from aos_api.tenant_scope import TenantScope
from tests.aip._migration_test_support import isolated_aip_migration_database
from tests.test_ecommerce_business_investigation_lifecycle import draft_case, requested_run


MIGRATION = Path(__file__).parents[2] / "alembic/versions/ar2_011_ecommerce_analysis_resume.py"
SCOPE = TenantScope("org-org", "dev-project")
OTHER_SCOPE = TenantScope("dev-org", "dev-project")
NOW = datetime(2026, 9, 9, 2, tzinfo=UTC)
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


def _migration():
    spec = util.spec_from_file_location("ar2_011", MIGRATION)
    assert spec and spec.loader
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_is_linear_rls_bounded_and_fail_closed() -> None:
    module = _migration()
    assert module.revision == "ar2_011" and module.down_revision == "ar2_010"
    statements: list[str] = []
    with patch.object(module.op, "execute", statements.append):
        module.upgrade()
        module.downgrade()
    sql = "\n".join(statements)
    assert "resume_after_data" in sql and "RUN_DATA_RESUMED" in sql
    assert "WAITING_DATA" in sql and "PREPARING" in sql
    assert "NO_AIP_TASKRUN" in sql and "NO_ANALYSIS_STEP_COMPLETION" in sql
    assert "cannot downgrade ar2_011 with data-resume authority" in sql
    assert "GRANT EXECUTE" in sql and "GRANT INSERT" not in sql
    assert "search_path=pg_catalog,public,pg_temp" in sql


def test_empty_upgrade_downgrade_round_trip() -> None:
    with isolated_aip_migration_database(
        "ar2_analysis_resume_empty", migration_target="ar2_011"
    ) as (config, _dsn):
        command.downgrade(config, "ar2_010")
        command.upgrade(config, "ar2_011")


def test_resume_after_data_replay_history_isolation_and_illegal_transitions() -> None:
    with isolated_aip_migration_database(
        "ar2_analysis_resume", migration_target="ar2_011"
    ) as (config, dsn):
        with psycopg.connect(dsn) as conn:
            conn.execute(
                "INSERT INTO twa_org(id,name) VALUES('org-org','AR2') ON CONFLICT DO NOTHING"
            )
            conn.execute(
                "INSERT INTO twa_workspace(org_id,project_id,name) VALUES"
                "('org-org','dev-project','AR2'),('dev-org','dev-project','canary') "
                "ON CONFLICT DO NOTHING"
            )
            conn.execute(
                "INSERT INTO data_requirement_head(org_id,project_id,requirement_id,"
                "current_revision,current_content_hash,status,version,created_by) "
                "VALUES('org-org','dev-project','requirement-1',1,%s,'requested',1,'owner')",
                ("a" * 64,),
            )
            conn.execute(
                "INSERT INTO data_requirement_revision(org_id,project_id,requirement_id,revision,"
                "prior_revision,content_hash,status,operation,idempotency_key,request_hash,case_ref,"
                "run_ref,checkpoint_ref,payload,created_by) VALUES"
                "('org-org','dev-project','requirement-1',1,NULL,%s,'requested',"
                "'data_requirement.create','seed-resume',%s,'{}','{}','{}','{}','owner')",
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
        case = draft_case("case-ar2-resume")
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
        run = requested_run(active, "run-ar2-resume")
        runs.request(SCOPE, run, idempotency_key="run-create")

        with pytest.raises(BusinessInvestigationRunConflict, match="authority rejected"):
            runs.resume_after_data(
                SCOPE, run.run_id, requirement_ref(), expected_version=1,
                idempotency_key="resume-too-early", actor="owner", occurred_at=NOW,
            )
        waiting = runs.request_data(
            SCOPE, run.run_id, requirement_ref(), expected_version=1,
            idempotency_key="request-data", actor="owner", occurred_at=NOW,
        ).authority
        direct_payload = waiting.model_dump(by_alias=True, mode="json")
        direct_payload.update(
            {
                "version": 3,
                "lifecycle": "PREPARING",
                "eventSequence": 3,
                "contentHash": HASH_A,
                "pendingRequirementRef": None,
            }
        )
        direct_payload.pop("tenant")
        requirement_payload = requirement_ref().model_dump(by_alias=True, mode="json")
        direct_request_hash = _canonical_hash(
            {
                "runId": run.run_id,
                "expectedVersion": 2,
                "operation": "business_investigation_run.resume_after_data",
                "requirementRef": requirement_payload,
            }
        )
        with runtime_connect(SCOPE) as conn:
            with pytest.raises(psycopg.DatabaseError, match="request invalid"):
                conn.execute(
                    "SELECT * FROM public.ecommerce_investigation_run_data_resume_ar2_011"
                    "(%s,%s,%s,%s,%s,%s)",
                    (
                        run.run_id, 2, "direct-missing-tenant", direct_request_hash,
                        Jsonb(requirement_payload),
                        Jsonb(direct_payload),
                    ),
                )
        for label, invalid_version in (("string", "3"), ("float", 3.0)):
            invalid_version_payload = waiting.model_dump(by_alias=True, mode="json")
            invalid_version_payload.update(
                {
                    "version": invalid_version,
                    "lifecycle": "PREPARING",
                    "eventSequence": 3,
                    "contentHash": HASH_A,
                    "pendingRequirementRef": None,
                }
            )
            with runtime_connect(SCOPE) as conn:
                with pytest.raises(psycopg.DatabaseError, match="request invalid"):
                    conn.execute(
                        "SELECT * FROM public.ecommerce_investigation_run_data_resume_ar2_011"
                        "(%s,%s,%s,%s,%s,%s)",
                        (
                            run.run_id, 2, f"direct-{label}-version", direct_request_hash,
                            Jsonb(requirement_payload), Jsonb(invalid_version_payload),
                        ),
                    )
        bad_hash_payload = waiting.model_dump(by_alias=True, mode="json")
        bad_hash_payload.update(
            {
                "version": 3,
                "lifecycle": "PREPARING",
                "eventSequence": 3,
                "contentHash": HASH_A,
                "pendingRequirementRef": None,
            }
        )
        with runtime_connect(SCOPE) as conn:
            with pytest.raises(psycopg.DatabaseError, match="successor rejected"):
                conn.execute(
                    "SELECT * FROM public.ecommerce_investigation_run_data_resume_ar2_011"
                    "(%s,%s,%s,%s,%s,%s)",
                    (
                        run.run_id, 2, "direct-bad-content-hash", direct_request_hash,
                        Jsonb(requirement_payload), Jsonb(bad_hash_payload),
                    ),
                )
        for suffix, prior_mutation in (
            ("missing-prior-revision", None),
            ("string-prior-revision", "2"),
        ):
            bad_prior_payload = waiting.model_dump(by_alias=True, mode="json")
            bad_prior_payload.update(
                {
                    "version": 3,
                    "lifecycle": "PREPARING",
                    "eventSequence": 3,
                    "pendingRequirementRef": None,
                }
            )
            if prior_mutation is None:
                bad_prior_payload["priorRef"].pop("revision")
            else:
                bad_prior_payload["priorRef"]["revision"] = prior_mutation
            bad_prior_payload["contentHash"] = _canonical_hash(
                {k: v for k, v in bad_prior_payload.items() if k != "contentHash"}
            )
            with runtime_connect(SCOPE) as conn:
                with pytest.raises(psycopg.DatabaseError, match="request invalid"):
                    conn.execute(
                        "SELECT * FROM public.ecommerce_investigation_run_data_resume_ar2_011"
                        "(%s,%s,%s,%s,%s,%s)",
                        (
                            run.run_id, 2, f"direct-{suffix}", direct_request_hash,
                            Jsonb(requirement_payload), Jsonb(bad_prior_payload),
                        ),
                    )
        resumed = runs.resume_after_data(
            SCOPE, run.run_id, requirement_ref(), expected_version=2,
            idempotency_key="resume-data", actor="owner", occurred_at=NOW,
        )
        replay = runs.resume_after_data(
            SCOPE, run.run_id, requirement_ref(), expected_version=2,
            idempotency_key="resume-data", actor="ignored-on-replay", occurred_at=NOW,
        )
        assert waiting.lifecycle is BusinessInvestigationRunLifecycle.WAITING_DATA
        assert resumed.authority.lifecycle is BusinessInvestigationRunLifecycle.PREPARING
        assert resumed.authority.version == 3
        assert resumed.authority.pending_requirement_ref is None
        assert replay.replayed and replay.authority == resumed.authority
        assert runs.read_data_resume_receipt(
            SCOPE, run.run_id, requirement_ref(), expected_version=2,
            idempotency_key="resume-data",
        ) == resumed.authority
        with pytest.raises(BusinessInvestigationRunConflict, match="historical"):
            runs.resume_after_data(
                SCOPE, run.run_id, requirement_ref("requirement-other"), expected_version=2,
                idempotency_key="resume-data", actor="owner", occurred_at=NOW,
            )
        with pytest.raises(BusinessInvestigationRunConflict):
            runs.resume_after_data(
                SCOPE, run.run_id, requirement_ref(), expected_version=2,
                idempotency_key="resume-again", actor="owner", occurred_at=NOW,
            )
        with pytest.raises(BusinessInvestigationRunNotFound):
            runs.get(OTHER_SCOPE, run.run_id)
        assert runs.read_data_resume_receipt(
            OTHER_SCOPE, run.run_id, requirement_ref(), expected_version=2,
            idempotency_key="resume-data",
        ) is None
        with runtime_connect(SCOPE) as conn:
            event = conn.execute(
                "SELECT event_type,event_data FROM ecommerce_investigation_run_event "
                "WHERE run_id=%s AND sequence=3", (run.run_id,),
            ).fetchone()
            assert event["event_type"] == "RUN_DATA_RESUMED"
            assert event["event_data"]["requirementRef"] == requirement_ref().model_dump(
                by_alias=True, mode="json"
            )
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(
                    "UPDATE ecommerce_investigation_run_state_transition_receipt "
                    "SET request_hash=%s WHERE idempotency_key='resume-data'", (HASH_A,),
                )
        with pytest.raises(Exception, match="cannot downgrade ar2_011"):
            command.downgrade(config, "ar2_010")
