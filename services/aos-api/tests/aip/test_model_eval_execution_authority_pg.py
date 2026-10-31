"""Native private storage checks; these do not prove a signed execution."""
import hashlib

import psycopg
import pytest
from psycopg import sql

from aos_api.db import get_dsn
from psycopg.rows import tuple_row

OWNER = 'aos_model_eval_execution_owner'
SCHEMA = 'aos_model_eval_execution_private'
TABLES = ('manifest', 'case_result', 'obligation_event', 'report_link')

def _native_certificate_interval():
    """Fresh test input from real DB clock; production clock stays unchanged."""
    from datetime import timedelta
    with psycopg.connect(get_dsn(), row_factory=tuple_row) as conn:
        conn.read_only = True
        now = conn.execute('SELECT clock_timestamp()').fetchone()[0]
        conn.rollback()
    return dict(valid_from=now-timedelta(minutes=5), valid_until=now+timedelta(minutes=25))


def test_persisted_model_certificate_bytes_signature_and_current_epochs():
    import json,importlib,base64
    from tests.aip.test_model_eval_execution_contracts import _issuer_signature_inputs
    from aos_api.aip_model_eval_execution_contracts import ModelEvalIssuerVerificationInput,ModelEvalExecutorCertificateSigningInput
    from aos_api.aip_contracts import TenantContext
    reader=importlib.import_module('aos_api.aip_model_eval_execution_reader')
    plan,cert,root,sig=_issuer_signature_inputs(**_native_certificate_interval())
    def encode(value):return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
    plan_bytes=encode(plan.model_dump(mode='json',by_alias=True));plan_hash=hashlib.sha256(plan_bytes).hexdigest()
    root_bytes=encode(ModelEvalIssuerVerificationInput.model_validate(root).model_dump(mode='json',by_alias=True));root_hash=hashlib.sha256(root_bytes).hexdigest()
    claim=ModelEvalExecutorCertificateSigningInput.model_validate(cert).model_dump(mode='json',by_alias=True)
    envelope=dict(schemaVersion='aos.model-eval-signed-certificate-envelope/v1',certificate=claim,signatureBase64=sig)
    cert_bytes=encode(envelope);cert_hash=hashlib.sha256(cert_bytes).hexdigest()
    args=dict(expected_tenant=TenantContext(orgId='org-org',projectId='dev-project'),execution_id=plan.execution_id,manifest_hash=plan_hash,certificate_hash=cert_hash,root_hash=root_hash,expected_root_epoch=1,expected_certificate_epoch=1)
    def owned():
        c=psycopg.connect(get_dsn(),row_factory=tuple_row);c.execute('BEGIN ISOLATION LEVEL SERIALIZABLE')
        c.execute('SET LOCAL ROLE aos_model_eval_issuer_owner');c.execute("SET LOCAL aos.org_id='org-org'");c.execute("SET LOCAL aos.project_id='dev-project'");return c
    def put_cert(c,raw):
        digest=hashlib.sha256(raw).hexdigest()
        c.execute('INSERT INTO aos_model_eval_issuer_private.executor_certificate(org_id,project_id,execution_id,case_id,purpose,attempt,issuer_id,key_id,content_hash,body) VALUES (%s,%s,%s,%s,%s,1,%s,%s,%s,%s)',('org-org','dev-project',plan.execution_id,claim['caseId'],claim['purpose'],root['issuerId'],root['issuerKeyId'],digest,raw));return digest
    assert hasattr(reader,'validate_persisted_model_certificate'), 'persisted signed Model certificate reader missing'
    with owned() as c:
        c.execute('RESET ROLE');c.execute('SET LOCAL ROLE aos_model_eval_execution_owner')
        c.execute('INSERT INTO aos_model_eval_execution_private.manifest VALUES (%s,%s,%s,%s,%s)',('org-org','dev-project',plan.execution_id,plan_hash,plan_bytes))
        c.execute('RESET ROLE');c.execute('SET LOCAL ROLE aos_model_eval_issuer_owner')
        c.execute('INSERT INTO aos_model_eval_issuer_private.issuer_root(org_id,project_id,issuer_id,key_id,bootstrap_hash,content_hash,body) VALUES (%s,%s,%s,%s,%s,%s,%s)',('org-org','dev-project',root['issuerId'],root['issuerKeyId'],'a'*64,root_hash,root_bytes))
        c.execute('INSERT INTO aos_model_eval_issuer_private.issuer_epoch(org_id,project_id,issuer_id,key_id,epoch,root_hash) VALUES (%s,%s,%s,%s,1,%s)',('org-org','dev-project',root['issuerId'],root['issuerKeyId'],root_hash))
        for bad in (envelope|{'signatureBase64':base64.b64encode(bytes(64)).decode()},envelope|{'certificate':claim|{'caseId':'borrowed-case'}},envelope|{'trusted':True},envelope|{'certificate':claim|{'manifestHash':'f'*64}}):
            c.execute('SAVEPOINT bad_cert');digest=put_cert(c,encode(bad))
            with pytest.raises(ValueError):reader.validate_persisted_model_certificate(c,**(args|dict(certificate_hash=digest)))
            c.execute('ROLLBACK TO SAVEPOINT bad_cert');c.execute('RELEASE SAVEPOINT bad_cert')
        c.execute('SAVEPOINT noncanonical');digest=put_cert(c,json.dumps(envelope,indent=2).encode())
        with pytest.raises(ValueError):reader.validate_persisted_model_certificate(c,**(args|dict(certificate_hash=digest)))
        c.execute('ROLLBACK TO SAVEPOINT noncanonical');c.execute('RELEASE SAVEPOINT noncanonical')
        put_cert(c,cert_bytes);c.commit()
    with owned() as c:
        assert reader.validate_persisted_model_certificate(c,**args) is None
        for change in (dict(expected_root_epoch=True), dict(expected_certificate_epoch=0),
                       dict(manifest_hash='f'*64), dict(root_hash='f'*64), dict(execution_id='borrowed')):
            c.execute('SAVEPOINT bad_binding')
            with pytest.raises(ValueError): reader.validate_persisted_model_certificate(c, **(args | change))
            c.execute('ROLLBACK TO SAVEPOINT bad_binding'); c.execute('RELEASE SAVEPOINT bad_binding')
        for statement in (
            'DELETE FROM aos_model_eval_execution_private.manifest',
            'UPDATE aos_model_eval_execution_private.manifest SET body=body',
            'DELETE FROM aos_model_eval_execution_private.case_result',
            'SELECT * FROM aos_model_eval_execution_private.obligation_event',
            'SELECT * FROM aos_model_eval_execution_private.report_link',
        ):
            c.execute('SAVEPOINT closed_manifest')
            with pytest.raises(psycopg.errors.InsufficientPrivilege): c.execute(statement)
            c.execute('ROLLBACK TO SAVEPOINT closed_manifest'); c.execute('RELEASE SAVEPOINT closed_manifest')
        c.execute('SAVEPOINT canary_manifest')
        c.execute("SET LOCAL aos.org_id='dev-org'")
        assert c.execute('SELECT count(*) FROM aos_model_eval_execution_private.manifest').fetchone()[0] == 0
        with pytest.raises(ValueError): reader.validate_persisted_model_certificate(c, **args)
        c.execute('ROLLBACK TO SAVEPOINT canary_manifest'); c.execute('RELEASE SAVEPOINT canary_manifest')
        for role in ('aos_runtime','aos_model_eval_execution_owner','aos_app'):
            c.execute('SAVEPOINT bad_role');c.execute(sql.SQL('SET LOCAL ROLE {}').format(sql.Identifier(role)))
            with pytest.raises(ValueError):reader.validate_persisted_model_certificate(c,**args)
            c.execute('ROLLBACK TO SAVEPOINT bad_role');c.execute('RELEASE SAVEPOINT bad_role')
        c.rollback()
    with owned() as c:
        c.execute('INSERT INTO aos_model_eval_issuer_private.authority_withdrawal(org_id,project_id,event_id,certificate_hash,content_hash,body) VALUES (%s,%s,%s,%s,%s,%s)',('org-org','dev-project','signed-cert-withdraw',cert_hash,cert_hash,cert_bytes));c.commit()
    with owned() as c:
        with pytest.raises(ValueError):reader.validate_persisted_model_certificate(c,**args)
        c.rollback()
    with owned() as c:
        c.execute('INSERT INTO aos_model_eval_issuer_private.authority_withdrawal(org_id,project_id,event_id,issuer_id,key_id,content_hash,body) VALUES (%s,%s,%s,%s,%s,%s,%s)',('org-org','dev-project','signed-root-withdraw',root['issuerId'],root['issuerKeyId'],root_hash,root_bytes));c.commit()
    with owned() as c:
        with pytest.raises(ValueError):reader.validate_persisted_model_certificate(c,**args)
        c.rollback()


def test_model_certificate_epoch_real_commit_and_two_withdrawal_orders():
    import importlib,time
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from aos_api.aip_contracts import TenantContext
    reader=importlib.import_module('aos_api.aip_model_eval_execution_reader')
    tenant=TenantContext(orgId='org-org',projectId='dev-project')
    root_body=b'{"untrusted_certificate_epoch_root":true}';root_hash=hashlib.sha256(root_body).hexdigest()
    bodies={order:('untrusted certificate '+order).encode() for order in ('reader-first','writer-first')}
    hashes={order:hashlib.sha256(body).hexdigest() for order,body in bodies.items()}
    def owned():
        c=psycopg.connect(get_dsn(),row_factory=tuple_row);c.execute('BEGIN ISOLATION LEVEL SERIALIZABLE')
        c.execute('SET LOCAL ROLE aos_model_eval_issuer_owner');c.execute("SET LOCAL aos.org_id='org-org'");c.execute("SET LOCAL aos.project_id='dev-project'");c.execute("SET LOCAL statement_timeout='15s'");return c
    def args(order):return dict(expected_tenant=tenant,issuer_id='certificate-'+order,issuer_key_id='key',expected_epoch=1,root_hash=root_hash,certificate_hash=hashes[order],expected_certificate_epoch=1,execution_id='certificate-epoch-probe',case_id=order,purpose='target')
    def blocked(pid,by):
        until=time.monotonic()+8
        with psycopg.connect(get_dsn(),row_factory=tuple_row) as observer:
            while time.monotonic()<until:
                if by in observer.execute('SELECT pg_blocking_pids(%s)',(pid,)).fetchone()[0]:return
                time.sleep(.02)
        raise AssertionError('exact certificate PID block not observed')
    with owned() as c:
        assert c.execute("SELECT to_regclass('aos_model_eval_issuer_private.certificate_epoch')").fetchone()[0], 'Model certificate epoch missing'
        c.execute('RESET ROLE');c.execute('SET LOCAL ROLE aos_model_eval_execution_owner')
        c.execute('INSERT INTO aos_model_eval_execution_private.manifest VALUES (%s,%s,%s,%s,%s)',('org-org','dev-project','certificate-epoch-probe',root_hash,root_body))
        c.execute('RESET ROLE');c.execute('SET LOCAL ROLE aos_model_eval_issuer_owner')
        for order in bodies:
            issuer='certificate-'+order
            c.execute('INSERT INTO aos_model_eval_issuer_private.issuer_root(org_id,project_id,issuer_id,key_id,bootstrap_hash,content_hash,body) VALUES (%s,%s,%s,%s,%s,%s,%s)',('org-org','dev-project',issuer,'key','a'*64,root_hash,root_body))
            c.execute('INSERT INTO aos_model_eval_issuer_private.issuer_epoch(org_id,project_id,issuer_id,key_id,epoch,root_hash) VALUES (%s,%s,%s,%s,1,%s)',('org-org','dev-project',issuer,'key',root_hash))
            c.execute('INSERT INTO aos_model_eval_issuer_private.executor_certificate(org_id,project_id,execution_id,case_id,purpose,attempt,issuer_id,key_id,content_hash,body) VALUES (%s,%s,%s,%s,%s,1,%s,%s,%s,%s)',('org-org','dev-project','certificate-epoch-probe',order,'target',issuer,'key',hashes[order],bodies[order]))
        c.commit()
    def withdraw(c,order):
        c.execute('INSERT INTO aos_model_eval_issuer_private.authority_withdrawal(org_id,project_id,event_id,certificate_hash,content_hash,body) VALUES (%s,%s,%s,%s,%s,%s)',('org-org','dev-project','certificate-'+order+'-withdraw',hashes[order],hashes[order],bodies[order]))
    with owned() as c,ThreadPoolExecutor(max_workers=1) as pool:
        assert reader.read_model_certificate_epoch(c,**args('reader-first'))==(1,hashes['reader-first'])
        for change in (dict(case_id='other'),dict(purpose='judge'),dict(expected_certificate_epoch=True),dict(certificate_hash='f'*64)):
            with pytest.raises(ValueError):reader.read_model_certificate_epoch(c,**(args('reader-first')|change))
        ready=Event();pids=[]
        def writer():
            with owned() as w:pids.append(w.info.backend_pid);ready.set();withdraw(w,'reader-first');w.commit()
        pending=pool.submit(writer);assert ready.wait(8);blocked(pids[0],c.info.backend_pid);c.commit();pending.result(timeout=15)
    with owned() as c:
        with pytest.raises(reader.ModelExecutionPlanRejected,match='certificate epoch or binding drifted'):
            reader.read_model_certificate_epoch(c,**args('reader-first'))
        assert reader.read_model_issuer_epoch(c,**{k:v for k,v in args('reader-first').items() if k in ('expected_tenant','issuer_id','issuer_key_id','expected_epoch','root_hash')})==(1,root_hash)
        c.execute('SAVEPOINT reactivate')
        with pytest.raises(psycopg.errors.InsufficientPrivilege,match='MODEL_CERTIFICATE_EPOCH_TRANSITION'):
            c.execute('UPDATE aos_model_eval_issuer_private.certificate_epoch SET epoch=epoch+1,active_hash=certificate_hash WHERE certificate_hash=%s',(hashes['reader-first'],))
        c.execute('ROLLBACK TO SAVEPOINT reactivate');c.rollback()
    with owned() as w,owned() as stale,ThreadPoolExecutor(max_workers=1) as pool:
        stale.execute('SELECT 1');withdraw(w,'writer-first')
        pending=pool.submit(reader.read_model_certificate_epoch,stale,**args('writer-first'));blocked(stale.info.backend_pid,w.info.backend_pid);w.commit()
        with pytest.raises(reader.ModelExecutionPlanRejected) as error:pending.result(timeout=15)
        assert isinstance(error.value.__cause__,psycopg.errors.SerializationFailure);stale.rollback()


