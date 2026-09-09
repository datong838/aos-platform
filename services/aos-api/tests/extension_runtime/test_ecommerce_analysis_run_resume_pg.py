"""AR2-7D atomic analysis data-resume Run authority tests."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from importlib import util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4, uuid5

from alembic import command
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
import pytest

from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.aip_task_models import (
    CreatePlanRevisionRequest,
    CreateTaskRequest,
    CreateTaskRunRequest,
    PlanStep,
)
from aos_api.aip_task_store import AipTaskStore
from aos_api.ecommerce_business_investigation_case import (
    BusinessInvestigationCaseLifecycle,
    BusinessInvestigationCaseStore,
)
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import (
    ANALYSIS_RECEIPT_NAMESPACE,
    AnalysisAdvanceHostService,
    TransactionBoundConnectFactory,
    _AnalysisRunAndTaskResumer,
    _HostAnalysisReceiptStore,
    _analysis_command_hash,
)
from aos_api.ecommerce_business_investigation_run import (
    BusinessInvestigationRunConflict,
    BusinessInvestigationRunControl,
    BusinessInvestigationRunLifecycle,
    BusinessInvestigationRunNotFound,
    BusinessInvestigationRunStore,
    BusinessInvestigationUncertainCommand,
    _canonical_hash,
    _strict_legacy_state_authority,
)
from aos_api.aip_business_investigation_reconcile_saga import (
    BusinessInvestigationReconciliationCoordinator,
)
from aos_api.tenant_scope import TenantScope
from tests.aip._migration_test_support import isolated_aip_migration_database
from tests.test_ecommerce_business_investigation_lifecycle import draft_case, requested_run


MIGRATION = Path(__file__).parents[2] / "alembic/versions/ar2_011_ecommerce_analysis_resume.py"
RECONCILE_MIGRATION = (
    Path(__file__).parents[2]
    / "alembic/versions/ar2_012_ecommerce_analysis_reconcile_search_path.py"
)
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


def _reconcile_migration():
    spec = util.spec_from_file_location("ar2_012", RECONCILE_MIGRATION)
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


def test_reconcile_migration_pins_public_before_temporary_schema() -> None:
    module = _reconcile_migration()
    assert module.revision == "ar2_012" and module.down_revision == "ar2_011"
    statements: list[str] = []
    with patch.object(module.op, "execute", statements.append):
        module.upgrade()
        module.downgrade()
    assert statements == [
        "ALTER FUNCTION public.ecommerce_investigation_run_state_transition_biw4_007"
        "(text,bigint,text,text,text,jsonb) SET search_path = pg_catalog, public, pg_temp",
        "ALTER FUNCTION public.ecommerce_investigation_run_state_transition_biw4_007"
        "(text,bigint,text,text,text,jsonb) SET search_path = pg_catalog, public",
    ]


def test_empty_upgrade_downgrade_round_trip() -> None:
    with isolated_aip_migration_database(
        "ar2_analysis_resume_empty", migration_target="ar2_011"
    ) as (config, _dsn):
        command.downgrade(config, "ar2_010")
        command.upgrade(config, "ar2_011")


def test_reconcile_search_path_upgrade_downgrade_round_trip() -> None:
    with isolated_aip_migration_database(
        "ar2_analysis_reconcile_search_path_empty", migration_target="ar2_012"
    ) as (config, _dsn):
        command.downgrade(config, "ar2_011")
        command.upgrade(config, "ar2_012")


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


def test_three_resume_owners_commit_replay_and_rollback_as_one_transaction() -> None:
    with isolated_aip_migration_database(
        "ar2_analysis_three_owner_resume", migration_target="ar2_011"
    ) as (_config, dsn):
        with psycopg.connect(dsn) as conn:
            conn.execute(
                "INSERT INTO twa_org(id,name) VALUES('org-org','AR2') ON CONFLICT DO NOTHING"
            )
            conn.execute(
                "INSERT INTO twa_workspace(org_id,project_id,name) "
                "VALUES('org-org','dev-project','AR2') ON CONFLICT DO NOTHING"
            )
            conn.commit()

        @contextmanager
        def runtime_connect(scope):
            with psycopg.connect(dsn, row_factory=dict_row) as conn:
                conn.execute("SET LOCAL ROLE aos_runtime")
                conn.execute("SELECT set_config('aos.org_id',%s,true)", (scope.org_id,))
                conn.execute("SELECT set_config('aos.project_id',%s,true)", (scope.project_id,))
                yield conn

        def seed_waiting_domain(suffix: str):
            requirement = requirement_ref(f"requirement-{suffix}")
            with psycopg.connect(dsn) as conn:
                conn.execute(
                    "INSERT INTO data_requirement_head(org_id,project_id,requirement_id,"
                    "current_revision,current_content_hash,status,version,created_by) "
                    "VALUES(%s,%s,%s,1,%s,'requested',1,'owner')",
                    (*SCOPE.key, requirement.resource_id, requirement.content_hash[7:]),
                )
                conn.execute(
                    "INSERT INTO data_requirement_revision(org_id,project_id,requirement_id,"
                    "revision,prior_revision,content_hash,status,operation,idempotency_key,"
                    "request_hash,case_ref,run_ref,checkpoint_ref,payload,created_by) "
                    "VALUES(%s,%s,%s,1,NULL,%s,'requested','data_requirement.create',%s,%s,"
                    "'{}','{}','{}','{}','owner')",
                    (
                        *SCOPE.key,
                        requirement.resource_id,
                        requirement.content_hash[7:],
                        f"seed-{suffix}",
                        requirement.content_hash[7:],
                    ),
                )
                conn.commit()
            cases = BusinessInvestigationCaseStore(runtime_connect)
            case = draft_case(f"case-{suffix}")
            cases.create_draft(SCOPE, case, idempotency_key=f"case-create-{suffix}")
            active = cases.transition(
                SCOPE,
                case.case_id,
                BusinessInvestigationCaseLifecycle.ACTIVE,
                expected_version=1,
                idempotency_key=f"case-active-{suffix}",
                actor="owner",
                occurred_at=NOW,
            ).authority
            runs = BusinessInvestigationRunStore(runtime_connect)
            domain = requested_run(active, f"domain-run-{suffix}")
            runs.request(SCOPE, domain, idempotency_key=f"run-create-{suffix}")
            waiting = runs.request_data(
                SCOPE,
                domain.run_id,
                requirement,
                expected_version=1,
                idempotency_key=f"request-data-{suffix}",
                actor="owner",
                occurred_at=NOW,
            ).authority
            return requirement, waiting

        def seed_paused_task(suffix: str):
            tasks = AipTaskStore(runtime_connect)
            task = tasks.create_task(
                SCOPE,
                "owner",
                f"task-{suffix}",
                CreateTaskRequest(title=f"AR2 three owner {suffix}"),
            )
            plan = tasks.create_plan(
                SCOPE,
                "owner",
                task.id,
                f"plan-{suffix}",
                CreatePlanRevisionRequest(
                    expected_task_version=task.version,
                    steps=[PlanStep(step_key="analysis", title="经营分析")],
                ),
            )
            tasks.approve_plan(
                SCOPE,
                "owner",
                task.id,
                plan.revision,
                task.version + 1,
                plan.content_hash,
            )
            task_run = tasks.create_run(
                SCOPE,
                "owner",
                task.id,
                f"task-run-{suffix}",
                CreateTaskRunRequest(
                    plan_revision_id=plan.id,
                    expected_task_version=task.version + 2,
                ),
            )
            started = tasks.start_run(
                SCOPE,
                task_run.id,
                expected_run_version=task_run.version,
                expected_task_version=task.version + 2,
                actor="owner",
                idempotency_key=f"start-{suffix}",
            )
            paused = tasks.pause_run(
                SCOPE,
                task_run.id,
                expected_run_version=started.run.version,
                expected_task_version=started.task.version,
                actor="owner",
                idempotency_key=f"pause-{suffix}",
                reason="WAITING_DATA",
            )
            return paused

        installation_id = uuid4()
        generation = uuid4()
        cutover_group_id = uuid4()
        with psycopg.connect(dsn) as conn:
            conn.execute("SET LOCAL session_replication_role=replica")
            conn.execute(
                "INSERT INTO bundle_installation(org_id,project_id,installation_pk,"
                "installation_id,display_name,current_revision,etag_version,created_by) "
                "VALUES(%s,%s,%s,%s,'AR2 analysis runtime',1,1,'test')",
                (*SCOPE.key, installation_id, installation_id),
            )
            conn.execute(
                "INSERT INTO extension_runtime_binding(org_id,project_id,installation_id,"
                "generation,installation_revision,package_lock_ref,profile_ref,execution_epoch,"
                "desired_state,observed_state,enabled,operation_fence,config_ref) "
                "VALUES(%s,%s,%s,%s,1,'{}','internal-python-v1',3,'enabled','ready',true,false,'{}')",
                (*SCOPE.key, installation_id, generation),
            )
            conn.execute(
                "INSERT INTO extension_operation_dispatch_binding(org_id,project_id,operation_id,"
                "handler_kind,installation_id,generation,execution_epoch,operation_fence,revision,"
                "cutover_group_id,cutover_group_revision,updated_by) "
                "VALUES(%s,%s,'ecommerce_growth_analysis_advance','extension',%s,%s,3,false,5,%s,11,'test')",
                (*SCOPE.key, installation_id, generation, cutover_group_id),
            )
            conn.commit()
        dispatch = SimpleNamespace(
            operation_id="ecommerce_growth_analysis_advance",
            dispatch_revision=5,
            installation_id=installation_id,
            generation=generation,
            execution_epoch=3,
            cutover_group_id=cutover_group_id,
            cutover_group_revision=11,
        )

        def compose(suffix: str, *, commit: bool, invalid_dispatch: bool = False):
            requirement, waiting = seed_waiting_domain(suffix)
            paused = seed_paused_task(suffix)
            receipt_id = f"analysis-receipt-{suffix}"
            receipt_ref = {
                "resourceType": "AnalysisRuntimeReceipt",
                "resourceId": receipt_id,
                "revision": 1,
                "contentHash": HASH_A,
                "receiptId": receipt_id,
            }
            payload = {
                "receiptRef": receipt_ref,
                "requestHash": HASH_A,
                "phase": "RUNNING",
            }
            conn = psycopg.connect(dsn, row_factory=dict_row)
            conn.execute("SET LOCAL ROLE aos_runtime")
            conn.execute("SELECT set_config('aos.org_id',%s,true)", (SCOPE.org_id,))
            conn.execute("SELECT set_config('aos.project_id',%s,true)", (SCOPE.project_id,))
            transaction = HostTransaction(conn)
            factory = TransactionBoundConnectFactory(transaction, SCOPE)
            resumer = _AnalysisRunAndTaskResumer(
                BusinessInvestigationRunStore(factory),
                AipTaskStore(factory),
                requirement,
                waiting.run_id,
                waiting.version,
                NOW,
            )
            result = resumer.resume_run(
                SCOPE,
                paused.run.id,
                expected_run_version=paused.run.version,
                expected_task_version=paused.task.version,
                actor="ecommerce-growth-analysis-host",
                idempotency_key=f"resume-{suffix}",
                reason="DATA_FULFILLED_AND_EVIDENCE_COMPLETE",
            )
            selected_dispatch = (
                SimpleNamespace(**{**dispatch.__dict__, "generation": uuid4()})
                if invalid_dispatch
                else dispatch
            )
            try:
                saved = _HostAnalysisReceiptStore(transaction, SCOPE).put(
                    f"resume-key-{suffix}",
                    payload,
                    dispatch_ref=selected_dispatch,
                    checked_at=NOW,
                )
                if commit:
                    conn.commit()
                return waiting, paused, result, saved
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

        waiting, paused, result, saved = compose("commit", commit=True)
        assert result.run.version == paused.run.version + 1
        assert result.task.version == paused.task.version + 1
        assert saved["phase"] == "RUNNING"

        with psycopg.connect(dsn, row_factory=dict_row) as conn:
            conn.execute("SET LOCAL ROLE aos_runtime")
            conn.execute("SELECT set_config('aos.org_id',%s,true)", (SCOPE.org_id,))
            conn.execute("SELECT set_config('aos.project_id',%s,true)", (SCOPE.project_id,))
            transaction = HostTransaction(conn)
            factory = TransactionBoundConnectFactory(transaction, SCOPE)
            replay_resumer = _AnalysisRunAndTaskResumer(
                BusinessInvestigationRunStore(factory),
                AipTaskStore(factory),
                requirement_ref("requirement-commit"),
                waiting.run_id,
                waiting.version,
                NOW,
            )
            replay = replay_resumer.resume_run(
                SCOPE,
                paused.run.id,
                expected_run_version=paused.run.version,
                expected_task_version=paused.task.version,
                actor="ecommerce-growth-analysis-host",
                idempotency_key="resume-commit",
                reason="DATA_FULFILLED_AND_EVIDENCE_COMPLETE",
            )
            reread = _HostAnalysisReceiptStore(transaction, SCOPE).put(
                "resume-key-commit", saved
            )
            conn.commit()
        assert replay == result and reread == saved

        with psycopg.connect(dsn, row_factory=dict_row) as conn:
            conn.execute("SET LOCAL ROLE aos_runtime")
            conn.execute("SELECT set_config('aos.org_id',%s,true)", (SCOPE.org_id,))
            conn.execute("SELECT set_config('aos.project_id',%s,true)", (SCOPE.project_id,))
            assert conn.execute(
                "SELECT count(*) AS n FROM ecommerce_investigation_run_state_transition_receipt "
                "WHERE run_id=%s "
                "AND operation='business_investigation_run.resume_after_data'",
                (waiting.run_id,),
            ).fetchone()["n"] == 1
            assert conn.execute(
                "SELECT count(*) AS n FROM aip_evidence WHERE run_id=%s "
                "AND evidence_type='run.control' "
                "AND source_ref=%s",
                (paused.run.id, "run-control:resume:resume-commit"),
            ).fetchone()["n"] == 1
            assert conn.execute(
                "SELECT count(*) AS n FROM ecommerce_growth_runtime_command_receipt "
                "WHERE operation_id='ecommerce_growth_analysis_advance' "
                "AND idempotency_key='resume-key-commit'"
            ).fetchone()["n"] == 1
            assert conn.execute(
                "SELECT count(*) AS n FROM aip_checkpoint WHERE run_id=%s",
                (paused.run.id,),
            ).fetchone()["n"] == 0

        with pytest.raises(ValueError, match="binding"):
            compose("rollback", commit=False, invalid_dispatch=True)
        with runtime_connect(SCOPE) as conn:
            assert conn.execute(
                "SELECT lifecycle FROM ecommerce_investigation_run_state_head "
                "WHERE run_id='domain-run-rollback'"
            ).fetchone()["lifecycle"] == "WAITING_DATA"
            assert conn.execute(
                "SELECT status FROM aip_task_run WHERE idempotency_key='task-run-rollback'"
            ).fetchone()["status"] == "paused"
            assert conn.execute(
                "SELECT count(*) AS n FROM ecommerce_growth_runtime_command_receipt "
                "WHERE idempotency_key='resume-key-rollback'"
            ).fetchone()["n"] == 0
            assert conn.execute(
                "SELECT count(*) AS n FROM ecommerce_investigation_run_state_transition_receipt "
                "WHERE run_id='domain-run-rollback' "
                "AND operation='business_investigation_run.resume_after_data'"
            ).fetchone()["n"] == 0
            assert conn.execute(
                "SELECT count(*) AS n FROM aip_evidence WHERE evidence_type='run.control' "
                "AND source_ref='run-control:resume:resume-rollback'"
            ).fetchone()["n"] == 0


def test_reconcile_host_commits_domain_and_unified_receipts_atomically() -> None:
    with isolated_aip_migration_database(
        "ar2_analysis_reconcile_host", migration_target="ar2_012"
    ) as (_config, dsn):
        with psycopg.connect(dsn) as conn:
            conn.execute(
                "INSERT INTO twa_org(id,name) VALUES('org-org','AR2') ON CONFLICT DO NOTHING"
            )
            conn.execute(
                "INSERT INTO twa_workspace(org_id,project_id,name) "
                "VALUES('org-org','dev-project','AR2'),('dev-org','dev-project','canary') "
                "ON CONFLICT DO NOTHING"
            )
            conn.commit()

        @contextmanager
        def runtime_connect(scope):
            with psycopg.connect(dsn, row_factory=dict_row) as conn:
                conn.execute("SET LOCAL ROLE aos_runtime")
                conn.execute("SELECT set_config('aos.org_id',%s,true)", (scope.org_id,))
                conn.execute("SELECT set_config('aos.project_id',%s,true)", (scope.project_id,))
                yield conn

        installation_id = uuid4()
        generation = uuid4()
        cutover_group_id = uuid4()
        with psycopg.connect(dsn) as conn:
            conn.execute("SET LOCAL session_replication_role=replica")
            conn.execute(
                "INSERT INTO bundle_installation(org_id,project_id,installation_pk,"
                "installation_id,display_name,current_revision,etag_version,created_by) "
                "VALUES(%s,%s,%s,%s,'AR2 reconcile runtime',1,1,'test')",
                (*SCOPE.key, installation_id, installation_id),
            )
            conn.execute(
                "INSERT INTO extension_runtime_binding(org_id,project_id,installation_id,"
                "generation,installation_revision,package_lock_ref,profile_ref,execution_epoch,"
                "desired_state,observed_state,enabled,operation_fence,config_ref) "
                "VALUES(%s,%s,%s,%s,1,'{}','internal-python-v1',3,'enabled','ready',true,false,'{}')",
                (*SCOPE.key, installation_id, generation),
            )
            conn.execute(
                "INSERT INTO extension_operation_dispatch_binding(org_id,project_id,operation_id,"
                "handler_kind,installation_id,generation,execution_epoch,operation_fence,revision,"
                "cutover_group_id,cutover_group_revision,updated_by) "
                "VALUES(%s,%s,'ecommerce_growth_analysis_advance','extension',%s,%s,3,false,5,%s,11,'test')",
                (*SCOPE.key, installation_id, generation, cutover_group_id),
            )
            conn.commit()
        dispatch = SimpleNamespace(
            operation_id="ecommerce_growth_analysis_advance",
            dispatch_revision=5,
            installation_id=installation_id,
            generation=generation,
            execution_epoch=3,
            cutover_group_id=cutover_group_id,
            cutover_group_revision=11,
        )

        def seed_unknown(suffix: str, *, target_hash: str = HASH_A):
            cases = BusinessInvestigationCaseStore(runtime_connect)
            case = draft_case(f"case-reconcile-{suffix}")
            cases.create_draft(SCOPE, case, idempotency_key=f"case-create-{suffix}")
            active = cases.transition(
                SCOPE,
                case.case_id,
                BusinessInvestigationCaseLifecycle.ACTIVE,
                expected_version=1,
                idempotency_key=f"case-active-{suffix}",
                actor="owner",
                occurred_at=NOW,
            ).authority
            runs = BusinessInvestigationRunStore(runtime_connect)
            domain = requested_run(active, f"domain-reconcile-{suffix}")
            run = runs.request(SCOPE, domain, idempotency_key=f"run-create-{suffix}").authority
            target_id = f"target-{suffix}"
            uncertain = BusinessInvestigationUncertainCommand(
                command_id=target_id,
                operation="business_investigation.compile",
                request_hash=HASH_A,
            )
            unknown = BusinessInvestigationReconciliationCoordinator(runs).record_timeout(
                SCOPE,
                run.run_id,
                InvestigationExactRef(
                    resource_type="BusinessInvestigationRunStateRevision",
                    resource_id=run.run_id,
                    revision=1,
                    content_hash=runs.get(SCOPE, run.run_id).state.content_hash,
                ),
                uncertain,
                actor="owner",
                occurred_at=NOW,
            )
            target = {
                "resourceType": "RuntimeCommandReceipt",
                "resourceId": target_id,
                "revision": 1,
                "contentHash": target_hash,
                "receiptId": target_id,
            }
            receipt_id = f"analysis-unknown-{suffix}"
            body = {
                "requestHash": HASH_A,
                "occurrenceRef": {
                    "resourceType": "AutomationOccurrence",
                    "resourceId": str(uuid4()),
                    "revision": 1,
                    "contentHash": HASH_A,
                },
                "caseRef": {
                    "resourceType": "BusinessInvestigationCaseRevision",
                    "resourceId": active.case_id,
                    "revision": active.revision,
                    "contentHash": active.content_hash,
                },
                "profileRef": active.investigation_profile_ref.model_dump(
                    by_alias=True, mode="json", exclude_none=True
                ),
                "cutoffAt": NOW.isoformat(),
                "runRef": {
                    "resourceType": "BusinessInvestigationRun",
                    "resourceId": run.run_id,
                    "revision": run.version,
                    "contentHash": run.content_hash,
                },
                "compilationRef": {
                    "resourceType": "BusinessInvestigationCompilationReceipt",
                    "resourceId": f"compilation-{suffix}",
                    "revision": 1,
                    "contentHash": HASH_A,
                },
                "planRef": {
                    "resourceType": "PlanRevision",
                    "resourceId": f"plan-{suffix}",
                    "revision": 1,
                    "contentHash": HASH_A,
                },
                "taskRunRef": {
                    "resourceType": "TaskRun",
                    "resourceId": f"task-run-{suffix}",
                    "revision": 1,
                    "contentHash": HASH_A,
                },
                "phase": "UNKNOWN",
                "recoverableAction": "RECONCILE_RECEIPT",
                "checkpointRef": None,
                "priorCheckpointRef": None,
                "requirementRef": None,
                "fulfillmentRef": None,
                "sourceReadinessRef": None,
                "mappingRef": None,
                "evidenceRefs": [],
                "observedAt": None,
                "targetReceiptRef": target,
                "completed": False,
            }
            prior_ref = {
                "resourceType": "AnalysisRuntimeReceipt",
                "resourceId": receipt_id,
                "revision": 1,
                "contentHash": _analysis_command_hash(body),
                "receiptId": receipt_id,
            }
            prior = {"receiptRef": prior_ref, **body}
            with psycopg.connect(dsn, row_factory=dict_row) as conn:
                conn.execute("SET LOCAL ROLE aos_runtime")
                conn.execute("SELECT set_config('aos.org_id',%s,true)", (SCOPE.org_id,))
                conn.execute("SELECT set_config('aos.project_id',%s,true)", (SCOPE.project_id,))
                _HostAnalysisReceiptStore(HostTransaction(conn), SCOPE).put(
                    f"unknown-{suffix}", prior, dispatch_ref=dispatch, checked_at=NOW
                )
                conn.commit()
            command_body = {
                "operation": "runtime.analysis.reconcile_unknown",
                "occurrenceRef": body["occurrenceRef"],
                "caseRef": body["caseRef"],
                "profileRef": body["profileRef"],
                "cutoffAt": body["cutoffAt"],
                "idempotencyKey": f"reconcile-{suffix}",
                "priorReceiptRef": prior_ref,
                "requirementRef": None,
                "fulfillmentRef": None,
                "checkpointRef": None,
            }
            command_body["requestHash"] = _analysis_command_hash(command_body)
            return runs, unknown, command_body

        runs, unknown, reconcile = seed_unknown("commit")
        with psycopg.connect(dsn, row_factory=dict_row) as conn:
            conn.execute("SET LOCAL ROLE aos_runtime")
            conn.execute("SELECT set_config('aos.org_id',%s,true)", (SCOPE.org_id,))
            conn.execute("SELECT set_config('aos.project_id',%s,true)", (SCOPE.project_id,))
            conn.execute(
                "CREATE TEMP TABLE ecommerce_investigation_run AS "
                "SELECT * FROM public.ecommerce_investigation_run WITH NO DATA"
            )
            conn.execute(
                "CREATE TEMP TABLE ecommerce_investigation_run_state_head AS "
                "SELECT * FROM public.ecommerce_investigation_run_state_head WITH NO DATA"
            )
            conn.execute(
                "CREATE TEMP TABLE ecommerce_investigation_run_state_revision AS "
                "SELECT * FROM public.ecommerce_investigation_run_state_revision WITH NO DATA"
            )
            conn.execute(
                "CREATE TEMP TABLE ecommerce_investigation_run_state_transition_receipt AS "
                "SELECT * FROM public.ecommerce_investigation_run_state_transition_receipt "
                "WITH NO DATA"
            )
            transaction = HostTransaction(conn)
            response = AnalysisAdvanceHostService().execute(
                transaction=transaction,
                scope=SCOPE,
                dispatch_ref=dispatch,
                command=reconcile,
                checked_at=NOW,
                occurred_at=NOW,
            )
            conn.commit()
        assert response["phase"] == "RECONCILING"
        assert response["targetReceiptRef"]["resourceId"] == "target-commit"
        current = runs.get(SCOPE, "domain-reconcile-commit").state
        assert current.control is BusinessInvestigationRunControl.RECONCILING
        predecessor = runs.read_state_exact(SCOPE, current.prior_ref)
        assert predecessor is not None and predecessor.version == unknown.current_state_ref.revision
        key = BusinessInvestigationReconciliationCoordinator._idempotency_key(
            SCOPE, "reconciling", unknown.current_state_ref, predecessor.uncertain_command
        )
        assert runs.read_reconcile_receipt(
            SCOPE, predecessor, idempotency_key=key
        ) == current

        with psycopg.connect(dsn, row_factory=dict_row) as conn:
            conn.execute("SET LOCAL ROLE aos_runtime")
            conn.execute("SELECT set_config('aos.org_id',%s,true)", (SCOPE.org_id,))
            conn.execute("SELECT set_config('aos.project_id',%s,true)", (SCOPE.project_id,))
            transaction = HostTransaction(conn)
            replay = AnalysisAdvanceHostService().execute(
                transaction=transaction,
                scope=SCOPE,
                dispatch_ref=dispatch,
                command=reconcile,
                checked_at=NOW,
                occurred_at=NOW,
            )
            conn.commit()
        assert replay == response
        assert runs.read_state_exact(OTHER_SCOPE, current.prior_ref) is None

        drifted_raw = predecessor.model_dump(by_alias=True, mode="json")
        drifted_raw["createdAt"] = predecessor.created_at.isoformat()
        drifted_raw["priorRef"].pop("receiptId")
        drifted_raw["priorRef"]["resourceId"] = "  domain-reconcile-commit  "
        with pytest.raises(BusinessInvestigationRunConflict, match="authority drifted"):
            _strict_legacy_state_authority(
                drifted_raw, error="historical Run state authority drifted"
            )

        drift_runs, _drift_unknown, drift_command = seed_unknown(
            "target-drift", target_hash=f"sha256:{'b' * 64}"
        )
        with psycopg.connect(dsn, row_factory=dict_row) as conn:
            conn.execute("SET LOCAL ROLE aos_runtime")
            conn.execute("SELECT set_config('aos.org_id',%s,true)", (SCOPE.org_id,))
            conn.execute("SELECT set_config('aos.project_id',%s,true)", (SCOPE.project_id,))
            with pytest.raises(ValueError, match="target authority drifted"):
                AnalysisAdvanceHostService().execute(
                    transaction=HostTransaction(conn),
                    scope=SCOPE,
                    dispatch_ref=dispatch,
                    command=drift_command,
                    checked_at=NOW,
                    occurred_at=NOW,
                )
            conn.rollback()
        assert (
            drift_runs.get(SCOPE, "domain-reconcile-target-drift").state.control
            is BusinessInvestigationRunControl.UNKNOWN
        )

        _rollback_runs, _rollback_unknown, rollback_command = seed_unknown("rollback")
        with psycopg.connect(dsn, row_factory=dict_row) as conn:
            conn.execute("SET LOCAL ROLE aos_runtime")
            conn.execute("SELECT set_config('aos.org_id',%s,true)", (SCOPE.org_id,))
            conn.execute("SELECT set_config('aos.project_id',%s,true)", (SCOPE.project_id,))
            transaction = HostTransaction(conn)
            with pytest.raises(ValueError, match="binding"):
                AnalysisAdvanceHostService().execute(
                    transaction=transaction,
                    scope=SCOPE,
                    dispatch_ref=SimpleNamespace(
                        **{**dispatch.__dict__, "generation": uuid4()}
                    ),
                    command=rollback_command,
                    checked_at=NOW,
                    occurred_at=NOW,
                )
            conn.rollback()
        rollback_state = _rollback_runs.get(SCOPE, "domain-reconcile-rollback").state
        assert rollback_state.control is BusinessInvestigationRunControl.UNKNOWN
        with runtime_connect(SCOPE) as conn:
            assert conn.execute(
                "SELECT count(*) AS n FROM public.ecommerce_growth_runtime_command_receipt "
                "WHERE idempotency_key='reconcile-rollback'"
            ).fetchone()["n"] == 0
            assert conn.execute(
                "SELECT count(*) AS n FROM public.ecommerce_investigation_run_state_transition_receipt "
                "WHERE run_id='domain-reconcile-rollback' "
                "AND operation='business_investigation_run.begin_reconcile'"
            ).fetchone()["n"] == 0
