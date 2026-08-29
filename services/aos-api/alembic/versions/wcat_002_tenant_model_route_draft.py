"""Add tenant-bound, non-runtime model route draft authority.

Revision ID: wcat_002
Revises: wcat_001
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "wcat_002"
down_revision: str | Sequence[str] | None = "wcat_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""CREATE TABLE aip_model_route_draft(
      org_id text NOT NULL,
      project_id text NOT NULL,
      version integer NOT NULL CHECK(version >= 2),
      payload jsonb NOT NULL,
      updated_by text NOT NULL,
      updated_at timestamptz NOT NULL DEFAULT NOW(),
      PRIMARY KEY(org_id,project_id)
    )""")
    op.execute("ALTER TABLE aip_model_route_draft ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE aip_model_route_draft FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY tenant_scope_aip_model_route_draft_wcat_002
      ON aip_model_route_draft TO aos_runtime
      USING (org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))""")
    op.execute("GRANT SELECT ON aip_model_route_draft TO aos_runtime")
    op.execute("REVOKE INSERT,UPDATE,DELETE,TRUNCATE ON aip_model_route_draft FROM aos_runtime")
    op.execute("""CREATE FUNCTION aip_replace_model_route_draft(
      v_org text,v_project text,v_payload jsonb,v_expected integer,v_actor text
    ) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public AS $$
    DECLARE v_current integer; v_next integer;
    BEGIN
      IF v_org IS DISTINCT FROM current_setting('aos.org_id',true)
         OR v_project IS DISTINCT FROM current_setting('aos.project_id',true) THEN
        RAISE EXCEPTION 'tenant scope mismatch' USING ERRCODE='42501';
      END IF;
      SELECT version INTO v_current FROM aip_model_route_draft
        WHERE org_id=v_org AND project_id=v_project FOR UPDATE;
      IF v_current IS NULL THEN v_current := 1; END IF;
      IF v_expected <> v_current THEN
        RAISE EXCEPTION 'route draft version conflict: expected %, current %',v_expected,v_current USING ERRCODE='40001';
      END IF;
      v_next := v_current + 1;
      INSERT INTO aip_model_route_draft(org_id,project_id,version,payload,updated_by)
        VALUES(v_org,v_project,v_next,v_payload,v_actor)
      ON CONFLICT(org_id,project_id) DO UPDATE SET
        version=EXCLUDED.version,payload=EXCLUDED.payload,updated_by=EXCLUDED.updated_by,updated_at=NOW();
      RETURN jsonb_build_object('items',v_payload,'version',v_next,'updatedAt',NOW(),'activated',false);
    END $$""")
    op.execute("REVOKE ALL ON FUNCTION aip_replace_model_route_draft(text,text,jsonb,integer,text) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION aip_replace_model_route_draft(text,text,jsonb,integer,text) TO aos_runtime")
    op.execute("""CREATE TABLE aip_model_circuit_draft(
      org_id text NOT NULL,
      project_id text NOT NULL,
      version integer NOT NULL CHECK(version >= 2),
      payload jsonb NOT NULL,
      updated_by text NOT NULL,
      updated_at timestamptz NOT NULL DEFAULT NOW(),
      PRIMARY KEY(org_id,project_id)
    )""")
    op.execute("ALTER TABLE aip_model_circuit_draft ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE aip_model_circuit_draft FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY tenant_scope_aip_model_circuit_draft_wcat_002
      ON aip_model_circuit_draft TO aos_runtime
      USING (org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))""")
    op.execute("GRANT SELECT ON aip_model_circuit_draft TO aos_runtime")
    op.execute("REVOKE INSERT,UPDATE,DELETE,TRUNCATE ON aip_model_circuit_draft FROM aos_runtime")
    op.execute("""CREATE FUNCTION aip_replace_model_circuit_draft(
      v_org text,v_project text,v_payload jsonb,v_expected integer,v_actor text
    ) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public AS $$
    DECLARE v_current integer; v_next integer;
    BEGIN
      IF v_org IS DISTINCT FROM current_setting('aos.org_id',true)
         OR v_project IS DISTINCT FROM current_setting('aos.project_id',true) THEN
        RAISE EXCEPTION 'tenant scope mismatch' USING ERRCODE='42501';
      END IF;
      SELECT version INTO v_current FROM aip_model_circuit_draft
        WHERE org_id=v_org AND project_id=v_project FOR UPDATE;
      IF v_current IS NULL THEN v_current := 1; END IF;
      IF v_expected <> v_current THEN
        RAISE EXCEPTION 'circuit draft version conflict: expected %, current %',v_expected,v_current USING ERRCODE='40001';
      END IF;
      v_next := v_current + 1;
      INSERT INTO aip_model_circuit_draft(org_id,project_id,version,payload,updated_by)
        VALUES(v_org,v_project,v_next,v_payload,v_actor)
      ON CONFLICT(org_id,project_id) DO UPDATE SET
        version=EXCLUDED.version,payload=EXCLUDED.payload,updated_by=EXCLUDED.updated_by,updated_at=NOW();
      RETURN jsonb_build_object('config',v_payload,'version',v_next,'updatedAt',NOW(),'activated',false);
    END $$""")
    op.execute("REVOKE ALL ON FUNCTION aip_replace_model_circuit_draft(text,text,jsonb,integer,text) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION aip_replace_model_circuit_draft(text,text,jsonb,integer,text) TO aos_runtime")


def downgrade() -> None:
    op.execute("DROP FUNCTION aip_replace_model_circuit_draft(text,text,jsonb,integer,text)")
    op.execute("""DO $$ BEGIN IF EXISTS(SELECT 1 FROM aip_model_circuit_draft LIMIT 1)
      THEN RAISE EXCEPTION 'refuse downgrade: aip_model_circuit_draft is not empty'; END IF; END $$""")
    op.execute("DROP TABLE aip_model_circuit_draft")
    op.execute("DROP FUNCTION aip_replace_model_route_draft(text,text,jsonb,integer,text)")
    op.execute("""DO $$ BEGIN IF EXISTS(SELECT 1 FROM aip_model_route_draft LIMIT 1)
      THEN RAISE EXCEPTION 'refuse downgrade: aip_model_route_draft is not empty'; END IF; END $$""")
    op.execute("DROP TABLE aip_model_route_draft")
