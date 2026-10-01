"""Real signed Guard sources for disposable PostgreSQL compatibility tests.

The historical filename is retained for callers; no historical active row is
injected. Every returned active revision is produced through the formal chain.
"""
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
import datetime as dt
import json
import os
import socket
import ssl
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from uuid import uuid4

import jwt
import psycopg
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from jwt.algorithms import RSAAlgorithm

from tests.aip.test_network_consumer_boundary_pg import isolated_owner, SCOPE
from tests.aip.test_network_consumer_connection_pg import private_passfile


@pytest.fixture
def https_signer(tmp_path, monkeypatch):
    host = 'aos-jwks.integration.test'
    tls_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, host)])
    now = dt.datetime.now(dt.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(tls_key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - dt.timedelta(minutes=1)).not_valid_after(now + dt.timedelta(hours=1))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .add_extension(x509.SubjectAlternativeName([x509.DNSName(host)]), critical=False)
            .sign(tls_key, hashes.SHA256()))
    tls_dir = tmp_path / 'tls'
    tls_dir.mkdir(mode=0o700)
    cert_path, key_path = tls_dir / 'ca.pem', tls_dir / 'key.pem'
    for path, data in ((cert_path, cert.public_bytes(serialization.Encoding.PEM)),
                       (key_path, tls_key.private_bytes(serialization.Encoding.PEM,
                           serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))):
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
    signing_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(RSAAlgorithm.to_jwk(signing_key.public_key()))
    jwk.update(kid='isolated-consumer-key', use='sig', alg='RS256')
    body = json.dumps({'keys': [jwk]}).encode()
    requests = []
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *args):
            pass
    server = HTTPServer(('127.0.0.1', 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert_path, key_path)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    original_dns = socket.getaddrinfo
    def local_dns(address, *args, **kwargs):
        return original_dns('127.0.0.1' if address == host else address, *args, **kwargs)
    monkeypatch.setattr(socket, 'getaddrinfo', local_dns)
    monkeypatch.setenv('SSL_CERT_FILE', str(cert_path))
    monkeypatch.setenv('NO_PROXY', host + ',127.0.0.1,localhost')
    monkeypatch.setenv('no_proxy', host + ',127.0.0.1,localhost')
    issuer = f'https://{host}:{server.server_port}'
    for key, value in {'AOS_AUTH_ALLOW_DEV': '0', 'AOS_AUTH_EXTERNAL_ONLY': '1',
                       'AOS_OIDC_ISSUER': issuer, 'AOS_OIDC_AUDIENCE': 'isolated-consumer',
                       'AOS_OIDC_JWKS_URL': issuer + '/jwks'}.items():
        monkeypatch.setenv(key, value)
    for key in ('AOS_OIDC_ISSUERS', 'AOS_OIDC_JWKS_URLS'):
        monkeypatch.delenv(key, raising=False)
    thread.start()
    def sign(subject, *, changes=None, omit=None, wrong_key=False):
        claims = {'sub': subject, 'iss': issuer, 'aud': 'isolated-consumer',
                  'exp': int(time.time()) + 120, 'org_id': SCOPE.org_id,
                  'project_id': SCOPE.project_id}
        claims.update(changes or {})
        if omit:
            claims.pop(omit)
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048) if wrong_key else signing_key
        return jwt.encode(claims, key, algorithm='RS256', headers={'kid': jwk['kid']})
    try:
        yield sign, requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        key_path.unlink()


@pytest.fixture
def guard_issuer_factory(private_passfile):
    from contextlib import contextmanager
    import secrets
    from psycopg import sql, IsolationLevel
    from psycopg.rows import dict_row
    from aos_api.tenant_scope import apply_transaction_scope
    path = private_passfile.with_name("guard-issuer-pgpass")
    path.write_text("# isolated temporary credential\n")
    path.chmod(0o600)
    with isolated_owner() as admin:
        admin.execute("SELECT pg_advisory_lock(hashtext('guard-issuer-tests'))")
        original = admin.execute("SELECT rolcanlogin,rolpassword IS NULL AS no_password "
                                 "FROM pg_authid WHERE rolname='aos_guard_approval_issuer'").fetchone()
        assert original == {"rolcanlogin":False,"no_password":True}
        password = secrets.token_urlsafe(32)
        admin.execute(sql.SQL("ALTER ROLE aos_guard_approval_issuer LOGIN PASSWORD {}").format(sql.Literal(password)))
        admin.commit()
        host,port,database = admin.info.host,admin.info.port,admin.info.dbname
        path.write_text(f"{host}:{port}:{database}:aos_guard_approval_issuer:{password}\n")
        @contextmanager
        def factory(scope,read_only):
            with psycopg.connect(host=host,port=port,dbname=database,user="aos_guard_approval_issuer",
                passfile=str(path),row_factory=dict_row,
                options="-c statement_timeout=10000 -c lock_timeout=5000 -c idle_in_transaction_session_timeout=10000") as conn:
                conn.isolation_level = IsolationLevel.REPEATABLE_READ if read_only else IsolationLevel.SERIALIZABLE
                conn.read_only = read_only
                apply_transaction_scope(conn,scope)
                yield conn
        try:
            yield factory,database
        finally:
            admin.execute("ALTER ROLE aos_guard_approval_issuer NOLOGIN PASSWORD NULL")
            admin.commit()
            path.write_text("# removed temporary guard issuer credential\n")
            assert admin.execute("SELECT rolcanlogin,rolpassword IS NULL AS no_password "
                                 "FROM pg_authid WHERE rolname='aos_guard_approval_issuer'").fetchone() == original
            admin.execute("SELECT pg_advisory_unlock(hashtext('guard-issuer-tests'))")


