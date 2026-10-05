"""Independent original source approval ACL, disposable PG only."""
import pytest
import psycopg
from tests.aip.test_network_consumer_boundary_pg import isolated_owner, SCOPE

ISSUER='aos_source_license_approval_issuer'


def test_source_approval_acl_is_narrow_and_does_not_provision_login():
    with isolated_owner() as conn:
        assert conn.execute('SELECT rolcanlogin FROM pg_roles WHERE rolname=%s',(ISSUER,)).fetchone()=={'rolcanlogin':False}
        assert conn.execute('SELECT count(*) AS n FROM pg_auth_members WHERE roleid=%s::regrole OR member=%s::regrole',(ISSUER,ISSUER)).fetchone()['n']==0
        for table in ('aip_action_approval_event','aip_action_event'):
            assert conn.execute("SELECT has_table_privilege(%s,%s,'INSERT') AS allowed",(ISSUER,table)).fetchone()['allowed']
            assert not conn.execute("SELECT has_table_privilege(%s,%s,'UPDATE,DELETE') AS allowed",(ISSUER,table)).fetchone()['allowed']
        for table in ('aip_license_source_issuance','aip_license_source_head','aip_agent_registry_receipt','meta_membership','bundle_installation'):
            assert not conn.execute("SELECT has_table_privilege(%s,%s,'INSERT,UPDATE,DELETE') AS allowed",(ISSUER,table)).fetchone()['allowed']
        for table,column in [('meta_membership','subject'),('bundle_installation','installation_id'),('meta_action_type','id'),('meta_object_type','id')]:
            assert conn.execute("SELECT has_column_privilege(%s,%s,%s,'UPDATE') AS allowed",(ISSUER,table,column)).fetchone()['allowed']
        updates=conn.execute("SELECT table_name,column_name FROM information_schema.columns WHERE table_schema='public' AND has_column_privilege(%s,table_schema||'.'||quote_ident(table_name),column_name,'UPDATE')",(ISSUER,)).fetchall()
        assert {(row['table_name'],row['column_name']) for row in updates}=={
            ('meta_membership','subject'),('bundle_installation','installation_id'),
            ('meta_object_type','id'),('meta_action_type','id'),
            ('aip_action_proposal','status'),('aip_action_proposal','version'),('aip_action_proposal','updated_at'),
            ('aip_action_draft','status'),('aip_action_draft','updated_at')}
        assert conn.execute("SELECT has_function_privilege(%s,'public.aos_license_source_initialization_lock(text,text,text,bigint,text,boolean)','EXECUTE') AS allowed",(ISSUER,)).fetchone()['allowed']


def test_store_rejects_callback_as_independent_source_checker():
    from aos_api.aip_action_store import AipActionStore
    with pytest.raises(TypeError,match='exact source license approval guard'):
        AipActionStore(lambda: pytest.fail('must reject before connection'),source_license_approval_guard=lambda:None)


@pytest.mark.parametrize('table,column',[('meta_membership','subject')])
def test_issuer_lock_column_cannot_change_current_owner_or_installation(table,column):
    from psycopg import sql
    with isolated_owner() as conn:
        conn.execute("INSERT INTO twa_org(id,name) VALUES('org-org','test-only') ON CONFLICT DO NOTHING")
        conn.execute("INSERT INTO twa_workspace(org_id,project_id,name) VALUES('org-org','dev-project','test-only') ON CONFLICT DO NOTHING")
        conn.execute("INSERT INTO meta_org(id,name) VALUES('org-org','test-only') ON CONFLICT DO NOTHING")
        conn.execute("INSERT INTO meta_workspace(org_id,project_id,name) VALUES('org-org','dev-project','test-only') ON CONFLICT DO NOTHING")
        if table=='meta_membership':
            conn.execute("INSERT INTO meta_membership(org_id,project_id,subject,role) VALUES(%s,%s,'b88-acl-readonly-owner','owner') ON CONFLICT DO NOTHING",SCOPE.key)
        # Metadata row always exists; installation rows need the signed acceptance fixture.
        conn.execute(sql.SQL('SET SESSION AUTHORIZATION {}').format(sql.Identifier(ISSUER)))
        conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",SCOPE.key)
        with pytest.raises(psycopg.errors.InsufficientPrivilege,match='SOURCE_APPROVAL_READ_LOCK_ONLY'):
            conn.execute(sql.SQL('UPDATE public.{} SET {}={} WHERE org_id=%s AND project_id=%s').format(sql.Identifier(table),sql.Identifier(column),sql.Identifier(column)),SCOPE.key)
        conn.rollback()


