"""Offline original material-record composition, NOT native or report proof.

Only the native connection-type/property guard is substituted in positive cases.
Original Action metadata/risk and membership code run on fixed synthetic rows.
No real DB/Source/approval/budget or Provider is contacted.
"""
from copy import deepcopy
from datetime import timedelta
import json
import os

import pytest

from aos_api import aip_model_route_eval_action as action
from aos_api import aip_model_route_eval_owner as owner
from aos_api.aip_action_policy import classify_action_risk
from aos_api.aip_action_store import AipActionStore,canonical_hash
from aos_api.tenant_scope import TenantScope
from test_model_route_eval_manifest import route_inputs,NOW,TENANT,dump
from test_capacity_source_publication_transaction_pg import (
    exact_public_source_caller,
    native_full_signed_reader,
    native_original_fact_reader,
    native_signed_source,
    approved_command,
    private_database,
    signed_capacity_documents,
    source_proposal,
    source_inputs,
    drafted,
    original_inputs,
)


def test_g6_route_private_proof_authority_installer_is_closed_and_route_specific():
    from aos_api.aip_model_route_eval_proof_authority import (
        install_closed_route_eval_proof_authority,
    )

    statements=[]
    install_closed_route_eval_proof_authority(statements.append)
    contract='\n'.join(statements)
    assert 'aos_model_route_eval_issuer_owner' in contract
    assert 'aos_model_route_eval_issuer_reader' in contract
    assert 'aos_model_route_eval_issuer_private' in contract
    for relation in ('issuer_root','executor_certificate','issuer_epoch',
                     'certificate_epoch','authority_withdrawal'):
        assert relation in contract
    assert 'ENABLE ROW LEVEL SECURITY' in contract
    assert 'FORCE ROW LEVEL SECURITY' in contract
    assert 'pg_advisory_xact_lock_shared' in contract
    assert 'pg_advisory_xact_lock' in contract
    assert 'read_current_issuer_root' in contract
    assert 'read_current_executor_certificate' in contract
    assert 'SECURITY DEFINER' in contract
    assert 'GRANT EXECUTE ON FUNCTION' in contract
    assert 'TO aos_runtime' in contract
    assert "CHECK(org_id='org-org')" in contract
    assert "CHECK(project_id='dev-project')" in contract
    assert 'CREATE ROLE aos_model_route_eval ' not in contract
    assert 'aos_model_eval_issuer_private' not in contract
    assert 'GRANT SELECT ON aos_model_route_eval_issuer_private.issuer_root TO aos_runtime' not in contract
    assert 'GRANT SELECT ON aos_model_route_eval_issuer_private.executor_certificate TO aos_runtime' not in contract
    assert 'GRANT aos_model_route_eval_issuer_reader TO aos_runtime' not in contract
    assert 'GRANT aos_model_route_eval_issuer_reader TO aos_model_route_eval' not in contract


def test_g6_route_private_proof_authority_exports_nonexecuting_verified_result():
    from aos_api.aip_model_route_eval_proof_authority import (
        VerifiedRouteEvalProofAuthority,
    )

    value=VerifiedRouteEvalProofAuthority(
        execution_id='route-execution',manifest_hash='a'*64,
        issuer_epochs=(('issuer','key',1,'b'*64),),
        certificate_epochs=(('c'*64,1),),checked_at=NOW,
        caller_xid='42',caller_pid=84,
    )
    assert value.execution_allowed is False


