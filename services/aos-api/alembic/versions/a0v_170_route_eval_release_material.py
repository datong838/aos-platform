"""Immutable Route release manifest material; no executor is enabled."""
from alembic import op


revision = "a0v_170"
down_revision = "a0v_169"
branch_labels = depends_on = None


def upgrade():
    op.execute("""CREATE TABLE aip_route_eval_release_material (
      org_id text NOT NULL,project_id text NOT NULL,execution_id text NOT NULL,
      manifest_hash text NOT NULL,manifest_payload bytea NOT NULL,
      created_at timestamptz NOT NULL DEFAULT now(),
      PRIMARY KEY(org_id,project_id,execution_id),
      UNIQUE(org_id,project_id,manifest_hash),
      FOREIGN KEY(org_id,project_id,execution_id)
        REFERENCES aip_route_eval_finalization_proof(org_id,project_id,execution_id),
      CHECK(manifest_hash ~ '^[0-9a-f]{64}$'),
      CHECK(octet_length(manifest_payload) BETWEEN 1 AND 67108864),
      CHECK(encode(digest(manifest_payload,'sha256'),'hex')=manifest_hash)
    )""")
    table = "aip_route_eval_release_material"
    scope = ("org_id=NULLIF(current_setting('aos.org_id',true),'') AND "
        "project_id=NULLIF(current_setting('aos.project_id',true),'')")
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(f"""CREATE POLICY route_eval_finalizer_{table} ON {table}
      TO aos_route_eval_finalizer USING({scope}) WITH CHECK({scope})""")
    op.execute(f"""CREATE POLICY route_eval_release_reader_{table} ON {table}
      FOR SELECT TO aos_runtime USING({scope})""")
    op.execute(f"REVOKE ALL ON {table} FROM PUBLIC,aos_runtime,aos_route_eval_finalizer")
    op.execute(f"GRANT SELECT,INSERT ON {table} TO aos_route_eval_finalizer")
    op.execute(f"GRANT SELECT ON {table} TO aos_runtime")
    op.execute(f"""CREATE TRIGGER route_eval_release_frozen_{table}
      BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW
      EXECUTE FUNCTION guard_aip4_append_only()""")
    op.execute(f"""CREATE TRIGGER route_eval_release_no_truncate_{table}
      BEFORE TRUNCATE ON {table} FOR EACH STATEMENT
      EXECUTE FUNCTION guard_aip4_append_only()""")


def downgrade():
    raise RuntimeError("Route release material removal requires explicit reconciliation")
