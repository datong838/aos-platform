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
        assert os.environ["AOS_WINDOW_RUNTIME_EXPECTED_SCHEMA"] in {"a0v_163", "a0v_164", "a0v_165"}
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
            path.write_text(f"{parts['host']}:{parts['port']}:{parts['dbname']}:{RUNTIME}:{password}\n")
            yield connect
        finally:
            admin.execute(sql.SQL("ALTER ROLE {} NOLOGIN PASSWORD NULL").format(sql.Identifier(RUNTIME)))
            admin.commit()
            path.write_text("# removed isolated runtime credential\n")


@pytest.fixture
def actual_evaluator(tmp_path, monkeypatch):
    from aos_api.aip_binding_evaluator_connection import (
        BindingEvaluatorDatabaseConfig, BindingEvaluatorConnectionFactory, _FORBIDDEN_ENV,
    )
    login = 'aos_aip_binding_evaluator'
    parts = conninfo_to_dict(get_dsn())
    path = tmp_path / 'evaluator.pgpass'
    path.touch(mode=0o600)
    with isolated_owner() as admin:
        row = admin.execute('SELECT rolcanlogin,rolinherit,rolsuper,rolbypassrls,rolcreatedb,'
                            'rolcreaterole,rolreplication FROM pg_roles WHERE rolname=%s', (login,)).fetchone()
        assert row is not None and not any(row.values())
        assert admin.execute('SELECT count(*) AS n FROM pg_auth_members WHERE '
                             'roleid=%s::regrole OR member=%s::regrole', (login, login)).fetchone()['n'] == 0
        password = secrets.token_urlsafe(32)
        admin.execute(sql.SQL('ALTER ROLE {} LOGIN PASSWORD {}').format(sql.Identifier(login), sql.Literal(password)))
        admin.commit()
        try:
            path.write_text(f"{parts['host']}:{parts['port']}:{parts['dbname']}:{login}:{password}\n")
            factory = BindingEvaluatorConnectionFactory(BindingEvaluatorDatabaseConfig(
                parts['host'], int(parts['port']), parts['dbname'], path))

            @contextmanager
            def connect(scope=SCOPE):
                with monkeypatch.context() as clean:
                    for name in _FORBIDDEN_ENV:
                        clean.delenv(name, raising=False)
                    with factory(scope) as conn:
                        yield conn
            yield connect
        finally:
            admin.execute(sql.SQL('ALTER ROLE {} NOLOGIN PASSWORD NULL').format(sql.Identifier(login)))
            admin.commit()
            path.write_text('# removed isolated evaluator credential\n')


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


def test_native_child_fact_is_bound_to_existing_consumed_pair(actual_runtime):
    from psycopg.types.json import Jsonb
    root = Path(os.environ['AOS_WINDOW_RUNTIME_KNOWN_CASE_DIR'])
    state = json.loads((root / 'case.json').read_text())
    assert state['cluster'] == os.environ['AOS_POLICY_WINDOW_TEST_CLUSTER']
    assert state['database'] == os.environ['AOS_POLICY_WINDOW_TEST_DATABASE']
    assert set(state['results']) == {'propose', 'decide', 'consume'}
    receipt = state['results']['consume']
    with actual_runtime() as conn:
        # Use the existing native caller's head-lock privileges. The child
        # definer gains no new UPDATE privilege on the old sealed relations.
        conn.execute('SELECT current_revision FROM public.aip_model_price_snapshot_head '
                     'WHERE org_id=%s AND project_id=%s AND model_price_snapshot_id=%s FOR SHARE',
                     (*SCOPE.key, receipt['priceRef']['assetId'])).fetchone()
        conn.execute("SELECT current_revision FROM public.aip_model_governance_policy_head "
                     "WHERE org_id=%s AND project_id=%s AND policy_kind='budget' AND policy_id=%s FOR SHARE",
                     (*SCOPE.key, receipt['policyRef']['assetId'])).fetchone()
        result = conn.execute('SELECT public.aip_policy_window_risk_fact_v1(%s,%s) AS fact',
            (Jsonb(receipt['budgetRef']), Jsonb(receipt['priceRef']))).fetchone()['fact']
        assert result['activationEligible'] is False
        assert result['parent'] == state['results']['propose']['proposal']['parent']
        assert result['policyRef'] == receipt['policyRef']
        assert result['priceRef'] == receipt['priceRef']
        assert result['decisionId'] == receipt['decisionId']
        assert result['receiptId'] == receipt['receiptId']
        assert result['bindingId'] == receipt['bindingId']
        assert result['fenceVersion'] == 2
        conn.rollback()


