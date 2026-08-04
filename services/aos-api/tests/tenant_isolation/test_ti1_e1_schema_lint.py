from __future__ import annotations

from aos_api.tenant_schema_lint import (
    EXPECTED_FOREIGN_KEYS,
    build_ti1_e1_schema_report,
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
    def __init__(self, *, validated: bool = False, rls_count: int = 0) -> None:
        self.validated = validated
        self.rls_count = rls_count

    def execute(self, query: str):
        if "information_schema.columns" in query:
            return Result(
                rows=[
                    {"column_name": "org_id", "is_nullable": "YES"},
                    {"column_name": "project_id", "is_nullable": "YES"},
                ]
            )
        if "pg_constraint" in query:
            return Result(
                rows=[
                    {"conname": name, "convalidated": self.validated}
                    for name in sorted(EXPECTED_FOREIGN_KEYS)
                ]
            )
        if "pg_class" in query:
            return Result(row={"count": self.rls_count})
        return Result(row={"version_num": "228ti1e1expand"})


def test_ti1_e1_schema_lint_accepts_expand_without_rls() -> None:
    report = build_ti1_e1_schema_report(FakeConnection())

    assert report["ok"] is True
    assert report["foreignKeyCount"] == 7
    assert report["authzTenantColumns"] == ["org_id", "project_id"]
    assert report["rlsEnabledOrForcedTableCount"] == 0


def test_ti1_e1_schema_lint_fails_on_early_validate_or_rls() -> None:
    report = build_ti1_e1_schema_report(
        FakeConnection(validated=True, rls_count=1)
    )

    assert report["ok"] is False
    assert "TI1_FOREIGN_KEYS_PREMATURELY_VALIDATED" in report["issues"]
    assert "RLS_ENABLED_BEFORE_E6" in report["issues"]