def test_model_issuer_epoch_real_commit_and_two_withdrawal_orders():
    import importlib,time
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from aos_api.aip_contracts import TenantContext
    reader=importlib.import_module('aos_api.aip_model_eval_execution_reader')
    tenant=TenantContext(orgId='org-org',projectId='dev-project')
    body=b'{"untrusted_epoch_probe":true}';digest=hashlib.sha256(body).hexdigest()
    def owned():
        conn=psycopg.connect(get_dsn(),row_factory=tuple_row)
        conn.execute('BEGIN ISOLATION LEVEL SERIALIZABLE')
        conn.execute("SET LOCAL ROLE aos_model_eval_issuer_owner")
        conn.execute("SET LOCAL aos.org_id='org-org'");conn.execute("SET LOCAL aos.project_id='dev-project'")
        conn.execute("SET LOCAL statement_timeout='15s'")
        return conn
    def args(issuer):return dict(expected_tenant=tenant,issuer_id=issuer,issuer_key_id='key',expected_epoch=1,root_hash=digest)
    def blocked(pid,by):
        until=time.monotonic()+8
        with psycopg.connect(get_dsn(),row_factory=tuple_row) as observer:
            while time.monotonic()<until:
                if by in observer.execute('SELECT pg_blocking_pids(%s)',(pid,)).fetchone()[0]:return
                time.sleep(.02)
        raise AssertionError('native exact PID blocking not observed')
    with owned() as bootstrap:
        assert bootstrap.execute("SELECT to_regclass('aos_model_eval_issuer_private.issuer_epoch')").fetchone()[0], 'Model issuer epoch missing'
        for issuer in ('epoch-reader-first','epoch-writer-first'):
            bootstrap.execute('INSERT INTO aos_model_eval_issuer_private.issuer_root(org_id,project_id,issuer_id,key_id,bootstrap_hash,content_hash,body) VALUES (%s,%s,%s,%s,%s,%s,%s)',('org-org','dev-project',issuer,'key','a'*64,digest,body))
            bootstrap.execute('INSERT INTO aos_model_eval_issuer_private.issuer_epoch(org_id,project_id,issuer_id,key_id,epoch,root_hash) VALUES (%s,%s,%s,%s,1,%s)',('org-org','dev-project',issuer,'key',digest))
        bootstrap.commit()
    def withdraw(conn,issuer):
        conn.execute('INSERT INTO aos_model_eval_issuer_private.authority_withdrawal(org_id,project_id,event_id,issuer_id,key_id,content_hash,body) VALUES (%s,%s,%s,%s,%s,%s,%s)',('org-org','dev-project',issuer+'-withdraw',issuer,'key',digest,body))
    with owned() as read_conn,ThreadPoolExecutor(max_workers=1) as pool:
        assert reader.read_model_issuer_epoch(read_conn,**args('epoch-reader-first'))==(1,digest)
        for changed in (dict(expected_epoch=True),dict(root_hash='bad'),dict(issuer_id=' padded'),
                        dict(expected_tenant=TenantContext(orgId='dev-org',projectId='dev-project'))):
            with pytest.raises(ValueError):reader.read_model_issuer_epoch(read_conn,**(args('epoch-reader-first')|changed))
        for role in ('aos_runtime',OWNER,'aos_app'):
            read_conn.execute('SAVEPOINT wrong_reader')
            read_conn.execute(sql.SQL('SET LOCAL ROLE {}').format(sql.Identifier(role)))
            with pytest.raises(reader.ModelExecutionPlanRejected,match='exact private Issuer SERIAL snapshot'):
                reader.read_model_issuer_epoch(read_conn,**args('epoch-reader-first'))
            read_conn.execute('ROLLBACK TO SAVEPOINT wrong_reader');read_conn.execute('RELEASE SAVEPOINT wrong_reader')
        for updates in ('epoch=3','epoch=0','root_hash=NULL'):
            read_conn.execute('SAVEPOINT transition')
            with pytest.raises(psycopg.errors.InsufficientPrivilege,match='MODEL_ISSUER_EPOCH_TRANSITION'):
                read_conn.execute('UPDATE aos_model_eval_issuer_private.issuer_epoch SET '+updates+" WHERE issuer_id='epoch-reader-first'")
            read_conn.execute('ROLLBACK TO SAVEPOINT transition');read_conn.execute('RELEASE SAVEPOINT transition')
        ready=Event();pid=[]
        def writer():
            with owned() as conn:
                pid.append(conn.info.backend_pid);ready.set();withdraw(conn,'epoch-reader-first');conn.commit()
        pending=pool.submit(writer);assert ready.wait(8)
        blocked(pid[0],read_conn.info.backend_pid)
        read_conn.commit();pending.result(timeout=15)
    with owned() as fresh:
        with pytest.raises(reader.ModelExecutionPlanRejected,match='epoch or root drifted'):
            reader.read_model_issuer_epoch(fresh,**args('epoch-reader-first'))
        fresh.execute('SAVEPOINT reactivation')
        with pytest.raises(psycopg.errors.InsufficientPrivilege,match='MODEL_ISSUER_EPOCH_TRANSITION'):
            fresh.execute("UPDATE aos_model_eval_issuer_private.issuer_epoch SET epoch=epoch+1,root_hash=%s WHERE issuer_id='epoch-reader-first'",(digest,))
        fresh.execute('ROLLBACK TO SAVEPOINT reactivation');fresh.execute('RELEASE SAVEPOINT reactivation')
        fresh.rollback()
    with owned() as writer_conn,owned() as stale,ThreadPoolExecutor(max_workers=1) as pool:
        stale.execute('SELECT 1')  # establish old SERIAL snapshot before withdrawal
        withdraw(writer_conn,'epoch-writer-first')
        pending=pool.submit(reader.read_model_issuer_epoch,stale,**args('epoch-writer-first'))
        blocked(stale.info.backend_pid,writer_conn.info.backend_pid)
        writer_conn.commit()
        with pytest.raises(reader.ModelExecutionPlanRejected) as error:pending.result(timeout=15)
        assert isinstance(error.value.__cause__,psycopg.errors.SerializationFailure)
        stale.rollback()


def test_model_issuer_history_has_independent_closed_owner_and_native_boundaries():
    issuer_owner='aos_model_eval_issuer_owner'
    issuer_schema='aos_model_eval_issuer_private'
    tables=('issuer_root','executor_certificate','authority_withdrawal')
    with psycopg.connect(get_dsn(),row_factory=tuple_row) as conn:
        conn.execute('BEGIN ISOLATION LEVEL SERIALIZABLE')
        assert conn.execute('SELECT to_regnamespace(%s)',(issuer_schema,)).fetchone()[0], 'independent Model Issuer storage missing'
        assert conn.execute('SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname=%s',(issuer_owner,)).fetchone()==(False,)*7
        assert conn.execute('SELECT count(*) FROM pg_auth_members WHERE roleid=%s::regrole OR member=%s::regrole',(issuer_owner,issuer_owner)).fetchone()[0]==0
        for table in tables:
            relation=f'{issuer_schema}.{table}'
            assert conn.execute('SELECT relowner::regrole::text,relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid=%s::regclass',(relation,)).fetchone()==(issuer_owner,True,True)
            assert conn.execute(sql.SQL('SELECT count(*) FROM {}.{}').format(sql.Identifier(issuer_schema),sql.Identifier(table))).fetchone()[0]==0
        for role in ('aos_runtime',OWNER,'aos_provider_capacity_issuer'):
            conn.execute(sql.SQL('SET LOCAL ROLE {}').format(sql.Identifier(role)))
            for table in tables:
                for template in ('SELECT * FROM {}.{}','INSERT INTO {}.{} DEFAULT VALUES','UPDATE {}.{} SET org_id=org_id WHERE false','DELETE FROM {}.{} WHERE false','TRUNCATE {}.{}'):
                    conn.execute('SAVEPOINT deny')
                    with pytest.raises(psycopg.errors.InsufficientPrivilege):
                        conn.execute(sql.SQL(template).format(sql.Identifier(issuer_schema),sql.Identifier(table)))
                    conn.execute('ROLLBACK TO SAVEPOINT deny');conn.execute('RELEASE SAVEPOINT deny')
            conn.execute('RESET ROLE')
        # These bytes are deliberately untrusted storage probes, never issued roots.
        body=b'{"untrusted_storage_probe":true}';digest=hashlib.sha256(body).hexdigest()
        conn.execute(sql.SQL('SET LOCAL ROLE {}').format(sql.Identifier(OWNER)))
        conn.execute("SET LOCAL aos.org_id='org-org'");conn.execute("SET LOCAL aos.project_id='dev-project'")
        conn.execute(sql.SQL('INSERT INTO {}.manifest VALUES (%s,%s,%s,%s,%s)').format(sql.Identifier(SCHEMA)),('org-org','dev-project','issuer-probe',digest,body))
        conn.execute('RESET ROLE');conn.execute(sql.SQL('SET LOCAL ROLE {}').format(sql.Identifier(issuer_owner)))
        root_query=sql.SQL('INSERT INTO {}.issuer_root(org_id,project_id,issuer_id,key_id,bootstrap_hash,content_hash,body) VALUES (%s,%s,%s,%s,%s,%s,%s)').format(sql.Identifier(issuer_schema))
        values=('org-org','dev-project','issuer','key','a'*64,digest,body)
        for scope in ('','dev-org'):
            conn.execute('SAVEPOINT scope');conn.execute("SELECT set_config('aos.org_id',%s,true)",(scope,))
            with pytest.raises(psycopg.errors.InsufficientPrivilege):conn.execute(root_query,values)
            conn.execute('ROLLBACK TO SAVEPOINT scope');conn.execute('RELEASE SAVEPOINT scope')
        conn.execute('SAVEPOINT bad_hash')
        with pytest.raises(psycopg.errors.CheckViolation):conn.execute(root_query,values[:5]+('0'*64,body))
        conn.execute('ROLLBACK TO SAVEPOINT bad_hash');conn.execute('RELEASE SAVEPOINT bad_hash')
        conn.execute(root_query,values)
        conn.execute(root_query,values[:2]+('no-head',)+values[3:])
        cert_query=sql.SQL('INSERT INTO {}.executor_certificate(org_id,project_id,execution_id,case_id,purpose,attempt,issuer_id,key_id,content_hash,body) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)').format(sql.Identifier(issuer_schema))
        cert=('org-org','dev-project','issuer-probe','case1','target',1,'issuer','key',digest,body)
        for index,value in ((2,'missing-plan'),(6,'missing-root')):
            bad=list(cert);bad[index]=value;conn.execute('SAVEPOINT orphan')
            with pytest.raises(psycopg.errors.ForeignKeyViolation):conn.execute(cert_query,bad)
            conn.execute('ROLLBACK TO SAVEPOINT orphan');conn.execute('RELEASE SAVEPOINT orphan')
        conn.execute('INSERT INTO aos_model_eval_issuer_private.issuer_epoch(org_id,project_id,issuer_id,key_id,epoch,root_hash) VALUES (%s,%s,%s,%s,1,%s)',('org-org','dev-project','issuer','key',digest))
        conn.execute(cert_query,cert)
        withdrawal=sql.SQL('INSERT INTO {}.authority_withdrawal(org_id,project_id,event_id,issuer_id,key_id,certificate_hash,content_hash,body) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)').format(sql.Identifier(issuer_schema))
        for middle,error in ((('issuer','key',digest),psycopg.errors.CheckViolation),(('missing','key',None),psycopg.errors.ForeignKeyViolation),((None,None,'f'*64),psycopg.errors.ForeignKeyViolation),(('no-head','key',None),psycopg.errors.InsufficientPrivilege)):
            conn.execute('SAVEPOINT withdraw')
            with pytest.raises(error):conn.execute(withdrawal,('org-org','dev-project','bad',*middle,digest,body))
            conn.execute('ROLLBACK TO SAVEPOINT withdraw');conn.execute('RELEASE SAVEPOINT withdraw')
        conn.execute(withdrawal,('org-org','dev-project','root-withdraw','issuer','key',None,digest,body))
        conn.execute(withdrawal,('org-org','dev-project','cert-withdraw',None,None,digest,digest,body))
        for table in tables:
            for template in ('UPDATE {}.{} SET org_id=org_id','DELETE FROM {}.{}','TRUNCATE {}.{} CASCADE'):
                conn.execute('SAVEPOINT immutable')
                with pytest.raises(psycopg.errors.InsufficientPrivilege,match='MODEL_ISSUER_HISTORY_IMMUTABLE'):
                    conn.execute(sql.SQL(template).format(sql.Identifier(issuer_schema),sql.Identifier(table)))
                conn.execute('ROLLBACK TO SAVEPOINT immutable');conn.execute('RELEASE SAVEPOINT immutable')
        conn.execute(sql.SQL('CREATE TABLE {}.future_probe(id integer)').format(sql.Identifier(issuer_schema)))
        conn.execute(sql.SQL("CREATE FUNCTION {}.future_probe_fn() RETURNS integer LANGUAGE sql AS 'SELECT 1'").format(sql.Identifier(issuer_schema)))
        conn.execute('RESET ROLE')
        for role in ('aos_runtime',OWNER,'aos_provider_capacity_issuer'):
            for privilege in ('SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER'):
                assert not conn.execute('SELECT has_table_privilege(%s,%s,%s)',(role,f'{issuer_schema}.future_probe',privilege)).fetchone()[0]
            assert not conn.execute('SELECT has_function_privilege(%s,%s,%s)',(role,f'{issuer_schema}.future_probe_fn()','EXECUTE')).fetchone()[0]
        conn.rollback()
    with psycopg.connect(get_dsn(),row_factory=tuple_row) as conn:
        conn.execute('BEGIN ISOLATION LEVEL SERIALIZABLE READ ONLY')
        for table in tables:
            assert conn.execute(sql.SQL('SELECT count(*) FROM {}.{}').format(sql.Identifier(issuer_schema),sql.Identifier(table))).fetchone()[0]==0
        conn.rollback()


