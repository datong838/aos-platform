"""Add canonical tenant-scoped AIP BudgetRevision authority.

Revision ID: aip10_001
Revises: aip9_002
Create Date: 2026-08-17
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "aip10_001"
down_revision: str | Sequence[str] | None = "aip9_002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TABLES = ("aip_budget_head", "aip_budget_revision", "aip_budget_receipt")


def _tenant_table(name: str, *, mutable: bool) -> None:
    op.execute(f"ALTER TABLE {name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {name} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""CREATE POLICY tenant_scope_{name}_aip10 ON {name} TO aos_runtime
        USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
          AND project_id=NULLIF(current_setting('aos.project_id',true),''))
        WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
          AND project_id=NULLIF(current_setting('aos.project_id',true),''))"""
    )
    grant = "SELECT,INSERT,UPDATE" if mutable else "SELECT,INSERT"
    op.execute(f"GRANT {grant} ON {name} TO aos_runtime")
    if mutable:
        op.execute(f"REVOKE DELETE,TRUNCATE ON {name} FROM aos_runtime")
    else:
        op.execute(f"REVOKE UPDATE,DELETE,TRUNCATE ON {name} FROM aos_runtime")


def _append_only(name: str) -> None:
    op.execute(
        f"""CREATE TRIGGER trg_{name}_append_only
        BEFORE UPDATE OR DELETE ON {name}
        FOR EACH ROW EXECUTE FUNCTION guard_aip4_append_only()"""
    )
    op.execute(
        f"""CREATE TRIGGER trg_{name}_truncate_guard
        BEFORE TRUNCATE ON {name}
        FOR EACH STATEMENT EXECUTE FUNCTION guard_aip4_append_only()"""
    )


def upgrade() -> None:
    op.execute(
        """CREATE TABLE aip_budget_head (
        org_id TEXT NOT NULL, project_id TEXT NOT NULL, budget_id TEXT NOT NULL,
        current_revision BIGINT NOT NULL, version BIGINT NOT NULL DEFAULT 1,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY(org_id,project_id,budget_id),
        CHECK(current_revision>=1), CHECK(version>=1))"""
    )
    op.execute(
        """CREATE TABLE aip_budget_revision (
        org_id TEXT NOT NULL, project_id TEXT NOT NULL, budget_id TEXT NOT NULL,
        revision BIGINT NOT NULL, content_hash TEXT NOT NULL, lifecycle TEXT NOT NULL,
        environment TEXT NOT NULL, currency TEXT NOT NULL,
        daily_limit_minor BIGINT NOT NULL, monthly_limit_minor BIGINT NOT NULL,
        alert_threshold_pct BIGINT NOT NULL, hard_stop BOOLEAN NOT NULL,
        unknown_usage_behavior TEXT NOT NULL,
        effective_from TIMESTAMPTZ NOT NULL, effective_until TIMESTAMPTZ NOT NULL,
        owner TEXT NOT NULL, over_budget_approver TEXT NOT NULL,
        payload JSONB NOT NULL, created_by TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY(org_id,project_id,budget_id,revision),
        UNIQUE(org_id,project_id,budget_id,content_hash),
        CHECK(revision>=1), CHECK(content_hash ~ '^[0-9a-f]{64}$'),
        CHECK(lifecycle IN ('draft','active','suspended','revoked','expired')),
        CHECK(environment='development'), CHECK(currency='CNY'),
        CHECK(daily_limit_minor>0 AND monthly_limit_minor>=daily_limit_minor),
        CHECK(alert_threshold_pct BETWEEN 1 AND 100), CHECK(hard_stop),
        CHECK(unknown_usage_behavior='block'), CHECK(effective_until>effective_from),
        CHECK(jsonb_typeof(payload)='object'),
        FOREIGN KEY(org_id,project_id,budget_id)
          REFERENCES aip_budget_head(org_id,project_id,budget_id)
          DEFERRABLE INITIALLY DEFERRED)"""
    )
    op.execute(
        """CREATE TABLE aip_budget_receipt (
        org_id TEXT NOT NULL, project_id TEXT NOT NULL, receipt_id TEXT NOT NULL,
        operation TEXT NOT NULL, idempotency_key TEXT NOT NULL,
        request_hash TEXT NOT NULL, result_ref JSONB NOT NULL,
        created_by TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY(org_id,project_id,receipt_id),
        UNIQUE(org_id,project_id,operation,idempotency_key),
        CHECK(request_hash ~ '^[0-9a-f]{64}$'),
        CHECK(jsonb_typeof(result_ref)='object'))"""
    )
    for table in TABLES:
        _tenant_table(table, mutable=table == "aip_budget_head")
    _append_only("aip_budget_revision")
    _append_only("aip_budget_receipt")
    op.execute(
        "CREATE INDEX aip_budget_effective_idx ON aip_budget_revision"
        "(org_id,project_id,lifecycle,effective_until)"
    )


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
