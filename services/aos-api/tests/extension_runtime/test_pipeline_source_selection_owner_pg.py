"""Persistence/CAS only. The named fake current check is not permission evidence."""
from datetime import datetime, timedelta, timezone

import pytest

from test_pipeline_source_selection_schema_pg import ledger
from test_lifecycle_pg import database, pytestmark
from tests.test_pipeline_runtime_control_contracts import payload
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict, RuntimeRevisionConflict
from aos_api.pipeline_runtime_control_contracts import PipelineSourceSelectionDraft
from aos_api.pipeline_source_selection import MappingReadSpec
from aos_api.pipeline_source_selection_owner import PipelineSourceSelectionOwner


@pytest.fixture
def owner_case(ledger):
    conn, row, _ = ledger
    body = payload()
    body.pop('sourceSelectionRef')
    body['orgId'], body['projectId'] = row['org_id'], row['project_id']
    body['pipelineId'] = row['pipeline_id']
    body['installationRef']['installationId'] = str(row['installation_id'])
    body['generation'] = str(row['generation'])
    body['sourceId'] = row['source_id']
    body['sourceConfigurationRef']['resourceId'] = 'source-config-'+str(row['source_configuration_revision'])
    body['notBefore'] = datetime.now(timezone.utc)-timedelta(minutes=1)
    body['expiresAt'] = body['notBefore']+timedelta(hours=1)
    draft = PipelineSourceSelectionDraft.model_validate(body)
    spec = MappingReadSpec('ns_site','Shop','site_id',('site_id','site_name'),(('site_id',1),))
    owner = object.__new__(PipelineSourceSelectionOwner)
    calls = []
    def named_fake_current_check(db, item, actor, callback):
        calls.append(actor)
        return callback(spec)
    owner._guarded = named_fake_current_check
    # Only the disposable fixture parent: production grants are unchanged.
    assert conn.execute('SELECT current_schema()').fetchone()[0] != 'public'
    conn.execute('GRANT SELECT, UPDATE ON bundle_installation TO aos_runtime')
    conn.execute('SET ROLE aos_runtime')
    return conn, owner, draft, calls


def approve(conn, owner, draft, key='first', previous=None):
    with conn.transaction():
        return owner.append(conn, draft=draft, actor='test-actor', idempotency_key=key, previous_ref=previous)


def test_append_replay_and_next_revision_are_atomic(owner_case):
    conn, owner, draft, calls = owner_case
    first = approve(conn, owner, draft)
    assert approve(conn, owner, draft) == first
    assert len(calls) == 2
    assert conn.execute('SELECT count(*) FROM pipeline_source_selection_revision').fetchone() == (1,)
    second = approve(conn, owner, draft.model_copy(update={'row_limit':5}), 'second', first)
    assert second.resource_id == first.resource_id and second.revision == 2
    with pytest.raises(RuntimeRevisionConflict):
        approve(conn, owner, draft, 'stale', first)
    with pytest.raises(RuntimeConflict):
        approve(conn, owner, draft.model_copy(update={'row_limit':6}))
    assert conn.execute('SELECT count(*) FROM pipeline_source_selection_revision').fetchone() == (2,)


def test_outer_rollback_removes_append(owner_case):
    conn, owner, draft, _ = owner_case
    with pytest.raises(RuntimeError, match='rollback test'), conn.transaction():
        owner.append(conn, draft=draft, actor='test-actor', idempotency_key='rollback')
        raise RuntimeError('rollback test')
    assert conn.execute('SELECT count(*) FROM pipeline_source_selection_revision').fetchone() == (0,)


def test_replay_does_not_skip_current_denial(owner_case):
    conn, owner, draft, _ = owner_case
    approve(conn, owner, draft)
    def denied(*args): raise PermissionError('named current denial')
    owner._guarded = denied
    with pytest.raises(PermissionError):
        approve(conn, owner, draft)
    assert conn.execute('SELECT count(*) FROM pipeline_source_selection_revision').fetchone() == (1,)


@pytest.mark.parametrize('mode', ['tenant','role'])
def test_wrong_connection_identity_never_reaches_current_reader(owner_case, mode):
    conn, owner, draft, calls = owner_case
    if mode == 'tenant': conn.execute("SELECT set_config('aos.org_id','dev-org',false)")
    else: conn.execute('RESET ROLE')
    with pytest.raises(PermissionError):
        approve(conn, owner, draft)
    assert calls == []