def test_model_private_storage_native_boundary():
    with psycopg.connect(get_dsn(), row_factory=tuple_row) as conn:
        conn.execute('BEGIN ISOLATION LEVEL SERIALIZABLE')
        assert conn.execute('SELECT to_regnamespace(%s)', (SCHEMA,)).fetchone()[0], (
            'Model independent private storage is not installed'
        )
        role = conn.execute('SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,'
                            'rolcreaterole,rolreplication,rolbypassrls '
                            'FROM pg_roles WHERE rolname=%s', (OWNER,)).fetchone()
        assert role == (False,) * 7
        assert conn.execute('SELECT count(*) FROM pg_auth_members '
                            'WHERE roleid=%s::regrole OR member=%s::regrole',
                            (OWNER, OWNER)).fetchone()[0] == 0
        for table in TABLES:
            relation = f'{SCHEMA}.{table}'
            assert conn.execute('SELECT relowner::regrole::text,relrowsecurity,relforcerowsecurity '
                                'FROM pg_class WHERE oid=%s::regclass', (relation,)).fetchone() == (
                                    OWNER, True, True)
            assert conn.execute(sql.SQL('SELECT count(*) FROM {}.{}').format(
                sql.Identifier(SCHEMA), sql.Identifier(table))).fetchone()[0] == 0
        # A native runtime caller must not gain direct storage access.
        conn.execute('SET LOCAL ROLE aos_runtime')
        for table in TABLES:
            for operation in ('SELECT * FROM {}.{}', 'INSERT INTO {}.{} DEFAULT VALUES',
                              'UPDATE {}.{} SET org_id=org_id WHERE false',
                              'DELETE FROM {}.{} WHERE false', 'TRUNCATE {}.{}'):
                conn.execute('SAVEPOINT denied')
                try:
                    conn.execute(sql.SQL(operation).format(sql.Identifier(SCHEMA), sql.Identifier(table)))
                except psycopg.errors.InsufficientPrivilege:
                    conn.execute('ROLLBACK TO SAVEPOINT denied')
                else:
                    raise AssertionError(f'Runtime acquired access: {table}/{operation}')
                conn.execute('RELEASE SAVEPOINT denied')
        conn.execute('RESET ROLE')
        conn.execute(sql.SQL('SET LOCAL ROLE {}').format(sql.Identifier(OWNER)))
        conn.execute("SET LOCAL aos.org_id='org-org'")
        conn.execute("SET LOCAL aos.project_id='dev-project'")
        body = b'{"storage_probe":true}'  # Synthetic bytes, never an approved manifest.
        conn.execute(sql.SQL('INSERT INTO {}.manifest VALUES (%s,%s,%s,%s,%s)').format(
            sql.Identifier(SCHEMA)), ('org-org', 'dev-project', 'storage-probe',
                                    hashlib.sha256(body).hexdigest(), body))
        # No scope or canary scope may write, even through the Owner role.
        for bad_scope in ('', 'dev-org'):
            conn.execute('SAVEPOINT tenant_denied')
            conn.execute("SELECT set_config('aos.org_id',%s,true)", (bad_scope,))
            try:
                conn.execute(sql.SQL('INSERT INTO {}.manifest VALUES (%s,%s,%s,%s,%s)').format(
                    sql.Identifier(SCHEMA)), ('org-org', 'dev-project', 'bad-scope',
                                            hashlib.sha256(body).hexdigest(), body))
            except psycopg.errors.InsufficientPrivilege:
                conn.execute('ROLLBACK TO SAVEPOINT tenant_denied')
            else:
                raise AssertionError('Owner tenant scope was bypassed')
            conn.execute('RELEASE SAVEPOINT tenant_denied')
        conn.execute('SAVEPOINT hash_denied')
        try:
            conn.execute(sql.SQL('INSERT INTO {}.manifest VALUES (%s,%s,%s,%s,%s)').format(
                sql.Identifier(SCHEMA)), ('org-org', 'dev-project', 'bad-hash', '0' * 64, body))
        except psycopg.errors.CheckViolation:
            conn.execute('ROLLBACK TO SAVEPOINT hash_denied')
        else:
            raise AssertionError('Bytes/hash mismatch was stored')
        conn.execute('RELEASE SAVEPOINT hash_denied')
        for table in ('case_result', 'obligation_event', 'report_link'):
            extras = [] if table == 'report_link' else ['case1', 'target', 1]
            if table == 'obligation_event':
                extras.append('event1')
            values = ['org-org', 'dev-project', 'missing-manifest', *extras,
                      hashlib.sha256(body).hexdigest(), body]
            query = sql.SQL('INSERT INTO {}.{} VALUES ({})').format(
                sql.Identifier(SCHEMA), sql.Identifier(table),
                sql.SQL(',').join(sql.Placeholder() for _ in values))
            conn.execute('SAVEPOINT orphan_denied')
            try:
                conn.execute(query, values)
            except psycopg.errors.ForeignKeyViolation:
                conn.execute('ROLLBACK TO SAVEPOINT orphan_denied')
            else:
                raise AssertionError(f'Orphan proof was stored: {table}')
            conn.execute('RELEASE SAVEPOINT orphan_denied')
            values[2] = 'storage-probe'
            conn.execute(query, values)
        # Owner-created future objects do not inherit PUBLIC/runtime access.
        conn.execute(sql.SQL('CREATE TABLE {}.future_probe (id integer)').format(sql.Identifier(SCHEMA)))
        conn.execute(sql.SQL("CREATE FUNCTION {}.future_probe_fn() RETURNS integer LANGUAGE sql AS 'SELECT 1'").format(
            sql.Identifier(SCHEMA)))
        conn.execute('RESET ROLE')
        for grantee in ('aos_runtime', 'aos_provider_capacity_issuer'):
            for privilege in ('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER'):
                assert not conn.execute('SELECT has_table_privilege(%s,%s,%s)',
                    (grantee, f'{SCHEMA}.future_probe', privilege)).fetchone()[0]
            assert not conn.execute("SELECT has_function_privilege(%s,%s,'EXECUTE')",
                (grantee, f'{SCHEMA}.future_probe_fn()')).fetchone()[0]
        conn.execute(sql.SQL('SET LOCAL ROLE {}').format(sql.Identifier(OWNER)))
        for operation in ('UPDATE {}.manifest SET body=body', 'DELETE FROM {}.manifest',
                          'TRUNCATE {}.manifest CASCADE'):
            conn.execute('SAVEPOINT immutable')
            try:
                conn.execute(sql.SQL(operation).format(sql.Identifier(SCHEMA)))
            except psycopg.errors.InsufficientPrivilege:
                conn.execute('ROLLBACK TO SAVEPOINT immutable')
            else:
                raise AssertionError(f'Owner mutated immutable storage: {operation}')
            conn.execute('RELEASE SAVEPOINT immutable')
        for table in ('case_result', 'obligation_event', 'report_link'):
            for operation in ('UPDATE {}.{} SET body=body', 'DELETE FROM {}.{}', 'TRUNCATE {}.{}'):
                conn.execute('SAVEPOINT child_immutable')
                try:
                    conn.execute(sql.SQL(operation).format(sql.Identifier(SCHEMA), sql.Identifier(table)))
                except psycopg.errors.InsufficientPrivilege:
                    conn.execute('ROLLBACK TO SAVEPOINT child_immutable')
                else:
                    raise AssertionError(f'Owner mutated proof: {table}/{operation}')
                conn.execute('RELEASE SAVEPOINT child_immutable')
        conn.rollback()

    # An independent connection checks that the synthetic probe did not persist.
    with psycopg.connect(get_dsn(), row_factory=tuple_row) as conn:
        conn.execute('BEGIN ISOLATION LEVEL SERIALIZABLE READ ONLY')
        for table in TABLES:
            assert conn.execute(sql.SQL('SELECT count(*) FROM {}.{}').format(
                sql.Identifier(SCHEMA), sql.Identifier(table))).fetchone()[0] == 0
        conn.rollback()


