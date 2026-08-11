from pathlib import Path

from aos_api.db import connect


TABLES = {
    "aip_eval_dataset_revision",
    "aip_eval_run",
    "aip_eval_run_event",
    "aip_release_gate_decision",
    "aip_publication_event",
    "aip_lineage_event",
    "aip_usage_receipt",
    "aip_usage_adjustment",
    "aip_metric_definition_revision",
}

APPEND_ONLY = TABLES - {"aip_eval_run"}


def test_migration_is_linear_from_aip3b_head() -> None:
    migration = Path(__file__).parents[2] / "alembic" / "versions" / "aip4_001_eval_lineage_observability_contract.py"
    text = migration.read_text(encoding="utf-8")
    assert 'revision: str = "aip4_001"' in text
    assert 'down_revision: str | Sequence[str] | None = "aip3b_002"' in text


def test_aip4_tables_are_scoped_and_append_only() -> None:
    with connect() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        rows = conn.execute(
            """SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
               FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
               WHERE n.nspname='public' AND c.relname=ANY(%s)""",
            (list(TABLES),),
        ).fetchall()
        facts = {str(row["relname"]): row for row in rows}
        assert set(facts) == TABLES
        assert all(bool(row["relrowsecurity"]) for row in rows)
        assert all(bool(row["relforcerowsecurity"]) for row in rows)

        triggers = conn.execute(
            """SELECT c.relname AS event_object_table, t.tgname AS trigger_name
               FROM pg_trigger t
               JOIN pg_class c ON c.oid=t.tgrelid
               JOIN pg_namespace n ON n.oid=c.relnamespace
               WHERE n.nspname='public' AND NOT t.tgisinternal
                 AND c.relname=ANY(%s)""",
            (list(APPEND_ONLY),),
        ).fetchall()
        by_table: dict[str, set[str]] = {}
        for row in triggers:
            by_table.setdefault(str(row["event_object_table"]), set()).add(
                str(row["trigger_name"])
            )
        assert set(by_table) == APPEND_ONLY
        assert all(any(name.endswith("append_only") for name in names) for names in by_table.values())
        assert all(any(name.endswith("truncate_guard") for name in names) for names in by_table.values())


def test_migration_does_not_rewrite_existing_authorities() -> None:
    migration = Path(__file__).parents[2] / "alembic" / "versions" / "aip4_001_eval_lineage_observability_contract.py"
    text = migration.read_text(encoding="utf-8").lower()
    for table in (
        "aip_eval_suite",
        "aip_eval_report",
        "aip_logic_publication",
        "decision_lineage",
    ):
        assert f"alter table {table}" not in text
        assert f"drop table {table}" not in text
        assert f"delete from {table}" not in text
