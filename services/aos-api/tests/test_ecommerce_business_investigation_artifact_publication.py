"""BI-W6-04 controlled Artifact publication tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from contextlib import contextmanager
from importlib import util
from pathlib import Path
from unittest.mock import patch

import pytest
from alembic import command
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from aos_api.aip_business_investigation_eval import BusinessInvestigationStageQualityGate
from aos_api.aip_eval_contracts import EvalStageAttemptRef, EvalSubjectArtifactRef
from aos_api.aip_production_contracts import ExactRevisionRef
from aos_api.ecommerce_business_investigation_artifact import (
    BusinessInvestigationArtifactBinding,
    BusinessInvestigationArtifactRevision,
)
from aos_api.ecommerce_business_investigation_artifact_publication import (
    ArtifactPublicationBlocked,
    ArtifactPublicationStore,
    ArtifactPublicationWrite,
    BusinessInvestigationArtifactPublisher,
)
from aos_api.tenant_scope import TenantScope
from tests.aip._migration_test_support import isolated_aip_migration_database


NOW = datetime(2026, 8, 26, 5, 0, tzinfo=UTC)
HASH_A = f"sha256:{'a' * 64}"
HASH_B = f"sha256:{'b' * 64}"
HASH_C = f"sha256:{'c' * 64}"
MIGRATION = Path(__file__).parents[1] / "alembic/versions/biw6_002_investigation_artifact_publication.py"
SCOPE = TenantScope("org-org", "dev-project")


def _ref(kind: str, identity: str, *, content_hash: str = HASH_A, revision: int = 1) -> dict:
    return {"resourceType": kind, "resourceId": identity, "revision": revision, "contentHash": content_hash}


def artifact() -> BusinessInvestigationArtifactRevision:
    value = {
        "tenant": {"orgId": "org-org", "projectId": "dev-project"},
        "artifactId": "dossier-1",
        "artifactType": "BusinessDossierRevision",
        "revision": 1,
        "version": 1,
        "contentHash": HASH_A,
        "caseRef": _ref("BusinessInvestigationCaseRevision", "case-1", content_hash=HASH_B),
        "runRef": _ref("BusinessInvestigationRun", "run-1", content_hash=HASH_C),
        "inputRefs": [
            _ref("DataRequirementRevision", "requirement-1"),
            {**_ref("SourceReadinessEnvelope", "readiness-1"), "receiptId": "readiness-1"},
        ],
        "createdBy": "analyst",
        "createdAt": NOW,
    }
    draft = BusinessInvestigationArtifactRevision.model_validate(value)
    value["contentHash"] = draft.calculated_content_hash()
    return BusinessInvestigationArtifactRevision.model_validate(value)


def binding(item: BusinessInvestigationArtifactRevision) -> BusinessInvestigationArtifactBinding:
    value = {
        "tenant": item.tenant.model_dump(mode="json", by_alias=True),
        "bindingId": "binding-dossier-1",
        "bindingHash": HASH_A,
        "artifactRef": _ref(item.artifact_type.value, item.artifact_id, content_hash=item.content_hash),
        "selectedChannelRef": _ref("ChannelRevision", "private-mall"),
        "selectedEntityRef": _ref("BusinessEntityRevision", "store-1"),
        "caseRef": item.case_ref.model_dump(mode="json", by_alias=True),
        "runRef": item.run_ref.model_dump(mode="json", by_alias=True),
        "selectionRevision": 3,
        "dataCutoff": NOW - timedelta(hours=1),
        "lineageRef": _ref("LineageEventRevision", "lineage-1"),
        "boundBy": "analyst",
        "boundAt": NOW,
    }
    draft = BusinessInvestigationArtifactBinding.model_validate(value)
    value["bindingHash"] = draft.calculated_binding_hash()
    return BusinessInvestigationArtifactBinding.model_validate(value)


def stage_attempt() -> EvalStageAttemptRef:
    return EvalStageAttemptRef(
        runId="run-1", stepKey="portrait", stepRunId="step-run-1", attempt=1, inputHash="d" * 64
    )


def gate(item: BusinessInvestigationArtifactRevision, *, passed: bool = True) -> BusinessInvestigationStageQualityGate:
    return BusinessInvestigationStageQualityGate(
        stage="portrait",
        evalReportRef=ExactRevisionRef(
            resourceType="EvalReportRevision", resourceId="eval-report-1", revision=1, contentHash="e" * 64
        ),
        subjectArtifactRef=EvalSubjectArtifactRef(
            resourceId=item.artifact_id, contentHash=item.content_hash.removeprefix("sha256:")
        ),
        passed=1 if passed else 0,
        failed=0 if passed else 1,
        total=1,
        passRate=1 if passed else 0,
        gatePassed=passed,
    )


class Authority:
    calls = 0
    last = None

    def publish(self, scope, **kwargs):
        self.calls += 1
        self.last = kwargs
        return ArtifactPublicationWrite(authority=kwargs["receipt"], replayed=self.calls > 1)


def test_publisher_builds_stable_receipt_and_preserves_explicit_command() -> None:
    item = artifact()
    selected = binding(item)
    authority = Authority()
    publisher = BusinessInvestigationArtifactPublisher(authority)
    first = publisher.publish(
        SCOPE,
        actor="analyst",
        expected_head_revision=0,
        artifact=item,
        binding=selected,
        quality_gate=gate(item),
        stage_attempt=stage_attempt(),
        published_at=NOW,
    )
    second = publisher.publish(
        SCOPE,
        actor="analyst",
        expected_head_revision=0,
        artifact=item,
        binding=selected,
        quality_gate=gate(item),
        stage_attempt=stage_attempt(),
        published_at=NOW,
    )
    assert first.authority == second.authority
    assert second.replayed is True
    assert first.authority.artifact_ref.content_hash == item.content_hash
    assert first.authority.data_cutoff == selected.data_cutoff
    assert first.authority.calculated_content_hash().startswith("sha256:")


@pytest.mark.parametrize(
    ("change", "code"),
    [
        ("gate", "EVAL_GATE_NOT_PASSED"),
        ("attempt", "STAGE_ATTEMPT_RUN_DRIFTED"),
        ("version", "ARTIFACT_EXPECTED_VERSION_DRIFTED"),
        ("tenant", "PUBLICATION_TENANT_DRIFTED"),
    ],
)
def test_publisher_fails_closed_before_authority(change: str, code: str) -> None:
    item = artifact()
    selected = binding(item)
    quality = gate(item)
    attempt = stage_attempt()
    expected = 0
    scope = SCOPE
    if change == "gate":
        quality = gate(item, passed=False)
    elif change == "attempt":
        attempt = attempt.model_copy(update={"run_id": "other-run"})
    elif change == "version":
        expected = 1
    else:
        scope = TenantScope("dev-org", "dev-project")
    authority = Authority()
    with pytest.raises(ArtifactPublicationBlocked) as raised:
        BusinessInvestigationArtifactPublisher(authority).publish(
            scope,
            actor="analyst",
            expected_head_revision=expected,
            artifact=item,
            binding=selected,
            quality_gate=quality,
            stage_attempt=attempt,
            published_at=NOW,
        )
    assert raised.value.code == code
    assert authority.calls == 0


def test_migration_is_single_head_cas_receipt_authority_without_runtime_table_writes() -> None:
    spec = util.spec_from_file_location("biw6_002", MIGRATION)
    assert spec and spec.loader
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    statements: list[str] = []
    with patch.object(module.op, "execute", statements.append):
        module.upgrade()
    sql = "\n".join(statements)
    assert module.revision == "biw6_002" and module.down_revision == "biw6_001"
    assert "pg_advisory_xact_lock" in sql and "artifact head expected-version conflict" in sql
    assert "exact passed EvalReport and StageAttempt are required" in sql
    assert "FORCE ROW LEVEL SECURITY" in sql
    assert "GRANT EXECUTE ON FUNCTION ecommerce_investigation_publish_artifact_biw6_002" in sql
    assert "GRANT INSERT ON ecommerce_investigation_artifact_publication_receipt" not in sql
    assert "cannot downgrade biw6_002 with Artifact publication authority" in Path(MIGRATION).read_text()


def test_disposable_database_empty_upgrade_and_downgrade() -> None:
    with isolated_aip_migration_database("biw6_artifact_publication_empty") as (config, _dsn):
        command.downgrade(config, "biw6_001")
        command.upgrade(config, "head")
        command.downgrade(config, "biw6_001")


def _seed_publication_dependencies(conn, item: BusinessInvestigationArtifactRevision) -> None:
    subject = {"resourceType": "Artifact", "resourceId": item.artifact_id, "contentHash": item.content_hash.removeprefix("sha256:")}
    attempt = stage_attempt().model_dump(mode="json", by_alias=True)
    gate_policy = {"resourceType": "MediaGatePolicyRevision", "resourceId": "policy-1", "revision": 1, "contentHash": "f" * 64}
    conn.execute("INSERT INTO twa_workspace(org_id,project_id,name) VALUES('org-org','dev-project','BI-W6') ON CONFLICT DO NOTHING")
    conn.execute("INSERT INTO aip_task(org_id,project_id,task_id,task_type,title,status,idempotency_key,request_hash,created_by) VALUES('org-org','dev-project','task-1','business_investigation','BI','executing','task-key','task-hash','analyst')")
    conn.execute("INSERT INTO aip_plan_revision(org_id,project_id,plan_revision_id,task_id,revision,content_hash,steps,approval_status,idempotency_key,request_hash,created_by) VALUES('org-org','dev-project','plan-1','task-1',1,%s,%s,'approved','plan-key','plan-hash','analyst')", ("1" * 64, Jsonb([{"stepKey": "portrait"}])))
    conn.execute("UPDATE aip_task SET current_plan_revision_id='plan-1' WHERE org_id='org-org' AND project_id='dev-project' AND task_id='task-1'")
    conn.execute("INSERT INTO aip_task_run(org_id,project_id,run_id,task_id,plan_revision_id,status,idempotency_key,request_hash,created_by) VALUES('org-org','dev-project','run-1','task-1','plan-1','running','run-key','run-hash','analyst')")
    conn.execute("INSERT INTO aip_step_run(org_id,project_id,step_run_id,run_id,step_key,attempt,status,input_hash) VALUES('org-org','dev-project','step-run-1','run-1','portrait',1,'running',%s)", ("d" * 64,))
    conn.execute("INSERT INTO aip_eval_run(org_id,project_id,run_id,suite_id,suite_revision,suite_hash,target_ref,dataset_ref,judge_ref,status,idempotency_key,created_by,subject_artifact_ref,stage_attempt_ref,gate_policy_ref,evidence_cutoff_at) VALUES('org-org','dev-project','eval-run-1','suite-1',1,%s,%s,%s,%s,'succeeded','eval-key','analyst',%s,%s,%s,%s)", ("2" * 64, Jsonb({}), Jsonb({}), Jsonb({}), Jsonb(subject), Jsonb(attempt), Jsonb(gate_policy), NOW - timedelta(hours=1)))
    conn.execute("INSERT INTO aip_eval_report_revision(org_id,project_id,report_id,revision,content_hash,run_id,suite_ref,target_ref,dataset_ref,judge_ref,results,passed,failed,total,pass_rate,gate_passed,created_at,subject_artifact_ref,stage_attempt_ref,gate_policy_ref,evidence_cutoff_at) VALUES('org-org','dev-project','eval-report-1',1,%s,'eval-run-1',%s,%s,%s,%s,%s,1,0,1,1,true,%s,%s,%s,%s,%s)", ("e" * 64, Jsonb({}), Jsonb({}), Jsonb({}), Jsonb({}), Jsonb([{"passed": True}]), NOW, Jsonb(subject), Jsonb(attempt), Jsonb(gate_policy), NOW - timedelta(hours=1)))
    conn.execute("INSERT INTO ecommerce_investigation_case_head(org_id,project_id,case_id,current_revision,version,lifecycle,analysis_type,channel_id,business_entity_id) VALUES('org-org','dev-project','case-1',1,1,'ACTIVE','initial_store_analysis','private-mall','store-1')")
    conn.execute("INSERT INTO ecommerce_investigation_case_revision(org_id,project_id,case_id,revision,version,content_hash,lifecycle,analysis_type,channel_id,business_entity_id,entity_channel_binding_id,idempotency_key,request_hash,authority_data,created_by,created_at) VALUES('org-org','dev-project','case-1',1,1,%s,'ACTIVE','initial_store_analysis','private-mall','store-1','entity-binding','case-key',%s,'{}','analyst',%s)", (item.case_ref.content_hash, HASH_A, NOW))
    conn.execute("INSERT INTO ecommerce_investigation_run(org_id,project_id,run_id,version,content_hash,case_id,case_revision,lifecycle,control,analysis_type,trigger_kind,trigger_key,current_event_sequence,authority_data,created_by,created_at) VALUES('org-org','dev-project','run-1',1,%s,'case-1',1,'PREPARING','RUNNING','initial_store_analysis','manual','manual-key',1,'{}','analyst',%s)", (item.run_ref.content_hash, NOW))


def test_disposable_database_publish_replay_rls_and_nonempty_downgrade() -> None:
    with isolated_aip_migration_database("biw6_artifact_publication") as (config, dsn):
        item = artifact()
        selected = binding(item)
        with psycopg.connect(dsn) as conn:
            _seed_publication_dependencies(conn, item)
            conn.commit()
        @contextmanager
        def scoped_connection(scope):
            with psycopg.connect(dsn, row_factory=dict_row) as conn:
                conn.execute("SELECT set_config('aos.org_id',%s,false),set_config('aos.project_id',%s,false)", scope.key)
                yield conn

        store = ArtifactPublicationStore(scoped_connection)
        publisher = BusinessInvestigationArtifactPublisher(store)
        first = publisher.publish(SCOPE, actor="analyst", expected_head_revision=0, artifact=item, binding=selected, quality_gate=gate(item), stage_attempt=stage_attempt(), published_at=NOW)
        replay = publisher.publish(SCOPE, actor="analyst", expected_head_revision=0, artifact=item, binding=selected, quality_gate=gate(item), stage_attempt=stage_attempt(), published_at=NOW)
        assert first.replayed is False and replay.replayed is True
        with psycopg.connect(dsn) as conn:
            conn.execute("SELECT set_config('aos.org_id','org-org',false),set_config('aos.project_id','dev-project',false)")
            with pytest.raises(psycopg.Error, match="tenant scope"):
                conn.execute(
                    "SELECT * FROM ecommerce_investigation_publish_artifact_biw6_002('dev-org','dev-project',0,%s,%s,%s)",
                    (
                        Jsonb(item.model_dump(mode="json", by_alias=True)),
                        Jsonb(selected.model_dump(mode="json", by_alias=True)),
                        Jsonb(first.authority.model_dump(mode="json", by_alias=True)),
                    ),
                )
        with psycopg.connect(dsn) as conn:
            conn.execute("SET LOCAL ROLE aos_runtime")
            conn.execute("SELECT set_config('aos.org_id','org-org',true),set_config('aos.project_id','dev-project',true)")
            assert conn.execute("SELECT count(*) FROM ecommerce_investigation_artifact_publication_receipt").fetchone()[0] == 1
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute("DELETE FROM ecommerce_investigation_artifact_publication_receipt")
        with psycopg.connect(dsn) as conn:
            conn.execute("SET LOCAL ROLE aos_runtime")
            conn.execute("SELECT set_config('aos.org_id','dev-org',true),set_config('aos.project_id','dev-project',true)")
            assert conn.execute("SELECT count(*) FROM ecommerce_investigation_artifact_publication_receipt").fetchone()[0] == 0
        with pytest.raises(Exception, match="cannot downgrade biw6_002"):
            command.downgrade(config, "biw6_001")
