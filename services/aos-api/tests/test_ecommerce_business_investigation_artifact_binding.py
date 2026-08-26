"""BI-W4-05 artifact cutoff and atomic selection binding tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from importlib import util
from pathlib import Path
from unittest.mock import patch

from alembic import command
import psycopg
from psycopg.types.json import Jsonb
import pytest
from pydantic import ValidationError

from aos_api.ecommerce_business_investigation_artifact import (
    BusinessInvestigationArtifactBinding,
    BusinessInvestigationArtifactRevision,
)
from tests.aip._migration_test_support import isolated_aip_migration_database


MIGRATION = Path(__file__).parents[1] / "alembic/versions/biw4_005_artifact_cutoff_selection_binding.py"
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


def _dossier() -> BusinessInvestigationArtifactRevision:
    value = {
        "schemaVersion": "aos.ecommerce.business-investigation-artifact-revision/v1",
        "tenant": {"orgId": "org-org", "projectId": "dev-project"},
        "artifactId": "dossier-1",
        "artifactType": "BusinessDossierRevision",
        "revision": 1,
        "version": 1,
        "contentHash": HASH_A,
        "caseRef": _ref("BusinessInvestigationCaseRevision", "case-active", revision=2, content_hash=HASH_B),
        "runRef": _ref("BusinessInvestigationRun", "run-1", content_hash=HASH_C),
        "inputRefs": [
            _ref("DataRequirementRevision", "requirement-1"),
            _ref("SourceReadinessEnvelope", "readiness-1", receipt=True),
        ],
        "createdBy": "business-owner",
        "createdAt": NOW,
    }
    draft = BusinessInvestigationArtifactRevision.model_validate(value)
    value["contentHash"] = draft.calculated_content_hash()
    return BusinessInvestigationArtifactRevision.model_validate(value)


def _binding(artifact: BusinessInvestigationArtifactRevision, **changes) -> BusinessInvestigationArtifactBinding:
    value = {
        "schemaVersion": "aos.ecommerce.business-investigation-artifact-binding/v1",
        "tenant": {"orgId": "org-org", "projectId": "dev-project"},
        "bindingId": "binding-1",
        "bindingHash": HASH_A,
        "artifactRef": _ref(
            "BusinessDossierRevision", artifact.artifact_id, content_hash=artifact.content_hash
        ),
        "selectedChannelRef": _ref("ChannelRevision", "private-mall"),
        "selectedEntityRef": _ref("BusinessEntityRevision", "store-1"),
        "caseRef": _ref("BusinessInvestigationCaseRevision", "case-active", revision=2, content_hash=HASH_B),
        "runRef": _ref("BusinessInvestigationRun", "run-1", content_hash=HASH_C),
        "selectionRevision": 7,
        "dataCutoff": NOW - timedelta(hours=1),
        "lineageRef": _ref("LineageEventRevision", "lineage-1"),
        "boundBy": "business-owner",
        "boundAt": NOW,
    }
    value.update(changes)
    draft = BusinessInvestigationArtifactBinding.model_validate(value)
    value["bindingHash"] = draft.calculated_binding_hash()
    return BusinessInvestigationArtifactBinding.model_validate(value)


def _migration():
    spec = util.spec_from_file_location("biw4_005", MIGRATION)
    assert spec and spec.loader
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_binding_hash_covers_atomic_selection_cutoff_and_exact_lineage() -> None:
    binding = _binding(_dossier())
    assert binding.calculated_binding_hash() == binding.binding_hash
    assert binding.selection_revision == 7
    assert binding.data_cutoff < binding.bound_at
    changed = binding.model_copy(update={"selection_revision": 8})
    assert changed.calculated_binding_hash() != binding.binding_hash


def test_binding_rejects_future_cutoff_noncanonical_lineage_bad_selection_and_extra_time() -> None:
    artifact = _dossier()
    with pytest.raises(ValidationError, match="dataCutoff"):
        _binding(artifact, dataCutoff=NOW + timedelta(seconds=1))
    with pytest.raises(ValidationError, match="lineageRef"):
        _binding(artifact, lineageRef=_ref("TraceId", "not-lineage"))
    with pytest.raises(ValidationError, match="selectedChannelRef"):
        _binding(artifact, selectedChannelRef=_ref("Channel", "private-mall"))
    with pytest.raises(ValidationError, match="Extra inputs"):
        _binding(artifact, generatedAt=NOW)


def test_migration_has_atomic_guard_append_only_rls_and_no_runtime_write() -> None:
    module = _migration()
    assert module.revision == "biw4_005" and module.down_revision == "biw4_004"
    statements: list[str] = []
    with patch.object(module.op, "execute", statements.append):
        module.upgrade()
    sql = "\n".join(statements)
    assert "CREATE TABLE ecommerce_investigation_artifact_binding" in sql
    assert "data_cutoff<=bound_at" in sql
    assert "artifact selection does not match exact Case/Run" in sql
    assert "exact governed artifact revision is required" in sql
    assert "LineageEventRevision" in sql and "LineageRevision" in sql
    assert "FORCE ROW LEVEL SECURITY" in sql
    assert "GRANT INSERT" not in sql and "GRANT UPDATE" not in sql


def test_disposable_database_empty_upgrade_and_downgrade() -> None:
    with isolated_aip_migration_database("biw4_artifact_binding_empty") as (config, _dsn):
        command.downgrade(config, "biw4_004")
        command.upgrade(config, "head")


def _seed_artifact(conn, artifact: BusinessInvestigationArtifactRevision) -> None:
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
            artifact.artifact_id,
            artifact.content_hash,
            HASH_B,
            HASH_C,
            Jsonb([ref.model_dump(by_alias=True, mode="json") for ref in artifact.input_refs]),
        ),
    )


def _insert_binding(conn, binding: BusinessInvestigationArtifactBinding, *, channel_id: str = "private-mall") -> None:
    conn.execute(
        "INSERT INTO ecommerce_investigation_artifact_binding(org_id,project_id,binding_id,binding_hash,artifact_type,artifact_id,artifact_revision,artifact_hash,channel_id,channel_revision,channel_hash,business_entity_id,business_entity_revision,business_entity_hash,case_id,case_revision,case_hash,run_id,run_version,run_hash,selection_revision,data_cutoff,lineage_ref,binding_data,bound_by,bound_at) VALUES('org-org','dev-project',%s,%s,'BusinessDossierRevision','dossier-1',1,%s,%s,1,%s,'store-1',1,%s,'case-active',2,%s,'run-1',1,%s,7,%s,%s,%s,'business-owner',%s)",
        (
            binding.binding_id,
            binding.binding_hash,
            binding.artifact_ref.content_hash,
            channel_id,
            binding.selected_channel_ref.content_hash,
            binding.selected_entity_ref.content_hash,
            HASH_B,
            HASH_C,
            binding.data_cutoff,
            Jsonb(binding.lineage_ref.model_dump(by_alias=True, mode="json")),
            Jsonb(binding.model_dump(by_alias=True, mode="json")),
            binding.bound_at,
        ),
    )


def test_disposable_database_selection_guard_rls_runtime_write_and_nonempty_downgrade() -> None:
    with isolated_aip_migration_database("biw4_artifact_binding") as (config, dsn):
        artifact = _dossier()
        binding = _binding(artifact)
        with psycopg.connect(dsn) as conn:
            _seed_artifact(conn, artifact)
            conn.commit()
        with pytest.raises(psycopg.Error, match="selection"):
            with psycopg.connect(dsn) as conn:
                _insert_binding(conn, binding, channel_id="wrong-channel")
        with psycopg.connect(dsn) as conn:
            _insert_binding(conn, binding)
            conn.commit()

        with psycopg.connect(dsn) as conn:
            conn.execute("SET LOCAL ROLE aos_runtime")
            conn.execute(
                "SELECT set_config('aos.org_id','org-org',true),set_config('aos.project_id','dev-project',true)"
            )
            assert conn.execute("SELECT count(*) FROM ecommerce_investigation_artifact_binding").fetchone()[0] == 1
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute("DELETE FROM ecommerce_investigation_artifact_binding")
        with psycopg.connect(dsn) as conn:
            conn.execute("SET LOCAL ROLE aos_runtime")
            conn.execute(
                "SELECT set_config('aos.org_id','dev-org',true),set_config('aos.project_id','dev-project',true)"
            )
            assert conn.execute("SELECT count(*) FROM ecommerce_investigation_artifact_binding").fetchone()[0] == 0
        with pytest.raises(Exception, match="cannot downgrade biw4_006"):
            command.downgrade(config, "biw4_004")
