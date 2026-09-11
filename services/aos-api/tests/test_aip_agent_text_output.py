from hashlib import sha256
from types import SimpleNamespace

import pytest

from aos_api.aip_agent_text_output import read_agent_text, validate_agent_text
from aos_api.aip_contracts import ArtifactRef
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope("org-org", "dev-project")
TEXT = "可恢复的经营建议"
HASH = sha256(TEXT.encode()).hexdigest()


def test_valid_text_is_bounded_and_hash_exact():
    validate_agent_text(TEXT, HASH, ["internal"])


@pytest.mark.parametrize("text,hash_value,markings", [(TEXT, "f" * 64, ["internal"]), ("x" * (2*1024*1024+1), HASH, ["internal"]), (TEXT, HASH, []), (TEXT, HASH, ["unknown"]), (None, HASH, ["internal"])])
def test_invalid_text_rejected(text, hash_value, markings):
    with pytest.raises(ValueError): validate_agent_text(text, hash_value, markings)


@pytest.mark.parametrize("change", [None, "missing", "marking", "hash", "body", "artifact_type"])
def test_read_checks_scope_exact_artifact_and_markings(change):
    row = dict(content_text=TEXT, content_hash=HASH, marking=["internal"], artifact_hash=HASH,
               artifact_type="agent_text_output", artifact_marking=["internal"])
    if change == "missing": row = None
    elif change == "marking": row["marking"] = ["confidential"]
    elif change == "hash": row["artifact_hash"] = "f" * 64
    elif change == "body": row["content_text"] = "被替换"
    elif change == "artifact_type": row["artifact_type"] = "other"
    class Connection:
        def execute(self, sql, params):
            assert params == (*SCOPE.key, "artifact-1")
            return SimpleNamespace(fetchone=lambda: row)
    ref = ArtifactRef(artifactId="artifact-1", artifactType="agent_text_output", revision="1", contentHash=HASH)
    if change is None:
        assert read_agent_text(Connection(), SCOPE, ref, markings=["internal"]) == TEXT
    else:
        with pytest.raises(ValueError): read_agent_text(Connection(), SCOPE, ref, markings=["internal"])


@pytest.mark.parametrize("retain", [False, True])
def test_executor_retention_is_explicit_and_not_metadata(retain):
    import json
    from aos_api.aip_agent_run_executor import AipAgentRunExecutor
    from test_ecommerce_analyst_growth_plan_draft import generation
    _, attempt, raw = generation()
    calls = []
    class Artifacts:
        def record_artifact(self, *args, **kwargs):
            calls.append((args, kwargs))
            return "artifact-1"
    executor = AipAgentRunExecutor(artifact_store=Artifacts(), retain_output_text=retain)
    executor._record_output_artifact(SCOPE, SimpleNamespace(task_run_id="task-run-1", agent_run_id=attempt.agent_run_id),
        attempt, dict(answer=raw, providerReceiptId="provider-1", usageReceiptIds=["usage-1"]), "pytest")
    args, kwargs = calls[0]
    assert kwargs == ({"text_content": raw} if retain else {})
    assert "answerText" not in args[4]["metadata"] and raw not in json.dumps(args[4], ensure_ascii=False)


def test_private_output_actual_migration_storage_and_isolation():
    import os
    if os.getenv("AOS_GROWTH_DRAFT_FULL_GRAPH_TEST") != "1":
        pytest.skip("requires explicitly selected disposable database test")
    import importlib.util
    from pathlib import Path
    import psycopg
    from aos_api.aip_task_store import AipTaskStore
    from test_ecommerce_analyst_growth_plan_full_graph import disposable_database, seed_graph
    with disposable_database() as connect:
        seed_graph(connect)
        path = Path(__file__).resolve().parents[1] / "alembic/versions/a0v_012_agent_text_output.py"
        spec = importlib.util.spec_from_file_location("a0v_text_test_migration", path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        with connect(SCOPE) as conn:
            migration.op = SimpleNamespace(execute=conn.execute)
            migration.upgrade()
        store = AipTaskStore(connect)
        artifact_id = "artifact-" + "d" * 20
        payload = dict(contentHash=HASH, contentRef="sha256://" + HASH, marking=["internal"], metadata={"answerLength": len(TEXT)})
        assert store.record_artifact(SCOPE, "a0v-full-task-run", "pytest", "agent_text_output", payload, artifact_id=artifact_id, text_content=TEXT) == artifact_id
        assert store.record_artifact(SCOPE, "a0v-full-task-run", "pytest", "agent_text_output", payload, artifact_id=artifact_id, text_content=TEXT) == artifact_id
        ref = ArtifactRef(artifactId=artifact_id, artifactType="agent_text_output", revision="1", contentHash=HASH)
        with connect(SCOPE) as conn:
            assert read_agent_text(conn, SCOPE, ref, markings=["internal"]) == TEXT
            with pytest.raises(ValueError): read_agent_text(conn, SCOPE, ref, markings=["public"])
            with pytest.raises(ValueError): read_agent_text(conn, TenantScope("dev-org", "dev-project"), ref, markings=["internal"])
            for command in ["UPDATE aip_agent_text_output SET content_text=content_text", "DELETE FROM aip_agent_text_output", "TRUNCATE aip_agent_text_output"]:
                with pytest.raises(psycopg.Error):
                    with conn.transaction(): conn.execute(command)
            with conn.transaction():
                conn.execute("SET LOCAL ROLE aos_runtime")
                conn.execute("SELECT set_config('aos.org_id','dev-org',true),set_config('aos.project_id','dev-project',true)")
                assert conn.execute("SELECT count(*) AS n FROM aip_agent_text_output").fetchone()["n"] == 0
        legacy_id = "artifact-" + "f" * 20
        store.record_artifact(SCOPE, "a0v-full-task-run", "pytest", "agent_text_output", payload, artifact_id=legacy_id)
        with pytest.raises(ValueError):
            store.record_artifact(SCOPE, "a0v-full-task-run", "pytest", "agent_text_output", payload, artifact_id=legacy_id, text_content=TEXT)
        with connect(SCOPE) as conn:
            assert conn.execute("SELECT count(*) AS n FROM aip_agent_text_output WHERE artifact_id=%s", (legacy_id,)).fetchone()["n"] == 0
        assert TEXT not in str(store.timeline(SCOPE, "a0v-full-task-run").model_dump())
        # An insertion failure after Artifact insert must roll back both owners.
        with connect(SCOPE) as conn:
            conn.execute("CREATE FUNCTION a0v_test_reject_text() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic body failure'; END $$")
            conn.execute("CREATE TRIGGER a0v_test_reject_text BEFORE INSERT ON aip_agent_text_output FOR EACH ROW EXECUTE FUNCTION a0v_test_reject_text()")
        rejected_id = "artifact-" + "e" * 20
        with pytest.raises(psycopg.Error):
            store.record_artifact(SCOPE, "a0v-full-task-run", "pytest", "agent_text_output", payload, artifact_id=rejected_id, text_content=TEXT)
        with connect(SCOPE) as conn:
            assert conn.execute("SELECT count(*) AS n FROM aip_artifact WHERE artifact_id=%s", (rejected_id,)).fetchone()["n"] == 0


@pytest.mark.parametrize("value", ["false", "true", 1, None])
def test_retention_configuration_is_not_coerced(value):
    from aos_api.aip_agent_run_executor import AipAgentRunExecutor
    with pytest.raises(ValueError): AipAgentRunExecutor(retain_output_text=value)
