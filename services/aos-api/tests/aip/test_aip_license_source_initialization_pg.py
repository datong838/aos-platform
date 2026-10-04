"""First initialization races; fixture issuance is never formal authorization."""
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from uuid import uuid4

import psycopg
from psycopg import IsolationLevel
from psycopg.rows import dict_row
import pytest

from aos_api import aip_license_source_authority as authority
from aos_api.aip_production_contracts import ExactRevisionRef
from aos_api.db import connect,get_dsn
from tests.aip.test_aip_license_source_authority_pg import (
    source,SCOPE,HASH,raw_revoke,wait_blocked,invoke,
)


def ref(bundle):
    return ExactRevisionRef(resource_type='EvidenceBundleRevision',resource_id=bundle,revision=1,content_hash=HASH)


def initialization_lock(conn,bundle,shared=True):
    method=getattr(authority,'lock_license_source_initialization',None)
    if method is None:
        # RED-only probe of the prior read-only first-source strategy. No
        # production fallback, role or permission is introduced by this branch.
        return conn.execute('SELECT content_hash FROM aip_evidence_bundle_revision WHERE org_id=%s AND project_id=%s AND bundle_id=%s',(*SCOPE.key,bundle)).fetchone()['content_hash']
    return method(conn,SCOPE,ref(bundle),shared=shared)


def set_scope(conn):
    conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",SCOPE.key)


def append_fixture_issuance(conn,bundle,template):
    # Copies test-only FK parents to prove transaction behavior. This bypasses
    # no production command: legal Owner/Policy approval is deliberately absent.
    issuance='b86.fixture.'+uuid4().hex
    conn.execute("""INSERT INTO aip_license_source_issuance
        SELECT org_id,project_id,%s,%s,revision,content_hash,installation_id,
            installation_etag,receipt_id,owner_authorization_ref,policy_ref,issued_at,expires_at
        FROM aip_license_source_issuance WHERE bundle_id=%s""",(issuance,bundle,template))
    conn.execute("""INSERT INTO aip_license_source_head
        (org_id,project_id,bundle_id,revision,content_hash,issuance_id,epoch)
        VALUES(%s,%s,%s,1,%s,%s,0)""",(*SCOPE.key,bundle,HASH,issuance))


def test_stale_first_initialization_cannot_commit_after_read_committed_raw_revoke(source):
    admin,create=source
    template=create()
    bundle=create(False)
    with psycopg.connect(get_dsn(),row_factory=dict_row) as initializer:
        initializer.isolation_level=IsolationLevel.SERIALIZABLE
        set_scope(initializer)
        assert initializer.execute('SELECT count(*) AS n FROM aip_evidence_bundle_revoke_event WHERE bundle_id=%s',(bundle,)).fetchone()['n']==0
        with connect(SCOPE) as writer:
            assert writer.execute('SHOW transaction_isolation').fetchone()['transaction_isolation']=='read committed'
            raw_revoke(writer,bundle)
            writer.commit()
        with pytest.raises(psycopg.errors.SerializationFailure):
            initialization_lock(initializer,bundle)
            assert initializer.execute('SELECT count(*) AS n FROM aip_evidence_bundle_revoke_event WHERE bundle_id=%s',(bundle,)).fetchone()['n']==0
            append_fixture_issuance(initializer,bundle,template)
            initializer.commit()
        initializer.rollback()
    admin.rollback()
    assert admin.execute('SELECT count(*) AS n FROM aip_license_source_issuance WHERE bundle_id=%s',(bundle,)).fetchone()['n']==0
    assert admin.execute('SELECT count(*) AS n FROM aip_evidence_bundle_revoke_event WHERE bundle_id=%s',(bundle,)).fetchone()['n']==1


