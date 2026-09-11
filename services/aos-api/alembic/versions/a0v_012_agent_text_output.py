"""Private, tenant-bound retained AgentRun text outputs."""
from alembic import op

revision = "a0v_012"
down_revision = "a0v_011"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE aip_agent_text_output (
        org_id TEXT NOT NULL, project_id TEXT NOT NULL, artifact_id TEXT NOT NULL,
        content_text TEXT NOT NULL, content_hash TEXT NOT NULL,
        marking JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
        PRIMARY KEY(org_id,project_id,artifact_id),
        FOREIGN KEY(org_id,project_id,artifact_id) REFERENCES aip_artifact(org_id,project_id,artifact_id),
        CHECK(octet_length(content_text)<=2097152),
        CHECK(content_hash=encode(sha256(convert_to(content_text,'UTF8')),'hex')),
        CHECK(jsonb_typeof(marking)='array' AND jsonb_array_length(marking)>0)
    )""")
    op.execute("""CREATE TRIGGER immutable_agent_text_output BEFORE UPDATE OR DELETE ON aip_agent_text_output
        FOR EACH ROW EXECUTE FUNCTION guard_aip4_append_only()""")
    op.execute("""CREATE TRIGGER no_truncate_agent_text_output BEFORE TRUNCATE ON aip_agent_text_output
        FOR EACH STATEMENT EXECUTE FUNCTION guard_aip4_append_only()""")
    op.execute("ALTER TABLE aip_agent_text_output ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE aip_agent_text_output FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY agent_text_output_scope ON aip_agent_text_output TO aos_runtime
        USING(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))
        WITH CHECK(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
    op.execute("REVOKE ALL ON aip_agent_text_output FROM PUBLIC")
    op.execute("GRANT SELECT,INSERT ON aip_agent_text_output TO aos_runtime")


def downgrade():
    raise RuntimeError("Forward-only retained output authority; do not discard recovery evidence")
