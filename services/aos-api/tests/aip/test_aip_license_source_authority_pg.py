"""Production fence algorithms in disposable PG, not real issuer authorization."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, UTC
from queue import Queue
import time
import os
from uuid import uuid4

import psycopg
from psycopg import IsolationLevel, sql
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
import pytest

from aos_api.db import get_dsn, connect
from aos_api.tenant_scope import TenantScope, apply_transaction_scope
from aos_api.aip_production_contract_store import AipProductionContractStore, ProductionContractIdempotencyConflict, ProductionContractDependencyBlocked
from aos_api.aip_production_contracts import ExactRevisionRef, RevokeEvidenceBundleRequest
from aos_api.asset_registry.composition_store import PostgresCompositionStore
from aos_api.asset_registry.installation_store import PostgresInstallationStore
from tests.asset_registry.test_installation_store import _composition_inputs, _create_request
from tests.aip.test_aip_binding_evaluator_connection_pg import independent_login
from aos_api.aip_binding_evaluator_connection import BindingEvaluatorConnectionFactory

SCOPE = TenantScope('org-org','dev-project')
HASH = 'a'*64
OWNER = 'aos_license_source_fence_owner'


def test_strict_login_returns_first_revoke_response_without_postcommit_scope_loss(source,independent_login):
    admin,create=source
    bundle=create()
    owner,role,config=independent_login
    tables=('aip_evidence_bundle_revision','aip_license_source_issuance','aip_license_source_head',
            'aip_evidence_bundle_revoke_event','aip_production_contract_receipt')
    policy='b84_'+uuid4().hex[:12]
    created=[]
    try:
        owner.execute(sql.SQL('GRANT USAGE ON SCHEMA public TO {}').format(sql.Identifier(role)))
        for table in tables:
            owner.execute(sql.SQL('GRANT SELECT ON public.{} TO {}').format(sql.Identifier(table),sql.Identifier(role)))
            owner.execute(sql.SQL("CREATE POLICY {} ON public.{} TO {} USING ("
                "org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true)) "
                "WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))").format(
                    sql.Identifier(policy),sql.Identifier(table),sql.Identifier(role)))
            created.append(table)
        for table in ('aip_evidence_bundle_revoke_event','aip_production_contract_receipt'):
            owner.execute(sql.SQL('GRANT INSERT ON public.{} TO {}').format(sql.Identifier(table),sql.Identifier(role)))
        owner.execute(sql.SQL('GRANT EXECUTE ON FUNCTION public.aos_license_source_lock(text,text,text,bigint,text,boolean) TO {}').format(sql.Identifier(role)))
        factory=BindingEvaluatorConnectionFactory(config)
        try:
            response=invoke(bundle,'b84.'+bundle,factory=factory)
        except Exception:
            # Read-only reconciliation, never retry an unknown first outcome.
            assert snapshot(admin,bundle)==(1,1,1), 'first outcome must be independently reconciled'
            raise
        assert response.revoked and response.bundle_id==bundle
        assert snapshot(admin,bundle)==(1,1,1)
        assert invoke(bundle,'b84.'+bundle,factory=factory).revoked
        assert snapshot(admin,bundle)==(1,1,1)
        with factory(TenantScope('dev-org','dev-project')) as conn:
            assert conn.execute('SELECT count(*) AS n FROM aip_evidence_bundle_revision WHERE bundle_id=%s',(bundle,)).fetchone()['n']==0
    finally:
        admin.rollback()
        for table in created:
            owner.execute(sql.SQL('DROP POLICY {} ON public.{}').format(sql.Identifier(policy),sql.Identifier(table)))


def create_source(admin, trusted=True, *, installation_id=None):
    bundle, issuance, receipt = ['b83.'+uuid4().hex for _ in range(3)]
    install = uuid4()
    admin.execute("INSERT INTO twa_org(id,name) VALUES('org-org','test-only') ON CONFLICT DO NOTHING")
    admin.execute("INSERT INTO twa_workspace(org_id,project_id,name) VALUES('org-org','dev-project','test-only') ON CONFLICT DO NOTHING")
    admin.execute("INSERT INTO meta_org(id,name) VALUES('org-org','test-only') ON CONFLICT DO NOTHING")
    admin.execute("INSERT INTO meta_workspace(org_id,project_id,name) VALUES('org-org','dev-project','test-only') ON CONFLICT DO NOTHING")
    admin.commit()
    brief = Jsonb(dict(resourceType='TaskBriefRevision',resourceId='test-only',revision=1,contentHash=HASH))
    admin.execute("""INSERT INTO aip_evidence_bundle_revision
        (org_id,project_id,bundle_id,revision,brief_ref,subject_refs,cutoff_at,item_refs,
         coverage,missing,conflicts,uncertainties,freshness,marking,license_summary,
         content_hash,lifecycle,created_by)
        VALUES('org-org','dev-project',%s,1,%s,'[]',NOW(),'[]','complete','[]','[]',
        '[]','fresh','[]','{"test":"ordinary-license-summary"}',%s,'frozen','b83-test-only')""", (bundle,brief,HASH))
    if trusted:
        if installation_id is None:
            request,snapshot,payload=_composition_inputs()
            composition=PostgresCompositionStore().create_or_get(
                org_id=SCOPE.org_id,project_id=SCOPE.project_id,request=request,
                snapshot=snapshot,payload=payload,created_by='b83-test-only')
            draft=PostgresInstallationStore().create_draft(
                org_id=SCOPE.org_id,project_id=SCOPE.project_id,
                request=_create_request(composition.composition_id),
                requested_by='b83-test-only')
            install=draft.installation_id
            etag=1
        else:
            install=installation_id
            etag=admin.execute('SELECT etag_version FROM bundle_installation WHERE org_id=%s AND project_id=%s AND installation_id=%s',(*SCOPE.key,install)).fetchone()['etag_version']
        admin.execute("""INSERT INTO aip_agent_registry_receipt(org_id,project_id,receipt_id,
            operation,idempotency_key,request_hash,resource_ref,result_ref,status,created_by,created_at)
            VALUES('org-org','dev-project',%s,'b83.test-only',%s,%s,'{}','{}','applied','test-only',NOW())""", (receipt,receipt,HASH))
        admin.execute("""INSERT INTO aip_license_source_issuance(org_id,project_id,issuance_id,
            bundle_id,revision,content_hash,installation_id,installation_etag,receipt_id,
            owner_authorization_ref,policy_ref,issued_at,expires_at)
            VALUES('org-org','dev-project',%s,%s,1,%s,%s,%s,%s,
            '{"test":"owner-fixture"}','{"test":"policy-fixture"}',
            NOW()-INTERVAL '1 second',NOW()+INTERVAL '1 hour')""", (issuance,bundle,HASH,install,etag,receipt))
        admin.execute("""INSERT INTO aip_license_source_head(org_id,project_id,bundle_id,
            revision,content_hash,issuance_id,epoch) VALUES('org-org','dev-project',%s,1,%s,%s,0)""", (bundle,HASH,issuance))
    admin.commit()
    return bundle


def test_revoke_response_validation_failure_rolls_back_before_commit(source,monkeypatch):
    admin,create=source
    bundle=create()
    def reject_response(self,scope,bundle_id,revision=1,*,conn=None,**kwargs):
        assert conn.execute('SELECT epoch FROM aip_license_source_head WHERE bundle_id=%s',(bundle,)).fetchone()['epoch']==1
        assert conn.execute('SELECT count(*) AS n FROM aip_evidence_bundle_revoke_event WHERE bundle_id=%s',(bundle,)).fetchone()['n']==1
        assert conn.execute("SELECT count(*) AS n FROM aip_production_contract_receipt WHERE result_ref->>'resourceId'=%s",(bundle,)).fetchone()['n']==1
        raise ValueError('b84 response validation rejected')
    monkeypatch.setattr(AipProductionContractStore,'get_evidence_bundle',reject_response)
    with pytest.raises(ValueError,match='response validation rejected'):
        invoke(bundle,'b84.'+bundle)
    assert snapshot(admin,bundle)==(0,0,0)


@pytest.fixture
def source():
    assert conninfo_to_dict(get_dsn())['dbname'].startswith('aos_test_')
    with psycopg.connect(get_dsn(),row_factory=dict_row) as admin:
        yield admin, lambda trusted=True: create_source(admin,trusted)

def raw_revoke(conn, bundle, *, conflict=False, content_hash=HASH):
    conn.execute("""INSERT INTO aip_evidence_bundle_revoke_event
        (org_id,project_id,event_id,bundle_id,revision,content_hash,reason,actor)
        VALUES(%s,%s,%s,%s,1,%s,'test-only','b83-test-only')""" +
        (' ON CONFLICT DO NOTHING' if conflict else ''), (*SCOPE.key,'b83.'+uuid4().hex,bundle,content_hash))


def snapshot(admin, bundle):
    admin.rollback()
    head = admin.execute('SELECT epoch FROM aip_license_source_head WHERE bundle_id=%s',(bundle,)).fetchone()
    events = admin.execute('SELECT count(*) AS n FROM aip_evidence_bundle_revoke_event WHERE bundle_id=%s',(bundle,)).fetchone()['n']
    receipts = admin.execute("SELECT count(*) AS n FROM aip_production_contract_receipt WHERE result_ref->>'resourceId'=%s",(bundle,)).fetchone()['n']
    return (head['epoch'] if head else None,events,receipts)


def invoke(bundle, key, *, factory=connect, reason='b83 test-only'):
    return AipProductionContractStore(connect_factory=factory).revoke_evidence_bundle(
        SCOPE,'b83-test-only',bundle,key,RevokeEvidenceBundleRequest(
            expected_revision=1,expected_content_hash=HASH,reason=reason))


def lock(conn,bundle,shared=True):
    from aos_api.aip_license_source_authority import lock_license_source_head
    return lock_license_source_head(conn,SCOPE,ExactRevisionRef(
        resource_type='EvidenceBundleRevision',resource_id=bundle,revision=1,content_hash=HASH),shared=shared)


def test_raw_revoke_advances_epoch_only_for_inserted_event(source):
    admin,create=source
    bundle=create()
    with connect(SCOPE) as conn:
        raw_revoke(conn,bundle)
        conn.commit()
    assert snapshot(admin,bundle)==(1,1,0)
    with connect(SCOPE) as conn:
        raw_revoke(conn,bundle,conflict=True)
        conn.commit()
    assert snapshot(admin,bundle)==(1,1,0), 'ON CONFLICT must not advance epoch'


def test_store_replay_conflict_new_key_and_generic_compatibility(source):
    admin,create=source
    bundle=create()
    assert invoke(bundle,'b83.'+bundle).revoked
    assert invoke(bundle,'b83.'+bundle).revoked
    assert snapshot(admin,bundle)==(1,1,1)
    with pytest.raises(ProductionContractIdempotencyConflict):
        invoke(bundle,'b83.'+bundle,reason='different body')
    assert snapshot(admin,bundle)==(1,1,1)
    assert invoke(bundle,'b83.new.'+bundle).revoked
    assert snapshot(admin,bundle)==(1,1,2)
    ordinary=create(False)
    assert invoke(ordinary,'b83.'+ordinary).revoked
    assert snapshot(admin,ordinary)==(None,1,1)


def test_generic_revoke_remains_compatible_without_issuance_schema(source):
    admin,create=source
    if os.getenv('AOS_B83_135_COMPAT')=='1':
        assert admin.execute('SELECT version_num FROM alembic_version').fetchone()['version_num']=='a0v_135'
        assert admin.execute("SELECT to_regclass('public.aip_license_source_issuance') AS t").fetchone()['t'] is None
    bundle=create(False)
    assert invoke(bundle,'b83.'+bundle).revoked
    assert invoke(bundle,'b83.'+bundle).revoked
    assert admin.execute('SELECT count(*) AS n FROM aip_evidence_bundle_revoke_event WHERE bundle_id=%s',(bundle,)).fetchone()['n']==1
    assert admin.execute("SELECT count(*) AS n FROM aip_production_contract_receipt WHERE result_ref->>'resourceId'=%s",(bundle,)).fetchone()['n']==1


def test_epoch_event_receipt_rollback_together(source):
    admin,create=source
    bundle=create()
    @contextmanager
    def failing_factory(scope):
        with connect(scope) as conn:
            class Proxy:
                def __getattr__(self,name): return getattr(conn,name)
                def commit(self):
                    assert conn.execute('SELECT epoch FROM aip_license_source_head WHERE bundle_id=%s',(bundle,)).fetchone()['epoch']==1
                    assert conn.execute('SELECT count(*) AS n FROM aip_evidence_bundle_revoke_event WHERE bundle_id=%s',(bundle,)).fetchone()['n']==1
                    assert conn.execute("SELECT count(*) AS n FROM aip_production_contract_receipt WHERE result_ref->>'resourceId'=%s",(bundle,)).fetchone()['n']==1
                    raise RuntimeError('b83 precommit rollback')
            yield Proxy()
    with pytest.raises(RuntimeError,match='precommit rollback'):
        invoke(bundle,'b83.'+bundle,factory=failing_factory)
    assert snapshot(admin,bundle)==(0,0,0)


def test_missing_head_and_wrong_tenant_do_not_revoke(source):
    from aos_api.aip_license_source_authority import LicenseSourceUnavailable
    admin,create=source
    bundle=create()
    with connect(TenantScope('dev-org','dev-project')) as conn:
        with pytest.raises(LicenseSourceUnavailable,match='SCOPE_MISMATCH'),conn.transaction():
            lock(conn,bundle)
    admin.execute('DELETE FROM aip_license_source_head WHERE bundle_id=%s',(bundle,))
    admin.commit()
    with pytest.raises(ProductionContractDependencyBlocked,match='LICENSE_SOURCE_HEAD_MISSING'):
        invoke(bundle,'b83.'+bundle)
    with connect(SCOPE) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege),conn.transaction():
            raw_revoke(conn,bundle)
    assert snapshot(admin,bundle)==(None,0,0)


def test_source_reader_wrong_hash_has_safe_domain_error(source):
    from aos_api.aip_license_source_authority import lock_license_source_head, LicenseSourceUnavailable
    admin,create=source
    bundle=create()
    with connect(SCOPE) as conn:
        with pytest.raises(LicenseSourceUnavailable,match='LICENSE_SOURCE_EXACT_FROZEN_MISSING'):
            lock_license_source_head(conn,SCOPE,ExactRevisionRef(resource_type='EvidenceBundleRevision',
                resource_id=bundle,revision=1,content_hash='e'*64))
    assert snapshot(admin,bundle)==(0,0,0)


def test_missing_trusted_head_api_returns_dependency_reason_and_zero_effect(source,client):
    from tests.test_w2a_production_contract_api import headers
    admin,create=source
    bundle=create()
    admin.execute('DELETE FROM aip_license_source_head WHERE bundle_id=%s',(bundle,))
    admin.commit()
    response=client.post('/v1/aip/production-contracts/evidence-bundles/'+bundle+'/revoke',
        headers=headers(key='b83.'+bundle),json=dict(expectedRevision=1,expectedContentHash=HASH,reason='test-only'))
    assert response.status_code==422
    assert 'LICENSE_SOURCE_HEAD_MISSING' in response.text
    assert snapshot(admin,bundle)==(None,0,0)


@pytest.mark.parametrize('failure,reason',[('missing','LICENSE_SOURCE_FENCE_UNAVAILABLE'),
                                         ('denied','LICENSE_SOURCE_FENCE_DENIED')])
def test_partial_fence_function_is_safe_dependency_error_with_zero_effect(source,failure,reason):
    admin,create=source
    bundle=create()
    signature=sql.SQL('public.aos_license_source_lock(text,text,text,bigint,text,boolean)')
    temporary='b83_unavailable_'+uuid4().hex[:12]
    if failure=='missing':
        admin.execute(sql.SQL('ALTER FUNCTION {} RENAME TO {}').format(signature,sql.Identifier(temporary)))
    else:
        admin.execute(sql.SQL('REVOKE EXECUTE ON FUNCTION {} FROM aos_runtime').format(signature))
    admin.commit()
    try:
        with pytest.raises(ProductionContractDependencyBlocked,match=reason):
            invoke(bundle,'b83.'+bundle)
        assert snapshot(admin,bundle)==(0,0,0)
    finally:
        admin.rollback()
        if failure=='missing':
            admin.execute(sql.SQL('ALTER FUNCTION public.{}(text,text,text,bigint,text,boolean) RENAME TO aos_license_source_lock').format(sql.Identifier(temporary)))
        else:
            admin.execute(sql.SQL('GRANT EXECUTE ON FUNCTION {} TO aos_runtime').format(signature))
        admin.commit()


def test_fence_has_narrow_owner_runtime_acl_and_unfiltered_event_triggers(source):
    admin,create=source
    create()
    attrs=admin.execute('SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname=%s',(OWNER,)).fetchone()
    assert not any(attrs.values())
    assert admin.execute('SELECT count(*) AS n FROM pg_auth_members WHERE roleid=%s::regrole OR member=%s::regrole',(OWNER,OWNER)).fetchone()['n']==0
    rows=admin.execute("SELECT prosecdef,proconfig,pg_get_userbyid(proowner) AS owner FROM pg_proc WHERE proname IN ('aos_license_source_lock','aos_license_revoke_fence')").fetchall()
    assert len(rows)==2 and all(r['prosecdef'] and r['owner']==OWNER and r['proconfig']==['search_path=pg_catalog, public'] for r in rows)
    assert admin.execute("SELECT has_function_privilege('aos_runtime','public.aos_license_revoke_fence()','EXECUTE') AS p").fetchone()['p'] is False
    triggers=admin.execute("SELECT tgqual FROM pg_trigger WHERE tgname IN ('aos_license_revoke_before','aos_license_revoke_after')").fetchall()
    assert len(triggers)==2 and all(r['tgqual'] is None for r in triggers)
    with connect(SCOPE) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege),conn.transaction():
            conn.execute('UPDATE aip_license_source_head SET epoch=epoch+1')


def wait_blocked(admin,pids,blocker,futures):
    deadline=time.monotonic()+6
    while time.monotonic()<deadline:
        graph={pid:admin.execute('SELECT pg_blocking_pids(%s) AS blockers',(pid,)).fetchone()['blockers'] for pid in pids}
        def reaches(pid,seen):
            if pid==blocker:return True
            if pid in seen:return False
            return any(reaches(parent,seen|{pid}) for parent in graph.get(pid,[]))
        if all(reaches(pid,set()) for pid in pids):return
        assert not any(f.done() for f in futures), 'writer escaped shared source head'
        time.sleep(.025)
    pytest.fail('exact writer PIDs did not wait on common head')


def test_two_same_key_store_writers_wait_before_replay_and_both_succeed(source,monkeypatch):
    if os.getenv('AOS_B83_PRE_REPLAY_PROBE')=='1':
        from aos_api import aip_license_source_authority
        monkeypatch.setattr(aip_license_source_authority,'lock_existing_license_source_for_revoke',lambda *args:None)
        monkeypatch.setattr(AipProductionContractStore,'_lock_evidence_revoke_key',staticmethod(lambda *args:None))
    admin,create=source
    bundle=create()
    pids=Queue()
    @contextmanager
    def writer_factory(scope):
        with connect(scope) as conn:
            pids.put(conn.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid'])
            yield conn
    with connect(SCOPE) as blocker:
        blocker_pid=blocker.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid']
        assert lock(blocker,bundle,False)==0
        with ThreadPoolExecutor(max_workers=2) as pool:
            fs=[pool.submit(invoke,bundle,'b83.'+bundle,factory=writer_factory) for _ in range(2)]
            try: wait_blocked(admin,[pids.get(timeout=6) for _ in fs],blocker_pid,fs)
            finally:blocker.rollback()
            assert all(f.result(timeout=10).revoked for f in fs)
    assert snapshot(admin,bundle)==(1,1,1)


def test_trusted_source_revision_cannot_evade_fence_using_wrong_hash(source):
    admin,create=source
    bundle=create()
    with connect(SCOPE) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege),conn.transaction():
            raw_revoke(conn,bundle,content_hash='e'*64)
    assert snapshot(admin,bundle)==(0,0,0)


def test_same_key_different_source_writers_return_conflict_without_partial_revoke(source):
    admin,create=source
    bundles=[create(),create()]
    key='b83.cross-resource.'+uuid4().hex
    gate=int(uuid4().hex[:15],16)
    name='b83_receipt_gate_'+uuid4().hex[:12]
    admin.execute(sql.SQL("""CREATE FUNCTION public.{}() RETURNS trigger
        LANGUAGE plpgsql SET search_path=pg_catalog AS $$ BEGIN
        IF NEW.operation='evidence_bundle.revoke' AND NEW.idempotency_key={} THEN
            PERFORM pg_advisory_xact_lock({});
        END IF;
        RETURN NEW; END $$""").format(sql.Identifier(name),sql.Literal(key),sql.Literal(gate)))
    admin.execute(sql.SQL('CREATE TRIGGER {} BEFORE INSERT ON aip_production_contract_receipt FOR EACH ROW EXECUTE FUNCTION public.{}()').format(sql.Identifier(name),sql.Identifier(name)))
    admin.commit()
    pids=Queue()
    @contextmanager
    def writer_factory(scope):
        with connect(scope) as conn:
            pids.put(conn.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid'])
            yield conn
    def run(bundle):
        try:
            assert invoke(bundle,key,factory=writer_factory).revoked
            return 'ok'
        except ProductionContractIdempotencyConflict:
            return 'conflict'
    try:
        with connect(SCOPE) as blocker:
            blocker_pid=blocker.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid']
            blocker.execute('SELECT pg_advisory_xact_lock(%s)',(gate,))
            with ThreadPoolExecutor(max_workers=2) as pool:
                fs=[pool.submit(run,bundle) for bundle in bundles]
                try:
                    writer_pids=[pids.get(timeout=6) for _ in fs]
                    assert len(set(writer_pids))==2
                    wait_blocked(admin,writer_pids,blocker_pid,fs)
                finally:blocker.rollback()
                assert sorted(f.result(timeout=10) for f in fs)==['conflict','ok']
        assert sorted(snapshot(admin,bundle) for bundle in bundles)==[(0,0,0),(1,1,1)]
    finally:
        admin.rollback()
        admin.execute(sql.SQL('DROP TRIGGER {} ON aip_production_contract_receipt').format(sql.Identifier(name)))
        admin.execute(sql.SQL('DROP FUNCTION public.{}()').format(sql.Identifier(name)))
        admin.commit()


def test_serializable_old_snapshot_cannot_acquire_changed_license_head(source):
    admin,create=source
    bundle=create()
    with psycopg.connect(get_dsn(),row_factory=dict_row) as evaluator:
        evaluator.isolation_level=IsolationLevel.SERIALIZABLE
        apply_transaction_scope(evaluator,SCOPE)
        evaluator.execute('SELECT epoch FROM aip_license_source_head WHERE bundle_id=%s',(bundle,)).fetchone()
        assert invoke(bundle,'b83.'+bundle).revoked
        with pytest.raises(psycopg.errors.SerializationFailure):lock(evaluator,bundle)
        evaluator.rollback()
    assert snapshot(admin,bundle)==(1,1,1)


def test_evaluate_first_shared_lock_blocks_actual_store_writer(source):
    admin,create=source
    bundle=create()
    pids=Queue()
    @contextmanager
    def writer_factory(scope):
        with connect(scope) as conn:
            pids.put(conn.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid'])
            yield conn
    with connect(SCOPE) as evaluator:
        evaluator_pid=evaluator.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid']
        assert lock(evaluator,bundle)==0
        with ThreadPoolExecutor(max_workers=1) as pool:
            fs=[pool.submit(invoke,bundle,'b83.'+bundle,factory=writer_factory)]
            try:
                wait_blocked(admin,[pids.get(timeout=6)],evaluator_pid,fs)
                assert snapshot(admin,bundle)==(0,0,0)
            finally:evaluator.commit()
            assert fs[0].result(timeout=10).revoked
    assert snapshot(admin,bundle)==(1,1,1)


def test_source_fact_is_transactional_and_rejects_revoke_and_installation_drift(source):
    from aos_api.aip_license_source_authority import read_license_source_fact, LicenseSourceUnavailable
    admin,create=source
    bundle=create()
    ref=ExactRevisionRef(resource_type='EvidenceBundleRevision',resource_id=bundle,revision=1,content_hash=HASH)
    with connect(SCOPE) as conn:
        with pytest.raises(LicenseSourceUnavailable,match='INSTALLATION_DRIFT'):
            read_license_source_fact(conn,SCOPE,ref,checked_at=datetime.now(UTC))
    assert invoke(bundle,'b83.'+bundle).revoked
    with connect(SCOPE) as conn:
        with pytest.raises(LicenseSourceUnavailable,match='REVOKED'):
            read_license_source_fact(conn,SCOPE,ref,checked_at=datetime.now(UTC))


def assert_active_installation_source_reader(installation_id):
    """Only called by explicit signed-full-schema test opt-in."""
    from aos_api.aip_license_source_authority import read_license_source_fact, LicenseSourceUnavailable
    assert conninfo_to_dict(get_dsn())['dbname'].startswith('aos_test_')
    with psycopg.connect(get_dsn(),row_factory=dict_row) as admin:
        bundle=create_source(admin,installation_id=installation_id)
        ref=ExactRevisionRef(resource_type='EvidenceBundleRevision',resource_id=bundle,revision=1,content_hash=HASH)
        with connect(SCOPE) as conn:
            fact=read_license_source_fact(conn,SCOPE,ref,checked_at=datetime.now(UTC))
            assert fact.epoch==0 and fact.installation_id==installation_id
            assert fact.authorization=='SOURCE_FACT_ONLY_NO_START'
            with pytest.raises(LicenseSourceUnavailable,match='OUTSIDE_VALIDITY'):
                read_license_source_fact(conn,SCOPE,ref,checked_at=fact.expires_at)
        with connect(SCOPE) as conn:
            raw_revoke(conn,bundle)
            conn.commit()
        assert snapshot(admin,bundle)==(1,1,0)
        with connect(SCOPE) as conn:
            with pytest.raises(LicenseSourceUnavailable,match='REVOKED'):
                read_license_source_fact(conn,SCOPE,ref,checked_at=datetime.now(UTC))