@pytest.mark.parametrize('change,states', [
    ('extra_budget_field', {'22023'}), ('bool_budget_revision', {'22023'}),
    ('string_price_revision', {'22023'}), ('nonwindow_price', {'22023'}),
    ('wrong_price_hash', {'P0002'}), ('wrong_parent_hash', {'23514'}),
    ('wrong_parent_id', {'23514'}), ('null_price', {'22023'}),
])
def test_native_child_fact_rejects_wrong_exact_references(actual_runtime, change, states):
    from psycopg.types.json import Jsonb
    state = json.loads((Path(os.environ['AOS_WINDOW_RUNTIME_KNOWN_CASE_DIR']) / 'case.json').read_text())
    assert state['database'] == os.environ['AOS_POLICY_WINDOW_TEST_DATABASE']
    assert state['cluster'] == os.environ['AOS_POLICY_WINDOW_TEST_CLUSTER']
    receipt = state['results']['consume']
    budget, price = dict(receipt['budgetRef']), dict(receipt['priceRef'])
    if change == 'extra_budget_field': budget['approved'] = True
    elif change == 'bool_budget_revision': budget['revision'] = True
    elif change == 'string_price_revision': price['revision'] = '1'
    elif change == 'nonwindow_price': price['assetId'] = 'legacy-price'
    elif change == 'wrong_price_hash': price['contentHash'] = 'f' * 64
    elif change == 'wrong_parent_hash': budget['contentHash'] = 'f' * 64
    elif change == 'wrong_parent_id': budget['assetId'] += '-different'
    elif change == 'null_price': price = None
    with actual_runtime() as conn:
        with pytest.raises(psycopg.Error) as rejected:
            conn.execute('SELECT public.aip_policy_window_risk_fact_v1(%s,%s)',
                         (Jsonb(budget), Jsonb(price))).fetchone()
        assert rejected.value.sqlstate in states
        conn.rollback()


def test_another_actual_runtime_member_cannot_borrow_the_entry(issuer_factory):
    from psycopg.types.json import Jsonb
    state = json.loads((Path(os.environ['AOS_WINDOW_RUNTIME_KNOWN_CASE_DIR']) / 'case.json').read_text())
    receipt = state['results']['consume']
    with issuer_factory(SCOPE, False) as conn:
        row = conn.execute('SELECT session_user AS login,current_user AS role').fetchone()
        assert row == dict(login='aos_budget_cost_issuer', role='aos_runtime')
        with pytest.raises(psycopg.errors.InsufficientPrivilege, match='ACTUAL_CALLER_REQUIRED'):
            conn.execute('SELECT public.aip_policy_window_risk_fact_v1(%s,%s)',
                (Jsonb(receipt['budgetRef']), Jsonb(receipt['priceRef']))).fetchone()
        conn.rollback()


@pytest.mark.parametrize('purpose', ['maker', 'issuer', 'consumer'])
def test_original_purpose_callers_have_no_new_fact_execute(native_roles, purpose):
    from psycopg.types.json import Jsonb
    state = json.loads((Path(os.environ['AOS_WINDOW_RUNTIME_KNOWN_CASE_DIR']) / 'case.json').read_text())
    receipt = state['results']['consume']
    with native_roles(purpose) as conn:
        assert conn.execute("SELECT has_function_privilege(current_user,"
            "'public.aip_policy_window_risk_fact_v1(jsonb,jsonb)','EXECUTE') AS allowed").fetchone()['allowed'] is False
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute('SELECT public.aip_policy_window_risk_fact_v1(%s,%s)',
                (Jsonb(receipt['budgetRef']), Jsonb(receipt['priceRef']))).fetchone()
        conn.rollback()


