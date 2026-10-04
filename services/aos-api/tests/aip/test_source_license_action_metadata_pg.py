"""Source action metadata and reserved writer in disposable full-schema PG."""
import pytest
import psycopg
from aos_api.db import connect
from tests.aip.test_network_consumer_boundary_pg import isolated_owner,SCOPE

ACTION='aip_issue_source_license'
OBJECT='SourceLicenseRequest'
ISSUER='aos_source_license_approval_issuer'


def test_original_metadata_defines_exact_requested_grant_action():
    with isolated_owner() as conn:
        assert conn.execute('SELECT id,name,description,published,properties,required_markings FROM meta_object_type WHERE id=%s',(OBJECT,)).fetchone()=={
            'id':OBJECT,'name':'来源许可请求','description':'原Proposal内的精确来源许可声明',
            'published':True,'properties':[],'required_markings':[]}
        assert conn.execute('SELECT id,name,object_type,parameters,required_markings,submission_criteria FROM meta_action_type WHERE id=%s',(ACTION,)).fetchone()=={
            'id':ACTION,'name':'申请精确来源许可','object_type':OBJECT,'parameters':[],
            'required_markings':[],'submission_criteria':[]}


def test_reserved_approval_identity_has_no_login_members_or_license_write():
    with isolated_owner() as conn:
        role=conn.execute('SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname=%s',(ISSUER,)).fetchone()
        assert role is not None
        assert all(value is False for value in role.values())
        assert conn.execute('SELECT count(*) AS n FROM pg_auth_members WHERE roleid=%s::regrole OR member=%s::regrole',(ISSUER,ISSUER)).fetchone()['n']==0
        for table in ('aip_action_approval_event','aip_license_source_issuance','aip_license_source_head'):
            for privilege in ('INSERT','UPDATE','DELETE'):
                allowed=conn.execute('SELECT has_table_privilege(%s,%s,%s) AS allowed',(ISSUER,table,privilege)).fetchone()['allowed']
                assert allowed is (table=='aip_action_approval_event' and privilege=='INSERT')


@pytest.mark.parametrize('table,identity',[('meta_action_type',ACTION),('meta_object_type',OBJECT)])
@pytest.mark.parametrize('operation',['UPDATE','DELETE'])
def test_runtime_cannot_mutate_reserved_metadata(table,identity,operation):
    # Closed table/operation choices; exact scoped ordinary runtime adversary.
    with connect(SCOPE) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege,match='SOURCE_LICENSE_METADATA_RESERVED'):
            if operation=='UPDATE':
                conn.execute(f'UPDATE {table} SET name=\'forged\' WHERE id=%s',(identity,))
            else:
                conn.execute(f'DELETE FROM {table} WHERE id=%s',(identity,))
        conn.rollback()


