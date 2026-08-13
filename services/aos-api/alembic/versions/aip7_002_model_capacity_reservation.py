"""Add AIP-7 exact model capacity pool and reservation authority.

Revision ID: aip7_002
Revises: w2_002
Create Date: 2026-08-14
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "aip7_002"
down_revision: str | Sequence[str] | None = "w2_002"
branch_labels = None
depends_on = None

TABLES = (
    "aip_model_price_snapshot_head",
    "aip_model_price_snapshot_revision",
    "aip_model_capacity_pool_head",
    "aip_model_capacity_pool_revision",
    "aip_model_capacity_reservation",
    "aip_model_capacity_event",
)


def _tenant_table(name: str, *, mutable: bool) -> None:
    op.execute(f"ALTER TABLE {name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {name} FORCE ROW LEVEL SECURITY")
    op.execute(f"""CREATE POLICY tenant_scope_{name}_aip7 ON {name} TO aos_runtime
        USING (org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))
        WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
    grant = "SELECT,INSERT,UPDATE" if mutable else "SELECT,INSERT"
    op.execute(f"GRANT {grant} ON {name} TO aos_runtime")


def _append_only(name: str) -> None:
    op.execute(f"""CREATE TRIGGER trg_{name}_append_only
        BEFORE UPDATE OR DELETE ON {name}
        FOR EACH ROW EXECUTE FUNCTION guard_aip4_append_only()""")
    op.execute(f"""CREATE TRIGGER trg_{name}_truncate_guard
        BEFORE TRUNCATE ON {name}
        FOR EACH STATEMENT EXECUTE FUNCTION guard_aip4_append_only()""")