def test_model_persisted_plan_reader_requires_exact_owner_snapshot():
    import importlib
    import json
    from aos_api.aip_contracts import TenantContext
    from tests.aip.test_model_eval_execution_contracts import _plan_body

    reader = importlib.import_module('aos_api.aip_model_eval_execution_reader')
    plan = _plan_body()  # Synthetic leg refs: never a trusted execution proof.
    body = json.dumps(plan, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    digest = hashlib.sha256(body).hexdigest()
    tenant = TenantContext(orgId='org-org', projectId='dev-project')
    with psycopg.connect(get_dsn(), row_factory=tuple_row) as conn:
        conn.execute('BEGIN ISOLATION LEVEL SERIALIZABLE')
        conn.execute(sql.SQL('SET LOCAL ROLE {}').format(sql.Identifier(OWNER)))
        conn.execute("SET LOCAL aos.org_id='org-org'")
        conn.execute("SET LOCAL aos.project_id='dev-project'")
        conn.execute(sql.SQL('INSERT INTO {}.manifest VALUES (%s,%s,%s,%s,%s)').format(
            sql.Identifier(SCHEMA)), (*('org-org', 'dev-project'), plan['executionId'], digest, body))
        args = dict(expected_tenant=tenant, execution_id=plan['executionId'], manifest_hash=digest)
        parsed = reader.read_model_execution_plan(conn, **args)
        assert parsed.execution_allowed is False
        assert parsed.model_dump(mode='json', by_alias=True) == plan
        for changed in (dict(execution_id='missing'), dict(manifest_hash='0' * 64),
                        dict(execution_id=' '+plan['executionId']),
                        dict(expected_tenant=TenantContext(orgId='dev-org', projectId='dev-project'))):
            with pytest.raises(reader.ModelExecutionPlanRejected):
                reader.read_model_execution_plan(conn, **(args | changed))
        for role, org in (('aos_runtime', 'org-org'), ('aos_app', 'org-org'), (OWNER, 'dev-org')):
            conn.execute('SAVEPOINT wrong_context')
            conn.execute(sql.SQL('SET LOCAL ROLE {}').format(sql.Identifier(role)))
            conn.execute("SELECT set_config('aos.org_id',%s,true)", (org,))
            with pytest.raises(reader.ModelExecutionPlanRejected):
                reader.read_model_execution_plan(conn, **args)
            conn.execute('ROLLBACK TO SAVEPOINT wrong_context')
            conn.execute('RELEASE SAVEPOINT wrong_context')
        # Storage hashes can be coherent for bytes which are not a strict plan.
        for ident, raw in (
            ('unknown-field', json.dumps(plan | {'executionId': 'unknown-field', 'trusted': True}).encode()),
            ('bad-typed', json.dumps(plan | {'executionId': 'bad-typed', 'schemaVersion': True}).encode()),
            ('header-drift', body),
            ('noncanonical', json.dumps(plan | {'executionId': 'noncanonical'}, indent=2).encode()),
            ('duplicate-key', b'{"schemaVersion":9,' + body.replace(b'"executionId":"test-plan"', b'"executionId":"duplicate-key"')[1:]),
        ):
            hashed = hashlib.sha256(raw).hexdigest()
            conn.execute(sql.SQL('INSERT INTO {}.manifest VALUES (%s,%s,%s,%s,%s)').format(
                sql.Identifier(SCHEMA)), ('org-org', 'dev-project', ident, hashed, raw))
            with pytest.raises(reader.ModelExecutionPlanRejected):
                reader.read_model_execution_plan(conn, **(args | dict(execution_id=ident, manifest_hash=hashed)))
        conn.rollback()
    with psycopg.connect(get_dsn(), row_factory=tuple_row) as conn:
        conn.execute('BEGIN ISOLATION LEVEL SERIALIZABLE READ ONLY')
        assert conn.execute(f'SELECT count(*) FROM {SCHEMA}.manifest').fetchone()[0] == 0
        conn.rollback()
    with psycopg.connect(get_dsn(), row_factory=tuple_row) as conn:
        conn.execute('BEGIN ISOLATION LEVEL READ COMMITTED')
        conn.execute(sql.SQL('SET LOCAL ROLE {}').format(sql.Identifier(OWNER)))
        conn.execute("SET LOCAL aos.org_id='org-org'")
        conn.execute("SET LOCAL aos.project_id='dev-project'")
        with pytest.raises(reader.ModelExecutionPlanRejected):
            reader.read_model_execution_plan(conn, **args)
        conn.rollback()
    # Same isolation label across two autocommit statements is not one snapshot.
    with psycopg.connect(get_dsn(), row_factory=tuple_row, autocommit=True) as conn:
        conn.execute(sql.SQL('SET ROLE {}').format(sql.Identifier(OWNER)))
        conn.execute("SET aos.org_id='org-org'")
        conn.execute("SET aos.project_id='dev-project'")
        conn.execute("SET default_transaction_isolation='serializable'")
        with pytest.raises(reader.ModelExecutionPlanRejected, match='caller transaction required'):
            reader.read_model_execution_plan(conn, **args)


def test_persisted_model_target_judge_case_bytes_and_current_certificates():
    _persisted_model_case_native(identity_gate=False)


def test_persisted_model_case_global_identity_currentness():
    _persisted_model_case_native(identity_gate=True)


@pytest.mark.parametrize('entry',['case','certificate','registration','executor-set','runtime-executor-set'])
@pytest.mark.parametrize('purpose',['target','judge'])
def test_model_identity_wait_rechecks_certificate_window(entry,purpose):
    _persisted_model_case_native(identity_gate=True,expiry_wait=(entry,purpose))


def test_runtime_target_result_identity_wait_rechecks_window():
    _persisted_model_case_native(identity_gate=True,expiry_wait=('runtime-target-result','target'))


def test_runtime_judge_input_identity_wait_rechecks_window():
    _persisted_model_case_native(identity_gate=True,expiry_wait=('runtime-judge-input','target'))


def test_target_result_identity_wait_rechecks_window():
    _persisted_model_case_native(identity_gate=True,expiry_wait=('target-result','target'))


def test_target_result_before_judge_native():
    _persisted_model_case_native(identity_gate=True,target_only=True)


def _persisted_model_case_native(*, identity_gate, expiry_wait=None,target_only=False):
    import importlib,json,base64,os
    from pathlib import Path
    from tests.aip.test_model_eval_execution_contracts import _signed_model_case_fixture
    from aos_api.aip_contracts import TenantContext
    from aos_api.aip_model_runtime_store import canonical_hash
    module,plan,root,certs,envelopes,claims,raw,keys=_signed_model_case_fixture(**_native_certificate_interval())
    reader=importlib.import_module('aos_api.aip_model_eval_execution_reader')
    assert hasattr(reader,'validate_persisted_model_case'), 'persisted signed Model case reader missing'
    def encode(value):return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
    def owned(role='aos_model_eval_issuer_owner'):
        c=psycopg.connect(get_dsn(),row_factory=tuple_row);c.execute('BEGIN ISOLATION LEVEL SERIALIZABLE')
        c.execute('SET LOCAL ROLE '+role);c.execute("SET LOCAL aos.org_id='org-org'");c.execute("SET LOCAL aos.project_id='dev-project'");return c
    def dump(value):return value.model_dump(mode='json',by_alias=True)
    # Distinct fixture identity avoids other retained durable samples.
    body=dump(plan);body['executionId']='target-before-judge-native' if target_only else ('signed-case-identity-native' if identity_gate else 'signed-case-native')
    expected_output=b'original expected output'
    if target_only or (expiry_wait and expiry_wait[0]=='runtime-judge-input'):
        body['cases'][0]['expectedHash']=hashlib.sha256(expected_output).hexdigest()
        body['caseSetHash']=canonical_hash([dict(caseId=x['caseId'],inputHash=x['inputHash'],expectedHash=x['expectedHash']) for x in body['cases']])
    if target_only:
        for purpose in ('target','judge'):body['cases'][0][purpose]['identityId']='target-before-judge-'+purpose
    if expiry_wait:
        body['executionId']='identity-wait-'+ '-'.join(expiry_wait)
        for purpose in ('target','judge'):body['cases'][0][purpose]['identityId']=body['executionId']+'-'+purpose
    plan=module.ModelEvalExecutionManifest.model_validate(body);plan_hash=canonical_hash(dump(plan))
    # Existing certificate signatures bind original execution. Generate new
    # issuer locally and re-sign exact adjusted certificates, never persist keys.
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
    issuer=Ed25519PrivateKey.generate();root['issuerId']='target-before-judge-issuer' if target_only else ('native-identity-case-issuer' if identity_gate else 'native-case-issuer')
    if expiry_wait:root['issuerId']=body['executionId']+'-issuer'
    root['publicKeyBase64']=base64.b64encode(issuer.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)).decode()
    root=module.ModelEvalIssuerVerificationInput.model_validate(root);root_bytes=encode(dump(root));root_hash=hashlib.sha256(root_bytes).hexdigest()
    expires=None
    if expiry_wait and not expiry_wait[0].startswith('runtime-withdrawal-'):
        from datetime import timedelta
        with psycopg.connect(get_dsn()) as clock:
            expires=clock.execute('SELECT clock_timestamp()').fetchone()[0]+timedelta(seconds=4)
    for purpose in ('target','judge'):
        cert=dump(certs[purpose].certificate);cert.update(executionId=plan.execution_id,manifestHash=plan_hash,issuerId=root.issuer_id,leg=dump(getattr(plan.cases[0],purpose)))
        if expires is not None and purpose==expiry_wait[1]:cert['validUntil']=expires
        certs[purpose]=module.ModelEvalSignedCertificateEnvelope.model_validate(dict(schemaVersion='aos.model-eval-signed-certificate-envelope/v1',certificate=cert,
            signatureBase64=base64.b64encode(issuer.sign(module.canonical_model_certificate_signing_bytes(plan,cert))).decode()))
    with owned() as c:
        c.execute('RESET ROLE');c.execute('SET LOCAL ROLE aos_model_eval_execution_owner')
        c.execute('INSERT INTO aos_model_eval_execution_private.manifest VALUES (%s,%s,%s,%s,%s)',('org-org','dev-project',plan.execution_id,plan_hash,encode(dump(plan))))
        c.execute('RESET ROLE');c.execute('SET LOCAL ROLE aos_model_eval_issuer_owner')
        c.execute('INSERT INTO aos_model_eval_issuer_private.issuer_root(org_id,project_id,issuer_id,key_id,bootstrap_hash,content_hash,body) VALUES (%s,%s,%s,%s,%s,%s,%s)',('org-org','dev-project',root.issuer_id,root.issuer_key_id,'a'*64,root_hash,root_bytes))
        c.execute('INSERT INTO aos_model_eval_issuer_private.issuer_epoch(org_id,project_id,issuer_id,key_id,epoch,root_hash) VALUES (%s,%s,%s,%s,1,%s)',('org-org','dev-project',root.issuer_id,root.issuer_key_id,root_hash))
        for purpose in ('target','judge'):
            certbytes=encode(dump(certs[purpose]));digest=hashlib.sha256(certbytes).hexdigest()
            c.execute('INSERT INTO aos_model_eval_issuer_private.executor_certificate(org_id,project_id,execution_id,case_id,purpose,attempt,issuer_id,key_id,content_hash,body) VALUES (%s,%s,%s,%s,%s,1,%s,%s,%s,%s)',('org-org','dev-project',plan.execution_id,'case-1',purpose,root.issuer_id,root.issuer_key_id,digest,certbytes))
        c.commit()
    if expiry_wait and expiry_wait[0].startswith('runtime-withdrawal-'):
        _runtime_executor_identity_withdrawal_native(module,reader,plan,plan_hash,root_hash,certs,expiry_wait[1],owned,order=expiry_wait[0].removeprefix('runtime-withdrawal-'))
        return
    if expiry_wait and expiry_wait[0] in ('executor-set','runtime-executor-set'):
        _executor_set_identity_window_native(module,reader,plan,plan_hash,root_hash,certs,expires,expiry_wait[1],owned,entry=expiry_wait[0])
        return
    bindings={}
    with owned() as c:
        for purpose in ('target','judge'):
            claim=dump(claims[purpose]);claim.update(executionId=plan.execution_id,manifestHash=plan_hash,leg=dump(getattr(plan.cases[0],purpose)),occurredAt=c.execute('SELECT clock_timestamp()').fetchone()[0])
            if purpose=='judge':
                claim['expectedHash']=plan.cases[0].expected_hash
                target=module.canonical_model_case_signing_bytes(plan,claims['target'],input_bytes=raw['target'][0],output_bytes=raw['target'][1])
                claim['targetClaimHash']=hashlib.sha256(target).hexdigest()
            claims[purpose]=module.ModelEvalCaseSigningInput.model_validate(claim)
            payload=module.ModelEvalCaseSignaturePayload.model_validate(dict(schemaVersion='aos.model-eval-case-signature-payload/v1',certificateHash=canonical_hash(dump(certs[purpose])),claim=claims[purpose]))
            signing=module.canonical_model_signed_case_bytes(plan,payload,input_bytes=raw[purpose][0],output_bytes=raw[purpose][1],target_claim=claims['target'] if purpose=='judge' else None)
            envelopes[purpose]=module.ModelEvalSignedCaseEnvelope.model_validate(dict(schemaVersion='aos.model-eval-signed-case-envelope/v1',payload=payload,signatureBase64=base64.b64encode(keys[purpose].sign(signing)).decode()))
            bindings[purpose]=dict(caseHash=canonical_hash(dump(envelopes[purpose])),certificateHash=canonical_hash(dump(certs[purpose])),rootHash=root_hash,rootEpoch=1,certificateEpoch=1)
        c.rollback()
    args=dict(expected_tenant=TenantContext(orgId='org-org',projectId='dev-project'),execution_id=plan.execution_id,manifest_hash=plan_hash,case_id='case-1',target_binding=bindings['target'],judge_binding=bindings['judge'],target_input=raw['target'][0],target_output=raw['target'][1],judge_input=raw['judge'][0],judge_output=raw['judge'][1])
    def put_case(c,purpose,value):
        encoded=value if type(value) is bytes else encode(value);digest=hashlib.sha256(encoded).hexdigest()
        c.execute('INSERT INTO aos_model_eval_execution_private.case_result VALUES (%s,%s,%s,%s,%s,1,%s,%s)',('org-org','dev-project',plan.execution_id,'case-1',purpose,digest,encoded));return digest
    if target_only:
        authority=importlib.import_module('aos_api.aip_model_eval_execution_authority')
        with psycopg.connect(get_dsn()) as c:
            if c.execute("SELECT to_regclass('aos_model_eval_issuer_private.identity_epoch')").fetchone()[0] is None:authority.install_closed_model_identity_authority(c.execute)
            if c.execute("SELECT to_regprocedure('public.read_model_executor_set_facts(text,text)')").fetchone()[0] is None:
                for statement in authority.runtime_executor_fact_statements():c.execute(statement)
            for statement in authority.runtime_target_fact_statements():c.execute(statement)
            if hasattr(authority,'target_origin_statements'):
                for statement in authority.target_origin_statements():c.execute(statement)
            c.commit()
        witnesses=tuple(dict(caseId='case-1',purpose=purpose,certificateHash=bindings[purpose]['certificateHash'],rootHash=root_hash,rootEpoch=1,certificateEpoch=1,identityEpoch=1) for purpose in ('target','judge'))
        pending_args={k:v for k,v in args.items() if not k.startswith('judge')}|dict(certificates=witnesses)
        with owned('aos_model_eval_execution_owner') as c:
            put_case(c,'target',dump(envelopes['target']));target_xid=c.execute('SELECT pg_current_xact_id()::text').fetchone()[0]
            c.execute('RESET ROLE');c.execute('SET LOCAL ROLE aos_model_eval_issuer_owner')
            for purpose in ('target','judge'):
                reader.register_persisted_model_identity(c,expected_tenant=args['expected_tenant'],execution_id=plan.execution_id,manifest_hash=plan_hash,certificate_hash=bindings[purpose]['certificateHash'],root_hash=root_hash,expected_root_epoch=1,expected_certificate_epoch=1)
            c.execute('RESET ROLE');c.execute('SET LOCAL ROLE aos_runtime');c.execute('SAVEPOINT uncommitted_target')
            with pytest.raises(ValueError,match='Target facts'):reader.validate_runtime_model_target_result(c,**pending_args)
            c.execute('ROLLBACK TO SAVEPOINT uncommitted_target')
            c.execute('RESET ROLE');c.execute('SET LOCAL ROLE aos_model_eval_execution_owner');c.execute('SAVEPOINT origin_rollback_probe')
            probe=b'{}';c.execute('INSERT INTO aos_model_eval_execution_private.case_result VALUES (%s,%s,%s,%s,%s,1,%s,%s)',('org-org','dev-project',plan.execution_id,'origin-rollback-probe','target',hashlib.sha256(probe).hexdigest(),probe))
            c.execute('RESET ROLE');c.execute('SET LOCAL ROLE aos_model_eval_issuer_owner')
            assert c.execute("SELECT count(*) FROM aos_model_eval_issuer_private.target_result_origin WHERE execution_id=%s AND case_id='origin-rollback-probe'",(plan.execution_id,)).fetchone()[0]==1
            c.execute('ROLLBACK TO SAVEPOINT origin_rollback_probe');c.commit()


        authority=importlib.import_module('aos_api.aip_model_eval_execution_authority')
        with psycopg.connect(get_dsn()) as c:
            if c.execute("SELECT to_regclass('aos_model_eval_issuer_private.identity_epoch')").fetchone()[0] is None:authority.install_closed_model_identity_authority(c.execute)
            c.commit()
        certificate_args=dict(expected_tenant=args['expected_tenant'],execution_id=plan.execution_id,manifest_hash=plan_hash,certificate_hash=bindings['target']['certificateHash'],root_hash=root_hash,expected_root_epoch=1,expected_certificate_epoch=1)
        with owned() as c:reader.register_persisted_model_identity(c,**certificate_args);c.commit()
        with owned() as c:
            origin=c.execute('SELECT content_hash,origin_xid::text,pg_xact_status(origin_xid),origin_pid FROM aos_model_eval_issuer_private.target_result_origin WHERE execution_id=%s AND case_id=%s',(plan.execution_id,'case-1')).fetchone()
            assert origin[0]==bindings['target']['caseHash'] and origin[1]==target_xid and origin[2]=='committed' and origin[3]>0
            assert c.execute("SELECT count(*) FROM aos_model_eval_issuer_private.target_result_origin WHERE execution_id=%s AND case_id='origin-rollback-probe'",(plan.execution_id,)).fetchone()[0]==0
            for sql in ('INSERT INTO aos_model_eval_issuer_private.target_result_origin SELECT * FROM aos_model_eval_issuer_private.target_result_origin', 'UPDATE aos_model_eval_issuer_private.target_result_origin SET origin_pid=origin_pid', 'DELETE FROM aos_model_eval_issuer_private.target_result_origin', 'TRUNCATE aos_model_eval_issuer_private.target_result_origin'):
                c.execute('SAVEPOINT forged_origin')
                with pytest.raises(psycopg.Error) as denied:c.execute(sql)
                assert denied.value.sqlstate=='23514';c.execute('ROLLBACK TO SAVEPOINT forged_origin')
            c.rollback()

        assert hasattr(reader,'validate_persisted_model_target_result'),'Target-before-Judge reader missing after actual signed Target COMMIT'
        target_args={k:v for k,v in args.items() if not k.startswith('judge')};target_args['expected_identity_epoch']=1
        with owned() as c:
            before=c.execute('SELECT pg_current_xact_id()::text,pg_backend_pid()').fetchone()
            assert c.execute("SELECT count(*) FROM aos_model_eval_execution_private.case_result WHERE execution_id=%s AND purpose='judge'",(plan.execution_id,)).fetchone()[0]==0
            assert reader.validate_persisted_model_target_result(c,**target_args) is None
            for change in (dict(target_output=b'borrowed'),dict(target_input=b'borrowed'),dict(case_id='borrowed'),dict(expected_identity_epoch=True),dict(target_binding=bindings['target']|dict(certificateHash=bindings['judge']['certificateHash'])),dict(target_binding=bindings['target']|dict(caseHash='f'*64))):
                with pytest.raises(ValueError):reader.validate_persisted_model_target_result(c,**(target_args|change))
            with pytest.raises(ValueError,match='original case bytes unavailable'):reader.validate_persisted_model_case(c,**args)
            c.execute('SAVEPOINT target_canary');c.execute("SET LOCAL aos.org_id='dev-org'")
            with pytest.raises(ValueError):reader.validate_persisted_model_target_result(c,**target_args)
            c.execute('ROLLBACK TO SAVEPOINT target_canary')
            c.execute('SAVEPOINT target_revoked')
            event=dict(schemaVersion='aos.model-eval-identity-withdrawal/v1',tenant=dump(plan.tenant),identityId=plan.cases[0].target.identity_id,eventId='target-before-judge-withdrawal')
            withdrawal=encode(event)
            c.execute('INSERT INTO aos_model_eval_issuer_private.identity_withdrawal(org_id,project_id,event_id,identity_id,content_hash,body) VALUES (%s,%s,%s,%s,%s,%s)',('org-org','dev-project',event['eventId'],event['identityId'],hashlib.sha256(withdrawal).hexdigest(),withdrawal))
            with pytest.raises(ValueError,match='identity'):reader.validate_persisted_model_target_result(c,**target_args)
            c.execute('ROLLBACK TO SAVEPOINT target_revoked')
            assert reader.validate_persisted_model_target_result(c,**target_args) is None
            assert c.execute('SELECT pg_current_xact_id()::text,pg_backend_pid()').fetchone()==before
            c.rollback()
        assert hasattr(authority,'runtime_target_fact_statements'),'runtime Target fact missing after signed Target COMMIT and Judge zero'
        with psycopg.connect(get_dsn()) as c:
            if c.execute("SELECT to_regprocedure('public.read_model_executor_set_facts(text,text)')").fetchone()[0] is None:
                for statement in authority.runtime_executor_fact_statements():c.execute(statement)
            if c.execute("SELECT to_regprocedure('public.read_model_target_result_facts(text,text,text)')").fetchone()[0] is None:
                for statement in authority.runtime_target_fact_statements():c.execute(statement)
            c.commit()
        with owned() as c:
            judge_certificate_args=certificate_args|dict(certificate_hash=bindings['judge']['certificateHash'])
            reader.register_persisted_model_identity(c,**judge_certificate_args);c.commit()
        witnesses=tuple(dict(caseId='case-1',purpose=purpose,certificateHash=bindings[purpose]['certificateHash'],rootHash=root_hash,rootEpoch=1,certificateEpoch=1,identityEpoch=1) for purpose in ('target','judge'))
        runtime_args={k:v for k,v in target_args.items() if k!='expected_identity_epoch'}|dict(certificates=witnesses)
        assert hasattr(reader,'validate_runtime_model_target_result'),'runtime Target result reader missing'
        with owned('aos_runtime') as c:
            before=c.execute('SELECT pg_current_xact_id()::text,pg_backend_pid()').fetchone()
            assert reader.validate_runtime_model_target_result(c,**runtime_args) is None
            assert hasattr(reader,'prepare_runtime_model_judge_input'),'committed Target-to-Judge input binding missing'
            judge_bytes=reader.prepare_runtime_model_judge_input(c,**runtime_args,expected_output=expected_output)
            judge_payload=json.loads(judge_bytes)
            assert judge_bytes==encode(judge_payload)
            assert judge_payload['actualHash']==hashlib.sha256(raw['target'][1]).hexdigest()
            assert base64.b64decode(judge_payload['actualBase64'],validate=True)==raw['target'][1]
            assert base64.b64decode(judge_payload['expectedBase64'],validate=True)==expected_output
            assert judge_payload['expectedHash']==plan.cases[0].expected_hash
            assert judge_payload['targetCaseHash']==bindings['target']['caseHash']
            assert judge_payload['judgeLeg']==dump(plan.cases[0].judge)
            assert (judge_payload['executionId'],judge_payload['manifestHash'],judge_payload['caseId'])==(plan.execution_id,plan_hash,'case-1')
            assert judge_payload['tenant']==dump(plan.tenant) and judge_payload['executionAllowed'] is False
            for bad_expected in (None,b'borrowed',bytearray(expected_output)):
                with pytest.raises(ValueError):reader.prepare_runtime_model_judge_input(c,**runtime_args,expected_output=bad_expected)
            for change in (dict(target_output=b'borrowed'),dict(target_input=b'borrowed'),dict(case_id='borrowed'),dict(target_binding=bindings['target']|dict(caseHash='f'*64)),dict(certificates=witnesses[:1])):
                c.execute('SAVEPOINT runtime_target_bad')
                with pytest.raises(ValueError):reader.validate_runtime_model_target_result(c,**(runtime_args|change))
                c.execute('ROLLBACK TO SAVEPOINT runtime_target_bad')
            c.execute('SAVEPOINT runtime_target_canary');c.execute("SET LOCAL aos.org_id='dev-org'")
            with pytest.raises(ValueError):reader.validate_runtime_model_target_result(c,**runtime_args)
            with pytest.raises(ValueError):reader.prepare_runtime_model_judge_input(c,**runtime_args,expected_output=expected_output)
            c.execute('ROLLBACK TO SAVEPOINT runtime_target_canary')
            for sql in ('SELECT * FROM aos_model_eval_execution_private.case_result','SELECT * FROM aos_model_eval_issuer_private.target_result_origin','DROP FUNCTION public.read_model_target_result_facts(text,text,text)'):
                c.execute('SAVEPOINT runtime_target_acl')
                with pytest.raises(psycopg.Error) as denied:c.execute(sql)
                assert denied.value.sqlstate=='42501';c.execute('ROLLBACK TO SAVEPOINT runtime_target_acl')
            assert c.execute('SELECT pg_current_xact_id()::text,pg_backend_pid()').fetchone()==before;c.rollback()
        with owned() as c:
            c.execute('SAVEPOINT runtime_target_withdrawal')
            event=dict(schemaVersion='aos.model-eval-identity-withdrawal/v1',tenant=dump(plan.tenant),identityId=plan.cases[0].judge.identity_id,eventId='runtime-target-judge-withdrawal')
            withdrawal=encode(event)
            c.execute('INSERT INTO aos_model_eval_issuer_private.identity_withdrawal(org_id,project_id,event_id,identity_id,content_hash,body) VALUES (%s,%s,%s,%s,%s,%s)',('org-org','dev-project',event['eventId'],event['identityId'],hashlib.sha256(withdrawal).hexdigest(),withdrawal))
            c.execute('SET LOCAL ROLE aos_runtime')
            with pytest.raises(ValueError):reader.validate_runtime_model_target_result(c,**runtime_args)
            c.execute('ROLLBACK TO SAVEPOINT runtime_target_withdrawal');c.rollback()
        with owned('aos_runtime') as c:
            assert reader.validate_runtime_model_target_result(c,**runtime_args) is None;c.rollback()
        directory=os.environ.get('AOS_IDENTITY_WAIT_EVIDENCE')
        if directory:
            with (Path(directory)/'target-before-judge.json').open('x') as h:json.dump(dict(execution_id=plan.execution_id,manifest_hash=plan_hash,target_hash=bindings['target']['caseHash'],target_xid=target_xid,producer_origin_xid=origin[1],producer_native_status=origin[2],origin_forgery_mutation_denied=True,origin_atomic_rollback_verified=True,judge_input_base64=base64.b64encode(judge_bytes).decode(),judge_input_hash=hashlib.sha256(judge_bytes).hexdigest(),expected_output_base64=base64.b64encode(expected_output).decode(),target_binding=bindings['target'],target_input=base64.b64encode(raw['target'][0]).decode(),target_output=base64.b64encode(raw['target'][1]).decode(),judge_count=0,runtime_target_verified=True,runtime_private_acl_denied=True,runtime_judge_identity_withdrawal_rejected=True,canary_and_withdrawal_rejected=True,necessary_validation=True,execution_allowed=False),h,indent=2)
        return
    if expiry_wait and expiry_wait[0] in ('runtime-target-result','runtime-judge-input'):
        authority=importlib.import_module('aos_api.aip_model_eval_execution_authority')
        with psycopg.connect(get_dsn()) as c:
            if c.execute("SELECT to_regclass('aos_model_eval_issuer_private.target_result_origin')").fetchone()[0] is None:
                for statement in authority.target_origin_statements():c.execute(statement)
            c.commit()
    with owned('aos_model_eval_execution_owner') as c:
        put_case(c,'target',dump(envelopes['target']))
        borrowed=dump(envelopes['judge']);borrowed['payload']['claim']['caseId']='borrowed-case'
        payload=module.ModelEvalCaseSignaturePayload.model_validate(borrowed['payload'])
        signing=b'AOS-MODEL-EVAL-SIGNED-CASE-v1\n'+encode(dump(payload))
        borrowed['signatureBase64']=base64.b64encode(keys['judge'].sign(signing)).decode()
        for bad in (dump(envelopes['judge'])|dict(signatureBase64=base64.b64encode(bytes(64)).decode()),
                    dump(envelopes['judge'])|dict(trusted=True),borrowed,
                    json.dumps(dump(envelopes['judge']),indent=2).encode()):
            c.execute('SAVEPOINT bad_case');digest=put_case(c,'judge',bad)
            c.execute('RESET ROLE');c.execute('SET LOCAL ROLE aos_model_eval_issuer_owner')
            with pytest.raises(ValueError):reader.validate_persisted_model_case(c,**(args|dict(judge_binding=bindings['judge']|dict(caseHash=digest))))
            c.execute('ROLLBACK TO SAVEPOINT bad_case');c.execute('RELEASE SAVEPOINT bad_case')
        put_case(c,'judge',dump(envelopes['judge']));c.commit()
    if identity_gate:
        with owned() as c:
            assert reader.validate_persisted_model_case(c,**args) is None
            c.rollback()
        assert hasattr(reader,'validate_persisted_model_identity_case'), 'full case identity consumer missing after signed case COMMIT'
        authority=importlib.import_module('aos_api.aip_model_eval_execution_authority')
        with psycopg.connect(get_dsn()) as c:
            if c.execute("SELECT to_regclass('aos_model_eval_issuer_private.identity_epoch')").fetchone()[0] is None:
                authority.install_closed_model_identity_authority(c.execute)
            c.commit()
        for purpose in ('target','judge'):
            with owned() as c:
                binding=bindings[purpose]
                reader.register_persisted_model_identity(c,expected_tenant=args['expected_tenant'],execution_id=plan.execution_id,manifest_hash=plan_hash,certificate_hash=binding['certificateHash'],root_hash=root_hash,expected_root_epoch=1,expected_certificate_epoch=1)
                c.commit()
        with owned() as c:
            assert reader.validate_persisted_model_identity_case(c,**args,target_identity_epoch=1,judge_identity_epoch=1) is None
            for change in (dict(target_identity_epoch=True),dict(judge_identity_epoch=0)):
                with pytest.raises(ValueError):reader.validate_persisted_model_identity_case(c,**args,**(dict(target_identity_epoch=1,judge_identity_epoch=1)|change))
            c.rollback()
        if expiry_wait and expiry_wait[0] in ('runtime-target-result','runtime-judge-input'):
            with psycopg.connect(get_dsn()) as c:
                if c.execute("SELECT to_regprocedure('public.read_model_executor_set_facts(text,text)')").fetchone()[0] is None:
                    for statement in authority.runtime_executor_fact_statements():c.execute(statement)
                if c.execute("SELECT to_regprocedure('public.read_model_target_result_facts(text,text,text)')").fetchone()[0] is None:
                    for statement in authority.runtime_target_fact_statements():c.execute(statement)
                c.commit()
        if expiry_wait:
            import threading,queue,time,os
            from pathlib import Path
            entry,short_purpose=expiry_wait;binding=bindings[short_purpose]
            certificate_args=dict(expected_tenant=args['expected_tenant'],execution_id=plan.execution_id,manifest_hash=plan_hash,certificate_hash=binding['certificateHash'],root_hash=root_hash,expected_root_epoch=1,expected_certificate_epoch=1)
            ready=queue.Queue();terminal=queue.Queue();blocker=owned()
            blocker.execute('SELECT identity_id FROM aos_model_eval_issuer_private.identity_epoch WHERE identity_id=%s FOR UPDATE',(getattr(plan.cases[0],short_purpose).identity_id,))
            def consume():
                try:
                    with owned('aos_runtime' if entry in ('runtime-target-result','runtime-judge-input') else 'aos_model_eval_issuer_owner') as call:
                        call.execute("SET LOCAL statement_timeout='12s'")
                        before=call.execute('SELECT clock_timestamp(),pg_current_xact_id()::text').fetchone()
                        ready.put(call.info.backend_pid);rejected=False;reason=None
                        try:
                            if entry in ('runtime-target-result','runtime-judge-input'):
                                witnesses=tuple(dict(caseId='case-1',purpose=purpose,certificateHash=bindings[purpose]['certificateHash'],rootHash=root_hash,rootEpoch=1,certificateEpoch=1,identityEpoch=1) for purpose in ('target','judge'))
                                if entry=='runtime-judge-input':reader.prepare_runtime_model_judge_input(call,**{k:v for k,v in args.items() if not k.startswith('judge')},certificates=witnesses,expected_output=expected_output)
                                else:reader.validate_runtime_model_target_result(call,**{k:v for k,v in args.items() if not k.startswith('judge')},certificates=witnesses)
                            elif entry=='target-result':reader.validate_persisted_model_target_result(call,**{k:v for k,v in args.items() if not k.startswith('judge')},expected_identity_epoch=1)
                            elif entry=='case':reader.validate_persisted_model_identity_case(call,**args,target_identity_epoch=1,judge_identity_epoch=1)
                            elif entry=='certificate':reader.validate_persisted_model_identity(call,**certificate_args,expected_identity_epoch=1)
                            else:reader.register_persisted_model_identity(call,**certificate_args)
                        except ValueError as exc:rejected=True;reason=str(exc)
                        after=call.execute('SELECT clock_timestamp(),pg_current_xact_id()::text').fetchone()
                        assert before[1]==after[1];call.rollback()
                        terminal.put(dict(rejected=rejected,reason=reason,caller_xid=before[1],before=before[0].isoformat(),after=after[0].isoformat()))
                except Exception as exc:terminal.put(exc)
            thread=threading.Thread(target=consume);thread.start();blocked=False
            try:
                pid=ready.get(timeout=5)
                with psycopg.connect(get_dsn(),autocommit=True) as monitor:
                    for _ in range(100):
                        if blocker.info.backend_pid in monitor.execute('SELECT pg_blocking_pids(%s)',(pid,)).fetchone()[0]:blocked=True;break
                        time.sleep(.02)
                    assert blocked,'actual identity head wait not observed'
                    while True:
                        released=monitor.execute('SELECT clock_timestamp()').fetchone()[0]
                        if released>=expires:break
                        time.sleep(.02)
            finally:
                blocker.rollback();blocker.close();thread.join(timeout=15)
            assert not thread.is_alive();outcome=terminal.get(timeout=1);assert isinstance(outcome,dict),repr(outcome)
            record=dict(entry=entry,purpose=short_purpose,expires=expires.isoformat(),released=released.isoformat(),actual_blocking=blocked,**outcome)
            directory=os.environ.get('AOS_IDENTITY_WAIT_EVIDENCE')
            if directory:
                with (Path(directory)/('identity-wait-'+entry+'-'+short_purpose+'.json')).open('x') as out:json.dump(record,out,indent=2)
            assert outcome['rejected'] and outcome['reason']=='current contained half-open certificate interval required',record
            return
    with owned() as c:
        assert reader.validate_persisted_model_case(c,**args) is None
        for change in (dict(target_output=b'borrowed'),dict(judge_binding=bindings['judge']|dict(rootEpoch=True)),dict(target_binding=bindings['target']|dict(certificateHash=bindings['judge']['certificateHash'])),dict(case_id='borrowed')):
            c.execute('SAVEPOINT bad_binding')
            with pytest.raises(ValueError):reader.validate_persisted_model_case(c,**(args|change))
            c.execute('ROLLBACK TO SAVEPOINT bad_binding');c.execute('RELEASE SAVEPOINT bad_binding')
        c.rollback()
    with owned() as c:
        for role in ('aos_runtime','aos_model_eval_execution_owner','aos_app'):
            c.execute('SAVEPOINT bad_case_role');c.execute('RESET ROLE');c.execute('SET LOCAL ROLE '+role)
            with pytest.raises(ValueError):reader.validate_persisted_model_case(c,**args)
            c.execute('ROLLBACK TO SAVEPOINT bad_case_role');c.execute('RELEASE SAVEPOINT bad_case_role')
        c.execute('SAVEPOINT case_canary');c.execute("SET LOCAL aos.org_id='dev-org'")
        assert c.execute('SELECT count(*) FROM aos_model_eval_execution_private.case_result').fetchone()[0]==0
        with pytest.raises(ValueError):reader.validate_persisted_model_case(c,**args)
        c.execute('ROLLBACK TO SAVEPOINT case_canary');c.execute('RELEASE SAVEPOINT case_canary')
        c.execute('SAVEPOINT root_withdraw_probe')
        c.execute('INSERT INTO aos_model_eval_issuer_private.authority_withdrawal(org_id,project_id,event_id,issuer_id,key_id,content_hash,body) VALUES (%s,%s,%s,%s,%s,%s,%s)',('org-org','dev-project','case-root-probe',root.issuer_id,root.issuer_key_id,root_hash,root_bytes))
        with pytest.raises(ValueError):reader.validate_persisted_model_case(c,**args)
        c.execute('ROLLBACK TO SAVEPOINT root_withdraw_probe');c.execute('RELEASE SAVEPOINT root_withdraw_probe')
        assert reader.validate_persisted_model_case(c,**args) is None
        c.rollback()
    if identity_gate:
        event=dict(schemaVersion='aos.model-eval-identity-withdrawal/v1',tenant=dict(orgId='org-org',projectId='dev-project'),identityId=plan.cases[0].judge.identity_id,eventId='identity-case-judge-revoke')
        wb=encode(event)
        with owned() as revoke:
            revoke.execute('INSERT INTO aos_model_eval_issuer_private.identity_withdrawal(org_id,project_id,event_id,identity_id,content_hash,body) VALUES (%s,%s,%s,%s,%s,%s)',('org-org','dev-project',event['eventId'],event['identityId'],hashlib.sha256(wb).hexdigest(),wb));revoke.commit()
        with owned() as current:
            assert reader.validate_persisted_model_case(current,**args) is None
            with pytest.raises(ValueError,match='identity revoked or binding drifted'):
                reader.validate_persisted_model_identity_case(current,**args,target_identity_epoch=1,judge_identity_epoch=1)
            current.rollback()
    with owned() as c:
        digest=bindings['judge']['certificateHash'];encoded=encode(dump(certs['judge']))
        c.execute('INSERT INTO aos_model_eval_issuer_private.authority_withdrawal(org_id,project_id,event_id,certificate_hash,content_hash,body) VALUES (%s,%s,%s,%s,%s,%s)',('org-org','dev-project','native-identity-judge-withdraw' if identity_gate else 'native-judge-withdraw',digest,digest,encoded));c.commit()
    with owned() as c:
        with pytest.raises(ValueError):reader.validate_persisted_model_case(c,**args)
        c.rollback()


