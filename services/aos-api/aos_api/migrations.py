"""Trusted database migration control plane.

``AOS_DB_MIGRATION_MODE`` selects one of three explicit modes:

* ``legacy-bootstrap`` (default): keep the existing dev/test ``init_schema``
  path.  This function deliberately performs no Alembic operation.
* ``managed``: classify the database and fail closed until a complete,
  versioned schema inventory exists.  The current core-only baseline is not
  represented as production-ready.
* ``disabled``: perform no migration, for explicit read-only diagnostics.

The deprecated ``AOS_DB_MIGRATE=1`` setting remains a compatibility alias for
``managed``.  It is never used to infer a production environment.
"""
from __future__ import annotations

import os
from enum import Enum
from typing import Mapping

from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.engine.reflection import Inspector

from aos_api.logging_facade import get_logger

log = get_logger("aos-api.migrations")

MIGRATION_MODE_ENV = "AOS_DB_MIGRATION_MODE"
LEGACY_MIGRATE_ENV = "AOS_DB_MIGRATE"


class MigrationMode(str, Enum):
    """Supported startup migration modes."""

    LEGACY_BOOTSTRAP = "legacy-bootstrap"
    MANAGED = "managed"
    DISABLED = "disabled"


class DatabaseState(str, Enum):
    """Database states relevant to adopting Alembic."""

    EMPTY = "empty"
    LEGACY_COMPATIBLE = "legacy-compatible"
    MANAGED = "managed"
    INCOMPATIBLE = "incompatible"


class MigrationConfigurationError(ValueError):
    """Raised when migration mode configuration is invalid."""


class IncompatibleSchemaError(RuntimeError):
    """Raised when an unmanaged database fails the legacy schema preflight."""


class ManagedMigrationNotReadyError(RuntimeError):
    """Raised while the repository lacks a complete managed schema snapshot."""


# This is the minimum schema created by the baseline revision.  Additional
# runtime DDL remains registered as legacy debt and is intentionally not
# claimed as Alembic-managed by this Wave.
REQUIRED_LEGACY_SCHEMA: Mapping[str, frozenset[str]] = {
    "meta_object_type": frozenset(
        {
            "id",
            "name",
            "description",
            "published",
            "properties",
            "required_markings",
            "created_at",
        }
    ),
    "obj_instance": frozenset({"object_type", "object_id", "props"}),
    "graph_edge": frozenset(
        {"src_type", "src_id", "rel", "dst_type", "dst_id"}
    ),
    "wiki_page": frozenset(
        {"object_type", "object_id", "body", "org_id", "project_id"}
    ),
    "wiki_page_version": frozenset(
        {
            "id",
            "object_type",
            "object_id",
            "body",
            "draft_id",
            "org_id",
            "project_id",
            "created_at",
        }
    ),
    "meta_branch": frozenset(
        {"id", "name", "base_ref", "readonly", "created_at"}
    ),
    "obj_branch_overlay": frozenset(
        {
            "branch_id",
            "object_type",
            "object_id",
            "props",
            "op",
            "updated_at",
        }
    ),
    "meta_link_type": frozenset(
        {
            "id",
            "name",
            "src_type",
            "dst_type",
            "rel",
            "cardinality",
            "expected_edges",
            "mdo_approved",
            "published",
            "description",
            "created_at",
        }
    ),
    "funnel_status": frozenset({"object_type", "stage", "detail"}),
    "authz_tuple": frozenset({"user_key", "relation", "object_key"}),
}


