"""TI-3 E7 contract Object Runtime tenant identities and active rows.

Revision ID: 228ti3e7contract
Revises: 228ti3e6rls
Create Date: 2026-08-04
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "228ti3e7contract"
down_revision: str | Sequence[str] | None = "228ti3e6rls"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCOPED_PRIMARY_KEYS = {
    "funnel_status": ("org_id", "project_id", "object_type"),
    "graph_edge": (
        "org_id", "project_id", "src_type", "src_id", "rel", "dst_type", "dst_id",
    ),
    "meta_branch": ("org_id", "project_id", "id"),
    "obj_branch_overlay": (
        "org_id", "project_id", "branch_id", "object_type", "object_id",
    ),
    "obj_instance": ("org_id", "project_id", "object_type", "object_id"),
    "object_lifecycle": ("org_id", "project_id", "object_type", "object_id"),
    "draft_dataset": ("org_id", "project_id", "id"),
    "wiki_page": ("org_id", "project_id", "object_type", "object_id"),
    "wiki_page_version": ("org_id", "project_id", "id"),
}

LEGACY_PRIMARY_KEYS = {
    "funnel_status": ("object_type",),
    "graph_edge": ("src_type", "src_id", "rel", "dst_type", "dst_id"),
    "meta_branch": ("id",),
    "obj_branch_overlay": ("branch_id", "object_type", "object_id"),
    "obj_instance": ("object_type", "object_id"),
    "object_lifecycle": ("object_type", "object_id"),
    "draft_dataset": ("id",),
    "wiki_page": ("object_type", "object_id"),
    "wiki_page_version": ("id",),
}

QUARANTINE_KEYS = {
    "funnel_status": ("object_type",),
    "graph_edge": ("src_type", "src_id", "rel", "dst_type", "dst_id"),
    "meta_branch": ("id",),
    "obj_instance": ("object_type", "object_id"),
}

EXPANDED_NULLABLE_TABLES = tuple(QUARANTINE_KEYS) + ("obj_branch_overlay",)
QUARANTINE_TABLE = "object_runtime_orphan_quarantine"


def _columns(columns: tuple[str, ...]) -> str:
    return ", ".join(columns)


def _json_key(columns: tuple[str, ...], alias: str = "source") -> str:
    args = ", ".join(f"'{column}', {alias}.{column}" for column in columns)
    return f"jsonb_build_object({args})"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE {QUARANTINE_TABLE} (
          quarantine_id TEXT PRIMARY KEY,
          source_table TEXT NOT NULL,
          source_key JSONB NOT NULL,
          payload JSONB NOT NULL,
          payload_hash TEXT NOT NULL,
          reason_code TEXT NOT NULL DEFAULT 'UNKNOWN_TENANT_SCOPE',
          source_revision TEXT NOT NULL DEFAULT '228ti3e6rls',
          quarantined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          CONSTRAINT object_runtime_orphan_quarantine_source_unique
            UNIQUE (source_table, payload_hash)
        )
        """
    )
    op.execute(f"REVOKE ALL ON {QUARANTINE_TABLE} FROM aos_runtime")
    op.execute(
        """
        CREATE FUNCTION guard_object_runtime_quarantine_immutable()
        RETURNS trigger LANGUAGE plpgsql AS $guard$
        BEGIN
          RAISE EXCEPTION 'Object Runtime quarantine is append-only';
        END
        $guard$
        """
    )
    op.execute(
        f"CREATE TRIGGER trg_{QUARANTINE_TABLE}_immutable "
        f"BEFORE UPDATE OR DELETE ON {QUARANTINE_TABLE} FOR EACH ROW "
        "EXECUTE FUNCTION guard_object_runtime_quarantine_immutable()"
    )
    op.execute(
        f"CREATE TRIGGER trg_{QUARANTINE_TABLE}_truncate_guard "
        f"BEFORE TRUNCATE ON {QUARANTINE_TABLE} FOR EACH STATEMENT "
        "EXECUTE FUNCTION guard_object_runtime_quarantine_immutable()"
    )

    for table, key_columns in QUARANTINE_KEYS.items():
        key_expr = _json_key(key_columns)
        op.execute(
            f"""
            DO $move$
            DECLARE
              expected_count BIGINT;
              copied_count BIGINT;
              removed_count BIGINT;
            BEGIN
              SELECT COUNT(*) INTO expected_count
                FROM {table}
               WHERE org_id IS NULL OR project_id IS NULL;

              INSERT INTO {QUARANTINE_TABLE} (
                quarantine_id, source_table, source_key, payload, payload_hash
              )
              SELECT '{table}:' || md5(to_jsonb(source)::text),
                     '{table}', {key_expr}, to_jsonb(source),
                     md5(to_jsonb(source)::text)
                FROM {table} AS source
               WHERE source.org_id IS NULL OR source.project_id IS NULL;
              GET DIAGNOSTICS copied_count = ROW_COUNT;

              DELETE FROM {table}
               WHERE org_id IS NULL OR project_id IS NULL;
              GET DIAGNOSTICS removed_count = ROW_COUNT;

              IF copied_count <> expected_count OR removed_count <> expected_count THEN
                RAISE EXCEPTION
                  'TI-3 E7 quarantine mismatch for {table}: expected %, copied %, removed %',
                  expected_count, copied_count, removed_count;
              END IF;
            END
            $move$;
            """
        )

    for table in SCOPED_PRIMARY_KEYS:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN org_id SET NOT NULL")
        op.execute(f"ALTER TABLE {table} ALTER COLUMN project_id SET NOT NULL")

    op.execute(
        "ALTER TABLE obj_branch_overlay "
        "DROP CONSTRAINT obj_branch_overlay_branch_id_fkey"
    )
    for table, columns in SCOPED_PRIMARY_KEYS.items():
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {table}_pkey")
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {table}_pkey "
            f"PRIMARY KEY ({_columns(columns)})"
        )
    op.execute(
        "ALTER TABLE obj_branch_overlay "
        "ADD CONSTRAINT fk_obj_branch_overlay_branch_ti3 "
        "FOREIGN KEY (org_id, project_id, branch_id) "
        "REFERENCES meta_branch(org_id, project_id, id) ON DELETE CASCADE"
    )


