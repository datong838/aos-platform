import importlib
import json
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def identity(monkeypatch,tmp_path):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[4] / 'scripts'))
    module=importlib.import_module('a0v_ui_read_identity')
    monkeypatch.setattr(module,'STATE',tmp_path)
    monkeypatch.setattr(module,'require_lease',lambda:None)
    return module


def test_existing_role_without_private_file_never_resets_identity(identity,monkeypatch):
    monkeypatch.setattr(identity,'_assert_database',lambda *_:{})
    conn=SimpleNamespace(execute=lambda *a:SimpleNamespace(fetchone=lambda:{'exists':1}))
    monkeypatch.setattr(identity.deployment.storage,'connect',lambda *a,**k:nullcontext(conn))
    monkeypatch.setattr(identity.secrets,'token_urlsafe',lambda *_:pytest.fail('identity regenerated'))
    with pytest.raises(ValueError,match='retained identity'):identity.clone()
    assert not (identity.STATE/'ui-read-clone-identity.json').exists()


def test_unverified_main_schema_never_derives_main_identity(identity,monkeypatch):
    monkeypatch.setattr(identity,'verify',lambda *a:{})
    (identity.STATE/'apply.json').write_text(json.dumps({'outcome':'UI_READ_LOCAL_SCHEMA_DEPLOYED','revision':'a0v_030'}))
    monkeypatch.setattr(identity,'_read_private',lambda *_:pytest.fail('private identity read too early'))
    with pytest.raises(ValueError,match='main deployment'):identity.main_identity()


def test_existing_main_identity_cannot_be_overwritten(identity,monkeypatch):
    from psycopg.conninfo import make_conninfo
    monkeypatch.setattr(identity,'verify',lambda *a:{})
    monkeypatch.setattr(identity,'_assert_database',lambda *a:{})
    (identity.STATE/'apply.json').write_text(json.dumps({'outcome':'UI_READ_LOCAL_SCHEMA_DEPLOYED','revision':'a0v_035'}))
    target=identity.STATE/'ui-read-main-identity.json';target.write_text('retained')
    clone=dict(schemaVersion=identity.SCHEMA,role=identity.ROLE,
        dsn=make_conninfo(dbname=identity.deployment.CLONE,user=identity.ROLE))
    monkeypatch.setattr(identity,'_read_private',lambda path:clone if 'clone' in path.name else {})
    with pytest.raises(ValueError,match='main identity differs'):identity.main_identity()
    assert target.read_text()=='retained'


def test_invalid_private_file_restores_environment_without_leak(identity,monkeypatch):
    from aos_api.extension_runtime.ui_read_connection import CREDENTIAL_FILE
    monkeypatch.setenv(CREDENTIAL_FILE,'old-reference')
    with pytest.raises(RuntimeError):identity._read_private(identity.STATE/'absent.json')
    assert identity.os.environ[CREDENTIAL_FILE]=='old-reference'