def _migration():
    import importlib.util
    from pathlib import Path
    path=Path(__file__).resolve().parents[2]/'alembic/versions/a0v_140_source_license_action_metadata.py'
    spec=importlib.util.spec_from_file_location('source_metadata_boundary',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('flag',['LOGIN','INHERIT','SUPERUSER','CREATEDB','CREATEROLE','REPLICATION','BYPASSRLS'])
def test_upgrade_rejects_existing_unsafe_role_without_repair(monkeypatch,flag):
    migration=_migration()
    with isolated_owner() as conn:
        monkeypatch.setattr(migration.op,'execute',conn.execute)
        with pytest.raises(psycopg.errors.InsufficientPrivilege,match='SOURCE_LICENSE_APPROVAL_ROLE_DRIFT'):
            with conn.transaction():
                conn.execute(f'ALTER ROLE {ISSUER} {flag}')
                migration.upgrade()
        assert conn.execute('SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname=%s',(ISSUER,)).fetchone()=={
            'rolcanlogin':False,'rolinherit':False,'rolsuper':False,'rolcreatedb':False,
            'rolcreaterole':False,'rolreplication':False,'rolbypassrls':False}


@pytest.mark.parametrize('direction',['issuer_member','issuer_parent'])
def test_upgrade_rejects_either_membership_direction(monkeypatch,direction):
    migration=_migration()
    with isolated_owner() as conn:
        monkeypatch.setattr(migration.op,'execute',conn.execute)
        with pytest.raises(psycopg.errors.InsufficientPrivilege,match='SOURCE_LICENSE_APPROVAL_MEMBERSHIP_DRIFT'):
            with conn.transaction():
                if direction=='issuer_member':
                    conn.execute(f'GRANT aos_runtime TO {ISSUER}')
                else:
                    conn.execute(f'GRANT {ISSUER} TO aos_runtime')
                migration.upgrade()
        assert conn.execute('SELECT count(*) AS n FROM pg_auth_members WHERE roleid=%s::regrole OR member=%s::regrole',(ISSUER,ISSUER)).fetchone()['n']==0


@pytest.mark.parametrize('identity_part',['action_type','snapshot'])
@pytest.mark.parametrize('hide_source',[False,True])
def test_runtime_cannot_append_source_approval_even_with_adversarial_original_rows(client,identity_part,hide_source):
    from uuid import uuid4
    from psycopg import sql
    from psycopg.types.json import Jsonb
    from tests.aip.test_aip3b_action_execution import _create_approved
    # Existing ordinary Action approval provides valid schema/FK parents only.
    # These copied rows are adversarial fixtures, never legal source requests.
    original=_create_approved(client,'send_controlled_'+uuid4().hex)
    forged='b88-adversarial-'+uuid4().hex
    with isolated_owner() as admin:
        row=admin.execute('SELECT * FROM aip_action_proposal WHERE org_id=%s AND project_id=%s AND proposal_id=%s',(*SCOPE.key,original['id'])).fetchone()
        row.update(proposal_id=forged,idempotency_key=forged,status='drafted',version=1)
        if identity_part=='action_type': row['action_type_id']=ACTION
        else: row['action_type_snapshot']={**row['action_type_snapshot'],'id':ACTION}
        fields=list(row)
        values=[Jsonb(value) if isinstance(value,(dict,list)) else value for value in row.values()]
        admin.execute(sql.SQL('INSERT INTO aip_action_proposal ({}) VALUES ({})').format(
            sql.SQL(',').join(map(sql.Identifier,fields)),sql.SQL(',').join(sql.Placeholder() for _ in fields)),values)
        event=admin.execute('SELECT * FROM aip_action_approval_event WHERE org_id=%s AND project_id=%s AND proposal_id=%s',(*SCOPE.key,original['id'])).fetchone()
    policy='b88_hide_'+uuid4().hex
    if hide_source:
        with isolated_owner() as admin:
            admin.execute(sql.SQL("CREATE POLICY {} ON public.aip_action_proposal AS RESTRICTIVE FOR SELECT TO aos_runtime USING (action_type_id<>'aip_issue_source_license' AND action_type_snapshot->>'id'<>'aip_issue_source_license')").format(sql.Identifier(policy)))
    event.update(approval_event_id=forged,proposal_id=forged,idempotency_key=forged)
    fields=list(event)
    values=[Jsonb(value) if isinstance(value,(dict,list)) else value for value in event.values()]
    try:
        with connect(SCOPE) as conn:
            expected='SOURCE_LICENSE_INDEPENDENT_APPROVAL_ISSUER_REQUIRED'
            if hide_source:
                # The existing original network approval guard already rejects
                # any unavailable Proposal. Do not invent a successful bypass.
                expected+='|NETWORK_APPROVAL_PROPOSAL_UNAVAILABLE'
            with pytest.raises(psycopg.errors.InsufficientPrivilege,match=expected):
                conn.execute(sql.SQL('INSERT INTO aip_action_approval_event ({}) VALUES ({})').format(
                    sql.SQL(',').join(map(sql.Identifier,fields)),sql.SQL(',').join(sql.Placeholder() for _ in fields)),values)
            conn.rollback()
    finally:
        if hide_source:
            with isolated_owner() as admin:
                admin.execute(sql.SQL('DROP POLICY {} ON public.aip_action_proposal').format(sql.Identifier(policy)))
    with isolated_owner() as admin:
        assert admin.execute('SELECT count(*) AS n FROM aip_action_approval_event WHERE org_id=%s AND project_id=%s AND proposal_id=%s',(*SCOPE.key,forged)).fetchone()['n']==0


def test_source_proposal_terms_cannot_be_disguised_as_an_ordinary_action(client):
    from uuid import uuid4
    from psycopg import sql
    from psycopg.types.json import Jsonb
    from tests.aip.test_aip3b_action_execution import _create_approved
    original=_create_approved(client,'send_controlled_'+uuid4().hex)
    forged='b88-disguised-'+uuid4().hex
    with isolated_owner() as admin:
        row=admin.execute('SELECT * FROM aip_action_proposal WHERE org_id=%s AND project_id=%s AND proposal_id=%s',(*SCOPE.key,original['id'])).fetchone()
        row.update(proposal_id=forged,idempotency_key=forged,status='drafted',version=1,action_type_id=ACTION,
                   action_type_snapshot={**row['action_type_snapshot'],'id':ACTION})
        fields=list(row)
        values=[Jsonb(value) if isinstance(value,(dict,list)) else value for value in row.values()]
        admin.execute(sql.SQL('INSERT INTO aip_action_proposal ({}) VALUES ({})').format(
            sql.SQL(',').join(map(sql.Identifier,fields)),sql.SQL(',').join(sql.Placeholder() for _ in fields)),values)
    with connect(SCOPE) as conn:
        try:
            with pytest.raises(psycopg.errors.InsufficientPrivilege,match='SOURCE_LICENSE_PROPOSAL_TERMS_IMMUTABLE'):
                conn.execute("UPDATE aip_action_proposal SET action_type_id='ordinary',action_type_snapshot=%s WHERE org_id=%s AND project_id=%s AND proposal_id=%s",
                    (Jsonb({'id':'ordinary'}),*SCOPE.key,forged))
        finally:
            conn.rollback()
