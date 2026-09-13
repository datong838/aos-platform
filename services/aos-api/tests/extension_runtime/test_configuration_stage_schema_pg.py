"""Staging transport constraints in disposable PostgreSQL schemas only."""
import ast
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import psycopg
from psycopg.types.json import Jsonb
import pytest

from test_lifecycle_pg import database, pytestmark
from test_configuration_store_pg import configuration_case
from test_configuration_stage_contracts import request
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.extension_runtime.configuration_contracts import ConfigurationDocument
from aos_api.extension_runtime.configuration_store import append_configuration

TABLE = 'extension_runtime_configuration_stage_request'


@pytest.fixture
def stage(configuration_case, database):
    conn, args = configuration_case
    _, _, schema = database
    conn.execute('RESET ROLE')
    root = Path(__file__).resolve().parents[2]/'alembic/versions'
    source = ast.parse((root/'228asset0_evidence_snapshot.py').read_text())
    conn.execute(next(n.value for n in ast.walk(source) if isinstance(n, ast.Constant)
        and isinstance(n.value, str) and n.value.strip().startswith('CREATE OR REPLACE FUNCTION canonical_asset_registry_jsonb')))
    spec = importlib.util.spec_from_file_location('configuration_stage_migration', root/'a0v_036_runtime_configuration_stage.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    module.op = SimpleNamespace(execute=lambda q: conn.execute(q.replace(
        'SET search_path=pg_catalog,public,pg_temp', f'SET search_path=pg_catalog,{schema},pg_temp')))
    module.upgrade()
    body = request()
    body['target'].update(installationId=str(args['installation_id']), installationEtag=1,
                          generation=str(args['generation']), bindingRevision=1)
    body['previousRef'] = None
    return conn, args, body


def insert(stage, *, body=None, subject='test-actor', digest=None, key=None):
    conn, args, original = stage
    body = original if body is None else body
    identity = uuid4()
    digest = digest or canonical_sha256(dict(tenant=dict(orgId='org-org', projectId='dev-project'),
                                             subject=subject, request=body))
    conn.execute(f'''INSERT INTO {TABLE}(org_id,project_id,request_id,subject,idempotency_key,
       installation_id,generation,installation_etag,binding_revision,request_json,request_hash,deadline)
       VALUES('org-org','dev-project',%s,%s,%s,%s,%s,1,1,%s,%s,clock_timestamp()+interval '1 minute')''',
       (identity,subject,key or str(identity),args['installation_id'],args['generation'],Jsonb(body),digest))
    return identity


def complete(conn, ref):
    conn.execute(f"UPDATE {TABLE} SET state='succeeded',revision=2,completed_at=clock_timestamp(),result_json=%s", (Jsonb(ref),))


def record(stage, identity, **changes):
    conn, args, body = stage
    data = dict(args['configuration'])
    data.update(roleRefs=tuple(body['roleRefs']), policyRef=body['policyRef'])
    # Association fixture only; production permission is tested by its original adapter.
    values = dict(args, configuration=ConfigurationDocument.model_validate(data), authorize=lambda *a, **k: True,
                  idempotency_key='configuration-stage:'+str(identity))
    values.update(changes)
    with conn.transaction(): return append_configuration(conn, **values).model_dump(mode='json')


def test_success_is_exact_owned_request_configuration(stage):
    conn, _, _ = stage
    identity = insert(stage)
    ref = record(stage, identity)
    conn.execute('SET ROLE aos_runtime')
    complete(conn, ref)
    assert conn.execute(f'SELECT state,result_json FROM {TABLE}').fetchone() == ('succeeded', ref)
    with pytest.raises(psycopg.Error): complete(conn, ref)