def upgrade() -> None:
    op.execute("""CREATE TABLE aip_model_price_snapshot_head (
      org_id TEXT NOT NULL, project_id TEXT NOT NULL, model_price_snapshot_id TEXT NOT NULL,
      current_revision BIGINT NOT NULL, version BIGINT NOT NULL DEFAULT 1,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY(org_id,project_id,model_price_snapshot_id),
      CHECK(current_revision>=1), CHECK(version>=1))""")
    op.execute("""CREATE TABLE aip_model_price_snapshot_revision (
      org_id TEXT NOT NULL, project_id TEXT NOT NULL, model_price_snapshot_id TEXT NOT NULL,
      revision BIGINT NOT NULL, content_hash TEXT NOT NULL, lifecycle TEXT NOT NULL,
      payload JSONB NOT NULL, created_by TEXT NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY(org_id,project_id,model_price_snapshot_id,revision),
      UNIQUE(org_id,project_id,model_price_snapshot_id,content_hash),
      CHECK(revision>=1), CHECK(content_hash ~ '^[0-9a-f]{64}$'),
      CHECK(lifecycle IN ('draft','validated','active','suspended','revoked')),
      CHECK(jsonb_typeof(payload)='object'),
      FOREIGN KEY(org_id,project_id,model_price_snapshot_id)
        REFERENCES aip_model_price_snapshot_head(org_id,project_id,model_price_snapshot_id)
        DEFERRABLE INITIALLY DEFERRED)""")
    op.execute("""CREATE TABLE aip_model_capacity_pool_head (
      org_id TEXT NOT NULL, project_id TEXT NOT NULL, pool_id TEXT NOT NULL,
      current_revision BIGINT NOT NULL, version BIGINT NOT NULL DEFAULT 1,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY(org_id,project_id,pool_id),
      CHECK(current_revision>=1), CHECK(version>=1))""")
    op.execute("""CREATE TABLE aip_model_capacity_pool_revision (
      org_id TEXT NOT NULL, project_id TEXT NOT NULL, pool_id TEXT NOT NULL,
      revision BIGINT NOT NULL, content_hash TEXT NOT NULL,
      route_ref JSONB NOT NULL, model_ref JSONB NOT NULL, provider_ref JSONB NOT NULL,
      route_id TEXT NOT NULL, route_revision BIGINT NOT NULL, route_hash TEXT NOT NULL,
      model_id TEXT NOT NULL, model_revision BIGINT NOT NULL, model_hash TEXT NOT NULL,
      provider_id TEXT NOT NULL, provider_revision BIGINT NOT NULL, provider_hash TEXT NOT NULL,
      max_concurrency BIGINT NOT NULL, max_token_units BIGINT NOT NULL,
      token_unit_per_reservation BIGINT NOT NULL, lease_seconds BIGINT NOT NULL,
      lifecycle TEXT NOT NULL, created_by TEXT NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY(org_id,project_id,pool_id,revision),
      UNIQUE(org_id,project_id,pool_id,content_hash),
      CHECK(revision>=1), CHECK(content_hash ~ '^[0-9a-f]{64}$'),
      CHECK(route_revision>=1 AND model_revision>=1 AND provider_revision>=1),
      CHECK(route_hash ~ '^[0-9a-f]{64}$' AND model_hash ~ '^[0-9a-f]{64}$' AND provider_hash ~ '^[0-9a-f]{64}$'),
      CHECK(jsonb_typeof(route_ref)='object' AND jsonb_typeof(model_ref)='object' AND jsonb_typeof(provider_ref)='object'),
      CHECK(route_ref->>'assetType'='ModelRouteRevision' AND route_ref->>'assetId'=route_id
        AND (route_ref->>'revision')::BIGINT=route_revision AND route_ref->>'contentHash'=route_hash),
      CHECK(model_ref->>'assetType'='RegisteredModelRevision' AND model_ref->>'assetId'=model_id
        AND (model_ref->>'revision')::BIGINT=model_revision AND model_ref->>'contentHash'=model_hash),
      CHECK(provider_ref->>'assetType'='ProviderInstanceRevision' AND provider_ref->>'assetId'=provider_id
        AND (provider_ref->>'revision')::BIGINT=provider_revision AND provider_ref->>'contentHash'=provider_hash),
      CHECK(max_concurrency>0 AND max_token_units>0),
      CHECK(token_unit_per_reservation>0 AND token_unit_per_reservation<=max_token_units),
      CHECK(lease_seconds BETWEEN 1 AND 86400),
      CHECK(lifecycle IN ('draft','active','suspended','revoked')),
      FOREIGN KEY(org_id,project_id,pool_id) REFERENCES aip_model_capacity_pool_head(org_id,project_id,pool_id)
        DEFERRABLE INITIALLY DEFERRED)""")
    op.execute("""CREATE UNIQUE INDEX aip_model_capacity_one_active_exact_idx
      ON aip_model_capacity_pool_revision(
        org_id,project_id,route_id,route_revision,route_hash,
        model_id,model_revision,model_hash,provider_id,provider_revision,provider_hash)
      WHERE lifecycle='active'""")
    op.execute("""CREATE TABLE aip_model_capacity_reservation (
      org_id TEXT NOT NULL, project_id TEXT NOT NULL, reservation_id TEXT NOT NULL,
      pool_id TEXT NOT NULL, pool_revision BIGINT NOT NULL, agent_run_id TEXT NOT NULL,
      request_hash TEXT NOT NULL, request_units BIGINT NOT NULL, token_units BIGINT NOT NULL,
      status TEXT NOT NULL, expires_at TIMESTAMPTZ NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY(org_id,project_id,reservation_id),
      UNIQUE(org_id,project_id,agent_run_id),
      CHECK(request_hash ~ '^[0-9a-f]{64}$'),
      CHECK(request_units>0 AND token_units>0),
      CHECK(status IN ('reserved','consumed','released','expired')),
      CHECK(expires_at>created_at),
      FOREIGN KEY(org_id,project_id,pool_id,pool_revision)
        REFERENCES aip_model_capacity_pool_revision(org_id,project_id,pool_id,revision))""")
    op.execute("""CREATE TABLE aip_model_capacity_event (
      org_id TEXT NOT NULL, project_id TEXT NOT NULL, event_id TEXT NOT NULL,
      reservation_id TEXT NOT NULL, event_type TEXT NOT NULL,
      occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY(org_id,project_id,event_id),
      CHECK(event_type IN ('reserved','consumed','released','expired')),
      FOREIGN KEY(org_id,project_id,reservation_id)
        REFERENCES aip_model_capacity_reservation(org_id,project_id,reservation_id))""")
    op.execute("""CREATE FUNCTION guard_aip7_capacity_reservation_identity() RETURNS trigger
      LANGUAGE plpgsql AS $$ BEGIN
        IF ROW(NEW.org_id,NEW.project_id,NEW.reservation_id,NEW.pool_id,NEW.pool_revision,
               NEW.agent_run_id,NEW.request_hash,NEW.request_units,NEW.token_units,NEW.created_at)
           IS DISTINCT FROM
           ROW(OLD.org_id,OLD.project_id,OLD.reservation_id,OLD.pool_id,OLD.pool_revision,
               OLD.agent_run_id,OLD.request_hash,OLD.request_units,OLD.token_units,OLD.created_at)
        THEN RAISE EXCEPTION 'capacity reservation identity is immutable'; END IF;
        RETURN NEW;
      END $$""")
    op.execute("""CREATE TRIGGER trg_aip_model_capacity_reservation_identity
      BEFORE UPDATE ON aip_model_capacity_reservation
      FOR EACH ROW EXECUTE FUNCTION guard_aip7_capacity_reservation_identity()""")
    for table in TABLES:
        _tenant_table(
            table,
            mutable=table in {"aip_model_price_snapshot_head", "aip_model_capacity_pool_head", "aip_model_capacity_reservation"},
        )
    _append_only("aip_model_price_snapshot_revision")
    _append_only("aip_model_capacity_pool_revision")
    _append_only("aip_model_capacity_event")
    op.execute("""CREATE INDEX aip_model_capacity_active_reservation_idx
      ON aip_model_capacity_reservation(org_id,project_id,pool_id,pool_revision,expires_at)
      WHERE status IN ('reserved','consumed')""")
    op.execute("""CREATE INDEX aip_model_capacity_event_order_idx
      ON aip_model_capacity_event(org_id,project_id,reservation_id,occurred_at,event_id)""")


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
    op.execute("DROP FUNCTION IF EXISTS guard_aip7_capacity_reservation_identity() CASCADE")
