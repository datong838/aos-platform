from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
import json

import psycopg
import pytest

from aos_api.ecommerce_workshop_creator_prepare import (
    CreatorBatchPreparationRevision,
    CreatorPrepareBlocked,
)
from aos_api.ecommerce_workshop_creator_prepare_store import EcommerceWorkshopCreatorPrepareStore
from aos_api.tenant_scope import TenantScope


NOW = datetime(2026, 8, 25, 6, 0, tzinfo=UTC)
SCOPE = TenantScope("org-org", "dev-project")
OTHER = TenantScope("dev-org", "dev-project")
HASH = "a" * 64


class Cursor:
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row


class Connection:
    def __init__(self, rows, fail=False):
        self.rows = rows
        self.fail = fail
        self.commits = 0

    def execute(self, sql, params=None):
        if self.fail:
            raise psycopg.OperationalError("database unavailable")
        if sql.startswith("INSERT INTO"):
            table = sql.split()[2].split("(")[0]
            identity = params[2]
            revision = params[3]
            key = (table, params[0], params[1], identity, revision)
            self.rows.setdefault(key, {"authority_data": json.loads(params[5]), "content_hash": params[4]})
            return Cursor()
        if "WHERE org_id=%s" in sql and "revision=%s" in sql:
            table = sql.split("FROM ", 1)[1].split()[0]
            key = (table, params[0], params[1], params[2], params[3])
            return Cursor(self.rows.get(key))
        if "ORDER BY created_at" in sql:
            candidates = [row for key, row in self.rows.items() if key[0] == "ecommerce_creator_batch_preparation_revision" and key[1:3] == params]
            return Cursor(candidates[-1] if candidates else None)
        return Cursor()

    def commit(self):
        self.commits += 1


class Factory:
    def __init__(self, *, fail=False):
        self.rows = {}
        self.fail = fail

    @contextmanager
    def __call__(self, _scope):
        yield Connection(self.rows, self.fail)


def batch(scope=SCOPE, content_hash=HASH):
    return CreatorBatchPreparationRevision(
        tenant={"orgId": scope.org_id, "projectId": scope.project_id},
        batchId="batch-1", revision=1, version=1, lifecycle="prepared",
        exactRefs={}, skillRefs=[], itemHashes=[],
        ledger={"input": 0, "eligible": 0, "needsReview": 0, "excluded": 0, "unknown": 0, "deduplicated": 0},
        contentHash=content_hash, createdBy="user:maker", createdAt=NOW,
    )


def test_append_is_tenant_scoped_idempotent_and_conflict_closed():
    factory = Factory(); store = EcommerceWorkshopCreatorPrepareStore(factory)
    item = store.append_batch(SCOPE, batch())
    assert item.content_hash == HASH
    assert store.append_batch(SCOPE, batch()).content_hash == HASH
    with pytest.raises(CreatorPrepareBlocked, match="IDEMPOTENCY_CONFLICT"):
        store.append_batch(SCOPE, batch(content_hash="b" * 64))
    with pytest.raises(CreatorPrepareBlocked, match="TENANT_DRIFT"):
        store.append_batch(OTHER, batch())


def test_contribution_read_reports_authority_unavailable_without_fallback():
    store = EcommerceWorkshopCreatorPrepareStore(Factory(fail=True))
    with pytest.raises(CreatorPrepareBlocked, match="AUTHORITY_UNAVAILABLE"):
        store.latest_batch_or_none(SCOPE)
