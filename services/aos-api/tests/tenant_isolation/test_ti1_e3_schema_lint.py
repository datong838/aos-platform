from __future__ import annotations

from aos_api.tenant_schema_lint import (
    E3_REQUIRED_COLUMNS,
    EXPECTED_FOREIGN_KEYS,
    build_ti1_e3_schema_report,
)


class Result:
    def __init__(self, *, rows=None, row=None) -> None:
        self.rows = rows or []
        self.row = row

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.row


class FakeConnection:
    def __init__(self, *, omit_trigger: bool = False) -> None:
        self.omit_trigger = omit_trigger

    def execute(self, query: str):
        if "table_name='tenant_dual_write_ledger'" in query:
            nullable = {"observed_org_id", "observed_project_id"}
            names = {
                "org_id", "project_id", "ledger_id", "resource", "operation",
                "key_hash", "observed_org_id", "observed_project_id", "status",
                "created_at",
            }
            return Result(rows=[
                {"column_name": name, "is_nullable": "YES" if name in nullable else "NO"}
                for name in sorted(names)
            ])
        for table, names in E3_REQUIRED_COLUMNS.items():
            if f"table_name='{table}'" in query:
                nullable = {
                    "approved_at", "completed_at", "target_org_id",
                    "target_project_id", "after_hash",
                }
                return Result(rows=[
                    {"column_name": name, "is_nullable": "YES" if name in nullable else "NO"}
                    for name in sorted(names)
                ])
        if "information_schema.columns" in query:
            return Result(rows=[
                {"column_name": "org_id", "is_nullable": "YES"},
                {"column_name": "project_id", "is_nullable": "YES"},
            ])
        if "pg_constraint" in query:
            return Result(rows=[
                {"conname": name, "convalidated": False}
                for name in sorted(EXPECTED_FOREIGN_KEYS)
            ])
        if "pg_trigger" in query:
            rows = [
                {"table_name": table, "trigger_name": f"trg_{table}_{suffix}"}
                for table in E3_REQUIRED_COLUMNS
                for suffix in ("immutable", "truncate_guard")
            ]
            return Result(rows=rows[1:] if self.omit_trigger else rows)
        if "pg_class" in query:
            return Result(row={"count": 0})
        return Result(row={"version_num": "228ti1e3ledger"})


def test_e3_schema_lint_accepts_strong_append_only_ledgers() -> None:
    report = build_ti1_e3_schema_report(FakeConnection())

    assert report["ok"] is True
    assert report["stage"] == "TI-1-E3-1"
    assert report["e3MissingColumnsByTable"] == {}
    assert report["e3NullableScopeByTable"] == {}
    assert report["e3MissingAppendOnlyTriggers"] == []


def test_e3_schema_lint_fails_when_immutability_trigger_missing() -> None:
    report = build_ti1_e3_schema_report(FakeConnection(omit_trigger=True))

    assert report["ok"] is False
    assert "E3_APPEND_ONLY_TRIGGERS_MISSING" in report["issues"]
