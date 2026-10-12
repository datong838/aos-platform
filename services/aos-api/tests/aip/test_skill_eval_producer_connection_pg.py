"""Private connection and commit boundary in isolated native PostgreSQL."""
import json
import os

import psycopg
import pytest
from psycopg.pq import TransactionStatus
from psycopg.conninfo import conninfo_to_dict

from aos_api.aip_skill_eval_producer_connection import (
    configured_skill_producer_connection, skill_producer_connection,
)
from aos_api.aip_eval_writer_connection import _identity_file
from test_skill_eval_producer_identity_pg import producer_login
from test_skill_eval_atomic_finisher_pg import complete_source

ENV = 'AOS_AIP_SKILL_PRODUCER_CREDENTIAL_FILE'
SCHEMA = 'aos.aip.skill-producer-identity/v1'


@pytest.fixture(autouse=True)
def exact_isolated_database():
    parts=conninfo_to_dict(os.environ['AOS_DATABASE_URL'])
    assert parts['host']=='127.0.0.1' and parts['port']=='18431'
    assert parts['dbname'].startswith('aos_test_') and parts['dbname'].endswith('_ti4_test')


def identity_file(tmp_path, dsn, schema=SCHEMA, role='aos_skill_eval_finisher'):
    path=tmp_path/'producer.json'
    path.write_text(json.dumps({'schemaVersion':schema,'dsn':dsn,'role':role}))
    path.chmod(0o600)
    return path


def test_unconfigured_never_falls_back(monkeypatch):
    monkeypatch.delenv(ENV,raising=False)
    monkeypatch.setenv('AOS_DATABASE_URL','ignored-runtime-identity')
    assert configured_skill_producer_connection() is None
    monkeypatch.setattr(psycopg,'connect',lambda *a,**k:pytest.fail('unconfigured connect'))
    with pytest.raises(RuntimeError):
        with skill_producer_connection(expected_database='unused'):pass


@pytest.mark.parametrize('bad',['permissions','schema','role','duplicate','symlink'])
def test_invalid_file_rejects_before_connect(tmp_path,monkeypatch,bad):
    path=identity_file(tmp_path,'unused')
    if bad=='permissions':path.chmod(0o644)
    elif bad=='schema':path=identity_file(tmp_path,'unused',schema='wrong')
    elif bad=='role':path=identity_file(tmp_path,'unused',role='aos_runtime')
    elif bad=='duplicate':path.write_text('{"schemaVersion":"'+SCHEMA+'","dsn":"unused","role":"aos_skill_eval_finisher","dsn":"changed"}')
    else:
        link=tmp_path/'link.json';link.symlink_to(path);path=link
    monkeypatch.setenv(ENV,str(path))
    monkeypatch.setattr(psycopg,'connect',lambda *a,**k:pytest.fail('invalid file connected'))
    with pytest.raises(RuntimeError):
        with skill_producer_connection(expected_database='unused'):pass


@pytest.mark.parametrize('commit',[False,True])
def test_idle_verified_connection_explicit_commit_only(producer_login,tmp_path,monkeypatch,commit):
    login,database,dsn=producer_login
    with psycopg.connect(os.environ['AOS_DATABASE_URL']) as admin:
        admin.execute('CREATE TABLE producer_commit_fixture(value integer)')
        from psycopg import sql
        admin.execute(sql.SQL('GRANT INSERT,SELECT ON producer_commit_fixture TO {}').format(sql.Identifier(login)))
    monkeypatch.setenv(ENV,str(identity_file(tmp_path,dsn)))
    try:
        connector=configured_skill_producer_connection();assert connector is skill_producer_connection
        with connector(expected_database=database) as conn:
            assert conn.info.transaction_status==TransactionStatus.IDLE
            conn.execute('INSERT INTO producer_commit_fixture VALUES(1)')
            if commit:conn.commit()
        assert conn.closed
        with psycopg.connect(os.environ['AOS_DATABASE_URL']) as reader:
            assert reader.execute('SELECT count(*) FROM producer_commit_fixture').fetchone()[0]==int(commit)
    finally:
        with psycopg.connect(os.environ['AOS_DATABASE_URL']) as admin:
            admin.execute('DROP TABLE producer_commit_fixture')


