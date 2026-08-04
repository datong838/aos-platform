from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from aos_api.db import connect, get_dsn

TABLES = (
    "funnel_status",
    "graph_edge",
    "meta_branch",
    "obj_branch_overlay",
    "obj_instance",
    "object_lifecycle",
    "draft_dataset",
    "wiki_page",
    "wiki_page_version",
)


def _config() -> Config:
    root = Path(__file__).resolve().parents[2]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", get_dsn())
    return cfg


def _validated(conn) -> dict[str, bool]:
    rows = conn.execute(
        """
        SELECT c.conname,c.convalidated
        FROM pg_constraint c
        WHERE c.conname = ANY(%s)
        """,
        ([f"fk_{table}_workspace_ti3" for table in TABLES],),
    ).fetchall()
    return {row["conname"]: bool(row["convalidated"]) for row in rows}


def _counts(conn) -> dict[str, tuple[int, int]]:
    result = {}
    for table in TABLES:
        row = conn.execute(
            f"SELECT COUNT(*) AS total, COUNT(*) FILTER "
            f"(WHERE org_id IS NULL OR project_id IS NULL) AS unknown FROM {table}"
        ).fetchone()
        result[table] = (int(row["total"]), int(row["unknown"]))
    return result


def test_workspace_fk_precheck_has_no_non_null_orphans() -> None:
    with connect() as conn:
        violations = {}
        for table in TABLES:
            row = conn.execute(
                f"""
                SELECT COUNT(*) AS c FROM {table} t
                WHERE t.org_id IS NOT NULL AND t.project_id IS NOT NULL
                  AND NOT EXISTS (
                    SELECT 1 FROM twa_workspace w
                    WHERE w.org_id=t.org_id AND w.project_id=t.project_id
                  )
                """
            ).fetchone()
            violations[table] = int(row["c"])
    assert violations == {table: 0 for table in TABLES}


def test_validate_downgrade_upgrade_preserves_rows_and_null_quarantine() -> None:
    cfg = _config()
    command.downgrade(cfg, "228ti3e1expand")
    with connect() as conn:
        before = _counts(conn)
    command.upgrade(cfg, "228ti3e4validate")
    with connect() as conn:
        assert _validated(conn) == {
            f"fk_{table}_workspace_ti3": True for table in TABLES
        }
        assert _counts(conn) == before
    command.downgrade(cfg, "228ti3e1expand")
    with connect() as conn:
        assert _validated(conn) == {
            f"fk_{table}_workspace_ti3": False for table in TABLES
        }
        assert _counts(conn) == before
    command.upgrade(cfg, "228ti3e4validate")
    with connect() as conn:
        assert _validated(conn) == {
            f"fk_{table}_workspace_ti3": True for table in TABLES
        }
        assert _counts(conn) == before
    # Restore the session database to the latest contract for subsequent gates.
    command.upgrade(cfg, "head")
