"""Add W2-B eval contract and responsibility plan authority.

Revision ID: w2_002
Revises: aip7_001
Create Date: 2026-08-13
"""
from __future__ import annotations

from collections.abc import Sequence
from alembic import op

revision: str = "w2_002"
down_revision: str | Sequence[str] | None = "aip7_001"
branch_labels = None
depends_on = None

TABLES = (
    "aip_eval_contract_head",
    "aip_eval_contract_revision",
    "aip_responsibility_plan_head",
    "aip_responsibility_plan_revision",
)


def _tenant_table(name: str, *, mutable: bool) -> None:
    op.execute(f"ALTER TABLE {name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {name} FORCE ROW LEVEL SECURITY")
    op.execute(f"""CREATE POLICY tenant_scope_{name}_w2 ON {name} TO aos_runtime
        USING (org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))
        WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
    grant = "SELECT,INSERT,UPDATE" if mutable else "SELECT,INSERT"
    op.execute(f"GRANT {grant} ON {name} TO aos_runtime")


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


def _head(name: str, id_column: str) -> None:
    op.execute(f"""CREATE TABLE {name} (
      org_id TEXT NOT NULL, project_id TEXT NOT NULL, {id_column} TEXT NOT NULL,
      current_revision BIGINT NOT NULL, version BIGINT NOT NULL DEFAULT 1,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY(org_id,project_id,{id_column}),
      CHECK(current_revision>=1), CHECK(version>=1),
      FOREIGN KEY(org_id,project_id) REFERENCES twa_workspace(org_id,project_id))""")


def upgrade() -> None:
    _head("aip_eval_contract_head", "contract_id")
    op.execute("""CREATE TABLE aip_eval_contract_revision (
      org_id TEXT NOT NULL, project_id TEXT NOT NULL, contract_id TEXT NOT NULL, revision BIGINT NOT NULL,
      suite_ref JSONB NOT NULL, publication_ref JSONB, release_gate_ref JSONB,
      artifact_schema_ref JSONB NOT NULL, severity_thresholds JSONB NOT NULL,
      gate_policy JSONB NOT NULL, return_mapping JSONB NOT NULL, override_policy JSONB NOT NULL,
      content_hash TEXT NOT NULL, lifecycle TEXT NOT NULL, created_by TEXT NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY(org_id,project_id,contract_id,revision),
      CHECK(revision>=1), CHECK(content_hash ~ '^[0-9a-f]{64}$'),
      CHECK(lifecycle IN ('draft','frozen','withdrawn','superseded')),
      CHECK(jsonb_typeof(suite_ref)='object'), CHECK(jsonb_typeof(artifact_schema_ref)='object'),
      CHECK(jsonb_typeof(severity_thresholds)='object'), CHECK(jsonb_typeof(gate_policy)='object'),
      CHECK(jsonb_typeof(return_mapping)='object'), CHECK(jsonb_typeof(override_policy)='object'),
      FOREIGN KEY(org_id,project_id,contract_id) REFERENCES aip_eval_contract_head(org_id,project_id,contract_id)
        DEFERRABLE INITIALLY DEFERRED)""")
    _head("aip_responsibility_plan_head", "plan_id")
    op.execute("""CREATE TABLE aip_responsibility_plan_revision (
      org_id TEXT NOT NULL, project_id TEXT NOT NULL, plan_id TEXT NOT NULL, revision BIGINT NOT NULL,
      profile TEXT NOT NULL, template_ref JSONB NOT NULL, slots JSONB NOT NULL, merge_decisions JSONB NOT NULL,
      content_hash TEXT NOT NULL, lifecycle TEXT NOT NULL, created_by TEXT NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY(org_id,project_id,plan_id,revision),
      CHECK(revision>=1), CHECK(content_hash ~ '^[0-9a-f]{64}$'),
      CHECK(lifecycle IN ('draft','frozen','withdrawn','superseded')),
      CHECK(jsonb_typeof(template_ref)='object'),
      CHECK(jsonb_typeof(slots)='array' AND jsonb_array_length(slots)>0),
      CHECK(jsonb_typeof(merge_decisions)='array'),
      FOREIGN KEY(org_id,project_id,plan_id) REFERENCES aip_responsibility_plan_head(org_id,project_id,plan_id)
        DEFERRABLE INITIALLY DEFERRED)""")
    for table in TABLES:
        _tenant_table(table, mutable=table.endswith("_head"))
    _append_only("aip_eval_contract_revision")
    _append_only("aip_responsibility_plan_revision")
    op.execute("CREATE INDEX aip_eval_contract_updated_idx ON aip_eval_contract_head(org_id,project_id,updated_at DESC,contract_id)")
    op.execute("CREATE INDEX aip_responsibility_plan_updated_idx ON aip_responsibility_plan_head(org_id,project_id,updated_at DESC,plan_id)")


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
