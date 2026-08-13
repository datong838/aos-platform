"""Add AIP-7 immutable model runtime authority.

Revision ID: aip7_001
Revises: w2_001
Create Date: 2026-08-13
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "aip7_001"
down_revision: str | Sequence[str] | None = "w2_001"
branch_labels = None
depends_on = None

KINDS = ("provider_instance", "registered_model", "runtime_policy", "model_route")
TABLES = tuple(
    table
    for kind in KINDS
    for table in (f"aip_{kind}_head", f"aip_{kind}_revision")
) + ("aip_provider_health_observation", "aip_model_runtime_receipt")


def _tenant_table(name: str, *, mutable: bool = True) -> None:
    op.execute(f"ALTER TABLE {name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {name} FORCE ROW LEVEL SECURITY")
    op.execute(f"""CREATE POLICY tenant_scope_{name}_aip7 ON {name} TO aos_runtime
        USING (org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))
        WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
    grant = "SELECT,INSERT,UPDATE" if mutable else "SELECT,INSERT"
    op.execute(f"GRANT {grant} ON {name} TO aos_runtime")


def _authority(kind: str) -> None:
    id_column = f"{kind}_id"
    head = f"aip_{kind}_head"
    revision_table = f"aip_{kind}_revision"
    op.execute(f"""CREATE TABLE {head} (
      org_id TEXT NOT NULL, project_id TEXT NOT NULL, {id_column} TEXT NOT NULL,
      current_revision BIGINT NOT NULL, version BIGINT NOT NULL DEFAULT 1,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY(org_id,project_id,{id_column}),
      CHECK(current_revision>=1), CHECK(version>=1))""")
    op.execute(f"""CREATE TABLE {revision_table} (
      org_id TEXT NOT NULL, project_id TEXT NOT NULL, {id_column} TEXT NOT NULL,
      revision BIGINT NOT NULL, content_hash TEXT NOT NULL, lifecycle TEXT NOT NULL,
      payload JSONB NOT NULL, created_by TEXT NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY(org_id,project_id,{id_column},revision),
      UNIQUE(org_id,project_id,{id_column},content_hash),
      CHECK(revision>=1), CHECK(content_hash ~ '^[0-9a-f]{{64}}$'),
      CHECK(lifecycle IN ('draft','validated','active','suspended','revoked')),
      CHECK(jsonb_typeof(payload)='object'),
      FOREIGN KEY(org_id,project_id,{id_column}) REFERENCES {head}(org_id,project_id,{id_column})
        DEFERRABLE INITIALLY DEFERRED)""")


def upgrade() -> None:
    for kind in KINDS:
        _authority(kind)
    op.execute("""CREATE TABLE aip_provider_health_observation (
      org_id TEXT NOT NULL, project_id TEXT NOT NULL, observation_id TEXT NOT NULL,
      provider_ref JSONB NOT NULL, status TEXT NOT NULL, availability_pct DOUBLE PRECISION,
      p50_latency_ms BIGINT, observed_at TIMESTAMPTZ NOT NULL, expires_at TIMESTAMPTZ NOT NULL,
      recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY(org_id,project_id,observation_id),
      CHECK(status IN ('healthy','degraded','unavailable','unknown')),
      CHECK(availability_pct IS NULL OR (availability_pct>=0 AND availability_pct<=100)),
      CHECK(p50_latency_ms IS NULL OR p50_latency_ms>=0), CHECK(expires_at>observed_at),
      CHECK(jsonb_typeof(provider_ref)='object'))""")
    op.execute("""CREATE TABLE aip_model_runtime_receipt (
      org_id TEXT NOT NULL, project_id TEXT NOT NULL, receipt_id TEXT NOT NULL,
      operation TEXT NOT NULL, idempotency_key TEXT NOT NULL, request_hash TEXT NOT NULL,
      result_ref JSONB NOT NULL, created_by TEXT NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY(org_id,project_id,receipt_id),
      UNIQUE(org_id,project_id,operation,idempotency_key),
      CHECK(request_hash ~ '^[0-9a-f]{64}$'), CHECK(jsonb_typeof(result_ref)='object'))""")
    for table in TABLES:
        _tenant_table(table, mutable=table.endswith("_head"))
    op.execute("CREATE INDEX aip_provider_health_expiry_idx ON aip_provider_health_observation(org_id,project_id,expires_at DESC)")


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
