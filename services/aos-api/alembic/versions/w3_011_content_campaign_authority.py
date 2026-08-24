"""Add tenant-safe content and campaign canonical authorities.

Revision ID: w3_011
Revises: d0_after_001
Create Date: 2026-08-24
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "w3_011"
down_revision: str | Sequence[str] | None = "d0_after_001"
branch_labels = None
depends_on = None


TABLES = (
    "ecommerce_campaign_head",
    "ecommerce_campaign_revision",
    "ecommerce_content_calendar_head",
    "ecommerce_content_calendar_entry_revision",
    "ecommerce_content_calendar_decision_revision",
    "ecommerce_master_content_intent_head",
    "ecommerce_master_content_intent_revision",
    "ecommerce_content_campaign_authority_receipt",
)
MUTABLE_HEAD_TABLES = {
    "ecommerce_campaign_head",
    "ecommerce_content_calendar_head",
    "ecommerce_master_content_intent_head",
}
APPEND_ONLY_TABLES = tuple(
    table for table in TABLES if table not in MUTABLE_HEAD_TABLES
)


def _tenant_security(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""CREATE POLICY tenant_scope_{table}_w3_011 ON {table} TO aos_runtime
        USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
          AND project_id=NULLIF(current_setting('aos.project_id',true),''))
        WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
          AND project_id=NULLIF(current_setting('aos.project_id',true),''))"""
    )
    if table in MUTABLE_HEAD_TABLES:
        op.execute(f"GRANT SELECT,INSERT,UPDATE ON {table} TO aos_runtime")
        op.execute(f"REVOKE DELETE,TRUNCATE ON {table} FROM aos_runtime")
        return
    op.execute(f"GRANT SELECT,INSERT ON {table} TO aos_runtime")
    op.execute(f"REVOKE UPDATE,DELETE,TRUNCATE ON {table} FROM aos_runtime")
    op.execute(
        f"""CREATE TRIGGER trg_{table}_append_only
        BEFORE UPDATE OR DELETE ON {table}
        FOR EACH ROW EXECUTE FUNCTION guard_aip4_append_only()"""
    )
    op.execute(
        f"""CREATE TRIGGER trg_{table}_truncate_guard
        BEFORE TRUNCATE ON {table}
        FOR EACH STATEMENT EXECUTE FUNCTION guard_aip4_append_only()"""
    )


def _head(table: str, identity: str) -> None:
    op.execute(
        f"""CREATE TABLE {table} (
        org_id TEXT NOT NULL, project_id TEXT NOT NULL, {identity} TEXT NOT NULL,
        current_revision BIGINT NOT NULL, version BIGINT NOT NULL DEFAULT 1,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY(org_id,project_id,{identity}),
        CHECK(current_revision>=1), CHECK(version>=1))"""
    )


def _revision(table: str, identity: str, *, extra: str = "") -> None:
    op.execute(
        f"""CREATE TABLE {table} (
        org_id TEXT NOT NULL, project_id TEXT NOT NULL, {identity} TEXT NOT NULL,
        revision BIGINT NOT NULL, parent_revision BIGINT,
        content_hash TEXT NOT NULL, receipt_id TEXT NOT NULL, authority_data JSONB NOT NULL,
        created_by TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(){extra},
        PRIMARY KEY(org_id,project_id,{identity},revision),
        UNIQUE(org_id,project_id,receipt_id),
        CHECK(revision>=1),
        CHECK((revision=1 AND parent_revision IS NULL)
          OR (revision>1 AND parent_revision=revision-1)),
        CHECK(content_hash ~ '^[0-9a-f]{{64}}$'),
        CHECK(jsonb_typeof(authority_data)='object'))"""
    )


def upgrade() -> None:
    _head("ecommerce_campaign_head", "campaign_id")
    _revision("ecommerce_campaign_revision", "campaign_id")
    _head("ecommerce_content_calendar_head", "entry_id")
    _revision(
        "ecommerce_content_calendar_entry_revision",
        "entry_id",
        extra=(
            ", timezone TEXT NOT NULL, resolved_start TIMESTAMPTZ NOT NULL, "
            "resolved_end TIMESTAMPTZ NOT NULL, CHECK(resolved_start<resolved_end)"
        ),
    )
    _revision(
        "ecommerce_content_calendar_decision_revision",
        "decision_id",
        extra=", entry_id TEXT NOT NULL",
    )
    _head("ecommerce_master_content_intent_head", "intent_id")
    _revision("ecommerce_master_content_intent_revision", "intent_id")
    op.execute(
        """CREATE TABLE ecommerce_content_campaign_authority_receipt (
        org_id TEXT NOT NULL, project_id TEXT NOT NULL, receipt_id TEXT NOT NULL,
        operation TEXT NOT NULL, idempotency_key TEXT NOT NULL,
        request_hash TEXT NOT NULL, result_ref JSONB NOT NULL,
        created_by TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY(org_id,project_id,receipt_id),
        UNIQUE(org_id,project_id,operation,idempotency_key),
        CHECK(operation ~ '^content_campaign[.][a-z_]+$'),
        CHECK(request_hash ~ '^[0-9a-f]{64}$'),
        CHECK(jsonb_typeof(result_ref)='object'))"""
    )
    for table in TABLES:
        _tenant_security(table)
    op.execute(
        "CREATE INDEX ecommerce_content_calendar_window_idx ON "
        "ecommerce_content_calendar_entry_revision"
        "(org_id,project_id,resolved_start,resolved_end,entry_id,revision)"
    )


def downgrade() -> None:
    nonempty = " OR ".join(
        f"EXISTS (SELECT 1 FROM {table} LIMIT 1)" for table in TABLES
    )
    op.execute(
        f"""DO $$ BEGIN
        IF {nonempty} THEN
          RAISE EXCEPTION 'cannot downgrade w3_011: canonical content campaign authority exists'
            USING ERRCODE = '55000';
        END IF;
        END $$"""
    )
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
