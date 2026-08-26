"""BI-W2-02 tenant-bound DataRequirement Store/CAS tests."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from importlib import util
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import psycopg
import pytest
from alembic import command
from psycopg.rows import dict_row

from tests.aip._migration_test_support import isolated_aip_migration_database

from aos_api.data_requirement_contracts import DataRequirementRevisionRecord
from aos_api.data_requirement_store import (
    DataRequirementConflict,
    DataRequirementIdempotencyConflict,
    DataRequirementInvalidTransition,
    DataRequirementStore,
    DataRequirementValidationError,
    canonical_revision_content_hash,
)
from aos_api.tenant_scope import TenantScope


MIGRATION = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "biw2_002_data_requirement_cas.py"
)
NOW = datetime(2026, 8, 26, 4, 0, tzinfo=UTC)
SCOPE = TenantScope(org_id="org-org", project_id="dev-project")


def ref(resource_type: str, resource_id: str, revision: int = 1) -> dict[str, object]:
    return {
        "resourceType": resource_type,
        "resourceId": resource_id,
        "revision": revision,
        "contentHash": f"sha256:{'b' * 64}",
    }


def requirement(
    *,
    revision: int = 1,
    status: str = "requested",
    org_id: str = "org-org",
    blocker: bool = False,
    budget_minor: int = 1000,
    requirement_id: str = "requirement-1",
) -> DataRequirementRevisionRecord:
    raw: dict[str, object] = {
        "schemaVersion": "aos.data-requirement-authority/v1",
        "tenant": {"orgId": org_id, "projectId": "dev-project"},
        "requirementId": requirement_id,
        "revision": revision,
        "priorRef": None
        if revision == 1
        else ref("DataRequirementRevision", requirement_id, revision - 1),
        "contentHash": f"sha256:{'a' * 64}",
        "status": status,
        "caseRef": ref("BusinessInvestigationCaseRevision", "case-1"),
        "runRef": ref("BusinessInvestigationRun", "run-1"),
        "checkpointRef": ref("CheckpointRevision", "checkpoint-1"),
        "purposeCode": "business_portrait_gap",
        "channelRef": ref("ChannelRevision", "channel-niushop"),
        "entityRef": ref("BusinessEntityRevision", "shop-qyh"),
        "requiredFacts": ["Order", "Product"],
        "timeWindow": {"startAt": NOW - timedelta(days=30), "endAt": NOW},
        "grain": "day",
        "cutoffAt": NOW,
        "freshnessMaxAgeSeconds": 3600,
        "qualityThreshold": 0.95,
        "markings": ["INTERNAL"],
        "piiAllowed": False,
        "minPopulation": 20,
        "acceptableDegradation": ["narrow_time_window"],
        "requestedOutputs": ["DataProductRevision", "EvidenceBundleRevision"],
        "budgetMinor": budget_minor,
        "expiresAt": NOW + timedelta(days=1),
        "createdBy": "user:data-owner",
        "createdAt": NOW,
        "blockers": [
            {
                "code": "DATA_REQUIREMENT_REJECTED",
                "severity": "blocking",
                "dependency": "data-owner-review",
                "requiredAction": "revise requirement scope",
            }
        ]
        if blocker
        else [],
    }
    parsed = DataRequirementRevisionRecord.model_validate(raw)
    return parsed.model_copy(
        update={"content_hash": canonical_revision_content_hash(parsed)}
    )


def _load_migration():
    spec = util.spec_from_file_location("biw2_002_data_requirement_cas", MIGRATION)
    assert spec and spec.loader
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Cursor:
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row


class Connection:
    def __init__(self, row=None):
        self.row = row
        self.calls: list[tuple[str, object]] = []
        self.commits = 0

    def execute(self, sql, params=None):
        self.calls.append((" ".join(sql.split()), params))
        return Cursor(self.row)

    def commit(self):
        self.commits += 1


def factory(connection: Connection):
    @contextmanager
    def connect(scope):
        assert scope == SCOPE
        yield connection

    return connect


def test_migration_defines_single_tenant_cas_entrypoint() -> None:
    module = _load_migration()
    assert module.revision == "biw2_002"
    assert module.down_revision == "biw2_001"
    statements: list[str] = []
    with patch.object(module.op, "execute", statements.append):
        module.upgrade()
    sql = "\n".join(statements)
    assert "CREATE FUNCTION data_requirement_apply_biw2_002" in sql
    assert "SECURITY DEFINER" in sql
    assert "SET search_path = pg_catalog, public" in sql
    assert "pg_advisory_xact_lock" in sql
    assert "current_setting('aos.org_id', true)" in sql
    assert "expected version mismatch" in sql
    assert "requested' AND p_status IN ('accepted','rejected','cancelled')" in sql
    assert "accepted' AND p_status='cancelled'" in sql
    assert "INSERT INTO data_requirement_event" in sql
    assert "INSERT INTO data_requirement_outbox" in sql
    assert "GRANT EXECUTE ON FUNCTION" in sql
    assert "GRANT UPDATE ON data_requirement_head" not in sql


def test_store_request_returns_exact_ref_etag_and_commits_once() -> None:
    item = requirement()
    connection = Connection(
        {
            "requirement_revision": 1,
            "result_content_hash": item.content_hash.removeprefix("sha256:"),
            "head_version": 1,
            "replayed": False,
        }
    )
    result = DataRequirementStore(factory(connection)).request(
        SCOPE,
        actor="user:data-owner",
        idempotency_key="request-1",
        item=item,
        expected_version=0,
    )
    assert result.exact_ref.resource_type == "DataRequirementRevision"
    assert result.exact_ref.content_hash == item.content_hash
    assert result.version == 1
    assert result.etag == item.content_hash
    assert result.replayed is False
    assert connection.commits == 1
    assert "data_requirement_apply_biw2_002" in connection.calls[0][0]


def test_store_fails_closed_before_db_for_scope_actor_hash_and_operation() -> None:
    untouched = Connection()
    store = DataRequirementStore(factory(untouched))
    with pytest.raises(DataRequirementValidationError, match="tenant"):
        store.request(SCOPE, "user:data-owner", "key-1", requirement(org_id="dev-org"), expected_version=0)
    with pytest.raises(DataRequirementValidationError, match="actor"):
        store.request(SCOPE, "user:other", "key-2", requirement(), expected_version=0)
    tampered = requirement().model_copy(update={"content_hash": f"sha256:{'f' * 64}"})
    with pytest.raises(DataRequirementValidationError, match="content hash"):
        store.request(SCOPE, "user:data-owner", "key-3", tampered, expected_version=0)
    with pytest.raises(DataRequirementValidationError, match="requested"):
        store.request(SCOPE, "user:data-owner", "key-4", requirement(revision=2, status="accepted"), expected_version=1)
    assert untouched.calls == []


def test_disposable_database_runtime_cas_idempotency_audit_and_isolation() -> None:
    with isolated_aip_migration_database("biw2_requirement_cas") as (config, dsn):
        @contextmanager
        def runtime_connect(scope: TenantScope):
            with psycopg.connect(dsn, row_factory=dict_row) as conn:
                conn.execute("SET LOCAL ROLE aos_runtime")
                conn.execute(
                    "SELECT set_config('aos.org_id',%s,true), set_config('aos.project_id',%s,true)",
                    scope.key,
                )
                yield conn

        store = DataRequirementStore(runtime_connect)
        created = store.request(SCOPE, "user:data-owner", "request-once", requirement(), expected_version=0)
        replay = store.request(SCOPE, "user:data-owner", "request-once", requirement(), expected_version=0)
        assert created.version == replay.version == 1
        assert replay.replayed is True

        with pytest.raises(DataRequirementIdempotencyConflict):
            changed = requirement(budget_minor=2000)
            store.request(SCOPE, "user:data-owner", "request-once", changed, expected_version=0)
        with pytest.raises(DataRequirementConflict):
            store.accept(
                SCOPE,
                "user:data-owner",
                "accept-stale",
                requirement(revision=3, status="accepted"),
                expected_version=2,
            )

        accepted = store.accept(
            SCOPE,
            "user:data-owner",
            "accept-once",
            requirement(revision=2, status="accepted"),
            expected_version=1,
        )
        assert accepted.version == 2
        cancelled = store.cancel(
            SCOPE,
            "user:data-owner",
            "cancel-once",
            requirement(revision=3, status="cancelled"),
            expected_version=2,
        )
        assert cancelled.version == 3

        store.request(
            SCOPE,
            "user:data-owner",
            "request-rejected",
            requirement(requirement_id="requirement-rejected"),
            expected_version=0,
        )
        rejected = store.reject(
            SCOPE,
            "user:data-owner",
            "reject-once",
            requirement(
                requirement_id="requirement-rejected",
                revision=2,
                status="rejected",
                blocker=True,
            ),
            expected_version=1,
        )
        assert rejected.version == 2
        with pytest.raises(DataRequirementInvalidTransition):
            store.cancel(
                SCOPE,
                "user:data-owner",
                "cancel-rejected",
                requirement(
                    requirement_id="requirement-rejected",
                    revision=3,
                    status="cancelled",
                ),
                expected_version=2,
            )

        with psycopg.connect(dsn, row_factory=dict_row) as conn:
            counts = conn.execute(
                "SELECT (SELECT count(*) FROM data_requirement_revision) revisions, "
                "(SELECT count(*) FROM data_requirement_event) events, "
                "(SELECT count(*) FROM data_requirement_outbox) outbox"
            ).fetchone()
            assert counts == {"revisions": 5, "events": 5, "outbox": 5}
            conn.execute("SET LOCAL ROLE aos_runtime")
            conn.execute("SELECT set_config('aos.org_id','dev-org',true)")
            conn.execute("SELECT set_config('aos.project_id','dev-project',true)")
            assert conn.execute("SELECT count(*) FROM data_requirement_head").fetchone()["count"] == 0
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute("UPDATE data_requirement_head SET version=99")

        command.downgrade(config, "biw2_001")
        command.upgrade(config, "head")


def test_reject_and_illegal_transition_are_fail_closed() -> None:
    suffix = uuid4().hex[:8]
    assert suffix
    rejected = requirement(revision=2, status="rejected", blocker=True)
    assert rejected.blockers[0].code == "DATA_REQUIREMENT_REJECTED"
    with pytest.raises(DataRequirementValidationError, match="rejected"):
        DataRequirementStore(factory(Connection())).reject(
            SCOPE,
            "user:data-owner",
            "reject",
            requirement(revision=2, status="accepted"),
            expected_version=1,
        )
