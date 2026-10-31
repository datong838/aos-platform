"""Dedicated fresh-cluster SQL-role proof; child signed gateway remains pending."""
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
import json
import os
from pathlib import Path
import secrets

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row
import pytest

from aos_api.db import get_dsn
from aos_api.aip_budget_cost_basis import BudgetCostBasisProposal
from aos_api.aip_budget_policy_window_commands import WindowProposeCommand
from tests.aip.test_budget_cost_consumer_pg import caller, approved, consume
from tests.aip.test_budget_cost_issuer_pg import issuer_factory
from tests.aip.test_network_consumer_signed_https_pg import https_signer
from tests.aip.test_network_consumer_boundary_pg import isolated_owner, SCOPE

MACHINE = 'postgres-service:aos_budget_renewal_maker_call'
CHECKER = '6f31cfdc-a26c-4f1f-ad6b-95a8559cc657'
TABLES = tuple('aip_budget_policy_window_' + n for n in ('proposal', 'decision', 'receipt', 'binding', 'fence'))
ROLES = {'maker': 'aos_budget_renewal_maker_call', 'issuer': 'aos_budget_renewal_issuer_call',
         'consumer': 'aos_budget_consumer_call'}


@pytest.fixture(scope='session', autouse=True)
def _isolated_postgres_database():
    """Pin the already-bootstrapped task DB; never fall back or create another."""
    assert os.environ.get('AOS_TEST_USE_SHARED_DATABASE') != '1'
    expected_db = os.environ['AOS_POLICY_WINDOW_TEST_DATABASE']
    expected_cluster = os.environ['AOS_POLICY_WINDOW_TEST_CLUSTER']
    assert expected_db.startswith('aos_test_') and expected_db.endswith('_ti4_test')
    with psycopg.connect(get_dsn()) as conn:
        assert conn.info.dbname == expected_db
        assert str(conn.execute('SELECT system_identifier FROM pg_control_system()').fetchone()[0]) == expected_cluster
        assert conn.execute('SELECT version_num FROM alembic_version').fetchone()[0] == 'a0v_163'
    yield


@pytest.fixture
def native_roles(caller, tmp_path):
    """Only this module's pinned cluster can provision ephemeral SQL callers."""
    with isolated_owner() as admin:
        parts = conninfo_to_dict(get_dsn())
        for role in (ROLES['maker'], ROLES['issuer']):
            assert admin.execute('SELECT rolcanlogin FROM pg_roles WHERE rolname=%s', (role,)).fetchone()['rolcanlogin'] is False
        paths = {}
        for role in (ROLES['maker'], ROLES['issuer']):
            password = secrets.token_urlsafe(32)
            admin.execute(sql.SQL('ALTER ROLE {} LOGIN PASSWORD {}').format(sql.Identifier(role), sql.Literal(password)))
            path = tmp_path / (role + '.pgpass'); path.touch(mode=0o600)
            path.write_text(f"{parts['host']}:{parts['port']}:{parts['dbname']}:{role}:{password}\n")
            paths[role] = path
        admin.commit()

        @contextmanager
        def connect(purpose):
            if purpose == 'consumer':
                with caller() as conn: yield conn
                return
            role = ROLES[purpose]
            with psycopg.connect(host=parts['host'], port=parts['port'], dbname=parts['dbname'],
                    user=role, passfile=str(paths[role]), row_factory=dict_row,
                    options='-c statement_timeout=15000 -c lock_timeout=5000') as conn:
                conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)", SCOPE.key)
                yield conn
        try:
            yield connect
        finally:
            for role, path in paths.items():
                admin.execute(sql.SQL('ALTER ROLE {} NOLOGIN PASSWORD NULL').format(sql.Identifier(role)))
            admin.commit()
            for path in paths.values():
                path.write_text('# removed\n')


def invoke(conn, operation, command, actor=None):
    name = 'public.aip_policy_window_' + operation + '_v1'
    query = sql.SQL('SELECT {}(%s::jsonb' + (',%s' if actor is not None else '') + ') AS result').format(sql.SQL(name))
    return conn.execute(query, [json.dumps(command)] + ([actor] if actor is not None else [])).fetchone()['result']


def totals():
    with isolated_owner() as conn:
        return tuple(conn.execute(sql.SQL('SELECT count(*) AS n FROM {}').format(sql.Identifier(t))).fetchone()['n'] for t in TABLES)


def test_closed_native_installation_has_no_shared_write_entry():
    with isolated_owner() as conn:
        seal = json.loads(conn.execute("SELECT obj_description('public.aip_budget_policy_window_proposal'::regclass,'pg_class') AS value").fetchone()['value'])
        assert len(seal['functions']) == 22 and len(seal['relations']) == 19
        assert all(not conn.execute('SELECT rolcanlogin FROM pg_roles WHERE rolname=%s', (r,)).fetchone()['rolcanlogin'] for r in ROLES.values())
        for op, role in [('propose', ROLES['maker']), ('decide', ROLES['issuer']), ('revoke', ROLES['issuer']), ('consume', ROLES['consumer'])]:
            sig = f'public.aip_policy_window_{op}_v1(jsonb' + (',text)' if op in {'decide', 'revoke'} else ')')
            assert conn.execute("SELECT has_function_privilege(%s,%s,'EXECUTE') AS value", (role, sig)).fetchone()['value']
            assert not conn.execute("SELECT has_function_privilege('aos_runtime',%s,'EXECUTE') AS value", (sig,)).fetchone()['value']
        for table in TABLES:
            for role in ROLES.values():
                for privilege in ('SELECT', 'INSERT', 'UPDATE', 'DELETE'):
                    assert not conn.execute('SELECT has_table_privilege(%s,%s,%s) AS value', (role, table, privilege)).fetchone()['value']


def test_shared_database_login_cannot_propose_even_with_synthetic_command():
    before = totals()
    with isolated_owner() as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege): invoke(conn, 'propose', {})
    assert totals() == before


def prepare_parent(issuer_factory, https_signer, native_roles):
    marker = Path(os.environ['AOS_POLICY_WINDOW_PARENT_CASE']) if os.environ.get('AOS_POLICY_WINDOW_PARENT_CASE') else None
    state = json.loads(marker.read_text()) if marker and marker.exists() else None
    if state:
        assert state['database'] == os.environ['AOS_POLICY_WINDOW_TEST_DATABASE']
        parent = BudgetCostBasisProposal.from_canonical_payload(state['proposal'])
        saved, decision = state['saved'], state['decision']
    else:
        _, _, parent, saved, decision = approved(issuer_factory, https_signer)
        state = dict(database=os.environ['AOS_POLICY_WINDOW_TEST_DATABASE'], proposal=parent.canonical_payload(),
                     saved=saved, decision=decision)
        if marker: marker.write_text(json.dumps(state))
    with isolated_owner() as conn:
        prior = conn.execute("SELECT result_ref FROM aip_budget_receipt WHERE org_id=%s AND project_id=%s "
            "AND operation='budget_revision.activate_cost' AND idempotency_key=%s", (*SCOPE.key, saved['proposalId'])).fetchone()
    if prior:
        parent_receipt = prior['result_ref']
    else:
        with native_roles('consumer') as conn: parent_receipt = consume(conn, saved, decision)
    if state.get('command'): return state['command'], parent
    with isolated_owner() as conn:
        for subject in (MACHINE, CHECKER):
            conn.execute("INSERT INTO meta_membership(org_id,project_id,subject,role) VALUES(%s,%s,%s,'admin') "
                         'ON CONFLICT(org_id,project_id,subject) DO NOTHING', (*SCOPE.key, subject))
        conn.commit()
    now = datetime.now(UTC)
    command = WindowProposeCommand(schemaVersion=1, orgId=SCOPE.org_id, projectId=SCOPE.project_id,
        idempotencyKey='window-parent-' + secrets.token_hex(12), parentCostProposalId=saved['proposalId'],
        parentCostProposalHash=saved['proposalHash'], parentCostDecisionId=decision['decisionId'],
        parentConsumptionReceiptId=parent_receipt['receiptId'],
        expectedBudgetRef=dict(assetType='BudgetRevision', assetId=parent_receipt['resourceId'],
            revision=parent_receipt['revision'], contentHash=parent_receipt['contentHash']),
        expectedBudgetHeadVersion=parent.expected_head_version + 1, expectedProviderRef=parent.basis.provider,
        expectedProviderModelId=parent.basis.provider_model_id,
        effectiveFrom=max(parent.target.effective_from, now-timedelta(minutes=1)),
        effectiveUntil=now+timedelta(hours=1))
    state['command'] = command.canonical_payload()
    if marker: marker.write_text(json.dumps(state))
    return state['command'], parent


def test_native_roles_create_pair_and_receipt_without_expanding_parent_risk(native_roles, issuer_factory, https_signer):
    command, parent = prepare_parent(issuer_factory, https_signer, native_roles)
    before = totals()
    with isolated_owner() as conn:
        done = {r['operation'] for r in conn.execute('SELECT operation FROM aip_budget_policy_window_receipt WHERE '
            'org_id=%s AND project_id=%s AND idempotency_key=ANY(%s)',
            (*SCOPE.key, [command['idempotencyKey'], command['idempotencyKey']+'.review', command['idempotencyKey']+'.consume'])).fetchall()}
    with native_roles('maker') as conn: proposal = invoke(conn, 'propose', command)
    review = dict(schemaVersion=1, orgId=SCOPE.org_id, projectId=SCOPE.project_id,
        idempotencyKey=command['idempotencyKey']+'.review', proposalId=proposal['proposalId'],
        proposalHash=proposal['proposalHash'], targetPairHash=proposal['targetPairHash'], decision='approved')
    with native_roles('issuer') as conn: decision = invoke(conn, 'decide', review, CHECKER)
    consume_command = {k: v for k, v in review.items() if k != 'decision'}
    consume_command.update(idempotencyKey=command['idempotencyKey']+'.consume',
        decisionId=decision['decisionId'], decisionHash=decision['decisionHash'])
    with native_roles('consumer') as conn: result = invoke(conn, 'consume', consume_command)
    with native_roles('consumer') as conn: assert invoke(conn, 'consume', consume_command) == result
    delta = (int('propose' not in done), int('decide' not in done), 3-len(done),
             int('consume' not in done), int('propose' not in done))
    assert totals() == tuple(n+d for n, d in zip(before, delta))
    assert result['budgetRef']['assetId'] == parent.target.budget_id
    assert result['policyRef']['revision'] == result['priceRef']['revision'] == 1
    assert result['activationEligible'] is False


@pytest.fixture
def committed_case():
    """Reconcile the original proof; never seed a substitute for missing receipts."""
    state = json.loads(Path(os.environ['AOS_POLICY_WINDOW_PARENT_CASE']).read_text())
    command = state['command']
    with isolated_owner() as conn:
        rows = conn.execute('SELECT operation,payload FROM aip_budget_policy_window_receipt WHERE '
            'org_id=%s AND project_id=%s AND idempotency_key=ANY(%s)',
            (*SCOPE.key, [command['idempotencyKey'], command['idempotencyKey']+'.review',
                         command['idempotencyKey']+'.consume'])).fetchall()
    receipts = {r['operation']: r['payload'] for r in rows}
    assert set(receipts) == {'propose', 'decide', 'consume'}, 'original committed proof required'
    return command, receipts


def test_same_key_changed_content_is_rejected_without_effect(native_roles, committed_case):
    command, _ = committed_case
    altered = dict(command, expectedBudgetHeadVersion=command['expectedBudgetHeadVersion'] + 1)
    before = totals()
    with pytest.raises(psycopg.errors.CheckViolation, match='POLICY_WINDOW_RECEIPT_CONFLICT'):
        with native_roles('maker') as conn: invoke(conn, 'propose', altered)
    assert totals() == before


def test_cross_tenant_command_is_rejected_without_effect(native_roles, committed_case):
    command, _ = committed_case
    before = totals()
    with pytest.raises(psycopg.errors.InvalidParameterValue, match='POLICY_WINDOW_EXACT_COMMAND_REQUIRED'):
        with native_roles('maker') as conn: invoke(conn, 'propose', dict(command, orgId='dev-org'))
    assert totals() == before


def test_maker_cannot_execute_checker_entry(native_roles, committed_case):
    _, receipts = committed_case
    before = totals()
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with native_roles('maker') as conn: invoke(conn, 'decide', receipts['decide']['command'], CHECKER)
    assert totals() == before


def test_readonly_reconcile_distinguishes_known_unknown_and_actor(native_roles, committed_case):
    command, receipts = committed_case
    before = totals()
    with native_roles('maker') as conn:
        conn.rollback()
        conn.execute('SET TRANSACTION READ ONLY')
        conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)", SCOPE.key)
        def query(value, actor):
            return conn.execute('SELECT public.aip_policy_window_reconcile_v1(%s::jsonb,%s,%s) AS result',
                                (json.dumps(value), 'propose', actor)).fetchone()['result']
        assert query(command, MACHINE) == dict(status='observed', receipt=receipts['propose'], activationEligible=False)
        assert query(dict(command, idempotencyKey=command['idempotencyKey']+'.unknown'), MACHINE) == dict(
            status='unresolved', activationEligible=False)
        with pytest.raises(psycopg.errors.InsufficientPrivilege, match='POLICY_WINDOW_ORIGINAL_ACTOR_REQUIRED'):
            with conn.transaction(): query(command, CHECKER)
    assert totals() == before


