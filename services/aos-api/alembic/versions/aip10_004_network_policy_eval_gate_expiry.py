"""Add NetworkPolicy authority and fixed EvalGate expiry.

Revision ID: aip10_004
Revises: aip10_003
Create Date: 2026-08-17
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "aip10_004"
down_revision: str | Sequence[str] | None = "aip10_003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TABLES = (
    "aip_network_policy_head",
    "aip_network_policy_revision",
    "aip_network_policy_receipt",
)


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
        f"""CREATE TRIGGER trg_{name}_append_only BEFORE UPDATE OR DELETE ON {name}
        FOR EACH ROW EXECUTE FUNCTION guard_aip4_append_only()"""
    )
    op.execute(
        f"""CREATE TRIGGER trg_{name}_truncate_guard BEFORE TRUNCATE ON {name}
        FOR EACH STATEMENT EXECUTE FUNCTION guard_aip4_append_only()"""
    )


def upgrade() -> None:
    op.execute(
        """CREATE TABLE aip_network_policy_head (
        org_id TEXT NOT NULL, project_id TEXT NOT NULL, policy_id TEXT NOT NULL,
        current_revision BIGINT NOT NULL, version BIGINT NOT NULL DEFAULT 1,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY(org_id,project_id,policy_id),
        CHECK(current_revision>=1), CHECK(version>=1))"""
    )
    op.execute(
        """CREATE TABLE aip_network_policy_revision (
        org_id TEXT NOT NULL, project_id TEXT NOT NULL, policy_id TEXT NOT NULL,
        revision BIGINT NOT NULL, content_hash TEXT NOT NULL, lifecycle TEXT NOT NULL,
        effective_from TIMESTAMPTZ NOT NULL, effective_until TIMESTAMPTZ NOT NULL,
        payload JSONB NOT NULL, created_by TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY(org_id,project_id,policy_id,revision),
        UNIQUE(org_id,project_id,policy_id,content_hash),
        CHECK(revision>=1), CHECK(content_hash ~ '^[0-9a-f]{64}$'),
        CHECK(lifecycle IN ('draft','blocked','active','suspended','revoked','expired')),
        CHECK(effective_until>effective_from), CHECK(jsonb_typeof(payload)='object'),
        FOREIGN KEY(org_id,project_id,policy_id)
          REFERENCES aip_network_policy_head(org_id,project_id,policy_id)
          DEFERRABLE INITIALLY DEFERRED)"""
    )
    op.execute(
        """CREATE TABLE aip_network_policy_receipt (
        org_id TEXT NOT NULL, project_id TEXT NOT NULL, receipt_id TEXT NOT NULL,
        operation TEXT NOT NULL, idempotency_key TEXT NOT NULL,
        request_hash TEXT NOT NULL, result_ref JSONB NOT NULL,
        created_by TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY(org_id,project_id,receipt_id),
        UNIQUE(org_id,project_id,operation,idempotency_key),
        CHECK(request_hash ~ '^[0-9a-f]{64}$'), CHECK(jsonb_typeof(result_ref)='object'))"""
    )
    for table in TABLES:
        _tenant_table(table, mutable=table == "aip_network_policy_head")
    _append_only("aip_network_policy_revision")
    _append_only("aip_network_policy_receipt")
    op.execute(
        "CREATE INDEX aip_network_policy_effective_idx ON aip_network_policy_revision"
        "(org_id,project_id,lifecycle,effective_until)"
    )
    op.execute("ALTER TABLE aip_release_gate_decision ADD COLUMN expires_at TIMESTAMPTZ")
    op.execute("UPDATE aip_release_gate_decision SET expires_at=decided_at + INTERVAL '30 days'")
    op.execute("ALTER TABLE aip_release_gate_decision ALTER COLUMN expires_at SET NOT NULL")
    op.execute(
        "ALTER TABLE aip_release_gate_decision ADD CONSTRAINT aip_release_gate_expiry_after_decision "
        "CHECK(expires_at>decided_at)"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE aip_release_gate_decision DROP CONSTRAINT IF EXISTS "
        "aip_release_gate_expiry_after_decision"
    )
    op.execute("ALTER TABLE aip_release_gate_decision DROP COLUMN IF EXISTS expires_at")
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
