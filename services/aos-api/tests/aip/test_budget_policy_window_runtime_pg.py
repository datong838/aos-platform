"""Real consumed child through the original fee gate; isolated new cases only."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import hashlib
import os
from pathlib import Path
import secrets

import psycopg
from psycopg import IsolationLevel, sql
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row
from pydantic import SecretStr
import pytest

from aos_api.aip_budget_cost_runtime import require_cost_risk
from aos_api.aip_budget_reservation_contracts import BudgetExactRef
from aos_api.db import get_dsn
from tests.aip.test_budget_policy_window_native_pg import (
    CHECKER, SCOPE, caller, issuer_factory, https_signer, isolated_owner,
    native_roles, prepare_parent, private_window_service_config, window_signer,
)

TASK = "qyh-policy-window-runtime-bridge-20261017"
RUNTIME = "aos_a0v_runtime_20260912"


def save(path, value):
    temporary = path.with_suffix(".pending")
    with temporary.open("x") as stream:
        os.chmod(temporary, 0o600)
        json.dump(value, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


@pytest.fixture(scope="session", autouse=True)
def _isolated_postgres_database():
    assert os.environ.get("AOS_TEST_USE_SHARED_DATABASE") != "1"
    database = os.environ["AOS_POLICY_WINDOW_TEST_DATABASE"]
    cluster = os.environ["AOS_POLICY_WINDOW_TEST_CLUSTER"]
    assert database.startswith("aos_test_") and database.endswith("_ti4_test")
    assert cluster not in {"7695302940039200809", "7697539289714241576"}
    with psycopg.connect(get_dsn()) as connection:
        connection.execute("SET TRANSACTION READ ONLY")
        assert connection.info.dbname == database
        assert str(connection.execute("SELECT system_identifier FROM pg_control_system()").fetchone()[0]) == cluster
        assert connection.execute("SELECT version_num FROM public.alembic_version").fetchone()[0] == os.environ["AOS_WINDOW_RUNTIME_EXPECTED_SCHEMA"]
        assert os.environ["AOS_WINDOW_RUNTIME_EXPECTED_SCHEMA"] in {"a0v_163", "a0v_164"}
    yield


@pytest.fixture
def fresh_parent(native_roles, issuer_factory, https_signer, monkeypatch):
    directory = Path(os.environ["AOS_WINDOW_RUNTIME_CASE_DIR"])
    assert directory.parent == Path("/tmp") and directory.name.startswith("window-runtime-bridge-")
    resume_hash = os.environ.get("AOS_WINDOW_RUNTIME_RESUME_PARENT_SHA256")
    if resume_hash:
        # A known, consumed parent can be carried forward only before any child
        # attempt. Never use this to retry an unknown parent/child operation.
        from aos_api.aip_budget_cost_basis import BudgetCostBasisProposal
        raw = (directory / "parent.json").read_bytes()
        assert hashlib.sha256(raw).hexdigest() == resume_hash
        state = json.loads((directory / "case.json").read_text())
        parent = json.loads(raw)
        assert state["task"] == TASK and state["parentKnownConsumed"] is True
        assert state["database"] == parent["database"] == os.environ["AOS_POLICY_WINDOW_TEST_DATABASE"]
        assert state["cluster"] == os.environ["AOS_POLICY_WINDOW_TEST_CLUSTER"]
        assert state["results"] == {} and set(state["commands"]) == {"propose"}
        assert "feeGateAttemptStarted" not in state
        assert state["commands"]["propose"] == parent["command"]
        return directory, state, BudgetCostBasisProposal.from_canonical_payload(parent["proposal"])
    assert not directory.exists(), "existing effect must be reconciled, never replayed"
    directory.mkdir(mode=0o700)
    state = dict(task=TASK, database=os.environ["AOS_POLICY_WINDOW_TEST_DATABASE"],
                 cluster=os.environ["AOS_POLICY_WINDOW_TEST_CLUSTER"], parentCreationStarted=True,
                 commands={}, results={})
    save(directory / "case.json", state)
    monkeypatch.setenv("AOS_POLICY_WINDOW_PARENT_CASE", str(directory / "parent.json"))
    command, parent = prepare_parent(issuer_factory, https_signer, native_roles)
    state["parentKnownConsumed"] = True
    state["commands"]["propose"] = command
    save(directory / "case.json", state)
    return directory, state, parent


@pytest.fixture
def current_signer(fresh_parent, monkeypatch):
    # Parent uses its original HTTPS issuer first, then the isolated child issuer.
    yield from window_signer.__wrapped__(monkeypatch)


@pytest.fixture
def actual_runtime(tmp_path):
    parts = conninfo_to_dict(get_dsn())
    path = tmp_path / "runtime.pgpass"
    path.touch(mode=0o600)
    with isolated_owner() as admin:
        existing = admin.execute("SELECT rolcanlogin,rolsuper,rolbypassrls,rolinherit,rolcreatedb,"
                                 "rolcreaterole,rolreplication FROM pg_roles WHERE rolname=%s", (RUNTIME,)).fetchone()
        if existing is None:
            admin.execute(sql.SQL("CREATE ROLE {} NOLOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION").format(sql.Identifier(RUNTIME)))
            admin.execute(sql.SQL("GRANT aos_runtime TO {} WITH INHERIT FALSE, SET TRUE, ADMIN FALSE").format(sql.Identifier(RUNTIME)))
        else:
            assert not any(existing.values()), "never replace an existing active credential or privileged role"
        password = secrets.token_urlsafe(32)
        admin.execute(sql.SQL("ALTER ROLE {} LOGIN PASSWORD {}").format(sql.Identifier(RUNTIME), sql.Literal(password)))
        admin.commit()
        path.write_text(f"{parts['host']}:{parts['port']}:{parts['dbname']}:{RUNTIME}:{password}\n")
        @contextmanager
        def connect():
            with psycopg.connect(host=parts["host"], port=parts["port"], dbname=parts["dbname"],
                    user=RUNTIME, passfile=str(path), require_auth="scram-sha-256", row_factory=dict_row,
                    options="-c statement_timeout=15000 -c lock_timeout=5000") as conn:
                assert conn.pgconn.used_password
                conn.isolation_level = IsolationLevel.SERIALIZABLE
                conn.execute("SET LOCAL ROLE aos_runtime")
                conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)", SCOPE.key)
                yield conn
        try:
            yield connect
        finally:
            admin.execute(sql.SQL("ALTER ROLE {} NOLOGIN PASSWORD NULL").format(sql.Identifier(RUNTIME)))
            admin.commit()
            path.write_text("# removed isolated runtime credential\n")


def test_consumed_child_reaches_original_current_cost_gate(
        fresh_parent, current_signer, native_roles, actual_runtime, tmp_path, monkeypatch):
    from aos_api.aip_budget_policy_window_service import (
        WindowRequest, WindowService, load_protected_config, _FORBIDDEN_ENV,
    )
    directory, state, parent = fresh_parent
    _, signed, _ = current_signer
    config = load_protected_config(private_window_service_config(native_roles, tmp_path))
    (directory / "attempts").mkdir(mode=0o700)
    service = WindowService(config, directory / "attempts")
    with monkeypatch.context() as clean:
        for key in (*_FORBIDDEN_ENV, "PGREQUIREAUTH"):
            clean.delenv(key, raising=False)
        for operation in ("propose", "decide", "consume"):
            if operation == "propose":
                command = state["commands"]["propose"]
            else:
                proposal = state["results"]["propose"]
                command = dict(schemaVersion=1, orgId=SCOPE.org_id, projectId=SCOPE.project_id,
                    idempotencyKey=state["commands"]["propose"]["idempotencyKey"] + "." + operation,
                    proposalId=proposal["proposalId"], proposalHash=proposal["proposalHash"],
                    targetPairHash=proposal["targetPairHash"])
                if operation == "decide":
                    command["decision"] = "approved"
                else:
                    decision = state["results"]["decide"]
                    command.update(decisionId=decision["decisionId"], decisionHash=decision["decisionHash"])
            state["commands"][operation] = command
            save(directory / "case.json", state)
            envelope = dict(schemaVersion=1, mode="execute", operation=operation, command=command)
            if operation == "decide":
                envelope["bearerToken"] = SecretStr(signed())
            result = service.execute(WindowRequest.model_validate(envelope))
            if "receipt" in result:
                result = result["receipt"]
            state["results"][operation] = result
            save(directory / "case.json", state)
            assert result.get("operation") == operation, "unknown effect: reconcile original command only"
    result = state["results"]["consume"]
    def ref(value):
        return BudgetExactRef(resourceType=value["assetType"], resourceId=value["assetId"],
                              revision=value["revision"], contentHash="sha256:" + value["contentHash"])
    state["feeGateAttemptStarted"] = True
    save(directory / "case.json", state)
    try:
        with actual_runtime() as conn:
            price = require_cost_risk(conn, SCOPE, ref(result["budgetRef"]), ref(result["priceRef"]),
                parent.basis.per_request_risk_minor)
            assert price is not None and price.price_snapshot_id == result["priceRef"]["assetId"]
            # This test only observes admission. It never commits a hold or a fence increment.
            conn.rollback()
    except Exception as error:
        state["feeGateKnownRejected"] = True
        state["failureType"] = type(error).__name__
        state["finishedAt"] = datetime.now(timezone.utc).isoformat()
        save(directory / "case.json", state)
        raise
    state["feeGatePassedWithoutHold"] = True
    save(directory / "case.json", state)


@pytest.mark.parametrize('operation', ['propose', 'consume'])
def test_known_child_catalog_reconciliation_keeps_original_receipt(
        native_roles, tmp_path, monkeypatch, operation):
    from aos_api.aip_budget_policy_window_service import (
        WindowRequest, WindowService, load_protected_config, _FORBIDDEN_ENV,
    )
    root = Path(os.environ['AOS_WINDOW_RUNTIME_KNOWN_CASE_DIR'])
    state = json.loads((root / 'case.json').read_text())
    assert state['cluster'] == os.environ['AOS_POLICY_WINDOW_TEST_CLUSTER']
    assert state['database'] == os.environ['AOS_POLICY_WINDOW_TEST_DATABASE']
    assert state['feeGateKnownRejected'] and set(state['results']) == {'propose', 'decide', 'consume'}
    attempts = tmp_path / 'readonly-attempts'
    attempts.mkdir(mode=0o700)
    service = WindowService(load_protected_config(private_window_service_config(native_roles, tmp_path)), attempts)
    with monkeypatch.context() as clean:
        for key in (*_FORBIDDEN_ENV, 'PGREQUIREAUTH'):
            clean.delenv(key, raising=False)
        result = service.execute(WindowRequest(schemaVersion=1, mode='reconcile',
            operation=operation, command=state['commands'][operation]))
    assert result == dict(status='observed', receipt=state['results'][operation], activationEligible=False)
    assert not list(attempts.iterdir())


@pytest.mark.parametrize('mutation,code', [
    ('ALTER FUNCTION public.aip_policy_window_parent_v1(jsonb,boolean) SET search_path=public', 'FUNCTION_SEAL_DRIFT'),
    ('ALTER FUNCTION public.aip_policy_window_parent_v1(jsonb,boolean) STABLE', 'FUNCTION_SEAL_DRIFT'),
    ('ALTER TABLE public.aip_budget_policy_window_binding DISABLE ROW LEVEL SECURITY', 'RELATION_SEAL_DRIFT'),
    ('ALTER TABLE public.aip_budget_policy_window_binding DISABLE TRIGGER policy_window_insert_guard', 'RELATION_SEAL_DRIFT'),
    ('GRANT SELECT ON public.aip_budget_policy_window_binding TO aos_budget_renewal_maker_call', 'RELATION_SEAL_DRIFT'),
])
def test_shared_catalog_observes_real_drift_and_rolls_back(mutation, code):
    from aos_api.aip_budget_policy_window_catalog import verify_window_catalog, WindowCatalogBlocked
    with isolated_owner() as conn:
        conn.execute("SELECT set_config('search_path','pg_catalog',true)")
        pins = {}
        for name, table in [('manifest_sha256', 'aip_budget_policy_window_proposal'),
                            ('legacy_manifest_sha256', 'aip_budget_policy_renewal_proposal')]:
            raw = conn.execute('SELECT obj_description(%s::regclass,%s) AS seal',
                               ('public.' + table, 'pg_class')).fetchone()['seal']
            pins[name] = hashlib.sha256(raw.encode()).hexdigest()
        # Synthetic baseline pins only. Runtime deployment must supply independent pins.
        verify_window_catalog(conn, **pins)
        try:
            conn.execute(mutation)
            with pytest.raises(WindowCatalogBlocked, match=code):
                verify_window_catalog(conn, **pins)
        finally:
            conn.rollback()
        conn.execute("SELECT set_config('search_path','pg_catalog',true)")
        verify_window_catalog(conn, **pins)
        conn.rollback()
