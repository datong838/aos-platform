"""Wave 0 tests for the trusted database migration control plane."""
from __future__ import annotations

import importlib.util
import logging
from pathlib import Path
import sys
import types

import pytest

# The repository package imports the complete FastAPI application from
# ``aos_api.__init__``.  Standalone migration tests must not require the dev
# database merely to import their target module.  The normal full suite has
# already imported the real package from conftest, so this shim is only used
# with ``pytest --noconftest``.
if "aos_api" not in sys.modules:
    package = types.ModuleType("aos_api")
    package.__path__ = [
        str(Path(__file__).resolve().parents[1] / "aos_api")
    ]
    sys.modules["aos_api"] = package

from aos_api import migrations


class FakeInspector:
    def __init__(self, schema: dict[str, set[str]]) -> None:
        self.schema = schema

    def get_table_names(self) -> list[str]:
        return list(self.schema)

    def get_columns(self, table: str) -> list[dict[str, str]]:
        return [{"name": name} for name in self.schema[table]]


def compatible_schema() -> dict[str, set[str]]:
    return {
        table: set(columns)
        for table, columns in migrations.REQUIRED_LEGACY_SCHEMA.items()
    }


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("legacy-bootstrap", migrations.MigrationMode.LEGACY_BOOTSTRAP),
        ("MANAGED", migrations.MigrationMode.MANAGED),
        (" disabled ", migrations.MigrationMode.DISABLED),
    ],
)
def test_parse_migration_mode(raw: str, expected: migrations.MigrationMode) -> None:
    assert migrations.parse_migration_mode(raw) is expected


def test_parse_migration_mode_defaults_to_legacy_bootstrap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(migrations.MIGRATION_MODE_ENV, raising=False)
    monkeypatch.delenv(migrations.LEGACY_MIGRATE_ENV, raising=False)
    assert (
        migrations.parse_migration_mode()
        is migrations.MigrationMode.LEGACY_BOOTSTRAP
    )


def test_parse_migration_mode_supports_explicit_legacy_alias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(migrations.MIGRATION_MODE_ENV, raising=False)
    monkeypatch.setenv(migrations.LEGACY_MIGRATE_ENV, "1")
    assert migrations.parse_migration_mode() is migrations.MigrationMode.MANAGED


def test_parse_migration_mode_rejects_invalid_value() -> None:
    with pytest.raises(migrations.MigrationConfigurationError):
        migrations.parse_migration_mode("production-ish")


def test_classify_empty_database() -> None:
    assert (
        migrations.classify_database(FakeInspector({}))
        is migrations.DatabaseState.EMPTY
    )


def test_classify_alembic_managed_database() -> None:
    assert (
        migrations.classify_database(
            FakeInspector({"alembic_version": {"version_num"}})
        )
        is migrations.DatabaseState.MANAGED
    )


def test_classify_compatible_legacy_database() -> None:
    assert (
        migrations.classify_database(FakeInspector(compatible_schema()))
        is migrations.DatabaseState.LEGACY_COMPATIBLE
    )


def test_validate_core_schema_rejects_known_revision_without_core_tables() -> None:
    inspector = FakeInspector({"alembic_version": {"version_num"}})
    assert (
        migrations.classify_database(inspector)
        is migrations.DatabaseState.MANAGED
    )
    with pytest.raises(migrations.IncompatibleSchemaError, match="missing table"):
        migrations.validate_core_schema(inspector)


@pytest.mark.parametrize("damage", ["missing-table", "missing-column"])
def test_classify_incompatible_legacy_database(damage: str) -> None:
    schema = compatible_schema()
    if damage == "missing-table":
        schema.pop("authz_tuple")
    else:
        schema["meta_object_type"].remove("required_markings")
    assert (
        migrations.classify_database(FakeInspector(schema))
        is migrations.DatabaseState.INCOMPATIBLE
    )


@pytest.mark.parametrize(
    "mode",
    [
        migrations.MigrationMode.LEGACY_BOOTSTRAP,
        migrations.MigrationMode.DISABLED,
    ],
)
def test_non_managed_modes_do_not_touch_database(
    monkeypatch: pytest.MonkeyPatch,
    mode: migrations.MigrationMode,
) -> None:
    touched = False

    def unexpected() -> None:
        nonlocal touched
        touched = True

    monkeypatch.setattr(migrations, "_run_managed_migrations", unexpected)
    assert migrations.run_migrations(mode) is mode
    assert touched is False


class FakeEngine:
    disposed = False

    def dispose(self) -> None:
        self.disposed = True


@pytest.mark.parametrize("state", list(migrations.DatabaseState))
def test_managed_mode_fails_closed_without_full_schema_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    state: migrations.DatabaseState,
) -> None:
    engine = FakeEngine()

    monkeypatch.setattr("aos_api.db.get_dsn", lambda: "postgresql://host/db")
    monkeypatch.setattr(migrations, "create_engine", lambda _dsn: engine)
    monkeypatch.setattr(migrations, "inspect", lambda _engine: object())
    monkeypatch.setattr(migrations, "classify_database", lambda _inspector: state)

    with pytest.raises(migrations.ManagedMigrationNotReadyError, match="blocked"):
        migrations._run_managed_migrations()
    assert engine.disposed is True


def test_managed_failure_is_propagated_and_dsn_is_not_logged(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = "do-not-log-this-password"

    def fail() -> None:
        raise RuntimeError(f"postgresql://user:{secret}@db/aos")

    monkeypatch.setattr(migrations, "_run_managed_migrations", fail)
    with caplog.at_level(logging.ERROR):
        with pytest.raises(RuntimeError):
            migrations.run_migrations(migrations.MigrationMode.MANAGED)

    assert secret not in caplog.text
    assert "RuntimeError" in caplog.text


def test_postgres_dsn_uses_psycopg3_driver() -> None:
    assert (
        migrations._sqlalchemy_dsn("postgresql://user:pass@host/db")
        == "postgresql+psycopg://user:pass@host/db"
    )


def test_baseline_upgrade_executes_real_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    revision_path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "6cd2ca0eff8f_baseline.py"
    )
    spec = importlib.util.spec_from_file_location("aos_baseline_revision", revision_path)
    assert spec and spec.loader
    revision = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(revision)
    statements: list[str] = []
    monkeypatch.setattr(revision.op, "execute", statements.append)

    revision.upgrade()

    sql = "\n".join(statements)
    assert len(statements) == 11
    assert "CREATE TABLE meta_object_type" in sql
    assert "CREATE TABLE authz_tuple" in sql
    assert "CREATE INDEX idx_wiki_page_version_obj" in sql


def test_baseline_downgrade_is_explicitly_irreversible() -> None:
    revision_path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "6cd2ca0eff8f_baseline.py"
    )
    spec = importlib.util.spec_from_file_location(
        "aos_baseline_revision_for_downgrade", revision_path
    )
    assert spec and spec.loader
    revision = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(revision)

    with pytest.raises(RuntimeError, match="restore a verified database backup"):
        revision.downgrade()
