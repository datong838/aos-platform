"""Ledger constraints in the opt-in disposable schema, not live approvals."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb
import pytest

from test_lifecycle_pg import database, pytestmark
from test_configuration_target_pg import case


@pytest.fixture
def ledger(database):
    conn, _, schema = database
    args = case(conn)
    conn.execute('''CREATE TABLE data_source_configuration_revision(
        org_id text,project_id text,source_id text,revision_id uuid,
        PRIMARY KEY(org_id,project_id,source_id,revision_id))''')
    source_revision = uuid4()
    conn.execute("INSERT INTO data_source_configuration_revision VALUES('org-org','dev-project','test-source',%s)", (source_revision,))
    path = Path(__file__).resolve().parents[2] / 'alembic/versions/a0v_022_pipeline_source_selection.py'
    spec = importlib.util.spec_from_file_location('selection_ledger_test_migration', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.op = SimpleNamespace(execute=conn.execute)
    module.upgrade()
    conn.execute(sql.SQL('GRANT USAGE ON SCHEMA {} TO aos_runtime').format(sql.Identifier(schema)))
    row = dict(org_id='org-org', project_id='dev-project', installation_id=args['installation_id'],
        generation=args['configuration_target']['generation'], pipeline_id='test-pipeline', selection_id=uuid4(),
        revision=1, source_id='test-source', source_configuration_revision=source_revision,
        content_hash='sha256:'+'a'*64, previous_revision=None, previous_hash=None,
        request_hash='sha256:'+'b'*64, idempotency_key='first', actor='test-actor')
    return conn, row, module


def append(conn, row, *, payload_override=None):
    names = {'org_id':'orgId', 'project_id':'projectId', 'installation_id':'installationId',
        'generation':'generation', 'pipeline_id':'pipelineId', 'selection_id':'selectionId',
        'revision':'revision', 'source_id':'sourceId', 'source_configuration_revision':'sourceConfigurationRevision',
        'actor':'actor'}
    body = {'schemaVersion':'aos.pipeline-source-selection-revision/v1'}
    body.update({target:(row[source] if source=='revision' else str(row[source])) for source,target in names.items()})
    if payload_override is not None:
        body = payload_override
    columns = tuple(row) + ('payload',)
    conn.execute(sql.SQL('INSERT INTO pipeline_source_selection_revision ({}) VALUES ({})').format(
        sql.SQL(',').join(map(sql.Identifier, columns)), sql.SQL(',').join(sql.Placeholder() for _ in columns)),
        (*row.values(), Jsonb(body)))


def test_valid_chain_and_duplicate_revisions_are_database_enforced(ledger):
    conn, first, _ = ledger
    conn.execute('SET ROLE aos_runtime')
    append(conn, first)
    second = first | dict(revision=2, previous_revision=1, previous_hash=first['content_hash'],
        content_hash='sha256:'+'c'*64, idempotency_key='second')
    append(conn, second)
    assert conn.execute('SELECT revision FROM pipeline_source_selection_revision ORDER BY revision').fetchall() == [(1,), (2,)]
    with pytest.raises(psycopg.errors.UniqueViolation):
        append(conn, second)


@pytest.mark.parametrize('mode', ['hash', 'skip', 'identity', 'source', 'generation', 'idempotency'])
def test_bad_chain_or_reference_is_rejected(ledger, mode):
    conn, first, _ = ledger
    append(conn, first)
    second = first | dict(revision=2, previous_revision=1, previous_hash=first['content_hash'],
        content_hash='sha256:'+'c'*64, idempotency_key='second')
    if mode == 'hash': second['previous_hash'] = 'sha256:'+'d'*64
    elif mode == 'skip': second['revision'] = 3
    elif mode == 'identity': second['selection_id'] = uuid4()
    elif mode == 'source':
        other_revision = uuid4()
        conn.execute("INSERT INTO data_source_configuration_revision VALUES('dev-org','dev-project','test-source',%s)", (other_revision,))
        second['source_configuration_revision'] = other_revision
    elif mode == 'generation': second['generation'] = uuid4()
    else: second['idempotency_key'] = first['idempotency_key']
    with pytest.raises(psycopg.IntegrityError):
        append(conn, second)
    assert conn.execute('SELECT count(*) FROM pipeline_source_selection_revision').fetchone() == (1,)


def test_tenant_isolation_hides_rows_and_rejects_cross_scope_write(ledger):
    conn, row, _ = ledger
    append(conn, row)
    conn.execute('SET ROLE aos_runtime')
    conn.execute("SELECT set_config('aos.org_id','dev-org',false)")
    assert conn.execute('SELECT count(*) FROM pipeline_source_selection_revision').fetchone() == (0,)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        append(conn, row | dict(idempotency_key='cross-scope'))


@pytest.mark.parametrize('statement', [
    "UPDATE pipeline_source_selection_revision SET actor='changed'",
    'DELETE FROM pipeline_source_selection_revision',
    'TRUNCATE pipeline_source_selection_revision',
])
def test_history_cannot_be_mutated_even_by_owner(ledger, statement):
    conn, row, _ = ledger
    append(conn, row)
    with pytest.raises(psycopg.DatabaseError, match='immutable'):
        conn.execute(statement)
    assert conn.execute('SELECT count(*) FROM pipeline_source_selection_revision').fetchone() == (1,)


@pytest.mark.parametrize('body', [{}, {'schemaVersion':'aos.pipeline-source-selection-revision/v1', 'orgId':'dev-org'}])
def test_missing_or_different_payload_scope_is_not_accepted_as_null(ledger, body):
    conn, row, _ = ledger
    with pytest.raises(psycopg.errors.CheckViolation):
        append(conn, row, payload_override=body)


def test_destructive_downgrade_is_not_available(ledger):
    _, _, migration = ledger
    with pytest.raises(RuntimeError, match='retained'):
        migration.downgrade()