def assert_independent_signed_source_approval(proposal,maker,loader,release_policy):
    """Real dedicated PG login, actual signed installation, original event.

    Test-only Owner/LOGIN provision. Production credentials/JWT are not supplied.
    """
    import secrets
    from uuid import uuid4
    from psycopg import sql, IsolationLevel
    from psycopg.rows import dict_row
    from aos_api.db import get_dsn
    from aos_api.auth import Principal
    from aos_api.aip_action_models import DecideActionProposalRequest
    from aos_api.aip_action_store import AipActionConflict,canonical_hash
    from aos_api.aip_license_source_approval import approve_source_license_in_transaction
    from aos_api.aip_license_source_proposal import SourceLicenseProposalBlocked
    checker='b88-checker-'+uuid4().hex
    admin_actor='b88-admin-checker-'+uuid4().hex
    other_owner='b88-other-owner-'+uuid4().hex
    password=secrets.token_urlsafe(32)
    with isolated_owner() as admin:
        admin.execute("INSERT INTO meta_membership(org_id,project_id,subject,role) VALUES(%s,%s,%s,'owner')",(*SCOPE.key,checker))
        admin.execute("INSERT INTO meta_membership(org_id,project_id,subject,role) VALUES(%s,%s,%s,'admin')",(*SCOPE.key,admin_actor))
        admin.execute("INSERT INTO meta_membership(org_id,project_id,subject,role) VALUES(%s,%s,%s,'owner')",(*SCOPE.key,other_owner))
    # Adversarial original row/draft: internal snapshot and row disagree,
    # while both hashes are internally consistent. This is not a legal request.
    forged='b88-draft-mismatch-'+uuid4().hex
    from psycopg.types.json import Jsonb
    with isolated_owner() as admin:
        row=admin.execute('SELECT * FROM aip_action_proposal WHERE org_id=%s AND project_id=%s AND proposal_id=%s',(*SCOPE.key,proposal.proposal.id)).fetchone()
        draft=admin.execute('SELECT * FROM aip_action_draft WHERE org_id=%s AND project_id=%s AND proposal_id=%s',(*SCOPE.key,proposal.proposal.id)).fetchone()
        draft['snapshot']={**draft['snapshot'],'purpose':'forged different immutable purpose'}
        forged_hash=canonical_hash(draft['snapshot'])
        row.update(proposal_id=forged,idempotency_key=forged,proposal_hash=forged_hash)
        draft.update(proposal_id=forged,draft_id=forged,proposal_hash=forged_hash)
        for table,values in [('aip_action_proposal',row),('aip_action_draft',draft)]:
            admin.execute(sql.SQL('INSERT INTO public.{} ({}) VALUES ({})').format(sql.Identifier(table),sql.SQL(',').join(map(sql.Identifier,values)),sql.SQL(',').join(sql.Placeholder() for _ in values)),[Jsonb(v) if isinstance(v,(dict,list)) else v for v in values.values()])
    principal=Principal(subject=checker,org_id=SCOPE.org_id,project_id=SCOPE.project_id,token_kind='oidc')
    decision=DecideActionProposalRequest(expectedProposalVersion=proposal.proposal.version,
        expectedProposalHash=proposal.proposal.proposal_hash,decision='approved',reason='test-only exact source rights review')
    key='b88-approval-'+uuid4().hex
    from concurrent.futures import ThreadPoolExecutor
    from queue import Queue
    from tests.aip.test_aip_license_source_authority_pg import raw_revoke,wait_blocked
    pool=ThreadPoolExecutor(max_workers=4)
    futures=[]
    pids=Queue()
    grant=proposal.proposal.payload['requestedGrant']
    def writer(kind):
        with isolated_owner() as writer_conn:
            writer_conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",SCOPE.key)
            pids.put(writer_conn.info.backend_pid)
            try:
                if kind in ('maker','checker'):
                    subject=maker if kind=='maker' else checker
                    writer_conn.execute('DELETE FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s',(*SCOPE.key,subject))
                elif kind=='installation':
                    writer_conn.execute('SELECT installation_pk FROM bundle_installation WHERE org_id=%s AND project_id=%s AND installation_id=%s FOR UPDATE',(*SCOPE.key,grant['installationId']))
                else:
                    raw_revoke(writer_conn,grant['source']['resourceId'],content_hash=grant['source']['contentHash'])
            finally: writer_conn.rollback()
    try:
        with isolated_owner() as admin:
            admin.execute(sql.SQL('ALTER ROLE {} LOGIN PASSWORD {}').format(sql.Identifier(ISSUER),sql.Literal(password)))
        with isolated_source_oidc(checker) as token, isolated_source_approval_connection(password) as conn:
            conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",SCOPE.key)
            assert conn.execute('SELECT session_user AS login,current_user AS role').fetchone()=={'login':ISSUER,'role':ISSUER}
            from aos_api.aip_license_source_proposal_contracts import SourceLicenseApprovalCommand
            from aos_api.aip_license_source_approval import authenticate_source_license_command
            command=SourceLicenseApprovalCommand(schemaVersion=1,bearerToken=token,orgId=SCOPE.org_id,projectId=SCOPE.project_id,proposalId=proposal.proposal.id,idempotencyKey=key,decision=decision)
            principal=authenticate_source_license_command(command)
            args=dict(conn=conn,principal=principal,proposal_id=proposal.proposal.id,idempotency_key=key,decision=decision,loader=loader,release_policy=release_policy)
            for actor,reason in [(maker,'INDEPENDENT_OWNER_CHECKER_REQUIRED'),(admin_actor,'CURRENT_CHECKER_OWNER_REQUIRED'),('missing-checker','CURRENT_CHECKER_OWNER_REQUIRED')]:
                with pytest.raises(SourceLicenseProposalBlocked,match=reason):
                    with conn.transaction():
                        approve_source_license_in_transaction(**{**args,'principal':Principal(subject=actor,org_id=SCOPE.org_id,project_id=SCOPE.project_id,token_kind='oidc')})
            for changed in [decision.model_copy(update={'expected_proposal_version':99}),decision.model_copy(update={'expected_proposal_hash':'0'*64})]:
                with pytest.raises(AipActionConflict):
                    with conn.transaction(): approve_source_license_in_transaction(**{**args,'decision':changed})
            with pytest.raises(SourceLicenseProposalBlocked,match='ORIGINAL_DRAFT_DRIFT'):
                with conn.transaction():
                    approve_source_license_in_transaction(**{**args,'proposal_id':forged,'idempotency_key':forged,'decision':decision.model_copy(update={'expected_proposal_hash':forged_hash})})
            with pytest.raises(SourceLicenseProposalBlocked,match='INDEPENDENT_APPROVAL_IDENTITY_REQUIRED'):
                with conn.transaction():
                    conn.execute('SET LOCAL search_path=pg_temp,public,pg_catalog')
                    approve_source_license_in_transaction(**args)
            approved=approve_source_license_in_transaction(**args)
            assert approved.proposal.status.value=='approved' and approved.proposal.version==proposal.proposal.version+1
            assert len(approved.approvals)==1
            event=approved.approvals[0]
            assert event.actor.actor_id==checker and event.slot_id=='checker.1'
            assert event.action_binding_hash==proposal.proposal.action_binding_hash
            assert event.approval_policy_hash==proposal.proposal.approval_policy_hash
            assert event.eligibility_snapshot_hash==canonical_hash({'tenant':{'orgId':SCOPE.org_id,'projectId':SCOPE.project_id},'actorId':checker,'roles':['owner'],'slotId':'checker.1','approvalPolicyHash':event.approval_policy_hash})
            replay=approve_source_license_in_transaction(**args)
            assert replay.proposal.version==approved.proposal.version
            assert replay.approvals==approved.approvals
            with pytest.raises(SourceLicenseProposalBlocked,match='APPROVAL_REPLAY_ACTOR_OR_BINDING_DRIFT'):
                with conn.transaction():
                    approve_source_license_in_transaction(**{**args,'principal':Principal(subject=other_owner,org_id=SCOPE.org_id,project_id=SCOPE.project_id,token_kind='oidc')})
            for table,target in [('aip_action_proposal','drafted'),('aip_action_draft','awaiting_approval')]:
                with pytest.raises(psycopg.errors.InsufficientPrivilege,match='SOURCE_APPROVAL_TRANSITION_INVALID'):
                    with conn.transaction():
                        version_clause=',version=version+1' if table=='aip_action_proposal' else ''
                        conn.execute(f"UPDATE {table} SET status=%s{version_clause} WHERE org_id=%s AND project_id=%s AND proposal_id=%s",(target,*SCOPE.key,proposal.proposal.id))
            # The narrow issuer's SELECT policies hide every ordinary Action.
            assert conn.execute("SELECT count(*) AS n FROM aip_action_proposal WHERE action_type_id<>'aip_issue_source_license'").fetchone()['n']==0
            # Test actual installation row: row-lock privilege cannot mutate it.
            with pytest.raises(psycopg.errors.InsufficientPrivilege,match='SOURCE_APPROVAL_READ_LOCK_ONLY'):
                with conn.transaction():
                    conn.execute('UPDATE bundle_installation SET installation_id=installation_id WHERE org_id=%s AND project_id=%s AND installation_id=%s',(*SCOPE.key,proposal.proposal.payload['requestedGrant']['installationId']))
            futures=[pool.submit(writer,kind) for kind in ('maker','checker','installation','revoke')]
            writer_pids=[pids.get(timeout=6) for _ in futures]
            with isolated_owner() as observer:
                wait_blocked(observer,writer_pids,conn.info.backend_pid,futures)
        for future in futures: future.result(timeout=8)
        with isolated_source_approval_connection(password) as canary:
            canary.execute("SELECT set_config('aos.org_id','dev-org',true)")
            assert canary.execute('SELECT count(*) AS n FROM aip_action_proposal').fetchone()['n']==0
            assert canary.execute('SELECT count(*) AS n FROM aip_action_approval_event').fetchone()['n']==0
        for subject,reason in [(maker,'CURRENT_OWNER_REQUIRED'),(checker,'CURRENT_CHECKER_OWNER_REQUIRED')]:
            with isolated_owner() as admin:
                admin.execute('DELETE FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s',(*SCOPE.key,subject))
            try:
                with isolated_source_approval_connection(password) as lost:
                    with pytest.raises(SourceLicenseProposalBlocked,match=reason):
                        approve_source_license_in_transaction(**{**args,'conn':lost})
            finally:
                with isolated_owner() as admin:
                    admin.execute("INSERT INTO meta_membership(org_id,project_id,subject,role) VALUES(%s,%s,%s,'owner')",(*SCOPE.key,subject))
        with isolated_source_oidc(checker) as token, isolated_source_database_config(password) as config:
            from aos_api.aip_license_source_approval import execute_source_license_approval
            command=SourceLicenseApprovalCommand(schemaVersion=1,bearerToken=token,orgId=SCOPE.org_id,projectId=SCOPE.project_id,proposalId=proposal.proposal.id,idempotencyKey=key,decision=decision)
            reconciled=execute_source_license_approval(command,database=config,loader=loader,release_policy=release_policy)
            assert reconciled.approvals==approved.approvals and reconciled.proposal.version==approved.proposal.version
        assert_signed_source_withdrawal_and_expiry(proposal,maker,password,principal,loader,release_policy)
        import os
        issuance_expected=0
        if os.environ.get('AOS_B89_SOURCE_ISSUER_TEST')=='1':
            from tests.aip.test_source_license_issuer_pg import assert_signed_original_source_issuance
            assert_signed_original_source_issuance(approved,maker,loader,release_policy,approval_password=password)
            issuance_expected=1
        with isolated_owner() as observer:
            assert observer.execute('SELECT count(*) AS n FROM aip_action_approval_event WHERE org_id=%s AND project_id=%s AND proposal_id=%s',(*SCOPE.key,proposal.proposal.id)).fetchone()['n']==1
            assert observer.execute('SELECT count(*) AS n FROM aip_license_source_issuance').fetchone()['n']==issuance_expected
    finally:
        try:
            for future in futures: future.result(timeout=8)
        finally:
            pool.shutdown(wait=True)
            with isolated_owner() as admin:
                admin.execute(sql.SQL('ALTER ROLE {} NOLOGIN PASSWORD NULL').format(sql.Identifier(ISSUER)))


