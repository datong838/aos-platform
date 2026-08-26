"""BI-W4-01 ecommerce BusinessInvestigationCase authority tests."""

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
from pydantic import ValidationError

from aos_api.ecommerce_business_investigation_case import (
    BusinessInvestigationCaseConflict,
    BusinessInvestigationCaseLifecycle,
    BusinessInvestigationCaseRevision,
    BusinessInvestigationCaseStore,
)
from aos_api.tenant_scope import TenantScope
from tests.aip._migration_test_support import isolated_aip_migration_database


MIGRATION = Path(__file__).parents[1] / "alembic/versions/biw4_001_business_investigation_case.py"
SCOPE = TenantScope(org_id="org-org", project_id="dev-project")
NOW = datetime.now(UTC)
HASH_A = f"sha256:{'a' * 64}"
HASH_B = f"sha256:{'b' * 64}"


def ref(kind: str, identity: str, *, revision: int = 1, content_hash: str = HASH_A) -> dict:
    return {
        "resourceType": kind,
        "resourceId": identity,
        "revision": revision,
        "contentHash": content_hash,
    }


def case_payload(**changes) -> dict:
    value = {
        "schemaVersion": "aos.ecommerce.business-investigation-case/v1",
        "tenant": {"orgId": "org-org", "projectId": "dev-project"},
        "caseId": "case-1",
        "revision": 1,
        "version": 1,
        "contentHash": HASH_A,
        "lifecycle": "DRAFT",
        "analysisType": "initial_store_analysis",
        "title": "首次全店经营分析",
        "purposeCode": "business.investigation.initial",
        "channelRef": ref("ChannelRevision", "private-mall"),
        "businessEntityRef": ref("BusinessEntityRevision", "store-1"),
        "entityChannelBindingRef": ref("BusinessEntityChannelBindingRevision", "binding-store-1"),
        "investigationProfileRef": ref("InvestigationProfileRevision", "profile-initial"),
        "scopeRef": ref("InvestigationScopeRevision", "scope-1"),
        "createdBy": "business-owner",
        "createdAt": NOW,
    }
    value.update(changes)
    draft = BusinessInvestigationCaseRevision.model_validate(value)
    value["contentHash"] = draft.calculated_content_hash()
    return value


def successor(previous: BusinessInvestigationCaseRevision, lifecycle: str) -> BusinessInvestigationCaseRevision:
    value = case_payload()
    value.update(
        revision=previous.revision + 1,
        version=previous.version + 1,
        lifecycle=lifecycle,
        priorRef=ref(
            "BusinessInvestigationCaseRevision",
            previous.case_id,
            revision=previous.revision,
            content_hash=previous.content_hash,
        ),
    )
    value["contentHash"] = HASH_A
    item = BusinessInvestigationCaseRevision.model_validate(value)
    value["contentHash"] = item.calculated_content_hash()
    return BusinessInvestigationCaseRevision.model_validate(value)


def _migration():
    spec = util.spec_from_file_location("biw4_001", MIGRATION)
    assert spec and spec.loader
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_case_contract_is_strict_draft_exact_ref_only() -> None:
    draft = BusinessInvestigationCaseRevision.model_validate(case_payload())
    assert draft.lifecycle is BusinessInvestigationCaseLifecycle.DRAFT
    assert draft.calculated_content_hash() == draft.content_hash
    with pytest.raises(ValidationError):
        BusinessInvestigationCaseRevision.model_validate(case_payload(analysisType="cross_channel_comparison"))
    with pytest.raises(ValidationError, match="numeric ChannelRevision"):
        BusinessInvestigationCaseRevision.model_validate(
            case_payload(channelRef=ref("ChannelRevision", "private-mall", revision="latest"))
        )
    with pytest.raises(ValidationError, match="Extra inputs"):
        BusinessInvestigationCaseRevision.model_validate(case_payload(taskRunStatus="RUNNING"))


def test_successor_chain_and_lifecycle_are_fail_closed() -> None:
    draft = BusinessInvestigationCaseRevision.model_validate(case_payload())
    active = successor(draft, "ACTIVE")
    active.validate_successor(draft)
    archived = successor(active, "ARCHIVED")
    archived.validate_successor(active)
    closed = successor(archived, "CLOSED")
    closed.validate_successor(archived)
    with pytest.raises(ValueError, match="transition"):
        successor(draft, "CLOSED").validate_successor(draft)
    with pytest.raises(ValueError, match="transition"):
        successor(closed, "ACTIVE").validate_successor(closed)
    changed_entity = successor(draft, "ACTIVE").model_copy(
        update={"business_entity_ref": BusinessInvestigationCaseRevision.model_validate(case_payload()).business_entity_ref.model_copy(update={"resource_id": "other"})}
    )
    with pytest.raises(ValueError, match="cannot change"):
        changed_entity.validate_successor(draft)