def test_initialization_before_any_issuance_blocks_raw_revoke_pid(source):
    admin,create=source
    bundle=create(False)
    pids=Queue()
    def writer():
        with connect(SCOPE) as conn:
            pids.put(conn.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid'])
            raw_revoke(conn,bundle)
            conn.commit()
        return 'ok'
    with connect(SCOPE) as initializer:
        initialization_lock(initializer,bundle)
        pid=initializer.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid']
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(writer)
            try:
                wait_blocked(admin,[pids.get(timeout=6)],pid,[future])
            finally:
                initializer.rollback()
            assert future.result(timeout=10)=='ok'


def coordination_epoch(admin,bundle):
    admin.rollback()
    row=admin.execute('SELECT epoch FROM aip_license_source_initialization_fence WHERE bundle_id=%s',(bundle,)).fetchone()
    return row['epoch'] if row else None


def test_initialization_commit_then_raw_revoke_sees_new_issuance_head(source):
    admin,create=source
    template=create()
    bundle=create(False)
    pids=Queue()
    def writer():
        with connect(SCOPE) as conn:
            pids.put(conn.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid'])
            raw_revoke(conn,bundle)
            conn.commit()
        return 'ok'
    with psycopg.connect(get_dsn(),row_factory=dict_row) as initializer:
        initializer.isolation_level=IsolationLevel.SERIALIZABLE
        set_scope(initializer)
        assert initialization_lock(initializer,bundle)==0
        append_fixture_issuance(initializer,bundle,template)
        pid=initializer.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid']
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(writer)
            try:
                wait_blocked(admin,[pids.get(timeout=6)],pid,[future])
            finally:
                initializer.commit()
            assert future.result(timeout=10)=='ok'
    assert coordination_epoch(admin,bundle)==1
    assert admin.execute('SELECT epoch FROM aip_license_source_head WHERE bundle_id=%s',(bundle,)).fetchone()['epoch']==1


def test_raw_revoke_first_blocks_stale_initializer_until_serialization_failure(source):
    admin,create=source
    bundle=create(False)
    pids=Queue()
    def initializer():
        with psycopg.connect(get_dsn(),row_factory=dict_row) as conn:
            conn.isolation_level=IsolationLevel.SERIALIZABLE
            set_scope(conn)
            pids.put(conn.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid'])
            try:
                initialization_lock(conn,bundle)
            except psycopg.errors.SerializationFailure:
                conn.rollback()
                return 'stale rejected'
            pytest.fail('stale initializer escaped committed raw revoke')
    with connect(SCOPE) as writer:
        raw_revoke(writer,bundle)
        pid=writer.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid']
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(initializer)
            try:
                wait_blocked(admin,[pids.get(timeout=6)],pid,[future])
            finally:
                writer.commit()
            assert future.result(timeout=10)=='stale rejected'
    assert coordination_epoch(admin,bundle)==1


def test_neutral_coordination_does_not_issue_and_replay_does_not_advance(source):
    admin,create=source
    bundle=create(False)
    with connect(SCOPE) as conn:
        assert initialization_lock(conn,bundle)==0
        conn.commit()
    assert coordination_epoch(admin,bundle)==0
    assert admin.execute('SELECT count(*) AS n FROM aip_license_source_issuance WHERE bundle_id=%s',(bundle,)).fetchone()['n']==0
    assert admin.execute('SELECT count(*) AS n FROM aip_license_source_head WHERE bundle_id=%s',(bundle,)).fetchone()['n']==0
    invoke(bundle,'b86.'+bundle)
    invoke(bundle,'b86.'+bundle)
    with connect(SCOPE) as conn:
        raw_revoke(conn,bundle,conflict=True)
        conn.commit()
    assert coordination_epoch(admin,bundle)==1


def test_initialization_epoch_rolls_back_with_failed_raw_revoke(source):
    admin,create=source
    bundle=create(False)
    with pytest.raises(RuntimeError,match='precommit fault'):
        with connect(SCOPE) as conn:
            raw_revoke(conn,bundle)
            assert conn.execute('SELECT epoch FROM aip_license_source_initialization_fence WHERE bundle_id=%s',(bundle,)).fetchone()['epoch']==1
            raise RuntimeError('b86 precommit fault')
    assert coordination_epoch(admin,bundle) is None
    assert admin.execute('SELECT count(*) AS n FROM aip_evidence_bundle_revoke_event WHERE bundle_id=%s',(bundle,)).fetchone()['n']==0


@pytest.mark.parametrize('lifecycle',['withdrawn','superseded'])
def test_ordinary_historical_lifecycle_keeps_generic_revoke_compatibility(source,lifecycle):
    admin,create=source
    bundle=create(False)
    admin.execute('UPDATE aip_evidence_bundle_revision SET lifecycle=%s WHERE bundle_id=%s',(lifecycle,bundle))
    admin.commit()
    assert invoke(bundle,'b86.'+bundle).revoked
    assert coordination_epoch(admin,bundle)==1
    assert admin.execute('SELECT count(*) AS n FROM aip_license_source_issuance WHERE bundle_id=%s',(bundle,)).fetchone()['n']==0


def test_initialization_definer_owner_scope_and_acl_are_narrow(source):
    from aos_api.tenant_scope import TenantScope
    from aos_api.aip_license_source_authority import LicenseSourceUnavailable
    admin,create=source
    bundle=create(False)
    signature='public.aos_license_source_initialization_lock(text,text,text,bigint,text,boolean)'
    proc=admin.execute('SELECT prosecdef,proconfig,pg_get_userbyid(proowner) AS owner FROM pg_proc WHERE oid=%s::regprocedure',(signature,)).fetchone()
    assert proc==dict(prosecdef=True,proconfig=['search_path=pg_catalog, public'],owner='aos_license_source_fence_owner')
    assert not admin.execute("SELECT EXISTS(SELECT 1 FROM pg_proc p, LATERAL aclexplode(p.proacl) a WHERE p.oid=%s::regprocedure AND a.grantee=0) AS granted",(signature,)).fetchone()['granted']
    with connect(SCOPE) as conn:
        for permission in ('INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER'):
            assert not conn.execute('SELECT has_table_privilege(current_user,%s,%s) AS allowed',('aip_license_source_initialization_fence',permission)).fetchone()['allowed']
        with pytest.raises(LicenseSourceUnavailable,match='SCOPE_MISMATCH'),conn.transaction():
            authority.lock_license_source_initialization(conn,TenantScope('dev-org','dev-project'),ref(bundle))
        with pytest.raises(LicenseSourceUnavailable,match='EXACT_FROZEN_MISSING'),conn.transaction():
            authority.lock_license_source_initialization(conn,SCOPE,ref(bundle).model_copy(update={'content_hash':'d'*64}))
        assert initialization_lock(conn,bundle)==0
        conn.commit()
    with connect(TenantScope('dev-org','dev-project')) as conn:
        assert conn.execute('SELECT count(*) AS n FROM aip_license_source_initialization_fence WHERE bundle_id=%s',(bundle,)).fetchone()['n']==0
    assert coordination_epoch(admin,bundle)==0