def test_source_adapter_verifies_signed_oidc_and_rejects_wrong_signature_scope_and_expiry(monkeypatch):
    import time
    import jwt
    from cryptography.hazmat.primitives.asymmetric import rsa
    from jwt.algorithms import RSAAlgorithm
    from aos_api.aip_license_source_proposal_contracts import SourceLicenseApprovalCommand
    from aos_api.aip_license_source_approval import authenticate_source_license_command,SourceLicenseAuthBlocked
    from aos_api.aip_action_models import DecideActionProposalRequest
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    jwk=__import__('json').loads(RSAAlgorithm.to_jwk(key.public_key()))
    jwk.update(kid='b88-isolated-jwk',use='sig',alg='RS256')
    # Only JWKS transport is substituted. Actual PyJWT signature/claims checks run.
    monkeypatch.setattr(jwt.PyJWKClient,'fetch_data',lambda self:{'keys':[jwk]})
    monkeypatch.setenv('AOS_AUTH_ALLOW_DEV','0')
    monkeypatch.setenv('AOS_AUTH_EXTERNAL_ONLY','1')
    monkeypatch.setenv('AOS_OIDC_ISSUER','https://b88-id.example.test/realm')
    monkeypatch.setenv('AOS_OIDC_JWKS_URL','https://b88-id.example.test/jwks')
    monkeypatch.setenv('AOS_OIDC_AUDIENCE','b88-source-approval')
    monkeypatch.delenv('AOS_OIDC_ISSUERS',raising=False)
    monkeypatch.delenv('AOS_OIDC_JWKS_URLS',raising=False)
    claims=dict(sub='verified-checker',iss='https://b88-id.example.test/realm',aud='b88-source-approval',exp=int(time.time())+120,org_id='org-org',project_id='dev-project',roles=['admin'])
    def command(changes=None,signer=None):
        token=jwt.encode({**claims,**(changes or {})},signer or key,algorithm='RS256',headers={'kid':'b88-isolated-jwk'})
        return SourceLicenseApprovalCommand(schemaVersion=1,bearerToken=token,orgId='org-org',projectId='dev-project',proposalId='test-only-proposal',idempotencyKey='test-only-approval',decision=DecideActionProposalRequest(expectedProposalVersion=1,expectedProposalHash='a'*64,decision='approved'))
    assert authenticate_source_license_command(command()).subject=='verified-checker'
    wrong=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    for changes,signer in [({'org_id':'dev-org'},None),({'exp':int(time.time())-1},None),({'aud':'other'},None),({},wrong),({'sub':'unknown'},None)]:
        value=command(changes,signer)
        with pytest.raises(SourceLicenseAuthBlocked) as error:
            authenticate_source_license_command(value)
        assert value.bearer_token.get_secret_value() not in str(error.value)


