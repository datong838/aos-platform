"""Receipt-first review terminal Owner remains off until exact authority exists."""

from contextlib import contextmanager

import pytest

from aos_api.ecommerce_content_review_step_owner import (
    ContentReviewStepConflict, ContentReviewStepOwner,
)
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")


class Cursor:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows


class Connection:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def execute(self, query, params=()):
        self.calls.append((query, params))
        return Cursor(self.rows)


@contextmanager
def connect(connection):
    yield connection


def test_selector_only_names_current_accepted_receipts_without_review_attempt():
    connection = Connection([{"receipt_id": "a366a04f-f954-4e4b-8cb9-6ea8b4b26410"}])
    owner = ContentReviewStepOwner(connect_read=lambda scope: connect(connection))
    assert owner.list_pending(SCOPE, limit=3) == ["a366a04f-f954-4e4b-8cb9-6ea8b4b26410"]
    query, params = connection.calls[0]
    assert "ecommerce_growth_runtime_command_receipt" in query
    assert "ecommerce_growth_feedback_command" in query
    assert "r.status='running'" in query and "t.status='executing'" in query
    assert "NOT EXISTS" in query and "step_key='content_review'" in query
    assert params == (*SCOPE.key, 3)


@pytest.mark.parametrize("limit", [0, 17, True])
def test_selector_rejects_unbounded_limit(limit):
    owner = ContentReviewStepOwner(connect_read=lambda scope: connect(Connection([])))
    with pytest.raises(ValueError, match="bounded"):
        owner.list_pending(SCOPE, limit=limit)


def test_missing_receipt_never_opens_a_review_attempt():
    connection = Connection([])
    owner = ContentReviewStepOwner(connect_write=lambda scope: connect(connection))
    with pytest.raises(ContentReviewStepConflict, match="Receipt"):
        owner.run_one(SCOPE, "a366a04f-f954-4e4b-8cb9-6ea8b4b26410")
    assert len(connection.calls) == 1


def test_ambiguous_receipts_never_open_a_review_attempt():
    connection = Connection([{"response": {}}, {"response": {}}])
    owner = ContentReviewStepOwner(connect_write=lambda scope: connect(connection))
    with pytest.raises(ContentReviewStepConflict, match="unique current"):
        owner.run_one(SCOPE, "a366a04f-f954-4e4b-8cb9-6ea8b4b26410")
    assert len(connection.calls) == 1


def test_selector_refuses_duplicate_receipt_identity():
    identity = "a366a04f-f954-4e4b-8cb9-6ea8b4b26410"
    owner = ContentReviewStepOwner(connect_read=lambda scope: connect(
        Connection([{"receipt_id": identity}, {"receipt_id": identity}])))
    with pytest.raises(ContentReviewStepConflict, match="identity drifted"):
        owner.list_pending(SCOPE)


def test_incomplete_receipt_cannot_be_reconstructed_as_a_review_command():
    connection = Connection([{"response": {}, "metadata": {"ecommerceGrowthContentArtifact": {}}}])
    owner = ContentReviewStepOwner(connect_write=lambda scope: connect(connection))
    with pytest.raises(ContentReviewStepConflict, match="cannot be reconstructed"):
        owner.run_one(SCOPE, "a366a04f-f954-4e4b-8cb9-6ea8b4b26410")
    assert len(connection.calls) == 1
