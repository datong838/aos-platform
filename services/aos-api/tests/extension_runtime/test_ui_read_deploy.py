import importlib
import os
from pathlib import Path

import pytest
import psycopg
from psycopg.rows import dict_row


@pytest.fixture
def deploy(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[4] / 'scripts'))
    return importlib.import_module('a0v_ui_read_deploy')


def test_exact_checked_in_migration_chain(deploy):
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    cfg=Config(str(deploy.ROOT/'services/aos-api/alembic.ini'))
    cfg.set_main_option('script_location',str(deploy.ROOT/'services/aos-api/alembic'))
    directory=ScriptDirectory.from_config(cfg)
    assert directory.get_heads()==[deploy.TARGET]
    assert [r.revision for r in directory.iterate_revisions(deploy.TARGET,deploy.SOURCE)]==deploy.CHAIN
    assert len(deploy.storage.migration_hashes())==5


@pytest.mark.parametrize('grant',[None,'INSERT','UPDATE(subject)'])
def test_real_full_schema_verifier_rejects_widened_queue_acl(deploy,grant):
    with psycopg.connect(os.environ['AOS_DATABASE_URL'],row_factory=dict_row) as conn:
        assert conn.info.dbname.endswith('_ti4_test')
        if grant:
            conn.execute(f'GRANT {grant} ON public.extension_runtime_ui_read_request TO aos_runtime')
            with pytest.raises(ValueError):deploy.verify(conn)
        else:
            result=deploy.verify(conn)
            assert result['forceRls'] and result['queueCount']==0 and result['restrictedFunctionCount']==5
        conn.rollback()


@pytest.fixture
def proof(deploy,tmp_path,monkeypatch):
    monkeypatch.setattr(deploy,'STATE',tmp_path)
    backup=tmp_path/'aos_meta_head-before-a0v_035.dump';backup.write_bytes(b'retained-backup');backup.chmod(0o600)
    value=dict(outcome='UI_READ_RESTORE_VERIFIED',source=deploy.SOURCE,target=deploy.TARGET,
        main=deploy.storage.MAIN,clone=deploy.CLONE,migrations=deploy.storage.migration_hashes(),
        executors=deploy.executor_hashes(),backup=dict(path=str(backup),sha256=deploy.storage.digest(backup),bytes=backup.stat().st_size),
        before={'business':{'count':1,'digest':'same'}},after={'business':{'count':1,'digest':'same'}})
    return value


def test_proof_and_backup_bytes_are_bound(deploy,proof):
    deploy.validate_proof(proof)
    (deploy.STATE/'aos_meta_head-before-a0v_035.dump').write_bytes(b'changed')
    with pytest.raises(ValueError):deploy.validate_proof(proof)


@pytest.mark.parametrize('field',['source','target','executors','migrations','after'])
def test_drifted_preparation_cannot_authorize_apply(deploy,proof,field):
    proof[field]='changed'
    with pytest.raises(ValueError):deploy.validate_proof(proof)


def test_existing_intent_never_retries_migration(deploy,tmp_path,monkeypatch):
    monkeypatch.setattr(deploy,'STATE',tmp_path)
    monkeypatch.setattr(deploy,'require_lease',lambda:None)
    monkeypatch.setattr(deploy,'upgrade',lambda *_:pytest.fail('migration replayed'))
    (tmp_path/'apply-intent.json').write_text('{}')
    with pytest.raises(ValueError,match='readback'):deploy.apply()


def test_durable_proof_is_private_and_never_overwritten(deploy,tmp_path):
    path=tmp_path/'intent.json'
    deploy.protected_write(path,{'target':'a0v_035'})
    original=path.read_bytes()
    assert path.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):deploy.protected_write(path,{'target':'other'})
    assert path.read_bytes()==original