@pytest.mark.parametrize('mode',[0o644,0o666])
def test_source_connection_rejects_public_credential_file(tmp_path,mode):
    from aos_api.aip_license_source_approval import SourceApprovalDatabaseConfig,SourceLicenseDatabaseBlocked
    tmp_path.chmod(0o700)
    secret=tmp_path/'source.pgpass'
    secret.write_text('test-only-no-credential')
    secret.chmod(mode)
    with pytest.raises(SourceLicenseDatabaseBlocked,match='PRIVATE_CREDENTIAL'):
        SourceApprovalDatabaseConfig('127.0.0.1',25432,'aos_test_isolated',secret)


from contextlib import contextmanager


@contextmanager
def isolated_source_database_config(password):
    from tempfile import TemporaryDirectory
    from pathlib import Path
    from psycopg.conninfo import conninfo_to_dict
    from aos_api.db import get_dsn
    from aos_api.aip_license_source_approval import SourceApprovalDatabaseConfig
    parameters=conninfo_to_dict(get_dsn())
    assert parameters['dbname'].startswith('aos_test_')
    with TemporaryDirectory(prefix='b88-source-approval-') as directory:
        folder=Path(directory);folder.chmod(0o700)
        secret=folder/'source.pgpass'
        host='127.0.0.1';port=int(parameters['port'])
        secret.write_text(f"{host}:{port}:{parameters['dbname']}:{ISSUER}:{password}\n")
        secret.chmod(0o600)
        yield SourceApprovalDatabaseConfig(host,port,parameters['dbname'],secret)


