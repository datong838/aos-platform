"""E17-s3o-f: ordinary tenant runtime must not issue AIP authority receipts."""

from __future__ import annotations

from uuid import uuid4

import psycopg
import pytest

from aos_api.db import connect
from aos_api.tenant_scope import TenantScope


@pytest.mark.xfail(
    strict=True,
    reason="E17-s3o-f RED: current aos_runtime can directly issue Assignee Receipt",
)
def test_runtime_cannot_insert_assignee_resolution_receipt_directly() -> None:
    # conftest owns a fresh disposable DB and drops it after this test session.
    scope = TenantScope("org-org", "dev-project")
    with connect(scope) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                """INSERT INTO aip_assignee_resolution_receipt
                   (org_id, project_id, receipt_id, subject_id, kind, resource_id,
                    version, status, blocker_codes, actor, content_hash)
                   VALUES (%s, %s, %s, 's3of-subject', 'human_principal',
                           's3of-principal', 1, 'blocked', '[]'::jsonb,
                           'untrusted-runtime', %s)""",
                (*scope.key, f"s3of-{uuid4().hex}", "a" * 64),
            )
