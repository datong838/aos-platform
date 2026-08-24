"""Add W3-13 ecommerce analyst canonical authorities.

Revision ID: w3_018
Revises: w3_017
Create Date: 2026-08-25
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "w3_018"
down_revision: str | Sequence[str] | None = "w3_017"
branch_labels = None
depends_on = None

KINDS = ("insight", "decision", "growth_plan", "task_graph", "effect_review")
HEADS = (
    "ecommerce_analyst_insight_head",
    "ecommerce_analyst_decision_head",
    "ecommerce_analyst_growth_plan_head",
    "ecommerce_analyst_task_graph_head",
    "ecommerce_analyst_effect_review_head",
)
REVISIONS = (
    "ecommerce_analyst_insight_revision",
    "ecommerce_analyst_decision_revision",
    "ecommerce_analyst_growth_plan_revision",
    "ecommerce_analyst_task_graph_revision",
    "ecommerce_analyst_effect_review_revision",
)
TABLES = HEADS + REVISIONS + ("ecommerce_analyst_authority_receipt",)
IDENTITIES = {
    "insight": "insight_id",
    "decision": "decision_id",
    "growth_plan": "plan_id",
    "task_graph": "graph_id",
    "effect_review": "review_id",
}


def _protect(name: str, *, mutable: bool) -> None:
    op.execute(f"ALTER TABLE {name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {name} FORCE ROW LEVEL SECURITY")
    op.execute(f"""CREATE POLICY tenant_scope_{name}_w3_018 ON {name} TO aos_runtime
        USING (org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))
        WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
    if mutable:
        op.execute(f"GRANT SELECT,INSERT,UPDATE ON {name} TO aos_runtime")
        op.execute(f"REVOKE DELETE,TRUNCATE ON {name} FROM aos_runtime")
    else:
        op.execute(f"GRANT SELECT,INSERT ON {name} TO aos_runtime")
        op.execute(f"REVOKE UPDATE,DELETE,TRUNCATE ON {name} FROM aos_runtime")
        op.execute(f"CREATE TRIGGER trg_{name}_append_only_w3_018 BEFORE UPDATE OR DELETE ON {name} FOR EACH ROW EXECUTE FUNCTION guard_aip4_append_only()")
        op.execute(f"CREATE TRIGGER trg_{name}_truncate_guard_w3_018 BEFORE TRUNCATE ON {name} FOR EACH STATEMENT EXECUTE FUNCTION guard_aip4_append_only()")


def upgrade() -> None:
    for kind in KINDS:
        identity = IDENTITIES[kind]
        op.execute(f"""CREATE TABLE ecommerce_analyst_{kind}_head (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, {identity} TEXT NOT NULL,
          current_revision BIGINT NOT NULL, version BIGINT NOT NULL DEFAULT 1,
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,{identity}), CHECK(current_revision>=1), CHECK(version>=1))""")
        op.execute(f"""CREATE TABLE ecommerce_analyst_{kind}_revision (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, {identity} TEXT NOT NULL,
          revision BIGINT NOT NULL, parent_revision BIGINT, content_hash CHAR(64) NOT NULL,
          receipt_id TEXT NOT NULL, payload JSONB NOT NULL, created_by TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,{identity},revision), UNIQUE(org_id,project_id,receipt_id),
          CHECK(revision>=1), CHECK((revision=1 AND parent_revision IS NULL) OR (revision>1 AND parent_revision=revision-1)),
          CHECK(content_hash ~ '^[0-9a-f]{{64}}$'), CHECK(jsonb_typeof(payload)='object'))""")
    op.execute("""CREATE TABLE ecommerce_analyst_authority_receipt (
      org_id TEXT NOT NULL, project_id TEXT NOT NULL, receipt_id TEXT NOT NULL,
      operation TEXT NOT NULL, idempotency_key TEXT NOT NULL, request_hash CHAR(64) NOT NULL,
      result_ref JSONB NOT NULL, created_by TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY(org_id,project_id,receipt_id), UNIQUE(org_id,project_id,operation,idempotency_key),
      CHECK(operation ~ '^analyst[.][a-z_]+$'), CHECK(request_hash ~ '^[0-9a-f]{64}$'),
      CHECK(jsonb_typeof(result_ref)='object'))""")
    for table in TABLES:
        _protect(table, mutable=table in HEADS)


def downgrade() -> None:
    nonempty = " OR ".join(f"EXISTS (SELECT 1 FROM {table} LIMIT 1)" for table in TABLES)
    op.execute(f"""DO $$ BEGIN IF {nonempty} THEN RAISE EXCEPTION 'cannot downgrade w3_018 with canonical analyst data' USING ERRCODE='55000'; END IF; END $$""")
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE {table} CASCADE")