@pytest.mark.parametrize('canary', [False, True])
def test_actual_evaluator_native_fact_keeps_tenant_boundary(actual_evaluator, canary):
    from aos_api.tenant_scope import TenantScope
    from psycopg.types.json import Jsonb
    state = json.loads((Path(os.environ['AOS_WINDOW_RUNTIME_KNOWN_CASE_DIR']) / 'case.json').read_text())
    receipt = state['results']['consume']
    scope = TenantScope('dev-org', 'dev-project') if canary else SCOPE
    with actual_evaluator(scope) as conn:
        if canary:
            with pytest.raises(psycopg.errors.InsufficientPrivilege, match='NATIVE_TRANSACTION_REQUIRED'):
                conn.execute('SELECT public.aip_policy_window_risk_fact_v1(%s,%s)',
                    (Jsonb(receipt['budgetRef']), Jsonb(receipt['priceRef']))).fetchone()
        else:
            # These are original evaluator row-lock grants, not new privileges.
            conn.execute('SELECT current_revision FROM public.aip_model_price_snapshot_head '
                'WHERE org_id=%s AND project_id=%s AND model_price_snapshot_id=%s FOR SHARE',
                (*SCOPE.key, receipt['priceRef']['assetId'])).fetchone()
            conn.execute("SELECT current_revision FROM public.aip_model_governance_policy_head "
                "WHERE org_id=%s AND project_id=%s AND policy_kind='budget' AND policy_id=%s FOR SHARE",
                (*SCOPE.key, receipt['policyRef']['assetId'])).fetchone()
            fact = conn.execute('SELECT public.aip_policy_window_risk_fact_v1(%s,%s) AS fact',
                (Jsonb(receipt['budgetRef']), Jsonb(receipt['priceRef']))).fetchone()['fact']
            assert fact['receiptId'] == receipt['receiptId'] and fact['activationEligible'] is False
        conn.rollback()


def test_actual_runtime_native_fact_rejects_canary(actual_runtime):
    from psycopg.types.json import Jsonb
    state = json.loads((Path(os.environ['AOS_WINDOW_RUNTIME_KNOWN_CASE_DIR']) / 'case.json').read_text())
    receipt = state['results']['consume']
    with actual_runtime() as conn:
        conn.execute("SELECT set_config('aos.org_id','dev-org',true)")
        with pytest.raises(psycopg.errors.InsufficientPrivilege, match='NATIVE_TRANSACTION_REQUIRED'):
            conn.execute('SELECT public.aip_policy_window_risk_fact_v1(%s,%s)',
                (Jsonb(receipt['budgetRef']), Jsonb(receipt['priceRef']))).fetchone()
        conn.rollback()


