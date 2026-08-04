from __future__ import annotations

import importlib.util
from pathlib import Path

from aos_api.db import connect
from aos_api.tenant_schema_lint import (
    TI2_NOT_VALID_FOREIGN_KEYS,
    build_ti2_e4_schema_report,
)


def _revision_module():
    path = (
        Path(__file__).parents[2]
        / "alembic"
        / "versions"
        / "228ti2e4_validate_module_fks.py"
    )
    spec = importlib.util.spec_from_file_location("ti2e4_revision", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, path.read_text(encoding="utf-8")


def test_e4_revision_is_validate_only_and_reversible_metadata() -> None:
    revision, source = _revision_module()
    assert revision.revision == "228ti2e4validate"
    assert revision.down_revision == "228ti2e1expand"
    upgrade_source = source.split("def upgrade()", 1)[1].split("def downgrade()", 1)[0]
    assert "VALIDATE CONSTRAINT" in upgrade_source
    for forbidden in ("UPDATE ", "INSERT ", "DELETE ", "TRUNCATE "):
        assert forbidden not in upgrade_source
    assert "NOT VALID" in source.split("def downgrade()", 1)[1]


def test_e4_schema_report_has_all_validated_foreign_keys() -> None:
    with connect() as conn:
        report = build_ti2_e4_schema_report(conn)
    assert report["ok"] is True
    assert report["ti2ValidatedForeignKeyCount"] == len(
        TI2_NOT_VALID_FOREIGN_KEYS
    )
    assert report["ti2NotValidatedForeignKeys"] == []
