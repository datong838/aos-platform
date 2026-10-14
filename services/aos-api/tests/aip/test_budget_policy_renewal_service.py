"""Pure B envelope/schema tests; no identity/PG acceptance inferred here."""
import json
from pathlib import Path
import pytest
from aos_api.aip_budget_policy_renewal_service import RenewalRequest,protocol_schema
from aos_api.aip_budget_policy_renewal_contracts import (
    RenewalDecisionCommand,RenewalConsumeCommand,RenewalRevocationCommand,
)


def envelope(operation,**extra):
    c={'schemaVersion':1,'orgId':'org-org','projectId':'dev-project','idempotencyKey':'fixture-service',
       'proposalId':'fixture-proposal','proposalHash':'a'*64}
    if operation=='decide':c.update(targetActiveHash='b'*64,decision='approved')
    else:c.update(decisionId='fixture-decision',decisionHash='b'*64)
    if operation=='revoke':c['reasonCode']='approval_withdrawn'
    body={'schemaVersion':1,'mode':'execute','operation':operation,'command':c}
    if operation in {'decide','revoke'}:body['bearerToken']='fixture-invalid-token-not-consent'
    return {**body,**extra}


@pytest.mark.parametrize('op,cls',[('decide',RenewalDecisionCommand),('consume',RenewalConsumeCommand),('revoke',RenewalRevocationCommand)])
def test_exact_operation_and_typed_command_reparse(op,cls):
    r=RenewalRequest.model_validate(envelope(op))
    assert type(r.command) is cls
    assert r.revalidated().command.request_hash==r.command.request_hash


@pytest.mark.parametrize('mutation',['boolVersion','wrongCommand','machineToken','issuerMissingToken','extraActor'])
def test_wire_identity_and_discriminator_mutation_rejected(mutation):
    body=envelope('consume')
    if mutation=='boolVersion':body['schemaVersion']=True
    elif mutation=='wrongCommand':body['operation']='decide'
    elif mutation=='machineToken':body['bearerToken']=None
    elif mutation=='issuerMissingToken':body=envelope('decide');body.pop('bearerToken')
    else:body['actor']='forged'
    with pytest.raises(ValueError):RenewalRequest.model_validate(body)


def test_generated_json_schema_matches_shipped_schema_and_discriminator():
    path=Path(__file__).resolve().parents[2]/'aos_api/aip_budget_policy_renewal_schema.json'
    schema=json.loads(path.read_text())
    assert schema==protocol_schema()
    assert schema['additionalProperties'] is False
    assert len(schema['allOf'])==4


def test_generated_schema_includes_closed_native_result_frame():
    frame=protocol_schema()['$defs']['RenewalResponseFrame']
    assert frame['additionalProperties'] is False
    assert set(frame['required'])=={'schemaVersion','operation','requestHash','activationEligible','result'}
    properties=frame['properties']
    assert properties['schemaVersion']=={'type':'integer','const':1}
    assert properties['activationEligible']=={'type':'boolean','const':False}
    assert properties['requestHash']['pattern']=='^[0-9a-f]{64}$'
    assert set(properties['operation']['enum'])=={'propose','decide','consume','revoke'}
    result=properties['result']
    assert set(result['required'])=={'operation','requestHash','activationEligible','status'}
    assert set(result['properties']['status']['enum'])=={'prepared','decided','revoked','observed','unresolved','conflict','blocked'}


def test_model_copy_cannot_smuggle_actor_or_command_kind():
    r=RenewalRequest.model_validate(envelope('consume'))
    altered=r.model_copy(update={'operation':'decide'})
    with pytest.raises(ValueError):altered.revalidated()


# Original fixtures only create data in the explicitly owned disposable DB.
from tests.aip.test_budget_policy_renewal_pg import schema_database, schema_source as original_schema_source


