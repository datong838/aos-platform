"""Add immutable AIP capability catalog authority.

Revision ID: aip6_004
Revises: aip6_003
Create Date: 2026-08-13
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "aip6_004"
down_revision: str | Sequence[str] | None = "aip6_003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """CREATE TABLE aip_capability_revision (
          capability_id TEXT NOT NULL, revision BIGINT NOT NULL,
          display_name TEXT NOT NULL, lifecycle TEXT NOT NULL,
          parent_ref JSONB, aliases JSONB NOT NULL,
          input_schema_ref JSONB NOT NULL, output_schema_ref JSONB NOT NULL,
          risk_level TEXT NOT NULL, required_data_refs JSONB NOT NULL,
          required_tool_refs JSONB NOT NULL, required_capability_refs JSONB NOT NULL,
          eval_pack_ref JSONB, memory_policy_ref JSONB NOT NULL,
          handoff_policy_ref JSONB NOT NULL, effect_review_schema_ref JSONB NOT NULL,
          license_policy_ref JSONB NOT NULL, readiness_policy_ref JSONB NOT NULL,
          readiness TEXT NOT NULL, readiness_reasons JSONB NOT NULL,
          source_ref JSONB NOT NULL, source_license TEXT NOT NULL,
          content_hash TEXT NOT NULL, created_by TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (capability_id,revision),
          UNIQUE (capability_id,content_hash),
          CHECK (revision >= 1), CHECK (content_hash ~ '^[0-9a-f]{64}$'),
          CHECK (lifecycle IN ('draft','evaluated','published','deprecated','revoked')),
          CHECK (risk_level IN ('low','medium','high','critical')),
          CHECK (readiness IN ('available','degraded','disabled','blocked','unknown')),
          CHECK (jsonb_typeof(aliases)='array'),
          CHECK (jsonb_typeof(input_schema_ref)='object'),
          CHECK (jsonb_typeof(output_schema_ref)='object'),
          CHECK (jsonb_typeof(required_data_refs)='array'),
          CHECK (jsonb_typeof(required_tool_refs)='array'),
          CHECK (jsonb_typeof(required_capability_refs)='array'),
          CHECK (jsonb_typeof(readiness_reasons)='array'),
          CHECK (jsonb_typeof(source_ref)='object')
        )"""
    )
    op.execute(
        """CREATE TABLE aip_capability_alias (
          alias TEXT PRIMARY KEY, capability_id TEXT NOT NULL,
          capability_revision BIGINT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          CHECK (length(btrim(alias)) > 0),
          FOREIGN KEY (capability_id,capability_revision)
            REFERENCES aip_capability_revision(capability_id,revision)
        )"""
    )
    for table in ("aip_capability_revision", "aip_capability_alias"):
        op.execute(
            f"""CREATE TRIGGER trg_{table}_append_only
            BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION guard_aip6_registry_append_only()"""
        )
        op.execute(
            f"""CREATE TRIGGER trg_{table}_truncate_guard
            BEFORE TRUNCATE ON {table}
            FOR EACH STATEMENT EXECUTE FUNCTION guard_aip6_registry_append_only()"""
        )
        op.execute(f"REVOKE ALL ON {table} FROM aos_runtime")
        op.execute(f"GRANT SELECT ON {table} TO aos_runtime")


def downgrade() -> None:
    op.execute("REVOKE SELECT ON aip_capability_alias FROM aos_runtime")
    op.execute("REVOKE SELECT ON aip_capability_revision FROM aos_runtime")
    op.execute("DROP TABLE IF EXISTS aip_capability_alias")
    op.execute("DROP TABLE IF EXISTS aip_capability_revision")