class RouteProofAuthorityFixture:
    def __init__(self):
        import base64
        import hashlib
        from datetime import timedelta
        from test_model_route_eval_finalization_proof import finalization_fixture

        self.proof,self.manifest,*_=finalization_fixture()
        self.now=self.proof.finalized_at+timedelta(seconds=1)
        self.calls=[];self.fault=None;self.boundaries=0
        self.function_profiles=[dict(proname='read_current_executor_certificate',
            owner='aos_model_route_eval_issuer_reader',prosecdef=True,
            proconfig=['search_path=pg_catalog'],body='',runtime_execute=True,
            public_revoked=True,exact_acl=True),dict(proname='read_current_issuer_root',
            owner='aos_model_route_eval_issuer_reader',prosecdef=True,
            proconfig=['search_path=pg_catalog'],body='',runtime_execute=True,
            public_revoked=True,exact_acl=True)]
        self.function_profiles[0]['body']='executor-body'
        self.function_profiles[1]['body']='issuer-body'
        self.context=dict(database='aos_test_route_authority_ti4_test',database_oid=321,
            login='aos_model_route_eval',role='aos_runtime',
            org_id='org-org',project_id='dev-project',isolation='serializable',readonly='off',
            xid='42',pid=84,now=self.now)
        self.roots={};self.certificates={}
        for item in self.proof.calls:
            root=item.issuer_input;cert=item.signed_certificate.certificate
            root_body=json.dumps(root.model_dump(mode='json',by_alias=True),sort_keys=True,
                separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
            self.roots[(root.issuer_id,root.issuer_key_id)]=dict(
                input_hash=item.issuer_input_hash,
                public_key_hash=hashlib.sha256(base64.b64decode(root.public_key_base64)).hexdigest(),
                body=root_body,valid_from=root.valid_from,valid_until=root.valid_until,
                epoch=1,active_hash=item.issuer_input_hash)
            signed=item.signed_certificate
            signed_body=json.dumps(signed.model_dump(mode='json',by_alias=True),sort_keys=True,
                separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
            self.certificates[item.certificate_hash]=dict(execution_id=cert.execution_id,
                case_id=cert.case_id,purpose=cert.purpose,identity_id=cert.identity_id,
                identity_key_hash=cert.identity_key_hash,issuer_id=cert.issuer_id,
                issuer_key_id=cert.issuer_key_id,manifest_hash=cert.manifest_hash,
                certificate_hash=item.certificate_hash,body=signed_body,
                valid_from=cert.valid_from,valid_until=cert.valid_until,epoch=1,
                active_hash=item.certificate_hash)

    def execute(self,statement,params=()):
        sql=' '.join(statement.split());self.calls.append((sql,params))
        if 'session_user AS login' in sql:
            self.boundaries+=1;row=deepcopy(self.context)
            if self.boundaries>1 and self.fault=='xid_after':row['xid']='43'
            if self.boundaries>1 and self.fault=='clock_backwards':row['now']=self.now-timedelta(seconds=1)
            if self.fault=='role':row['role']='aos_model_route_eval_issuer_reader'
            return Rows(row)
        if 'p.prosrc AS body' in sql:
            rows=deepcopy(self.function_profiles)
            if self.fault=='contract':rows[0]['owner']='aos_runtime'
            return Rows(rows)
        if 'AS membership_edges' in sql:
            return Rows(dict(rolcanlogin=False,rolinherit=False,rolsuper=False,
                rolbypassrls=False,rolcreatedb=False,rolcreaterole=False,rolreplication=False,
                membership_edges=0,owned_relations=0,owned_schemas=0,owned_databases=0))
        if 'AS runtime_table_selects' in sql:return Rows({'runtime_table_selects':0})
        if 'pg_advisory_xact_lock_shared' in sql:return Rows({'lock':None})
        if 'read_current_issuer_root' in sql:
            row=deepcopy(self.roots.get((params[-2],params[-1])))
            if self.fault=='root_missing':row=None
            elif self.fault=='root_inactive':row['active_hash']=None
            elif self.fault=='root_bytes':row['body']+=b'\n'
            return Rows(row)
        if 'read_current_executor_certificate' in sql:
            row=deepcopy(self.certificates.get(params[-1]))
            if self.fault=='certificate_missing':row=None
            elif self.fault=='certificate_inactive':row['active_hash']=None
            elif self.fault=='certificate_bytes':row['body']+=b'\n'
            return Rows(row)
        raise AssertionError(sql)

    def commit(self):raise AssertionError('Reader must retain caller transaction')
    rollback=commit
    close=commit


def test_g6_route_private_proof_authority_reader_revalidates_exact_current_rows(monkeypatch):
    from aos_api import aip_model_route_eval_owner as route_owner
    from aos_api import aip_model_route_eval_proof_authority as authority
    import hashlib
    monkeypatch.setattr(route_owner,'_require_native_connection',lambda conn:None)
    monkeypatch.setattr(authority,'READER_BODY_HASHES',{
        'read_current_executor_certificate':hashlib.sha256(b'executor-body').hexdigest(),
        'read_current_issuer_root':hashlib.sha256(b'issuer-body').hexdigest()})
    fixture=RouteProofAuthorityFixture()
    value=authority.read_current_route_eval_proof_authority(fixture,
        scope=TenantScope('org-org','dev-project'),proof=fixture.proof,
        manifest_bytes=fixture.manifest)
    assert value.execution_id==fixture.proof.execution_id
    assert value.manifest_hash==fixture.proof.manifest_hash
    assert value.execution_allowed is False
    assert value.caller_xid=='42' and value.caller_pid==84
    assert len(value.issuer_epochs)==len(fixture.roots)
    assert len(value.certificate_epochs)==len(fixture.certificates)
    assert fixture.boundaries==2
    assert any('read_current_issuer_root' in sql for sql,_ in fixture.calls)
    assert any('read_current_executor_certificate' in sql for sql,_ in fixture.calls)
    assert not any('FROM aos_model_route_eval_issuer_private.issuer_root' in sql
                   or 'FROM aos_model_route_eval_issuer_private.executor_certificate' in sql
                   for sql,_ in fixture.calls)
    assert all('INSERT ' not in sql and 'UPDATE ' not in sql and 'DELETE ' not in sql
               for sql,_ in fixture.calls)


@pytest.mark.parametrize('fault',['role','contract','root_missing','root_inactive','root_bytes',
    'certificate_missing','certificate_inactive','certificate_bytes','xid_after','clock_backwards'])
def test_g6_route_private_proof_authority_reader_fails_closed_on_drift(monkeypatch,fault):
    from aos_api import aip_model_route_eval_owner as route_owner
    from aos_api import aip_model_route_eval_proof_authority as authority
    import hashlib
    monkeypatch.setattr(route_owner,'_require_native_connection',lambda conn:None)
    monkeypatch.setattr(authority,'READER_BODY_HASHES',{
        'read_current_executor_certificate':hashlib.sha256(b'executor-body').hexdigest(),
        'read_current_issuer_root':hashlib.sha256(b'issuer-body').hexdigest()})
    fixture=RouteProofAuthorityFixture();fixture.fault=fault
    with pytest.raises(authority.RouteEvalProofAuthorityRejected,match='current Route proof authority'):
        authority.read_current_route_eval_proof_authority(fixture,
            scope=TenantScope('org-org','dev-project'),proof=fixture.proof,
            manifest_bytes=fixture.manifest)


def test_g6_route_private_proof_authority_native_scram_rls_and_withdrawal_lock():
    """Run only in a new disposable PostgreSQL container/database."""
    import base64
    import hashlib
    import os
    import secrets
    from datetime import UTC,datetime

    import psycopg
    from psycopg import sql
    from psycopg.conninfo import conninfo_to_dict,make_conninfo
    from psycopg.rows import dict_row

    from aos_api import aip_model_route_eval_proof_authority as authority
    import test_model_route_eval_context_reader as context_reader_fixture
    import test_model_route_eval_finalization_proof as finalization_fixture_module
    import test_model_route_eval_manifest as manifest_fixture
    import test_model_route_eval_signatures as signatures_fixture
    import test_model_route_eval_subject_binding as subject_fixture

    if os.getenv('AOS_ROUTE_EVAL_PRIVATE_AUTHORITY_NATIVE')!='1':
        pytest.skip('explicit disposable Route proof authority native window required')
    admin_dsn=os.getenv('AOS_DATABASE_URL')
    try:
        parts=conninfo_to_dict(admin_dsn or '')
        port=int(parts.get('port','0'));database=parts.get('dbname','')
        if (parts.get('host') not in {'127.0.0.1','localhost','::1'} or port<1024
            or port in {5432,5433} or not database.startswith('aos_test_')
            or not database.endswith('_ti4_test') or not parts.get('user')
            or not parts.get('password')):raise ValueError
    except (TypeError,ValueError):
        pytest.fail('native Route proof authority test requires loopback random test database')

    fresh_now=datetime.now(UTC)-timedelta(minutes=1)
    with pytest.MonkeyPatch.context() as clock:
        for module in (subject_fixture,context_reader_fixture,manifest_fixture,
                       signatures_fixture,finalization_fixture_module):
            clock.setattr(module,'NOW',fresh_now)
        proof,manifest,*_=finalization_fixture_module.finalization_fixture()
    login='aos_model_route_eval';password=secrets.token_urlsafe(32)
    caller_dsn=make_conninfo(**{**parts,'user':login,'password':password,
        'require_auth':'scram-sha-256'})

    def canonical(value):
        return json.dumps(value.model_dump(mode='json',by_alias=True),sort_keys=True,
            separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()

    def set_owner(conn):
        conn.execute('SET LOCAL ROLE '+authority.ISSUER_OWNER)
        conn.execute("SELECT set_config('aos.org_id','org-org',true),"
            "set_config('aos.project_id','dev-project',true)")

    def set_reader(conn):
        conn.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ WRITE')
        conn.execute('SET LOCAL ROLE aos_runtime')
        conn.execute("SELECT set_config('aos.org_id','org-org',true),"
            "set_config('aos.project_id','dev-project',true)")

    try:
        with psycopg.connect(admin_dsn,autocommit=True,row_factory=dict_row) as admin:
            authority.install_closed_route_eval_proof_authority(admin.execute)
            admin.execute("SET password_encryption='scram-sha-256'")
            admin.execute(sql.SQL('CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS '
                'NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD {}').format(
                    sql.Identifier(login),sql.Literal(password)))
            admin.execute(sql.SQL('GRANT aos_runtime TO {}').format(sql.Identifier(login)))
            reader_profile=admin.execute("""SELECT rolcanlogin,rolinherit,rolsuper,rolbypassrls,
                rolcreatedb,rolcreaterole,rolreplication FROM pg_catalog.pg_roles
                WHERE rolname=%s""",(authority.ISSUER_READER,)).fetchone()
            assert reader_profile==dict(rolcanlogin=False,rolinherit=False,rolsuper=False,
                rolbypassrls=False,rolcreatedb=False,rolcreaterole=False,rolreplication=False)
            assert admin.execute("""SELECT count(*) AS count FROM pg_catalog.pg_auth_members m
                JOIN pg_catalog.pg_roles member_role ON member_role.oid=m.member
                JOIN pg_catalog.pg_roles granted_role ON granted_role.oid=m.roleid
                WHERE member_role.rolname IN (%s,'aos_runtime')
                  AND granted_role.rolname=%s""",(login,authority.ISSUER_READER)).fetchone()['count']==0
            functions=admin.execute("""SELECT p.proname,owner_role.rolname AS owner,p.prosecdef,
                p.proconfig FROM pg_catalog.pg_proc p
                JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
                JOIN pg_catalog.pg_roles owner_role ON owner_role.oid=p.proowner
                WHERE n.nspname=%s AND p.proname IN
                  ('read_current_issuer_root','read_current_executor_certificate')
                ORDER BY p.proname""",(authority.ISSUER_SCHEMA,)).fetchall()
            assert len(functions)==2
            assert all(row['owner']==authority.ISSUER_READER and row['prosecdef'] is True
                and row['proconfig']==['search_path=pg_catalog'] for row in functions)
            for relation in ('issuer_root','executor_certificate'):
                assert admin.execute("SELECT pg_catalog.has_table_privilege('aos_runtime',%s,'SELECT') AS allowed",
                    (f'{authority.ISSUER_SCHEMA}.{relation}',)).fetchone()['allowed'] is False

        with psycopg.connect(admin_dsn,row_factory=dict_row) as writer:
            set_owner(writer)
            roots={}
            for item in proof.calls:
                root=item.issuer_input;cert=item.signed_certificate.certificate
                roots.setdefault((root.issuer_id,root.issuer_key_id),(root,item.issuer_input_hash))
            for (issuer_id,key_id),(root,digest) in roots.items():
                writer.execute(f'''INSERT INTO {authority.ISSUER_SCHEMA}.issuer_root(
                    org_id,project_id,issuer_id,issuer_key_id,input_hash,public_key_hash,
                    body,valid_from,valid_until) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                    ('org-org','dev-project',issuer_id,key_id,digest,
                     hashlib.sha256(base64.b64decode(root.public_key_base64)).hexdigest(),
                     canonical(root),root.valid_from,root.valid_until))
            for item in proof.calls:
                cert=item.signed_certificate.certificate
                writer.execute(f'''INSERT INTO {authority.ISSUER_SCHEMA}.executor_certificate(
                    org_id,project_id,execution_id,case_id,purpose,identity_id,identity_key_hash,
                    issuer_id,issuer_key_id,manifest_hash,certificate_hash,body,valid_from,valid_until)
                    VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                    ('org-org','dev-project',cert.execution_id,cert.case_id,cert.purpose,
                     cert.identity_id,cert.identity_key_hash,cert.issuer_id,cert.issuer_key_id,
                     cert.manifest_hash,item.certificate_hash,canonical(item.signed_certificate),
                     cert.valid_from,cert.valid_until))
            writer.commit()

        first_hash=proof.calls[0].certificate_hash
        with psycopg.connect(caller_dsn,row_factory=dict_row) as caller:
            set_reader(caller)
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with caller.transaction():
                    caller.execute('SET LOCAL ROLE '+authority.ISSUER_READER)
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with caller.transaction():
                    caller.execute(f'SELECT 1 FROM {authority.ISSUER_SCHEMA}.issuer_root LIMIT 1')
            verified=authority.read_current_route_eval_proof_authority(caller,
                scope=TenantScope('org-org','dev-project'),proof=proof,manifest_bytes=manifest)
            assert verified.execution_id==proof.execution_id and not verified.execution_allowed
            assert caller.pgconn.used_password is True
            assert caller.info.get_parameters().get('require_auth')=='scram-sha-256'
            with psycopg.connect(admin_dsn,row_factory=dict_row) as withdrawer:
                withdrawer.execute("SET lock_timeout='150ms'");set_owner(withdrawer)
                with pytest.raises(psycopg.errors.LockNotAvailable):
                    withdrawer.execute(f'''INSERT INTO {authority.ISSUER_SCHEMA}.authority_withdrawal(
                        org_id,project_id,event_id,target_kind,certificate_hash,content_hash,body)
                        VALUES(%s,%s,%s,'executor_certificate',%s,%s,%s)''',
                        ('org-org','dev-project','blocked-withdraw',first_hash,'d'*64,b'{}'))
            caller.rollback()

        with psycopg.connect(admin_dsn,row_factory=dict_row) as withdrawer:
            set_owner(withdrawer)
            withdrawer.execute(f'''INSERT INTO {authority.ISSUER_SCHEMA}.authority_withdrawal(
                org_id,project_id,event_id,target_kind,certificate_hash,content_hash,body)
                VALUES(%s,%s,%s,'executor_certificate',%s,%s,%s)''',
                ('org-org','dev-project','committed-withdraw',first_hash,'e'*64,b'{}'))
            withdrawer.commit()
        with psycopg.connect(caller_dsn,row_factory=dict_row) as caller:
            set_reader(caller)
            with pytest.raises(authority.RouteEvalProofAuthorityRejected):
                authority.read_current_route_eval_proof_authority(caller,
                    scope=TenantScope('org-org','dev-project'),proof=proof,manifest_bytes=manifest)
    finally:
        with psycopg.connect(admin_dsn,autocommit=True) as admin:
            admin.execute('SELECT pg_terminate_backend(pid) FROM pg_stat_activity '
                'WHERE usename=%s AND pid<>pg_backend_pid()',(login,))
            admin.execute(sql.SQL('DROP SCHEMA IF EXISTS {} CASCADE').format(
                sql.Identifier(authority.ISSUER_SCHEMA)))
            admin.execute(sql.SQL('DROP ROLE IF EXISTS {}').format(sql.Identifier(login)))
            admin.execute(sql.SQL('DROP ROLE IF EXISTS {}').format(sql.Identifier(authority.ISSUER_READER)))
            admin.execute(sql.SQL('DROP ROLE IF EXISTS {}').format(sql.Identifier(authority.ISSUER_OWNER)))


class Rows:
    def __init__(self,value):self.value=value
    def fetchone(self):return deepcopy(self.value)
    def fetchall(self):return deepcopy(self.value)


class MaterialFixture:
    def __init__(self,revision=1,version=1):
        raw,self.app,_=route_inputs();self.raw=raw;self.scope=TenantScope('org-org','dev-project')
        self.request=action.build_route_eval_material_draft(raw,application=self.app,checked_at=NOW)
        self.obj=dict(id='RouteEvalApplication',name='路由评测申请',
            description='仅存材料与独立调用申请，不授执行权限',published=True,properties=[],required_markings=[])
        self.meta=dict(id='aip_prepare_route_eval_application',name='准备路由评测材料',object_type='RouteEvalApplication',
            parameters=[],required_markings=[],submission_criteria=[])
        snapshot=dict(id=self.meta['id'],name=self.meta['name'],objectType=self.meta['object_type'],
            parameters=[],requiredMarkings=[],submissionCriteria=[])
        snapshot['revisionHash']=canonical_hash(snapshot)
        risk=classify_action_risk(self.request.action_type_id,snapshot,self.request.payload,None)
        self.members=[{'role':'owner'}];self.calls=[];self.after=None
        self.ctx=dict(database='aos_test_material',database_oid=123,login='isolated_material_reader',role='aos_runtime',
            org_id='org-org',project_id='dev-project',isolation='serializable',readonly='off',xid='234',pid=99,now=NOW,
            original_relations=[True]*5,append_only_revision=[True]*4)
        self.head=dict(org_id='org-org',project_id='dev-project',draft_id='material',current_revision=revision,
            version=version,lifecycle='editable',submitted_proposal_id=None,created_by='synthetic-maker',
            created_at=NOW-timedelta(seconds=1),updated_at=NOW)
        self.row=dict(org_id='org-org',project_id='dev-project',draft_id='material',revision=revision,lifecycle='editable',
            request_payload=dump(self.request),action_type_snapshot=snapshot,risk_snapshot=AipActionStore._risk_snapshot(risk),
            approval_policy_hash=canonical_hash({'floor':risk.floor.value,'reasons':list(risk.reasons),**risk.approval_policy}),
            created_by='synthetic-maker',created_at=NOW)
        self.ref=dict(tenant=deepcopy(TENANT),resourceType='ActionDraftRevision',resourceId='material',
            revision=revision,headVersion=version,contentHash='a'*64)
        self.seal()

    def seal(self):
        self.row['content_hash']=canonical_hash(dict(request=self.row['request_payload'],actionType=self.row['action_type_snapshot'],
            risk=self.row['risk_snapshot'],lifecycle=self.row['lifecycle']))
        self.ref['contentHash']=self.row['content_hash']

    def execute(self,sql,params=()):
        assert sql.lstrip().startswith('SELECT '),'material reader may only SELECT'
        assert 'pg_control_system' not in sql,'no extra privileged control-file reads'
        self.calls.append((sql,params))
        if 'session_user AS login' in sql:return Rows(self.ctx if len(self.calls)==1 or self.after is None else self.after)
        if 'FROM meta_object_type' in sql or 'FROM public.meta_object_type' in sql:return Rows(self.obj)
        if 'FROM meta_action_type' in sql or 'FROM public.meta_action_type' in sql:return Rows(self.meta)
        if 'FROM meta_membership' in sql:return Rows(self.members)
        if 'FROM aip_action_draft_head' in sql or 'FROM public.aip_action_draft_head' in sql:return Rows(self.head)
        if 'FROM aip_action_draft_revision' in sql or 'FROM public.aip_action_draft_revision' in sql:return Rows(self.row)
        raise AssertionError('unexpected SQL')

    def commit(self):raise AssertionError('caller transaction must be retained')
    rollback=commit
    close=commit


def read(fixture):
    return action.read_route_eval_material_draft(fixture,expected_database='aos_test_material',
        scope=fixture.scope,material_ref=fixture.ref,expected_maker='synthetic-maker')


def offline(monkeypatch,**kwargs):
    fixture=MaterialFixture(**kwargs)
    monkeypatch.setattr(owner,'_require_native_connection',lambda conn:None)
    return fixture


@pytest.mark.parametrize('revision,version',[(1,1),(2,2),(2,4)])
def test_original_material_head_revision_and_complete_request_are_read_on_same_caller(monkeypatch,revision,version):
    f=offline(monkeypatch,revision=revision,version=version);result=read(f)
    assert result.startswith(b'AOS-ROUTE-EVAL-MATERIAL-READBACK-v1\n')
    body=json.loads(result.split(b'\n',1)[1])
    assert body['materialRef']==f.ref and body['application']==dump(f.app)
    assert body['context']==json.loads(f.raw.split(b'\n',1)[1])
    assert body['makerId']=='synthetic-maker' and body['callerXid']=='234'
    assert body['executionAllowed'] is False and body['approvalAllowed'] is False
    assert all(sql.lstrip().startswith('SELECT ') for sql,_ in f.calls)
    member=next(i for i,(s,_) in enumerate(f.calls) if 'FROM meta_membership' in s)
    head=next(i for i,(s,_) in enumerate(f.calls) if 'aip_action_draft_head' in s and 'FOR SHARE' in s)
    assert member<head
    assert all('FOR SHARE' in s for s,_ in f.calls if 'FROM public.aip_action_draft_head' in s)
    assert all('FOR SHARE' not in s and 'FOR UPDATE' not in s for s,_ in f.calls if 'FROM public.aip_action_draft_revision' in s)


@pytest.mark.parametrize('fault',['head_missing','row_missing','head_version','head_revision','row_revision',
    'head_maker','row_maker','head_lifecycle','row_lifecycle','submitted','hash','member_missing','member_two','member_viewer',
    'bool_head_version','string_row_revision','wrong_head_tenant','wrong_row_id'])
def test_material_current_head_and_original_maker_cannot_be_replaced_by_a_presented_ref(monkeypatch,fault):
    f=offline(monkeypatch)
    if fault=='head_missing':f.head=None
    elif fault=='row_missing':f.row=None
    elif fault=='head_version':f.head['version']=2
    elif fault=='head_revision':f.head['current_revision']=2
    elif fault=='row_revision':f.row['revision']=2
    elif fault=='head_maker':f.head['created_by']='other'
    elif fault=='row_maker':f.row['created_by']='other'
    elif fault=='head_lifecycle':f.head['lifecycle']='submitted'
    elif fault=='row_lifecycle':f.row['lifecycle']='submitted'
    elif fault=='submitted':f.head['submitted_proposal_id']='other'
    elif fault=='hash':f.ref['contentHash']='0'*64
    elif fault=='member_missing':f.members=[]
    elif fault=='member_two':f.members=[{'role':'owner'},{'role':'admin'}]
    elif fault=='member_viewer':f.members=[{'role':'viewer'}]
    elif fault=='bool_head_version':f.head['version']=True
    elif fault=='string_row_revision':f.row['revision']='1'
    elif fault=='wrong_head_tenant':f.head['org_id']='dev-org'
    else:f.row['draft_id']='other'
    with pytest.raises(action.RouteEvalMaterialRejected):read(f)


@pytest.mark.parametrize('fault',['unknown_field','task','purpose','normalization','run','hint','evidence','expiry','payload_extra',
    'policy','risk','action_hash','row_action','meta_action','meta_object_bool','bool_reference'])
def test_self_consistent_record_hash_does_not_hide_original_material_or_metadata_drift(monkeypatch,fault):
    f=offline(monkeypatch);request=f.row['request_payload']
    if fault=='unknown_field':request['trusted']=True
    elif fault=='task':request['taskId']='other-task'
    elif fault=='purpose':request['purpose']='route-eval'
    elif fault=='normalization':request['purpose']=' route-eval-material '
    elif fault=='run':request['runId']='not-an-original-TaskRun'
    elif fault=='hint':request['riskHint']='R1'
    elif fault=='evidence':request['evidenceRefs']=[{'resourceType':'Evidence','resourceId':'invented'}]
    elif fault=='expiry':request['expiresAt']=(NOW+timedelta(hours=3)).isoformat()
    elif fault=='payload_extra':request['payload']['approved']=True
    elif fault=='policy':f.row['approval_policy_hash']='0'*64
    elif fault=='risk':f.row['risk_snapshot']['policy']['draftOnly']=False
    elif fault=='action_hash':f.row['action_type_snapshot']['revisionHash']='0'*64
    elif fault=='row_action':f.row['action_type_snapshot']['name']='other'
    elif fault=='meta_action':f.meta['name']='other'
    elif fault=='meta_object_bool':f.obj['published']=1
    else:f.ref['revision']=True
    f.seal()
    with pytest.raises(action.RouteEvalMaterialRejected):read(f)


@pytest.mark.parametrize('fault',['database','role','tenant','isolation','readonly','xid','pid','db_oid_bool',
    'session_after_wait','xid_after_wait','shadowed_relation','namespace_after_wait','clock_backwards','expired_after_wait','row_clock_naive','row_clock_future','head_clock_future'])
def test_material_reader_retains_exact_native_context_and_rechecks_clock_after_waits(monkeypatch,fault):
    f=offline(monkeypatch)
    if fault in {'database','role','isolation','readonly','xid','pid'}:f.ctx[fault]='other'
    elif fault=='tenant':f.ctx['org_id']='dev-org'
    elif fault=='db_oid_bool':f.ctx['database_oid']=True
    elif fault=='session_after_wait':f.after={**f.ctx,'login':'other'}
    elif fault=='xid_after_wait':f.after={**f.ctx,'xid':'235'}
    elif fault=='shadowed_relation':f.ctx['original_relations']=[True,True,False,True,True]
    elif fault=='namespace_after_wait':f.after={**f.ctx,'original_relations':[True,True,False,True,True]}
    elif fault=='clock_backwards':f.after={**f.ctx,'now':NOW-timedelta(seconds=1)}
    elif fault=='expired_after_wait':f.after={**f.ctx,'now':NOW+timedelta(hours=2)}
    elif fault=='row_clock_naive':f.row['created_at']=NOW.replace(tzinfo=None)
    elif fault=='row_clock_future':f.row['created_at']=NOW+timedelta(seconds=1)
    else:f.head['updated_at']=NOW+timedelta(seconds=1)
    with pytest.raises(action.RouteEvalMaterialRejected):read(f)


def test_material_reader_unmodified_native_guard_rejects_all_fake_connections_before_sql():
    f=MaterialFixture()
    with pytest.raises(action.RouteEvalMaterialRejected):read(f)
    assert f.calls==[]


def test_original_append_only_revision_permissions_do_not_require_update_row_lock(monkeypatch):
    from psycopg.errors import InsufficientPrivilege
    f=offline(monkeypatch)
    execute=f.execute
    def original_permissions(statement,params=()):
        if 'FROM public.aip_action_draft_revision' in statement and ('FOR SHARE' in statement or 'FOR UPDATE' in statement):
            raise InsufficientPrivilege('synthetic original revision table rejects row locks')
        return execute(statement,params)
    f.execute=original_permissions
    result=read(f)
    assert json.loads(result.split(b'\n',1)[1])['materialRef']==f.ref
    head=next(i for i,(s,_) in enumerate(f.calls) if 'FROM public.aip_action_draft_head' in s)
    revision=next(i for i,(s,_) in enumerate(f.calls) if 'FROM public.aip_action_draft_revision' in s)
    assert head<revision and 'FOR SHARE' in f.calls[head][0]
    assert all('has_any_column_privilege' in s and 'TRUNCATE' in s for s,_ in f.calls if 'session_user AS login' in s)


@pytest.mark.parametrize('proof',[None,[],[True]*3,(True,)*4,[1,True,True,True],
    [False,True,True,True],[True,False,True,True],[True,True,False,True],[True,True,True,False]])
def test_material_requires_native_complete_append_only_revision_permissions(monkeypatch,proof):
    f=offline(monkeypatch);f.ctx['append_only_revision']=proof
    with pytest.raises(action.RouteEvalMaterialRejected):read(f)
    assert not any('FROM public.aip_action_draft_head' in s for s,_ in f.calls)


def test_append_only_revision_permission_is_rechecked_after_head_lock_wait(monkeypatch):
    f=offline(monkeypatch);f.after={**f.ctx,'append_only_revision':[True,False,True,True]}
    with pytest.raises(action.RouteEvalMaterialRejected):read(f)
    assert any('FROM public.aip_action_draft_head' in s and 'FOR SHARE' in s for s,_ in f.calls)


# Protocol-only cases. Native type check substitution is never SCRAM evidence.
from test_model_route_eval_context_reader import SQLSnapshot,Rows as SnapshotRows
from test_model_route_eval_subject_binding import SCOPE as SNAP_SCOPE,NOW as SNAP_NOW
from aos_api.aip_eval_contracts import EvalRunStatus


class NativeContextSnapshot(SQLSnapshot):
    def __init__(self,*,route=True):
        super().__init__(route=route)
        self.native=dict(database='unit_only',database_oid=123,login='synthetic_runtime',
            role='aos_runtime',org_id=SNAP_SCOPE.org_id,project_id=SNAP_SCOPE.project_id,
            isolation='serializable',readonly='off',xid='123',pid=456,now=SNAP_NOW,
            original_relations=[True]*14)
        self.context.update(isolation='serializable',read_only='off')
        self.native_after={};self.boundaries=0
        from test_model_route_eval_publication_epoch import ProfileFixture
        self.epoch_profile=ProfileFixture();self.epoch_value=1;self.epoch_error=None
        self.info.dbname='unit_only'

    def execute(self,sql,params=()):
        compact=' '.join(sql.split())
        if 'AS epoch_reader_context' in compact:
            self.calls.append((compact,params));return SnapshotRows([dict(self.native)])
        if any(marker in compact for marker in ('AS epoch_reader_profile','AS epoch_original_table',
                'AS epoch_reader_policy','AS epoch_original_trigger')):
            self.calls.append((compact,params));return self.epoch_profile.execute(sql,params)
        if 'SELECT public.aos_model_route_eval_publication_epoch_lock' in compact:
            self.calls.append((compact,params))
            if self.epoch_error:raise self.epoch_error
            return SnapshotRows([dict(epoch=self.epoch_value)])
        if 'AS native_eval_context' in compact:
            self.calls.append((compact,params));self.boundaries+=1
            return SnapshotRows([{**self.native,**(self.native_after if self.boundaries>1 else {})}])
        if 'FOR UPDATE OF h' in compact:
            self.calls.append((compact,params))
            return SnapshotRows([dict(kind='model_route' if self.claim.source_ref.asset_type=='ModelRouteRevision' else 'registered_model',
                version=self.head_version,asset_id=self.claim.source_ref.asset_id,
                revision=self.source.revision,content_hash=self.source.content_hash,
                lifecycle=self.source.lifecycle.value,payload=self.source.model_dump(mode='json',by_alias=True))])
        return super().execute(sql,params)


def native_context_read(conn,**changes):
    args=dict(expected_database='unit_only',scope=SNAP_SCOPE,candidate=conn.claim,
        run_id='run',expected_run_version=2,expected_run_status=EvalRunStatus.RUNNING,
        expires_at=SNAP_NOW+timedelta(minutes=1))
    args.update(changes)
    return action.read_native_eval_subject_context_bytes(conn,**args)


@pytest.mark.parametrize('route',[False,True])
def test_native_context_original_dao_locked_snapshot(monkeypatch,route):
    monkeypatch.setattr(owner,'_require_native_connection',lambda conn:None)
    conn=NativeContextSnapshot(route=route)
    result=native_context_read(conn)
    assert result.startswith(b'AOS-MODEL-ROUTE-EVAL-CONTEXT-v1\n')
    data=json.loads(result.split(b'\n',1)[1])
    assert data['executionAllowed'] is False
    from test_model_route_eval_context_reader import read as readonly_context_read
    assert result==readonly_context_read(SQLSnapshot(route=route))
    assert data['run']['runId']=='run' and data['snapshotReadAt']==SNAP_NOW.isoformat()
    sql=[s for s,p in conn.calls]
    locks=[s for s in sql if 'FOR UPDATE' in s or 'FOR SHARE' in s]
    assert 'FOR UPDATE OF h' in locks[0]
    assert any('aip_eval_run' in s and 'FOR UPDATE' in s for s in locks)
    assert any('aip_eval_contract_head' in s and 'FOR SHARE' in s for s in locks)
    assert any('aip_publication_event' in s and 'ORDER BY p.occurred_at,p.event_id LIMIT 1 FOR SHARE OF p' in s for s in locks)
    assert any('aip_release_gate_decision' in s and 'FOR SHARE' in s for s in locks)
    assert not any('_revision' in s.split(' FROM ',1)[1].split(' WHERE ',1)[0] and 'FOR SHARE' in s for s in locks)
    assert conn.boundaries==2
    assert all(s.startswith('SELECT ') for s in sql)
    assert conn.info.transaction_status.name=='INTRANS'


def test_native_context_rejects_fake_connection_before_sql():
    conn=NativeContextSnapshot()
    with pytest.raises(ValueError):native_context_read(conn)
    assert conn.calls==[]


@pytest.mark.parametrize('changes',[
    dict(scope=TenantScope('dev-org','dev-project')),dict(expected_database='wrong database'),
    dict(run_id=' run'),dict(expected_run_version=True),dict(expected_run_status='running'),
    dict(expected_run_status=EvalRunStatus.SUCCEEDED),dict(expires_at=SNAP_NOW.replace(tzinfo=None)),
])
def test_native_context_input_rejection_before_sql(monkeypatch,changes):
    monkeypatch.setattr(owner,'_require_native_connection',lambda conn:None)
    conn=NativeContextSnapshot()
    with pytest.raises(ValueError):native_context_read(conn,**changes)
    assert conn.calls==[]


@pytest.mark.parametrize('changes',[
    dict(database='other'),dict(database_oid=True),dict(login='bad login'),dict(role='aos_app'),
    dict(org_id='dev-org'),dict(isolation='repeatable read'),dict(readonly='on'),dict(xid='0'),
    dict(pid=True),dict(now=SNAP_NOW.replace(tzinfo=None)),dict(original_relations=[True]*13),
    dict(original_relations=[True]*13+[None]),dict(original_relations=[True]*13+[1]),
])
def test_native_context_boundary_rejection(monkeypatch,changes):
    monkeypatch.setattr(owner,'_require_native_connection',lambda conn:None)
    conn=NativeContextSnapshot();conn.native.update(changes)
    with pytest.raises(ValueError):native_context_read(conn)
    assert not any('FOR UPDATE' in s for s,p in conn.calls)


@pytest.mark.parametrize('changes',[
    dict(login='different_login'),dict(database_oid=124),dict(xid='124'),dict(pid=457),
    dict(now=SNAP_NOW-timedelta(seconds=1)),dict(now=SNAP_NOW+timedelta(minutes=1)),
    dict(original_relations=[True]*13+[False]),
])
def test_native_context_after_wait_identity_and_expiry(monkeypatch,changes):
    monkeypatch.setattr(owner,'_require_native_connection',lambda conn:None)
    conn=NativeContextSnapshot();conn.native_after=changes
    with pytest.raises(ValueError):native_context_read(conn)
    assert conn.boundaries==2


@pytest.mark.parametrize('fault',['candidate','run','contract','publication','gate','json'])
def test_native_context_original_authority_refusals(monkeypatch,fault):
    monkeypatch.setattr(owner,'_require_native_connection',lambda conn:None)
    conn=NativeContextSnapshot()
    if fault=='candidate':conn.head_version+=1
    elif fault=='run':conn.run['version']+=1
    elif fault=='contract':conn.contract_head['current_revision']+=1
    elif fault=='publication':conn.publication['event_type']='revoked'
    elif fault=='gate':conn.gate['status']='failed'
    else:conn.payload_tamper=True
    from aos_api.aip_model_runtime_store import ModelRuntimeConflict
    with pytest.raises(ModelRuntimeConflict if fault=='candidate' else ValueError):native_context_read(conn)


def test_native_context_publication_epoch_precedes_gate_and_full_read(monkeypatch):
    monkeypatch.setattr(owner,'_require_native_connection',lambda conn:None)
    conn=NativeContextSnapshot();native_context_read(conn)
    sql=[s for s,p in conn.calls]
    publication=next(i for i,s in enumerate(sql) if 'FOR SHARE OF p' in s)
    fence=next(i for i,s in enumerate(sql) if 'SELECT public.aos_model_route_eval_publication_epoch_lock' in s)
    gate=next(i for i,s in enumerate(sql) if 'aip_release_gate_decision' in s and 'FOR SHARE' in s)
    body=next(i for i,s in enumerate(sql) if 'UNION ALL' in s)
    assert publication<fence<gate<body


def test_native_context_old_snapshot_epoch_conflict_propagates_before_gate(monkeypatch):
    import psycopg
    monkeypatch.setattr(owner,'_require_native_connection',lambda conn:None)
    conn=NativeContextSnapshot();error=psycopg.errors.SerializationFailure('synthetic old snapshot')
    conn.epoch_error=error
    with pytest.raises(psycopg.errors.SerializationFailure) as result:native_context_read(conn)
    assert result.value is error
    assert not any('aip_release_gate_decision' in s and 'FOR SHARE' in s for s,p in conn.calls)


@pytest.mark.parametrize('value',[0,None,True])
def test_native_context_bad_epoch_never_reaches_gate(monkeypatch,value):
    monkeypatch.setattr(owner,'_require_native_connection',lambda conn:None)
    conn=NativeContextSnapshot();conn.epoch_value=value
    with pytest.raises(ValueError):native_context_read(conn)
    assert not any('aip_release_gate_decision' in s and 'FOR SHARE' in s for s,p in conn.calls)


# Necessary whole-request equality for the dedicated Route guard. These are
# synthetic DTOs, never original approval, Source, native or budget proof.
@pytest.mark.parametrize('purpose',['target','judge'])
def test_route_call_request_exact_binding_accepts_both_original_direct_proposals(purpose):
    f=MaterialFixture(); call=next(c for c in f.app.calls if c.purpose==purpose)
    request=action.build_route_eval_call_proposal(f.raw,application=f.app,recipe=call,material_ref=f.ref,checked_at=NOW)
    original=dump(request)
    result=action.validate_route_eval_call_proposal(f.raw,application=f.app,recipe=call,
        material_ref=f.ref,request=request,checked_at=NOW)
    assert type(result) is type(request) and result is not request
    assert dump(result)==original and dump(request)==original


@pytest.mark.parametrize('fault',[
    'operation','task','purpose','run','object','risk','diff','evidence','impact','expiry','missing_expiry',
    'applicationHash','recipeHash','callKey','caseId','callPurpose','upperBound','extra_payload','missing_payload',
    'materialTenant','materialId','materialRevision','materialHead','materialHash','materialBoolRevision',
    'draft_subclass','dict','other_call',
])
def test_route_call_request_cannot_borrow_another_call_or_material_approval(fault):
    from aos_api.aip_action_models import CreateActionProposalRequest,CreateActionDraftRequest
    f=MaterialFixture(); call=f.app.calls[0]
    request=action.build_route_eval_call_proposal(f.raw,application=f.app,recipe=call,material_ref=f.ref,checked_at=NOW)
    raw=dump(request)
    if fault=='operation':raw['actionTypeId']='aip_route_eval_judge_call'
    elif fault=='task':raw['taskId']='other-task'
    elif fault=='purpose':raw['purpose']='other-purpose'
    elif fault=='run':raw['runId']='other-run'
    elif fault=='object':raw['objectRef']={'resourceType':'Object','resourceId':'other','authority':'synthetic'}
    elif fault=='risk':raw['riskHint']='R2'
    elif fault=='diff':raw['diff']={'extra':'value'}
    elif fault=='evidence':raw['evidenceRefs']=[{'resourceType':'Object','resourceId':'other','authority':'synthetic'}]
    elif fault=='impact':raw['impactPreviewRef']={'resourceType':'ImpactPreviewRevision','resourceId':'other','revision':1,'contentHash':'a'*64}
    elif fault=='expiry':raw['expiresAt']=(f.app.expires_at-timedelta(seconds=1)).isoformat()
    elif fault=='missing_expiry':raw['expiresAt']=None
    elif fault in ('applicationHash','recipeHash','callKey','caseId'):raw['payload'][fault]='other'
    elif fault=='callPurpose':raw['payload']['purpose']='judge'
    elif fault=='upperBound':raw['payload']['budgetUpperBoundMinor']+=1
    elif fault=='extra_payload':raw['payload']['unreviewed']='value'
    elif fault=='missing_payload':del raw['payload']['recipeHash']
    elif fault=='materialTenant':raw['payload']['materialRef']['tenant']['orgId']='dev-org'
    elif fault=='materialId':raw['payload']['materialRef']['resourceId']='other'
    elif fault=='materialRevision':raw['payload']['materialRef']['revision']+=1
    elif fault=='materialHead':raw['payload']['materialRef']['headVersion']+=1
    elif fault=='materialHash':raw['payload']['materialRef']['contentHash']='b'*64
    elif fault=='materialBoolRevision':raw['payload']['materialRef']['revision']=True
    elif fault=='other_call':raw=dump(action.build_route_eval_call_proposal(f.raw,application=f.app,
        recipe=f.app.calls[1],material_ref=f.ref,checked_at=NOW))
    if fault=='draft_subclass':request=CreateActionDraftRequest.model_validate(raw)
    elif fault=='dict':request=raw
    else:request=CreateActionProposalRequest.model_validate(raw)
    with pytest.raises(action.RouteEvalMaterialRejected,match='ROUTE_EVAL_EXACT_CALL_REQUEST_REQUIRED'):
        action.validate_route_eval_call_proposal(f.raw,application=f.app,recipe=call,
            material_ref=f.ref,request=request,checked_at=NOW)


@pytest.mark.parametrize('fault',['expired','stale_context','wrong_recipe','wrong_material_tenant'])
def test_route_call_request_binding_rederives_the_complete_current_application(fault):
    f=MaterialFixture(); call=f.app.calls[0];at=NOW;context=f.raw;ref=deepcopy(f.ref)
    request=action.build_route_eval_call_proposal(context,application=f.app,recipe=call,material_ref=ref,checked_at=at)
    if fault=='expired':at=f.app.expires_at
    elif fault=='stale_context':context=context.replace(b'case',b'CASE',1)
    elif fault=='wrong_recipe':call=call.model_copy(update={'case_id':'other'})
    elif fault=='wrong_material_tenant':ref['tenant']['orgId']='dev-org'
    with pytest.raises(action.RouteEvalMaterialRejected,match='ROUTE_EVAL_EXACT_CALL_REQUEST_REQUIRED'):
        action.validate_route_eval_call_proposal(context,application=f.app,recipe=call,
            material_ref=ref,request=request,checked_at=at)


@pytest.mark.parametrize('fault',['unknown_model_copy_field','copied_untrimmed_purpose','copied_payload_nan'])
def test_route_call_request_cannot_hide_unvalidated_model_copy_fields(fault):
    f=MaterialFixture();call=f.app.calls[0]
    request=action.build_route_eval_call_proposal(f.raw,application=f.app,recipe=call,material_ref=f.ref,checked_at=NOW)
    if fault=='unknown_model_copy_field':request=request.model_copy(update={'unreviewed':'value'})
    elif fault=='copied_untrimmed_purpose':request=request.model_copy(update={'purpose':' route-eval '})
    else:
        payload=deepcopy(request.payload);payload['budgetUpperBoundMinor']=float('nan')
        request=request.model_copy(update={'payload':payload})
    with pytest.raises(action.RouteEvalMaterialRejected,match='ROUTE_EVAL_EXACT_CALL_REQUEST_REQUIRED'):
        action.validate_route_eval_call_proposal(f.raw,application=f.app,recipe=call,
            material_ref=f.ref,request=request,checked_at=NOW)


@pytest.mark.parametrize('purpose',['target','judge'])
def test_route_action_guard_first_slice_reaches_native_source_gate_only_after_exact_leaf(purpose):
    from aos_api.aip_action_store import AipActionTransitionBlocked
    f=MaterialFixture();call=next(item for item in f.app.calls if item.purpose==purpose)
    request=action.build_route_eval_call_proposal(f.raw,application=f.app,recipe=call,
        material_ref=f.ref,checked_at=NOW)
    snapshot={'id':request.action_type_id,'revisionHash':'a'*64}
    risk=classify_action_risk(request.action_type_id,snapshot,request.payload,None)
    guard=action.RouteEvalActionGuard()
    assert all(callable(getattr(guard,name)) for name in
        ('check_request','check_proposal','prelock_decision','assert_prelocked_proposal'))
    with pytest.raises(AipActionTransitionBlocked,match='ROUTE_EVAL_NATIVE_SOURCE_GUARD_REQUIRED'):
        guard.check_request(None,f.scope,'synthetic-maker',request,snapshot,risk)


@pytest.mark.parametrize('fault',['action_mismatch','snapshot_mismatch','snapshot_type','snapshot_hash','purpose','task',
    'payload_extra','bool_amount','material_tenant','actor','scope','naive_expiry','risk_drift'])
def test_route_action_guard_first_slice_rejects_inexact_leaf_before_native_source(fault):
    from aos_api.aip_action_models import CreateActionProposalRequest
    from aos_api.aip_action_store import AipActionTransitionBlocked
    f=MaterialFixture();call=f.app.calls[0]
    request=action.build_route_eval_call_proposal(f.raw,application=f.app,recipe=call,
        material_ref=f.ref,checked_at=NOW)
    raw=dump(request);snapshot={'id':request.action_type_id,'revisionHash':'a'*64}
    if fault=='action_mismatch':raw['actionTypeId']='aip_route_eval_judge_call'
    elif fault=='snapshot_mismatch':snapshot['id']='aip_route_eval_judge_call'
    elif fault=='snapshot_type':snapshot=object()
    elif fault=='snapshot_hash':snapshot['revisionHash']='not-a-hash'
    elif fault=='purpose':raw['purpose']='other'
    elif fault=='task':raw['taskId']=None
    elif fault=='payload_extra':raw['payload']['approved']=True
    elif fault=='bool_amount':raw['payload']['budgetUpperBoundMinor']=True
    elif fault=='material_tenant':raw['payload']['materialRef']['tenant']['orgId']='dev-org'
    elif fault=='naive_expiry':raw['expiresAt']=f.app.expires_at.replace(tzinfo=None).isoformat()
    changed=CreateActionProposalRequest.model_validate(raw)
    scope=TenantScope('dev-org','dev-project') if fault=='scope' else f.scope
    actor=' synthetic-maker ' if fault=='actor' else 'synthetic-maker'
    risk=(classify_action_risk(changed.action_type_id,snapshot,changed.payload,None)
          if isinstance(snapshot,dict) else object())
    if fault=='risk_drift':risk=object()
    with pytest.raises(AipActionTransitionBlocked,match='ROUTE_EVAL_DIRECT_CALL_REQUIRED'):
        action.RouteEvalActionGuard().check_request(None,scope,actor,changed,snapshot,risk)


def route_guard_native_inputs(fixture):
    from aos_api.aip_eval_contracts import EvalRunStatus
    from aos_api.aip_model_runtime_contracts import ModelEvalCandidate
    from aos_api.aip_provider_capacity_source_contracts import ProviderCapacityConsumptionCommand
    context=json.loads(fixture.raw.split(b'\n',1)[1])
    candidate=ModelEvalCandidate.model_validate(context['subject']['candidate'])
    unique={}
    for call in fixture.app.calls:unique.setdefault(call.source_ref.asset_id,call.source_ref)
    commands=tuple(ProviderCapacityConsumptionCommand(schemaVersion=1,tenant=TENANT,
        bearerToken='a.b.c',sourceRef=dump(unique[key])) for key in sorted(unique))
    return dict(expected_database='aos_test_guard',context_bytes=fixture.raw,
        application=fixture.app,candidate=candidate,run_id=context['run']['runId'],
        expected_run_version=context['run']['version'],
        expected_run_status=EvalRunStatus(context['run']['status']),source_commands=commands)


@pytest.mark.parametrize('fault',['partial','database','context','application','candidate','candidate_context','run_id',
    'run_version','run_status','commands_list','commands_empty','command_dict'])
def test_route_action_guard_g2a_requires_one_complete_exact_native_input_package(fault):
    f=MaterialFixture();inputs=route_guard_native_inputs(f)
    if fault=='partial':inputs={'expected_database':'aos_test_guard'}
    elif fault=='database':inputs['expected_database']='bad database'
    elif fault=='context':inputs['context_bytes']=bytearray(inputs['context_bytes'])
    elif fault=='application':inputs['application']=dump(inputs['application'])
    elif fault=='candidate':inputs['candidate']=dump(inputs['candidate'])
    elif fault=='candidate_context':inputs['candidate']=inputs['candidate'].model_copy(
        update={'expected_head_version':inputs['candidate'].expected_head_version+1})
    elif fault=='run_id':inputs['run_id']=' run'
    elif fault=='run_version':inputs['expected_run_version']=True
    elif fault=='run_status':inputs['expected_run_status']='running'
    elif fault=='commands_list':inputs['source_commands']=list(inputs['source_commands'])
    elif fault=='commands_empty':inputs['source_commands']=()
    else:inputs['source_commands']=(dump(inputs['source_commands'][0]),)
    with pytest.raises(TypeError,match='exact Route Eval native guard inputs required'):
        action.RouteEvalActionGuard(**inputs)


def test_route_action_guard_g2a_deep_copies_server_owned_native_inputs(monkeypatch):
    from aos_api.aip_action_store import AipActionTransitionBlocked
    from aos_api.aip_model_route_eval_manifest import _canonical
    f=MaterialFixture();call=f.app.calls[0]
    request=action.build_route_eval_call_proposal(f.raw,application=f.app,recipe=call,
        material_ref=f.ref,checked_at=NOW)
    snapshot={'id':request.action_type_id,'revisionHash':'a'*64}
    risk=classify_action_risk(request.action_type_id,snapshot,request.payload,None)
    inputs=route_guard_native_inputs(f);original_app=deepcopy(dump(inputs['application']))
    original_commands=tuple(dump(item.source_ref) for item in inputs['source_commands'])
    guard=action.RouteEvalActionGuard(**inputs)
    inputs['application'].calls.clear()
    def source(conn,**kwargs):
        assert dump(kwargs['application'])==original_app
        assert tuple(dump(item.source_ref) for item in kwargs['commands'])==original_commands
        body={'schemaVersion':'aos.route-eval-preapproval-source-prefix/v1',
            'applicationHash':request.payload['applicationHash'],'contextBindingHash':original_app['contextBindingHash'],
            'database':'aos_test_guard','databaseOid':123,'callerXid':'234','callerPid':99,
            'checkedAt':NOW.isoformat(),'sources':[],'executionAllowed':False}
        return b'AOS-ROUTE-EVAL-NATIVE-SOURCE-PREFIX-v1\n'+_canonical(body)
    material={'schemaVersion':'aos.route-eval-material-readback/v1','tenant':TENANT,
        'materialRef':f.ref,'makerId':'synthetic-maker','context':json.loads(f.raw.split(b'\n',1)[1]),
        'application':original_app,'actionTypeRevisionHash':'b'*64,'database':'aos_test_guard',
        'databaseOid':123,'callerXid':'234','callerPid':99,'observedAt':NOW.isoformat(),
        'approvalAllowed':False,'executionAllowed':False}
    monkeypatch.setattr(owner,'prepare_route_eval_native_sources',source)
    monkeypatch.setattr(action,'read_route_eval_material_draft',lambda *a,**k:
        action.MATERIAL_READBACK_DOMAIN+_canonical(material))
    monkeypatch.setattr(action,'read_native_eval_subject_context_bytes',lambda *a,**k:f.raw)
    monkeypatch.setattr(action,'_native_eval_context_boundary',lambda *a,**k:
        {'database':'aos_test_guard','database_oid':123,'xid':'234','pid':99,'now':NOW})
    with pytest.raises(AipActionTransitionBlocked,match='ROUTE_EVAL_NATIVE_RULE_GUARD_REQUIRED'):
        guard.check_request(object(),f.scope,'synthetic-maker',request,snapshot,risk)


def test_route_action_guard_g2a_binds_source_material_and_current_context_before_rule(monkeypatch):
    from aos_api.aip_action_store import AipActionTransitionBlocked
    from aos_api.aip_model_route_eval_manifest import _canonical,route_eval_approval_payload
    f=MaterialFixture();call=f.app.calls[0]
    request=action.build_route_eval_call_proposal(f.raw,application=f.app,recipe=call,
        material_ref=f.ref,checked_at=NOW)
    snapshot={'id':request.action_type_id,'revisionHash':'a'*64}
    risk=classify_action_risk(request.action_type_id,snapshot,request.payload,None)
    order=[]
    def source(conn,**kwargs):
        order.append('source')
        assert kwargs['actor_id']=='synthetic-maker'
        body={'schemaVersion':'aos.route-eval-preapproval-source-prefix/v1',
            'applicationHash':request.payload['applicationHash'],
            'contextBindingHash':f.app.context_binding_hash,'database':'aos_test_guard',
            'databaseOid':123,'callerXid':'234','callerPid':99,'checkedAt':NOW.isoformat(),
            'sources':[],'executionAllowed':False}
        return b'AOS-ROUTE-EVAL-NATIVE-SOURCE-PREFIX-v1\n'+_canonical(body)
    def material(conn,**kwargs):
        order.append('material')
        body={'schemaVersion':'aos.route-eval-material-readback/v1','tenant':TENANT,
            'materialRef':f.ref,'makerId':'synthetic-maker',
            'context':json.loads(f.raw.split(b'\n',1)[1]),'application':dump(f.app),
            'actionTypeRevisionHash':'b'*64,'database':'aos_test_guard','databaseOid':123,
            'callerXid':'234','callerPid':99,'observedAt':NOW.isoformat(),
            'approvalAllowed':False,'executionAllowed':False}
        return action.MATERIAL_READBACK_DOMAIN+_canonical(body)
    def current(conn,**kwargs):order.append('context');return f.raw
    def final(conn,expected_database,scope):
        order.append('final')
        return {'database':'aos_test_guard','database_oid':123,'xid':'234','pid':99,'now':NOW}
    monkeypatch.setattr(owner,'prepare_route_eval_native_sources',source)
    monkeypatch.setattr(action,'read_route_eval_material_draft',material)
    monkeypatch.setattr(action,'read_native_eval_subject_context_bytes',current)
    monkeypatch.setattr(action,'_native_eval_context_boundary',final)
    guard=action.RouteEvalActionGuard(**route_guard_native_inputs(f))
    with pytest.raises(AipActionTransitionBlocked,match='ROUTE_EVAL_NATIVE_RULE_GUARD_REQUIRED'):
        guard.check_request(object(),f.scope,'synthetic-maker',request,snapshot,risk)
    assert order==['source','material','context','final']
    assert route_eval_approval_payload(f.app,call)=={k:v for k,v in request.payload.items() if k!='materialRef'}


@pytest.mark.parametrize('fault',['source','material','context','caller','clock','recipe'])
def test_route_action_guard_g2a_rejects_dependency_drift_before_rule(monkeypatch,fault):
    from aos_api.aip_action_store import AipActionTransitionBlocked
    from aos_api.aip_model_route_eval_manifest import _canonical
    f=MaterialFixture();call=f.app.calls[0]
    request=action.build_route_eval_call_proposal(f.raw,application=f.app,recipe=call,
        material_ref=f.ref,checked_at=NOW)
    snapshot={'id':request.action_type_id,'revisionHash':'a'*64}
    risk=classify_action_risk(request.action_type_id,snapshot,request.payload,None)
    source_body={'schemaVersion':'aos.route-eval-preapproval-source-prefix/v1',
        'applicationHash':request.payload['applicationHash'],'contextBindingHash':f.app.context_binding_hash,
        'database':'aos_test_guard','databaseOid':123,'callerXid':'234','callerPid':99,
        'checkedAt':NOW.isoformat(),'sources':[],'executionAllowed':False}
    material_body={'schemaVersion':'aos.route-eval-material-readback/v1','tenant':TENANT,
        'materialRef':f.ref,'makerId':'synthetic-maker','context':json.loads(f.raw.split(b'\n',1)[1]),
        'application':dump(f.app),'actionTypeRevisionHash':'b'*64,'database':'aos_test_guard',
        'databaseOid':123,'callerXid':'234','callerPid':99,'observedAt':NOW.isoformat(),
        'approvalAllowed':False,'executionAllowed':False}
    current=f.raw
    if fault=='source':source_body['applicationHash']='0'*64
    elif fault=='material':material_body['makerId']='other'
    elif fault=='context':current=current.replace(b'"executionAllowed":false',b'"executionAllowed":true')
    elif fault=='caller':material_body['callerXid']='235'
    elif fault=='clock':material_body['observedAt']=(NOW-timedelta(seconds=1)).isoformat()
    else:
        payload=deepcopy(request.payload);payload['callKey']='other'
        request=request.model_copy(update={'payload':payload})
    monkeypatch.setattr(owner,'prepare_route_eval_native_sources',lambda *a,**k:
        b'AOS-ROUTE-EVAL-NATIVE-SOURCE-PREFIX-v1\n'+_canonical(source_body))
    monkeypatch.setattr(action,'read_route_eval_material_draft',lambda *a,**k:
        action.MATERIAL_READBACK_DOMAIN+_canonical(material_body))
    monkeypatch.setattr(action,'read_native_eval_subject_context_bytes',lambda *a,**k:current)
    monkeypatch.setattr(action,'_native_eval_context_boundary',lambda *a,**k:
        {'database':'aos_test_guard','database_oid':123,'xid':'234','pid':99,'now':NOW})
    with pytest.raises(AipActionTransitionBlocked) as error:
        action.RouteEvalActionGuard(**route_guard_native_inputs(f)).check_request(
            object(),f.scope,'synthetic-maker',request,snapshot,risk)
    assert 'ROUTE_EVAL_NATIVE_RULE_GUARD_REQUIRED' not in str(error.value)


def route_guard_rule_inputs():
    from aos_api.asset_registry.release_policy import ReleasePolicy
    from aos_api.asset_registry.signature import FrozenTrustRootProvider
    return dict(release_policy=ReleasePolicy(trust_roots=FrozenTrustRootProvider({})),
        artifact_bytes={'rule.json':b'r','template.json':b't','implementation.json':b'i'})


def install_route_guard_native_stubs(monkeypatch,fixture,request,order):
    from aos_api.aip_model_route_eval_manifest import _canonical
    def source(conn,**kwargs):
        order.append('source')
        body={'schemaVersion':'aos.route-eval-preapproval-source-prefix/v1',
            'applicationHash':request.payload['applicationHash'],
            'contextBindingHash':fixture.app.context_binding_hash,'database':'aos_test_guard',
            'databaseOid':123,'callerXid':'234','callerPid':99,'checkedAt':NOW.isoformat(),
            'sources':[],'executionAllowed':False}
        return b'AOS-ROUTE-EVAL-NATIVE-SOURCE-PREFIX-v1\n'+_canonical(body)
    def material(conn,**kwargs):
        order.append('material')
        body={'schemaVersion':'aos.route-eval-material-readback/v1','tenant':TENANT,
            'materialRef':fixture.ref,'makerId':'synthetic-maker',
            'context':json.loads(fixture.raw.split(b'\n',1)[1]),'application':dump(fixture.app),
            'actionTypeRevisionHash':'b'*64,'database':'aos_test_guard','databaseOid':123,
            'callerXid':'234','callerPid':99,'observedAt':NOW.isoformat(),
            'approvalAllowed':False,'executionAllowed':False}
        return action.MATERIAL_READBACK_DOMAIN+_canonical(body)
    def current(conn,**kwargs):order.append('context');return fixture.raw
    def final(conn,expected_database,scope):
        order.append('final')
        return {'database':'aos_test_guard','database_oid':123,'xid':'234','pid':99,'now':NOW}
    monkeypatch.setattr(owner,'prepare_route_eval_native_sources',source)
    monkeypatch.setattr(action,'read_route_eval_material_draft',material)
    monkeypatch.setattr(action,'read_native_eval_subject_context_bytes',current)
    monkeypatch.setattr(action,'_native_eval_context_boundary',final)


def test_route_action_guard_g2b_reads_original_rule_before_and_after_all_waits(monkeypatch):
    from aos_api.aip_action_store import AipActionTransitionBlocked
    from aos_api.aip_model_eval_judge_request_store import ModelJudgeCallRequestStore
    f=MaterialFixture();call=f.app.calls[0]
    request=action.build_route_eval_call_proposal(f.raw,application=f.app,recipe=call,
        material_ref=f.ref,checked_at=NOW)
    snapshot={'id':request.action_type_id,'revisionHash':'a'*64}
    risk=classify_action_risk(request.action_type_id,snapshot,request.payload,None)
    order=[];facts={'source':dump(f.app.judge_rule_source),'rule':dump(f.app.judge_rule),
        'rootRevision':1,'validUntil':(NOW+timedelta(hours=2)).isoformat(),
        'ruleHash':canonical_hash(dump(f.app.judge_rule)),'signatureFingerprint':'sha256:'+'c'*64,
        'releaseEvidenceRevision':'sha256:'+'d'*64,'approvalAllowed':False,'executionAllowed':False}
    def rule(self,conn,scope,source,*,release_policy,artifact_bytes):
        order.append('rule-'+str(order.count('rule-1')+order.count('rule-2')+1))
        assert source==f.app.judge_rule_source
        assert artifact_bytes=={'rule.json':b'r','template.json':b't','implementation.json':b'i'}
        return deepcopy(facts)
    monkeypatch.setattr(ModelJudgeCallRequestStore,'read_published_rule',rule)
    install_route_guard_native_stubs(monkeypatch,f,request,order)
    inputs={**route_guard_native_inputs(f),**route_guard_rule_inputs()}
    guard=action.RouteEvalActionGuard(**inputs)
    inputs['artifact_bytes']['rule.json']=b'changed-after-construction'
    binding=guard.check_request(object(),f.scope,'synthetic-maker',request,snapshot,risk)
    assert binding==route_guard_expected_binding(f,request,snapshot)
    assert order==['rule-1','source','material','context','rule-2','final']


@pytest.mark.parametrize('fault',['partial_policy','partial_artifacts','artifact_value','policy_unsnapshotable',
    'source','rule','hash','window','drift'])
def test_route_action_guard_g2b_rejects_rule_configuration_or_currentness_drift(monkeypatch,fault):
    from aos_api.aip_action_store import AipActionTransitionBlocked
    from aos_api.aip_model_eval_judge_request_store import ModelJudgeCallRequestStore
    f=MaterialFixture();call=f.app.calls[0]
    request=action.build_route_eval_call_proposal(f.raw,application=f.app,recipe=call,
        material_ref=f.ref,checked_at=NOW)
    snapshot={'id':request.action_type_id,'revisionHash':'a'*64}
    risk=classify_action_risk(request.action_type_id,snapshot,request.payload,None)
    inputs=route_guard_native_inputs(f);rule_inputs=route_guard_rule_inputs()
    if fault=='partial_policy':rule_inputs.pop('artifact_bytes')
    elif fault=='partial_artifacts':rule_inputs.pop('release_policy')
    elif fault=='artifact_value':rule_inputs['artifact_bytes']['rule.json']='not-bytes'
    elif fault=='policy_unsnapshotable':
        from aos_api.asset_registry.release_policy import ReleasePolicy
        rule_inputs['release_policy']=ReleasePolicy(trust_roots=None)
    if fault in {'partial_policy','partial_artifacts','artifact_value','policy_unsnapshotable'}:
        with pytest.raises(TypeError,match='exact Route Eval native guard inputs required'):
            action.RouteEvalActionGuard(**inputs,**rule_inputs)
        return
    facts={'source':dump(f.app.judge_rule_source),'rule':dump(f.app.judge_rule),
        'rootRevision':1,'validUntil':(NOW+timedelta(hours=2)).isoformat(),
        'ruleHash':canonical_hash(dump(f.app.judge_rule)),'signatureFingerprint':'sha256:'+'c'*64,
        'releaseEvidenceRevision':'sha256:'+'d'*64,'approvalAllowed':False,'executionAllowed':False}
    if fault=='source':facts['source']={**facts['source'],'bundleId':'other'}
    elif fault=='rule':facts['rule']={**facts['rule'],'judgeId':'other'}
    elif fault=='hash':facts['ruleHash']='0'*64
    elif fault=='window':facts['validUntil']=(NOW+timedelta(minutes=1)).isoformat()
    calls=[]
    def rule(self,*args,**kwargs):
        calls.append(1);result=deepcopy(facts)
        if fault=='drift' and len(calls)==2:result['releaseEvidenceRevision']='sha256:'+'e'*64
        return result
    monkeypatch.setattr(ModelJudgeCallRequestStore,'read_published_rule',rule)
    install_route_guard_native_stubs(monkeypatch,f,request,[])
    with pytest.raises(AipActionTransitionBlocked,match='ROUTE_EVAL_NATIVE_RULE_GUARD_REQUIRED'):
        action.RouteEvalActionGuard(**inputs,**rule_inputs).check_request(
            object(),f.scope,'synthetic-maker',request,snapshot,risk)


def route_guard_expected_binding(fixture,request,snapshot):
    return canonical_hash({'schemaVersion':'aos.route-eval-action-binding/v1','tenant':TENANT,
        'taskId':request.task_id,'actionTypeId':request.action_type_id,
        'actionTypeRevisionHash':snapshot['revisionHash'],'payload':request.payload,
        'contextBindingHash':fixture.app.context_binding_hash,
        'judgeRuleSource':dump(fixture.app.judge_rule_source),
        'judgeRuleHash':canonical_hash(dump(fixture.app.judge_rule)),'executionAllowed':False})


def route_guard_proposal_fixture():
    from aos_api.aip_action_store import _proposal_stable_envelope
    f=MaterialFixture();call=f.app.calls[0]
    request=action.build_route_eval_call_proposal(f.raw,application=f.app,recipe=call,
        material_ref=f.ref,checked_at=NOW)
    snapshot={'id':request.action_type_id,'revisionHash':'a'*64}
    risk=classify_action_risk(request.action_type_id,snapshot,request.payload,None)
    binding=route_guard_expected_binding(f,request,snapshot)
    stable,_=_proposal_stable_envelope(f.scope,'synthetic-maker',request,snapshot,risk,
        action_binding_hash=binding,source_draft_ref=None,expires_at=request.expires_at)
    row={'proposal_id':'proposal','version':1,'action_type_id':request.action_type_id,
        'action_type_revision_hash':snapshot['revisionHash'],'action_type_snapshot':snapshot,
        'task_id':request.task_id,'run_id':None,'object_ref':None,'purpose':request.purpose,
        'client_risk_hint':None,'risk_level':risk.level.value,'policy_snapshot':stable['policy'],
        'payload':deepcopy(request.payload),'diff':{},'evidence_refs':[],'impact_preview_id':None,
        'impact_preview_revision':None,'impact_preview_hash':None,'action_binding_hash':binding,
        'source_draft_id':None,'source_draft_revision':None,'source_draft_hash':None,
        'approval_policy_hash':stable['approvalPolicyHash'],'proposal_hash':canonical_hash(stable),
        'status':'drafted','expires_at':request.expires_at,'created_by':'synthetic-maker'}
    return f,request,snapshot,risk,binding,stable,row


class RouteProposalConnection:
    def __init__(self,stable,row=None):self.stable=stable;self.row=row;self.calls=[]
    def execute(self,sql,params=()):
        self.calls.append((sql,params))
        if 'FROM aip_action_proposal' in sql:return Rows(deepcopy(self.row))
        if 'FROM aip_action_draft' in sql:return Rows({'snapshot':deepcopy(self.stable)})
        raise AssertionError('proposal guard must only read the stable Action draft')


def install_route_guard_rule_stub(monkeypatch,fixture):
    from aos_api.aip_model_eval_judge_request_store import ModelJudgeCallRequestStore
    facts={'source':dump(fixture.app.judge_rule_source),'rule':dump(fixture.app.judge_rule),
        'rootRevision':1,'validUntil':(NOW+timedelta(hours=2)).isoformat(),
        'ruleHash':canonical_hash(dump(fixture.app.judge_rule)),
        'signatureFingerprint':'sha256:'+'c'*64,
        'releaseEvidenceRevision':'sha256:'+'d'*64,
        'approvalAllowed':False,'executionAllowed':False}
    monkeypatch.setattr(ModelJudgeCallRequestStore,'read_published_rule',
        lambda *args,**kwargs:deepcopy(facts))


def test_route_action_guard_g3_maker_replay_validates_stable_proposal_without_source_relock(monkeypatch):
    f,request,snapshot,risk,binding,stable,row=route_guard_proposal_fixture()
    guard=action.RouteEvalActionGuard(**route_guard_native_inputs(f),**route_guard_rule_inputs())
    monkeypatch.setattr(owner,'prepare_route_eval_native_sources',lambda *a,**k:
        (_ for _ in ()).throw(AssertionError('proposal row lock must not reacquire Source')))
    conn=RouteProposalConnection(stable)
    assert guard.check_proposal(conn,f.scope,'synthetic-maker',row,checker=False) is None
    assert len(conn.calls)==1


def test_route_action_guard_g3_independent_checker_uses_current_membership_without_source_relock(monkeypatch):
    from aos_api.aip_model_eval_action import ModelEvalActionGuard
    f,request,snapshot,risk,binding,stable,row=route_guard_proposal_fixture();seen=[]
    guard=action.RouteEvalActionGuard(**route_guard_native_inputs(f),**route_guard_rule_inputs())
    monkeypatch.setattr(owner,'prepare_route_eval_native_sources',lambda *a,**k:
        (_ for _ in ()).throw(AssertionError('checker path must rely on prelock for Source')))
    monkeypatch.setattr(ModelEvalActionGuard,'_role',lambda conn,scope,actor:
        seen.append((conn,scope,actor)) or 'owner')
    conn=RouteProposalConnection(stable)
    assert guard.check_proposal(conn,f.scope,'synthetic-checker',row,checker=True)==('owner',)
    assert seen==[(conn,f.scope,'synthetic-checker')]


@pytest.mark.parametrize('fault',['action_revision','task','payload','risk','policy','binding',
    'proposal_hash','source_draft','stable','replay_actor','self_checker'])
def test_route_action_guard_g3_rejects_proposal_draft_or_actor_drift(monkeypatch,fault):
    from aos_api.aip_action_store import AipActionTransitionBlocked
    from aos_api.aip_model_eval_action import ModelEvalActionGuard
    f,request,snapshot,risk,binding,stable,row=route_guard_proposal_fixture()
    if fault=='action_revision':row['action_type_revision_hash']='0'*64
    elif fault=='task':row['task_id']='other'
    elif fault=='payload':row['payload']['callKey']='other'
    elif fault=='risk':row['risk_level']='R1'
    elif fault=='policy':row['approval_policy_hash']='0'*64
    elif fault=='binding':row['action_binding_hash']='0'*64
    elif fault=='proposal_hash':row['proposal_hash']='0'*64
    elif fault=='source_draft':row['source_draft_id']='draft'
    elif fault=='stable':stable['purpose']='other'
    guard=action.RouteEvalActionGuard(**route_guard_native_inputs(f),**route_guard_rule_inputs())
    monkeypatch.setattr(ModelEvalActionGuard,'_role',lambda *a:'owner')
    actor='other-maker' if fault=='replay_actor' else ('synthetic-maker' if fault=='self_checker' else 'synthetic-checker')
    checker=fault not in {'replay_actor'}
    with pytest.raises(AipActionTransitionBlocked):
        guard.check_proposal(RouteProposalConnection(stable),f.scope,actor,row,checker=checker)


@pytest.mark.parametrize('drift',['status','binding','policy','version','expiry'])
def test_route_action_guard_g4a_prelock_rechecks_all_current_inputs_and_fingerprints_complete_row(monkeypatch,drift):
    from aos_api.aip_action_store import AipActionTransitionBlocked
    from aos_api.aip_model_eval_action import ModelEvalActionGuard
    f,request,snapshot,risk,binding,stable,row=route_guard_proposal_fixture();order=[];roles=[]
    install_route_guard_rule_stub(monkeypatch,f)
    install_route_guard_native_stubs(monkeypatch,f,request,order)
    monkeypatch.setattr(ModelEvalActionGuard,'_role',lambda conn,scope,actor:
        roles.append(actor) or 'owner')
    guard=action.RouteEvalActionGuard(**route_guard_native_inputs(f),**route_guard_rule_inputs())
    conn=RouteProposalConnection(stable,row)
    fingerprint=guard.prelock_decision(conn,f.scope,'synthetic-checker','proposal')
    assert roles==['synthetic-checker','synthetic-checker']
    assert order==['source','material','context','final']
    guard.assert_prelocked_proposal(row,fingerprint)
    changed=deepcopy(row)
    if drift=='status':changed['status']='withdrawn'
    elif drift=='binding':changed['action_binding_hash']='0'*64
    elif drift=='policy':changed['approval_policy_hash']='0'*64
    elif drift=='version':changed['version']+=1
    else:changed['expires_at']=changed['expires_at']+timedelta(seconds=1)
    with pytest.raises(AipActionTransitionBlocked,match='ROUTE_EVAL_PRELOCK_PROPOSAL_DRIFTED'):
        guard.assert_prelocked_proposal(changed,fingerprint)


def test_route_action_guard_g4a_rejects_expiry_after_currentness_wait_before_action_locks(monkeypatch):
    from aos_api.aip_action_store import AipActionTransitionBlocked
    from aos_api.aip_model_eval_action import ModelEvalActionGuard
    f,request,snapshot,risk,binding,stable,row=route_guard_proposal_fixture();order=[]
    row['expires_at']=NOW;stable['expiresAt']=NOW.isoformat();row['proposal_hash']=canonical_hash(stable)
    install_route_guard_rule_stub(monkeypatch,f)
    install_route_guard_native_stubs(monkeypatch,f,request.model_copy(update={'expires_at':NOW}),order)
    monkeypatch.setattr(ModelEvalActionGuard,'_role',lambda *args:'owner')
    guard=action.RouteEvalActionGuard(**route_guard_native_inputs(f),**route_guard_rule_inputs())
    with pytest.raises(AipActionTransitionBlocked,match='ROUTE_EVAL_NATIVE_INPUT_REQUIRED'):
        guard.prelock_decision(RouteProposalConnection(stable,row),f.scope,
            'synthetic-checker','proposal')


def route_guard_approved_fixture():
    from aos_api.aip_action_store import canonical_hash as action_hash
    f,request,snapshot,risk,binding,stable,row=route_guard_proposal_fixture()
    row['version']=2;row['status']='approved'
    eligibility={'tenant':TENANT,'actorId':'synthetic-checker','roles':['owner'],
        'slotId':'checker.1','approvalPolicyHash':row['approval_policy_hash']}
    approval={'approval_event_id':'approval-route','proposal_id':row['proposal_id'],
        'proposal_version':1,'proposal_hash':row['proposal_hash'],'decision':'approved',
        'actor_id':'synthetic-checker','reason':'approved offline','expires_at':NOW+timedelta(minutes=30),
        'created_at':NOW,'action_binding_hash':binding,
        'approval_policy_hash':row['approval_policy_hash'],'slot_id':'checker.1',
        'eligibility_snapshot_hash':action_hash(eligibility)}
    return f,request,snapshot,risk,binding,stable,row,approval


class RouteBudgetConnection:
    def __init__(self,stable,row,approval,events=None):
        self.stable=stable;self.row=row;self.approval=approval
        self.events=events if events is not None else [approval];self.calls=[]
    def execute(self,sql,params=()):
        assert sql.lstrip().startswith('SELECT '),'G4b1 admission must not write outside original budget Store'
        self.calls.append((sql,params))
        if 'FROM aip_action_approval_event' in sql and "decision='approved'" in sql:
            return Rows(deepcopy(self.events))
        if 'FROM aip_action_approval_event' in sql:return Rows(deepcopy(self.approval))
        if 'FROM aip_action_proposal' in sql:return Rows(deepcopy(self.row))
        if 'FROM aip_action_draft' in sql:return Rows({'snapshot':deepcopy(self.stable)})
        if 'clock_timestamp() AS now' in sql:return Rows({'now':NOW})
        raise AssertionError('unexpected G4b1 admission query: '+sql)
    def commit(self):raise AssertionError('G4b1 must retain the caller transaction')
    rollback=commit


def install_route_budget_currentness(monkeypatch,f,request,order):
    from aos_api.aip_model_eval_action import ModelEvalActionGuard
    install_route_guard_rule_stub(monkeypatch,f)
    install_route_guard_native_stubs(monkeypatch,f,request,order)
    monkeypatch.setattr(ModelEvalActionGuard,'_role',lambda *args:'owner')


def test_route_action_guard_g4b1_rechecks_unique_approval_and_calls_original_budget_store_once(monkeypatch):
    from aos_api.aip_budget_reservation_store import AipBudgetReservationStore,canonical_hash as budget_hash
    f,request,snapshot,risk,binding,stable,row,approval=route_guard_approved_fixture();order=[];reserved=[]
    install_route_budget_currentness(monkeypatch,f,request,order)
    def reserve(self,conn,scope,budget,*,actor):
        reserved.append((conn,scope,budget,actor));return {'state':'held','synthetic':True}
    monkeypatch.setattr(AipBudgetReservationStore,'reserve_in_transaction',reserve)
    guard=action.RouteEvalActionGuard(**route_guard_native_inputs(f),**route_guard_rule_inputs())
    conn=RouteBudgetConnection(stable,row,approval)
    result=guard.reserve_current_call_budget(conn,f.scope,approval['approval_event_id'])
    assert result=={'state':'held','synthetic':True} and len(reserved)==1
    _,scope,budget,actor=reserved[0];call=f.app.calls[0]
    projection={key:approval[key] for key in ('approval_event_id','proposal_id','proposal_version',
        'proposal_hash','decision','actor_id','reason','expires_at','created_at','action_binding_hash')}
    assert scope==f.scope and actor=='synthetic-maker'
    assert budget.operation_id==request.action_type_id
    assert budget.invocation_key==request.payload['callKey']
    assert budget.task_ref==f.app.task_ref and budget.policy_ref==call.task_budget_ref
    assert budget.upper_bound_minor==request.payload['budgetUpperBoundMinor']
    assert budget.approval_ref.resource_id==approval['approval_event_id']
    assert budget.approval_ref.content_hash==budget_hash(projection,prefixed=True)
    assert order==['source','material','context','final']


@pytest.mark.parametrize('fault',['duplicate','slot','checker','binding','policy','eligibility','version','expiry'])
def test_route_action_guard_g4b1_rejects_approval_or_proposal_drift_before_budget_store(monkeypatch,fault):
    from aos_api.aip_action_store import AipActionTransitionBlocked
    from aos_api.aip_budget_reservation_store import AipBudgetReservationStore
    f,request,snapshot,risk,binding,stable,row,approval=route_guard_approved_fixture();order=[]
    events=[approval]
    if fault=='duplicate':events=[approval,{**approval,'approval_event_id':'approval-other'}]
    elif fault=='slot':approval['slot_id']='checker.2'
    elif fault=='checker':approval['actor_id']='synthetic-maker'
    elif fault=='binding':approval['action_binding_hash']='0'*64
    elif fault=='policy':approval['approval_policy_hash']='0'*64
    elif fault=='eligibility':approval['eligibility_snapshot_hash']='0'*64
    elif fault=='version':approval['proposal_version']=2
    else:approval['expires_at']=NOW
    install_route_budget_currentness(monkeypatch,f,request,order)
    monkeypatch.setattr(AipBudgetReservationStore,'reserve_in_transaction',lambda *args,**kwargs:
        (_ for _ in ()).throw(AssertionError('drift must fail before original budget Store')))
    guard=action.RouteEvalActionGuard(**route_guard_native_inputs(f),**route_guard_rule_inputs())
    with pytest.raises(AipActionTransitionBlocked):
        guard.reserve_current_call_budget(RouteBudgetConnection(stable,row,approval,events),
            f.scope,approval['approval_event_id'])


def test_route_action_guard_g4b1_preserves_original_budget_store_rejection(monkeypatch):
    from aos_api.aip_budget_reservation_store import AipBudgetReservationStore,BudgetReservationBlocked
    f,request,snapshot,risk,binding,stable,row,approval=route_guard_approved_fixture();order=[]
    install_route_budget_currentness(monkeypatch,f,request,order)
    monkeypatch.setattr(AipBudgetReservationStore,'reserve_in_transaction',lambda *args,**kwargs:
        (_ for _ in ()).throw(BudgetReservationBlocked('original budget drift')))
    guard=action.RouteEvalActionGuard(**route_guard_native_inputs(f),**route_guard_rule_inputs())
    with pytest.raises(BudgetReservationBlocked,match='original budget drift'):
        guard.reserve_current_call_budget(RouteBudgetConnection(stable,row,approval),
            f.scope,approval['approval_event_id'])


@pytest.mark.parametrize('fault',['operation','invocation','task','policy','price','approval','amount','currency'])
def test_route_action_guard_g4b1_rejects_mutated_budget_builder_output(monkeypatch,fault):
    from aos_api.aip_action_store import AipActionTransitionBlocked
    from aos_api.aip_budget_reservation_contracts import BudgetExactRef
    from aos_api.aip_budget_reservation_store import AipBudgetReservationStore
    f,request,snapshot,risk,binding,stable,row,approval=route_guard_approved_fixture();order=[]
    install_route_budget_currentness(monkeypatch,f,request,order)
    original=action.build_route_eval_call_budget_request
    def changed(*args,**kwargs):
        budget=original(*args,**kwargs)
        ref=BudgetExactRef(resourceType='Task',resourceId='other',revision=1,
            contentHash='sha256:'+'0'*64)
        if fault=='operation':return budget.model_copy(update={'operation_id':'other'})
        if fault=='invocation':return budget.model_copy(update={'invocation_key':'other'})
        if fault=='task':return budget.model_copy(update={'task_ref':ref})
        if fault=='policy':return budget.model_copy(update={'policy_ref':budget.policy_ref.model_copy(update={'resource_id':'other'})})
        if fault=='price':return budget.model_copy(update={'pricing_ref':budget.pricing_ref.model_copy(update={'resource_id':'other'})})
        if fault=='approval':return budget.model_copy(update={'approval_ref':budget.approval_ref.model_copy(update={'resource_id':'other'})})
        if fault=='amount':return budget.model_copy(update={'upper_bound_minor':budget.upper_bound_minor+1})
        return budget.model_copy(update={'currency':'USD'})
    monkeypatch.setattr(action,'build_route_eval_call_budget_request',changed)
    monkeypatch.setattr(AipBudgetReservationStore,'reserve_in_transaction',lambda *args,**kwargs:
        (_ for _ in ()).throw(AssertionError('mutated request must fail before original budget Store')))
    guard=action.RouteEvalActionGuard(**route_guard_native_inputs(f),**route_guard_rule_inputs())
    with pytest.raises(AipActionTransitionBlocked,match='ROUTE_EVAL_BUDGET_REQUEST_BINDING_REQUIRED'):
        guard.reserve_current_call_budget(RouteBudgetConnection(stable,row,approval),
            f.scope,approval['approval_event_id'])


# G6 current-subject composition only.  Native connection and original DAO
# properties are substituted; these cases are not SCRAM/PG evidence.
class CurrentSubjectConnection:
    def __init__(self,proof,manifest):
        from aos_api.aip_model_runtime_contracts import (
            ModelEvalCandidate,ModelRouteRevision,RegisteredModelRevision,
            RuntimePolicyRevision,
        )
        body=json.loads(manifest.split(b'\n',1)[1]);subject=body['context']['subject']
        self.proof=proof;self.manifest=manifest;self.body=body
        self.claim=ModelEvalCandidate.model_validate(subject['candidate'])
        self.route=ModelRouteRevision.model_validate(subject['source'])
        self.models={m.registered_model_id:m for m in (
            RegisteredModelRevision.model_validate(value) for value in subject['models'])}
        judge=RegisteredModelRevision.model_validate(body['routeApplication']['judgeModel'])
        self.models.setdefault(judge.registered_model_id,judge)
        self.policy=RuntimePolicyRevision.model_validate(subject['runtimePolicy'])
        self.context=dict(database='unit_only',database_oid=123,login='aos_model_route_eval',
            role='aos_runtime',org_id='org-org',project_id='dev-project',
            isolation='serializable',readonly='off',xid='345',pid=101,
            now=proof.finalized_at+timedelta(seconds=1))
        self.after=None;self.calls=[];self.missing_model=None

    def execute(self,sql,params=()):
        self.calls.append((sql,params))
        if 'current_database() AS database' in sql:
            return Rows(deepcopy(self.context if self.after is None or len([
                call for call,_ in self.calls if 'current_database() AS database' in call])==1 else self.after))
        if 'FROM public.aip_registered_model_head' in sql:
            identifier=params[-2];item=None if identifier==self.missing_model else self.models.get(identifier)
            if item is None:return Rows(None)
            return Rows(dict(version=7,asset_id=item.registered_model_id,revision=item.revision,
                content_hash=item.content_hash,lifecycle=item.lifecycle.value,
                payload=item.model_dump(mode='json',by_alias=True)))
        if 'FROM public.aip_runtime_policy_head' in sql:
            item=self.policy
            return Rows(dict(version=5,asset_id=item.policy_id,revision=item.revision,
                content_hash=item.content_hash,lifecycle=item.lifecycle.value,
                payload=item.model_dump(mode='json',by_alias=True)))
        raise AssertionError('unexpected G6 current-subject SQL: '+sql)

    def commit(self):raise AssertionError('G6 reader must retain caller transaction')
    rollback=commit
    close=commit


def current_subject_fixture(monkeypatch):
    from test_model_route_eval_finalization_proof import finalization_fixture
    from aos_api.aip_model_runtime_store import AipModelRuntimeStore
    proof,manifest,*_=finalization_fixture();conn=CurrentSubjectConnection(proof,manifest)
    monkeypatch.setattr(owner,'_require_native_connection',lambda value:None)
    def current(_store,value,scope,source_ref,target_ref,*,expected_head_version):
        assert value is conn and scope==TenantScope('org-org','dev-project')
        assert source_ref==conn.claim.source_ref and target_ref==conn.claim.target_ref
        assert expected_head_version==conn.claim.expected_head_version
        return conn.claim
    monkeypatch.setattr(AipModelRuntimeStore,'require_current_route_eval_candidate_for_update',current)
    return conn,proof,manifest


def test_g6_final_proof_locks_current_route_models_judge_and_policy_on_same_caller(monkeypatch):
    from aos_api.aip_model_route_eval_proof_reader import read_current_route_eval_subject
    conn,proof,manifest=current_subject_fixture(monkeypatch)
    result=read_current_route_eval_subject(conn,scope=TenantScope('org-org','dev-project'),
        proof=proof,manifest_bytes=manifest)
    assert result.execution_id==proof.execution_id and result.manifest_hash==proof.manifest_hash
    assert result.source_ref==conn.claim.source_ref and result.target_ref==conn.claim.target_ref
    assert result.expected_head_version==conn.claim.expected_head_version
    from aos_api.aip_agent_registry_contracts import VersionedAssetRef
    expected={item.model.asset_id:item.model for item in conn.route.candidates}
    for call in conn.body['routeApplication']['calls']:
        ref=VersionedAssetRef.model_validate(call['modelRef']);expected[ref.asset_id]=ref
    assert result.model_refs==tuple(sorted(expected.values(),key=lambda ref:ref.asset_id))
    assert result.runtime_policy_ref.asset_id==conn.policy.policy_id
    assert result.caller_xid=='345' and result.caller_pid==101
    assert result.execution_allowed is False
    assert all(sql.lstrip().startswith('SELECT ') for sql,_ in conn.calls)
    assert all('FOR SHARE' in sql for sql,_ in conn.calls
        if 'aip_registered_model_head' in sql or 'aip_runtime_policy_head' in sql)


@pytest.mark.parametrize('fault',['scope','proof_tenant','manifest','proof','current','model_missing','model_hash',
    'model_lifecycle','policy_hash','caller','xid_after','clock_backwards','expired'])
def test_g6_current_subject_drift_fails_closed_before_consumer_authority(monkeypatch,fault):
    from aos_api.aip_model_route_eval_proof_reader import (
        RouteEvalCurrentSubjectRejected,read_current_route_eval_subject,
    )
    from aos_api.aip_model_runtime_store import AipModelRuntimeStore
    conn,proof,manifest=current_subject_fixture(monkeypatch);scope=TenantScope('org-org','dev-project')
    if fault=='scope':scope=TenantScope('dev-org','dev-project')
    elif fault=='proof_tenant':proof=proof.model_copy(
        update={'tenant':proof.tenant.model_copy(update={'org_id':'dev-org'})})
    elif fault=='manifest':manifest+=b'\n'
    elif fault=='proof':proof=proof.model_copy(update={'context_binding_hash':'0'*64})
    elif fault=='current':
        monkeypatch.setattr(AipModelRuntimeStore,'require_current_route_eval_candidate_for_update',
            lambda *args,**kwargs:conn.claim.model_copy(update={'expected_head_version':8}))
    elif fault=='model_missing':conn.missing_model=next(iter(conn.models))
    elif fault=='model_hash':next(iter(conn.models.values())).__dict__['content_hash']='0'*64
    elif fault=='model_lifecycle':next(iter(conn.models.values())).__dict__['lifecycle']='revoked'
    elif fault=='policy_hash':conn.policy.__dict__['content_hash']='0'*64
    elif fault=='caller':conn.context['role']='other'
    elif fault=='xid_after':conn.after={**conn.context,'xid':'346'}
    elif fault=='clock_backwards':conn.after={**conn.context,'now':conn.context['now']-timedelta(seconds=2)}
    else:conn.after={**conn.context,'now':NOW+timedelta(hours=2)}
    with pytest.raises(RouteEvalCurrentSubjectRejected,match='current Route Eval subject required'):
        read_current_route_eval_subject(conn,scope=scope,proof=proof,manifest_bytes=manifest)


def test_g6_native_current_subject_reader_scram_rls_locks_and_drift_matrix():
    """Run only on an explicit disposable PostgreSQL session database."""
    import os
    import secrets
    from datetime import UTC,datetime

    import psycopg
    from psycopg import sql
    from psycopg.conninfo import conninfo_to_dict,make_conninfo
    from psycopg.rows import dict_row
    from psycopg.types.json import Jsonb

    from aos_api.aip_model_route_eval_finalization_proof import (
        canonical_route_eval_finalization_proof,
    )
    from aos_api.aip_model_route_eval_manifest import (
        CONTEXT_DOMAIN,RouteEvalApplication,_canonical,_parse_context,
    )
    from aos_api.aip_model_route_eval_proof_reader import (
        RouteEvalCurrentSubjectRejected,read_current_route_eval_subject,
    )
    from aos_api.aip_model_route_eval_signatures import _manifest
    from aos_api.aip_model_runtime_contracts import (
        RegisteredModelRevision,RuntimePolicyRevision,
    )
    import test_model_route_eval_context_reader as context_reader_fixture
    import test_model_route_eval_finalization_proof as finalization_fixture_module
    import test_model_route_eval_manifest as manifest_fixture
    import test_model_route_eval_signatures as signatures_fixture
    import test_model_route_eval_subject_binding as subject_fixture

    if os.getenv('AOS_ROUTE_EVAL_CURRENT_SUBJECT_NATIVE')!='1':
        pytest.skip('explicit disposable current-subject native window required')
    admin_dsn=os.getenv('AOS_DATABASE_URL')
    try:
        parts=conninfo_to_dict(admin_dsn or '')
        port=int(parts.get('port','0'));database=parts.get('dbname','')
        if (parts.get('host') not in {'127.0.0.1','localhost','::1'} or port<1024
            or port in {5432,5433} or not database.startswith('aos_test_')
            or not database.endswith('_ti4_test') or not parts.get('user')
            or not parts.get('password')):
            raise ValueError
    except (TypeError,ValueError):
        pytest.fail('native current-subject test requires explicit loopback random test database')

    fresh_now=datetime.now(UTC)-timedelta(minutes=1)
    with pytest.MonkeyPatch.context() as clock:
        for module in (subject_fixture,context_reader_fixture,manifest_fixture,
                       signatures_fixture,finalization_fixture_module):
            clock.setattr(module,'NOW',fresh_now)
        proof,manifest,*_=finalization_fixture_module.finalization_fixture()
    canonical_route_eval_finalization_proof(proof)
    body=_manifest(manifest)
    context,route,claim,_,_,context_models=_parse_context(
        CONTEXT_DOMAIN+_canonical(body['context']))
    app=RouteEvalApplication.model_validate(body['routeApplication'])
    policy=RuntimePolicyRevision.model_validate(context['subject']['runtimePolicy'])
    models={item.registered_model_id:item for item in context_models}
    models.setdefault(app.judge_model.registered_model_id,app.judge_model)

    login='aos_model_route_eval';password=secrets.token_urlsafe(32)
    with psycopg.connect(admin_dsn,autocommit=True,row_factory=dict_row) as admin:
        if admin.execute('SELECT 1 FROM pg_roles WHERE rolname=%s',(login,)).fetchone():
            pytest.fail('dedicated current-subject login already exists')
        admin.execute("SET password_encryption='scram-sha-256'")
        admin.execute(sql.SQL(
            'CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS '
            'NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD {}'
        ).format(sql.Identifier(login),sql.Literal(password)))
        admin.execute(sql.SQL('GRANT aos_runtime TO {}').format(sql.Identifier(login)))
    caller_dsn=make_conninfo(**{**parts,'user':login,'password':password,
        'require_auth':'scram-sha-256'})

    def insert_revision(conn,prefix,id_column,asset_id,item,*,version):
        conn.execute(sql.SQL(
            'INSERT INTO {}(org_id,project_id,{},current_revision,version) '
            'VALUES(%s,%s,%s,%s,%s)'
        ).format(sql.Identifier('aip_'+prefix+'_head'),sql.Identifier(id_column)),
            (*TenantScope('org-org','dev-project').key,asset_id,item.revision,version))
        conn.execute(sql.SQL(
            'INSERT INTO {}(org_id,project_id,{},revision,content_hash,lifecycle,'
            'payload,created_by,created_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)'
        ).format(sql.Identifier('aip_'+prefix+'_revision'),sql.Identifier(id_column)),
            (*TenantScope('org-org','dev-project').key,asset_id,item.revision,item.content_hash,
             item.lifecycle.value,Jsonb(item.model_dump(mode='json',by_alias=True)),
             'route-g6-native-r5',item.created_at))

    def set_context(conn,*,tenant=TenantScope('org-org','dev-project'),
                    role=True,isolation='SERIALIZABLE',readonly=False):
        conn.read_only=readonly
        conn.execute('SET TRANSACTION ISOLATION LEVEL '+isolation+
            (' READ ONLY' if readonly else ' READ WRITE'))
        if role:conn.execute('SET LOCAL ROLE aos_runtime')
        conn.execute("SELECT set_config('aos.org_id',%s,true),"
            "set_config('aos.project_id',%s,true)",tenant.key)

    def read_native(dsn=caller_dsn,**context_kwargs):
        with psycopg.connect(dsn,row_factory=dict_row) as conn:
            set_context(conn,**context_kwargs)
            value=read_current_route_eval_subject(conn,
                scope=TenantScope('org-org','dev-project'),proof=proof,
                manifest_bytes=manifest)
            conn.rollback()
            return value

    try:
        with psycopg.connect(admin_dsn,row_factory=dict_row) as admin:
            admin.execute("INSERT INTO twa_org(id,name) VALUES('org-org','route-g6-native') "
                'ON CONFLICT(id) DO NOTHING')
            admin.execute("INSERT INTO twa_workspace(org_id,project_id,name) "
                "VALUES('org-org','dev-project','route-g6-native') "
                'ON CONFLICT(org_id,project_id) DO NOTHING')
            insert_revision(admin,'runtime_policy','runtime_policy_id',policy.policy_id,
                policy,version=5)
            for item in models.values():
                assert type(item) is RegisteredModelRevision
                insert_revision(admin,'registered_model','registered_model_id',
                    item.registered_model_id,item,version=7)
            insert_revision(admin,'model_route','model_route_id',route.route_id,route,
                version=claim.expected_head_version)
            admin.commit()

        with psycopg.connect(caller_dsn,row_factory=dict_row) as caller:
            set_context(caller)
            verified=read_current_route_eval_subject(caller,
                scope=TenantScope('org-org','dev-project'),proof=proof,
                manifest_bytes=manifest)
            assert verified.execution_id==proof.execution_id
            assert verified.manifest_hash==proof.manifest_hash
            assert verified.source_ref==claim.source_ref
            assert verified.target_ref==claim.target_ref
            assert verified.expected_head_version==claim.expected_head_version
            assert [(ref.asset_id,ref.revision,ref.content_hash)
                    for ref in verified.model_refs]==sorted(
                (item.registered_model_id,item.revision,item.content_hash)
                for item in models.values())
            assert verified.runtime_policy_ref==route.runtime_policy_ref
            assert verified.execution_allowed is False
            assert caller.pgconn.used_password is True
            assert caller.info.get_parameters().get('require_auth')=='scram-sha-256'
            for table,id_column,asset_id in (
                ('aip_model_route_head','model_route_id',route.route_id),
                ('aip_registered_model_head','registered_model_id',next(iter(models))),
                ('aip_runtime_policy_head','runtime_policy_id',policy.policy_id),
            ):
                with psycopg.connect(admin_dsn,autocommit=True) as contender:
                    contender.execute("SET lock_timeout='150ms'")
                    with pytest.raises(psycopg.errors.LockNotAvailable):
                        contender.execute(sql.SQL(
                            'UPDATE {} SET version=version WHERE org_id=%s '
                            'AND project_id=%s AND {}=%s'
                        ).format(sql.Identifier(table),sql.Identifier(id_column)),
                            (*TenantScope('org-org','dev-project').key,asset_id))
            caller.rollback()

        with psycopg.connect(admin_dsn,autocommit=True) as admin:
            admin.execute("SET lock_timeout='150ms'")
            admin.execute("UPDATE aip_model_route_head SET version=version+1 "
                "WHERE org_id='org-org' AND project_id='dev-project' AND model_route_id=%s",
                (route.route_id,))
        with pytest.raises(RouteEvalCurrentSubjectRejected):read_native()
        with psycopg.connect(admin_dsn,autocommit=True) as admin:
            admin.execute("UPDATE aip_model_route_head SET version=version-1 "
                "WHERE org_id='org-org' AND project_id='dev-project' AND model_route_id=%s",
                (route.route_id,))

        model=next(iter(models.values()))
        with psycopg.connect(admin_dsn) as admin:
            admin.execute("INSERT INTO aip_registered_model_revision(org_id,project_id,"
                "registered_model_id,revision,content_hash,lifecycle,payload,created_by,created_at) "
                "VALUES('org-org','dev-project',%s,%s,%s,%s,%s,%s,%s)",
                (model.registered_model_id,model.revision+1,'0'*64,model.lifecycle.value,
                 Jsonb(model.model_dump(mode='json',by_alias=True)),'route-g6-native-r5',model.created_at))
            admin.execute("UPDATE aip_registered_model_head SET current_revision=%s "
                "WHERE org_id='org-org' AND project_id='dev-project' AND registered_model_id=%s",
                (model.revision+1,model.registered_model_id));admin.commit()
        with pytest.raises(RouteEvalCurrentSubjectRejected):read_native()
        with psycopg.connect(admin_dsn) as admin:
            admin.execute("UPDATE aip_registered_model_head SET current_revision=%s "
                "WHERE org_id='org-org' AND project_id='dev-project' AND registered_model_id=%s",
                (model.revision,model.registered_model_id));admin.commit()

        with psycopg.connect(admin_dsn) as admin:
            admin.execute("INSERT INTO aip_runtime_policy_revision(org_id,project_id,"
                "runtime_policy_id,revision,content_hash,lifecycle,payload,created_by,created_at) "
                "VALUES('org-org','dev-project',%s,%s,%s,%s,%s,%s,%s)",
                (policy.policy_id,policy.revision+1,'0'*64,policy.lifecycle.value,
                 Jsonb(policy.model_dump(mode='json',by_alias=True)),'route-g6-native-r5',policy.created_at))
            admin.execute("UPDATE aip_runtime_policy_head SET current_revision=%s "
                "WHERE org_id='org-org' AND project_id='dev-project' AND runtime_policy_id=%s",
                (policy.revision+1,policy.policy_id));admin.commit()
        with pytest.raises(RouteEvalCurrentSubjectRejected):read_native()
        with psycopg.connect(admin_dsn) as admin:
            admin.execute("UPDATE aip_runtime_policy_head SET current_revision=%s "
                "WHERE org_id='org-org' AND project_id='dev-project' AND runtime_policy_id=%s",
                (policy.revision,policy.policy_id));admin.commit()

        wrong_login=make_conninfo(**{**parts,'require_auth':'scram-sha-256'})
        for kwargs in (
            {'dsn':wrong_login},
            {'role':False},
            {'tenant':TenantScope('dev-org','dev-project')},
            {'isolation':'REPEATABLE READ'},
            {'readonly':True},
        ):
            dsn=kwargs.pop('dsn',caller_dsn)
            with pytest.raises(RouteEvalCurrentSubjectRejected):read_native(dsn,**kwargs)
    finally:
        with psycopg.connect(admin_dsn,autocommit=True) as admin:
            admin.execute('SELECT pg_terminate_backend(pid) FROM pg_stat_activity '
                'WHERE usename=%s AND pid<>pg_backend_pid()',(login,))
            admin.execute(sql.SQL('REVOKE aos_runtime FROM {}').format(sql.Identifier(login)))
            admin.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(login)))


def test_g6_route_release_consumer_composition_contract_is_exposed():
    from aos_api.aip_model_route_eval_proof_authority import (
        RouteEvalReleaseEvidence,
        VerifiedRouteEvalReleaseEvidence,
        verify_route_eval_release_evidence,
    )

    assert RouteEvalReleaseEvidence is not None
    assert VerifiedRouteEvalReleaseEvidence is not None
    assert callable(verify_route_eval_release_evidence)


def test_g6_route_release_consumers_require_explicit_typed_evidence_parameter():
    import inspect

    from aos_api.aip_eval_authority_store import AipEvalAuthorityStore
    from aos_api.aip_release_publication_service import AipReleasePublicationService

    assert inspect.signature(AipEvalAuthorityStore.require_exact_passed).parameters[
        'route_evidence'
    ].kind is inspect.Parameter.KEYWORD_ONLY
    assert inspect.signature(AipReleasePublicationService.derive_gate).parameters[
        'route_evidence'
    ].kind is inspect.Parameter.KEYWORD_ONLY
    assert inspect.signature(AipReleasePublicationService.publish).parameters[
        'route_evidence'
    ].kind is inspect.Parameter.KEYWORD_ONLY


class RouteReleaseCompositionConnection:
    def __init__(self):self.commits=0
    def commit(self):self.commits+=1;raise AssertionError('composition must not commit')
    rollback=commit
    close=commit


def route_release_composition_fixture(monkeypatch,fail=None):
    from types import SimpleNamespace
    from aos_api import aip_model_route_eval_owner as route_owner
    from aos_api import aip_model_route_eval_proof_authority as authority
    from aos_api import aip_model_route_eval_proof_reader as subject_reader
    from aos_api import aip_model_route_eval_publication_epoch as epoch_reader
    from aos_api import aip_model_route_eval_report_proof_reader as report_reader
    from aos_api.aip_provider_capacity_source_contracts import ProviderCapacityConsumptionCommand
    from test_model_route_eval_finalization_native_pg import _prepare_native_case

    case=_prepare_native_case();at=case.proof.finalized_at+timedelta(seconds=1)
    command=ProviderCapacityConsumptionCommand(schemaVersion=1,tenant=TENANT,
        bearerToken='a.b.c',sourceRef=dict(assetType='ProviderCapacitySourceRevision',
            assetId='route-release-source',revision=1,contentHash='a'*64))
    evidence=authority.RouteEvalReleaseEvidence(manifest_bytes=case.manifest,
        source_commands=(command,))
    order=[];context=dict(database='aos_test_route_release',database_oid=321,
        login='aos_model_route_eval',role='aos_runtime',org_id='org-org',
        project_id='dev-project',isolation='serializable',readonly='off',
        xid='42',pid=84,now=at)
    monkeypatch.setattr(authority,'_authority_boundary',lambda conn,scope:deepcopy(context))
    def stage(name,value):
        def run(*args,**kwargs):
            order.append(name)
            if fail==name:raise RuntimeError('synthetic '+name)
            return value
        return run
    monkeypatch.setattr(route_owner,'prepare_governed_eval_native_sources',
        stage('source',b'qualified-source-prefix'))
    report_proof=SimpleNamespace(proof=case.proof,report_id=case.report.report_id,
        report_hash=case.report.content_hash)
    monkeypatch.setattr(report_reader,'read_verified_route_eval_report_from_persistence',
        stage('report',report_proof))
    proof_authority=SimpleNamespace(execution_id=case.proof.execution_id,checked_at=at)
    monkeypatch.setattr(authority,'read_current_route_eval_proof_authority',
        stage('authority',proof_authority))
    current_ref=SimpleNamespace(asset_id=case.report.target.asset_id,
        revision=case.report.target.revision,content_hash=case.report.target.content_hash)
    source_ref=SimpleNamespace(asset_id=case.report.target.asset_id,
        revision=int(case.report.target.revision)-1,content_hash='b'*64)
    subject=SimpleNamespace(execution_id=case.proof.execution_id,
        manifest_hash=case.proof.manifest_hash,source_ref=source_ref,
        target_ref=current_ref,checked_at=at)
    monkeypatch.setattr(subject_reader,'read_current_route_eval_subject',
        stage('subject',subject))
    monkeypatch.setattr(epoch_reader,'lock_eval_publication_epoch',stage('epoch',7))
    return authority,case,evidence,RouteReleaseCompositionConnection(),order


def test_g6_route_release_composition_uses_one_fixed_lock_order_without_commit(monkeypatch):
    authority,case,evidence,conn,order=route_release_composition_fixture(monkeypatch)
    result=authority.verify_route_eval_release_evidence(conn,
        scope=TenantScope('org-org','dev-project'),report=case.report,evidence=evidence,
        publication_id='publication-route')
    assert order==['source','report','authority','subject','epoch']
    assert (result.execution_id,result.report_id,result.report_hash,result.manifest_hash)==(
        case.proof.execution_id,case.report.report_id,case.report.content_hash,
        case.proof.manifest_hash)
    assert result.source_count==1 and result.publication_epoch==7
    assert result.release_allowed is False and conn.commits==0


@pytest.mark.parametrize('stage',['source','report','authority','subject','epoch'])
def test_g6_route_release_composition_stops_at_first_failed_gate(monkeypatch,stage):
    authority,case,evidence,conn,order=route_release_composition_fixture(monkeypatch,stage)
    with pytest.raises(authority.RouteEvalReleaseEvidenceRejected,
        match='current Route release evidence required'):
        authority.verify_route_eval_release_evidence(conn,
            scope=TenantScope('org-org','dev-project'),report=case.report,
            evidence=evidence,publication_id='publication-route')
    expected=['source','report','authority','subject','epoch']
    assert order==expected[:expected.index(stage)+1]
    assert conn.commits==0


def test_g6_route_publish_inserts_before_epoch_and_commits_last(monkeypatch):
    from contextlib import contextmanager
    from types import SimpleNamespace

    from aos_api import aip_model_route_eval_publication_epoch as epoch_reader
    from aos_api.aip_eval_contracts import AssetType, ReleaseGateDecision
    from aos_api.aip_release_publication_models import PublishReleaseRequest
    from aos_api.aip_release_publication_service import AipReleasePublicationService
    from test_model_route_eval_finalization_native_pg import _prepare_native_case

    case = _prepare_native_case()
    evidence = route_release_composition_fixture(monkeypatch)[2]
    checked_at = case.proof.finalized_at + timedelta(seconds=1)
    gate = ReleaseGateDecision(
        tenant=TENANT,
        decisionId='route-gate',
        target=case.report.target,
        suiteRef=case.report.suite_ref,
        evalRunId=case.report.run_id,
        evalReport={
            'artifactId': case.report.report_id,
            'artifactType': 'eval_report',
            'revision': str(case.report.revision),
            'contentHash': case.report.content_hash,
        },
        status='passed',
        decisionHash='d' * 64,
        decidedBy='route-publisher',
        decidedAt=checked_at - timedelta(seconds=1),
        expiresAt=checked_at - timedelta(seconds=1) + timedelta(days=30),
    )
    order = []

    class Connection:
        def execute(self, query, params=None):
            assert query == 'SELECT clock_timestamp() AS now'
            return SimpleNamespace(fetchone=lambda: {'now': checked_at})

        def commit(self):
            order.append('commit')

    connection = Connection()

    @contextmanager
    def connect(scope):
        assert scope == TenantScope('org-org', 'dev-project')
        yield connection

    service = AipReleasePublicationService(connect)
    monkeypatch.setattr(service, '_event_row', lambda *args: None)
    monkeypatch.setattr(service, '_gate_row', lambda *args: {'synthetic': True})
    monkeypatch.setattr(service, '_gate_from_row', lambda *args: gate)
    monkeypatch.setattr(
        service,
        '_verify_gate_evidence',
        lambda *args, **kwargs: case.report,
    )
    monkeypatch.setattr(
        service,
        '_verify_route_release',
        lambda *args, **kwargs: order.append(
            'verify-epoch' if kwargs.get('publication_id') else 'verify-four'
        ),
    )
    monkeypatch.setattr(
        service,
        '_insert_event',
        lambda *args, **kwargs: order.append('insert'),
    )
    monkeypatch.setattr(
        epoch_reader,
        'lock_eval_publication_epoch',
        lambda *args, **kwargs: order.append('epoch'),
    )

    event = service.publish(
        TenantScope('org-org', 'dev-project'),
        actor='route-publisher',
        request=PublishReleaseRequest(
            releaseGateDecisionId=gate.decision_id,
            reasonHash='e' * 64,
            idempotencyKey='route-publish-once',
        ),
        expected_target_type=AssetType.MODEL_ROUTE,
        route_evidence=evidence,
    )

    assert event.target.asset_type is AssetType.MODEL_ROUTE
    assert order == ['verify-four', 'insert', 'epoch', 'commit']


def test_g6_route_gate_reader_requires_one_live_publication_and_all_five_gates(
    monkeypatch,
):
    from contextlib import contextmanager

    from aos_api.aip_agent_registry_contracts import VersionedAssetRef
    from aos_api.aip_eval_authority_store import AipEvalAuthorityStore
    from aos_api.aip_eval_contracts import ReleaseGateDecision
    from aos_api.aip_release_publication_service import AipReleasePublicationService
    from test_model_route_eval_finalization_native_pg import _prepare_native_case

    case = _prepare_native_case()
    evidence = route_release_composition_fixture(monkeypatch)[2]
    checked_at = case.proof.finalized_at + timedelta(seconds=1)
    gate = ReleaseGateDecision(
        tenant=TENANT,
        decisionId='route-gate-reader',
        target=case.report.target,
        suiteRef=case.report.suite_ref,
        evalRunId=case.report.run_id,
        evalReport={
            'artifactId': case.report.report_id,
            'artifactType': 'eval_report',
            'revision': str(case.report.revision),
            'contentHash': case.report.content_hash,
        },
        status='passed',
        decisionHash='f' * 64,
        decidedBy='route-reader',
        decidedAt=checked_at - timedelta(seconds=1),
        expiresAt=checked_at - timedelta(seconds=1) + timedelta(days=30),
    )
    gate_row = gate.model_dump()
    gate_row['target_ref'] = gate_row.pop('target')
    gate_row['suite_ref'] = gate_row.pop('suite_ref')
    gate_row['eval_report_ref'] = gate_row.pop('eval_report')
    calls = []

    class Result:
        def __init__(self, one=None, many=None):
            self.one = one
            self.many = many

        def fetchone(self):
            return self.one

        def fetchall(self):
            return self.many

    class Connection:
        def execute(self, query, params=None):
            if 'FROM aip_release_gate_decision' in query:
                return Result(one=gate_row)
            if 'FROM aip_publication_event p' in query:
                return Result(many=[{'publication_id': 'route-publication'}])
            if 'FROM aip_eval_report_revision' in query:
                return Result(one={'synthetic': True})
            raise AssertionError(query)

    @contextmanager
    def connect(scope):
        assert scope == TenantScope('org-org', 'dev-project')
        yield Connection()

    store = AipEvalAuthorityStore(connect)
    monkeypatch.setattr(
        AipReleasePublicationService,
        '_report_from_row',
        staticmethod(lambda *args: case.report),
    )

    def verify(conn, *, scope, report, evidence, publication_id=None):
        calls.append((scope, report, evidence, publication_id))

    monkeypatch.setattr(
        'aos_api.aip_model_route_eval_proof_authority.verify_route_eval_release_evidence',
        verify,
    )
    ref = VersionedAssetRef(
        assetType='EvalGateDecision',
        assetId=gate.decision_id,
        revision=1,
        contentHash=gate.decision_hash,
    )

    assert store.require_exact_passed(
        TenantScope('org-org', 'dev-project'),
        ref,
        now=checked_at,
        route_evidence=evidence,
    ) == gate
    assert calls == [
        (
            TenantScope('org-org', 'dev-project'),
            case.report,
            evidence,
            'route-publication',
        )
    ]


def test_g6_native_publish_missing_formal_source_rolls_back_without_event(
    monkeypatch,
):
    """A real PostgreSQL publisher must not leave a half-publication.

    This is the r9a negative slice only.  It deliberately leaves the formal
    Route Source bridge absent, so it does not claim the positive five-gate
    native matrix.
    """
    import os
    import secrets
    from contextlib import contextmanager
    from datetime import UTC, datetime

    import psycopg
    from psycopg import sql
    from psycopg.conninfo import conninfo_to_dict, make_conninfo
    from psycopg.rows import dict_row

    from aos_api.aip_eval_contracts import (
        ArtifactRef,
        AssetType,
        ReleaseGateDecision,
    )
    from aos_api.aip_model_route_eval_proof_authority import (
        RouteEvalReleaseEvidence,
    )
    from aos_api.aip_provider_capacity_source_contracts import (
        ProviderCapacityConsumptionCommand,
    )
    from aos_api.aip_release_publication_models import PublishReleaseRequest
    from aos_api.aip_release_publication_service import (
        AipReleaseGateRejected,
        AipReleasePublicationService,
        _canonical_hash,
    )
    from test_model_route_eval_finalization_native_pg import (
        _finish_native,
        _install_native_seams,
        _prepare_native_case,
        _seed_native_case,
    )

    if os.getenv('AOS_ROUTE_EVAL_RELEASE_CONSUMER_NATIVE') != '1':
        pytest.skip('explicit disposable Route release consumer native window required')

    admin_dsn = os.getenv('AOS_DATABASE_URL')
    parts = conninfo_to_dict(admin_dsn or '')
    database = parts.get('dbname', '')
    if (
        parts.get('host') not in {'127.0.0.1', 'localhost', '::1'}
        or int(parts.get('port', '0')) in {5432, 5433}
        or not database.startswith('aos_test_')
        or not database.endswith('_ti4_test')
        or not parts.get('user')
        or not parts.get('password')
    ):
        pytest.fail('native Route release test requires loopback random test database')
    writer_dsn = make_conninfo(**{**parts, 'require_auth': 'scram-sha-256'})
    case = _prepare_native_case()
    _seed_native_case(admin_dsn, case)
    _install_native_seams(monkeypatch, case)
    assert _finish_native(writer_dsn, database, case) == case.proof

    scope = TenantScope('org-org', 'dev-project')
    decided_at = datetime.now(UTC)
    expires_at = decided_at + timedelta(days=30)
    report_ref = ArtifactRef(
        artifactId=case.report.report_id,
        artifactType=AssetType.EVAL_REPORT.value,
        revision=str(case.report.revision),
        contentHash=case.report.content_hash,
    )
    decision_hash = _canonical_hash({
        'target': case.report.target,
        'suiteRef': case.report.suite_ref,
        'evalRunId': case.report.run_id,
        'evalReport': report_ref,
        'status': 'passed',
        'expiresAt': expires_at,
    })
    gate = ReleaseGateDecision(
        tenant=TENANT,
        decisionId='route-native-r9a-gate',
        target=case.report.target,
        suiteRef=case.report.suite_ref,
        evalRunId=case.report.run_id,
        evalReport=report_ref,
        status='passed',
        decisionHash=decision_hash,
        decidedBy='route-native-r9a',
        decidedAt=decided_at,
        expiresAt=expires_at,
    )

    body = json.loads(case.manifest.split(b'\n', 1)[1])
    refs = {}
    for item in body['routeApplication']['calls']:
        ref = item['sourceRef']
        refs.setdefault(ref['assetId'], ref)
    evidence = RouteEvalReleaseEvidence(
        manifest_bytes=case.manifest,
        source_commands=tuple(
            ProviderCapacityConsumptionCommand(
                schemaVersion=1,
                tenant=TENANT,
                bearerToken='synthetic.test.token',
                sourceRef=refs[key],
            )
            for key in sorted(refs)
        ),
    )

    login = 'aos_model_route_eval'
    password = secrets.token_urlsafe(32)
    with psycopg.connect(admin_dsn, autocommit=True, row_factory=dict_row) as admin:
        if admin.execute(
            'SELECT 1 FROM pg_roles WHERE rolname=%s', (login,)
        ).fetchone() is not None:
            pytest.fail('dedicated Route release login already exists')
        assert admin.execute(
            "SELECT to_regprocedure("
            "'public.read_capacity_source_for_model_route_eval(bytea,jsonb)') AS fn"
        ).fetchone()['fn'] is None
        admin.execute("SET password_encryption='scram-sha-256'")
        admin.execute(sql.SQL(
            'CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS '
            'NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD {}'
        ).format(sql.Identifier(login), sql.Literal(password)))
        admin.execute(sql.SQL('GRANT aos_runtime TO {}').format(sql.Identifier(login)))

    caller_dsn = make_conninfo(
        **{**parts, 'user': login, 'password': password,
           'require_auth': 'scram-sha-256'}
    )

    @contextmanager
    def connect(requested_scope):
        assert requested_scope == scope
        with psycopg.connect(caller_dsn, row_factory=dict_row) as conn:
            conn.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ WRITE')
            conn.execute("SET LOCAL TimeZone='UTC'")
            conn.execute('SET LOCAL ROLE aos_runtime')
            conn.execute(
                "SELECT set_config('aos.org_id',%s,true),"
                "set_config('aos.project_id',%s,true)",
                scope.key,
            )
            yield conn

    try:
        with psycopg.connect(admin_dsn, row_factory=dict_row) as admin:
            AipReleasePublicationService._insert_gate(admin, scope, gate)
            admin.commit()
        with psycopg.connect(admin_dsn, row_factory=dict_row) as admin:
            before = admin.execute(
                'SELECT count(*) AS n FROM aip_publication_event '
                'WHERE org_id=%s AND project_id=%s',
                scope.key,
            ).fetchone()['n']

        service = AipReleasePublicationService(connect)
        with pytest.raises(
            AipReleaseGateRejected,
            match='current Route release evidence is unavailable',
        ):
            service.publish(
                scope,
                actor='route-native-r9a',
                request=PublishReleaseRequest(
                    releaseGateDecisionId=gate.decision_id,
                    reasonHash='9' * 64,
                    idempotencyKey='route-native-r9a-publish',
                ),
                expected_target_type=AssetType.MODEL_ROUTE,
                route_evidence=evidence,
            )

        with psycopg.connect(admin_dsn, row_factory=dict_row) as admin:
            assert admin.execute(
                'SELECT count(*) AS n FROM aip_publication_event '
                'WHERE org_id=%s AND project_id=%s',
                scope.key,
            ).fetchone()['n'] == before
            assert admin.execute(
                'SELECT count(*) AS n FROM aip_release_gate_decision '
                'WHERE org_id=%s AND project_id=%s AND decision_id=%s',
                (*scope.key, gate.decision_id),
            ).fetchone()['n'] == 1
            assert admin.execute(
                'SELECT count(*) AS n FROM aip_route_eval_finalization_proof '
                'WHERE org_id=%s AND project_id=%s AND execution_id=%s',
                (*scope.key, case.proof.execution_id),
            ).fetchone()['n'] == 1
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            admin.execute(
                'SELECT pg_terminate_backend(pid) FROM pg_stat_activity '
                'WHERE usename=%s AND pid<>pg_backend_pid()',
                (login,),
            )
            admin.execute(sql.SQL('REVOKE aos_runtime FROM {}').format(sql.Identifier(login)))
            admin.execute(sql.SQL('DROP ROLE IF EXISTS {}').format(sql.Identifier(login)))


@pytest.mark.skipif(
    os.getenv('AOS_ROUTE_EVAL_RELEASE_CONSUMER_NATIVE') != '1',
    reason='explicit disposable Route release consumer native window required',
)
@pytest.mark.parametrize('native_original_fact_reader', ['shared'], indirect=True)
def test_g6_native_publish_with_exact_formal_source_is_atomic(
    monkeypatch,
    request,
    route_release_native_owned_database_mode,
    exact_public_source_caller,
    https_signer,
):
    """One newly signed Source must bind the manifest and the publication.

    This r9b slice closes the positive Source-to-publication composition on one
    disposable PostgreSQL database.  It intentionally leaves replay, revoke,
    competition and injected late rollback to the following r9c matrix.
    """
    import base64
    import hashlib
    import secrets
    import threading
    import time
    from contextlib import contextmanager
    from datetime import UTC, datetime
    from uuid import uuid4

    import psycopg
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from pydantic import SecretStr
    from psycopg import sql
    from psycopg.conninfo import conninfo_to_dict, make_conninfo
    from psycopg.rows import dict_row
    from psycopg.types.json import Jsonb

    from aos_api import aip_model_route_eval_proof_authority as authority
    from aos_api import aip_model_route_eval_publication_epoch as publication_epoch
    from aos_api import aip_model_route_eval_source_bridge as source_bridge
    from aos_api.aip_route_release_request_context import RouteReleaseRequestContext
    from aos_api.auth import Principal
    from aos_api import aip_provider_capacity_catalog_audit_profile as catalog_profile
    from aos_api import aip_provider_capacity_occupation_epoch_profile as occupation_epoch
    from aos_api.aip_agent_registry_contracts import VersionedAssetRef
    from aos_api.aip_eval_contracts import (
        ArtifactRef,
        AssetType,
        EvalSuiteRevision,
        ReleaseGateDecision,
    )
    from aos_api.aip_eval_pack_registry import compute_eval_suite_hash
    from aos_api.aip_binding_formal_evaluator_contracts import FormalExactRef
    from aos_api.aip_model_route_eval_finalization_proof import (
        canonical_route_eval_finalization_proof,
    )
    from aos_api.aip_model_route_eval_manifest import (
        CONTEXT_DOMAIN,
        RouteEvalApplication,
        _canonical,
        _parse_context,
    )
    from aos_api.aip_model_route_eval_signatures import _manifest
    from aos_api.aip_model_runtime_contracts import RegisteredModelRevision, RuntimePolicyRevision
    from aos_api.aip_provider_capacity_publication_contracts import (
        PublishedProviderCapacitySourceV2,
        parse_signed_capacity_body,
    )
    from aos_api.aip_provider_capacity_source_contracts import (
        ProviderCapacityConsumptionCommand,
    )
    from aos_api.aip_eval_authority_store import (
        AipEvalAuthorityStore,
        AipEvalGateDependencyBlocked,
    )
    from aos_api.aip_release_publication_models import (
        DeriveReleaseGateRequest,
        PublishReleaseRequest,
        RevokePublicationRequest,
    )
    from aos_api.aip_release_publication_service import (
        AipReleaseGateRejected,
        AipReleasePublicationPersistenceError,
        AipReleasePublicationService,
    )
    from aos_api.routers.aip_release_publications import (
        get_aip_release_publication_service,
        router as release_publication_router,
    )
    from test_model_route_eval_finalization_native_pg import (
        _finish_native,
        _install_native_seams,
        _prepare_native_case,
        _seed_native_case,
    )
    from test_capacity_source_publication_transaction_pg import (
        _refresh_native_facts_transaction,
    )
    import test_model_route_eval_atomic_finalizer as atomic_fixture
    import test_model_route_eval_context_reader as context_reader_fixture
    import test_model_route_eval_finalization_proof as finalization_fixture_module
    import test_model_route_eval_manifest as manifest_fixture
    import test_model_route_eval_signatures as signatures_fixture
    import test_model_route_eval_subject_binding as subject_fixture

    admin_dsn = os.getenv('AOS_DATABASE_URL')
    parts = conninfo_to_dict(admin_dsn or '')
    database = parts.get('dbname', '')
    if (
        parts.get('host') not in {'127.0.0.1', 'localhost', '::1'}
        or int(parts.get('port', '0')) in {5432, 5433}
        or not database.startswith('aos_test_')
        or not database.endswith('_ti4_test')
        or not parts.get('user')
        or not parts.get('password')
    ):
        pytest.fail('native Route release test requires loopback random test database')

    issuer, packet, source_material, original_source = exact_public_source_caller
    issuer.rollback()
    with psycopg.connect(admin_dsn, autocommit=True, row_factory=dict_row) as admin:
        original_fact_body = admin.execute(
            'SELECT prosrc FROM pg_proc WHERE oid=to_regprocedure(%s)',
            (catalog_profile.FACT,),
        ).fetchone()['prosrc']
        for statement in catalog_profile.catalog_public_statements(
            include_consumer=True
        ):
            admin.execute(statement)
        with admin.transaction():
            admin.execute('SET LOCAL ROLE aos_capacity_publication_owner')
            admin.execute('SELECT ' + occupation_epoch.INSTALLATION)
        assert catalog_profile.catalog_profile_is_installed(admin) is True

    def restore_catalog_profile():
        with psycopg.connect(admin_dsn, autocommit=True, row_factory=dict_row) as admin:
            admin.execute(
                'DROP FUNCTION IF EXISTS '
                'public.read_current_capacity_source(bytea,jsonb)'
            )
            for statement in occupation_epoch.legacy_public_source_restoration_statements():
                admin.execute(statement)
            admin.execute(occupation_epoch._definition(
                catalog_profile.FACT, original_fact_body
            ))
            assert catalog_profile.catalog_profile_is_installed(admin) is False

    request.addfinalizer(restore_catalog_profile)
    _refresh_native_facts_transaction(issuer)
    issuance, _, _ = source_material['actual_command']()
    source_asset_id = 'route-release-source-' + uuid4().hex
    pending = issuer.execute(
        'SELECT * FROM public.prepare_capacity_source(%s,%s,%s,%s::jsonb)',
        (packet, issuance.idempotency_key, source_asset_id,
         Jsonb(source_material['refs'][-1])),
    ).fetchone()
    source_raw = bytes(pending['source_raw'])
    source_signature = source_material['source_key'].sign(source_raw)
    committed = issuer.execute(
        'SELECT * FROM public.commit_capacity_source(%s,%s,%s)',
        (issuance.idempotency_key, source_raw, source_signature),
    ).fetchone()
    issuer.commit()
    source = parse_signed_capacity_body(source_raw, PublishedProviderCapacitySourceV2)
    source_ref = VersionedAssetRef(
        assetType='ProviderCapacitySourceRevision',
        assetId=source_asset_id,
        revision=committed['revision'],
        contentHash=committed['content_hash'],
    )
    assert source.asset_id == source_asset_id
    assert source_ref.content_hash == hashlib.sha256(source_raw).hexdigest()
    assert source.execution_allowed is False

    exact_provider = VersionedAssetRef.model_validate(
        source.provider_refs[0].model_dump(mode='python', by_alias=True)
    )
    exact_account = VersionedAssetRef.model_validate(
        source.account_candidate_ref.model_dump(mode='python', by_alias=True)
    )
    original_context_inputs = context_reader_fixture.inputs
    original_outside_model = manifest_fixture.model

    def inputs_with_formal_provider(*args, **kwargs):
        route, models, policy = original_context_inputs(*args, **kwargs)
        models = [
            subject_fixture.seal(item.model_copy(update={'provider': exact_provider}))
            for item in models
        ]
        models_by_id = {item.registered_model_id: item for item in models}
        candidates = [
            candidate.model_copy(update={
                'model': subject_fixture.exact_ref(
                    models_by_id[candidate.model.asset_id],
                    'RegisteredModelRevision',
                    candidate.model.asset_id,
                )
            })
            for candidate in route.candidates
        ]
        route = subject_fixture.seal(route.model_copy(update={'candidates': candidates}))
        return route, models, policy

    def outside_model_with_formal_provider(*args, **kwargs):
        return subject_fixture.seal(
            original_outside_model(*args, **kwargs).model_copy(
                update={'provider': exact_provider}
            )
        )

    original_route_inputs = signatures_fixture.route_inputs

    def route_inputs_with_formal_source(*args, **kwargs):
        raw, application, bindings = original_route_inputs(*args, **kwargs)
        calls = [
            item.model_copy(update={
                'source_ref': source_ref,
                'physical_account_ref': exact_account,
            })
            for item in application.calls
        ]
        return raw, application.model_copy(update={'calls': calls}), bindings

    fresh_now = datetime.now(UTC) - timedelta(minutes=1)
    for module in (
        subject_fixture,
        context_reader_fixture,
        manifest_fixture,
        signatures_fixture,
        finalization_fixture_module,
        atomic_fixture,
    ):
        monkeypatch.setattr(module, 'NOW', fresh_now)
    monkeypatch.setattr(context_reader_fixture, 'inputs', inputs_with_formal_provider)
    monkeypatch.setattr(manifest_fixture, 'model', outside_model_with_formal_provider)
    monkeypatch.setattr(signatures_fixture, 'route_inputs', route_inputs_with_formal_source)
    case = _prepare_native_case()
    canonical_route_eval_finalization_proof(case.proof)
    manifest_body = _manifest(case.manifest)
    manifest_source_refs = {
        tuple(sorted(item['sourceRef'].items()))
        for item in manifest_body['routeApplication']['calls']
    }
    assert manifest_source_refs == {tuple(sorted(source_ref.model_dump(
        mode='json', by_alias=True).items()))}

    _seed_native_case(admin_dsn, case)
    _install_native_seams(monkeypatch, case)
    writer_dsn = make_conninfo(**{**parts, 'require_auth': 'scram-sha-256'})
    assert _finish_native(writer_dsn, database, case) == case.proof

    scope = TenantScope('org-org', 'dev-project')
    context, route, claim, _, suite, context_models = _parse_context(
        CONTEXT_DOMAIN + _canonical(manifest_body['context'])
    )
    application = RouteEvalApplication.model_validate(manifest_body['routeApplication'])
    assert type(suite) is EvalSuiteRevision
    assert compute_eval_suite_hash(suite) == suite.content_hash
    assert suite.content_hash == case.run.suite_ref.content_hash
    policy = RuntimePolicyRevision.model_validate(context['subject']['runtimePolicy'])
    models = {item.registered_model_id: item for item in context_models}
    models.setdefault(application.judge_model.registered_model_id, application.judge_model)
    assert all(type(item) is RegisteredModelRevision for item in models.values())

    login = 'aos_model_route_eval'
    password = secrets.token_urlsafe(32)
    bridge_installed = proof_authority_installed = login_created = False

    def canonical(value):
        return json.dumps(
            value.model_dump(mode='json', by_alias=True),
            sort_keys=True,
            separators=(',', ':'),
            ensure_ascii=False,
            allow_nan=False,
        ).encode()

    def insert_revision(conn, prefix, id_column, asset_id, item, *, version):
        conn.execute(sql.SQL(
            'INSERT INTO {}(org_id,project_id,{},current_revision,version) '
            'VALUES(%s,%s,%s,%s,%s)'
        ).format(sql.Identifier('aip_' + prefix + '_head'), sql.Identifier(id_column)),
            (*scope.key, asset_id, item.revision, version))
        conn.execute(sql.SQL(
            'INSERT INTO {}(org_id,project_id,{},revision,content_hash,lifecycle,'
            'payload,created_by,created_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)'
        ).format(sql.Identifier('aip_' + prefix + '_revision'), sql.Identifier(id_column)),
            (*scope.key, asset_id, item.revision, item.content_hash,
             item.lifecycle.value, Jsonb(item.model_dump(mode='json', by_alias=True)),
             'route-g6-native-r9b', item.created_at))

    try:
        with psycopg.connect(admin_dsn, autocommit=True, row_factory=dict_row) as admin:
            if admin.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', (login,)).fetchone():
                pytest.fail('dedicated Route release login already exists')
            for statement in source_bridge.source_bridge_statements():
                admin.execute(statement)
            bridge_installed = True
            authority.install_closed_route_eval_proof_authority(admin.execute)
            proof_authority_installed = True
            admin.execute("SET password_encryption='scram-sha-256'")
            admin.execute(sql.SQL(
                'CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS '
                'NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD {}'
            ).format(sql.Identifier(login), sql.Literal(password)))
            admin.execute(sql.SQL('GRANT aos_runtime TO {}').format(sql.Identifier(login)))
            login_created = True

        with psycopg.connect(admin_dsn, row_factory=dict_row) as writer:
            writer.execute('SET LOCAL ROLE ' + authority.ISSUER_OWNER)
            writer.execute(
                "SELECT set_config('aos.org_id',%s,true),"
                "set_config('aos.project_id',%s,true)", scope.key,
            )
            roots = {}
            for item in case.proof.calls:
                root = item.issuer_input
                roots.setdefault(
                    (root.issuer_id, root.issuer_key_id),
                    (root, item.issuer_input_hash),
                )
            for (issuer_id, key_id), (root, digest) in roots.items():
                writer.execute(f'''INSERT INTO {authority.ISSUER_SCHEMA}.issuer_root(
                    org_id,project_id,issuer_id,issuer_key_id,input_hash,public_key_hash,
                    body,valid_from,valid_until) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                    (*scope.key, issuer_id, key_id, digest,
                     hashlib.sha256(base64.b64decode(root.public_key_base64)).hexdigest(),
                     canonical(root), root.valid_from, root.valid_until))
            for item in case.proof.calls:
                cert = item.signed_certificate.certificate
                writer.execute(f'''INSERT INTO {authority.ISSUER_SCHEMA}.executor_certificate(
                    org_id,project_id,execution_id,case_id,purpose,identity_id,identity_key_hash,
                    issuer_id,issuer_key_id,manifest_hash,certificate_hash,body,valid_from,valid_until)
                    VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                    (*scope.key, cert.execution_id, cert.case_id, cert.purpose,
                     cert.identity_id, cert.identity_key_hash, cert.issuer_id,
                     cert.issuer_key_id, cert.manifest_hash, item.certificate_hash,
                     canonical(item.signed_certificate), cert.valid_from, cert.valid_until))
            writer.commit()

        with psycopg.connect(admin_dsn, row_factory=dict_row) as admin:
            admin.execute(
                "INSERT INTO twa_org(id,name) VALUES('org-org','route-g6-native-r9b') "
                'ON CONFLICT(id) DO NOTHING'
            )
            admin.execute(
                "INSERT INTO twa_workspace(org_id,project_id,name) "
                "VALUES('org-org','dev-project','route-g6-native-r9b') "
                'ON CONFLICT(org_id,project_id) DO NOTHING'
            )
            admin.execute(
                """INSERT INTO aip_eval_suite_revision(
                   org_id,project_id,suite_id,revision,content_hash,target_ref,
                   dataset_ref,judge_ref,cases,gate_threshold,actor)
                   VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (*scope.key, suite.suite_id, suite.revision, suite.content_hash,
                 Jsonb(suite.target.model_dump(mode='json', by_alias=True)),
                 Jsonb(suite.dataset.model_dump(mode='json', by_alias=True)),
                 Jsonb(suite.judge.model_dump(mode='json', by_alias=True)),
                 Jsonb([item.model_dump(mode='json', by_alias=True)
                        for item in suite.cases]),
                 suite.gate_threshold, 'route-native-r10h'),
            )
            insert_revision(admin, 'runtime_policy', 'runtime_policy_id',
                policy.policy_id, policy, version=5)
            for item in models.values():
                insert_revision(admin, 'registered_model', 'registered_model_id',
                    item.registered_model_id, item, version=7)
            insert_revision(admin, 'model_route', 'model_route_id', route.route_id,
                route, version=claim.expected_head_version)
            admin.commit()

        with psycopg.connect(admin_dsn, row_factory=dict_row) as admin:
            owner_rows = admin.execute(
                "SELECT subject FROM meta_membership WHERE org_id=%s AND project_id=%s "
                "AND lower(role)='owner' AND subject<>%s ORDER BY subject",
                (*scope.key, original_source[0]['maker']),
            ).fetchall()
            assert owner_rows
            consumer_subject = owner_rows[0]['subject']
            admin.commit()

        sign, _ = https_signer
        bearer_token = sign(consumer_subject)
        command = ProviderCapacityConsumptionCommand(
            schemaVersion=1,
            tenant=TENANT,
            bearerToken=bearer_token,
            sourceRef=FormalExactRef.model_validate(
                source_ref.model_dump(mode='python', by_alias=True)
            ),
        )
        evidence = authority.RouteEvalReleaseEvidence(
            manifest_bytes=case.manifest,
            source_commands=(command,),
        )
        route_request_context = RouteReleaseRequestContext(
            principal=Principal(subject=consumer_subject, org_id='org-org',
                project_id='dev-project', token_kind='oidc'),
            bearer_token=SecretStr(bearer_token),
        )
        caller_dsn = make_conninfo(
            **{**parts, 'user': login, 'password': password,
               'require_auth': 'scram-sha-256'}
        )

        @contextmanager
        def connect(requested_scope, **_kwargs):
            assert requested_scope == scope
            with psycopg.connect(caller_dsn, row_factory=dict_row) as conn:
                conn.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ WRITE')
                conn.execute("SET LOCAL TimeZone='UTC'")
                conn.execute('SET LOCAL ROLE aos_runtime')
                conn.execute(
                    "SELECT set_config('aos.org_id',%s,true),"
                    "set_config('aos.project_id',%s,true)", scope.key,
                )
                yield conn

        service = AipReleasePublicationService(connect)
        verify_calls = []
        real_verify = authority.verify_route_eval_release_evidence

        def counted_verify(*args, **kwargs):
            result = real_verify(*args, **kwargs)
            verify_calls.append(result)
            return result

        monkeypatch.setattr(
            authority, 'verify_route_eval_release_evidence', counted_verify
        )
        derive_request = DeriveReleaseGateRequest(
            reportId=case.report.report_id,
            reportRevision=case.report.revision,
            reportHash=case.report.content_hash,
            idempotencyKey='route-native-r10h-derived-gate',
        )
        gate = service.derive_gate(
            scope,
            actor=consumer_subject,
            request=derive_request,
            route_request_context=route_request_context,
        )
        assert gate.status.value == 'passed'
        assert gate.target == case.report.target
        assert gate.eval_report.artifact_id == case.report.report_id
        assert gate.eval_report.content_hash == case.report.content_hash
        assert len(verify_calls) == 1
        replayed_gate = service.derive_gate(
            scope,
            actor=consumer_subject,
            request=derive_request,
            route_request_context=route_request_context,
        )
        assert replayed_gate == gate
        assert len(verify_calls) == 2
        with psycopg.connect(admin_dsn, row_factory=dict_row) as admin:
            assert admin.execute(
                'SELECT count(*) AS n FROM aip_release_gate_decision '
                'WHERE org_id=%s AND project_id=%s AND decision_id=%s',
                (*scope.key, gate.decision_id),
            ).fetchone() == {'n': 1}

        publish_request = PublishReleaseRequest(
            releaseGateDecisionId=gate.decision_id,
            reasonHash='8' * 64,
            idempotencyKey='route-native-r9b-publish',
        )
        event = service.publish(
            scope,
            actor=consumer_subject,
            request=publish_request,
            expected_target_type=AssetType.MODEL_ROUTE,
            route_request_context=route_request_context,
        )
        assert event.target == case.report.target
        assert event.event_type.value == 'published'
        assert len(verify_calls) == 3

        http_app = FastAPI()
        http_app.include_router(release_publication_router)
        http_app.dependency_overrides[
            get_aip_release_publication_service
        ] = lambda: service
        http_headers = {
            'Authorization': 'Bearer ' + bearer_token,
            'X-Org-Id': scope.org_id,
            'X-Project-Id': scope.project_id,
        }
        with TestClient(http_app) as http_client:
            http_gate = http_client.post(
                '/v1/aip/release-gates/derive',
                headers=http_headers,
                json=derive_request.model_dump(mode='json', by_alias=True),
            )
            assert http_gate.status_code == 201
            assert http_gate.json()['decisionId'] == gate.decision_id
            assert len(verify_calls) == 4
            http_publication = http_client.post(
                '/v1/aip/publications/logic',
                headers=http_headers,
                json=publish_request.model_dump(mode='json', by_alias=True),
            )
            assert http_publication.status_code == 201
            assert http_publication.json()['eventId'] == event.event_id
            assert len(verify_calls) == 5
            response_text = http_gate.text + http_publication.text
            assert bearer_token not in response_text
            assert 'manifestBytes' not in response_text
            assert 'routeEvidence' not in response_text

        with psycopg.connect(admin_dsn, row_factory=dict_row) as admin:
            rows = admin.execute(
                'SELECT event_id,publication_id,event_type FROM aip_publication_event '
                'WHERE org_id=%s AND project_id=%s AND publication_id=%s',
                (*scope.key, event.publication_id),
            ).fetchall()
            assert len(rows) == 1 and rows[0]['event_type'] == 'published'
            persisted = admin.execute(
                'SELECT content_hash,source_raw,signature FROM '
                'aos_capacity_publication_private.source_publication '
                'WHERE org_id=%s AND project_id=%s AND asset_id=%s',
                (*scope.key, source_asset_id),
            ).fetchone()
            assert persisted['content_hash'] == source_ref.content_hash
            assert bytes(persisted['source_raw']) == source_raw
            assert bytes(persisted['signature']) == source_signature

        # N2: an identical request returns the same publication, but still
        # traverses the complete current Route evidence verifier.
        replay = service.publish(
            scope,
            actor=consumer_subject,
            request=publish_request,
            expected_target_type=AssetType.MODEL_ROUTE,
            route_request_context=route_request_context,
        )
        assert replay == event
        assert len(verify_calls) == 6

        gate_ref = VersionedAssetRef(
            assetType='EvalGateDecision',
            assetId=gate.decision_id,
            revision=1,
            contentHash=gate.decision_hash,
        )
        target_ref = VersionedAssetRef(
            assetType='ModelRouteRevision',
            assetId=gate.target.asset_id,
            revision=int(gate.target.revision),
            contentHash=gate.target.content_hash,
        )
        current_gate = AipEvalAuthorityStore(connect).require_exact_passed(
            scope,
            gate_ref,
            expected_target=target_ref,
            route_evidence=evidence,
        )
        assert current_gate == gate
        assert len(verify_calls) == 7
        with psycopg.connect(admin_dsn, row_factory=dict_row) as admin:
            replay_rows = admin.execute(
                'SELECT event_type FROM aip_publication_event '
                'WHERE org_id=%s AND project_id=%s AND publication_id=%s',
                (*scope.key, event.publication_id),
            ).fetchall()
            replay_epoch = admin.execute(
                'SELECT epoch FROM aip_publication_epoch '
                'WHERE org_id=%s AND project_id=%s AND publication_id=%s',
                (*scope.key, event.publication_id),
            ).fetchone()
            assert replay_rows == [{'event_type': 'published'}]
            assert replay_epoch == {'epoch': 1}

        # N4 + N3: hold the real epoch row with one native connection.  The
        # independent revocation must enter a PostgreSQL Lock wait, and only
        # completes after the holder releases it.
        contender_dsn = make_conninfo(
            caller_dsn, application_name='aos-r9c-revoke-contender'
        )

        @contextmanager
        def contender_connect(requested_scope, **_kwargs):
            assert requested_scope == scope
            with psycopg.connect(contender_dsn, row_factory=dict_row) as conn:
                conn.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ WRITE')
                conn.execute("SET LOCAL TimeZone='UTC'")
                conn.execute('SET LOCAL ROLE aos_runtime')
                conn.execute(
                    "SELECT set_config('aos.org_id',%s,true),"
                    "set_config('aos.project_id',%s,true)", scope.key,
                )
                yield conn

        revoke_result = {}

        def revoke_in_contender():
            try:
                revoke_result['event'] = AipReleasePublicationService(
                    contender_connect
                ).revoke(
                    scope,
                    publication_id=event.publication_id,
                    actor='route-native-r9c',
                    request=RevokePublicationRequest(
                        reasonHash='7' * 64,
                        idempotencyKey='route-native-r9c-revoke',
                    ),
                )
            except BaseException as exc:  # captured for the main test thread
                revoke_result['error'] = exc

        with psycopg.connect(caller_dsn, row_factory=dict_row) as holder:
            holder.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ WRITE')
            holder.execute("SET LOCAL TimeZone='UTC'")
            holder.execute('SET LOCAL ROLE aos_runtime')
            holder.execute(
                "SELECT set_config('aos.org_id',%s,true),"
                "set_config('aos.project_id',%s,true)", scope.key,
            )
            assert publication_epoch.lock_eval_publication_epoch(
                holder, scope, event.publication_id
            ) == 1
            contender = threading.Thread(target=revoke_in_contender, daemon=True)
            contender.start()
            deadline = time.monotonic() + 10
            waited_on_lock = False
            while time.monotonic() < deadline:
                with psycopg.connect(admin_dsn, row_factory=dict_row) as admin:
                    activity = admin.execute(
                        "SELECT wait_event_type FROM pg_stat_activity "
                        "WHERE application_name='aos-r9c-revoke-contender' "
                        "AND state='active'"
                    ).fetchone()
                if activity == {'wait_event_type': 'Lock'}:
                    waited_on_lock = True
                    break
                time.sleep(0.05)
            assert waited_on_lock
            holder.commit()
            contender.join(timeout=10)
            assert not contender.is_alive()
        if 'error' in revoke_result:
            raise revoke_result['error']
        revoked = revoke_result['event']
        assert revoked.event_type.value == 'revoked'
        assert revoked.publication_id == event.publication_id

        with pytest.raises(AipEvalGateDependencyBlocked):
            AipEvalAuthorityStore(connect).require_exact_passed(
                scope,
                gate_ref,
                expected_target=target_ref,
                route_evidence=evidence,
            )
        with pytest.raises(AipReleaseGateRejected):
            service.publish(
                scope,
                actor=consumer_subject,
                request=publish_request,
                expected_target_type=AssetType.MODEL_ROUTE,
                route_request_context=route_request_context,
            )
        with psycopg.connect(admin_dsn, row_factory=dict_row) as admin:
            event_types = admin.execute(
                'SELECT event_type FROM aip_publication_event '
                'WHERE org_id=%s AND project_id=%s AND publication_id=%s '
                'ORDER BY occurred_at,event_id',
                (*scope.key, event.publication_id),
            ).fetchall()
            assert [row['event_type'] for row in event_types] == [
                'published', 'revoked'
            ]

        # N5: after the new event and real epoch update have both occurred,
        # inject one explicit terminal failure.  The connection context must
        # roll back the event and epoch together while preserving the old gate.
        late_gate = gate.model_copy(update={
            'decision_id': 'route-native-r9c-late-failure-gate',
            'decided_by': 'route-native-r9c',
        })
        with psycopg.connect(admin_dsn, row_factory=dict_row) as admin:
            AipReleasePublicationService._insert_gate(admin, scope, late_gate)
            admin.commit()
        late_request = PublishReleaseRequest(
            releaseGateDecisionId=late_gate.decision_id,
            reasonHash='6' * 64,
            idempotencyKey='route-native-r9c-late-failure',
        )
        late_publication_id = service._stable_id(
            'publication', scope, late_request.idempotency_key
        )
        late_event_id = service._stable_id(
            'published', scope, late_request.idempotency_key
        )
        with psycopg.connect(admin_dsn, row_factory=dict_row) as admin:
            before_late = {
                'events': admin.execute(
                    'SELECT count(*) AS n FROM aip_publication_event '
                    'WHERE org_id=%s AND project_id=%s', scope.key,
                ).fetchone()['n'],
                'gates': admin.execute(
                    'SELECT count(*) AS n FROM aip_release_gate_decision '
                    'WHERE org_id=%s AND project_id=%s', scope.key,
                ).fetchone()['n'],
                'epoch': admin.execute(
                    'SELECT count(*) AS n FROM aip_publication_epoch '
                    'WHERE org_id=%s AND project_id=%s AND publication_id=%s',
                    (*scope.key, late_publication_id),
                ).fetchone()['n'],
            }
        real_epoch_lock = publication_epoch.lock_eval_publication_epoch

        def fail_after_real_epoch(conn, checked_scope, publication_id):
            result = real_epoch_lock(conn, checked_scope, publication_id)
            assert result == 1
            assert conn.execute(
                'SELECT event_id FROM aip_publication_event '
                'WHERE org_id=%s AND project_id=%s AND event_id=%s',
                (*scope.key, late_event_id),
            ).fetchone() == {'event_id': late_event_id}
            raise RuntimeError('synthetic explicit failure after real epoch')

        monkeypatch.setattr(
            publication_epoch,
            'lock_eval_publication_epoch',
            fail_after_real_epoch,
        )
        with pytest.raises(AipReleasePublicationPersistenceError):
            service.publish(
                scope,
                actor='route-native-r9c',
                request=late_request,
                expected_target_type=AssetType.MODEL_ROUTE,
                route_request_context=route_request_context,
            )
        monkeypatch.setattr(
            publication_epoch,
            'lock_eval_publication_epoch',
            real_epoch_lock,
        )
        with psycopg.connect(admin_dsn, row_factory=dict_row) as admin:
            after_late = {
                'events': admin.execute(
                    'SELECT count(*) AS n FROM aip_publication_event '
                    'WHERE org_id=%s AND project_id=%s', scope.key,
                ).fetchone()['n'],
                'gates': admin.execute(
                    'SELECT count(*) AS n FROM aip_release_gate_decision '
                    'WHERE org_id=%s AND project_id=%s', scope.key,
                ).fetchone()['n'],
                'epoch': admin.execute(
                    'SELECT count(*) AS n FROM aip_publication_epoch '
                    'WHERE org_id=%s AND project_id=%s AND publication_id=%s',
                    (*scope.key, late_publication_id),
                ).fetchone()['n'],
            }
            assert admin.execute(
                'SELECT event_id FROM aip_publication_event '
                'WHERE org_id=%s AND project_id=%s AND event_id=%s',
                (*scope.key, late_event_id),
            ).fetchone() is None
        assert before_late == after_late
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            if login_created:
                admin.execute(
                    'SELECT pg_terminate_backend(pid) FROM pg_stat_activity '
                    'WHERE usename=%s AND pid<>pg_backend_pid()', (login,),
                )
                admin.execute(sql.SQL('REVOKE aos_runtime FROM {}').format(sql.Identifier(login)))
                admin.execute(sql.SQL('DROP ROLE IF EXISTS {}').format(sql.Identifier(login)))
            if proof_authority_installed:
                admin.execute(sql.SQL('DROP SCHEMA IF EXISTS {} CASCADE').format(
                    sql.Identifier(authority.ISSUER_SCHEMA)))
                admin.execute(sql.SQL('DROP ROLE IF EXISTS {}').format(
                    sql.Identifier(authority.ISSUER_READER)))
                admin.execute(sql.SQL('DROP ROLE IF EXISTS {}').format(
                    sql.Identifier(authority.ISSUER_OWNER)))
            if bridge_installed:
                admin.execute('DROP FUNCTION IF EXISTS '
                    'public.require_model_route_eval_source_installation()')
                admin.execute('DROP FUNCTION IF EXISTS '
                    'public.read_capacity_source_for_model_route_eval(bytea,jsonb)')


@pytest.fixture
def route_release_native_owned_database_mode(monkeypatch):
    """Turn a pre-migrated retained test DB back into exclusive fixture mode."""
    import os

    from psycopg.conninfo import conninfo_to_dict

    if os.getenv('AOS_ROUTE_EVAL_RELEASE_CONSUMER_NATIVE') != '1':
        yield
        return
    parts = conninfo_to_dict(os.getenv('AOS_DATABASE_URL') or '')
    database = parts.get('dbname', '')
    if (
        os.getenv('AOS_TEST_USE_SHARED_DATABASE') != '1'
        or parts.get('host') not in {'127.0.0.1', 'localhost', '::1'}
        or int(parts.get('port', '0')) in {5432, 5433}
        or not database.startswith('aos_test_')
        or not database.endswith('_ti4_test')
    ):
        pytest.fail('r9b retained database must be an exclusive loopback test database')
    monkeypatch.setenv('AOS_TEST_USE_SHARED_DATABASE', '0')
    yield