@pytest.fixture(scope='session')
def schema_source(schema_database):
    """Seed historical fixture facts under admin locks; guards restored pre-commit.

    Full migrations prohibit unapproved ACTIVE inserts. This setup is explicitly
    fixture history, never an acceptance of human approval or a runtime bypass.
    No B operation runs until both original guards are enabled again.
    """
    _,admin=schema_database
    source=original_schema_source.__wrapped__(schema_database)
    with admin.transaction():
        admin.execute("INSERT INTO public.meta_org(id,name) VALUES('org-org','isolated B fixture org')")
        admin.execute("INSERT INTO public.meta_workspace(org_id,project_id,name) VALUES('org-org','dev-project','isolated B fixture workspace')")
        admin.execute('ALTER TABLE public.aip_budget_revision DISABLE TRIGGER aip_budget_active_insert_guard')
        admin.execute('ALTER TABLE public.aip_model_governance_policy_revision DISABLE TRIGGER cost_configuration_write_guard')
        value=next(source)
        admin.execute('SET CONSTRAINTS ALL IMMEDIATE')
        admin.execute('ALTER TABLE public.aip_budget_revision ENABLE TRIGGER aip_budget_active_insert_guard')
        admin.execute('ALTER TABLE public.aip_model_governance_policy_revision ENABLE TRIGGER cost_configuration_write_guard')
    try:yield value
    finally:
        try:next(source)
        except StopIteration:pass


@pytest.fixture
def isolated_signed_gateway(schema_source,tmp_path,monkeypatch):
    """Actual RS256/JWKS in a separate PG network namespace, never real consent."""
    import os,hashlib,threading,time
    import jwt
    from cryptography.hazmat.primitives.asymmetric import rsa
    from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
    from psycopg.conninfo import conninfo_to_dict
    from psycopg import sql
    from tests.aip.test_budget_policy_renewal_connection import closed_config
    from aos_api.aip_budget_policy_renewal_connection import load_protected_config,_CALLERS,_FORBIDDEN_ENV
    if os.environ.get('AOS_RENEWAL_ISOLATED_SIGNER')!='1':
        pytest.skip('separate owned network namespace required for fixture signer')
    dsn,admin,source,now=schema_source
    parts=conninfo_to_dict(dsn)
    assert parts['host']=='127.0.0.1' and parts['port']=='5432'
    assert parts['dbname'].startswith('aos_test_')
    for key in _FORBIDDEN_ENV:monkeypatch.delenv(key,raising=False)
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    jwk=json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    jwk.update(kid='isolated-b-fixture',alg='RS256',use='sig')
    requests=[]
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            if self.path!='/realms/qyh-local/protocol/openid-connect/certs':
                self.send_error(404);return
            body=json.dumps({'keys':[jwk]}).encode()
            self.send_response(200);self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',18448),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    path,value=closed_config(tmp_path)
    seal=admin.execute("SELECT obj_description('public.aip_budget_policy_renewal_proposal'::regclass,'pg_class')").fetchone()[0]
    value['enabled']=True
    for purpose,user in _CALLERS.items():
        # Fixture-only secret; HBA is SCRAM for callers in the owned test PG.
        password='isolated-b-fixture-password'
        admin.execute(sql.SQL('ALTER ROLE {} LOGIN PASSWORD {}').format(sql.Identifier(user),sql.Literal(password)))
        profile=value['profiles'][purpose]
        passfile=Path(profile['passfile'])
        passfile.write_text(f"127.0.0.1:5432:{parts['dbname']}:{user}:{password}\n")
        profile.update(port=5432,database=parts['dbname'],
            passfileSha256=hashlib.sha256(passfile.read_bytes()).hexdigest(),
            manifestSha256=hashlib.sha256(seal.encode()).hexdigest())
    path.write_text(json.dumps(value))
    attempts=tmp_path/'attempts';attempts.mkdir(mode=0o700)
    issuer='http://127.0.0.1:18448/realms/qyh-local'
    def token(**overrides):
        claims={'iss':issuer,'aud':'aos-api','sub':'6f31cfdc-a26c-4f1f-ad6b-95a8559cc657',
            'iat':int(time.time()),'exp':int(time.time())+120,
            'org_id':'org-org','project_id':'dev-project','roles':['admin']}
        claims.update(overrides)
        return jwt.encode(claims,key,algorithm='RS256',headers={'kid':'isolated-b-fixture'})
    try:yield load_protected_config(path),attempts,token,requests,schema_source
    finally:
        server.shutdown();server.server_close();thread.join(timeout=3)
        for user in _CALLERS.values():
            admin.execute(sql.SQL('ALTER ROLE {} NOLOGIN PASSWORD NULL').format(sql.Identifier(user)))


