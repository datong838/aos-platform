"""Private, tenant-bound retained AgentRun query inputs."""
from alembic import op

revision = "a0v_015"
down_revision = "a0v_014"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE aip_agent_query_input (
        org_id TEXT NOT NULL, project_id TEXT NOT NULL, artifact_id TEXT NOT NULL,
        attempt_id TEXT NOT NULL, content_text TEXT NOT NULL,
        content_hash TEXT NOT NULL, request_hash TEXT NOT NULL,
        marking JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
        PRIMARY KEY(org_id,project_id,artifact_id),
        UNIQUE(org_id,project_id,attempt_id),
        FOREIGN KEY(org_id,project_id,artifact_id)
            REFERENCES aip_artifact(org_id,project_id,artifact_id),
        FOREIGN KEY(org_id,project_id,attempt_id)
            REFERENCES aip_agent_run_execution_attempt(org_id,project_id,attempt_id),
        CHECK(char_length(content_text)<=16000 AND octet_length(content_text)<=2097152),
        CHECK(content_hash=encode(sha256(convert_to(content_text,'UTF8')),'hex')),
        CHECK(request_hash ~ '^[0-9a-f]{64}$'),
        CHECK(jsonb_typeof(marking)='array' AND jsonb_array_length(marking)>0)
    )""")
    op.execute("""CREATE TRIGGER immutable_agent_query_input
        BEFORE UPDATE OR DELETE ON aip_agent_query_input
        FOR EACH ROW EXECUTE FUNCTION guard_aip4_append_only()""")
    op.execute("""CREATE TRIGGER no_truncate_agent_query_input
        BEFORE TRUNCATE ON aip_agent_query_input
        FOR EACH STATEMENT EXECUTE FUNCTION guard_aip4_append_only()""")
    op.execute("ALTER TABLE aip_agent_query_input ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE aip_agent_query_input FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY agent_query_input_scope ON aip_agent_query_input TO aos_runtime
        USING(org_id=NULLIF(current_setting('aos.org_id',true),'')
          AND project_id=NULLIF(current_setting('aos.project_id',true),''))
        WITH CHECK(org_id=NULLIF(current_setting('aos.org_id',true),'')
          AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
    op.execute("REVOKE ALL ON aip_agent_query_input FROM PUBLIC")
    op.execute("GRANT SELECT,INSERT ON aip_agent_query_input TO aos_runtime")


def downgrade():
    raise RuntimeError("Forward-only AgentRun query authority; preserve original evaluation inputs")
