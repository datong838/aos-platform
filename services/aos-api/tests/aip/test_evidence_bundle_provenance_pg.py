"""Canonical build provenance is historical evidence, never a license grant."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict
from psycopg.types.json import Jsonb
from psycopg.rows import dict_row

from aos_api.aip_contracts import ResourceRef
from aos_api.aip_production_contract_store import AipProductionContractStore, canonical_hash
from aos_api.aip_production_contracts import BuildEvidenceBundleRequest, CreateBriefRequest, ExactRevisionRef
from aos_api.aip_task_models import CreateTaskRequest
from aos_api.aip_task_store import AipTaskStore
from aos_api.db import connect, get_dsn
from aos_api.tenant_scope import TenantScope

SCOPE=TenantScope('org-org','dev-project')
ACTOR='test:b85'


@contextmanager
def maintenance():
    assert conninfo_to_dict(get_dsn())['dbname'].startswith('aos_test_')
    with psycopg.connect(get_dsn(),row_factory=dict_row) as conn:
        conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",SCOPE.key)
        yield conn
        conn.rollback()


@pytest.fixture
def build_inputs():
    assert conninfo_to_dict(get_dsn())['dbname'].startswith('aos_test_')
    with connect() as conn:
        conn.execute("INSERT INTO twa_org(id,name) VALUES('org-org','test-only') ON CONFLICT DO NOTHING")
        conn.execute("INSERT INTO twa_workspace(org_id,project_id,name) VALUES('org-org','dev-project','test-only') ON CONFLICT DO NOTHING")
        conn.commit()
    key=uuid4().hex
    store=AipProductionContractStore()
    task=AipTaskStore().create_task(SCOPE,ACTOR,key+'.task',CreateTaskRequest(title='b85 build provenance'))
    brief=store.create_brief(SCOPE,ACTOR,key+'.brief',CreateBriefRequest(task_id=task.id,brief_type='ecommerce.analysis',schema_ref=ResourceRef(resource_type='Schema',resource_id='analysis',revision='1',authority='aip'),spec={'goal':'test-only'}))
    frozen=store.freeze_brief(SCOPE,ACTOR,brief.brief_id,brief.version,key+'.freeze')
    evidence=key+'.evidence'
    with connect(SCOPE) as conn:
        conn.execute("""INSERT INTO aip_evidence(org_id,project_id,evidence_id,evidence_type,
            subject_ref,source_type,source_ref,observed_at,freshness_at,content_hash,payload,created_by)
            VALUES(%s,%s,%s,'test-only','{}','database','test-only',NOW(),NOW(),%s,%s,%s)""",
            (*SCOPE.key,evidence,'c'*64,Jsonb({'factIds':['fact-a','fact-b']}),ACTOR))
        conn.commit()
    body=BuildEvidenceBundleRequest(brief_ref=ExactRevisionRef(resource_type='TaskBriefRevision',resource_id=frozen.brief_id,revision=frozen.revision,content_hash=frozen.content_hash),subject_refs=[],cutoff_at=datetime.now(timezone.utc)-timedelta(hours=1),item_refs=[ExactRevisionRef(resource_type='Evidence',resource_id=evidence,revision=1,content_hash='c'*64)],required_fact_ids=['fact-a'],license_summary={'test':'ordinary-no-grant'})
    return store,key,body


def test_original_required_fact_inputs_survive_build_and_reproduce_old_hash(build_inputs):
    store,key,body=build_inputs
    first=store.build_evidence_bundle(SCOPE,ACTOR,key,body)
    second=store.build_evidence_bundle(SCOPE,ACTOR,key+'.two',body.model_copy(update={'required_fact_ids':['fact-a','fact-b']}))
    # All old stored non-hash fields can be the same while required inputs differ.
    assert first.coverage==second.coverage and first.missing==second.missing==[]
    assert first.content_hash!=second.content_hash
    with connect(SCOPE) as conn:
        rows=conn.execute("SELECT * FROM public.aip_evidence_bundle_build_provenance WHERE org_id=%s AND project_id=%s AND bundle_id=ANY(%s) ORDER BY bundle_id",(*SCOPE.key,[first.bundle_id,second.bundle_id])).fetchall()
        assert len(rows)==2
        by_id={row['bundle_id']:row for row in rows}
        for bundle,required in ((first,['fact-a']),(second,['fact-a','fact-b'])):
            row=by_id[bundle.bundle_id]
            assert row['request_payload']['requiredFactIds']==required
            assert canonical_hash(row['request_payload'])==row['request_hash']
            assert canonical_hash(row['authority_payload'])==row['content_hash']==bundle.content_hash


def exact(bundle):
    return ExactRevisionRef(resource_type='EvidenceBundleRevision',resource_id=bundle.bundle_id,revision=bundle.revision,content_hash=bundle.content_hash)


def test_verified_reader_replay_canary_and_old_record_missing(build_inputs):
    from aos_api.evidence_bundle_provenance import read_build_provenance,BuildProvenanceUnavailable
    store,key,body=build_inputs
    bundle=store.build_evidence_bundle(SCOPE,ACTOR,key,body)
    assert store.create_evidence_bundle(SCOPE,ACTOR,key,body).bundle_id==bundle.bundle_id
    with connect(SCOPE) as conn:
        fact=read_build_provenance(conn,SCOPE,exact(bundle))
        assert fact.required_fact_ids==('fact-a',)
        assert fact.authorization=='BUILD_PROVENANCE_ONLY_NO_START'
        assert conn.execute('SELECT count(*) AS n FROM aip_evidence_bundle_build_provenance WHERE bundle_id=%s',(bundle.bundle_id,)).fetchone()['n']==1
        with pytest.raises(BuildProvenanceUnavailable,match='MISSING'):
            read_build_provenance(conn,SCOPE,exact(bundle).model_copy(update={'content_hash':'d'*64}))
        with pytest.raises(BuildProvenanceUnavailable,match='SCOPE_MISMATCH'):
            read_build_provenance(conn,TenantScope('dev-org','dev-project'),exact(bundle))
        # Owner fixture inserts an ordinary historical exact source with no original input.
        columns=conn.execute('SELECT * FROM aip_evidence_bundle_revision WHERE bundle_id=%s',(bundle.bundle_id,)).fetchone()
        legacy=bundle.bundle_id+'.legacy'
        names=list(columns)
        values=[columns[name] for name in names]
        values[names.index('bundle_id')]=legacy
        from psycopg import sql
        values=[Jsonb(v) if isinstance(v,(list,dict)) else v for v in values]
        conn.execute(sql.SQL('INSERT INTO aip_evidence_bundle_revision ({}) VALUES ({})').format(sql.SQL(',').join(map(sql.Identifier,names)),sql.SQL(',').join(sql.Placeholder() for _ in names)),values)
        with pytest.raises(BuildProvenanceUnavailable,match='MISSING'):
            read_build_provenance(conn,SCOPE,exact(bundle).model_copy(update={'resource_id':legacy}))
    with connect(TenantScope('dev-org','dev-project')) as conn:
        with pytest.raises(BuildProvenanceUnavailable,match='MISSING'):
            read_build_provenance(conn,TenantScope('dev-org','dev-project'),exact(bundle))


@pytest.mark.parametrize('command',['UPDATE aip_evidence_bundle_build_provenance SET request_payload=request_payload WHERE bundle_id=%s',
                                 'DELETE FROM aip_evidence_bundle_build_provenance WHERE bundle_id=%s',
                                 'TRUNCATE aip_evidence_bundle_build_provenance'])
def test_history_is_immutable_for_maintenance(build_inputs,command):
    store,key,body=build_inputs
    bundle=store.build_evidence_bundle(SCOPE,ACTOR,key,body)
    with maintenance() as conn:
        with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState,match='AIP6_REGISTRY_APPEND_ONLY'),conn.transaction():
            conn.execute(command,(bundle.bundle_id,) if '%s' in command else None)


def test_runtime_acl_rls_and_cross_scope_write_fail(build_inputs):
    store,key,body=build_inputs
    bundle=store.build_evidence_bundle(SCOPE,ACTOR,key,body)
    with connect(SCOPE) as conn:
        row=conn.execute('SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid=%s::regclass',('aip_evidence_bundle_build_provenance',)).fetchone()
        assert row==dict(relrowsecurity=True,relforcerowsecurity=True)
        assert not conn.execute("SELECT EXISTS(SELECT 1 FROM pg_class c, LATERAL aclexplode(c.relacl) a WHERE c.oid='aip_evidence_bundle_build_provenance'::regclass AND a.grantee=0) AS granted").fetchone()['granted']
        conn.execute('SET LOCAL ROLE aos_runtime')
        for permission in ('UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER'):
            assert not conn.execute('SELECT has_table_privilege(current_user,%s,%s) AS allowed',('aip_evidence_bundle_build_provenance',permission)).fetchone()['allowed']
        assert conn.execute('SELECT count(*) AS n FROM aip_evidence_bundle_build_provenance WHERE bundle_id=%s',(bundle.bundle_id,)).fetchone()['n']==1
        # Actual INSERT is attempted with same source/receipt; tenant mismatch fails RLS before conflict.
        with pytest.raises(psycopg.errors.InsufficientPrivilege),conn.transaction():
            conn.execute("""INSERT INTO aip_evidence_bundle_build_provenance SELECT
                'dev-org',project_id,bundle_id,revision,content_hash,operation,idempotency_key,
                request_hash,request_payload,authority_payload,created_at
                FROM aip_evidence_bundle_build_provenance WHERE bundle_id=%s""",(bundle.bundle_id,))
        conn.execute("SELECT set_config('aos.org_id','dev-org',true)")
        assert conn.execute('SELECT count(*) AS n FROM aip_evidence_bundle_build_provenance WHERE bundle_id=%s',(bundle.bundle_id,)).fetchone()['n']==0
        conn.execute("SELECT set_config('aos.org_id','',true)")
        assert conn.execute('SELECT count(*) AS n FROM aip_evidence_bundle_build_provenance WHERE bundle_id=%s',(bundle.bundle_id,)).fetchone()['n']==0


def test_provenance_failure_rolls_back_bundle_and_both_receipts(build_inputs,monkeypatch):
    import aos_api.evidence_bundle_provenance as provenance
    store,key,body=build_inputs
    original=provenance.append_build_provenance
    captured=[]
    def fail_after_insert(conn,scope,bundle_id,*args):
        assert original(conn,scope,bundle_id,*args)
        captured.append(bundle_id)
        assert conn.execute('SELECT count(*) AS n FROM aip_production_contract_receipt WHERE idempotency_key=%s',(key,)).fetchone()['n']==2
        raise ValueError('b85 precommit fault')
    monkeypatch.setattr(provenance,'append_build_provenance',fail_after_insert)
    with pytest.raises(ValueError,match='precommit fault'):
        store.build_evidence_bundle(SCOPE,ACTOR,key,body)
    with connect(SCOPE) as conn:
        for table in ('aip_evidence_bundle_revision','aip_evidence_bundle_build_provenance'):
            assert conn.execute('SELECT count(*) AS n FROM '+table+' WHERE bundle_id=%s',(captured[0],)).fetchone()['n']==0
        assert conn.execute('SELECT count(*) AS n FROM aip_production_contract_receipt WHERE idempotency_key=%s',(key,)).fetchone()['n']==0


@pytest.mark.parametrize('field',['request_hash','result_ref'])
def test_reader_rejects_receipt_drift_without_rewriting_history(build_inputs,field):
    from aos_api.evidence_bundle_provenance import read_build_provenance,BuildProvenanceUnavailable
    store,key,body=build_inputs
    bundle=store.build_evidence_bundle(SCOPE,ACTOR,key,body)
    # Maintenance mutation exposes a missing guard in the old Receipt domain;
    # new reader must refuse it. This remains only in the disposable fixture.
    with maintenance() as conn:
        with conn.transaction():
            from psycopg import sql
            conn.execute(sql.SQL("UPDATE aip_production_contract_receipt SET {}=%s WHERE operation='evidence_bundle.build' AND idempotency_key=%s").format(sql.Identifier(field)),('d'*64 if field=='request_hash' else Jsonb({}),key))
            with pytest.raises(BuildProvenanceUnavailable,match='RECEIPT_MISMATCH'):
                read_build_provenance(conn,SCOPE,exact(bundle))
        conn.rollback()


def test_reader_rejects_source_field_drift(build_inputs):
    from aos_api.evidence_bundle_provenance import read_build_provenance,BuildProvenanceUnavailable
    store,key,body=build_inputs
    bundle=store.build_evidence_bundle(SCOPE,ACTOR,key,body)
    with maintenance() as conn:
        conn.execute("UPDATE aip_evidence_bundle_revision SET license_summary='{}' WHERE bundle_id=%s",(bundle.bundle_id,))
        with pytest.raises(BuildProvenanceUnavailable,match='SOURCE_FIELDS_MISMATCH'):
            read_build_provenance(conn,SCOPE,exact(bundle))
        conn.rollback()


@pytest.mark.parametrize('fault,reason',[
    ('request_hash','REQUEST_HASH_MISMATCH'),
    ('invalid_input','INPUT_INVALID'),
    ('not_canonical','INPUT_NOT_CANONICAL'),
    ('authority_payload','AUTHORITY_HASH_MISMATCH'),
])
def test_reader_rejects_forged_inserted_history(build_inputs,fault,reason):
    from aos_api.evidence_bundle_provenance import read_build_provenance,BuildProvenanceUnavailable
    from psycopg import sql
    store,key,body=build_inputs
    bundle=store.build_evidence_bundle(SCOPE,ACTOR,key,body)
    # Maintenance-only copy creates another exact parent and build Receipt.
    # No guard is disabled; immutable original provenance is never changed.
    forged=bundle.bundle_id+'.forged'
    with maintenance() as conn:
        source=conn.execute('SELECT * FROM aip_evidence_bundle_revision WHERE bundle_id=%s',(bundle.bundle_id,)).fetchone()
        source['bundle_id']=forged
        names=list(source)
        conn.execute(sql.SQL('INSERT INTO aip_evidence_bundle_revision ({}) VALUES ({})').format(sql.SQL(',').join(map(sql.Identifier,names)),sql.SQL(',').join(sql.Placeholder() for _ in names)),[Jsonb(v) if isinstance(v,(list,dict)) else v for v in source.values()])
        row=conn.execute('SELECT * FROM aip_evidence_bundle_build_provenance WHERE bundle_id=%s',(bundle.bundle_id,)).fetchone()
        row['bundle_id']=forged
        row['idempotency_key']=key+'.forged'
        if fault=='request_hash':
            row['request_hash']='d'*64
        elif fault=='invalid_input':
            row['request_payload']['requiredFactIds']=[]
        elif fault=='not_canonical':
            row['request_payload']['requiredFactIds']=[' fact-a ']
        else:
            row['authority_payload']['requiredFactIds']=['fact-b']
        conn.execute("""INSERT INTO aip_production_contract_receipt(org_id,project_id,receipt_id,
            operation,idempotency_key,request_hash,result_ref,created_by)
            VALUES(%s,%s,%s,'evidence_bundle.build',%s,%s,%s,%s)""",(*SCOPE.key,key+'.receipt',row['idempotency_key'],row['request_hash'],Jsonb(dict(resourceType='EvidenceBundleRevision',resourceId=forged,revision=1,contentHash=bundle.content_hash)),ACTOR))
        names=list(row)
        conn.execute(sql.SQL('INSERT INTO aip_evidence_bundle_build_provenance ({}) VALUES ({})').format(sql.SQL(',').join(map(sql.Identifier,names)),sql.SQL(',').join(sql.Placeholder() for _ in names)),[Jsonb(v) if isinstance(v,(list,dict)) else v for v in row.values()])
        with pytest.raises(BuildProvenanceUnavailable,match=reason):
            read_build_provenance(conn,SCOPE,exact(bundle).model_copy(update={'resource_id':forged}))


def test_pre_migration_build_and_replay_do_not_retrofit_original_input(build_inputs):
    from aos_api.evidence_bundle_provenance import read_build_provenance,BuildProvenanceUnavailable
    store,key,body=build_inputs
    # Rename only this session-owned DB's new table, not any shared/current DB.
    with psycopg.connect(get_dsn(),autocommit=True) as admin:
        admin.execute('ALTER TABLE aip_evidence_bundle_build_provenance RENAME TO b85_provenance_held')
        try:
            bundle=store.build_evidence_bundle(SCOPE,ACTOR,key,body)
            with connect(SCOPE) as conn:
                with pytest.raises(BuildProvenanceUnavailable,match='SCHEMA_UNAVAILABLE'):
                    read_build_provenance(conn,SCOPE,exact(bundle))
        finally:
            admin.execute('ALTER TABLE b85_provenance_held RENAME TO aip_evidence_bundle_build_provenance')
    assert store.build_evidence_bundle(SCOPE,ACTOR,key,body).bundle_id==bundle.bundle_id
    with connect(SCOPE) as conn:
        with pytest.raises(BuildProvenanceUnavailable,match='MISSING'):
            read_build_provenance(conn,SCOPE,exact(bundle))


@pytest.mark.parametrize('fault',['source_hash','receipt_key'])
def test_provenance_exact_parent_links_cannot_be_detached(build_inputs,fault):
    store,key,body=build_inputs
    bundle=store.build_evidence_bundle(SCOPE,ACTOR,key,body)
    with maintenance() as conn:
        fresh_key=key+'.parent-test'
        conn.execute("""INSERT INTO aip_production_contract_receipt
            SELECT org_id,project_id,%s,operation,%s,request_hash,result_ref,created_by,created_at
            FROM aip_production_contract_receipt
            WHERE operation='evidence_bundle.build' AND idempotency_key=%s""",(key+'.parent-receipt',fresh_key,key))
        parent_id=bundle.bundle_id
        if fault=='receipt_key':
            # A second valid exact parent avoids an unrelated provenance PK conflict.
            from psycopg import sql
            source=conn.execute('SELECT * FROM aip_evidence_bundle_revision WHERE bundle_id=%s',(bundle.bundle_id,)).fetchone()
            parent_id=bundle.bundle_id+'.parent'
            source['bundle_id']=parent_id
            names=list(source)
            conn.execute(sql.SQL('INSERT INTO aip_evidence_bundle_revision ({}) VALUES ({})').format(sql.SQL(',').join(map(sql.Identifier,names)),sql.SQL(',').join(sql.Placeholder() for _ in names)),[Jsonb(v) if isinstance(v,(list,dict)) else v for v in source.values()])
        with pytest.raises(psycopg.errors.ForeignKeyViolation),conn.transaction():
            conn.execute("""INSERT INTO aip_evidence_bundle_build_provenance
                SELECT org_id,project_id,%s,revision,%s,operation,%s,request_hash,
                    request_payload,authority_payload,created_at
                FROM aip_evidence_bundle_build_provenance WHERE bundle_id=%s""",
                (parent_id,'d'*64 if fault=='source_hash' else bundle.content_hash,
                 fresh_key if fault=='source_hash' else fresh_key+'.absent',bundle.bundle_id))


def test_present_table_permission_failure_is_not_legacy_fallback(build_inputs):
    store,key,body=build_inputs
    with connect(SCOPE) as conn:
        before=conn.execute('SELECT count(*) AS n FROM aip_evidence_bundle_revision WHERE created_by=%s',(ACTOR,)).fetchone()['n']
    with psycopg.connect(get_dsn(),autocommit=True) as admin:
        admin.execute('REVOKE INSERT ON aip_evidence_bundle_build_provenance FROM aos_runtime')
        try:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                store.build_evidence_bundle(SCOPE,ACTOR,key,body)
        finally:
            admin.execute('GRANT INSERT ON aip_evidence_bundle_build_provenance TO aos_runtime')
    with connect(SCOPE) as conn:
        assert conn.execute('SELECT count(*) AS n FROM aip_evidence_bundle_revision WHERE created_by=%s',(ACTOR,)).fetchone()['n']==before
        assert conn.execute('SELECT count(*) AS n FROM aip_production_contract_receipt WHERE idempotency_key=%s',(key,)).fetchone()['n']==0
