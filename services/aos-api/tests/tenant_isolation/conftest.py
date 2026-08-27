from __future__ import annotations

from pathlib import Path

import psycopg
import pytest

from aos_api.db import get_dsn


_TI4_ISOLATED_DATABASE_SUFFIX = "_ti4_test"


def _is_ti4_test(item: pytest.Item) -> bool:
    return Path(str(item.path)).name.startswith("test_ti4_")


def _current_database_name() -> str | None:
    try:
        with psycopg.connect(get_dsn()) as conn:
            row = conn.execute("SELECT current_database()").fetchone()
    except psycopg.Error:
        return None
    return str(row[0]) if row else None


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    ti4_items = [item for item in items if _is_ti4_test(item)]
    if not ti4_items:
        return

    database_name = _current_database_name()
    if database_name and database_name.endswith(_TI4_ISOLATED_DATABASE_SUFFIX):
        return

    reason = (
        "TI-4 tests include writes and Alembic downgrade/upgrade drills; "
        "run them only against a disposable database named *_ti4_test"
    )
    skip = pytest.mark.skip(reason=reason)
    for item in ti4_items:
        item.add_marker(skip)
