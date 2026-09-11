from contextlib import contextmanager
from hashlib import sha256
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from aos_api.aip_agent_query_input import (
    read_agent_query,
    validate_agent_query,
    write_agent_query,
)
from aos_api.aip_contracts import ArtifactRef
from aos_api.aip_task_store import AipTaskStore, AipTaskTransitionBlocked
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
QUERY = '{"protocol":"aos.portrait-proposal/v1","sources":[{"fact":1}]}'
HASH = sha256(QUERY.encode()).hexdigest()
REQUEST_HASH = "a" * 64
ARTIFACT_ID = "artifact-" + "1" * 20
ATTEMPT_ID = "attempt-1"


def _ref(**change):
    values = dict(
        artifactId=ARTIFACT_ID,
        artifactType="agent_query_input",
        revision="1",
        contentHash=HASH,
    )
    values.update(change)
    return ArtifactRef(**values)


def test_query_validation_is_exact_and_bounded():
    validate_agent_query(QUERY, HASH, REQUEST_HASH, ["internal"])


@pytest.mark.parametrize(
    "query,content_hash,request_hash,marking",
    [
        (" ", HASH, REQUEST_HASH, ["internal"]),
        (QUERY, "f" * 64, REQUEST_HASH, ["internal"]),
        (QUERY, HASH, "x" * 64, ["internal"]),
        (QUERY, HASH, REQUEST_HASH, []),
        (QUERY, HASH, REQUEST_HASH, ["internal", "internal"]),
        ("x" * 16_001, sha256(("x" * 16_001).encode()).hexdigest(), REQUEST_HASH, ["internal"]),
    ],
)
def test_invalid_query_authority_is_rejected(query, content_hash, request_hash, marking):
    with pytest.raises(ValueError):
        validate_agent_query(query, content_hash, request_hash, marking)


def _row(**change):
    value = dict(
        content_text=QUERY,
        content_hash=HASH,
        request_hash=REQUEST_HASH,
        marking=["internal"],
        artifact_hash=HASH,
        artifact_type="agent_query_input",
        artifact_marking=["internal"],
        source={
            "attemptId": ATTEMPT_ID,
            "agentRunId": "agent-run-1",
            "requestHash": REQUEST_HASH,
        },
        agent_run_id="agent-run-1",
        attempt_request_hash=REQUEST_HASH,
    )
    value.update(change)
    return value


@pytest.mark.parametrize(
    "change",
    [
        None,
        {"artifact_hash": "f" * 64},
        {"request_hash": "b" * 64},
        {"artifact_type": "agent_text_output"},
        {"marking": ["confidential"]},
        {"source": {"attemptId": "other", "agentRunId": "agent-run-1", "requestHash": REQUEST_HASH}},
        {"attempt_request_hash": "b" * 64},
        {"content_text": "changed"},
    ],
)
def test_read_revalidates_artifact_attempt_request_and_access(change):
    row = _row(**(change or {}))

    class Connection:
        def execute(self, sql, params):
            assert params == (*SCOPE.key, ARTIFACT_ID, ATTEMPT_ID)
            return SimpleNamespace(fetchone=lambda: row)

    if change is None:
        assert read_agent_query(
            Connection(),
            SCOPE,
            _ref(),
            attempt_id=ATTEMPT_ID,
            request_hash=REQUEST_HASH,
            markings=["internal"],
        ) == QUERY
    else:
        with pytest.raises(ValueError):
            read_agent_query(
                Connection(),
                SCOPE,
                _ref(),
                attempt_id=ATTEMPT_ID,
                request_hash=REQUEST_HASH,
                markings=["internal"],
            )