@pytest.mark.parametrize('entry', ['native', 'cost'])
@pytest.mark.parametrize('winner', ['reader_commit', 'reader_rollback', 'writer'])
def test_native_child_fact_serializes_original_revocation(
        native_roles, actual_runtime, window_signer, tmp_path, monkeypatch, winner,
        entry, runtime_deployment_config):
    from concurrent.futures import ThreadPoolExecutor
    from datetime import timedelta
    from aos_api.aip_budget_cost_runtime import BudgetCostRuntimeBlocked
    import time
    from psycopg.types.json import Jsonb
    from aos_api.aip_budget_policy_window_service import (
        WindowService, WindowRequest, load_protected_config, _FORBIDDEN_ENV,
    )
    from tests.aip.test_budget_policy_window_native_pg import (
        original_risk_fingerprint, window_case_facts,
    )

    def risk_fingerprint():
        result = original_risk_fingerprint()
        with isolated_owner() as conn:
            for table in ('aip_model_eval_budget_reservation', 'aip_model_judge_budget_reservation'):
                result[table] = conn.execute(sql.SQL("SELECT md5(COALESCE(jsonb_agg(to_jsonb(t) "
                    "ORDER BY to_jsonb(t)::text),'[]'::jsonb)::text) AS value FROM public.{} t").format(
                    sql.Identifier(table))).fetchone()['value']
        return result

    root = Path('/tmp') / ('window-runtime-' + entry + '-race-' + winner + '-r1')
    assert not root.exists(), 'reconcile the original race; never resend its commands'
    root.mkdir(mode=0o700)
    prior = json.loads((Path(os.environ['AOS_WINDOW_RUNTIME_KNOWN_CASE_DIR']) / 'case.json').read_text())
    assert prior['parentKnownConsumed'] and prior['database'] == os.environ['AOS_POLICY_WINDOW_TEST_DATABASE']
    assert prior['cluster'] == os.environ['AOS_POLICY_WINDOW_TEST_CLUSTER']
    command = dict(prior['commands']['propose'], idempotencyKey='native-race-' + secrets.token_hex(12))
    if entry == 'cost':
        parent = json.loads((Path(os.environ['AOS_WINDOW_RUNTIME_KNOWN_CASE_DIR']) / 'parent.json').read_text())
        with isolated_owner() as conn:
            now = conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
            original = conn.execute("SELECT result_ref FROM public.aip_budget_receipt "
                "WHERE receipt_id=%s AND operation='budget_revision.activate_cost'",
                (command['parentConsumptionReceiptId'],)).fetchone()
            assert original and original['result_ref']['resourceId'] == prior['results']['consume']['budgetRef']['assetId']
        start = max(now - timedelta(minutes=1), datetime.fromisoformat(parent['proposal']['target']['effectiveFrom'].replace('Z', '+00:00')))
        until = min(now + timedelta(hours=1), datetime.fromisoformat(parent['proposal']['target']['effectiveUntil'].replace('Z', '+00:00')) - timedelta(seconds=1))
        assert now + timedelta(minutes=2) < until
        command.update(idempotencyKey='cost-race-' + secrets.token_hex(12),
            effectiveFrom=start.isoformat().replace('+00:00', 'Z'),
            effectiveUntil=until.isoformat().replace('+00:00', 'Z'))
    state = dict(task=('qyh-policy-window-runtime-bridge-r4-20261017' if entry == 'cost'
                       else 'qyh-policy-window-runtime-bridge-r3-20261017'),
        database=prior['database'], cluster=prior['cluster'], winner=winner,
        testOnlySyntheticChecker=True, entry=entry, commands={}, results={}, riskBefore=risk_fingerprint())
    if entry == 'cost':
        with isolated_owner() as conn:
            state['parentFencesBefore'] = conn.execute('SELECT * FROM public.aip_budget_cost_runtime_fence '
                'ORDER BY org_id,project_id,budget_id,revision').fetchall()
    save(root / 'case.json', state)

    attempts = root / 'attempts'
    attempts.mkdir(mode=0o700)
    service = WindowService(load_protected_config(private_window_service_config(native_roles, tmp_path)), attempts)
    _, signed, _ = window_signer

    def execute(operation, command):
        state['commands'][operation] = command
        save(root / 'case.json', state)
        envelope = dict(schemaVersion=1, mode='execute', operation=operation, command=command)
        if operation in {'decide', 'revoke'}:
            envelope['bearerToken'] = SecretStr(signed())
        result = service.execute(WindowRequest.model_validate(envelope))
        state['results'][operation] = result
        save(root / 'case.json', state)
        assert result.get('operation') == operation
        return result

    def fact(conn, receipt):
        if entry == 'cost':
            def ref(value):
                return BudgetExactRef(resourceType=value['assetType'], resourceId=value['assetId'],
                    revision=value['revision'], contentHash='sha256:' + value['contentHash'])
            price = require_cost_risk(conn, SCOPE, ref(receipt['budgetRef']), ref(receipt['priceRef']),
                parent['proposal']['basis']['perRequestRiskMinor'])
            assert price.price_snapshot_id == receipt['priceRef']['assetId']
            assert price.development_cost_authorization.approval_ref == receipt['decisionId']
        conn.execute('SELECT current_revision FROM public.aip_model_price_snapshot_head '
            'WHERE org_id=%s AND project_id=%s AND model_price_snapshot_id=%s FOR SHARE',
            (*SCOPE.key, receipt['priceRef']['assetId'])).fetchone()
        conn.execute("SELECT current_revision FROM public.aip_model_governance_policy_head "
            "WHERE org_id=%s AND project_id=%s AND policy_kind='budget' AND policy_id=%s FOR SHARE",
            (*SCOPE.key, receipt['policyRef']['assetId'])).fetchone()
        return conn.execute('SELECT public.aip_policy_window_risk_fact_v1(%s,%s) AS fact',
            (Jsonb(receipt['budgetRef']), Jsonb(receipt['priceRef']))).fetchone()['fact']

    # Open the observer before the protected gateway clears global PG variables.
    with isolated_owner() as observer, monkeypatch.context() as clean:
        for name in (*_FORBIDDEN_ENV, 'PGREQUIREAUTH'):
            clean.delenv(name, raising=False)
        proposal = execute('propose', command)
        common = dict(schemaVersion=1, orgId=SCOPE.org_id, projectId=SCOPE.project_id,
            proposalId=proposal['proposalId'], proposalHash=proposal['proposalHash'],
            targetPairHash=proposal['targetPairHash'])
        decision = execute('decide', dict(common, idempotencyKey=command['idempotencyKey'] + '.decide', decision='approved'))
        receipt = execute('consume', dict(common, idempotencyKey=command['idempotencyKey'] + '.consume',
            decisionId=decision['decisionId'], decisionHash=decision['decisionHash']))
        revoke = dict(schemaVersion=1, orgId=SCOPE.org_id, projectId=SCOPE.project_id,
            idempotencyKey=command['idempotencyKey'] + '.revoke', proposalId=proposal['proposalId'],
            proposalHash=proposal['proposalHash'], originalDecisionId=decision['decisionId'],
            originalDecisionHash=decision['decisionHash'], reason='isolated native barrier test')
        state['commands']['revoke'] = revoke
        state['revokeAttemptStarted'] = False
        save(root / 'case.json', state)
        request = WindowRequest(schemaVersion=1, mode='execute', operation='revoke',
                                command=revoke, bearerToken=SecretStr(signed()))
        with actual_runtime() as reader:
            if winner == 'writer':
                reader.execute('SELECT current_revision FROM public.aip_model_price_snapshot_head '
                    'WHERE org_id=%s AND project_id=%s AND model_price_snapshot_id=%s',
                    (*SCOPE.key, receipt['priceRef']['assetId'])).fetchone()
                state['oldReaderSnapshotEstablished'] = True
                state['revokeAttemptStarted'] = True
                save(root / 'case.json', state)
                state['results']['revoke'] = service.execute(request)
                save(root / 'case.json', state)
                if entry == 'cost':
                    with pytest.raises(BudgetCostRuntimeBlocked) as error:
                        fact(reader, receipt)
                    assert isinstance(error.value.__cause__, psycopg.errors.SerializationFailure)
                else:
                    with pytest.raises(psycopg.errors.SerializationFailure):
                        fact(reader, receipt)
                state['oldSnapshotRejected40001'] = True
                reader.rollback()
            else:
                assert fact(reader, receipt)['receiptId'] == receipt['receiptId']
                state['revokeAttemptStarted'] = True
                save(root / 'case.json', state)
                with ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(service.execute, request)
                    waited = None
                    deadline = time.monotonic() + 0.6
                    try:
                        while time.monotonic() < deadline:
                            observer.rollback()
                            observer.execute('SET TRANSACTION READ ONLY')
                            rows = observer.execute('SELECT pid,pg_blocking_pids(pid) AS blockers '
                                'FROM pg_stat_activity WHERE datname=%s AND usename=%s',
                                (state['database'], 'aos_budget_renewal_issuer_call')).fetchall()
                            waited = next((r for r in rows if reader.info.backend_pid in r['blockers']), None)
                            if waited is not None:
                                break
                            time.sleep(0.005)
                    finally:
                        if winner == 'reader_commit': reader.commit()
                        else: reader.rollback()
                    # Observe this same future after releasing the reader, even
                    # when the bounded waiter observation did not succeed.
                    state['results']['revoke'] = future.result(timeout=5)
                    state['writerObservedWaitingForReader'] = waited
                    save(root / 'case.json', state)
                    assert waited is not None, 'no lock proof; timeout is not evidence'
            save(root / 'case.json', state)
        with actual_runtime() as current:
            if entry == 'cost':
                with pytest.raises(BudgetCostRuntimeBlocked) as error:
                    fact(current, receipt)
                assert isinstance(error.value.__cause__, psycopg.errors.InsufficientPrivilege)
                assert 'CHILD_REVOKED' in str(error.value.__cause__)
            else:
                with pytest.raises(psycopg.errors.InsufficientPrivilege, match='CHILD_REVOKED'):
                    fact(current, receipt)
            current.rollback()
    facts = window_case_facts(state)
    assert facts == dict(receipts=dict(propose=1, decide=1, consume=1, revoke=1),
        binding=1, fence=dict(version=3, revoked=True), policy=1, price=1)
    after = risk_fingerprint()
    if entry == 'cost':
        expected = [dict(row) for row in state['parentFencesBefore']]
        if winner == 'reader_commit':
            selected = [row for row in expected if (row['org_id'], row['project_id'], row['budget_id'], row['revision'])
                == (*SCOPE.key, receipt['budgetRef']['assetId'], receipt['budgetRef']['revision'])]
            assert len(selected) == 1
            selected[0]['version'] += 1
        with isolated_owner() as conn:
            actual = conn.execute('SELECT * FROM public.aip_budget_cost_runtime_fence '
                'ORDER BY org_id,project_id,budget_id,revision').fetchall()
        assert actual == expected
        state['parentFencesAfter'] = actual
        state['expectedParentFenceIncrement'] = int(winner == 'reader_commit')
        assert {k:v for k,v in after.items() if k != 'aip_budget_cost_runtime_fence'} == {
            k:v for k,v in state['riskBefore'].items() if k != 'aip_budget_cost_runtime_fence'}
    else:
        assert after == state['riskBefore']
    state['facts'] = facts
    state['riskUnchanged'] = entry == 'native' or winner != 'reader_commit'
    state['riskLedgersUnchanged'] = True
    state['verified'] = True
    save(root / 'case.json', state)

