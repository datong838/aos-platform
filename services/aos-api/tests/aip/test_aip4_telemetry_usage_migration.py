from pathlib import Path

from aos_api.db import connect


def test_e3b_migration_is_linear_and_additive() -> None:
    path = (
        Path(__file__).parents[2]
        / "alembic/versions/aip4_005_telemetry_usage_authority.py"
    )
    text = path.read_text(encoding="utf-8")
    assert 'revision: str = "aip4_005"' in text
    assert 'down_revision: str | Sequence[str] | None = "aip4_004"' in text
    assert "CREATE TABLE aip_telemetry_span" in text
    assert "DROP TABLE aip_usage_receipt" not in text


def test_e3b_span_and_usage_contracts_are_scoped_and_append_only() -> None:
    with connect() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        table = conn.execute(
            """SELECT relrowsecurity,relforcerowsecurity FROM pg_class c
               JOIN pg_namespace n ON n.oid=c.relnamespace
               WHERE n.nspname='public' AND c.relname='aip_telemetry_span'"""
        ).fetchone()
        assert table is not None
        assert bool(table["relrowsecurity"])
        assert bool(table["relforcerowsecurity"])
        triggers = conn.execute(
            """SELECT c.relname,t.tgname FROM pg_trigger t
               JOIN pg_class c ON c.oid=t.tgrelid
               WHERE c.relname=ANY(%s) AND NOT t.tgisinternal""",
            (["aip_telemetry_span", "aip_usage_receipt", "aip_usage_adjustment"],),
        ).fetchall()
        by_table: dict[str, set[str]] = {}
        for row in triggers:
            by_table.setdefault(str(row["relname"]), set()).add(str(row["tgname"]))
        assert set(by_table) == {
            "aip_telemetry_span",
            "aip_usage_receipt",
            "aip_usage_adjustment",
        }
        assert all(
            any(name.endswith("append_only") for name in names)
            for names in by_table.values()
        )
        nullable = conn.execute(
            """SELECT is_nullable FROM information_schema.columns
               WHERE table_schema='public' AND table_name='aip_usage_receipt'
                 AND column_name='quantity'"""
        ).fetchone()
        assert nullable["is_nullable"] == "YES"