@contextmanager
def isolated_source_approval_connection(password):
    from aos_api.aip_license_source_approval import connect_source_approval
    with isolated_source_database_config(password) as config:
        with connect_source_approval(config,SCOPE) as conn:
            yield conn


@contextmanager
def isolated_source_oidc(subject):
    """Isolated real RSA signature; JWKS transport fixture, no production IdP."""
    import time,json,jwt
    from cryptography.hazmat.primitives.asymmetric import rsa
    from jwt.algorithms import RSAAlgorithm
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    jwk=json.loads(RSAAlgorithm.to_jwk(key.public_key()))
    jwk.update(kid='b88-jwk',use='sig',alg='RS256')
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(jwt.PyJWKClient,'fetch_data',lambda self:{'keys':[jwk]})
        for name,value in [('AOS_AUTH_ALLOW_DEV','0'),('AOS_AUTH_EXTERNAL_ONLY','1'),('AOS_OIDC_ISSUER','https://b88-id.example.test/realm'),('AOS_OIDC_JWKS_URL','https://b88-id.example.test/jwks'),('AOS_OIDC_AUDIENCE','b88-source-approval')]:
            patch.setenv(name,value)
        patch.delenv('AOS_OIDC_ISSUERS',raising=False)
        patch.delenv('AOS_OIDC_JWKS_URLS',raising=False)
        yield jwt.encode(dict(sub=subject,iss='https://b88-id.example.test/realm',aud='b88-source-approval',exp=int(time.time())+120,org_id=SCOPE.org_id,project_id=SCOPE.project_id,roles=['admin']),key,algorithm='RS256',headers={'kid':'b88-jwk'})