def test_native_private_service_signed_chain_and_at_most_once(isolated_signed_gateway):
    from datetime import timedelta
    from aos_api.aip_budget_policy_renewal_service import RenewalService
    from aos_api.aip_budget_policy_renewal_connection import open_purpose_connection
    from aos_api.aip_model_governance_policy_store import canonical_hash
    config,attempts,token,http_requests,(dsn,admin,source,now)=isolated_signed_gateway
    service=RenewalService(config,attempts)
    def actual_process(request):
        from aos_api.aip_budget_policy_renewal_process import run_renewal_process
        body=request.model_dump(mode='json',by_alias=True,exclude={'bearer_token'})
        if request.bearer_token is not None:
            body['bearerToken']=request.bearer_token.get_secret_value()
        result=run_renewal_process(config.path,attempts,json.dumps(body).encode(),timeout=15)
        assert result.get('result',{}).get('status')=='observed',result
        assert result['activationEligible'] is False
        return result['result']
    def request(op,command,bearer=None):
        value={'schemaVersion':1,'mode':'execute','operation':op,'command':command}
        if bearer is not None:value['bearerToken']=bearer
        return RenewalRequest.model_validate(value)
    base={'schemaVersion':1,'orgId':'org-org','projectId':'dev-project'}
    p=request('propose',{**base,'idempotencyKey':'b-native-propose','sourcePolicyId':source.policy_id,
        'expectedSourceRevision':13,'expectedHeadVersion':13,'expectedSourceHash':source.content_hash,
        'effectiveFrom':now-timedelta(minutes=1),'effectiveUntil':now+timedelta(minutes=30)})
    with open_purpose_connection(config,'maker',True) as conn:
        assert conn.read_only is True
        assert conn.execute('SHOW transaction_read_only').fetchone()[0]=='on'
        conn.rollback()
    proposal=actual_process(p)
    assert proposal['status']=='observed'
    assert service.execute(p)['status']=='observed'
    assert admin.execute('SELECT count(*) FROM public.aip_budget_policy_renewal_proposal').fetchone()[0]==1
    native_service_fault_matrix(service,p,config,attempts,admin)
    # The exact target is the SQL-authoritative proposal payload, not reconstructed UI data.
    payload=admin.execute('SELECT payload FROM public.aip_budget_policy_renewal_proposal WHERE proposal_id=%s',
                          (proposal['proposalId'],)).fetchone()[0]
    d=request('decide',{**base,'idempotencyKey':'b-native-decide','proposalId':proposal['proposalId'],
        'proposalHash':proposal['proposalHash'],'targetActiveHash':canonical_hash(payload['targetActive']),
        'decision':'approved'},token())
    # Crypto/tenant failures and current membership denial precede Attempt reservation.
    for bad in (token(aud='wrong'),token(exp=1),token(org_id='dev-org'),token(sub='fixture-other')):
        denied=d.model_copy(update={'bearer_token':__import__('pydantic').SecretStr(bad)})
        with pytest.raises(ValueError):service.execute(denied)
    assert len(list(attempts.iterdir()))==1
    admin.execute("UPDATE public.meta_membership SET role='viewer' WHERE subject=%s",(config.binding.subject,))
    try:
        with pytest.raises(ValueError):service.execute(d)
    finally:
        admin.execute("UPDATE public.meta_membership SET role='admin' WHERE subject=%s",(config.binding.subject,))
    decision=actual_process(d)
    assert decision['status']=='observed' and http_requests
    assert service.execute(d)['status']=='observed'
    c=request('consume',{**base,'idempotencyKey':'b-native-consume','proposalId':proposal['proposalId'],
        'proposalHash':proposal['proposalHash'],'decisionId':decision['decisionId'],
        'decisionHash':decision['decisionHash']})
    consumed=actual_process(c)
    assert consumed['status']=='observed' and consumed['activationEligible'] is False
    assert service.execute(c)['status']=='observed'
    assert admin.execute('SELECT current_revision,version FROM public.aip_model_governance_policy_head').fetchone()==(14,14)
    assert admin.execute('SELECT count(*) FROM public.aip_model_governance_policy_revision').fetchone()[0]==2
    from tests.aip.test_budget_policy_renewal_process import native_readonly_process_assertions
    native_readonly_process_assertions(isolated_signed_gateway)
    r=request('revoke',{**base,'idempotencyKey':'b-native-revoke','proposalId':proposal['proposalId'],
        'proposalHash':proposal['proposalHash'],'decisionId':decision['decisionId'],
        'decisionHash':decision['decisionHash'],'reasonCode':'approval_withdrawn'},token())
    assert actual_process(r)['status']=='observed'
    assert service.execute(r)['status']=='observed'
    assert service.reconcile(c)['status']=='observed'  # immutable historical publication
    markers=list(attempts.iterdir())
    assert len(markers)==4
    for marker in markers:
        record=json.loads(marker.read_text())
        assert record['state']=='ATTEMPTED' and record['namespace'].startswith('budget-policy-renewal/v1/')
        assert 'bearerToken' not in record and 'password' not in record