def test_model_multi_case_parent_plan_persistence():
    import json,importlib
    from tests.aip.test_model_eval_execution_contracts import _allocation_plan_body
    from aos_api.aip_model_eval_execution_contracts import ModelEvalExecutionManifest
    from aos_api.aip_contracts import TenantContext
    reader=importlib.import_module('aos_api.aip_model_eval_execution_reader')
    body=_allocation_plan_body();body['executionId']='multi-case-parent-native'
    plan=ModelEvalExecutionManifest.model_validate(body)
    raw=json.dumps(plan.model_dump(mode='json',by_alias=True),sort_keys=True,ensure_ascii=False,separators=(',',':')).encode();digest=hashlib.sha256(raw).hexdigest()
    def owned():
        c=psycopg.connect(get_dsn(),row_factory=tuple_row);c.execute('BEGIN ISOLATION LEVEL SERIALIZABLE')
        c.execute('SET LOCAL ROLE aos_model_eval_execution_owner');c.execute("SET LOCAL aos.org_id='org-org'");c.execute("SET LOCAL aos.project_id='dev-project'");return c
    args=dict(expected_tenant=TenantContext(orgId='org-org',projectId='dev-project'),execution_id=plan.execution_id,manifest_hash=digest)
    with owned() as c:
        c.execute('INSERT INTO aos_model_eval_execution_private.manifest VALUES (%s,%s,%s,%s,%s)',('org-org','dev-project',plan.execution_id,digest,raw));c.commit()
    with owned() as c:
        stored=reader.read_model_execution_plan(c,**args)
        assert len(stored.cases)==2 and stored.execution_allowed is False
        assert stored.cases[0].target.budget_hold_ref==stored.cases[1].target.budget_hold_ref
        assert stored.cases[0].target.budget_allocation_ref!=stored.cases[1].target.budget_allocation_ref
        c.rollback()
    bad=plan.model_dump(mode='json',by_alias=True);bad['executionId']='over-parent-native'
    bad['cases'][0]['target']['allocationUpperBoundMinor']=bad['parentBudgetLimits'][0]['upperBoundMinor']
    encoded=json.dumps(bad,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode();bad_hash=hashlib.sha256(encoded).hexdigest()
    with owned() as c:
        c.execute('INSERT INTO aos_model_eval_execution_private.manifest VALUES (%s,%s,%s,%s,%s)',('org-org','dev-project',bad['executionId'],bad_hash,encoded))
        with pytest.raises(ValueError):reader.read_model_execution_plan(c,**(args|dict(execution_id=bad['executionId'],manifest_hash=bad_hash)))
        c.rollback()


def _original_committed_model_parent(**fixture_options):
    import importlib
    from aos_api.db import connect_serializable
    from aos_api.aip_budget_reservation_store import canonical_hash
    from aos_api.aip_model_eval_budget_reservation import AipModelEvalBudgetReservationStore
    from aos_api.aip_model_eval_execution_contracts import ModelEvalParentBudgetLimit
    from aos_api.aip_contracts import TenantContext
    from tests.aip.test_model_eval_request_pg import seeded_approved_model_eval_request
    reader = importlib.import_module('aos_api.aip_model_eval_execution_reader')
    scope, first, request, proposal, _, _, _, _ = seeded_approved_model_eval_request(stop_after_approval=True, **fixture_options)
    with connect_serializable(scope) as conn:
        approval = conn.execute('''SELECT approval_event_id,proposal_id,proposal_version,
            proposal_hash,decision,actor_id,reason,expires_at,created_at,action_binding_hash
            FROM aip_action_approval_event WHERE org_id=%s AND project_id=%s
            AND proposal_id=%s AND decision='approved' ''', (*scope.key, proposal.proposal.id)).fetchone()
        held = AipModelEvalBudgetReservationStore().hold(conn, scope, first['request_id'], approval['approval_event_id'])
        held = conn.execute('SELECT * FROM aip_model_eval_budget_reservation WHERE org_id=%s AND project_id=%s AND request_id=%s',(*scope.key,first['request_id'])).fetchone()
    body = dict(parentHoldRef=dict(resourceType='ModelEvalBudgetReservation',resourceId=str(held['reservation_id']),revision=1,contentHash=held['content_hash']),
        requestId=first['request_id'],requestHash=held['request_hash'],approvalRef=dict(resourceType='ActionApprovalEvent',resourceId=approval['approval_event_id'],revision=approval['proposal_version'],contentHash=canonical_hash(dict(approval),prefixed=True)),
        budgetPolicyRef=request.budget_policy_ref.model_dump(mode='json',by_alias=True),priceRef=request.price_ref.model_dump(mode='json',by_alias=True),currency='CNY',upperBoundMinor=request.upper_bound_minor)
    tenant=TenantContext(orgId=scope.org_id,projectId=scope.project_id)
    return scope,held,body,tenant


def test_model_parent_hold_reader_uses_original_committed_budget():
    import importlib
    from aos_api.db import connect_serializable
    from aos_api.aip_model_eval_execution_contracts import ModelEvalParentBudgetLimit
    reader=importlib.import_module('aos_api.aip_model_eval_execution_reader')
    validate=reader.validate_model_parent_hold
    scope,held,body,tenant=_original_committed_model_parent()
    def consume(value):
        with connect_serializable(scope) as conn:
            before=conn.execute('SELECT count(*) AS n FROM aip_model_eval_budget_reservation').fetchone()['n']
            assert validate(conn,expected_tenant=tenant,parent_limit=ModelEvalParentBudgetLimit.model_validate(value)) is None
            assert conn.execute('SELECT count(*) AS n FROM aip_model_eval_budget_reservation').fetchone()['n']==before
    consume(body);consume(body)
    import copy
    for field,value in [('requestHash','0'*64),('requestId','missing-request'),('upperBoundMinor',199)]:
        bad=copy.deepcopy(body);bad[field]=value
        with pytest.raises(reader.ModelExecutionPlanRejected):consume(bad)
    for field in ('parentHoldRef','approvalRef'):
        bad=copy.deepcopy(body);bad[field]['contentHash']='sha256:'+'0'*64
        with pytest.raises(reader.ModelExecutionPlanRejected):consume(bad)
    with psycopg.connect(get_dsn()) as owner:
        with pytest.raises(reader.ModelExecutionPlanRejected):
            validate(owner,expected_tenant=tenant,parent_limit=ModelEvalParentBudgetLimit.model_validate(body))

    from aos_api.db import connect
    from aos_api.tenant_scope import TenantScope
    with connect(scope) as conn:
        with pytest.raises(reader.ModelExecutionPlanRejected):
            validate(conn,expected_tenant=tenant,parent_limit=ModelEvalParentBudgetLimit.model_validate(body))
    with connect_serializable(TenantScope('dev-org','dev-project')) as conn:
        with pytest.raises(reader.ModelExecutionPlanRejected):
            validate(conn,expected_tenant=tenant,parent_limit=ModelEvalParentBudgetLimit.model_validate(body))
    for kind in ('task','daily','pilot'):
        # Isolated fixture owner changes a balance in an uncommitted transaction;
        # the consumer itself never switches roles or writes any row.
        with psycopg.connect(get_dsn()) as fixture:
            fixture.execute('BEGIN ISOLATION LEVEL SERIALIZABLE')
            fixture.execute('''UPDATE aip_budget_bucket b SET held_minor=0,version=b.version+1
                FROM aip_model_eval_budget_reservation_bucket l
                WHERE (b.org_id,b.project_id,b.bucket_kind,b.account_id,b.period_start,b.currency)
                    =(l.org_id,l.project_id,l.bucket_kind,l.account_id,l.period_start,l.currency)
                AND l.reservation_id=%s AND l.bucket_kind=%s''',(held['reservation_id'],kind))
            fixture.execute("SET LOCAL ROLE aos_runtime")
            fixture.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",scope.key)
            with pytest.raises(reader.ModelExecutionPlanRejected,match='three original parent bucket'):
                validate(fixture,expected_tenant=tenant,parent_limit=ModelEvalParentBudgetLimit.model_validate(body))
            fixture.rollback()
        consume(body)


@pytest.mark.parametrize('layout', ['native', 'task-first'])
def test_model_parent_reader_follows_original_bucket_lock_order(layout):
    from concurrent.futures import ThreadPoolExecutor
    from queue import Queue
    import time
    from aos_api.db import connect_serializable
    from aos_api.aip_model_eval_execution_reader import validate_model_parent_hold
    from aos_api.aip_model_eval_execution_contracts import ModelEvalParentBudgetLimit
    scope,held,body,tenant=_original_committed_model_parent()
    query="""SELECT b.bucket_kind FROM aip_budget_bucket b
        JOIN aip_model_eval_budget_reservation_bucket l
        USING(org_id,project_id,bucket_kind,account_id,period_start,currency)
        WHERE l.reservation_id=%s AND l.bucket_kind=%s FOR UPDATE OF b"""
    if layout=='task-first':
        with psycopg.connect(get_dsn()) as fixture:
            for kind in ('task','pilot','daily'):
                fixture.execute('''UPDATE aip_budget_bucket b SET version=b.version+1
                    FROM aip_model_eval_budget_reservation_bucket l
                    WHERE (b.org_id,b.project_id,b.bucket_kind,b.account_id,b.period_start,b.currency)
                        =(l.org_id,l.project_id,l.bucket_kind,l.account_id,l.period_start,l.currency)
                    AND l.reservation_id=%s AND l.bucket_kind=%s''',(held['reservation_id'],kind))
    ready=Queue()
    def consume():
        with connect_serializable(scope) as conn:
            conn.execute("SET LOCAL statement_timeout='15s'")
            if layout=='task-first':
                conn.execute('SET LOCAL enable_hashjoin=off')
                conn.execute('SET LOCAL enable_mergejoin=off')
                conn.execute('SET LOCAL enable_indexscan=off')
                conn.execute('SET LOCAL enable_bitmapscan=off')
            ready.put(conn.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid'])
            return validate_model_parent_hold(conn,expected_tenant=tenant,
                parent_limit=ModelEvalParentBudgetLimit.model_validate(body))
    with psycopg.connect(get_dsn()) as blocker, ThreadPoolExecutor(max_workers=1) as pool:
        blocker.execute(query,(held['reservation_id'],'daily'))
        blocker_pid=blocker.execute('SELECT pg_backend_pid()').fetchone()[0]
        future=pool.submit(consume)
        try:
            pid=ready.get(timeout=5)
            with psycopg.connect(get_dsn(),autocommit=True) as observer:
                deadline=time.monotonic()+5
                while time.monotonic()<deadline:
                    if observer.execute('SELECT pg_blocking_pids(%s)',(pid,)).fetchone()[0]==[blocker_pid]:break
                    assert not future.done(), 'reader terminated before observed daily wait'
                    time.sleep(.02)
                else:raise AssertionError('actual daily lock wait not observed')
            with psycopg.connect(get_dsn()) as probe:
                assert probe.execute(query+' NOWAIT',(held['reservation_id'],'task')).fetchone()[0]=='task'
                probe.rollback()
        finally:
            blocker.rollback()
            assert future.result(timeout=10) is None


@pytest.mark.parametrize('stage', ['bucket-wait', 'after-check-before-commit'])
def test_model_parent_currentness_is_not_a_joint_commit_guard(stage):
    from concurrent.futures import ThreadPoolExecutor
    from queue import Queue
    from datetime import timedelta
    import time,json,os
    from pathlib import Path
    from aos_api.db import connect_serializable
    from aos_api.aip_model_eval_execution_reader import validate_model_parent_hold,ModelExecutionPlanRejected
    from aos_api.aip_model_eval_execution_contracts import ModelEvalParentBudgetLimit
    scope,held,body,tenant=_original_committed_model_parent(expiry_after=timedelta(seconds=8))
    parent=ModelEvalParentBudgetLimit.model_validate(body)
    with psycopg.connect(get_dsn()) as observer:
        expiry=observer.execute('SELECT expires_at FROM aip_model_eval_request WHERE request_id=%s',
            (body['requestId'],)).fetchone()[0]
    def wait_past_expiry(conn):
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            now=conn.execute('SELECT clock_timestamp()').fetchone()[0]
            if now>expiry:return now
            time.sleep(.05)
        raise AssertionError('native expiry clock not reached')
    record=dict(stage=stage,request_id=body['requestId'],parent_hash=held['content_hash'],expiry=expiry.isoformat())
    if stage=='bucket-wait':
        ready=Queue()
        def consume():
            with connect_serializable(scope) as conn:
                conn.execute("SET LOCAL statement_timeout='20s'")
                ready.put(conn.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid'])
                with pytest.raises(ModelExecutionPlanRejected,match='remain current after bucket locks'):
                    validate_model_parent_hold(conn,expected_tenant=tenant,parent_limit=parent)
                return conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        with psycopg.connect(get_dsn()) as blocker,ThreadPoolExecutor(max_workers=1) as pool:
            blocker.execute('''SELECT b.bucket_kind FROM aip_budget_bucket b
                JOIN aip_model_eval_budget_reservation_bucket l USING(org_id,project_id,bucket_kind,account_id,period_start,currency)
                WHERE l.reservation_id=%s AND l.bucket_kind='daily' FOR UPDATE OF b''',(held['reservation_id'],))
            blocker_pid=blocker.execute('SELECT pg_backend_pid()').fetchone()[0]
            future=pool.submit(consume)
            try:
                pid=ready.get(timeout=5)
                with psycopg.connect(get_dsn(),autocommit=True) as observer:
                    deadline=time.monotonic()+5
                    while time.monotonic()<deadline:
                        if observer.execute('SELECT pg_blocking_pids(%s)',(pid,)).fetchone()[0]==[blocker_pid]:break
                        assert not future.done()
                        time.sleep(.02)
                    else:raise AssertionError('actual expiry reader wait not observed')
                    record['release_clock']=wait_past_expiry(observer).isoformat()
                    record['blocked_pid']=pid;record['blocking_pid']=blocker_pid
            finally:
                blocker.rollback()
                record['rejected_clock']=future.result(timeout=10).isoformat()
        record['outcome']='necessary reader rejected after actual wait'
    else:
        with connect_serializable(scope) as conn:
            assert validate_model_parent_hold(conn,expected_tenant=tenant,parent_limit=parent) is None
            record['checked_clock']=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now'].isoformat()
            with psycopg.connect(get_dsn(),autocommit=True) as observer:
                record['precommit_clock']=wait_past_expiry(observer).isoformat()
            record['caller_xid']=str(conn.execute('SELECT pg_current_xact_id()::text AS xid').fetchone()['xid'])
            conn.commit()  # necessary reader is intentionally NOT a joint commit gate
        record['outcome']='known actual caller COMMIT after original expiry; no execution authority'
    with psycopg.connect(get_dsn()) as observer:
        assert observer.execute('SELECT count(*) FROM aip_model_eval_budget_reservation WHERE reservation_id=%s',
            (held['reservation_id'],)).fetchone()[0]==1
        assert observer.execute('''SELECT count(*) FROM aip_model_eval_budget_reservation_bucket l
            JOIN aip_budget_bucket b USING(org_id,project_id,bucket_kind,account_id,period_start,currency)
            WHERE reservation_id=%s AND b.held_minor>=l.reserved_minor''',(held['reservation_id'],)).fetchone()[0]==3
    evidence_dir=os.environ.get('AOS_PARENT_COMMIT_PROBE_EVIDENCE')
    if evidence_dir:
        with (Path(evidence_dir)/('parent-currentness-'+stage+'.json')).open('x') as out:
            json.dump(record,out,indent=2)


def test_model_identity_binding_global_withdrawal_native():
    """Real signed certificate prefix, durable global tombstone; no root trust."""
    import base64, json, importlib
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    from tests.aip.test_model_eval_execution_contracts import _certificate_input
    from aos_api.aip_contracts import TenantContext
    interval = _native_certificate_interval()
    module, original, _, _ = _certificate_input(**interval)
    reader = importlib.import_module('aos_api.aip_model_eval_execution_reader')
    authority = importlib.import_module('aos_api.aip_model_eval_execution_authority')
    issuer = Ed25519PrivateKey.generate()
    root = dict(schemaVersion='aos.model-eval-issuer-verification-input/v1',
        purpose='model-eval-execution', tenant=dict(orgId='org-org',projectId='dev-project'),
        issuerId='identity-native-issuer', issuerKeyId='identity-native-key',
        publicKeyBase64=base64.b64encode(issuer.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)).decode(),
        validFrom=interval['valid_from'],validUntil=interval['valid_until'],revokedAt=None)
    root = module.ModelEvalIssuerVerificationInput.model_validate(root)
    def raw(v): return json.dumps(v.model_dump(mode='json',by_alias=True) if hasattr(v,'model_dump') else v,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
    def digest(v):return hashlib.sha256(v).hexdigest()
    rb=raw(root);rh=digest(rb);tenant=TenantContext(orgId='org-org',projectId='dev-project')
    def owned():
        c=psycopg.connect(get_dsn(),row_factory=tuple_row);c.execute('BEGIN ISOLATION LEVEL SERIALIZABLE');c.execute('SET LOCAL ROLE aos_model_eval_issuer_owner');c.execute("SET LOCAL aos.org_id='org-org'");c.execute("SET LOCAL aos.project_id='dev-project'");return c
    module,original,cert,executor=_certificate_input(**interval);records=[]
    shared_plan,shared_cert=original,dict(cert)
    with owned() as c:
        c.execute('INSERT INTO aos_model_eval_issuer_private.issuer_root(org_id,project_id,issuer_id,key_id,bootstrap_hash,content_hash,body) VALUES (%s,%s,%s,%s,%s,%s,%s)',('org-org','dev-project',root.issuer_id,root.issuer_key_id,'a'*64,rh,rb))
        c.execute('INSERT INTO aos_model_eval_issuer_private.issuer_epoch(org_id,project_id,issuer_id,key_id,epoch,root_hash) VALUES (%s,%s,%s,%s,1,%s)',('org-org','dev-project',root.issuer_id,root.issuer_key_id,rh))
        for i in range(4):
            if i==2:module,original,cert,_=_certificate_input(**interval)
            purpose='judge' if i==3 else 'target'
            body=original.model_dump(mode='json',by_alias=True);body['executionId']=f'identity-native-exec-{i}'
            body['cases'][0][purpose]['identityId']='identity-native-target'
            if i==3:body['cases'][0]['judge']['identityKeyHash']=shared_plan.cases[0].target.identity_key_hash
            plan=module.ModelEvalExecutionManifest.model_validate(body);pb=raw(plan);ph=digest(pb)
            cb=dict(cert);cb.update(executionId=plan.execution_id,manifestHash=ph,purpose=purpose,leg=body['cases'][0][purpose],issuerId=root.issuer_id,issuerKeyId=root.issuer_key_id)
            if i==3:cb['publicKeyBase64']=shared_cert['publicKeyBase64']
            claim=module.ModelEvalExecutorCertificateSigningInput.model_validate(cb)
            env=module.ModelEvalSignedCertificateEnvelope.model_validate(dict(schemaVersion='aos.model-eval-signed-certificate-envelope/v1',certificate=claim.model_dump(mode='json',by_alias=True),signatureBase64=base64.b64encode(issuer.sign(module.canonical_model_certificate_signing_bytes(plan,claim))).decode()))
            eb=raw(env);eh=digest(eb)
            c.execute('RESET ROLE');c.execute('SET LOCAL ROLE aos_model_eval_execution_owner')
            c.execute('INSERT INTO aos_model_eval_execution_private.manifest VALUES (%s,%s,%s,%s,%s)',('org-org','dev-project',plan.execution_id,ph,pb))
            c.execute('RESET ROLE');c.execute('SET LOCAL ROLE aos_model_eval_issuer_owner')
            c.execute('INSERT INTO aos_model_eval_issuer_private.executor_certificate(org_id,project_id,execution_id,case_id,purpose,attempt,issuer_id,key_id,content_hash,body) VALUES (%s,%s,%s,%s,%s,1,%s,%s,%s,%s)',('org-org','dev-project',plan.execution_id,claim.case_id,purpose,root.issuer_id,root.issuer_key_id,eh,eb))
            args=dict(expected_tenant=tenant,execution_id=plan.execution_id,manifest_hash=ph,certificate_hash=eh,root_hash=rh,expected_root_epoch=1,expected_certificate_epoch=1)
            reader.validate_persisted_model_certificate(c,**args);records.append(args)
        c.commit()
    wrong_purpose=records.pop();wrong_key=records.pop()
    assert hasattr(authority,'install_closed_model_identity_authority'), 'native identity artifact missing after real signed prefix COMMIT'
    with psycopg.connect(get_dsn()) as c:
        authority.install_closed_model_identity_authority(c.execute);c.commit()
    for args in records:
        with owned() as c:
            with pytest.raises(ValueError):reader.validate_persisted_model_identity(c,**args,expected_identity_epoch=1)
            c.rollback()
        with owned() as c:
            reader.register_persisted_model_identity(c,**args);c.commit()
        with owned() as c:
            reader.register_persisted_model_identity(c,**args);c.commit()
        with owned() as c:
            assert reader.validate_persisted_model_identity(c,**args,expected_identity_epoch=1) is None
            with pytest.raises(ValueError):reader.validate_persisted_model_identity(c,**args,expected_identity_epoch=True)
            c.rollback()
    for denied in (wrong_key,wrong_purpose):
        with owned() as c:
            reader.validate_persisted_model_certificate(c,**denied)
            with pytest.raises(psycopg.errors.InsufficientPrivilege,match='MODEL_IDENTITY_BOUND_OR_REVOKED'):
                reader.register_persisted_model_identity(c,**denied)
            c.rollback()
    event=dict(schemaVersion='aos.model-eval-identity-withdrawal/v1',tenant=dict(orgId='org-org',projectId='dev-project'),identityId='identity-native-target',eventId='identity-native-revoke')
    wb=raw(event)
    import queue, threading, time
    statement='INSERT INTO aos_model_eval_issuer_private.identity_withdrawal(org_id,project_id,event_id,identity_id,content_hash,body) VALUES (%s,%s,%s,%s,%s,%s)'
    params=('org-org','dev-project',event['eventId'],event['identityId'],digest(wb),wb)
    held=owned();stale=owned();writer_pid=queue.Queue();terminal=queue.Queue()
    try:
        reader.validate_persisted_model_identity(held,**records[0],expected_identity_epoch=1)
        stale.execute('SELECT version FROM aos_model_eval_issuer_private.identity_epoch').fetchall()
        def revoke():
            try:
                with owned() as c:
                    c.execute("SET LOCAL statement_timeout='10s'")
                    writer_pid.put(c.info.backend_pid);c.execute(statement,params);c.commit()
                terminal.put('committed')
            except Exception as exc:terminal.put(exc)
        thread=threading.Thread(target=revoke);thread.start();pid=writer_pid.get(timeout=5)
        blocked=False
        with psycopg.connect(get_dsn(),autocommit=True) as monitor:
            for _ in range(100):
                if held.info.backend_pid in monitor.execute('SELECT pg_blocking_pids(%s)',(pid,)).fetchone()[0]:
                    blocked=True;break
                time.sleep(.02)
        assert blocked, 'identity withdrawal must wait for actual reader lock'
        held.commit();thread.join(timeout=12);assert not thread.is_alive()
        outcome=terminal.get(timeout=1);assert outcome=='committed',repr(outcome)
        with pytest.raises(ValueError) as failure:
            reader.validate_persisted_model_identity(stale,**records[0],expected_identity_epoch=1)
        assert isinstance(failure.value.__cause__,psycopg.errors.SerializationFailure)
        stale.rollback()
    finally:
        held.rollback();held.close();stale.rollback();stale.close()
    with owned() as c:
        c.execute('SAVEPOINT mutation')
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute("UPDATE aos_model_eval_issuer_private.identity_epoch SET active=true")
        c.execute('ROLLBACK TO SAVEPOINT mutation')
        for relation in ('identity_epoch','certificate_identity_binding','identity_withdrawal'):
            for command in ('DELETE FROM',):
                c.execute('SAVEPOINT mutation')
                with pytest.raises(psycopg.errors.InsufficientPrivilege):c.execute(f'{command} aos_model_eval_issuer_private.{relation}')
                c.execute('ROLLBACK TO SAVEPOINT mutation')
        c.execute('SAVEPOINT mutation')
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute('TRUNCATE aos_model_eval_issuer_private.identity_withdrawal,aos_model_eval_issuer_private.certificate_identity_binding,aos_model_eval_issuer_private.identity_epoch')
        c.execute('ROLLBACK TO SAVEPOINT mutation')
        c.execute('RESET ROLE');c.execute('SET LOCAL ROLE aos_runtime')
        for relation in ('identity_epoch','certificate_identity_binding','identity_withdrawal'):
            c.execute('SAVEPOINT runtime')
            with pytest.raises(psycopg.errors.InsufficientPrivilege):c.execute(f'SELECT * FROM aos_model_eval_issuer_private.{relation}')
            c.execute('ROLLBACK TO SAVEPOINT runtime')
        c.rollback()
    body=shared_plan.model_dump(mode='json',by_alias=True);body['executionId']='identity-native-after-revoke';body['cases'][0]['target']['identityId']='identity-native-target'
    plan=module.ModelEvalExecutionManifest.model_validate(body);pb=raw(plan);ph=digest(pb)
    cb=dict(shared_cert);cb.update(executionId=plan.execution_id,manifestHash=ph,leg=body['cases'][0]['target'],issuerId=root.issuer_id,issuerKeyId=root.issuer_key_id)
    claim=module.ModelEvalExecutorCertificateSigningInput.model_validate(cb)
    env=module.ModelEvalSignedCertificateEnvelope.model_validate(dict(schemaVersion='aos.model-eval-signed-certificate-envelope/v1',certificate=claim.model_dump(mode='json',by_alias=True),signatureBase64=base64.b64encode(issuer.sign(module.canonical_model_certificate_signing_bytes(plan,claim))).decode()))
    eb=raw(env);eh=digest(eb)
    late=dict(expected_tenant=tenant,execution_id=plan.execution_id,manifest_hash=ph,certificate_hash=eh,root_hash=rh,expected_root_epoch=1,expected_certificate_epoch=1)
    with owned() as c:
        c.execute('RESET ROLE');c.execute('SET LOCAL ROLE aos_model_eval_execution_owner')
        c.execute('INSERT INTO aos_model_eval_execution_private.manifest VALUES (%s,%s,%s,%s,%s)',('org-org','dev-project',plan.execution_id,ph,pb))
        c.execute('RESET ROLE');c.execute('SET LOCAL ROLE aos_model_eval_issuer_owner')
        c.execute('INSERT INTO aos_model_eval_issuer_private.executor_certificate(org_id,project_id,execution_id,case_id,purpose,attempt,issuer_id,key_id,content_hash,body) VALUES (%s,%s,%s,%s,%s,1,%s,%s,%s,%s)',('org-org','dev-project',plan.execution_id,claim.case_id,'target',root.issuer_id,root.issuer_key_id,eh,eb))
        reader.validate_persisted_model_certificate(c,**late);c.commit()
    with owned() as c:
        reader.validate_persisted_model_certificate(c,**late)
        with pytest.raises(psycopg.errors.InsufficientPrivilege,match='MODEL_IDENTITY_BOUND_OR_REVOKED'):
            reader.register_persisted_model_identity(c,**late)
        c.rollback()
    with owned() as c:
        with pytest.raises(ValueError):reader.validate_persisted_model_identity(c,**late,expected_identity_epoch=1)
        c.rollback()
    for args in records:
        with owned() as c:
            with pytest.raises(ValueError):reader.validate_persisted_model_identity(c,**args,expected_identity_epoch=1)
            c.rollback()
        with owned() as c:
            with pytest.raises((ValueError,psycopg.errors.InsufficientPrivilege)):reader.register_persisted_model_identity(c,**args)
            c.rollback()
    with owned() as c:
        assert c.execute('SELECT epoch,version,active FROM aos_model_eval_issuer_private.identity_epoch WHERE identity_id=%s',('identity-native-target',)).fetchone()==(2,3,False)
        assert c.execute('SELECT count(*) FROM aos_model_eval_issuer_private.certificate_epoch WHERE active_hash IS NOT NULL AND certificate_hash=ANY(%s)',([a['certificate_hash'] for a in records],)).fetchone()[0]==2
        c.rollback()


def test_persisted_model_whole_case_set_current_identity():
    import base64,copy,importlib,json
    from uuid import uuid4
    from aos_api.aip_contracts import TenantContext
    from aos_api.aip_model_runtime_store import canonical_hash
    from tests.aip.test_model_eval_execution_contracts import _signed_model_case_fixture
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
    module,template,root_template,cert_template,_,claim_template,raw,_=_signed_model_case_fixture(**_native_certificate_interval())
    reader=importlib.import_module('aos_api.aip_model_eval_execution_reader')
    authority=importlib.import_module('aos_api.aip_model_eval_execution_authority')
    def dump(x):return x.model_dump(mode='json',by_alias=True)
    def encode(x):return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
    def public(key):return key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
    def owned(role='aos_model_eval_issuer_owner'):
        c=psycopg.connect(get_dsn(),row_factory=tuple_row);c.execute('BEGIN ISOLATION LEVEL SERIALIZABLE')
        c.execute('SET LOCAL ROLE '+role);c.execute("SET LOCAL aos.org_id='org-org'");c.execute("SET LOCAL aos.project_id='dev-project'");return c
    nonce=uuid4().hex;body=dump(template);body['executionId']='whole-case-'+nonce
    body['cases'].append(copy.deepcopy(body['cases'][0]));body['cases'][1]['caseId']='case-2'
    keys={}
    for case in body['cases']:
        for purpose in ('target','judge'):
            key=Ed25519PrivateKey.generate();keys[case['caseId'],purpose]=key
            leg=case[purpose];leg['identityId']=nonce+'-'+case['caseId']+'-'+purpose
            leg['identityKeyHash']=hashlib.sha256(public(key)).hexdigest()
            for field in ('intentRef','budgetAllocationRef'):leg[field]['resourceId']+=case['caseId']
    body['caseSetHash']=canonical_hash([{k:c[k] for k in ('caseId','inputHash','expectedHash')} for c in body['cases']])
    plan=module.ModelEvalExecutionManifest.model_validate(body);plan_hash=canonical_hash(dump(plan))
    roots={};issuers={};certificates={};inputs=[]
    with owned() as c:
        c.execute('RESET ROLE');c.execute('SET LOCAL ROLE aos_model_eval_execution_owner')
        c.execute('INSERT INTO aos_model_eval_execution_private.manifest VALUES (%s,%s,%s,%s,%s)',('org-org','dev-project',plan.execution_id,plan_hash,encode(dump(plan))))
        c.execute('RESET ROLE');c.execute('SET LOCAL ROLE aos_model_eval_issuer_owner')
        for purpose in ('target','judge'):
            issuers[purpose]=Ed25519PrivateKey.generate();r=copy.deepcopy(root_template)
            r.update(issuerId=nonce+'-'+purpose,publicKeyBase64=base64.b64encode(public(issuers[purpose])).decode())
            r=dump(module.ModelEvalIssuerVerificationInput.model_validate(r))
            roots[purpose]=r;rb=encode(r);rh=hashlib.sha256(rb).hexdigest()
            c.execute('INSERT INTO aos_model_eval_issuer_private.issuer_root(org_id,project_id,issuer_id,key_id,bootstrap_hash,content_hash,body) VALUES (%s,%s,%s,%s,%s,%s,%s)',('org-org','dev-project',r['issuerId'],r['issuerKeyId'],'a'*64,rh,rb))
            c.execute('INSERT INTO aos_model_eval_issuer_private.issuer_epoch(org_id,project_id,issuer_id,key_id,epoch,root_hash) VALUES (%s,%s,%s,%s,1,%s)',('org-org','dev-project',r['issuerId'],r['issuerKeyId'],rh))
        for case in plan.cases:
            for purpose in ('target','judge'):
                cert=dump(cert_template[purpose].certificate);r=roots[purpose]
                cert.update(executionId=plan.execution_id,manifestHash=plan_hash,caseId=case.case_id,leg=dump(getattr(case,purpose)),issuerId=r['issuerId'],publicKeyBase64=base64.b64encode(public(keys[case.case_id,purpose])).decode())
                env=module.ModelEvalSignedCertificateEnvelope.model_validate(dict(schemaVersion='aos.model-eval-signed-certificate-envelope/v1',certificate=cert,signatureBase64=base64.b64encode(issuers[purpose].sign(module.canonical_model_certificate_signing_bytes(plan,cert))).decode()))
                certificates[case.case_id,purpose]=env;cb=encode(dump(env));ch=hashlib.sha256(cb).hexdigest()
                c.execute('INSERT INTO aos_model_eval_issuer_private.executor_certificate(org_id,project_id,execution_id,case_id,purpose,attempt,issuer_id,key_id,content_hash,body) VALUES (%s,%s,%s,%s,%s,1,%s,%s,%s,%s)',('org-org','dev-project',plan.execution_id,case.case_id,purpose,r['issuerId'],r['issuerKeyId'],ch,cb))
        c.commit()
    with owned('aos_model_eval_execution_owner') as c:
        for case in plan.cases:
            claims={};bindings={}
            for purpose in ('target','judge'):
                claim=dump(claim_template[purpose]);claim.update(executionId=plan.execution_id,manifestHash=plan_hash,caseId=case.case_id,leg=dump(getattr(case,purpose)),occurredAt=c.execute('SELECT clock_timestamp()').fetchone()[0])
                if purpose=='judge':claim['targetClaimHash']=hashlib.sha256(module.canonical_model_case_signing_bytes(plan,claims['target'],input_bytes=raw['target'][0],output_bytes=raw['target'][1])).hexdigest()
                claims[purpose]=module.ModelEvalCaseSigningInput.model_validate(claim)
                cert_hash=canonical_hash(dump(certificates[case.case_id,purpose]));payload=dict(schemaVersion='aos.model-eval-case-signature-payload/v1',certificateHash=cert_hash,claim=claims[purpose])
                signing=module.canonical_model_signed_case_bytes(plan,payload,input_bytes=raw[purpose][0],output_bytes=raw[purpose][1],target_claim=claims.get('target') if purpose=='judge' else None)
                env=module.ModelEvalSignedCaseEnvelope.model_validate(dict(schemaVersion='aos.model-eval-signed-case-envelope/v1',payload=payload,signatureBase64=base64.b64encode(keys[case.case_id,purpose].sign(signing)).decode()))
                rb=encode(dump(env));rh=hashlib.sha256(rb).hexdigest()
                c.execute('INSERT INTO aos_model_eval_execution_private.case_result VALUES (%s,%s,%s,%s,%s,1,%s,%s)',('org-org','dev-project',plan.execution_id,case.case_id,purpose,rh,rb))
                bindings[purpose]=dict(caseHash=rh,certificateHash=cert_hash,rootHash=hashlib.sha256(encode(roots[purpose])).hexdigest(),rootEpoch=1,certificateEpoch=1)
            inputs.append(dict(caseId=case.case_id,targetBinding=bindings['target'],judgeBinding=bindings['judge'],targetIdentityEpoch=1,judgeIdentityEpoch=1,targetInput=raw['target'][0],targetOutput=raw['target'][1],judgeInput=raw['judge'][0],judgeOutput=raw['judge'][1]))
        c.commit()
    assert hasattr(reader,'validate_persisted_model_case_set'), 'whole signed case-set consumer missing after four signed cases COMMIT'
    with psycopg.connect(get_dsn()) as c:
        if c.execute("SELECT to_regclass('aos_model_eval_issuer_private.identity_epoch')").fetchone()[0] is None:authority.install_closed_model_identity_authority(c.execute)
        c.commit()
    tenant=TenantContext(orgId='org-org',projectId='dev-project')
    for item in inputs:
        for purpose in ('target','judge'):
            binding=item[purpose+'Binding']
            with owned() as c:
                reader.register_persisted_model_identity(c,expected_tenant=tenant,execution_id=plan.execution_id,manifest_hash=plan_hash,certificate_hash=binding['certificateHash'],root_hash=binding['rootHash'],expected_root_epoch=1,expected_certificate_epoch=1);c.commit()
    args=dict(expected_tenant=tenant,execution_id=plan.execution_id,manifest_hash=plan_hash)
    with owned() as c:
        assert reader.validate_persisted_model_case_set(c,**args,cases=tuple(inputs)) is None
        assert reader.validate_persisted_model_case_set(c,**args,cases=tuple(reversed(inputs))) is None
        for bad in (tuple(inputs[:1]),(inputs[0],inputs[0]),tuple(inputs)+(inputs[0]|dict(caseId='extra'),),tuple([inputs[0]|dict(targetInput=b'wrong'),inputs[1]]),tuple([inputs[0]|dict(judgeIdentityEpoch=True),inputs[1]])):
            with pytest.raises(ValueError):reader.validate_persisted_model_case_set(c,**args,cases=bad)
        c.execute('SAVEPOINT extra_case');c.execute('RESET ROLE');c.execute('SET LOCAL ROLE aos_model_eval_execution_owner')
        c.execute("INSERT INTO aos_model_eval_execution_private.case_result SELECT org_id,project_id,execution_id,'extra',purpose,attempt,content_hash,body FROM aos_model_eval_execution_private.case_result WHERE execution_id=%s AND case_id='case-1' AND purpose='target'",(plan.execution_id,))
        c.execute('RESET ROLE');c.execute('SET LOCAL ROLE aos_model_eval_issuer_owner')
        with pytest.raises(ValueError,match='persisted complete case set'):reader.validate_persisted_model_case_set(c,**args,cases=tuple(inputs))
        c.execute('ROLLBACK TO SAVEPOINT extra_case')
        for role in ('aos_runtime','aos_model_eval_execution_owner','aos_app'):
            c.execute('SAVEPOINT wrong_whole_role');c.execute('RESET ROLE');c.execute('SET LOCAL ROLE '+role)
            with pytest.raises(ValueError,match='whole-case SERIAL caller'):reader.validate_persisted_model_case_set(c,**args,cases=tuple(inputs))
            c.execute('ROLLBACK TO SAVEPOINT wrong_whole_role')
        with pytest.raises(ValueError):reader.validate_persisted_model_case_set(c,**(args|dict(manifest_hash='f'*64)),cases=tuple(inputs))
        c.execute('SAVEPOINT whole_canary');c.execute("SET LOCAL aos.org_id='dev-org'")
        with pytest.raises(ValueError,match='whole-case SERIAL caller'):reader.validate_persisted_model_case_set(c,**args,cases=tuple(inputs))
        c.execute('ROLLBACK TO SAVEPOINT whole_canary')
        # The whole reader must keep even the second case's identity locked.
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event
        import time
        event=dict(schemaVersion='aos.model-eval-identity-withdrawal/v1',tenant=body['tenant'],
                   identityId=plan.cases[1].judge.identity_id,eventId=nonce+'-judge-withdraw')
        wb=encode(event);ready=Event();pids=[]
        def withdraw():
            with owned() as writer:
                writer.execute("SET LOCAL statement_timeout='15s'")
                pids.append(writer.info.backend_pid);ready.set()
                writer.execute('INSERT INTO aos_model_eval_issuer_private.identity_withdrawal(org_id,project_id,event_id,identity_id,content_hash,body) VALUES (%s,%s,%s,%s,%s,%s)',
                    ('org-org','dev-project',event['eventId'],event['identityId'],hashlib.sha256(wb).hexdigest(),wb));writer.commit()
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending=pool.submit(withdraw)
            try:
                assert ready.wait(5);blocked=False
                with psycopg.connect(get_dsn()) as observer:
                    until=time.monotonic()+5
                    while time.monotonic()<until:
                        blocked=c.info.backend_pid in observer.execute('SELECT pg_blocking_pids(%s)',(pids[0],)).fetchone()[0]
                        if blocked:break
                        time.sleep(.02)
                assert blocked and not pending.done()
            finally:
                c.commit();pending.result(timeout=16)
    with owned() as c:
        # Case one remains valid; the collection must reject withdrawn case two.
        first=inputs[0]
        assert reader.validate_persisted_model_identity_case(c,**args,case_id=first['caseId'],
            target_binding=first['targetBinding'],judge_binding=first['judgeBinding'],target_identity_epoch=1,judge_identity_epoch=1,
            target_input=first['targetInput'],target_output=first['targetOutput'],judge_input=first['judgeInput'],judge_output=first['judgeOutput']) is None
        with pytest.raises(ValueError,match='identity'):reader.validate_persisted_model_case_set(c,**args,cases=tuple(inputs))
        c.rollback()


def _executor_set_identity_window_native(module,reader,plan,plan_hash,root_hash,certs,expires,purpose,owned,*,entry='executor-set'):
    """Real private issuer lock wait without any case_result/transport output."""
    import importlib,json,threading,queue,time,os
    from pathlib import Path
    from aos_api.aip_model_runtime_store import canonical_hash
    authority=importlib.import_module('aos_api.aip_model_eval_execution_authority')
    with psycopg.connect(get_dsn()) as c:
        if c.execute("SELECT to_regclass('aos_model_eval_issuer_private.identity_epoch')").fetchone()[0] is None:
            authority.install_closed_model_identity_authority(c.execute)
        c.commit()
    items=[]
    for leg in ('target','judge'):
        digest=canonical_hash(certs[leg].model_dump(mode='json',by_alias=True))
        args=dict(expected_tenant=plan.tenant,execution_id=plan.execution_id,manifest_hash=plan_hash,
                  certificate_hash=digest,root_hash=root_hash,expected_root_epoch=1,expected_certificate_epoch=1)
        with owned() as c:reader.register_persisted_model_identity(c,**args);c.commit()
        items.append(dict(caseId=plan.cases[0].case_id,purpose=leg,certificateHash=digest,rootHash=root_hash,rootEpoch=1,certificateEpoch=1,identityEpoch=1))
    args=dict(expected_tenant=plan.tenant,execution_id=plan.execution_id,manifest_hash=plan_hash,certificates=tuple(items))
    runtime_entry=entry=='runtime-executor-set'
    if runtime_entry:
        with psycopg.connect(get_dsn()) as c:
            if c.execute("SELECT to_regprocedure('public.read_model_executor_set_facts(text,text)')").fetchone()[0] is None:
                for statement in authority.runtime_executor_fact_statements():c.execute(statement)
            c.commit()
    consume_reader=reader.validate_runtime_model_executor_set if runtime_entry else reader.validate_persisted_model_executor_set
    caller_role='aos_runtime' if runtime_entry else 'aos_model_eval_issuer_owner'
    with owned() as c:
        assert c.execute('SELECT count(*) FROM aos_model_eval_execution_private.case_result WHERE execution_id=%s',(plan.execution_id,)).fetchone()[0]==0
        c.rollback()
    with owned(caller_role) as c:
        assert consume_reader(c,**args) is None
        c.rollback()
    ready=queue.Queue();terminal=queue.Queue();blocker=owned()
    blocker.execute('SELECT identity_id FROM aos_model_eval_issuer_private.identity_epoch WHERE identity_id=%s FOR UPDATE',
                    (getattr(plan.cases[0],purpose).identity_id,))
    def consume():
        try:
            with owned(caller_role) as call:
                call.execute("SET LOCAL statement_timeout='12s'")
                before=call.execute('SELECT clock_timestamp(),pg_current_xact_id()::text').fetchone();ready.put(call.info.backend_pid)
                rejected=False;reason=None
                try:consume_reader(call,**args)
                except ValueError as exc:rejected=True;reason=str(exc)
                after=call.execute('SELECT clock_timestamp(),pg_current_xact_id()::text').fetchone()
                assert before[1]==after[1];call.rollback()
                terminal.put(dict(rejected=rejected,reason=reason,caller_xid=before[1],before=before[0].isoformat(),after=after[0].isoformat()))
        except Exception as exc:terminal.put(exc)
    thread=threading.Thread(target=consume);thread.start();blocked=False
    try:
        pid=ready.get(timeout=5)
        with psycopg.connect(get_dsn(),autocommit=True) as monitor:
            until=time.monotonic()+4
            while time.monotonic()<until:
                blocked=blocker.info.backend_pid in monitor.execute('SELECT pg_blocking_pids(%s)',(pid,)).fetchone()[0]
                if blocked:break
                time.sleep(.02)
            assert blocked,'actual executor-set identity wait not observed'
            monitor.execute('SELECT pg_sleep(GREATEST(0,EXTRACT(EPOCH FROM (%s::timestamptz-clock_timestamp())))+.01)',(expires,))
            released=monitor.execute('SELECT clock_timestamp()').fetchone()[0]
    finally:
        blocker.rollback();blocker.close();thread.join(timeout=15)
    assert not thread.is_alive();outcome=terminal.get(timeout=1);assert isinstance(outcome,dict),repr(outcome)
    record=dict(entry=entry,caller_role=caller_role,purpose=purpose,execution_id=plan.execution_id,manifest_hash=plan_hash,certificate_inputs=items,
                expires=expires.isoformat(),released=released.isoformat(),actual_blocking=blocked,reader_pid=pid,output_count=0,**outcome)
    directory=os.environ.get('AOS_IDENTITY_WAIT_EVIDENCE')
    if directory:
        with (Path(directory)/('identity-wait-'+entry+'-'+purpose+'.json')).open('x') as out:json.dump(record,out,indent=2)
    assert outcome['rejected'] and outcome['reason']=='current contained half-open certificate interval required',record


@pytest.mark.parametrize('order',['reader-first','writer-first'])
@pytest.mark.parametrize('purpose',['target','judge'])
def test_runtime_executor_identity_withdrawal_native(order,purpose):
    _persisted_model_case_native(identity_gate=True,expiry_wait=('runtime-withdrawal-'+order,purpose))


def _runtime_executor_identity_withdrawal_native(module,reader,plan,plan_hash,root_hash,certs,purpose,owned,*,order):
    """Original runtime bridge and real withdrawal, no output or transport."""
    import importlib,json,threading,queue,time,os
    from pathlib import Path
    from aos_api.aip_model_runtime_store import canonical_hash
    authority=importlib.import_module('aos_api.aip_model_eval_execution_authority')
    with psycopg.connect(get_dsn()) as install:
        if install.execute("SELECT to_regclass('aos_model_eval_issuer_private.identity_epoch')").fetchone()[0] is None:
            authority.install_closed_model_identity_authority(install.execute)
        if install.execute("SELECT to_regprocedure('public.read_model_executor_set_facts(text,text)')").fetchone()[0] is None:
            for statement in authority.runtime_executor_fact_statements():install.execute(statement)
        install.commit()
    items=[]
    for leg in ('target','judge'):
        digest=canonical_hash(certs[leg].model_dump(mode='json',by_alias=True))
        with owned() as c:
            reader.register_persisted_model_identity(c,expected_tenant=plan.tenant,execution_id=plan.execution_id,manifest_hash=plan_hash,
                certificate_hash=digest,root_hash=root_hash,expected_root_epoch=1,expected_certificate_epoch=1)
            c.commit()
        items.append(dict(caseId=plan.cases[0].case_id,purpose=leg,certificateHash=digest,rootHash=root_hash,rootEpoch=1,certificateEpoch=1,identityEpoch=1))
    args=dict(expected_tenant=plan.tenant,execution_id=plan.execution_id,manifest_hash=plan_hash,certificates=tuple(items))
    event=dict(schemaVersion='aos.model-eval-identity-withdrawal/v1',tenant=plan.tenant.model_dump(mode='json',by_alias=True),
               identityId=getattr(plan.cases[0],purpose).identity_id,eventId=plan.execution_id+'-withdraw')
    raw=json.dumps(event,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
    insert='INSERT INTO aos_model_eval_issuer_private.identity_withdrawal(org_id,project_id,event_id,identity_id,content_hash,body) VALUES (%s,%s,%s,%s,%s,%s)'
    params=('org-org','dev-project',event['eventId'],event['identityId'],hashlib.sha256(raw).hexdigest(),raw)
    with owned('aos_runtime') as positive:
        assert reader.validate_runtime_model_executor_set(positive,**args) is None
        positive.rollback()
    ready=queue.Queue();terminal=queue.Queue();blocked=False
    def observe_wait(waiter,holder):
        with psycopg.connect(get_dsn(),autocommit=True) as monitor:
            until=time.monotonic()+5
            while time.monotonic()<until:
                if holder in monitor.execute('SELECT pg_blocking_pids(%s)',(waiter,)).fetchone()[0]:return True
                time.sleep(.02)
        return False
    if order=='reader-first':
        c=owned('aos_runtime');c.execute("SET LOCAL statement_timeout='12s'")
        before=c.execute('SELECT clock_timestamp(),pg_current_xact_id()::text').fetchone()
        assert reader.validate_runtime_model_executor_set(c,**args) is None
        reader_pid=c.info.backend_pid
        def withdraw():
            try:
                with owned() as writer:
                    writer.execute("SET LOCAL statement_timeout='12s'")
                    writer_xid=writer.execute('SELECT pg_current_xact_id()::text').fetchone()[0]
                    ready.put(writer.info.backend_pid);writer.execute(insert,params);writer.commit()
                    terminal.put(dict(writer_xid=writer_xid))
            except Exception as exc:terminal.put(exc)
        worker=threading.Thread(target=withdraw);worker.start()
        try:
            writer_pid=ready.get(timeout=5);blocked=observe_wait(writer_pid,reader_pid)
            assert blocked and worker.is_alive(),'native withdrawal writer must wait on runtime reader'
            after=c.execute('SELECT clock_timestamp(),pg_current_xact_id()::text').fetchone();assert before[1]==after[1]
            c.commit()
        finally:
            c.close();worker.join(timeout=15)
        assert not worker.is_alive();outcome=terminal.get(timeout=1);assert isinstance(outcome,dict),repr(outcome)
        record=dict(caller_xid=before[1],caller_state='committed',before=before[0].isoformat(),after=after[0].isoformat(),**outcome)
    else:
        writer=owned();writer.execute("SET LOCAL statement_timeout='12s'")
        writer_xid=writer.execute('SELECT pg_current_xact_id()::text').fetchone()[0];writer_pid=writer.info.backend_pid
        writer.execute(insert,params)
        def consume():
            try:
                with owned('aos_runtime') as call:
                    call.execute("SET LOCAL statement_timeout='12s'")
                    before=call.execute('SELECT clock_timestamp(),pg_current_xact_id()::text').fetchone();ready.put(call.info.backend_pid)
                    try:reader.validate_runtime_model_executor_set(call,**args)
                    except ValueError as exc:
                        outcome=dict(reason=str(exc),sqlstate=getattr(exc.__cause__,'sqlstate',None),caller_xid=before[1],caller_state='aborted',before=before[0].isoformat())
                    else:raise AssertionError('old snapshot accepted actual withdrawal')
                    call.rollback();terminal.put(outcome)
            except Exception as exc:terminal.put(exc)
        worker=threading.Thread(target=consume);worker.start()
        try:
            reader_pid=ready.get(timeout=5);blocked=observe_wait(reader_pid,writer_pid)
            assert blocked and worker.is_alive(),'native runtime consumer must wait on pending identity withdrawal'
            writer.commit()
        finally:
            writer.close();worker.join(timeout=15)
        assert not worker.is_alive();outcome=terminal.get(timeout=1);assert isinstance(outcome,dict),repr(outcome)
        assert outcome['sqlstate']=='40001',outcome
        record=dict(writer_xid=writer_xid,**outcome)
    with owned('aos_runtime') as fresh:
        with pytest.raises(ValueError) as denied:reader.validate_runtime_model_executor_set(fresh,**args)
        assert getattr(denied.value.__cause__,'sqlstate',None)=='23514'
        fresh.rollback()
    with owned() as inspect:
        head=inspect.execute('SELECT epoch,version,active FROM aos_model_eval_issuer_private.identity_epoch WHERE identity_id=%s',(event['identityId'],)).fetchone()
        assert head==(2,2,False)
        assert inspect.execute('SELECT count(*) FROM aos_model_eval_execution_private.case_result WHERE execution_id=%s',(plan.execution_id,)).fetchone()[0]==0
        inspect.rollback()
    record.update(order=order,purpose=purpose,execution_id=plan.execution_id,manifest_hash=plan_hash,certificate_inputs=items,
                  withdrawal_event=event,withdrawal_hash=hashlib.sha256(raw).hexdigest(),actual_blocking=blocked,reader_pid=reader_pid,writer_pid=writer_pid,
                  fresh_sqlstate='23514',head=dict(epoch=head[0],version=head[1],active=head[2]),output_count=0,execution_allowed=False)
    directory=os.environ.get('AOS_IDENTITY_WAIT_EVIDENCE')
    if directory:
        with (Path(directory)/('runtime-withdrawal-'+order+'-'+purpose+'.json')).open('x') as out:json.dump(record,out,indent=2)