def test_revocation_duplicate_gate_and_outer_rollback(native_roles, committed_case):
    command, receipts = committed_case
    decision = receipts['decide']
    revoke = dict(schemaVersion=1, orgId=SCOPE.org_id, projectId=SCOPE.project_id,
        idempotencyKey=command['idempotencyKey']+'.rollback-revoke', proposalId=decision['proposalId'],
        proposalHash=decision['proposalHash'], originalDecisionId=decision['decisionId'],
        originalDecisionHash=decision['decisionHash'], reason='isolated transaction rollback proof')
    before = totals()
    with isolated_owner() as owner:
        fence_before = owner.execute('SELECT version,revoked FROM aip_budget_policy_window_fence '
            'WHERE org_id=%s AND project_id=%s AND proposal_id=%s', (*SCOPE.key, decision['proposalId'])).fetchone()
    with native_roles('issuer') as conn:
        result = invoke(conn, 'revoke', revoke, CHECKER)
        assert result['decision'] == 'revoked' and result['activationEligible'] is False
        assert invoke(conn, 'revoke', revoke, CHECKER) == result
        with pytest.raises(psycopg.errors.CheckViolation, match='POLICY_WINDOW_ALREADY_REVOKED'):
            with conn.transaction():
                invoke(conn, 'revoke', dict(revoke, idempotencyKey=revoke['idempotencyKey']+'.other'), CHECKER)
        conn.rollback()
    assert totals() == before
    with isolated_owner() as owner:
        assert owner.execute('SELECT version,revoked FROM aip_budget_policy_window_fence '
            'WHERE org_id=%s AND project_id=%s AND proposal_id=%s', (*SCOPE.key, decision['proposalId'])).fetchone() == fence_before


@pytest.mark.parametrize('actual', ['maker', 'issuer', 'consumer'])
@pytest.mark.parametrize('requested', ['maker', 'issuer', 'consumer'])
def test_window_identity_requires_actual_purpose_session(native_roles, actual, requested):
    from aos_api.aip_budget_policy_window_identity import database_identity, WindowIdentityBlocked
    before = totals()
    if actual == requested:
        with native_roles(actual) as conn:
            assert database_identity(conn, requested, read_only=False) == ROLES[actual]
    else:
        with pytest.raises(WindowIdentityBlocked, match='DATABASE_IDENTITY_PROFILE_REQUIRED'):
            with native_roles(actual) as conn: database_identity(conn, requested, read_only=False)
    assert totals() == before


@pytest.mark.parametrize('purpose', ['maker', 'issuer', 'consumer'])
def test_window_identity_enforces_transaction_mode_and_tenant(native_roles, purpose):
    from aos_api.aip_budget_policy_window_identity import database_identity, WindowIdentityBlocked
    before = totals()
    with native_roles(purpose) as conn:
        with pytest.raises(WindowIdentityBlocked, match='EXACT_TRANSACTION_PROFILE_REQUIRED'):
            database_identity(conn, purpose, read_only=True)
        conn.rollback()
        conn.execute('SET TRANSACTION READ ONLY')
        conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)", SCOPE.key)
        assert database_identity(conn, purpose, read_only=True) == ROLES[purpose]
        conn.execute("SELECT set_config('aos.org_id','dev-org',true)")
        with pytest.raises(WindowIdentityBlocked, match='DATABASE_IDENTITY_PROFILE_REQUIRED'):
            database_identity(conn, purpose, read_only=True)
    assert totals() == before