def test_migration_is_draft_only_receipt_first_rls_and_no_direct_write() -> None:
    module = _migration()
    assert module.revision == "biw4_001" and module.down_revision == "biw3_006"
    statements: list[str] = []
    with patch.object(module.op, "execute", statements.append):
        module.upgrade()
    sql = "\n".join(statements)
    assert sql.count("ENABLE ROW LEVEL SECURITY") == 3
    assert sql.count("FORCE ROW LEVEL SECURITY") == 3
    assert "business_investigation_case.create_draft" in sql
    assert "p_payload->>'lifecycle'<>'DRAFT'" in sql
    assert "GRANT EXECUTE ON FUNCTION" in sql
    assert "GRANT INSERT" not in sql and "GRANT UPDATE" not in sql
    assert "taskRunRef" in sql and "rawPayload" in sql
    assert "jsonb_typeof(p_ref->'revision')='number'" in sql
    assert "ecommerce_investigation_exact_ref_valid_biw4_001" in sql


def test_store_uses_single_controlled_create_and_checks_content_hash() -> None:
    draft = BusinessInvestigationCaseRevision.model_validate(case_payload())

    class Cursor:
        def fetchone(self):
            return {"authority_data": draft.model_dump(by_alias=True, mode="json"), "replayed": False}

    class Connection:
        commits = 0
        calls = []
        def execute(self, sql, params):
            self.calls.append((" ".join(sql.split()), params))
            return Cursor()
        def commit(self):
            self.commits += 1

    connection = Connection()

    @contextmanager
    def connect(scope):
        assert scope == SCOPE
        yield connection

    result = BusinessInvestigationCaseStore(connect).create_draft(SCOPE, draft, idempotency_key="create-case-1")
    assert not result.replayed and result.authority == draft
    assert connection.commits == 1
    assert "ecommerce_investigation_case_create_biw4_001" in connection.calls[0][0]
    with pytest.raises(BusinessInvestigationCaseConflict, match="content hash"):
        BusinessInvestigationCaseStore(connect).create_draft(
            SCOPE,
            draft.model_copy(update={"content_hash": HASH_B}),
            idempotency_key="bad-hash",
        )


def test_disposable_database_empty_upgrade_and_downgrade() -> None:
    with isolated_aip_migration_database("biw4_case_empty") as (config, _dsn):
        command.downgrade(config, "biw3_006")
        command.upgrade(config, "head")


def test_disposable_database_idempotency_isolation_restart_and_downgrade_guard() -> None:
    with isolated_aip_migration_database("biw4_case_authority") as (config, dsn):
        with psycopg.connect(dsn) as conn:
            conn.execute(
                "INSERT INTO twa_workspace(org_id,project_id,name) VALUES('org-org','dev-project','BI-W4') ON CONFLICT DO NOTHING"
            )
            conn.commit()

        @contextmanager
        def runtime_connect(scope):
            with psycopg.connect(dsn, row_factory=dict_row) as conn:
                conn.execute("SET LOCAL ROLE aos_runtime")
                conn.execute(
                    "SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",
                    scope.key,
                )
                yield conn

        draft = BusinessInvestigationCaseRevision.model_validate(case_payload())
        first = BusinessInvestigationCaseStore(runtime_connect).create_draft(
            SCOPE, draft, idempotency_key="create-case-1"
        )
        assert not first.replayed
        restarted_store = BusinessInvestigationCaseStore(runtime_connect)
        assert restarted_store.create_draft(SCOPE, draft, idempotency_key="create-case-1").replayed

        changed = BusinessInvestigationCaseRevision.model_validate(case_payload(title="different title"))
        with pytest.raises(BusinessInvestigationCaseConflict):
            restarted_store.create_draft(SCOPE, changed, idempotency_key="create-case-1")

        raw = draft.model_dump(by_alias=True, mode="json")
        raw["rawPayload"] = {"order": "must-not-persist"}
        with psycopg.connect(dsn) as conn:
            conn.execute("SET LOCAL ROLE aos_runtime")
            conn.execute(
                "SELECT set_config('aos.org_id','org-org',true),set_config('aos.project_id','dev-project',true)"
            )
            with pytest.raises(psycopg.Error):
                conn.execute(
                    "SELECT * FROM ecommerce_investigation_case_create_biw4_001(%s,%s,%s,%s)",
                    ("raw-case", "raw-case", HASH_A, Jsonb(raw)),
                )
            conn.rollback()
            invalid_ref = draft.model_dump(by_alias=True, mode="json")
            invalid_ref["caseId"] = "bad-ref-case"
            invalid_ref["channelRef"]["revision"] = "latest"
            conn.execute("SET LOCAL ROLE aos_runtime")
            conn.execute(
                "SELECT set_config('aos.org_id','org-org',true),set_config('aos.project_id','dev-project',true)"
            )
            with pytest.raises(psycopg.Error):
                conn.execute(
                    "SELECT * FROM ecommerce_investigation_case_create_biw4_001(%s,%s,%s,%s)",
                    ("bad-ref-case", "bad-ref-case", HASH_A, Jsonb(invalid_ref)),
                )
            conn.rollback()
            conn.execute("SET LOCAL ROLE aos_runtime")
            conn.execute(
                "SELECT set_config('aos.org_id','dev-org',true),set_config('aos.project_id','dev-project',true)"
            )
            assert conn.execute("SELECT count(*) FROM ecommerce_investigation_case_revision").fetchone()[0] == 0
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(
                    "UPDATE ecommerce_investigation_case_revision SET lifecycle='ACTIVE' WHERE case_id='case-1'"
                )
        with pytest.raises(Exception, match="cannot downgrade biw4_001"):
            command.downgrade(config, "biw3_006")