def downgrade() -> None:
    collision_checks = []
    for table, columns in LEGACY_PRIMARY_KEYS.items():
        collision_checks.append(
            f"EXISTS (SELECT 1 FROM {table} GROUP BY {_columns(columns)} "
            "HAVING COUNT(*) > 1)"
        )
    for table, columns in QUARANTINE_KEYS.items():
        matches = " AND ".join(
            f"active.{column} = quarantined.source_key->>'{column}'"
            for column in columns
        )
        collision_checks.append(
            f"EXISTS (SELECT 1 FROM {QUARANTINE_TABLE} quarantined "
            f"JOIN {table} active ON {matches} "
            f"WHERE quarantined.source_table='{table}')"
        )
    op.execute(
        "DO $contract$ BEGIN "
        f"IF {' OR '.join(collision_checks)} THEN "
        "RAISE EXCEPTION 'TI-3 E7 downgrade blocked by legacy key collision' "
        "USING ERRCODE='23505'; END IF; END $contract$;"
    )

    op.execute(
        "ALTER TABLE obj_branch_overlay "
        "DROP CONSTRAINT fk_obj_branch_overlay_branch_ti3"
    )
    for table in reversed(tuple(SCOPED_PRIMARY_KEYS)):
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {table}_pkey")
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {table}_pkey "
            f"PRIMARY KEY ({_columns(LEGACY_PRIMARY_KEYS[table])})"
        )
    op.execute(
        "ALTER TABLE obj_branch_overlay "
        "ADD CONSTRAINT obj_branch_overlay_branch_id_fkey "
        "FOREIGN KEY (branch_id) REFERENCES meta_branch(id) ON DELETE CASCADE"
    )

    for table in EXPANDED_NULLABLE_TABLES:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN org_id DROP NOT NULL")
        op.execute(f"ALTER TABLE {table} ALTER COLUMN project_id DROP NOT NULL")

    op.execute(
        f"DROP TRIGGER trg_{QUARANTINE_TABLE}_immutable ON {QUARANTINE_TABLE}"
    )
    op.execute(
        f"DROP TRIGGER trg_{QUARANTINE_TABLE}_truncate_guard ON {QUARANTINE_TABLE}"
    )
    for table in QUARANTINE_KEYS:
        op.execute(
            f"INSERT INTO {table} "
            f"SELECT (jsonb_populate_record(NULL::{table}, payload)).* "
            f"FROM {QUARANTINE_TABLE} WHERE source_table='{table}'"
        )
    op.execute(f"DROP TABLE {QUARANTINE_TABLE}")
    op.execute("DROP FUNCTION guard_object_runtime_quarantine_immutable()")
