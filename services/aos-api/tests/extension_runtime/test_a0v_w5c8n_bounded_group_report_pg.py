"""Bounded, same-snapshot report cannot grant witness writes or ACK."""

from datetime import datetime, timezone
from uuid import UUID

import pytest

pytest_plugins = ("test_analysis_snapshot_resume_chain_pg",)

from aos_api.pipeline_snapshot_group_witness_report import (
    GroupReportCursor, scan_group_report_page,
)
from aos_api.tenant_scope import TenantScope
from test_a0v_w5c8d_original_attempt_receipt_resolver_pg import _factory


@pytest.mark.parametrize("startup_case", ["defer-host"], indirect=True)
@pytest.mark.parametrize("stored", ["qualified-runtime"], indirect=True)
def test_one_saved_group_report_is_bounded_and_read_only(chain_case):
    conn, state, analysis, _session, _root, _requirement = chain_case
    conn.rollback()
    with _factory(conn, read_only=True)(analysis.scope) as reader:
        page = scan_group_report_page(reader, analysis.scope, page_size=1)
        assert page.processed == 1
        assert page.counts == (("READY_CANDIDATE", 1),)
        assert page.next_cursor is None
        with pytest.raises(ValueError, match="page size"):
            scan_group_report_page(reader, analysis.scope, page_size=0)
        with pytest.raises(ValueError, match="page size"):
            scan_group_report_page(reader, analysis.scope, page_size=13)
        wrong = GroupReportCursor(
            org_id=analysis.scope.org_id, project_id=analysis.scope.project_id,
            snapshot="forged", started_at=datetime.now(timezone.utc), backend_pid=0,
            created_at=datetime.now(timezone.utc), group_id=UUID(int=0),
        )
        with pytest.raises(ValueError, match="cursor"):
            scan_group_report_page(reader, analysis.scope, page_size=1, cursor=wrong)
        current = reader.execute("""SELECT pg_current_snapshot()::text AS snapshot,
            transaction_timestamp() AS started_at,pg_backend_pid() AS backend_pid""").fetchone()
        first = reader.execute("""SELECT created_at,group_id FROM pipeline_snapshot_group_claim
            WHERE org_id=%s AND project_id=%s ORDER BY created_at,group_id LIMIT 1""",
            analysis.scope.key).fetchone()
        prior_transaction_cursor = GroupReportCursor(
            analysis.scope.org_id, analysis.scope.project_id,
            current["snapshot"], current["started_at"], current["backend_pid"],
            first["created_at"], first["group_id"],
        )
    with _factory(conn, read_only=True)(analysis.scope) as fresh_reader:
        with pytest.raises(ValueError, match="cursor"):
            scan_group_report_page(fresh_reader, analysis.scope, page_size=1,
                                   cursor=prior_transaction_cursor)
    with _factory(conn, read_only=True)(TenantScope("dev-org", "dev-project")) as reader:
        page = scan_group_report_page(reader, TenantScope("dev-org", "dev-project"), page_size=1)
        assert page.processed == 0 and page.next_cursor is None
    with _factory(conn, read_only=False)(analysis.scope) as writer:
        with pytest.raises(ValueError, match="READ_ONLY"):
            scan_group_report_page(writer, analysis.scope, page_size=1)
    assert state["calls"] == 1
