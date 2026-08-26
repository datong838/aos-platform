"""BI-W4-04 governed investigation artifact revision tests."""

from __future__ import annotations

from datetime import UTC, datetime
from importlib import util
from pathlib import Path
from unittest.mock import patch

from alembic import command
import psycopg
import pytest
from pydantic import ValidationError

from aos_api.ecommerce_business_investigation_artifact import BusinessInvestigationArtifactRevision
from tests.aip._migration_test_support import isolated_aip_migration_database


MIGRATION = Path(__file__).parents[1] / "alembic/versions/biw4_004_investigation_artifact_revisions.py"
NOW = datetime.now(UTC)
HASH_A = f"sha256:{'a' * 64}"
HASH_B = f"sha256:{'b' * 64}"
HASH_C = f"sha256:{'c' * 64}"


def _ref(kind: str, identity: str, *, revision: int = 1, content_hash: str = HASH_A, receipt: bool = False) -> dict:
    value = {
        "resourceType": kind,
        "resourceId": identity,
        "revision": revision,
        "contentHash": content_hash,
    }
    if receipt:
        value["receiptId"] = f"receipt-{identity}"
    return value


def _inputs(kind: str) -> list[dict]:
    return {
        "BusinessDossierRevision": [
            _ref("DataRequirementRevision", "requirement-1"),
            _ref("SourceReadinessEnvelope", "readiness-1", receipt=True),
        ],
        "ProblemMapRevision": [
            _ref("BusinessDossierRevision", "dossier-1"),
            _ref("EvidenceBundleRevision", "evidence-1"),
        ],
        "OpportunityMapRevision": [
            _ref("BusinessDossierRevision", "dossier-1"),
            _ref("ProblemMapRevision", "problem-1"),
            _ref("EvidenceBundleRevision", "evidence-1"),
        ],
        "SolutionPortfolioRevision": [
            _ref("ProblemMapRevision", "problem-1"),
            _ref("OpportunityMapRevision", "opportunity-1"),
            _ref("DecisionSummaryRevision", "decision-1"),
        ],
    }[kind]


def _artifact(kind: str, **changes) -> BusinessInvestigationArtifactRevision:
    value = {
        "schemaVersion": "aos.ecommerce.business-investigation-artifact-revision/v1",
        "tenant": {"orgId": "org-org", "projectId": "dev-project"},
        "artifactId": f"{kind}-1",
        "artifactType": kind,
        "revision": 1,
        "version": 1,
        "contentHash": HASH_A,
        "caseRef": _ref("BusinessInvestigationCaseRevision", "case-active", revision=2, content_hash=HASH_B),
        "runRef": _ref("BusinessInvestigationRun", "run-1", content_hash=HASH_C),
        "inputRefs": _inputs(kind),
        "createdBy": "business-owner",
        "createdAt": NOW,
    }
    value.update(changes)
    draft = BusinessInvestigationArtifactRevision.model_validate(value)
    value["contentHash"] = draft.calculated_content_hash()
    return BusinessInvestigationArtifactRevision.model_validate(value)


def _migration():
    spec = util.spec_from_file_location("biw4_004", MIGRATION)
    assert spec and spec.loader
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "kind",
    ["BusinessDossierRevision", "ProblemMapRevision", "OpportunityMapRevision", "SolutionPortfolioRevision"],
)
def test_four_artifact_contracts_are_ref_only_and_hash_stable(kind: str) -> None:
    item = _artifact(kind)
    assert item.artifact_type == kind
    assert item.calculated_content_hash() == item.content_hash
    assert not hasattr(item, "payload") and not hasattr(item, "model_response")


def test_artifact_contract_rejects_bad_chain_missing_wrong_duplicate_and_raw_fields() -> None:
    with pytest.raises(ValidationError, match="priorRef"):
        _artifact("ProblemMapRevision", revision=2, version=2)
    with pytest.raises(ValidationError, match="missing required"):
        _artifact("ProblemMapRevision", inputRefs=[_ref("BusinessDossierRevision", "dossier-1")])
    with pytest.raises(ValidationError, match="unsupported"):
        _artifact(
            "SolutionPortfolioRevision",
            inputRefs=_inputs("SolutionPortfolioRevision") + [_ref("GrowthPlanRevision", "forbidden-plan")],
        )
    duplicated = _inputs("BusinessDossierRevision")
    with pytest.raises(ValidationError, match="unique"):
        _artifact("BusinessDossierRevision", inputRefs=duplicated + [duplicated[0]])
    with pytest.raises(ValidationError, match="receiptId"):
        _artifact(
            "BusinessDossierRevision",
            inputRefs=[_ref("DataRequirementRevision", "requirement-1"), _ref("SourceReadinessEnvelope", "readiness-1")],
        )
    with pytest.raises(ValidationError, match="Extra inputs"):
        _artifact("ProblemMapRevision", modelResponse="raw")


def test_successor_requires_exact_same_type_identity_and_preceding_revision() -> None:
    successor = _artifact(
        "ProblemMapRevision",
        revision=2,
        version=2,
        priorRef=_ref("ProblemMapRevision", "ProblemMapRevision-1", content_hash=HASH_B),
    )
    assert successor.prior_ref and successor.prior_ref.revision == 1
    with pytest.raises(ValidationError, match="preceding"):
        _artifact(
            "ProblemMapRevision",
            revision=2,
            version=2,
            priorRef=_ref("BusinessDossierRevision", "ProblemMapRevision-1"),
        )