def parse_migration_mode(value: str | MigrationMode | None = None) -> MigrationMode:
    """Parse the explicit mode while preserving the legacy env alias."""

    if isinstance(value, MigrationMode):
        return value
    raw = value
    if raw is None:
        raw = os.getenv(MIGRATION_MODE_ENV)
    if raw is None:
        legacy_value = os.getenv(LEGACY_MIGRATE_ENV)
        if legacy_value == "1":
            log.warning(
                "migration_mode_legacy_env deprecated_env=%s",
                LEGACY_MIGRATE_ENV,
            )
            return MigrationMode.MANAGED
        if legacy_value in {"0", ""}:
            log.warning(
                "migration_mode_legacy_env deprecated_env=%s",
                LEGACY_MIGRATE_ENV,
            )
        elif legacy_value is not None:
            raise MigrationConfigurationError(
                f"{LEGACY_MIGRATE_ENV} must be '0' or '1'"
            )
        return MigrationMode.LEGACY_BOOTSTRAP

    normalized = raw.strip().lower()
    try:
        return MigrationMode(normalized)
    except ValueError as exc:
        allowed = ", ".join(mode.value for mode in MigrationMode)
        raise MigrationConfigurationError(
            f"{MIGRATION_MODE_ENV} must be one of: {allowed}"
        ) from exc


def _sqlalchemy_dsn(dsn: str) -> str:
    """Select the installed psycopg v3 driver for PostgreSQL URLs."""

    if dsn.startswith("postgresql://"):
        return "postgresql+psycopg://" + dsn.removeprefix("postgresql://")
    if dsn.startswith("postgres://"):
        return "postgresql+psycopg://" + dsn.removeprefix("postgres://")
    return dsn


def classify_database(inspector: Inspector) -> DatabaseState:
    """Classify a database without mutating it."""

    tables = set(inspector.get_table_names())
    if "alembic_version" in tables:
        return DatabaseState.MANAGED
    if not tables:
        return DatabaseState.EMPTY

    try:
        validate_core_schema(inspector)
    except IncompatibleSchemaError:
        return DatabaseState.INCOMPATIBLE
    return DatabaseState.LEGACY_COMPATIBLE


def validate_core_schema(inspector: Inspector) -> None:
    """Require every table and column owned by the Wave 0 baseline."""

    tables = set(inspector.get_table_names())
    for table, required_columns in REQUIRED_LEGACY_SCHEMA.items():
        if table not in tables:
            raise IncompatibleSchemaError(
                f"core schema preflight failed: missing table {table}"
            )
        actual_columns = {
            column["name"] for column in inspector.get_columns(table)
        }
        missing_columns = required_columns - actual_columns
        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            raise IncompatibleSchemaError(
                f"core schema preflight failed: {table} missing columns {missing}"
            )


def run_migrations(mode: str | MigrationMode | None = None) -> MigrationMode:
    """Apply the selected migration policy and return the resolved mode."""

    resolved = parse_migration_mode(mode)
    log.info("migration_mode_selected mode=%s", resolved.value)
    if resolved is MigrationMode.LEGACY_BOOTSTRAP:
        log.info("migration_legacy_bootstrap delegated_to_init_schema")
        return resolved
    if resolved is MigrationMode.DISABLED:
        log.warning("migration_disabled explicit=true")
        return resolved

    try:
        _run_managed_migrations()
    except Exception as exc:
        # Log only the exception class: driver errors may embed a DSN.
        log.error(
            "migration_managed_failed error_type=%s",
            type(exc).__name__,
        )
        raise
    return resolved


def _run_managed_migrations() -> DatabaseState:
    """Classify the database and fail closed until the full snapshot exists.

    The repository still contains runtime DDL outside ``REQUIRED_LEGACY_SCHEMA``.
    Therefore none of the currently observable states can prove that every
    route's schema dependency is present.  The core baseline remains useful as
    a real, testable migration asset, but managed startup must not advertise it
    as a complete production schema.
    """

    from aos_api.db import get_dsn

    dsn = _sqlalchemy_dsn(get_dsn())
    engine: Engine = create_engine(dsn)
    try:
        state = classify_database(inspect(engine))
        log.info("migration_database_classified state=%s", state.value)
        raise ManagedMigrationNotReadyError(
            "managed migration is blocked: the current baseline covers only "
            f"the core schema (database state: {state.value}); use "
            "legacy-bootstrap until a complete versioned schema inventory is "
            "available"
        )
    finally:
        engine.dispose()