@pytest.fixture
def guard_consumer_factory(private_passfile):
    from contextlib import contextmanager
    import secrets
    from psycopg import sql, IsolationLevel
    from psycopg.rows import dict_row
    path=private_passfile.with_name("guard-consumer-pgpass")
    path.write_text("# isolated temporary credential\n");path.chmod(0o600)
    with isolated_owner() as admin:
        admin.execute("SELECT pg_advisory_lock(hashtext('guard-consumer-tests'))")
        original=admin.execute("SELECT rolcanlogin,rolpassword IS NULL AS no_password FROM pg_authid WHERE rolname='aos_guard_policy_consumer_call'").fetchone()
        assert original=={"rolcanlogin":False,"no_password":True}
        password=secrets.token_urlsafe(32)
        admin.execute(sql.SQL("ALTER ROLE aos_guard_policy_consumer_call LOGIN PASSWORD {}").format(sql.Literal(password)));admin.commit()
        host,port,database=admin.info.host,admin.info.port,admin.info.dbname
        path.write_text(f"{host}:{port}:{database}:aos_guard_policy_consumer_call:{password}\n")
        @contextmanager
        def factory(scope,read_only):
            with psycopg.connect(host=host,port=port,dbname=database,user="aos_guard_policy_consumer_call",
                passfile=str(path),row_factory=dict_row,
                options="-c statement_timeout=10000 -c lock_timeout=5000 -c idle_in_transaction_session_timeout=10000") as conn:
                conn.isolation_level=IsolationLevel.REPEATABLE_READ if read_only else IsolationLevel.SERIALIZABLE
                conn.read_only=read_only
                conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",scope.key)
                yield conn
        try: yield factory,database
        finally:
            admin.execute("ALTER ROLE aos_guard_policy_consumer_call NOLOGIN PASSWORD NULL");admin.commit()
            path.write_text("# removed temporary consumer credential\n")
            assert admin.execute("SELECT rolcanlogin,rolpassword IS NULL AS no_password FROM pg_authid WHERE rolname='aos_guard_policy_consumer_call'").fetchone()==original
            admin.execute("SELECT pg_advisory_unlock(hashtext('guard-consumer-tests'))")



_formal_source = ContextVar("isolated_formal_guard_source", default=None)
_formal_network_source = ContextVar("isolated_formal_network_source", default=None)


def seed_historical_runtime_guard(scope, actor, item):
    """Compatibility entry; returns real active2, never an injected active1."""
    produce = _formal_source.get()
    if produce is None:
        raise RuntimeError("formal_guard_sources fixture required; direct active seed is retired")
    return produce(scope, actor, item)


def produce_formal_network_policy(scope, actor, item):
    produce = _formal_network_source.get()
    if produce is None:
        raise RuntimeError("formal source fixture required")
    return produce(scope, actor, item)