def test_migration_has_four_append_only_exact_ref_tables_and_no_runtime_write() -> None:
    module = _migration()
    assert module.revision == "biw4_004" and module.down_revision == "biw4_003"
    statements: list[str] = []
    with patch.object(module.op, "execute", statements.append):
        module.upgrade()
    sql = "\n".join(statements)
    for table in module.ARTIFACT_TABLES.values():
        assert f"CREATE TABLE {table}" in sql
        assert f"trg_{table}_immutable" in sql
    assert "ecommerce_investigation_artifact_head" in sql
    assert "uq_ecommerce_investigation_case_exact_biw4_004" in sql
    assert "uq_ecommerce_investigation_run_exact_case_biw4_004" in sql
    assert sql.count("FORCE ROW LEVEL SECURITY") == 5
    assert "GRANT INSERT" not in sql and "GRANT UPDATE" not in sql
    assert "GrowthPlanCandidate" not in sql


def test_disposable_database_empty_upgrade_and_downgrade() -> None:
    with isolated_aip_migration_database("biw4_artifact_empty") as (config, _dsn):
        command.downgrade(config, "biw4_003")
        command.upgrade(config, "head")


def test_disposable_database_exact_case_run_rls_runtime_guard_and_nonempty_downgrade() -> None:
    with isolated_aip_migration_database("biw4_artifact_authority") as (config, dsn):
        dossier = _artifact("BusinessDossierRevision")
        with psycopg.connect(dsn) as conn:
            conn.execute(
                "INSERT INTO twa_workspace(org_id,project_id,name) VALUES('org-org','dev-project','BI-W4') ON CONFLICT DO NOTHING"
            )
            conn.execute(
                "INSERT INTO ecommerce_investigation_case_head(org_id,project_id,case_id,current_revision,version,lifecycle,analysis_type,channel_id,business_entity_id) VALUES('org-org','dev-project','case-active',2,2,'ACTIVE','initial_store_analysis','private-mall','store-1')"
            )
            conn.execute(
                "INSERT INTO ecommerce_investigation_case_revision(org_id,project_id,case_id,revision,version,prior_revision,content_hash,lifecycle,analysis_type,channel_id,business_entity_id,entity_channel_binding_id,idempotency_key,request_hash,authority_data,created_by,created_at) VALUES('org-org','dev-project','case-active',2,2,1,%s,'ACTIVE','initial_store_analysis','private-mall','store-1','binding-store-1','seed-active',%s,'{}','business-owner',NOW())",
                (HASH_B, HASH_A),
            )
            conn.execute(
                "INSERT INTO ecommerce_investigation_run(org_id,project_id,run_id,version,content_hash,case_id,case_revision,lifecycle,control,analysis_type,trigger_kind,trigger_key,current_event_sequence,authority_data,created_by,created_at) VALUES('org-org','dev-project','run-1',1,%s,'case-active',2,'PREPARING','RUNNING','initial_store_analysis','manual','manual-seed',1,'{}','business-owner',NOW())",
                (HASH_C,),
            )
            conn.execute(
                "INSERT INTO ecommerce_investigation_business_dossier_revision(org_id,project_id,artifact_id,revision,version,prior_revision,prior_content_hash,content_hash,case_id,case_revision,case_content_hash,run_id,run_version,run_content_hash,input_refs,created_by,created_at) VALUES('org-org','dev-project',%s,1,1,NULL,NULL,%s,'case-active',2,%s,'run-1',1,%s,%s,'business-owner',NOW())",
                (
                    dossier.artifact_id,
                    dossier.content_hash,
                    HASH_B,
                    HASH_C,
                    psycopg.types.json.Jsonb([ref.model_dump(by_alias=True, mode="json") for ref in dossier.input_refs]),
                ),
            )
            conn.execute(
                "INSERT INTO ecommerce_investigation_artifact_head(org_id,project_id,artifact_type,artifact_id,current_revision,current_content_hash,version,case_id,case_revision,run_id) VALUES('org-org','dev-project','BusinessDossierRevision',%s,1,%s,1,'case-active',2,'run-1')",
                (dossier.artifact_id, dossier.content_hash),
            )
            conn.commit()

        with psycopg.connect(dsn) as conn:
            conn.execute("SET LOCAL ROLE aos_runtime")
            conn.execute(
                "SELECT set_config('aos.org_id','org-org',true),set_config('aos.project_id','dev-project',true)"
            )
            assert conn.execute("SELECT count(*) FROM ecommerce_investigation_business_dossier_revision").fetchone()[0] == 1
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(
                    "INSERT INTO ecommerce_investigation_artifact_head(org_id,project_id,artifact_type,artifact_id,current_revision,current_content_hash,version,case_id,case_revision,run_id) VALUES('org-org','dev-project','BusinessDossierRevision','direct',1,%s,1,'case-active',2,'run-1')",
                    (HASH_A,),
                )
        with psycopg.connect(dsn) as conn:
            conn.execute("SET LOCAL ROLE aos_runtime")
            conn.execute(
                "SELECT set_config('aos.org_id','dev-org',true),set_config('aos.project_id','dev-project',true)"
            )
            assert conn.execute("SELECT count(*) FROM ecommerce_investigation_business_dossier_revision").fetchone()[0] == 0
        with pytest.raises(Exception, match="cannot downgrade biw4_006"):
            command.downgrade(config, "biw4_003")