@pytest.fixture
def runtime_deployment_config(tmp_path, monkeypatch):
    # Pins are supplied from the separately recorded installer/readback,
    # never initialized from the database catalog being checked by admission.
    body = json.loads(Path(os.environ['AOS_WINDOW_RUNTIME_TEST_PINS_FILE']).read_text())
    assert body['expectedDatabase'] == os.environ['AOS_POLICY_WINDOW_TEST_DATABASE']
    path = tmp_path / 'runtime-admission.json'
    path.touch(mode=0o600)
    path.write_text(json.dumps(body))
    monkeypatch.setenv('AOS_POLICY_WINDOW_RUNTIME_CONFIG', str(path))
    return path


@pytest.mark.parametrize('host', [False, True])
def test_runtime_adapter_connects_original_fee_gate_without_new_allowance(
        actual_runtime, runtime_deployment_config, host):
    from aos_api.ecommerce_growth_host_ports import HostTransaction
    root = Path(os.environ['AOS_WINDOW_RUNTIME_KNOWN_CASE_DIR'])
    state = json.loads((root / 'case.json').read_text())
    parent = json.loads((root / 'parent.json').read_text())
    receipt = state['results']['consume']
    def ref(item):
        return BudgetExactRef(resourceType=item['assetType'], resourceId=item['assetId'],
            revision=item['revision'], contentHash='sha256:' + item['contentHash'])
    with actual_runtime() as native:
        conn = HostTransaction(native) if host else native
        price = require_cost_risk(conn, SCOPE, ref(receipt['budgetRef']), ref(receipt['priceRef']),
                                 parent['proposal']['basis']['perRequestRiskMinor'])
        assert price.price_snapshot_id == receipt['priceRef']['assetId']
        assert price.development_cost_authorization.approval_ref == receipt['decisionId']
        native.rollback()