def assert_signed_source_withdrawal_and_expiry(original,maker,password,checker,loader,release_policy):
    import time
    from uuid import uuid4
    from datetime import datetime,timedelta,timezone
    from psycopg.rows import dict_row
    from aos_api.db import get_dsn
    from aos_api.tenant_scope import apply_transaction_scope
    from aos_api.aip_license_source_approval import propose_authenticated_source_license_in_transaction,approve_source_license_in_transaction
    from aos_api.aip_license_source_proposal import SourceLicenseProposalBlocked
    from aos_api.aip_license_source_proposal_contracts import SourceLicenseMakerCommand,SourceLicenseProposalRequest
    from aos_api.aip_action_models import WithdrawActionProposalRequest,DecideActionProposalRequest
    from aos_api.aip_action_store import AipActionStore
    from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
    from aos_api.ecommerce_growth_host_ports import HostTransaction
    request=SourceLicenseProposalRequest.model_validate(original.proposal.payload['requestedGrant'])
    with isolated_source_oidc(maker) as token, psycopg.connect(get_dsn(),row_factory=dict_row) as conn:
        conn.isolation_level=psycopg.IsolationLevel.SERIALIZABLE
        apply_transaction_scope(conn,SCOPE)
        command=SourceLicenseMakerCommand(schemaVersion=1,bearerToken=token,orgId=SCOPE.org_id,projectId=SCOPE.project_id,idempotencyKey='b88-withdraw-'+uuid4().hex,request=request)
        withdrawn=propose_authenticated_source_license_in_transaction(command,conn=conn,loader=loader,release_policy=release_policy)
        AipActionStore(TransactionBoundConnectFactory(HostTransaction(conn),SCOPE)).withdraw(SCOPE,maker,withdrawn.proposal.id,'b88-withdraw-event-'+uuid4().hex,WithdrawActionProposalRequest(expectedProposalVersion=withdrawn.proposal.version,expectedProposalHash=withdrawn.proposal.proposal_hash,reason='test-only withdrawal'))
        expiring=request.model_copy(update={'proposal_expires_at':datetime.now(timezone.utc)+timedelta(seconds=2)})
        expired_command=command.model_copy(update={'idempotency_key':'b88-expired-'+uuid4().hex,'request':expiring})
        expired=propose_authenticated_source_license_in_transaction(expired_command,conn=conn,loader=loader,release_policy=release_policy)
    with isolated_source_approval_connection(password) as conn:
        deadline=time.monotonic()+4
        while conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']<expired.proposal.expires_at:
            assert time.monotonic()<deadline
            time.sleep(0.02)
        for bundle,reason in [(withdrawn,'PROPOSAL_WITHDRAWN'),(expired,'REQUEST_WINDOW_EXPIRED|PROPOSAL_EXPIRED')]:
            with pytest.raises(SourceLicenseProposalBlocked,match=reason):
                with conn.transaction():
                    approve_source_license_in_transaction(conn=conn,principal=checker,proposal_id=bundle.proposal.id,idempotency_key='b88-denied-'+uuid4().hex,decision=DecideActionProposalRequest(expectedProposalVersion=bundle.proposal.version,expectedProposalHash=bundle.proposal.proposal_hash,decision='approved'),loader=loader,release_policy=release_policy)
            assert conn.execute('SELECT count(*) AS n FROM aip_action_approval_event WHERE org_id=%s AND project_id=%s AND proposal_id=%s',(*SCOPE.key,bundle.proposal.id)).fetchone()['n']==0


