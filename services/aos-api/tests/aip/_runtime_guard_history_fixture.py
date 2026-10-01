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
_formal_provider_source = ContextVar("isolated_formal_provider_source", default=None)


def produce_formal_provider(scope, actor, provider_id):
    produce = _formal_provider_source.get()
    if produce is None:
        raise RuntimeError("formal source fixture required")
    return produce(scope, actor, provider_id)


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
        from aos_api.aip_model_governance_policy_contracts import QuotaPolicyRevisionCreate
        from aos_api.aip_model_governance_policy_store import AipModelGovernancePolicyStore
        from aos_api.aip_quota_policy_consumer import QuotaPolicyConsumer
        sign, issuer, consumer = prepare()
        is_quota = type(item) is QuotaPolicyRevisionCreate
        if is_quota:
            factory, database = request.getfixturevalue('guard_consumer_factory')
            folder = request.getfixturevalue('tmp_path') / ('quota-attempts-'+uuid4().hex)
            folder.mkdir(mode=0o700)
            consumer = QuotaPolicyConsumer(factory,folder,expected_database=database)
        now = datetime.now(timezone.utc)
        if (scope != SCOPE or item.revision != 1 or item.lifecycle.value != "active"
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
        store = AipModelGovernancePolicyStore() if is_quota else AipRuntimeGuardPolicyStore()
        publish = store.publish_quota if is_quota else (store.publish_egress if type(item) is EgressPolicyRevisionCreate else store.publish_data_classification)
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
        read = store.get_quota if is_quota else (store.get_egress if type(item) is EgressPolicyRevisionCreate else store.get_data_classification)
        saved = read(scope,item.policy_id,2)
        assert saved.content_hash==result['result']['contentHash'] and saved.lifecycle.value == "active"
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

    def produce_provider(scope, actor, provider_id):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from aos_api.errors import register_exception_handlers
        from aos_api.routers.aip_model_runtime import router
        from aos_api.aip_provider_plugin_authority import ProviderPluginAuthority
        from aos_api.aip_model_runtime_contracts import ProviderInstanceRevision
        from aos_api.aip_model_runtime_store import canonical_hash
        from aos_api.aip_runtime_guard_policy_contracts import (
            EgressPolicyRevisionCreate, DataClassificationPolicyRevisionCreate,
        )
        sign, _, _ = prepare()
        now = datetime.now(timezone.utc)
        common = dict(revision=1, environment='development',
            effectiveFrom=now-timedelta(minutes=1), effectiveUntil=now+timedelta(hours=1),
            owner=actor, approvalRef='isolated-signed-source', lifecycle='active')
        egress = produce(scope, actor, EgressPolicyRevisionCreate(
            **common, policyId=provider_id+'-egress', allowedSchemes=['https'],
            allowedHosts=['api.agnes-ai.cn'], allowedPorts=[443],
            allowPublicFallback=False, unknownDestinationBehavior='block',
            regionState='confirmed', region='isolated-test'))
        data = produce(scope, actor, DataClassificationPolicyRevisionCreate(
            **common, policyId=provider_id+'-data', allowedClassifications=['public_catalog'],
            prohibitedClassifications=['direct_pii','raw_order_detail','customer_conversation',
                'credential','commercial_sensitive','cross_tenant','unknown'],
            denyUnknown=True, allowDirectPii=False, allowCommercialSensitive=False,
            allowCrossTenant=False))
        plugin = ProviderPluginAuthority().get(scope, 'agnes-text')
        def ref(kind, identity, item):
            return dict(assetType=kind, assetId=identity, revision=item.revision, contentHash=item.content_hash)
        provider = ProviderInstanceRevision(
            tenant=dict(orgId=scope.org_id,projectId=scope.project_id),
            providerInstanceId=provider_id, revision=1, contentHash='0'*64,
            pluginRef=ref('ProviderPluginRevision',plugin.provider_plugin_id,plugin),
            endpointProfile=dict(baseUrl='https://api.agnes-ai.cn',region='isolated-test',timeoutMs=1000),
            secretRef='vault://isolated/no-secret',secretVersion='1',
            egressPolicyRef=ref('EgressPolicyRevision',egress.policy_id,egress),
            dataClassificationPolicyRef=ref('DataClassificationPolicyRevision',data.policy_id,data),
            lifecycle='active',createdBy=actor,createdAt=now)
        body = provider.model_dump(mode='json',by_alias=True)
        body['contentHash'] = canonical_hash({k:v for k,v in body.items()
            if k not in {'tenant','revision','contentHash','createdBy','createdAt'}})
        app = FastAPI()
        register_exception_handlers(app)
        app.include_router(router)
        with TestClient(app) as client:
            response = client.post('/v1/aip/model-runtime/providers',json=body,headers={
                'Authorization':'Bearer '+sign(actor),'X-Org-Id':scope.org_id,
                'X-Project-Id':scope.project_id,'If-Match':'0',
                'Idempotency-Key':'formal-provider-'+uuid4().hex})
        assert response.status_code == 201, response.text
        return ProviderInstanceRevision.model_validate(response.json())

    token = _formal_source.set(produce)
    network_token = _formal_network_source.set(produce_network)
    provider_token = _formal_provider_source.set(produce_provider)
    try: yield produce
    finally:
        _formal_provider_source.reset(provider_token)
        _formal_network_source.reset(network_token)
        _formal_source.reset(token)