@pytest.mark.parametrize('policy_case', ['exact', 'wrong', 'missing'])
def test_formal_reader_binds_current_child_policy_under_actual_evaluator(
        actual_evaluator, runtime_deployment_config, policy_case):
    from aos_api.aip_budget_cost_runtime import read_formal_budget_fact, BudgetCostRuntimeBlocked
    root = Path(os.environ['AOS_WINDOW_RUNTIME_KNOWN_CASE_DIR'])
    state = json.loads((root / 'case.json').read_text())
    parent = json.loads((root / 'parent.json').read_text())
    receipt = state['results']['consume']
    policy = dict(receipt['policyRef'])
    if policy_case == 'wrong':
        policy['contentHash'] = '0' * 64
    elif policy_case == 'missing':
        policy = None
    with actual_evaluator() as conn:
        args = dict(conn=conn, scope=SCOPE, budget_ref=receipt['budgetRef'],
            price_ref=receipt['priceRef'], provider_ref=parent['proposal']['basis']['provider'],
            budget_policy_ref=policy)
        if policy_case == 'exact':
            fact = read_formal_budget_fact(**args)
            assert fact.policy_window_fact['policyRef'] == receipt['policyRef']
            assert fact.policy_window_fact['receiptId'] == receipt['receiptId']
            assert fact.policy_window_fact['factOnly'] is True
            assert fact.policy_window_fact['activationEligible'] is False
        else:
            with pytest.raises(BudgetCostRuntimeBlocked,
                               match='FORMAL_BUDGET_CHILD_POLICY_BINDING_REQUIRED'):
                read_formal_budget_fact(**args)
        conn.rollback()


