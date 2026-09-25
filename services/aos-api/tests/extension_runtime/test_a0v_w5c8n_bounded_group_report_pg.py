"""Bounded, same-snapshot report cannot grant witness writes or ACK."""

from datetime import datetime, timezone
import os
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
import pytest

pytest_plugins = ("test_analysis_snapshot_resume_chain_pg",)

from aos_api.pipeline_snapshot_group_witness_report import (
    GroupReportCursor, scan_group_report_page,
)
from aos_api.tenant_scope import TenantScope
from aos_api.ec_ingress_journal import _digest
from test_a0v_w5c8d_original_attempt_receipt_resolver_pg import _factory


def _insert_synthetic_missing_input_group(conn, scope, *, ordinal):
    """Disposable PG-only group: valid immutable claim/member, no input authority."""
    dsn = os.environ['AOS_DATABASE_URL']
    assert psycopg.conninfo.conninfo_to_dict(dsn)['dbname'] == conn.info.dbname
    run_id = f'fixture-report-{ordinal}'
    group_id = uuid4()
    binding = dict(schemaVersion='aos.snapshot-group-claim/v1', orgId=scope.org_id,
                   projectId=scope.project_id, groupId=str(group_id), actor='fixture-host',
                   members=[dict(runId=run_id)])
    with psycopg.connect(dsn, row_factory=dict_row) as admin:
        admin.execute('''INSERT INTO meta_schedule_run
            (id,org_id,project_id,schedule_id,scheduled_for,trigger,status)
            SELECT %s,org_id,project_id,schedule_id,clock_timestamp(),'manual','running'
            FROM meta_schedule_run WHERE org_id=%s AND project_id=%s AND id='fixture-original' ''',
            (run_id, *scope.key))
        admin.execute('''INSERT INTO pipeline_controlled_source_claim
            (org_id,project_id,run_id,installation_id,generation,pipeline_id,control_id,
             control_revision,control_hash,call_ordinal,actor)
            SELECT org_id,project_id,%s,installation_id,generation,pipeline_id,control_id,
                   control_revision,control_hash,%s,actor
            FROM pipeline_controlled_source_claim
            WHERE org_id=%s AND project_id=%s AND run_id='fixture-original' ''',
            (run_id, ordinal, *scope.key))
        admin.execute('''INSERT INTO pipeline_snapshot_group_claim
            (org_id,project_id,group_id,actor,request_hash,member_count,binding)
            VALUES(%s,%s,%s,'fixture-host',%s,1,%s)''',
            (*scope.key, group_id, 'sha256:' + _digest(binding), Jsonb(binding)))
        admin.execute('''INSERT INTO pipeline_snapshot_group_member
            (org_id,project_id,group_id,ordinal,run_id) VALUES(%s,%s,%s,1,%s)''',
            (*scope.key, group_id, run_id))
    return group_id


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


@pytest.mark.parametrize("startup_case", ["defer-host"], indirect=True)
@pytest.mark.parametrize("stored", ["qualified-runtime"], indirect=True)
def test_multigroup_pages_and_concurrent_insert_stay_inside_one_snapshot(chain_case):
    conn, state, analysis, _session, _root, _requirement = chain_case
    conn.rollback()
    original = conn.execute('''SELECT group_id FROM pipeline_snapshot_group_claim
        WHERE org_id=%s AND project_id=%s''', analysis.scope.key).fetchone()['group_id']
    conn.rollback()
    second = _insert_synthetic_missing_input_group(conn, analysis.scope, ordinal=2)
    with _factory(conn, read_only=True)(analysis.scope) as reader:
        first = scan_group_report_page(reader, analysis.scope, page_size=1)
        assert first.processed == 1 and first.counts == (("READY_CANDIDATE", 1),)
        assert first.next_cursor is not None
        third = _insert_synthetic_missing_input_group(conn, analysis.scope, ordinal=3)
        second_page = scan_group_report_page(reader, analysis.scope, page_size=1,
                                             cursor=first.next_cursor)
        assert second_page.processed == 1
        assert second_page.counts == (("MISSING_INPUT", 1),)
        assert second_page.next_cursor is None
        assert reader.execute('''SELECT group_id FROM pipeline_snapshot_group_claim
            WHERE org_id=%s AND project_id=%s ORDER BY created_at,group_id''',
            analysis.scope.key).fetchall()[-1]['group_id'] == second
    with _factory(conn, read_only=True)(analysis.scope) as fresh_reader:
        with pytest.raises(ValueError, match="cursor"):
            scan_group_report_page(fresh_reader, analysis.scope, page_size=1,
                                   cursor=first.next_cursor)
        pages = []
        cursor = None
        while True:
            page = scan_group_report_page(fresh_reader, analysis.scope,
                                          page_size=1, cursor=cursor)
            pages.append(page)
            cursor = page.next_cursor
            if cursor is None:
                break
        assert [page.processed for page in pages] == [1, 1, 1]
        assert tuple(page.counts for page in pages) == (
            (("READY_CANDIDATE", 1),), (("MISSING_INPUT", 1),),
            (("MISSING_INPUT", 1),))
        rows = fresh_reader.execute('''SELECT group_id FROM pipeline_snapshot_group_claim
            WHERE org_id=%s AND project_id=%s ORDER BY created_at,group_id''',
            analysis.scope.key).fetchall()
        assert [row['group_id'] for row in rows] == [original, second, third]
    assert state["calls"] == 1