@pytest.fixture
def window_signer(monkeypatch):
    """Temporary isolated RSA/JWKS, never a real customer signing key."""
    if os.environ.get('AOS_POLICY_WINDOW_ISOLATED_SIGNER') != '1':
        pytest.skip('explicit isolated signer namespace required')
    import threading
    import time
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import jwt
    from cryptography.hazmat.primitives.asymmetric import rsa
    from pydantic import SecretStr
    from aos_api.aip_budget_policy_window_identity import authenticate_checker, CheckerBinding, WindowIdentityBlocked
    from tests.aip.test_budget_policy_renewal_identity import protected_environment

    env = protected_environment()
    for name, value in env.items(): monkeypatch.setenv(name, value)
    binding = CheckerBinding(CHECKER, 'a'*64, tuple(env.items()))
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    jwk.update(kid='window-native-synthetic-r1', alg='RS256', use='sig')
    requests = []
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            if self.path != '/realms/qyh-local/protocol/openid-connect/certs':
                self.send_error(404)
                return
            body = json.dumps({'keys': [jwk]}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *args): pass
    server = ThreadingHTTPServer(('127.0.0.1', 18448), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    def signed(**changes):
        claims = dict(iss=env['AOS_OIDC_ISSUER'], aud='aos-api', sub=CHECKER,
            iat=int(time.time()), exp=int(time.time())+120,
            org_id='org-org', project_id='dev-project', roles=['admin'])
        claims.update(changes)
        return jwt.encode(claims, key, algorithm='RS256', headers={'kid': jwk['kid']})
    try:
        yield binding, signed, requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
        assert not thread.is_alive()


def test_window_checker_verifies_real_signature_in_isolated_namespace(native_roles, committed_case, monkeypatch, tmp_path, window_signer):
    """Synthetic cryptographic identity proof only, never actual human consent."""
    import time
    from pydantic import SecretStr
    from aos_api.aip_budget_policy_window_identity import authenticate_checker, WindowIdentityBlocked
    binding, signed, requests = window_signer
    before = totals()
    with native_roles('issuer') as conn:
        good = signed()
        assert authenticate_checker(SecretStr(good), binding=binding, conn=conn, read_only=False).subject == CHECKER
        for token in (signed(sub='another-member'), signed(org_id='dev-org'), signed(aud='another-app'),
                      signed(exp=int(time.time())-60), good.rsplit('.', 1)[0]+'.invalid-signature'):
            with pytest.raises(WindowIdentityBlocked, match='ORIGINAL_HUMAN_IDENTITY_REQUIRED'):
                authenticate_checker(SecretStr(token), binding=binding, conn=conn, read_only=False)
        # Same exact signed identity, now through the pinned native store.
        import hashlib
        from aos_api.aip_budget_policy_window_commands import WindowDecisionCommand
        from aos_api.aip_budget_policy_window_store import WindowAuthorityStore
        with isolated_owner() as owner:
            raw = owner.execute("SELECT obj_description('public.aip_budget_policy_window_proposal'::regclass,'pg_class') AS seal").fetchone()['seal']
            legacy = owner.execute("SELECT obj_description('public.aip_budget_policy_renewal_proposal'::regclass,'pg_class') AS seal").fetchone()['seal']
        conn.rollback()
        receipt = committed_case[1]['decide']
        store = WindowAuthorityStore(conn, manifest_sha256=hashlib.sha256(raw.encode()).hexdigest(), legacy_manifest_sha256=hashlib.sha256(legacy.encode()).hexdigest(), checker_binding=binding)
        command = WindowDecisionCommand.model_validate(receipt['command'])
        assert store.reconcile(command, token=SecretStr(good)) == dict(status='observed', receipt=receipt, activationEligible=False)
    from aos_api.aip_budget_policy_window_service import WindowService, WindowRequest, load_protected_config, _FORBIDDEN_ENV
    path = private_window_service_config(native_roles, tmp_path)
    config = load_protected_config(path)
    attempts = tmp_path/'signed-attempts'
    attempts.mkdir(mode=0o700)
    service = WindowService(config, attempts)
    request = WindowRequest(schemaVersion=1, mode='execute', operation='decide',
                            command=receipt['command'], bearerToken=SecretStr(good))
    with monkeypatch.context() as clean:
        for name in (*_FORBIDDEN_ENV, 'PGREQUIREAUTH'): clean.delenv(name, raising=False)
        assert service.execute(request) == receipt
        assert service.execute(request) == dict(status='observed', receipt=receipt, activationEligible=False)
        markers = list(attempts.iterdir())
        assert len(markers) == 1 and good not in markers[0].read_text()
    assert requests and totals() == before


@pytest.mark.parametrize('purpose,operation', [('maker', 'propose'), ('consumer', 'consume')])
def test_window_store_reads_pinned_native_history(native_roles, committed_case, purpose, operation):
    import hashlib
    from aos_api.aip_budget_policy_window_commands import WindowConsumeCommand
    from aos_api.aip_budget_policy_window_store import WindowAuthorityStore, WindowStoreBlocked
    command, receipts = committed_case
    cls = WindowProposeCommand if operation == 'propose' else WindowConsumeCommand
    original = cls.model_validate(receipts[operation]['command'])
    with isolated_owner() as owner:
        raw = owner.execute("SELECT obj_description('public.aip_budget_policy_window_proposal'::regclass,'pg_class') AS seal").fetchone()['seal']
        legacy = owner.execute("SELECT obj_description('public.aip_budget_policy_renewal_proposal'::regclass,'pg_class') AS seal").fetchone()['seal']
    pin = hashlib.sha256(raw.encode()).hexdigest()
    before = totals()
    with native_roles(purpose) as conn:
        conn.rollback()
        store = WindowAuthorityStore(conn, manifest_sha256=pin, legacy_manifest_sha256=hashlib.sha256(legacy.encode()).hexdigest())
        assert store.reconcile(original) == dict(status='observed', receipt=receipts[operation], activationEligible=False)
        unknown = cls.model_validate(dict(original.canonical_payload(), idempotencyKey=command['idempotencyKey']+'.store-unknown'))
        assert store.reconcile(unknown) == dict(status='unresolved', activationEligible=False)
        wrong = WindowAuthorityStore(conn, manifest_sha256='0'*64, legacy_manifest_sha256=hashlib.sha256(legacy.encode()).hexdigest())
        with pytest.raises(WindowStoreBlocked, match='PINNED_MANIFEST_REQUIRED'):
            wrong.reconcile(original)
        bad_legacy = WindowAuthorityStore(conn, manifest_sha256=pin, legacy_manifest_sha256='0'*64)
        with pytest.raises(WindowStoreBlocked, match='PINNED_LEGACY_MANIFEST_REQUIRED'):
            bad_legacy.reconcile(original)
    assert totals() == before


def test_window_store_rejects_response_changes_before_return(committed_case):
    import copy
    from aos_api.aip_budget_policy_window_commands import WindowConsumeCommand
    from aos_api.aip_budget_policy_window_store import WindowAuthorityStore, WindowStoreBlocked
    _, receipts = committed_case
    result = receipts['consume']
    command = WindowConsumeCommand.model_validate(result['command'])
    WindowAuthorityStore.validate_result(result, command, reconcile=False)
    for field, value in [('activationEligible', True), ('receiptId', 'changed'), ('decisionHash', '0'*64),
                         ('targetPairHash', '0'*64), ('requestHash', '0'*64), ('proposalId', 'another')]:
        altered = copy.deepcopy(result)
        altered[field] = value
        with pytest.raises(WindowStoreBlocked, match='NATIVE_RESULT_CONTRACT_REQUIRED'):
            WindowAuthorityStore.validate_result(altered, command, reconcile=False)


def private_window_service_config(native_roles, tmp_path):
    """Temporary credentials/config only inside the pinned synthetic cluster."""
    import hashlib
    from tests.aip.test_budget_policy_renewal_connection import closed_config
    from aos_api.aip_budget_policy_window_service import PACKAGE_FILES, ROOT
    path, value = closed_config(tmp_path)
    value['schemaVersion'] = 'aos.budget-policy-window.private/v1'
    value['enabled'] = True
    parts = conninfo_to_dict(get_dsn())
    with isolated_owner() as owner:
        for key, table in [('nativeManifestSha256', 'aip_budget_policy_window_proposal'),
                           ('legacyManifestSha256', 'aip_budget_policy_renewal_proposal')]:
            raw = owner.execute('SELECT obj_description(%s::regclass,%s) AS seal', ('public.'+table, 'pg_class')).fetchone()['seal']
            value[key] = hashlib.sha256(raw.encode()).hexdigest()
    for purpose, role in ROLES.items():
        profile = value['profiles'][purpose]
        profile.pop('manifestSha256')
        credential = tmp_path/('consumer.pgpass' if purpose == 'consumer' else role+'.pgpass')
        target = Path(profile['passfile'])
        target.write_bytes(credential.read_bytes())
        profile.update(host=parts['host'], port=int(parts['port']), database=parts['dbname'], user=role,
                       passfileSha256=hashlib.sha256(target.read_bytes()).hexdigest())
    value['packageSources'] = {f: hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in PACKAGE_FILES}
    path.write_text(json.dumps(value))
    return path


@pytest.mark.parametrize('operation,purpose', [('propose', 'maker'), ('consume', 'consumer')])
def test_window_service_scram_pinned_history_and_durable_no_resend(native_roles, committed_case, tmp_path, monkeypatch, operation, purpose):
    from aos_api.aip_budget_policy_window_service import WindowService, WindowRequest, load_protected_config, _FORBIDDEN_ENV
    _, receipts = committed_case
    path = private_window_service_config(native_roles, tmp_path)
    config = load_protected_config(path)
    attempts = tmp_path/'attempts'
    attempts.mkdir(mode=0o700)
    service = WindowService(config, attempts)
    request = WindowRequest(schemaVersion=1, mode='execute', operation=operation, command=receipts[operation]['command'])
    before = totals()
    with monkeypatch.context() as env:
        for key in (*_FORBIDDEN_ENV, 'PGREQUIREAUTH'): env.delenv(key, raising=False)
        # All service connections require SCRAM, exact roles, and both fixed seals.
        # This original committed key only returns its history, creating no pair.
        assert service.execute(request) == receipts[operation]
        assert len(list(attempts.iterdir())) == 1
        again = service.execute(request)
        assert again == dict(status='observed', receipt=receipts[operation], activationEligible=False)
        assert len(list(attempts.iterdir())) == 1
        marker = next(attempts.iterdir()).read_text()
        assert 'bearerToken' not in marker and 'password' not in marker
        altered = request.command.canonical_payload()
        if operation == 'propose': altered['expectedBudgetHeadVersion'] += 1
        else: altered['decisionHash'] = '0'*64
        conflict = WindowRequest(schemaVersion=1, mode='execute', operation=operation, command=altered)
        assert service.execute(conflict) == dict(operation=operation, requestHash=conflict.command.request_hash,
                                                status='conflict', activationEligible=False)
        assert len(list(attempts.iterdir())) == 1
    assert totals() == before


def persist_signed_case(path, value):
    """Atomic synthetic intent only; no token, credential, or automatic reset."""
    temporary = path.with_suffix('.next')
    assert not path.is_symlink()
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(directory)
        finally: os.close(directory)
    except Exception:
        # Keep an incomplete .next for readonly reconciliation, never reset it.
        raise


def original_risk_fingerprint():
    with isolated_owner() as owner:
        return {name: owner.execute(sql.SQL("SELECT md5(COALESCE(jsonb_agg(to_jsonb(t) "
            "ORDER BY to_jsonb(t)::text),'[]'::jsonb)::text) AS value FROM public.{} t").format(
            sql.Identifier(name))).fetchone()['value'] for name in (
                'aip_budget_cost_runtime_fence', 'aip_budget_reservation', 'aip_budget_bucket',
                'aip_budget_head', 'aip_budget_revision', 'aip_budget_receipt')}


def run_signed_window_service_case(native_roles, committed_case, tmp_path, monkeypatch, window_signer, *, case_name, proxy=None):
    """New synthetic consent/COMMIT proof, never original failure recovery."""
    import stat
    from pydantic import SecretStr
    from aos_api.aip_budget_policy_window_service import (
        WindowService, WindowRequest, load_protected_config, COMMANDS, _FORBIDDEN_ENV,
    )
    from aos_api.aip_budget_store import canonical_hash
    _, signed, requests = window_signer
    config_path = private_window_service_config(native_roles, tmp_path)
    if proxy is not None:
        import hashlib
        value = json.loads(config_path.read_text())
        for profile in value['profiles'].values():
            credential = Path(profile['passfile'])
            raw = credential.read_bytes()
            old_prefix = f"{profile['host']}:{profile['port']}:".encode()
            assert raw.startswith(old_prefix)
            new_prefix = f"{profile['host']}:{proxy['port']}:".encode()
            credential.write_bytes(new_prefix+raw[len(old_prefix):])
            profile.update(port=proxy['port'], passfileSha256=hashlib.sha256(credential.read_bytes()).hexdigest())
        config_path.write_text(json.dumps(value))
    config = load_protected_config(config_path)
    assert case_name in {'window-service-signed-state-r1', 'window-service-unknown-commit-state-r1'}
    directory = Path('/tmp')/case_name
    directory.mkdir(mode=0o700, exist_ok=True)
    info = directory.lstat()
    assert stat.S_ISDIR(info.st_mode) and not directory.is_symlink()
    assert info.st_uid == os.geteuid() and stat.S_IMODE(info.st_mode) == 0o700
    case = directory/'case.json'
    attempts = directory/'attempts'
    attempts.mkdir(mode=0o700, exist_ok=True)
    assert not (directory/'case.next').exists(), 'incomplete intent needs readonly reconciliation'
    if case.exists():
        assert not case.is_symlink() and stat.S_IMODE(case.stat().st_mode) == 0o600
        state = json.loads(case.read_text())
    else:
        with isolated_owner() as owner:
            now = owner.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        parent_window = committed_case[1]['propose']['proposal']['parent']['budgetWindow']
        parent_from = datetime.fromisoformat(parent_window['effectiveFrom'].replace('Z', '+00:00'))
        parent_until = datetime.fromisoformat(parent_window['effectiveUntil'].replace('Z', '+00:00'))
        until = min(parent_until-timedelta(microseconds=1), now+timedelta(hours=1))
        assert until > now, 'parent expired; never extend or replace it implicitly'
        payload = dict(committed_case[0], idempotencyKey='window-signed-'+secrets.token_hex(12),
            effectiveFrom=max(parent_from, now-timedelta(seconds=1)).isoformat(), effectiveUntil=until.isoformat())
        command = WindowProposeCommand.model_validate(payload).canonical_payload()
        state = dict(schema='aos.synthetic-window-signed-case/v1',
            task='qyh-policy-window-native-authority-20261017',
            thread='01a13484-f019-7d82-94ce-812396db9124',
            database=os.environ['AOS_POLICY_WINDOW_TEST_DATABASE'], cluster=os.environ['AOS_POLICY_WINDOW_TEST_CLUSTER'],
            nativeManifestSha256=config.native_manifest_sha256, legacyManifestSha256=config.legacy_manifest_sha256,
            commands={'propose': command}, results={})
        persist_signed_case(case, state)
    assert (state['schema'], state['task'], state['thread'], state['database'], state['cluster']) == (
        'aos.synthetic-window-signed-case/v1', 'qyh-policy-window-native-authority-20261017',
        '01a13484-f019-7d82-94ce-812396db9124', os.environ['AOS_POLICY_WINDOW_TEST_DATABASE'],
        os.environ['AOS_POLICY_WINDOW_TEST_CLUSTER'])
    assert state['nativeManifestSha256'] == config.native_manifest_sha256
    assert state['legacyManifestSha256'] == config.legacy_manifest_sha256
    command = state['commands']['propose']
    assert command['parentCostProposalId'] == committed_case[0]['parentCostProposalId']
    assert command['idempotencyKey'] != committed_case[0]['idempotencyKey']
    keys = [command['idempotencyKey']+suffix for suffix in ('', '.review', '.consume')]
    before = totals()
    risk_before = original_risk_fingerprint()
    with isolated_owner() as owner:
        done = {r['operation'] for r in owner.execute('SELECT operation FROM aip_budget_policy_window_receipt '
            'WHERE org_id=%s AND project_id=%s AND idempotency_key=ANY(%s)', (*SCOPE.key, keys)).fetchall()}
    service = WindowService(config, attempts)
    with monkeypatch.context() as clean:
        for name in (*_FORBIDDEN_ENV, 'PGREQUIREAUTH'): clean.delenv(name, raising=False)
        for operation in ('propose', 'decide', 'consume'):
            if operation == 'decide':
                p = state['results']['propose']
                payload = dict(schemaVersion=1, orgId=SCOPE.org_id, projectId=SCOPE.project_id,
                    idempotencyKey=keys[1], proposalId=p['proposalId'], proposalHash=p['proposalHash'],
                    targetPairHash=p['targetPairHash'], decision='approved')
            elif operation == 'consume':
                d = state['results']['decide']
                payload = {k: v for k, v in state['commands']['decide'].items() if k != 'decision'}
                payload.update(idempotencyKey=keys[2], decisionId=d['decisionId'], decisionHash=d['decisionHash'])
            else: payload = command
            payload = COMMANDS[operation].model_validate(payload).canonical_payload()
            if operation in state['commands']: assert state['commands'][operation] == payload
            else:
                state['commands'][operation] = payload
                persist_signed_case(case, state)
            envelope = dict(schemaVersion=1, mode='execute', operation=operation, command=payload)
            if operation == 'decide': envelope['bearerToken'] = SecretStr(signed())
            request = WindowRequest.model_validate(envelope)
            result = service.execute(request)
            if proxy is not None and operation == 'consume' and 'consume' not in done:
                assert result.get('status') == 'observed' and 'receipt' in result, 'lost COMMIT must recover only through RO history'
                assert proxy['consumeExecutions'] == 1
            if 'receipt' in result: result = result['receipt']
            assert result.get('operation') == operation and result.get('requestHash') == request.command.request_hash, (
                'original key unresolved/rejected; keep intent and reconcile, never reseed')
            assert result['status'] == ('prepared' if operation == 'propose' else 'observed')
            if operation in state['results']: assert state['results'][operation] == result
            else:
                state['results'][operation] = result
                persist_signed_case(case, state)
            # A second execute must route through the durable marker to RO history.
            assert service.execute(request) == dict(status='observed', receipt=result, activationEligible=False)
        assert len(list(attempts.iterdir())) == 3
        assert all('bearerToken' not in p.read_text() and 'password' not in p.read_text() for p in attempts.iterdir())
    delta = (int('propose' not in done), int('decide' not in done), 3-len(done),
             int('consume' not in done), int('propose' not in done))
    assert totals() == tuple(n+d for n, d in zip(before, delta))
    assert original_risk_fingerprint() == risk_before
    result = state['results']['consume']
    assert result['budgetRef'] == committed_case[0]['expectedBudgetRef']
    assert result['activationEligible'] is False
    with isolated_owner() as owner:
        binding = owner.execute('SELECT binding_hash,payload FROM aip_budget_policy_window_binding '
            'WHERE org_id=%s AND project_id=%s AND binding_id=%s', (*SCOPE.key, result['bindingId'])).fetchone()
        assert binding['binding_hash'] == result['bindingHash'] == canonical_hash(dict(
            domain='aos.budget-policy-window.binding/v1', binding=binding['payload']))
        assert binding['payload']['policyRef'] == result['policyRef']
        assert binding['payload']['priceRef'] == result['priceRef']
        assert binding['payload']['parent']['budgetRef'] == result['budgetRef']
    state['verified'] = dict(originalRiskUnchanged=True, committedPair=True, durableMarkers=3,
                            nativeFunctionCallbackApproval=False, formalHumanConsent=False)
    if proxy is not None:
        event = json.loads((directory/'protocol-event.json').read_text())
        assert event['serverCommitConfirmed'] and event['backendReadyIdle']
        assert event['consumeExecutions'] == 1 and event['clientReadyForwarded'] is False
        assert proxy['consumeExecutions'] == (0 if 'consume' in done else 1)
        assert not proxy['errors']
        state['verified']['commitAckDropped'] = True
        state['verified']['protocolEvent'] = event
    persist_signed_case(case, state)
    assert requests


@contextmanager
def dropping_commit_ack_proxy():
    """Actual PGv3 transport fault, no packet/SQL/credential capture."""
    import select
    import socket
    import socketserver
    import struct
    import threading

    state = dict(port=None, consumeExecutions=0, reconcileCalls=0, dropped=False, errors=[])
    lock = threading.Lock()
    stop = threading.Event()
    connections = set()
    event_path = Path('/tmp/window-service-unknown-commit-state-r1/protocol-event.json')

    def exact(stream, length):
        data = bytearray()
        while len(data) < length:
            part = stream.recv(length-len(data))
            if not part: raise EOFError()
            data.extend(part)
        return bytes(data)

    class Handler(socketserver.BaseRequestHandler):
        def handle(self):
            upstream = None
            client = self.request
            try:
                client.settimeout(5)
                upstream = socket.create_connection(('127.0.0.1', 5432), timeout=5)
                with lock: connections.update((client, upstream))
                # Forward startup and optional SSL/GSS negotiation before typed frames.
                while True:
                    header = exact(client, 4)
                    length = struct.unpack('!I', header)[0]
                    assert 8 <= length <= 65536
                    body = exact(client, length-4)
                    upstream.sendall(header+body)
                    protocol = struct.unpack('!I', body[:4])[0]
                    if protocol in (80877103, 80877104):
                        response = exact(upstream, 1)
                        assert response == b'N', 'isolated fixture has no TLS/GSS encryption'
                        client.sendall(response)
                        continue
                    assert protocol == 196608
                    break
                native_seen = False
                commit_requested = False
                commit_complete = False
                native_error = False
                while not stop.is_set():
                    ready, _, _ = select.select((client, upstream), (), (), 0.2)
                    for source in ready:
                        kind = exact(source, 1)
                        header = exact(source, 4)
                        length = struct.unpack('!I', header)[0]
                        assert 4 <= length <= 16*1024*1024
                        body = exact(source, length-4)
                        if source is client:
                            if kind in (b'P', b'Q'):
                                if b'public.aip_policy_window_consume_v1(' in body:
                                    native_seen = True
                                    with lock: state['consumeExecutions'] += 1
                                if b'public.aip_policy_window_reconcile_v1(' in body:
                                    with lock: state['reconcileCalls'] += 1
                            if native_seen and kind == b'Q' and body.rstrip(b'\x00').strip().upper() == b'COMMIT':
                                commit_requested = True
                            upstream.sendall(kind+header+body)
                        else:
                            if native_seen and kind == b'E': native_error = True
                            if commit_requested and kind == b'C' and body == b'COMMIT\x00':
                                commit_complete = True
                            if (kind == b'Z' and body == b'I' and native_seen and commit_requested
                                    and commit_complete and not native_error):
                                with lock:
                                    assert not state['dropped'], 'only the first new consume may lose its acknowledgement'
                                    state['dropped'] = True
                                    evidence = dict(schema='aos.synthetic-pg-commit-ack-loss/v1',
                                        case='window-service-unknown-commit-state-r1',
                                        serverCommitConfirmed=True, backendReadyIdle=True, clientReadyForwarded=False,
                                        consumeExecutions=state['consumeExecutions'])
                                    assert not event_path.exists(), 'retain previous fault evidence; never replace it'
                                    persist_signed_case(event_path, evidence)
                                # COMMIT completed upstream; client cannot receive ReadyForQuery.
                                return
                            client.sendall(kind+header+body)
            except (EOFError, ConnectionError):
                pass
            except Exception as error:
                with lock: state['errors'].append(type(error).__name__)
            finally:
                for stream in (client, upstream):
                    if stream is None: continue
                    with lock: connections.discard(stream)
                    try: stream.shutdown(socket.SHUT_RDWR)
                    except OSError: pass
                    stream.close()

    class Server(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = False
        block_on_close = True
    server = Server(('127.0.0.1', 0), Handler)
    state['port'] = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': 0.05}, daemon=True)
    thread.start()
    try:
        yield state
    finally:
        stop.set()
        server.shutdown()
        with lock: remaining = list(connections)
        for stream in remaining:
            try: stream.shutdown(socket.SHUT_RDWR)
            except OSError: pass
        server.server_close()
        thread.join(timeout=3)
        assert not thread.is_alive()
        assert not state['errors'], 'proxy fixture failed; do not infer a transaction outcome'


def test_new_signed_window_service_chain_commits_exact_pair(native_roles, committed_case, tmp_path, monkeypatch, window_signer):
    run_signed_window_service_case(native_roles, committed_case, tmp_path, monkeypatch, window_signer,
                                  case_name='window-service-signed-state-r1')


def test_new_consume_commit_ack_loss_reconciles_without_resend(native_roles, committed_case, tmp_path, monkeypatch, window_signer):
    case = Path('/tmp/window-service-unknown-commit-state-r1/case.json')
    if case.exists() and json.loads(case.read_text()).get('verified', {}).get('commitAckDropped') is True:
        pytest.skip('completed fault evidence retained; never replay or create a substitute case')
    with dropping_commit_ack_proxy() as proxy:
        run_signed_window_service_case(native_roles, committed_case, tmp_path, monkeypatch, window_signer,
                                      case_name='window-service-unknown-commit-state-r1', proxy=proxy)
        assert proxy['reconcileCalls'] >= 3


def prepare_window_race(native_roles, committed_case, tmp_path, monkeypatch, window_signer, name, *, window_seconds=3600):
    """New explicit signed case; never restart a race with unknown effects."""
    import stat
    from pydantic import SecretStr
    from aos_api.aip_budget_policy_window_service import WindowRequest, WindowService, load_protected_config, _FORBIDDEN_ENV
    assert name in {'window-concurrent-consume-r1', 'window-revoke-wins-r1', 'window-consume-wins-r1',
                    'window-rollback-r1', 'window-deferred-expiry-r1'}
    directory = Path('/tmp')/name
    directory.mkdir(mode=0o700, exist_ok=True)
    assert not directory.is_symlink() and stat.S_IMODE(directory.stat().st_mode) == 0o700
    case = directory/'case.json'
    assert not (directory/'case.next').exists(), 'incomplete intent requires readonly reconciliation'
    state = json.loads(case.read_text()) if case.exists() else None
    if state and state.get('verified'):
        pytest.skip('completed race evidence retained; no repeat or substitute case')
    if state and state.get('startedRace'):
        pytest.fail('original race outcome must be reconciled readonly before any further execution')
    config = load_protected_config(private_window_service_config(native_roles, tmp_path))
    if state is None:
        with isolated_owner() as owner: now = owner.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        window = committed_case[1]['propose']['proposal']['parent']['budgetWindow']
        start = max(datetime.fromisoformat(window['effectiveFrom'].replace('Z', '+00:00')), now-timedelta(seconds=1))
        end = min(datetime.fromisoformat(window['effectiveUntil'].replace('Z', '+00:00'))-timedelta(microseconds=1), now+timedelta(seconds=window_seconds))
        assert end > now
        command = WindowProposeCommand.model_validate(dict(committed_case[0],
            idempotencyKey=name+'-'+secrets.token_hex(10), effectiveFrom=start.isoformat(), effectiveUntil=end.isoformat())).canonical_payload()
        state = dict(schema='aos.synthetic-window-race/v1', case=name,
            task='qyh-policy-window-native-authority-20261017', thread='01a13484-f019-7d82-94ce-812396db9124',
            database=os.environ['AOS_POLICY_WINDOW_TEST_DATABASE'], cluster=os.environ['AOS_POLICY_WINDOW_TEST_CLUSTER'],
            nativeManifestSha256=config.native_manifest_sha256, legacyManifestSha256=config.legacy_manifest_sha256,
            commands={'propose': command}, results={})
        persist_signed_case(case, state)
    assert (state['schema'], state['case'], state['task'], state['thread'], state['database'], state['cluster']) == (
        'aos.synthetic-window-race/v1', name, 'qyh-policy-window-native-authority-20261017',
        '01a13484-f019-7d82-94ce-812396db9124', os.environ['AOS_POLICY_WINDOW_TEST_DATABASE'],
        os.environ['AOS_POLICY_WINDOW_TEST_CLUSTER'])
    assert state['nativeManifestSha256'] == config.native_manifest_sha256
    assert state['legacyManifestSha256'] == config.legacy_manifest_sha256
    attempts = directory/'attempts'
    attempts.mkdir(mode=0o700, exist_ok=True)
    service = WindowService(config, attempts)
    _, signed, _ = window_signer
    with monkeypatch.context() as clean:
        for key in (*_FORBIDDEN_ENV, 'PGREQUIREAUTH'): clean.delenv(key, raising=False)
        for operation in ('propose', 'decide'):
            if operation == 'decide':
                p = state['results']['propose']
                payload = dict(schemaVersion=1, orgId=SCOPE.org_id, projectId=SCOPE.project_id,
                    idempotencyKey=state['commands']['propose']['idempotencyKey']+'.review', proposalId=p['proposalId'],
                    proposalHash=p['proposalHash'], targetPairHash=p['targetPairHash'], decision='approved')
                if 'decide' in state['commands']: assert state['commands']['decide'] == payload
                else:
                    state['commands']['decide'] = payload
                    persist_signed_case(case, state)
            else: payload = state['commands']['propose']
            request = dict(schemaVersion=1, mode='execute', operation=operation, command=payload)
            if operation == 'decide': request['bearerToken'] = SecretStr(signed())
            result = service.execute(WindowRequest.model_validate(request))
            if 'receipt' in result: result = result['receipt']
            assert result.get('operation') == operation, 'keep unresolved original intent; never reseed'
            if operation in state['results']: assert state['results'][operation] == result
            else:
                state['results'][operation] = result
                persist_signed_case(case, state)
    d = state['results']['decide']
    base = dict(schemaVersion=1, orgId=SCOPE.org_id, projectId=SCOPE.project_id,
                proposalId=d['proposalId'], proposalHash=d['proposalHash'])
    commands = dict(consume=dict(base, idempotencyKey=state['commands']['propose']['idempotencyKey']+'.consume',
        decisionId=d['decisionId'], decisionHash=d['decisionHash'], targetPairHash=state['commands']['decide']['targetPairHash']),
        revoke=dict(base, idempotencyKey=state['commands']['propose']['idempotencyKey']+'.revoke',
            originalDecisionId=d['decisionId'], originalDecisionHash=d['decisionHash'], reason='synthetic concurrent revocation'))
    for op, command in commands.items():
        if op in state['commands']: assert state['commands'][op] == command
        else: state['commands'][op] = command
    persist_signed_case(case, state)
    return case, state, config


def race_store(conn, config):
    from aos_api.aip_budget_policy_window_store import WindowAuthorityStore
    conn.rollback()
    return WindowAuthorityStore(conn, manifest_sha256=config.native_manifest_sha256,
        legacy_manifest_sha256=config.legacy_manifest_sha256, checker_binding=config.binding)


@contextmanager
def verified_race_transaction(conn, config, purpose, token=None):
    from aos_api.aip_budget_policy_window_identity import database_identity, authenticate_checker
    store = race_store(conn, config)
    with conn.transaction():
        conn.execute('SET TRANSACTION ISOLATION LEVEL READ COMMITTED, READ WRITE')
        conn.execute("SELECT set_config('aos.org_id','org-org',true),set_config('aos.project_id','dev-project',true),"
                     "set_config('search_path','pg_catalog',true),set_config('lock_timeout','1000',true),"
                     "set_config('statement_timeout','5000',true)")
        database_identity(conn, purpose, read_only=False)
        with conn.cursor(row_factory=dict_row) as cursor: store.verify_native_manifest(cursor)
        actor = authenticate_checker(token, binding=config.binding, conn=conn, read_only=False).subject if purpose == 'issuer' else None
        yield actor


def observe_advisory_waiters(owner, pids):
    import time
    end = time.monotonic()+0.6
    while time.monotonic() < end:
        found = {r['pid'] for r in owner.execute("SELECT pid FROM pg_locks WHERE locktype='advisory' "
            'AND NOT granted AND pid=ANY(%s)', (pids,)).fetchall()}
        if found == set(pids): return sorted(found)
        time.sleep(0.005)
    pytest.fail('bounded schedule did not observe all real database waiters; do not infer concurrency')


def window_case_facts(state):
    p = state['results']['propose']
    targets = p['proposal']['targets']
    with isolated_owner() as owner:
        records = owner.execute('SELECT operation,count(*) AS n FROM aip_budget_policy_window_receipt '
            'WHERE org_id=%s AND project_id=%s AND proposal_id=%s GROUP BY operation', (*SCOPE.key, p['proposalId'])).fetchall()
        binding = owner.execute('SELECT count(*) AS n FROM aip_budget_policy_window_binding WHERE '
            'org_id=%s AND project_id=%s AND proposal_id=%s', (*SCOPE.key, p['proposalId'])).fetchone()['n']
        fence = owner.execute('SELECT version,revoked FROM aip_budget_policy_window_fence WHERE '
            'org_id=%s AND project_id=%s AND proposal_id=%s', (*SCOPE.key, p['proposalId'])).fetchone()
        policy = owner.execute('SELECT count(*) AS n FROM aip_model_governance_policy_head WHERE '
            'org_id=%s AND project_id=%s AND policy_id=%s', (*SCOPE.key, targets['policy']['policyId'])).fetchone()['n']
        price = owner.execute('SELECT count(*) AS n FROM aip_model_price_snapshot_head WHERE '
            'org_id=%s AND project_id=%s AND model_price_snapshot_id=%s', (*SCOPE.key, targets['price']['priceSnapshotId'])).fetchone()['n']
    return dict(receipts={r['operation']:r['n'] for r in records}, binding=binding, fence=fence, policy=policy, price=price)


def test_two_real_consumers_commit_only_one_pair(native_roles, committed_case, tmp_path, monkeypatch, window_signer):
    from concurrent.futures import ThreadPoolExecutor
    from aos_api.aip_budget_policy_window_commands import WindowConsumeCommand
    case, state, config = prepare_window_race(native_roles, committed_case, tmp_path, monkeypatch, window_signer,
                                             'window-concurrent-consume-r1')
    risk = original_risk_fingerprint()
    command = WindowConsumeCommand.model_validate(state['commands']['consume'])
    state['startedRace'] = True
    persist_signed_case(case, state)
    with native_roles('consumer') as a, native_roles('consumer') as b, isolated_owner() as keeper:
        stores = [race_store(c, config) for c in (a,b)]
        pids = [a.info.backend_pid,b.info.backend_pid]
        assert len(set(pids)) == 2
        label = 'budget-cost-review:org-org:dev-project:'+state['commands']['propose']['parentCostProposalId']
        keeper.execute('SELECT pg_advisory_lock(hashtextextended(%s,0))', (label,))
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(store.consume, command) for store in stores]
            try:
                state['waiters'] = observe_advisory_waiters(keeper,pids)
                persist_signed_case(case,state)
            finally:
                keeper.execute('SELECT pg_advisory_unlock(hashtextextended(%s,0))', (label,))
            results = [f.result(timeout=10) for f in futures]
    assert results[0] == results[1]
    facts = window_case_facts(state)
    assert facts == dict(receipts={'propose':1,'decide':1,'consume':1},binding=1,
                         fence=dict(version=2,revoked=False),policy=1,price=1)
    assert original_risk_fingerprint() == risk
    state['results']['consume'] = results[0]
    state['verified'] = dict(twoWaitingBackends=state['waiters'],sameReceipt=True,facts=facts,originalRiskUnchanged=True)
    persist_signed_case(case,state)


@pytest.mark.parametrize('winner', ['revoke','consume'])
def test_real_revocation_and_consume_order(native_roles, committed_case, tmp_path, monkeypatch, window_signer, winner):
    from concurrent.futures import ThreadPoolExecutor
    from pydantic import SecretStr
    from aos_api.aip_budget_policy_window_commands import WindowConsumeCommand, WindowRevocationCommand
    from aos_api.aip_budget_policy_window_store import WindowStoreBlocked
    name = 'window-revoke-wins-r1' if winner == 'revoke' else 'window-consume-wins-r1'
    case, state, config = prepare_window_race(native_roles, committed_case, tmp_path, monkeypatch, window_signer, name)
    risk = original_risk_fingerprint()
    consume = WindowConsumeCommand.model_validate(state['commands']['consume'])
    revoke = WindowRevocationCommand.model_validate(state['commands']['revoke'])
    _, signed, _ = window_signer
    token = SecretStr(signed())
    state['startedRace'] = True
    persist_signed_case(case,state)
    first_purpose = 'issuer' if winner == 'revoke' else 'consumer'
    second_purpose = 'consumer' if winner == 'revoke' else 'issuer'
    with native_roles(first_purpose) as first, native_roles(second_purpose) as second, isolated_owner() as observer:
        store = race_store(second, config)
        with ThreadPoolExecutor(max_workers=1) as pool:
            with verified_race_transaction(first,config,first_purpose,token) as actor:
                result = invoke(first,winner,state['commands'][winner],actor)
                future = pool.submit(store.consume,consume) if winner == 'revoke' else pool.submit(store.revoke,revoke,token=token)
                state['waiters'] = observe_advisory_waiters(observer,[second.info.backend_pid])
                persist_signed_case(case,state)
                # Exiting this exact transaction commits the winner, releasing the lock.
            if winner == 'revoke':
                with pytest.raises(WindowStoreBlocked,match='42501'): future.result(timeout=10)
            else:
                withdrawn = future.result(timeout=10)
                assert withdrawn['decision'] == 'revoked'
                state['results']['revoke'] = withdrawn
    state['results'][winner] = result
    facts = window_case_facts(state)
    if winner == 'revoke':
        assert facts == dict(receipts={'propose':1,'decide':1,'revoke':1},binding=0,
                             fence=dict(version=2,revoked=True),policy=0,price=0)
    else:
        assert facts == dict(receipts={'propose':1,'decide':1,'consume':1,'revoke':1},binding=1,
                             fence=dict(version=3,revoked=True),policy=1,price=1)
        with native_roles('consumer') as conn:
            store = race_store(conn, config)
            assert store.reconcile(consume) == dict(status='observed',receipt=result,activationEligible=False)
            changed = WindowConsumeCommand.model_validate(dict(consume.canonical_payload(),idempotencyKey=consume.idempotency_key+'.after-revoke'))
            with pytest.raises(WindowStoreBlocked,match='42501'): store.consume(changed)
    assert original_risk_fingerprint() == risk
    state['verified'] = dict(winner=winner,waiters=state['waiters'],facts=facts,originalRiskUnchanged=True,
                            runtimeHoldBarrierAccepted=False)
    persist_signed_case(case,state)


def test_native_dto_rolls_back_then_original_key_can_commit(native_roles, committed_case, tmp_path, monkeypatch, window_signer):
    from aos_api.aip_budget_policy_window_commands import WindowConsumeCommand
    case,state,config = prepare_window_race(native_roles,committed_case,tmp_path,monkeypatch,window_signer,'window-rollback-r1')
    risk = original_risk_fingerprint()
    command = WindowConsumeCommand.model_validate(state['commands']['consume'])
    state['startedRace'] = True
    persist_signed_case(case,state)
    class DeliberateRollback(Exception): pass
    empty = dict(receipts={'propose':1,'decide':1},binding=0,fence=dict(version=1,revoked=False),policy=0,price=0)
    with native_roles('consumer') as conn:
        with pytest.raises(DeliberateRollback):
            with verified_race_transaction(conn,config,'consumer'):
                dto = invoke(conn,'consume',command.canonical_payload())
                assert dto['status'] == 'observed'
                assert window_case_facts(state) == empty, 'uncommitted DTO is invisible to independent reader'
                raise DeliberateRollback()
        assert window_case_facts(state) == empty
        state['knownRollbackObserved'] = True
        persist_signed_case(case,state)
        # Confirmed rollback, not a network/COMMIT unknown or an automatic resend.
        result = race_store(conn,config).consume(command)
    facts = window_case_facts(state)
    assert facts == dict(receipts={'propose':1,'decide':1,'consume':1},binding=1,
                         fence=dict(version=2,revoked=False),policy=1,price=1)
    assert result == dto and original_risk_fingerprint() == risk
    state['results']['consume'] = result
    state['verified'] = dict(knownRollbackThenOriginalKeyCommit=True,facts=facts,originalRiskUnchanged=True)
    persist_signed_case(case,state)


def test_deferred_commit_rejects_expired_returned_dto(native_roles, committed_case, tmp_path, monkeypatch, window_signer):
    import time
    from aos_api.aip_budget_policy_window_commands import WindowConsumeCommand
    case,state,config = prepare_window_race(native_roles,committed_case,tmp_path,monkeypatch,window_signer,
                                           'window-deferred-expiry-r1',window_seconds=5)
    risk = original_risk_fingerprint()
    command = WindowConsumeCommand.model_validate(state['commands']['consume'])
    state['startedRace'] = True
    persist_signed_case(case,state)
    with native_roles('consumer') as conn:
        with pytest.raises(psycopg.errors.CheckViolation,match='POLICY_WINDOW_ATOMIC_BINDING_REQUIRED'):
            with verified_race_transaction(conn,config,'consumer'):
                dto = invoke(conn,'consume',command.canonical_payload())
                assert dto['status'] == 'observed'
                deadline = datetime.fromisoformat(state['results']['propose']['proposal']['expiresAt'].replace('Z','+00:00'))
                now = conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
                seconds = (deadline-now).total_seconds()
                assert 0 < seconds <= 5
                time.sleep(seconds+0.03)
                # Actual COMMIT now executes deferred checks; DTO success is not publication.
        store = race_store(conn,config)
        assert store.reconcile(command) == dict(status='unresolved',activationEligible=False)
    facts = window_case_facts(state)
    assert facts == dict(receipts={'propose':1,'decide':1},binding=0,
                         fence=dict(version=1,revoked=False),policy=0,price=0)
    assert original_risk_fingerprint() == risk
    state['verified'] = dict(returnedDtoRejectedAtActualCommit=True,sqlstate='23514',facts=facts,originalRiskUnchanged=True)
    persist_signed_case(case,state)


def clean_parent_case_location(name):
    """Explicit new synthetic case location; this marker grants no DB authority."""
    import hashlib
    import re
    import stat
    assert name in {'window-clean-parent-revocation-r1','window-clean-legacy-renewal-r1','window-clean-drift-member-r1',
                    'window-clean-drift-budget_head-r1','window-clean-drift-provider_head-r1','window-clean-drift-wire_source-r1'}
    namespace = os.environ.get('AOS_POLICY_WINDOW_CASE_NAMESPACE')
    expected_hash = os.environ.get('AOS_POLICY_WINDOW_CASE_CONTEXT_SHA256')
    if namespace is None and expected_hash is None:
        return Path('/tmp') / name, None
    assert type(namespace) is str and re.fullmatch(r'[a-z][a-z0-9-]{0,47}', namespace)
    assert type(expected_hash) is str and re.fullmatch(r'[0-9a-f]{64}', expected_hash)
    assert os.environ.get('AOS_POLICY_WINDOW_CLEAN_PARENT_TESTS') == '1'
    assert os.environ.get('AOS_POLICY_WINDOW_TEST_DATABASE') == 'aos_test_window_http_native_r1_20261018_ti4_test'
    assert os.environ.get('AOS_POLICY_WINDOW_TEST_CLUSTER') == '7695302940039200809'
    root = Path('/tmp') / ('qyh-native-cases-' + namespace)
    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        info = os.fstat(root_fd)
        assert (stat.S_ISDIR(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o700
                and info.st_uid == os.geteuid() and info.st_gid == os.getegid())
        fd = os.open('namespace.json', os.O_RDONLY | os.O_NOFOLLOW, dir_fd=root_fd)
        with os.fdopen(fd, 'rb') as stream:
            info = os.fstat(stream.fileno())
            assert (stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o600
                    and info.st_uid == os.geteuid() and info.st_gid == os.getegid()
                    and info.st_nlink == 1 and 0 < info.st_size <= 4096)
            raw = stream.read(4097)
            assert len(raw) == info.st_size and hashlib.sha256(raw).hexdigest() == expected_hash
    finally:
        os.close(root_fd)
    def unique(pairs):
        result = {}
        for key, value in pairs:
            assert key not in result, 'duplicate namespace marker key'
            result[key] = value
        return result
    context = json.loads(raw, object_pairs_hook=unique)
    assert type(context) is dict and all(type(v) is str for v in context.values())
    assert context == dict(schema='aos-native-case-namespace/v1', namespace=namespace,
        task='qyh-window-http-native-isolation-20261018', thread='01a13484-f019-7d82-94ce-812396db9124',
        owner='codex-01a13484-f019-7d82-94ce-812396db9124', authorityRevision='AOS-002054',
        database=os.environ['AOS_POLICY_WINDOW_TEST_DATABASE'], cluster=os.environ['AOS_POLICY_WINDOW_TEST_CLUSTER'],
        expiresAt=context.get('expiresAt'))
    expiry = datetime.fromisoformat(context['expiresAt'].replace('Z', '+00:00'))
    assert expiry.tzinfo is not None and expiry.utcoffset() is not None and expiry > datetime.now(UTC)
    return root / name, context


def prepare_clean_parent(native_roles, issuer_factory, https_signer, monkeypatch, name):
    """Dedicated new parent in the separately installed clean cluster."""
    if os.environ.get('AOS_POLICY_WINDOW_CLEAN_PARENT_TESTS') != '1':
        pytest.skip('explicit clean-cluster parent test entry required')
    assert os.environ['AOS_POLICY_WINDOW_TEST_CLUSTER'] != '7697483449264238613'
    assert name in {'window-clean-parent-revocation-r1','window-clean-legacy-renewal-r1','window-clean-drift-member-r1',
                    'window-clean-drift-budget_head-r1','window-clean-drift-provider_head-r1','window-clean-drift-wire_source-r1'}
    schema = 'aos.synthetic-parent-revocation/v1' if name=='window-clean-parent-revocation-r1' else 'aos.synthetic-parent-authority-drift/v1'
    directory, namespace_context = clean_parent_case_location(name)
    directory.mkdir(mode=0o700, exist_ok=True)
    assert not directory.is_symlink() and directory.stat().st_uid == os.geteuid()
    case = directory/'case.json'
    marker = directory/'parent.json'
    state = json.loads(case.read_text()) if case.exists() else None
    if namespace_context is not None and state is not None:
        assert (state.get('caseNamespace') == namespace_context['namespace']
                and state.get('task') == namespace_context['task']
                and state.get('thread') == namespace_context['thread']
                and state.get('sourceFixtureTask') == 'qyh-policy-window-native-authority-20261017'
                and state.get('caseContextSha256') == os.environ['AOS_POLICY_WINDOW_CASE_CONTEXT_SHA256']), 'case namespace provenance mismatch'
    if state and state.get('verified'):
        pytest.skip('completed dedicated parent revocation retained; never recreate it')
    if state and state.get('semanticStarted'):
        pytest.fail('original semantic effect needs readonly reconciliation; never rerun automatically')
    if state is None:
        state = dict(schema=schema,
            task=namespace_context['task'] if namespace_context is not None else 'qyh-policy-window-native-authority-20261017',thread='01a13484-f019-7d82-94ce-812396db9124',
            database=os.environ['AOS_POLICY_WINDOW_TEST_DATABASE'],cluster=os.environ['AOS_POLICY_WINDOW_TEST_CLUSTER'],
            creatingParent=True,commands={},results={})
        if namespace_context is not None:
            state.update(caseNamespace=namespace_context['namespace'],
                sourceFixtureTask='qyh-policy-window-native-authority-20261017',
                caseContextSha256=os.environ['AOS_POLICY_WINDOW_CASE_CONTEXT_SHA256'])
        persist_signed_case(case,state)
    elif not marker.exists():
        pytest.fail('parent creation outcome unknown; reconcile this DB, never create a substitute')
    assert state['database']==os.environ['AOS_POLICY_WINDOW_TEST_DATABASE']
    assert state['cluster']==os.environ['AOS_POLICY_WINDOW_TEST_CLUSTER']
    assert state['schema']==schema
    monkeypatch.setenv('AOS_POLICY_WINDOW_PARENT_CASE',str(marker))
    command,parent = prepare_parent(issuer_factory,https_signer,native_roles)
    keys=('AOS_AUTH_ALLOW_DEV','AOS_AUTH_EXTERNAL_ONLY','AOS_OIDC_ISSUER','AOS_OIDC_AUDIENCE',
        'AOS_OIDC_CLIENT_ID','AOS_OIDC_JWKS_URL','AOS_OIDC_ISSUERS','AOS_OIDC_JWKS_URLS',
        'AOS_OIDC_TOKEN_URL','AOS_OIDC_TOKEN_ALG','AOS_OIDC_LEEWAY_SECONDS')
    environment={k:os.environ.get(k) for k in keys}
    return case,state,command,parent,environment


@pytest.fixture
def clean_revocation_parent(native_roles, issuer_factory, https_signer, monkeypatch):
    return prepare_clean_parent(native_roles,issuer_factory,https_signer,monkeypatch,'window-clean-parent-revocation-r1')


@pytest.fixture
def clean_child_signer(clean_revocation_parent, monkeypatch):
    # Dependency ensures parent HTTPS approval completes before child OIDC setup.
    generator = window_signer.__wrapped__(monkeypatch)
    signer = next(generator)
    try: yield signer
    finally: generator.close()


@pytest.fixture
def clean_renewal_parent(native_roles, issuer_factory, https_signer, monkeypatch):
    return prepare_clean_parent(native_roles, issuer_factory, https_signer, monkeypatch,
                                'window-clean-legacy-renewal-r1')


@pytest.fixture
def clean_renewal_signer(clean_renewal_parent, monkeypatch):
    generator = window_signer.__wrapped__(monkeypatch)
    signer = next(generator)
    try: yield signer
    finally: generator.close()


def test_clean_legacy_policy_only_successor_cannot_split_native_pair(
        native_roles, clean_renewal_parent, clean_renewal_signer, tmp_path, monkeypatch):
    """A signed old-family approval cannot publish half a new-family successor."""
    import time
    from pydantic import SecretStr
    from aos_api.aip_budget_policy_window_service import (
        WindowService, WindowRequest, load_protected_config, _FORBIDDEN_ENV,
    )
    from aos_api.aip_budget_policy_renewal_contracts import (
        RenewalProposalCommand, RenewalDecisionCommand, RenewalConsumeCommand,
    )
    from aos_api.aip_budget_policy_renewal_store import RenewalAuthorityStore, RenewalStoreBlocked
    case, state, parent_command, _, _ = clean_renewal_parent
    _, signed, requests = clean_renewal_signer
    config = load_protected_config(private_window_service_config(native_roles, tmp_path))
    attempts = case.parent / 'attempts'
    attempts.mkdir(mode=0o700, exist_ok=True)
    service = WindowService(config, attempts)
    if 'propose' not in state['commands']:
        with isolated_owner() as owner:
            now = owner.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        state['commands']['propose'] = WindowProposeCommand.model_validate(dict(
            parent_command, effectiveUntil=(now + timedelta(seconds=30)).isoformat())).canonical_payload()
        state['riskBefore'] = original_risk_fingerprint()
        persist_signed_case(case, state)
    with monkeypatch.context() as clean:
        for key in (*_FORBIDDEN_ENV, 'PGREQUIREAUTH'): clean.delenv(key, raising=False)
        for operation in ('propose', 'decide', 'consume'):
            if operation == 'propose': payload = state['commands']['propose']
            elif operation == 'decide':
                p = state['results']['propose']
                payload = dict(schemaVersion=1, orgId=SCOPE.org_id, projectId=SCOPE.project_id,
                    idempotencyKey=parent_command['idempotencyKey']+'.review', proposalId=p['proposalId'],
                    proposalHash=p['proposalHash'], targetPairHash=p['targetPairHash'], decision='approved')
            else:
                d = state['results']['decide']
                payload = {k: v for k, v in state['commands']['decide'].items() if k != 'decision'}
                payload.update(idempotencyKey=parent_command['idempotencyKey']+'.consume',
                               decisionId=d['decisionId'], decisionHash=d['decisionHash'])
            if operation in state['commands']: assert state['commands'][operation] == payload
            else:
                state['commands'][operation] = payload
                persist_signed_case(case, state)
            envelope = dict(schemaVersion=1, mode='execute', operation=operation, command=payload)
            if operation == 'decide': envelope['bearerToken'] = SecretStr(signed())
            result = service.execute(WindowRequest.model_validate(envelope))
            if 'receipt' in result: result = result['receipt']
            assert result.get('operation') == operation, 'original native intent unresolved; no substitute'
            state['results'][operation] = result
            persist_signed_case(case, state)
    initial = state['results']['consume']
    target = state['results']['propose']['proposal']['targets']['policy']
    source_until = datetime.fromisoformat(target['effectiveUntil'].replace('Z', '+00:00'))
    if 'legacyCommands' not in state:
        command = RenewalProposalCommand(schemaVersion=1, orgId=SCOPE.org_id, projectId=SCOPE.project_id,
            idempotencyKey=parent_command['idempotencyKey']+'.legacy',
            sourcePolicyId=initial['policyRef']['assetId'], expectedSourceRevision=1,
            expectedHeadVersion=1, expectedSourceHash=initial['policyRef']['contentHash'],
            effectiveFrom=source_until, effectiveUntil=source_until+timedelta(minutes=30))
        state['legacyCommands'] = {'propose': command.canonical_payload()}
        state['legacyResults'], state['legacyAttempts'] = {}, []
        persist_signed_case(case, state)
    role = 'aos_budget_renewal_consumer_call'
    password = secrets.token_urlsafe(32)
    with isolated_owner() as owner:
        assert owner.execute('SELECT rolcanlogin FROM pg_roles WHERE rolname=%s', (role,)).fetchone()['rolcanlogin'] is False
        owner.execute(sql.SQL('ALTER ROLE {} LOGIN PASSWORD {}').format(sql.Identifier(role), sql.Literal(password)))
        owner.commit()
    try:
        for operation, model, purpose in [('propose', RenewalProposalCommand, 'maker'),
                ('decide', RenewalDecisionCommand, 'issuer'), ('consume', RenewalConsumeCommand, 'legacy-consumer')]:
            if operation == 'decide':
                p = state['legacyResults']['propose']
                payload = dict(schemaVersion=1, orgId=SCOPE.org_id, projectId=SCOPE.project_id,
                    idempotencyKey=parent_command['idempotencyKey']+'.legacy.review', proposalId=p['proposalId'],
                    proposalHash=p['proposalHash'], targetActiveHash=p['targetActiveHash'], decision='approved')
            elif operation == 'consume':
                d = state['legacyResults']['decide']
                payload = dict(schemaVersion=1, orgId=SCOPE.org_id, projectId=SCOPE.project_id,
                    idempotencyKey=parent_command['idempotencyKey']+'.legacy.consume', proposalId=d['proposalId'],
                    proposalHash=d['proposalHash'], decisionId=d['decisionId'], decisionHash=d['decisionHash'])
            else: payload = state['legacyCommands']['propose']
            if operation in state['legacyCommands']: assert state['legacyCommands'][operation] == payload
            else:
                state['legacyCommands'][operation] = payload
                persist_signed_case(case, state)
            command = model.model_validate(payload)
            @contextmanager
            def connection():
                if purpose != 'legacy-consumer':
                    with native_roles(purpose) as conn:
                        conn.rollback()
                        # Match migration's catalog deparse context without changing the seal.
                        conn.execute('SET search_path=pg_catalog'); conn.commit()
                        yield conn
                else:
                    parts = conninfo_to_dict(get_dsn())
                    with psycopg.connect(host=parts['host'], port=parts['port'], dbname=parts['dbname'],
                            user=role, password=password, row_factory=dict_row,
                            options='-c search_path=pg_catalog') as conn: yield conn
            with connection() as conn:
                store = RenewalAuthorityStore(conn, checker_binding=config.binding)
                token = {'token': SecretStr(signed())} if purpose == 'issuer' else {}
                history = store.reconcile(command, **token)
                if operation == 'consume':
                    assert history['status'] == 'unresolved'
                    if operation in state['legacyAttempts']:
                        proof = state.get('legacyKnownRollback', {}).get('consume')
                        assert proof and proof['command'] == payload and proof['consumeReceiptCount'] == 0
                    with isolated_owner() as owner:
                        now = owner.execute('SELECT clock_timestamp() AS now').fetchone()['now']
                    if now < source_until:
                        assert operation not in state['legacyAttempts']
                        state['legacyAttempts'].append(operation)
                        persist_signed_case(case, state)
                        with pytest.raises(RenewalStoreBlocked, match='REJECTED:42501'):
                            store.consume(command)
                        assert store.reconcile(command)['status'] == 'unresolved'
                        state['legacyKnownRollback'] = {'consume': dict(command=payload,
                            consumeReceiptCount=0, sqlstate='42501', prematureWindow=True)}
                        persist_signed_case(case, state)
                        delay = (source_until-now).total_seconds()+0.05
                        assert 0 < delay < 35, 'wait only for original bounded window; never extend it'
                        time.sleep(delay)
                    assert not state.get('legacySuccessorGateAttempted'), 'unknown successor outcome: readonly only'
                    state['legacySuccessorGateAttempted'] = True
                    persist_signed_case(case, state)
                    # The deferred guard requires this exact revision's pair binding.
                    with pytest.raises(RenewalStoreBlocked, match='REJECTED:P0002'):
                        store.consume(command)
                    assert store.reconcile(command)['status'] == 'unresolved'
                    state['legacyResults']['consume'] = dict(status='denied', sqlstate='P0002',
                        policyOnlySuccessorRolledBack=True)
                    persist_signed_case(case, state)
                    continue
                if history['status'] == 'observed': result = history
                else:
                    assert history['status'] == 'unresolved' and operation not in state['legacyAttempts'], 'unknown legacy effect: reconcile only'
                    state['legacyAttempts'].append(operation)
                    persist_signed_case(case, state)
                    result = getattr(store, operation)(command, **token)
                state['legacyResults'][operation] = result
                persist_signed_case(case, state)
                assert store.reconcile(command, **token)['status'] == 'observed'
    finally:
        with isolated_owner() as owner:
            owner.execute(sql.SQL('ALTER ROLE {} NOLOGIN PASSWORD NULL').format(sql.Identifier(role)))
            owner.commit()
    with isolated_owner() as owner:
        policy = owner.execute("SELECT current_revision,version FROM public.aip_model_governance_policy_head "
            "WHERE org_id=%s AND project_id=%s AND policy_id=%s",
            (*SCOPE.key, initial['policyRef']['assetId'])).fetchone()
        price = owner.execute("SELECT current_revision,version FROM public.aip_model_price_snapshot_head "
            "WHERE org_id=%s AND project_id=%s AND model_price_snapshot_id=%s",
            (*SCOPE.key, initial['priceRef']['assetId'])).fetchone()
        receipts = owner.execute("SELECT operation,count(*) AS n FROM public.aip_budget_policy_renewal_receipt "
            "WHERE org_id=%s AND project_id=%s AND proposal_id=%s GROUP BY operation",
            (*SCOPE.key, state['legacyResults']['propose']['proposalId'])).fetchall()
        assert policy == price == dict(current_revision=1, version=1)
        assert {r['operation']: r['n'] for r in receipts} == dict(propose=1, decide=1)
        assert owner.execute("SELECT count(*) AS n FROM public.aip_model_governance_policy_revision "
            "WHERE org_id=%s AND project_id=%s AND policy_id=%s AND revision>1",
            (*SCOPE.key, initial['policyRef']['assetId'])).fetchone()['n'] == 0
    assert initial['budgetRef'] == parent_command['expectedBudgetRef']
    assert original_risk_fingerprint() == state['riskBefore'] and requests
    state['verified'] = dict(nativePairCommitted=True, legacySignedApprovalCommitted=True,
        legacyPolicyOnlySuccessorDenied=True, legacySuccessorReceiptCount=0,
        sameBudgetRef=True, originalRiskUnchanged=True, formalHumanConsent=False, runtimeHoldBarrierAccepted=False)
    persist_signed_case(case, state)


def test_clean_parent_revocation_denies_unconsumed_child(native_roles, issuer_factory, https_signer,
        clean_revocation_parent, clean_child_signer, tmp_path, monkeypatch):
    from pydantic import SecretStr
    from aos_api.aip_budget_cost_issuer import BudgetCostIssuer,BudgetCostIssuerCommand
    from aos_api.aip_budget_policy_window_commands import WindowConsumeCommand
    from aos_api.aip_budget_policy_window_service import WindowService,WindowRequest,load_protected_config,_FORBIDDEN_ENV
    from aos_api.aip_budget_policy_window_store import WindowStoreBlocked
    case,state,command,parent,environment = clean_revocation_parent
    _,signed,requests = clean_child_signer
    config=load_protected_config(private_window_service_config(native_roles,tmp_path))
    attempts=case.parent/'attempts'
    attempts.mkdir(mode=0o700,exist_ok=True)
    service=WindowService(config,attempts)
    state['commands'].setdefault('propose',command)
    assert state['commands']['propose']==command
    persist_signed_case(case,state)
    with monkeypatch.context() as clean:
        for key in (*_FORBIDDEN_ENV,'PGREQUIREAUTH'):clean.delenv(key,raising=False)
        for operation in ('propose','decide'):
            if operation=='decide':
                p=state['results']['propose']
                payload=dict(schemaVersion=1,orgId=SCOPE.org_id,projectId=SCOPE.project_id,
                    idempotencyKey=command['idempotencyKey']+'.review',proposalId=p['proposalId'],
                    proposalHash=p['proposalHash'],targetPairHash=p['targetPairHash'],decision='approved')
            else:payload=command
            if operation in state['commands']:assert state['commands'][operation]==payload
            else:
                state['commands'][operation]=payload
                persist_signed_case(case,state)
            envelope=dict(schemaVersion=1,mode='execute',operation=operation,command=payload)
            if operation=='decide':envelope['bearerToken']=SecretStr(signed())
            result=service.execute(WindowRequest.model_validate(envelope))
            if 'receipt' in result:result=result['receipt']
            assert result.get('operation')==operation,'unresolved original child intent must not be replayed'
            state['results'][operation]=result
            persist_signed_case(case,state)
    d=state['results']['decide']
    consume=WindowConsumeCommand(schemaVersion=1,orgId=SCOPE.org_id,projectId=SCOPE.project_id,
        idempotencyKey=command['idempotencyKey']+'.consume',proposalId=d['proposalId'],proposalHash=d['proposalHash'],
        decisionId=d['decisionId'],decisionHash=d['decisionHash'],targetPairHash=state['commands']['decide']['targetPairHash'])
    parent_ref=command['expectedBudgetRef']
    with isolated_owner() as owner:
        before=owner.execute('SELECT version FROM aip_budget_cost_runtime_fence WHERE org_id=%s AND project_id=%s '
            'AND budget_id=%s AND revision=%s',(*SCOPE.key,parent_ref['assetId'],parent_ref['revision'])).fetchone()['version']
    state['commands']['consume']=consume.canonical_payload()
    revoke_body=dict(operation='revoke',orgId=SCOPE.org_id,projectId=SCOPE.project_id,
        proposalId=command['parentCostProposalId'],proposalHash=command['parentCostProposalHash'],
        idempotencyKey=command['idempotencyKey']+'.parent-revoke',decision=None,reason='dedicated synthetic parent withdrawal')
    if 'parentRevoke' in state['commands']:assert state['commands']['parentRevoke']==revoke_body
    else:state['commands']['parentRevoke']=revoke_body
    persist_signed_case(case,state)
    sign,_=https_signer
    with monkeypatch.context() as original:
        for key,value in environment.items():
            if value is None:original.delenv(key,raising=False)
            else:original.setenv(key,value)
        request=BudgetCostIssuerCommand.model_validate(dict(revoke_body,bearerToken=SecretStr(sign(parent.checker_subject))))
        issuer=BudgetCostIssuer(issuer_factory)
        # Inquiry first: a previous unknown result may only be reconciled.
        prior=issuer.inquire(request)
        if prior.get('status')=='observed':withdrawn=prior['result']
        else:
            assert not state.get('parentRevokeAttempted'),'unknown parent revoke must remain readonly'
            assert prior.get('status')=='unresolved'
            state['parentRevokeAttempted']=True
            state['parentRevokeHash']=request.request_hash
            persist_signed_case(case,state)
            withdrawn=issuer.execute(request)
        assert issuer.inquire(request)['result']==withdrawn
    state['results']['parentRevoke']=withdrawn
    persist_signed_case(case,state)
    assert withdrawn['decisionId']==command['parentCostDecisionId']
    with native_roles('consumer') as conn:
        with pytest.raises(WindowStoreBlocked,match='42501'):race_store(conn,config).consume(consume)
    facts=window_case_facts(state)
    assert facts==dict(receipts={'propose':1,'decide':1},binding=0,
                       fence=dict(version=1,revoked=False),policy=0,price=0)
    with isolated_owner() as owner:
        revoked=owner.execute('SELECT count(*) AS n FROM aip_budget_cost_revocation WHERE org_id=%s AND project_id=%s '
            'AND decision_id=%s',(*SCOPE.key,command['parentCostDecisionId'])).fetchone()['n']
        version=owner.execute('SELECT version FROM aip_budget_cost_runtime_fence WHERE org_id=%s AND project_id=%s '
            'AND budget_id=%s AND revision=%s',(*SCOPE.key,parent_ref['assetId'],parent_ref['revision'])).fetchone()['version']
    assert revoked==1 and version==before+1 and requests
    state['verified']=dict(parentRevocationCount=1,parentFenceBefore=before,parentFenceAfter=version,
                           consumerDeniedSqlstate='42501',facts=facts,formalHumanConsent=False,runtimeHoldBarrierAccepted=False)
    persist_signed_case(case,state)


def test_clean_revoked_parent_history_remains_readonly(native_roles, tmp_path, monkeypatch, window_signer):
    if os.environ.get('AOS_POLICY_WINDOW_CLEAN_PARENT_TESTS')!='1':pytest.skip('dedicated clean cluster required')
    from pydantic import SecretStr
    from aos_api.aip_budget_policy_window_service import WindowRequest,WindowService,load_protected_config,_FORBIDDEN_ENV
    state=json.loads(Path('/tmp/window-clean-parent-revocation-r1/case.json').read_text())
    assert state.get('verified') and state['database']==os.environ['AOS_POLICY_WINDOW_TEST_DATABASE']
    config=load_protected_config(private_window_service_config(native_roles,tmp_path))
    attempts=tmp_path/'readonly-attempts';attempts.mkdir(mode=0o700)
    service=WindowService(config,attempts)
    _,signed,_=window_signer
    before=totals();risk=original_risk_fingerprint()
    with monkeypatch.context() as clean:
        for key in (*_FORBIDDEN_ENV,'PGREQUIREAUTH'):clean.delenv(key,raising=False)
        for operation in ('propose','decide'):
            envelope=dict(schemaVersion=1,mode='reconcile',operation=operation,command=state['commands'][operation])
            if operation=='decide':envelope['bearerToken']=SecretStr(signed())
            assert service.execute(WindowRequest.model_validate(envelope))==dict(
                status='observed',receipt=state['results'][operation],activationEligible=False)
        assert not list(attempts.iterdir())
    assert totals()==before and original_risk_fingerprint()==risk


def clean_catalog_fingerprint(owner):
    import hashlib
    from aos_api.aip_budget_policy_window_store import FUNCTIONS,RELATIONS,LEGACY_FUNCTIONS,LEGACY_RELATIONS,_RELATION_METADATA
    owner.execute("SELECT set_config('search_path','pg_catalog',true)")
    functions={name:owner.execute("SELECT jsonb_build_object('owner',pg_get_userbyid(proowner),'definer',prosecdef,"
        "'config',to_jsonb(proconfig),'acl',proacl::text,'definition',pg_get_functiondef(oid)) AS value "
        'FROM pg_proc WHERE oid=to_regprocedure(%s)',(name,)).fetchone()['value'] for name in FUNCTIONS|LEGACY_FUNCTIONS}
    relations={name:owner.execute(_RELATION_METADATA,('public.'+name,)).fetchone()['metadata'] for name in RELATIONS|LEGACY_RELATIONS}
    roles=owner.execute("SELECT rolname,rolcanlogin,rolinherit,rolsuper,rolbypassrls,rolcreatedb,rolcreaterole,rolreplication "
        "FROM pg_roles WHERE rolname LIKE 'aos_budget_%' ORDER BY rolname").fetchall()
    members=owner.execute('SELECT pg_get_userbyid(roleid) AS role,pg_get_userbyid(member) AS member,admin_option '
        'FROM pg_auth_members ORDER BY roleid,member').fetchall()
    return hashlib.sha256(json.dumps(dict(functions=functions,relations=relations,roles=roles,members=members),sort_keys=True).encode()).hexdigest()


@pytest.mark.parametrize('kind', ['function_config','function_volatility','rls','trigger','role_membership','table_acl'])
def test_clean_catalog_drift_is_rejected_and_restored(native_roles, tmp_path, kind):
    if os.environ.get('AOS_POLICY_WINDOW_CLEAN_PARENT_TESTS')!='1':pytest.skip('dedicated clean cluster required')
    from aos_api.aip_budget_policy_window_commands import WindowProposeCommand
    from aos_api.aip_budget_policy_window_store import WindowStoreBlocked
    from aos_api.aip_budget_policy_window_identity import WindowIdentityBlocked
    from aos_api.aip_budget_policy_window_service import load_protected_config
    root=Path('/tmp/window-clean-parent-revocation-r1')
    state=json.loads((root/'case.json').read_text())
    assert state.get('verified') and state['database']==os.environ['AOS_POLICY_WINDOW_TEST_DATABASE']
    event=root/('catalog-'+kind+'.json')
    if event.exists():
        if json.loads(event.read_text()).get('verified'):pytest.skip('completed drift proof retained')
        pytest.fail('original catalog fault needs readonly reconciliation before any new mutation')
    cases={
        'function_config':('ALTER FUNCTION public.aip_policy_window_parent_v1(jsonb,boolean) SET search_path=public',
            'ALTER FUNCTION public.aip_policy_window_parent_v1(jsonb,boolean) SET search_path=pg_catalog',WindowStoreBlocked,'FUNCTION_SEAL_DRIFT'),
        'function_volatility':('ALTER FUNCTION public.aip_policy_window_parent_v1(jsonb,boolean) STABLE',
            'ALTER FUNCTION public.aip_policy_window_parent_v1(jsonb,boolean) VOLATILE',WindowStoreBlocked,'FUNCTION_SEAL_DRIFT'),
        'rls':('ALTER TABLE public.aip_budget_policy_window_binding DISABLE ROW LEVEL SECURITY',
            'ALTER TABLE public.aip_budget_policy_window_binding ENABLE ROW LEVEL SECURITY',WindowStoreBlocked,'RELATION_SEAL_DRIFT'),
        'trigger':('ALTER TABLE public.aip_budget_policy_window_binding DISABLE TRIGGER policy_window_insert_guard',
            'ALTER TABLE public.aip_budget_policy_window_binding ENABLE TRIGGER policy_window_insert_guard',WindowStoreBlocked,'RELATION_SEAL_DRIFT'),
        'role_membership':('GRANT aos_runtime TO aos_budget_renewal_maker_call',
            'REVOKE aos_runtime FROM aos_budget_renewal_maker_call',WindowIdentityBlocked,'DATABASE_IDENTITY_PROFILE_REQUIRED'),
        'table_acl':('GRANT SELECT ON public.aip_budget_policy_window_binding TO aos_budget_renewal_maker_call',
            'REVOKE SELECT ON public.aip_budget_policy_window_binding FROM aos_budget_renewal_maker_call',WindowStoreBlocked,'RELATION_SEAL_DRIFT'),
    }
    mutate,restore,error,message=cases[kind]
    config=load_protected_config(private_window_service_config(native_roles,tmp_path))
    command=WindowProposeCommand.model_validate(state['commands']['propose'])
    before=totals();risk=original_risk_fingerprint()
    with native_roles('maker') as conn, isolated_owner() as admin:
        store=race_store(conn,config)
        baseline=clean_catalog_fingerprint(admin)
        record=dict(schema='aos.synthetic-catalog-drift/v1',kind=kind,database=state['database'],cluster=state['cluster'],
            beforeSha256=baseline,mutation=mutate,restore=restore,verified=False)
        persist_signed_case(event,record)
        try:
            admin.execute(mutate);admin.commit()
            assert clean_catalog_fingerprint(admin)!=baseline
            with pytest.raises(error,match=message):store.reconcile(command)
            record['callerRejected']=True
        finally:
            admin.rollback()
            # Re-read instead of blindly reapplying a possibly unknown mutation.
            if clean_catalog_fingerprint(admin)!=baseline:
                admin.execute(restore);admin.commit()
            assert clean_catalog_fingerprint(admin)==baseline
            record['catalogRestored']=True
            persist_signed_case(event,record)
        assert store.reconcile(command)==dict(status='observed',receipt=state['results']['propose'],activationEligible=False)
    assert totals()==before and original_risk_fingerprint()==risk
    record['verified']=True
    record['dataUnchanged']=True
    persist_signed_case(event,record)


@pytest.fixture
def clean_drift_parent(request,native_roles,issuer_factory,https_signer,monkeypatch):
    kind=request.param
    return kind,prepare_clean_parent(native_roles,issuer_factory,https_signer,monkeypatch,'window-clean-drift-'+kind+'-r1')


@pytest.fixture
def clean_drift_signer(clean_drift_parent,monkeypatch):
    generator=window_signer.__wrapped__(monkeypatch)
    try:yield next(generator)
    finally:generator.close()


def prepare_drift_child(context,native_roles,tmp_path,monkeypatch,signer):
    from pydantic import SecretStr
    from aos_api.aip_budget_policy_window_service import WindowRequest,WindowService,load_protected_config,_FORBIDDEN_ENV
    case,state,command,parent,environment=context
    config=load_protected_config(private_window_service_config(native_roles,tmp_path))
    attempts=case.parent/'attempts';attempts.mkdir(mode=0o700,exist_ok=True)
    service=WindowService(config,attempts)
    _,signed,_=signer
    with monkeypatch.context() as clean:
        for key in (*_FORBIDDEN_ENV,'PGREQUIREAUTH'):clean.delenv(key,raising=False)
        for operation in ('propose','decide'):
            if operation=='propose':payload=command
            else:
                p=state['results']['propose']
                payload=dict(schemaVersion=1,orgId=SCOPE.org_id,projectId=SCOPE.project_id,
                    idempotencyKey=command['idempotencyKey']+'.review',proposalId=p['proposalId'],
                    proposalHash=p['proposalHash'],targetPairHash=p['targetPairHash'],decision='approved')
            if operation in state['commands']:assert state['commands'][operation]==payload
            else:
                state['commands'][operation]=payload
                persist_signed_case(case,state)
            envelope=dict(schemaVersion=1,mode='execute',operation=operation,command=payload)
            if operation=='decide':envelope['bearerToken']=SecretStr(signed())
            result=service.execute(WindowRequest.model_validate(envelope))
            if 'receipt' in result:result=result['receipt']
            assert result.get('operation')==operation,'unknown original child effect requires readonly reconciliation'
            state['results'][operation]=result
            persist_signed_case(case,state)
            assert result.get('status') == ('prepared' if operation == 'propose' else 'observed'), (
                'original child rejected or unresolved; retain result and marker, never reseed')
    from aos_api.aip_budget_policy_window_commands import WindowConsumeCommand
    d=state['results']['decide']
    consume=WindowConsumeCommand(schemaVersion=1,orgId=SCOPE.org_id,projectId=SCOPE.project_id,
        idempotencyKey=command['idempotencyKey']+'.consume',proposalId=d['proposalId'],proposalHash=d['proposalHash'],
        targetPairHash=state['commands']['decide']['targetPairHash'],decisionId=d['decisionId'],decisionHash=d['decisionHash'])
    state['commands']['consume']=consume.canonical_payload()
    state['semanticStarted']=True
    persist_signed_case(case,state)
    return config,consume


@pytest.mark.parametrize('clean_drift_parent',['member','budget_head','provider_head','wire_source'],indirect=True)
def test_clean_current_authority_semantic_drift(clean_drift_parent,clean_drift_signer,native_roles,tmp_path,monkeypatch):
    from copy import deepcopy
    from aos_api.aip_budget_policy_window_store import WindowStoreBlocked
    kind,context=clean_drift_parent
    case,state,command,parent,_=context
    config,consume=prepare_drift_child(context,native_roles,tmp_path,monkeypatch,clean_drift_signer)
    before=window_case_facts(state)
    assert before==dict(receipts={'propose':1,'decide':1},binding=0,fence=dict(version=1,revoked=False),policy=0,price=0)
    risk=original_risk_fingerprint()
    with isolated_owner() as owner:
        assert owner.execute('SELECT count(*) AS n FROM aip_budget_cost_revocation WHERE decision_id=%s',
                             (command['parentCostDecisionId'],)).fetchone()['n']==0
    if kind=='member':
        with isolated_owner() as admin, native_roles('consumer') as conn:
            row=admin.execute('SELECT role FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s',
                              (*SCOPE.key,parent.maker_subject)).fetchone()
            assert row['role'].lower() in {'owner','admin'}
            state['memberBefore']=dict(subject=parent.maker_subject,role=row['role'])
            persist_signed_case(case,state)
            try:
                admin.execute("UPDATE meta_membership SET role='viewer' WHERE org_id=%s AND project_id=%s AND subject=%s",
                              (*SCOPE.key,parent.maker_subject));admin.commit()
                with pytest.raises(WindowStoreBlocked,match='42501'):race_store(conn,config).consume(consume)
                assert window_case_facts(state)==before
            finally:
                admin.rollback()
                current=admin.execute('SELECT role FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s',
                                      (*SCOPE.key,parent.maker_subject)).fetchone()['role']
                if current!=row['role']:
                    assert current=='viewer'
                    admin.execute('UPDATE meta_membership SET role=%s WHERE org_id=%s AND project_id=%s AND subject=%s',
                                  (row['role'],*SCOPE.key,parent.maker_subject));admin.commit()
            assert admin.execute('SELECT role FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s',
                                 (*SCOPE.key,parent.maker_subject)).fetchone()['role']==row['role']
            state['memberRestored']=True
            persist_signed_case(case,state)
            result=race_store(conn,config).consume(consume)
            state['results']['consume']=result
    elif kind=='budget_head':
        from aos_api.aip_budget_store import AipBudgetAuthorityStore
        from aos_api.aip_budget_contracts import BudgetLifecycle
        from aos_api.aip_budget_store import canonical_hash
        draft=parent.target.model_copy(update={'revision':command['expectedBudgetRef']['revision']+1,'lifecycle':BudgetLifecycle.DRAFT})
        draft=type(parent.target).model_validate(draft.model_dump(mode='python',by_alias=True))
        key=command['idempotencyKey']+'.new-budget-draft'
        state['publication']=dict(kind=kind,key=key,expectedVersion=command['expectedBudgetHeadVersion'],
                                  payload=draft.model_dump(mode='json',by_alias=True))
        persist_signed_case(case,state)
        published=AipBudgetAuthorityStore().publish(SCOPE,parent.maker_subject,key,draft,
                                                    expected_version=command['expectedBudgetHeadVersion'])
        assert published.lifecycle==BudgetLifecycle.DRAFT and published.budget_id==parent.target.budget_id
        assert published.daily_limit_minor==parent.target.daily_limit_minor and published.monthly_limit_minor==parent.target.monthly_limit_minor
        state['publicationResult']=dict(revision=published.revision,contentHash=published.content_hash,lifecycle='draft')
        persist_signed_case(case,state)
        with native_roles('consumer') as conn:
            with pytest.raises(WindowStoreBlocked,match='23514'):race_store(conn,config).consume(consume)
        assert window_case_facts(state)==before
    elif kind=='provider_head':
        from aos_api.aip_model_runtime_store import AipModelRuntimeStore
        store=AipModelRuntimeStore()
        provider=store.get_provider(SCOPE,command['expectedProviderRef']['assetId'])
        with isolated_owner() as owner:
            head=owner.execute('SELECT version FROM aip_provider_instance_head WHERE org_id=%s AND project_id=%s AND provider_instance_id=%s',
                               (*SCOPE.key,provider.provider_instance_id)).fetchone()['version']
        candidate=changed_provider_revision(provider)
        key=command['idempotencyKey']+'.new-provider-revision'
        state['publication']=dict(kind=kind,key=key,expectedVersion=head,payload=candidate.model_dump(mode='json',by_alias=True))
        persist_signed_case(case,state)
        published=store.publish_provider(SCOPE,parent.maker_subject,key,candidate,expected_version=head)
        assert published.revision==provider.revision+1 and published.content_hash!=provider.content_hash
        state['publicationResult']=dict(revision=published.revision,contentHash=published.content_hash,lifecycle=published.lifecycle.value)
        persist_signed_case(case,state)
        with native_roles('consumer') as conn:
            with pytest.raises(WindowStoreBlocked,match='23514'):race_store(conn,config).consume(consume)
        assert window_case_facts(state)==before
    else:
        assert kind=='wire_source'
        variants={
            'proposal_hash':dict(command,parentCostProposalHash='0'*64),
            'consumption_receipt':dict(command,parentConsumptionReceiptId='different-receipt'),
            'budget_hash':deepcopy(command),'budget_asset':deepcopy(command),
            'budget_head':dict(command,expectedBudgetHeadVersion=command['expectedBudgetHeadVersion']+1),
            'provider_hash':deepcopy(command),'provider_model':dict(command,expectedProviderModelId='different-model'),
            'whole_budget_window':dict(command,effectiveUntil=parent.target.effective_until.isoformat()),
        }
        variants['budget_hash']['expectedBudgetRef']['contentHash']='0'*64
        variants['budget_asset']['expectedBudgetRef']['assetId']+='-other'
        variants['provider_hash']['expectedProviderRef']['contentHash']='0'*64
        state['wireChecks']={}
        with native_roles('maker') as conn:
            for i,(label,payload) in enumerate(variants.items()):
                payload['idempotencyKey']=command['idempotencyKey']+'.wire-'+str(i)
                checked=WindowProposeCommand.model_validate(payload)
                state['wireChecks'][label]=dict(command=checked.canonical_payload(),status='attempted')
                persist_signed_case(case,state)
                with pytest.raises(WindowStoreBlocked,match='23514'):race_store(conn,config).propose(checked)
                assert window_case_facts(state)==before
                state['wireChecks'][label]['status']='rejected-23514'
                persist_signed_case(case,state)
        with native_roles('consumer') as conn:state['results']['consume']=race_store(conn,config).consume(consume)
    after=original_risk_fingerprint()
    if kind=='budget_head':
        assert all(after[k]==risk[k] for k in ('aip_budget_cost_runtime_fence','aip_budget_reservation','aip_budget_bucket'))
    else:assert after==risk
    facts=window_case_facts(state)
    expected=dict(receipts={'propose':1,'decide':1,'consume':1},binding=1,fence=dict(version=2,revoked=False),policy=1,price=1)
    assert facts==(expected if kind in {'member','wire_source'} else before)
    state['verified']=dict(kind=kind,facts=facts,riskFenceReservationBucketUnchanged=True,
        budgetMetadataPublication=(kind=='budget_head'),legitimateProviderPublication=(kind=='provider_head'),
        originalParentInitiallyUnrevoked=True,formalHumanConsent=False,runtimeHoldBarrierAccepted=False)
    persist_signed_case(case,state)


def changed_provider_revision(provider):
    """A real bounded config change, not metadata-only duplicate content."""
    from aos_api.aip_model_runtime_store import AipModelRuntimeStore,canonical_hash
    timeout=provider.endpoint_profile.timeout_ms
    endpoint=provider.endpoint_profile.model_copy(update={'timeout_ms':timeout+1 if timeout<3_600_000 else timeout-1})
    candidate=provider.model_copy(update={'revision':provider.revision+1,'endpoint_profile':endpoint,'created_at':datetime.now(UTC)})
    body=candidate.model_dump(mode='json',by_alias=True)
    digest=canonical_hash({k:v for k,v in body.items() if k not in AipModelRuntimeStore._META_FIELDS})
    return type(provider).model_validate(candidate.model_copy(update={'content_hash':digest}).model_dump(mode='python',by_alias=True))


def test_clean_provider_drift_after_confirmed_publication_rollback(native_roles,tmp_path):
    if os.environ.get('AOS_POLICY_WINDOW_CLEAN_PARENT_TESTS')!='1':pytest.skip('dedicated clean cluster required')
    from aos_api.aip_model_runtime_store import AipModelRuntimeStore
    from aos_api.aip_budget_policy_window_commands import WindowConsumeCommand
    from aos_api.aip_budget_policy_window_store import WindowStoreBlocked
    from aos_api.aip_budget_policy_window_service import load_protected_config
    root=Path('/tmp/window-clean-drift-provider_head-r1');case=root/'case.json'
    state=json.loads(case.read_text())
    if state.get('verified'):pytest.skip('completed corrected original case retained')
    proof=json.loads((root/'provider-known-rollback-r1.json').read_text())
    assert state['database']==os.environ['AOS_POLICY_WINDOW_TEST_DATABASE']==proof['database']
    assert state['cluster']==os.environ['AOS_POLICY_WINDOW_TEST_CLUSTER']==proof['cluster']
    assert proof['knownRollback'] and proof['sqlstate']=='23505'
    assert state['publication']==proof['publication']
    assert not state.get('publicationRecoveryAttempted'),'unknown recovery outcome must be reconciled readonly, never repeated'
    command=state['commands']['propose'];old=command['expectedProviderRef'];publication=state['publication']
    with isolated_owner() as owner:
        head=owner.execute('SELECT current_revision,version FROM aip_provider_instance_head WHERE org_id=%s AND project_id=%s '
            'AND provider_instance_id=%s',(*SCOPE.key,old['assetId'])).fetchone()
        assert [head['current_revision'],head['version']]==proof['head']
        assert owner.execute("SELECT count(*) AS n FROM aip_model_runtime_receipt WHERE org_id=%s AND project_id=%s "
            "AND operation='provider_instance.publish' AND idempotency_key=%s",(*SCOPE.key,publication['key'])).fetchone()['n']==0
    config=load_protected_config(private_window_service_config(native_roles,tmp_path))
    store=AipModelRuntimeStore();provider=store.get_provider(SCOPE,old['assetId'])
    assert provider.revision==old['revision'] and provider.content_hash==old['contentHash']
    candidate=changed_provider_revision(provider)
    assert candidate.content_hash!=provider.content_hash
    state['publicationCorrection']=dict(key=publication['key'],expectedVersion=publication['expectedVersion'],
        payload=candidate.model_dump(mode='json',by_alias=True),reason='metadata-only duplicate rejected; bounded timeout config change')
    state['publicationRecoveryAttempted']=True
    persist_signed_case(case,state)
    risk=original_risk_fingerprint()
    published=store.publish_provider(SCOPE,provider.created_by,publication['key'],candidate,
                                     expected_version=publication['expectedVersion'])
    assert published.revision==provider.revision+1 and published.content_hash==candidate.content_hash
    state['publicationResult']=dict(revision=published.revision,contentHash=published.content_hash,lifecycle=published.lifecycle.value)
    persist_signed_case(case,state)
    consume=WindowConsumeCommand.model_validate(state['commands']['consume'])
    before=window_case_facts(state)
    assert before==dict(receipts={'propose':1,'decide':1},binding=0,fence=dict(version=1,revoked=False),policy=0,price=0)
    state['providerConsumerAttempted']=True
    persist_signed_case(case,state)
    with native_roles('consumer') as conn:
        with pytest.raises(WindowStoreBlocked,match='23514'):race_store(conn,config).consume(consume)
    assert window_case_facts(state)==before and original_risk_fingerprint()==risk
    state['verified']=dict(kind='provider_head',facts=before,riskFenceReservationBucketUnchanged=True,
        allSixRiskBudgetTablesUnchanged=True,legitimateProviderPublication=True,originalParentInitiallyUnrevoked=True,
        correctedKnownRollback23505=True,originalPublicationKeyPreserved=True,formalHumanConsent=False,runtimeHoldBarrierAccepted=False)
    persist_signed_case(case,state)
