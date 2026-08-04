"""TI-4 D7 contract Data OS tenant identities and quarantine history.

Revision ID: 228ti4d7contract
Revises: 228ti4d6rls
Create Date: 2026-08-04
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "228ti4d7contract"
down_revision: str | Sequence[str] | None = "228ti4d6rls"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCOPED_PRIMARY_KEYS = {
    "meta_source": ("org_id", "project_id", "id"),
    "meta_pipeline": ("org_id", "project_id", "id"),
    "meta_dataset": ("org_id", "project_id", "rid"),
    "meta_dataset_history": ("org_id", "project_id", "id"),
    "meta_sync": ("org_id", "project_id", "id"),
    "meta_schedule": ("org_id", "project_id", "id"),
    "phase5_pipeline_graph": ("org_id", "project_id", "pipeline_id"),
}
LEGACY_PRIMARY_KEYS = {
    "meta_source": ("id",),
    "meta_pipeline": ("id",),
    "meta_dataset": ("rid",),
    "meta_dataset_history": ("id",),
    "meta_sync": ("id",),
    "meta_schedule": ("id",),
    "phase5_pipeline_graph": ("pipeline_id",),
}
QUARANTINE_KEYS = LEGACY_PRIMARY_KEYS
QUARANTINE_TABLE = "data_os_orphan_quarantine"
EVIDENCE_BATCH_TABLE = "ti4_d7_evidence_batch"
PARENT_FOREIGN_KEYS = (
    (
        "meta_pipeline",
        "fk_meta_pipeline_source_ti4d7",
        "source_id",
        "meta_source",
        "id",
    ),
    (
        "meta_dataset",
        "fk_meta_dataset_source_ti4d7",
        "source_id",
        "meta_source",
        "id",
    ),
    (
        "meta_dataset",
        "fk_meta_dataset_pipeline_ti4d7",
        "pipeline_id",
        "meta_pipeline",
        "id",
    ),
    (
        "meta_dataset_history",
        "fk_meta_dataset_history_dataset_ti4d7",
        "dataset_rid",
        "meta_dataset",
        "rid",
    ),
    (
        "meta_sync",
        "fk_meta_sync_source_ti4d7",
        "source_id",
        "meta_source",
        "id",
    ),
    (
        "meta_schedule",
        "fk_meta_schedule_pipeline_ti4d7",
        "pipeline_id",
        "meta_pipeline",
        "id",
    ),
)


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
          reason_code TEXT NOT NULL DEFAULT 'TENANT_SCOPE_UNPROVEN',
          ownership_batch_id UUID NOT NULL,
          source_revision TEXT NOT NULL DEFAULT '228ti4d6rls',
          quarantined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          CONSTRAINT data_os_orphan_quarantine_source_unique
            UNIQUE (source_table, payload_hash)
        )
        """
    )
    op.execute(f"REVOKE ALL ON {QUARANTINE_TABLE} FROM aos_runtime")
    total_sql = " + ".join(
        f"(SELECT COUNT(*) FROM {table})" for table in SCOPED_PRIMARY_KEYS
    )
    unknown_sql = " + ".join(
        f"(SELECT COUNT(*) FROM {table} "
        "WHERE org_id IS NULL OR project_id IS NULL)"
        for table in SCOPED_PRIMARY_KEYS
    )
    op.execute(
        f"CREATE TEMP TABLE {EVIDENCE_BATCH_TABLE} "
        "(batch_id UUID PRIMARY KEY) ON COMMIT DROP"
    )
    op.execute(
        f"""
        DO $evidence$
        DECLARE
          current_total BIGINT := {total_sql};
          current_unknown BIGINT := {unknown_sql};
          selected_batch UUID;
        BEGIN
          IF current_unknown = 0 THEN
            RETURN;
          END IF;
          SELECT d.batch_id INTO selected_batch
            FROM tenant_ownership_decision d
            JOIN tenant_backfill_batch b
              ON b.org_id=d.org_id AND b.project_id=d.project_id
             AND b.batch_id=d.batch_id
           GROUP BY d.batch_id, b.created_at
          HAVING COUNT(*)=current_total
             AND COUNT(*) FILTER (WHERE d.decision='QUARANTINE')=current_unknown
             AND COUNT(*) FILTER (WHERE d.decision='NO_ACTION')=
                 current_total-current_unknown
             AND COUNT(*) FILTER (WHERE d.decision IN ('ASSIGN','BLOCKED'))=0
           ORDER BY b.created_at DESC
           LIMIT 1;
          IF selected_batch IS NULL THEN
            RAISE EXCEPTION
              'TI-4 D7 requires a matching complete D3 ownership batch: total %, unknown %',
              current_total, current_unknown;
          END IF;
          INSERT INTO {EVIDENCE_BATCH_TABLE} VALUES (selected_batch);
        END
        $evidence$;
        """
    )
    op.execute(
        """
        CREATE FUNCTION guard_data_os_quarantine_immutable()
        RETURNS trigger LANGUAGE plpgsql AS $guard$
        BEGIN
          RAISE EXCEPTION 'Data OS quarantine is append-only';
        END
        $guard$
        """
    )
    op.execute(
        f"CREATE TRIGGER trg_{QUARANTINE_TABLE}_immutable "
        f"BEFORE UPDATE OR DELETE ON {QUARANTINE_TABLE} FOR EACH ROW "
        "EXECUTE FUNCTION guard_data_os_quarantine_immutable()"
    )
    op.execute(
        f"CREATE TRIGGER trg_{QUARANTINE_TABLE}_truncate_guard "
        f"BEFORE TRUNCATE ON {QUARANTINE_TABLE} FOR EACH STATEMENT "
        "EXECUTE FUNCTION guard_data_os_quarantine_immutable()"
    )

    for table, key_columns in QUARANTINE_KEYS.items():
        key_expr = _json_key(key_columns)
        op.execute(
            f"""
            DO $move$
            DECLARE
              expected_count BIGINT;
              decision_count BIGINT;
              evidence_batch UUID;
              copied_count BIGINT;
              removed_count BIGINT;
            BEGIN
              SELECT COUNT(*) INTO expected_count FROM {table}
               WHERE org_id IS NULL OR project_id IS NULL;
              SELECT batch_id INTO evidence_batch FROM {EVIDENCE_BATCH_TABLE};
              SELECT COUNT(*) INTO decision_count FROM tenant_ownership_decision
               WHERE batch_id=evidence_batch AND resource='{table}'
                 AND decision='QUARANTINE';
              IF expected_count > 0 AND decision_count <> expected_count THEN
                RAISE EXCEPTION
                  'TI-4 D7 D3 decision mismatch for {table}: rows %, decisions %',
                  expected_count, decision_count;
              END IF;

              INSERT INTO {QUARANTINE_TABLE} (
                quarantine_id, source_table, source_key, payload, payload_hash,
                ownership_batch_id
              )
              SELECT '{table}:' || md5(to_jsonb(source)::text),
                     '{table}', {key_expr}, to_jsonb(source),
                     md5(to_jsonb(source)::text), evidence_batch
                FROM {table} AS source
               WHERE source.org_id IS NULL OR source.project_id IS NULL;
              GET DIAGNOSTICS copied_count = ROW_COUNT;

              DELETE FROM {table}
               WHERE org_id IS NULL OR project_id IS NULL;
              GET DIAGNOSTICS removed_count = ROW_COUNT;
              IF copied_count <> expected_count OR removed_count <> expected_count THEN
                RAISE EXCEPTION
                  'TI-4 D7 quarantine mismatch for {table}: expected %, copied %, removed %',
                  expected_count, copied_count, removed_count;
              END IF;
            END
            $move$;
            """
        )

    for table, primary_key in SCOPED_PRIMARY_KEYS.items():
        op.execute(f"ALTER TABLE {table} ALTER COLUMN org_id SET NOT NULL")
        op.execute(f"ALTER TABLE {table} ALTER COLUMN project_id SET NOT NULL")
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {table}_pkey")
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {table}_pkey "
            f"PRIMARY KEY ({_columns(primary_key)})"
        )

    for child, constraint, child_key, parent, parent_key in PARENT_FOREIGN_KEYS:
        op.execute(
            f"ALTER TABLE {child} ADD CONSTRAINT {constraint} "
            f"FOREIGN KEY (org_id, project_id, {child_key}) "
            f"REFERENCES {parent}(org_id, project_id, {parent_key})"
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
            f"active.{column}::text = quarantined.source_key->>'{column}'"
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
        "RAISE EXCEPTION 'TI-4 D7 downgrade blocked by legacy key collision' "
        "USING ERRCODE='23505'; END IF; END $contract$;"
    )

    for child, constraint, _, _, _ in reversed(PARENT_FOREIGN_KEYS):
        op.execute(f"ALTER TABLE {child} DROP CONSTRAINT {constraint}")
    for table in reversed(tuple(SCOPED_PRIMARY_KEYS)):
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {table}_pkey")
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {table}_pkey "
            f"PRIMARY KEY ({_columns(LEGACY_PRIMARY_KEYS[table])})"
        )
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
    op.execute("DROP FUNCTION guard_data_os_quarantine_immutable()")