def test_prepare_new_adapter_child_for_current_window(native_roles, window_signer, tmp_path, monkeypatch):
    from datetime import timedelta
    from aos_api.aip_budget_policy_window_service import (
        WindowService, WindowRequest, load_protected_config, _FORBIDDEN_ENV,
    )
    old = Path(os.environ['AOS_WINDOW_RUNTIME_KNOWN_CASE_DIR'])
    prior = json.loads((old / 'case.json').read_text())
    parent_raw = (old / 'parent.json').read_bytes()
    parent = json.loads(parent_raw)
    assert prior['parentKnownConsumed'] and prior['database'] == os.environ['AOS_POLICY_WINDOW_TEST_DATABASE']
    assert prior['cluster'] == os.environ['AOS_POLICY_WINDOW_TEST_CLUSTER']
    root = Path('/tmp/window-runtime-adapter-child-r1')
    assert not root.exists(), 'existing preparation must be reconciled, never replayed'
    root.mkdir(mode=0o700)
    with (root / 'parent.json').open('xb') as stream:
        os.chmod(stream.fileno(), 0o600)
        stream.write(parent_raw)
        stream.flush()
        os.fsync(stream.fileno())
    with isolated_owner() as conn:
        found = conn.execute("SELECT result_ref FROM public.aip_budget_receipt WHERE receipt_id=%s "
            "AND operation='budget_revision.activate_cost'", (prior['commands']['propose']['parentConsumptionReceiptId'],)).fetchone()
        assert found and found['result_ref']['resourceId'] == prior['results']['consume']['budgetRef']['assetId']
        now = conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
    target = parent['proposal']['target']
    start = max(now - timedelta(minutes=1), datetime.fromisoformat(target['effectiveFrom'].replace('Z', '+00:00')))
    until = min(now + timedelta(hours=1), datetime.fromisoformat(target['effectiveUntil'].replace('Z', '+00:00')) - timedelta(seconds=1))
    assert now + timedelta(minutes=2) < until
    wire_time = lambda value: value.isoformat(timespec='microseconds').replace('+00:00', 'Z')
    command = dict(prior['commands']['propose'], idempotencyKey='adapter-child-' + secrets.token_hex(12),
                   effectiveFrom=wire_time(start), effectiveUntil=wire_time(until))
    state = dict(task='qyh-policy-window-runtime-bridge-r3-20261017', database=prior['database'],
        cluster=prior['cluster'], parentKnownConsumed=True, originalParentSha256=hashlib.sha256(parent_raw).hexdigest(),
        testOnlySyntheticChecker=True, commands={}, results={})
    save(root / 'case.json', state)
    attempts = root / 'attempts'
    attempts.mkdir(mode=0o700)
    service = WindowService(load_protected_config(private_window_service_config(native_roles, tmp_path)), attempts)
    _, signed, _ = window_signer
    with monkeypatch.context() as clean:
        for name in (*_FORBIDDEN_ENV, 'PGREQUIREAUTH'):
            clean.delenv(name, raising=False)
        for operation in ('propose', 'decide', 'consume'):
            if operation != 'propose':
                proposal = state['results']['propose']
                command = dict(schemaVersion=1, orgId=SCOPE.org_id, projectId=SCOPE.project_id,
                    idempotencyKey=state['commands']['propose']['idempotencyKey'] + '.' + operation,
                    proposalId=proposal['proposalId'], proposalHash=proposal['proposalHash'],
                    targetPairHash=proposal['targetPairHash'])
                if operation == 'decide': command['decision'] = 'approved'
                else:
                    decision = state['results']['decide']
                    command.update(decisionId=decision['decisionId'], decisionHash=decision['decisionHash'])
            state['commands'][operation] = command
            save(root / 'case.json', state)
            envelope = dict(schemaVersion=1, mode='execute', operation=operation, command=command)
            if operation == 'decide': envelope['bearerToken'] = SecretStr(signed())
            result = service.execute(WindowRequest.model_validate(envelope))
            state['results'][operation] = result
            save(root / 'case.json', state)
            assert result.get('operation') == operation
    state['verifiedNewChildConsumption'] = True
    save(root / 'case.json', state)