@pytest.fixture(autouse=True)
def formal_guard_sources(request):
    resources = None

    def prepare():
        nonlocal resources
        if resources is not None:
            return resources
        https_signer = request.getfixturevalue('https_signer')
        guard_issuer_factory = request.getfixturevalue('guard_issuer_factory')
        guard_consumer_factory = request.getfixturevalue('guard_consumer_factory')
        tmp_path = request.getfixturevalue('tmp_path')
        from aos_api.aip_runtime_guard_policy_contracts import EgressPolicyRevisionCreate, GuardPolicyLifecycle
        from aos_api.aip_runtime_guard_policy_store import AipRuntimeGuardPolicyStore
        from aos_api.aip_guard_policy_issuer import GuardMakerCommand, GuardDecisionCommand, GuardPolicyIssuer, propose_guard_signed
        from aos_api.aip_guard_policy_consumer import GuardConsumeCommand, GuardPolicyConsumer
        sign, _ = https_signer
        issuer_connect, database = guard_issuer_factory
        consumer_connect, consumer_database = guard_consumer_factory
        assert database == consumer_database
        issuer_dir, consumer_dir = tmp_path/'formal-issuer-attempts', tmp_path/'formal-consumer-attempts'
        issuer_dir.mkdir(mode=0o700); consumer_dir.mkdir(mode=0o700)
        issuer = GuardPolicyIssuer(issuer_connect, issuer_dir, expected_database=database)
        consumer = GuardPolicyConsumer(consumer_connect, consumer_dir, expected_database=database)

        resources = sign, issuer, consumer
        return resources

    def produce(scope, actor, item):
        from aos_api.aip_runtime_guard_policy_contracts import EgressPolicyRevisionCreate, GuardPolicyLifecycle
        from aos_api.aip_runtime_guard_policy_store import AipRuntimeGuardPolicyStore
        from aos_api.aip_guard_policy_issuer import GuardMakerCommand, GuardDecisionCommand, propose_guard_signed
        from aos_api.aip_guard_policy_consumer import GuardConsumeCommand
        sign, issuer, consumer = prepare()
        now = datetime.now(timezone.utc)
        if (scope != SCOPE or item.revision != 1 or item.lifecycle is not GuardPolicyLifecycle.ACTIVE
                or not item.effective_from <= now < item.effective_until):
            raise ValueError("initial, current, scoped active candidate required; inputs are not repaired")
        checker = 'formal-guard-checker-'+uuid4().hex
        with isolated_owner() as conn:
            conn.execute("INSERT INTO meta_org(id,name) VALUES(%s,'isolated guard org') ON CONFLICT DO NOTHING", (scope.org_id,))
            conn.execute("INSERT INTO meta_workspace(org_id,project_id,name) VALUES(%s,%s,'isolated guard workspace') ON CONFLICT DO NOTHING", scope.key)
            for subject in (actor,checker):
                conn.execute("INSERT INTO meta_membership(org_id,project_id,subject,role) VALUES(%s,%s,%s,'owner') ON CONFLICT DO NOTHING", (*scope.key,subject))
        raw = item.model_dump(mode='json',by_alias=True)
        draft = type(item).model_validate({**raw,'lifecycle':'draft'})
        candidate = type(item).model_validate({**raw,'revision':2})
        store = AipRuntimeGuardPolicyStore()
        publish = store.publish_egress if type(item) is EgressPolicyRevisionCreate else store.publish_data_classification
        publish(scope, actor, 'formal-draft-'+uuid4().hex, draft)
        expiry = min(now+timedelta(minutes=5),item.effective_until)
        bundle = propose_guard_signed(GuardMakerCommand(orgId=scope.org_id,projectId=scope.project_id,
            bearerToken=sign(actor),candidate=candidate,expectedVersion=1,
            idempotencyKey='formal-maker-'+uuid4().hex,expiresAt=expiry))
        approval = issuer.execute(GuardDecisionCommand(orgId=scope.org_id,projectId=scope.project_id,
            bearerToken=sign(checker),proposalId=bundle.proposal.id,idempotencyKey='formal-checker-'+uuid4().hex,
            decision=dict(expectedProposalVersion=bundle.proposal.version,expectedProposalHash=bundle.proposal.proposal_hash,
                decision='approved',reason='isolated compatibility source',approvalExpiresAt=expiry)))
        assert approval['status']=='observed'
        result = consumer.execute(GuardConsumeCommand(orgId=scope.org_id,projectId=scope.project_id,
            bearerToken=sign(actor),proposalId=bundle.proposal.id,approvalEventId=approval['approvalEventId'],
            proposalHash=bundle.proposal.proposal_hash,targetContentHash=bundle.proposal.payload['targetContentHash'],
            bindingHash=bundle.proposal.action_binding_hash))
        assert result['status']=='observed'
        read = store.get_egress if type(item) is EgressPolicyRevisionCreate else store.get_data_classification
        saved = read(scope,item.policy_id,2)
        assert saved.content_hash==result['result']['contentHash'] and saved.lifecycle is GuardPolicyLifecycle.ACTIVE
        return saved

    def produce_network(scope, actor, item):
        import secrets
        from psycopg import sql
        from aos_api.auth import resolve_principal
        from aos_api.aip_network_policy_action_producer import propose_network_activation
        from aos_api.aip_network_policy_store import AipNetworkPolicyStore
        from aos_api.aip_network_issuer_contracts import NetworkIssuerDecisionCommand
        from aos_api.aip_network_issuer_connection import IssuerDatabaseConfig, connect_issuer_decision, connect_issuer_read_only
        from aos_api.aip_network_issuer_service import issue_decision_once
        from aos_api.aip_network_consumer_contracts import NetworkConsumerCommand
        from aos_api.aip_network_consumer_service import consume_network_once
        from tests.aip.test_network_consumer_connection_pg import live_test_config
        if scope != SCOPE: raise ValueError('isolated positive scope required')
        sign,_,_=prepare()
        checker='formal-network-checker-'+uuid4().hex
        with isolated_owner() as conn:
            conn.execute("INSERT INTO meta_membership(org_id,project_id,subject,role) VALUES(%s,%s,%s,'owner')",(*scope.key,checker))
        principal=resolve_principal(token=sign(actor),header_org=scope.org_id,header_project=scope.project_id)
        expiry=min(datetime.now(timezone.utc)+timedelta(minutes=5),item.effective_until)
        bundle=propose_network_activation(principal,item,expected_version=0,idempotency_key='formal-network-'+uuid4().hex,expires_at=expiry)
        command=NetworkIssuerDecisionCommand(schemaVersion=1,orgId=scope.org_id,projectId=scope.project_id,
            bearerToken=sign(checker),proposalId=bundle.proposal.id,idempotencyKey='formal-network-approve-'+uuid4().hex,
            decision=dict(expectedProposalVersion=bundle.proposal.version,expectedProposalHash=bundle.proposal.proposal_hash,
                decision='approved',reason='isolated formal network source',approvalExpiresAt=expiry))
        private=request.getfixturevalue('private_passfile')
        issuer_path=private.with_name('network-issuer-pgpass');issuer_path.write_text('# temporary\n');issuer_path.chmod(0o600)
        consumer_path=private.with_name('network-consumer-pgpass');consumer_path.write_text('# temporary\n');consumer_path.chmod(0o600)
        tmp=request.getfixturevalue('tmp_path')
        issuer_attempts=tmp/('network-issuer-'+uuid4().hex);issuer_attempts.mkdir(mode=0o700)
        consumer_attempts=tmp/('network-consumer-'+uuid4().hex);consumer_attempts.mkdir(mode=0o700)
        with isolated_owner() as admin:
            admin.execute("SELECT pg_advisory_lock(hashtext('formal-network-issuer-fixture'))")
            original=admin.execute("SELECT rolcanlogin,rolpassword IS NULL AS no_password FROM pg_authid WHERE rolname='aos_network_approval_issuer'").fetchone()
            assert original=={'rolcanlogin':False,'no_password':True}
            password=secrets.token_urlsafe(32)
            admin.execute(sql.SQL('ALTER ROLE aos_network_approval_issuer LOGIN PASSWORD {}').format(sql.Literal(password)));admin.commit()
            host,port,database=admin.info.host,admin.info.port,admin.info.dbname
            try:
                issuer_path.write_text(f'{host}:{port}:{database}:aos_network_approval_issuer:{password}\n')
                config=IssuerDatabaseConfig(host,port,database,issuer_path)
                result=issue_decision_once(command,attempt_directory=issuer_attempts,
                    decision_connect_factory=lambda target:connect_issuer_decision(config,target),
                    read_connect_factory=lambda:connect_issuer_read_only(config,scope),expected_database=database)
                assert result.status.value=='observed'
            finally:
                admin.execute('ALTER ROLE aos_network_approval_issuer NOLOGIN PASSWORD NULL');admin.commit()
                issuer_path.write_text('# removed temporary credential\n')
                assert admin.execute("SELECT rolcanlogin,rolpassword IS NULL AS no_password FROM pg_authid WHERE rolname='aos_network_approval_issuer'").fetchone()==original
                admin.execute("SELECT pg_advisory_unlock(hashtext('formal-network-issuer-fixture'))")
        consume=NetworkConsumerCommand(schemaVersion=1,orgId=scope.org_id,projectId=scope.project_id,
            bearerToken=sign(actor),proposalId=bundle.proposal.id,approvalEventId=result.event_id,
            proposalHash=bundle.proposal.proposal_hash,targetContentHash=bundle.proposal.payload['targetContentHash'],
            bindingHash=bundle.proposal.action_binding_hash)
        with live_test_config(consumer_path) as config:
            observed=consume_network_once(consume,config,consumer_attempts)
            assert observed['status']=='observed'
        return AipNetworkPolicyStore().get(scope,item.policy_id,item.revision)

    token = _formal_source.set(produce)
    network_token = _formal_network_source.set(produce_network)
    try: yield produce
    finally:
        _formal_network_source.reset(network_token)
        _formal_source.reset(token)