@pytest.mark.parametrize('case', ('missing', 'wrong_actor', 'wrong_key', 'wrong_source', 'wrong_hash'))
def test_success_cannot_borrow_an_unrelated_configuration(stage, case):
    conn, args, body = stage
    identity = insert(stage)
    if case == 'missing': ref = dict(configurationId=str(uuid4()), revision=1, hash='sha256:'+'a'*64)
    else:
        changes = {}
        if case == 'wrong_actor': changes['actor'] = 'another-actor'
        if case == 'wrong_key': changes['idempotency_key'] = 'unrelated'
        if case == 'wrong_source':
            changed = dict(args['configuration'])
            changes['configuration'] = ConfigurationDocument.model_validate(changed)
        ref = record(stage, identity, **changes)
        if case == 'wrong_hash': ref['hash'] = 'sha256:'+'f'*64
    with pytest.raises(psycopg.Error): complete(conn, ref)
    assert conn.execute(f'SELECT state FROM {TABLE}').fetchone()[0] == 'requested'


@pytest.mark.parametrize('case', ('subject', 'role_empty', 'role_duplicate', 'policy_authority',
                                  'target_version', 'target_float', 'previous', 'digest', 'extra', 'missing', 'role_null'))
def test_sql_input_boundary_rejects_bypassed_python_contract(stage, case):
    import copy
    conn, _, body = stage
    body = copy.deepcopy(body)
    changes = {}
    if case == 'subject': changes['subject'] = ' bad '
    elif case == 'role_empty': body['roleRefs'] = []
    elif case == 'role_duplicate': body['roleRefs'] *= 2
    elif case == 'role_null': body['roleRefs'] = [None]
    elif case == 'policy_authority': body['policyRef']['authority'] = 'other'
    elif case == 'target_version': body['target']['bindingRevision'] = True
    elif case == 'target_float': body['target']['installationEtag'] = 1.0
    elif case == 'previous': body['previousRef'] = {}
    elif case == 'digest': changes['digest'] = 'sha256:'+'f'*64
    elif case == 'extra': body['subject'] = 'other'
    elif case == 'missing': del body['previousRef']
    with pytest.raises(psycopg.Error): insert(stage, body=body, **changes)
    assert conn.execute(f'SELECT count(*) FROM {TABLE}').fetchone()[0] == 0


@pytest.mark.parametrize('sql', (
    f"UPDATE {TABLE} SET subject='other'", f'DELETE FROM {TABLE}', f'TRUNCATE {TABLE}',
    f"UPDATE {TABLE} SET state='expired',revision=2,completed_at=clock_timestamp(),failure_code='EXPIRED'",
))
def test_identity_history_and_early_expiry_are_rejected(stage, sql):
    conn, _, _ = stage
    insert(stage)
    with pytest.raises(psycopg.Error): conn.execute(sql)


def test_target_drift_and_duplicate_key_are_rejected(stage):
    conn, _, _ = stage
    insert(stage, key='same')
    with pytest.raises(psycopg.Error): insert(stage, key='same')
    conn.execute('UPDATE bundle_installation SET etag_version=2')
    with pytest.raises(psycopg.Error): insert(stage)


def test_runtime_is_column_limited_and_tenant_isolated(stage):
    conn, _, _ = stage
    insert(stage)
    conn.execute('SET ROLE aos_runtime')
    assert conn.execute(f'SELECT count(*) FROM {TABLE}').fetchone()[0] == 1
    with pytest.raises(psycopg.errors.InsufficientPrivilege): insert(stage)
    with pytest.raises(psycopg.errors.InsufficientPrivilege): conn.execute(f"UPDATE {TABLE} SET subject='other'")
    conn.execute("SELECT set_config('aos.org_id','dev-org',false)")
    assert conn.execute(f'SELECT count(*) FROM {TABLE}').fetchone()[0] == 0


def test_rejected_result_cannot_be_reopened(stage):
    conn, _, _ = stage
    insert(stage)
    conn.execute('SET ROLE aos_runtime')
    conn.execute(f"UPDATE {TABLE} SET state='rejected',revision=2,completed_at=clock_timestamp(),failure_code='ACCESS_DENIED'")
    with pytest.raises(psycopg.Error):
        conn.execute(f"UPDATE {TABLE} SET state='requested',revision=3,completed_at=NULL,failure_code=NULL")
    assert conn.execute(f'SELECT state FROM {TABLE}').fetchone()[0] == 'rejected'
