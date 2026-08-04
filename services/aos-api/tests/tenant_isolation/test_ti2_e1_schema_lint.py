from __future__ import annotations

from aos_api.db import connect
from aos_api.tenant_schema_lint import build_ti2_e1_schema_report


def test_ti2_e1_real_schema_lint_is_green() -> None:
    with connect() as conn:
        report = build_ti2_e1_schema_report(conn)

    assert report["ok"] is True, report
    assert report["stage"] == "TI-2-E1"
    assert report["alembicRevision"] in {
        "228ti2e1expand",
        "228ti2e4validate",
        "228ti2e6rls",
    }
    assert report["ti2MissingColumns"] == {}
    assert report["ti2NonNullableExpandColumns"] == {}
    assert report["ti2MissingHistoryTables"] == []
    assert report["ti2MissingForeignKeys"] == []
    assert report["ti2PrematurelyValidatedForeignKeys"] == []
    assert report["ti2MissingAppendOnlyTriggers"] == []
