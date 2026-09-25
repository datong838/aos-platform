"""Bounded same-snapshot keyset report over original historical group claims."""

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from aos_api.pipeline_snapshot_group_witness_classifier import (
    classify_group, require_read_only_snapshot,
)
from aos_api.tenant_scope import TenantScope


@dataclass(frozen=True)
class GroupReportCursor:
    org_id: str
    project_id: str
    snapshot: str
    started_at: datetime
    backend_pid: int
    created_at: datetime
    group_id: UUID


@dataclass(frozen=True)
class GroupReportPage:
    processed: int
    counts: tuple[tuple[str, int], ...]
    next_cursor: GroupReportCursor | None


def scan_group_report_page(conn, scope: TenantScope, *, page_size: int,
                           cursor: GroupReportCursor | None = None) -> GroupReportPage:
    if type(scope) is not TenantScope:
        raise TypeError("exact historical report tenant required")
    if type(page_size) is not int or not 1 <= page_size <= 12:
        raise ValueError("bounded page size 1-12 required")
    snapshot = require_read_only_snapshot(conn, scope)
    if cursor is not None:
        if (type(cursor) is not GroupReportCursor
                or (cursor.org_id, cursor.project_id) != scope.key
                or (cursor.snapshot, cursor.started_at, cursor.backend_pid)
                    != (snapshot["snapshot"], snapshot["started_at"], snapshot["backend_pid"])
                or type(cursor.group_id) is not UUID
                or type(cursor.created_at) is not datetime):
            raise ValueError("historical report cursor differs from current snapshot")
    if cursor is None:
        rows = conn.execute("""SELECT created_at,group_id
            FROM public.pipeline_snapshot_group_claim
            WHERE org_id=%s AND project_id=%s
            ORDER BY created_at,group_id LIMIT %s""",
            (*scope.key, page_size + 1)).fetchall()
    else:
        rows = conn.execute("""SELECT created_at,group_id
            FROM public.pipeline_snapshot_group_claim
            WHERE org_id=%s AND project_id=%s AND (created_at,group_id)>(%s,%s)
            ORDER BY created_at,group_id LIMIT %s""",
            (*scope.key, cursor.created_at, cursor.group_id, page_size + 1)).fetchall()
    selected = rows[:page_size]
    counts = Counter(classify_group(conn, scope, row["group_id"]).status.value
                     for row in selected)
    next_cursor = None
    if len(rows) > page_size:
        last = selected[-1]
        next_cursor = GroupReportCursor(
            scope.org_id, scope.project_id, snapshot["snapshot"], snapshot["started_at"],
            snapshot["backend_pid"], last["created_at"], last["group_id"],
        )
    return GroupReportPage(len(selected), tuple(sorted(counts.items())), next_cursor)