def native_service_fault_matrix(service,request,config,attempts,admin):
    """Real PG COMMIT with transport fault; no mocked identity or write outcome."""
    import psycopg
    from psycopg import sql
    from aos_api.aip_budget_policy_renewal_service import RenewalService
    from aos_api.aip_budget_policy_renewal_connection import RenewalConnectionBlocked
    from aos_api.aip_budget_policy_renewal_store import RenewalAuthorityStore,RenewalStoreUnknown
    before=admin.execute('SELECT count(*) FROM public.aip_budget_policy_renewal_receipt').fetchone()[0]
    marker=next(attempts.iterdir());original_marker=marker.read_bytes()
    marker.write_bytes(b'{"schemaVersion":1,')
    try:assert service.execute(request)['status']=='unresolved'
    finally:marker.write_bytes(original_marker)  # known fixture history, no execute rearming
    changed=request.model_copy(update={'command':request.command.model_copy(update={'expected_source_hash':'b'*64})})
    assert service.execute(changed)['status']=='conflict'
    assert admin.execute('SELECT count(*) FROM public.aip_budget_policy_renewal_receipt').fetchone()[0]==before
    private_original=config.path.read_bytes()
    closed=json.loads(private_original);closed['enabled']=False;config.path.write_text(json.dumps(closed))
    try:
        with pytest.raises(RenewalConnectionBlocked):service.execute(request)
    finally:config.path.write_bytes(private_original)
    seal=admin.execute("SELECT obj_description('public.aip_budget_policy_renewal_proposal'::regclass,'pg_class')").fetchone()[0]
    admin.execute("COMMENT ON TABLE public.aip_budget_policy_renewal_proposal IS 'fixture-manifest-drift'")
    try:
        with pytest.raises(RenewalConnectionBlocked):service.execute(request)
    finally:
        admin.execute(sql.SQL('COMMENT ON TABLE public.aip_budget_policy_renewal_proposal IS {}').format(sql.Literal(seal)))
    profile=config.profile('maker')
    with pytest.raises(psycopg.OperationalError,match='password authentication failed'):
        psycopg.connect(host=profile.host,port=profile.port,dbname=profile.database,
            user=profile.user,password='wrong-isolated-fixture-password',connect_timeout=3)
    lost_directory=attempts.parent/'lostack-attempts';lost_directory.mkdir(mode=0o700)
    lost_service=RenewalService(config,lost_directory)
    lost_request=request.model_copy(update={'command':request.command.model_copy(update={'idempotency_key':'b-native-commit-ack-lost'})})
    actual_propose=RenewalAuthorityStore.propose
    entered=[]
    def commit_then_drop_return(store,command):
        result=actual_propose(store,command)  # genuine native tx and outer COMMIT
        assert result['status']=='prepared'
        entered.append(command.request_hash)
        raise RenewalStoreUnknown(operation='propose',key=command.idempotency_key,request_hash=command.request_hash)
    with pytest.MonkeyPatch.context() as fault:
        fault.setattr(RenewalAuthorityStore,'propose',commit_then_drop_return)
        recovered=lost_service.execute(lost_request)
        assert recovered['status']=='observed' and recovered['requestHash']==lost_request.command.request_hash
        assert lost_service.execute(lost_request)['status']=='observed'
    assert entered==[lost_request.command.request_hash]
    assert len(list(lost_directory.iterdir()))==1
    assert admin.execute('SELECT count(*) FROM public.aip_budget_policy_renewal_proposal').fetchone()[0]==2
    assert admin.execute('SELECT count(*) FROM public.aip_budget_policy_renewal_receipt').fetchone()[0]==before+1