def test_source_adapter_rejects_development_config_before_any_database_access(monkeypatch):
    from aos_api import aip_license_source_approval as module
    from aos_api.aip_license_source_proposal_contracts import SourceLicenseApprovalCommand
    command=SourceLicenseApprovalCommand(schemaVersion=1,bearerToken='header.payload.signature',orgId='org-org',projectId='dev-project',proposalId='test-only',idempotencyKey='test-only',decision={'expectedProposalVersion':1,'expectedProposalHash':'a'*64,'decision':'approved'})
    monkeypatch.setenv('AOS_AUTH_ALLOW_DEV','1')
    monkeypatch.setattr(module,'connect_source_approval',lambda *args:pytest.fail('auth must precede DB access'))
    with pytest.raises(module.SourceLicenseAuthBlocked):
        module.execute_source_license_approval(command,database=None,loader=None,release_policy=None)


@pytest.mark.parametrize('table,protected',[('meta_object_type','SourceLicenseRequest'),('meta_action_type','aip_issue_source_license')])
def test_issuer_cannot_mutate_ordinary_metadata_using_lock_column(table,protected):
    from uuid import uuid4
    from psycopg import sql
    from psycopg.types.json import Jsonb
    with isolated_owner() as conn:
        row=conn.execute(sql.SQL('SELECT * FROM public.{} WHERE id=%s').format(sql.Identifier(table)),(protected,)).fetchone()
        ordinary='b88-ordinary-metadata-'+uuid4().hex
        row['id']=ordinary
        conn.execute(sql.SQL('INSERT INTO public.{} ({}) VALUES ({})').format(sql.Identifier(table),sql.SQL(',').join(map(sql.Identifier,row)),sql.SQL(',').join(sql.Placeholder() for _ in row)),[Jsonb(v) if isinstance(v,(dict,list)) else v for v in row.values()])
        conn.execute(sql.SQL('SET SESSION AUTHORIZATION {}').format(sql.Identifier(ISSUER)))
        with pytest.raises(psycopg.errors.InsufficientPrivilege,match='SOURCE_APPROVAL_READ_LOCK_ONLY'):
            conn.execute(sql.SQL('UPDATE public.{} SET id=id WHERE id=%s').format(sql.Identifier(table)),(ordinary,))
        conn.rollback()