@pytest.mark.parametrize('bad',['database','administrator'])
def test_native_identity_not_accepted(producer_login,tmp_path,monkeypatch,bad):
    _,database,dsn=producer_login
    monkeypatch.setenv(ENV,str(identity_file(tmp_path,os.environ['AOS_DATABASE_URL'] if bad=='administrator' else dsn)))
    with pytest.raises(RuntimeError,match='not permitted'):
        with skill_producer_connection(expected_database='wrong' if bad=='database' else database):
            pytest.fail('wrong identity yielded')


def test_shared_loader_keeps_original_writer_shape(tmp_path,monkeypatch):
    path=identity_file(tmp_path,'unused',schema='aos.aip.eval-writer-identity/v1',role='aos_aip_eval_writer')
    monkeypatch.setenv('AOS_AIP_EVAL_WRITER_CREDENTIAL_FILE',str(path))
    assert _identity_file()['role']=='aos_aip_eval_writer'
    monkeypatch.setenv(ENV,str(path))
    with pytest.raises(RuntimeError):
        with skill_producer_connection(expected_database='unused'):pass


@pytest.mark.parametrize('bad',['permissions','schema','role','duplicate','symlink'])
def test_original_writer_loader_still_rejects_invalid_file(tmp_path,monkeypatch,bad):
    path=identity_file(tmp_path,'unused',schema='aos.aip.eval-writer-identity/v1',role='aos_aip_eval_writer')
    if bad=='permissions':path.chmod(0o644)
    elif bad=='schema':path=identity_file(tmp_path,'unused',schema='wrong',role='aos_aip_eval_writer')
    elif bad=='role':path=identity_file(tmp_path,'unused',schema='aos.aip.eval-writer-identity/v1',role='aos_runtime')
    elif bad=='duplicate':path.write_text('{"schemaVersion":"aos.aip.eval-writer-identity/v1","dsn":"unused","role":"aos_aip_eval_writer","dsn":"changed"}')
    else:
        link=tmp_path/'old-link.json';link.symlink_to(path);path=link
    monkeypatch.setenv('AOS_AIP_EVAL_WRITER_CREDENTIAL_FILE',str(path))
    with pytest.raises(RuntimeError,match='Eval writer identity reference is invalid'):
        _identity_file()


@pytest.mark.parametrize('commit',[True,False])
def test_private_connector_with_full_atomic_ending(complete_source,tmp_path,monkeypatch,commit):
    from aos_api.aip_skill_eval_atomic_finisher import finish_signed_skill_eval_with_connection
    from test_aip_eval_execution_authority import INPUT_HASH
    from test_qyh_signed_proof_transaction_pg import SCOPE,view
    admin_dsn,dsn,report,pair,intent,event=complete_source
    before=view(admin_dsn,intent)
    monkeypatch.setenv(ENV,str(identity_file(tmp_path,dsn)))
    with skill_producer_connection(expected_database=psycopg.conninfo.conninfo_to_dict(dsn)['dbname']) as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
        conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",SCOPE.key)
        proof=finish_signed_skill_eval_with_connection(conn,expected_database=conn.info.dbname,
            scope=SCOPE,intent_id=intent,expected_intent_version=3,request_hash='a'*64,
            event=event,expected_run_version=2,report=report,
            expected_input_hashes={'case-1':INPUT_HASH},presented={'case-1':pair})
        assert proof.report_hash==report.content_hash and view(admin_dsn,intent)==before
        if commit:conn.commit()
    assert view(admin_dsn,intent)==(({'status':'succeeded','version':3},[2,1,1],4,3) if commit else before)