def test_write_requires_joined_artifact_and_attempt_authority():
    calls = []

    class Connection:
        allowed = True

        def execute(self, sql, params):
            calls.append((sql, params))
            return SimpleNamespace(
                fetchone=lambda: {"artifact_id": ARTIFACT_ID} if self.allowed else None
            )

    connection = Connection()
    write_agent_query(
        connection,
        SCOPE,
        ARTIFACT_ID,
        ATTEMPT_ID,
        QUERY,
        HASH,
        REQUEST_HASH,
        ["internal"],
    )
    assert "artifact.source->>'requestHash'=attempt.request_hash" in calls[0][0]
    assert ATTEMPT_ID in calls[0][1] and REQUEST_HASH in calls[0][1]
    connection.allowed = False
    with pytest.raises(ValueError, match="does not match Artifact and Attempt"):
        write_agent_query(
            connection,
            SCOPE,
            ARTIFACT_ID,
            ATTEMPT_ID,
            QUERY,
            HASH,
            REQUEST_HASH,
            ["internal"],
        )


def test_invalid_identity_and_read_access_fail_before_database():
    class Connection:
        def execute(self, *args):
            raise AssertionError("invalid boundary must not query")

    with pytest.raises(ValueError, match="Artifact and Attempt identities"):
        write_agent_query(
            Connection(), SCOPE, ARTIFACT_ID, " ", QUERY, HASH, REQUEST_HASH, ["internal"]
        )
    with pytest.raises(ValueError, match="exact AgentRun query"):
        read_agent_query(
            Connection(),
            SCOPE,
            _ref(),
            attempt_id=ATTEMPT_ID,
            request_hash="x" * 64,
            markings=["internal"],
        )


def test_task_store_routes_query_body_without_putting_it_in_metadata(monkeypatch):
    statements = []

    class Connection:
        def execute(self, sql, params=None):
            statements.append((sql, params))
            if "SELECT 1 FROM aip_task_run" in sql:
                row = {"exists": 1}
            elif "SELECT * FROM aip_artifact" in sql:
                row = None
            elif "INSERT INTO aip_agent_query_input" in sql:
                row = {"artifact_id": ARTIFACT_ID}
            else:
                row = None
            return SimpleNamespace(fetchone=lambda: row)

        def commit(self):
            statements.append(("COMMIT", None))

    connection = Connection()

    @contextmanager
    def connect(scope):
        assert scope == SCOPE
        yield connection

    source = {
        "attemptId": ATTEMPT_ID,
        "agentRunId": "agent-run-1",
        "requestHash": REQUEST_HASH,
    }
    payload = {
        "contentRef": "sha256://" + HASH,
        "schemaRef": "aos://schemas/aip-agent-query-input/v1",
        "contentHash": HASH,
        "marking": ["internal"],
        "source": source,
        "metadata": {"queryLength": len(QUERY)},
    }
    assert AipTaskStore(connect).record_artifact(
        SCOPE,
        "task-run-1",
        "tester",
        "agent_query_input",
        payload,
        artifact_id=ARTIFACT_ID,
        text_content=QUERY,
    ) == ARTIFACT_ID
    artifact_insert = next(params for sql, params in statements if "INSERT INTO aip_artifact" in sql)
    assert QUERY not in str(artifact_insert)
    assert statements[-1][0] == "COMMIT"


def test_other_artifact_types_cannot_use_retained_text():
    @contextmanager
    def unused(scope):
        raise AssertionError("validation must fail before connection")
        yield

    with pytest.raises(AipTaskTransitionBlocked, match="AgentRun input or output"):
        AipTaskStore(unused).record_artifact(
            SCOPE,
            "task-run-1",
            "tester",
            "eval_input",
            {"contentHash": HASH, "marking": ["internal"]},
            text_content=QUERY,
        )


def test_migration_is_forward_only_scoped_and_immutable():
    path = Path(__file__).resolve().parents[1] / "alembic/versions/a0v_015_agent_query_input.py"
    spec = importlib.util.spec_from_file_location("a0v_015_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    statements = []
    module.op = SimpleNamespace(execute=statements.append)
    module.upgrade()
    text = "\n".join(statements)
    assert module.down_revision == "a0v_014"
    assert "CREATE TABLE aip_agent_query_input" in text
    assert "aip_agent_run_execution_attempt" in text
    assert "UNIQUE(org_id,project_id,attempt_id)" in text
    assert "FORCE ROW LEVEL SECURITY" in text
    assert "immutable_agent_query_input" in text
    assert "no_truncate_agent_query_input" in text
    with pytest.raises(RuntimeError, match="preserve original evaluation inputs"):
        module.downgrade()
