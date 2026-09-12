"""Configuration registration cannot create execution evidence."""
import pytest
from aos_api.db import connect
from aos_api.auth import Principal
from aos_api.routers import wave_ext
from aos_api.tenant_scope import TenantScope


TEST_SCOPE = TenantScope('pipeline-registration-test', 'pipeline-registration-workspace')


@pytest.fixture
def auth_headers():
    with connect() as conn:
        conn.execute("INSERT INTO twa_org(id,name) VALUES (%s,%s) ON CONFLICT DO NOTHING",
                     (TEST_SCOPE.org_id, 'Isolated registration test'))
        conn.execute("INSERT INTO twa_workspace(org_id,project_id,name) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
                     (*TEST_SCOPE.key, 'Isolated registration test'))
        conn.commit()
    return {'Authorization': 'Bearer dev', 'X-Org-Id': TEST_SCOPE.org_id,
            'X-Project-Id': TEST_SCOPE.project_id}


def test_registration_creates_no_build_or_dataset_history(client, auth_headers):
    source = client.post('/v1/sources', headers=auth_headers,
                         json={'id': 'truth-source', 'type': 'file'})
    assert source.status_code == 200
    response = client.post('/v1/pipelines', headers=auth_headers,
                           json={'id': 'truth-pipeline', 'sourceId': 'truth-source'})
    assert response.status_code == 200
    item = response.json()
    assert item.get('lastBuild') is None
    scope = TEST_SCOPE
    key = wave_ext._resource_key(scope, item['datasetRid'])
    assert wave_ext._datasets[key]['status'] == 'PENDING'
    assert not wave_ext._dataset_history.get(key)
    builds = client.get('/v1/builds', headers=auth_headers).json()['items']
    assert not any(b.get('pipelineId') == item['id'] for b in builds)


def test_registration_preserves_previous_execution(client, auth_headers, monkeypatch):
    scope = TEST_SCOPE
    client.post('/v1/sources', headers=auth_headers,
                json={'id': 'truth-existing-source', 'type': 'file'})
    body = {'id': 'truth-existing-pipeline', 'sourceId': 'truth-existing-source'}
    item = client.post('/v1/pipelines', headers=auth_headers, json=body).json()
    key = wave_ext._resource_key(scope, item['datasetRid'])
    prior = {'id': 'real-run-preserved', 'status': 'FAILED', 'rowsWritten': 0}
    wave_ext._pipelines[body['id']]['lastBuild'] = dict(prior)
    wave_ext._datasets[key]['status'] = 'FAILED'
    history = [{'version': 1, 'buildId': prior['id'], 'status': 'FAILED'}]
    monkeypatch.setitem(wave_ext._dataset_history, key, list(history))
    updated = client.post('/v1/pipelines', headers=auth_headers, json=body)
    assert updated.status_code == 200
    assert updated.json()['lastBuild'] == prior
    assert wave_ext._datasets[key]['status'] == 'FAILED'
    assert wave_ext._dataset_history[key] == history


def test_seed_build_is_not_a_run_but_persisted_run_remains_visible(monkeypatch):
    scope = TEST_SCOPE
    principal = Principal('tester', *scope.key)
    pipelines = {
        'seed': {'id': 'seed', 'orgId': scope.org_id, 'projectId': scope.project_id,
                 'lastBuild': {'id': 'seed-build-seed', 'status': 'SUCCEEDED'}},
        'empty': {'id': 'empty', 'orgId': scope.org_id, 'projectId': scope.project_id},
        'other': {'id': 'other', 'orgId': 'other-org', 'projectId': scope.project_id,
                  'lastBuild': {'id': 'other-run', 'status': 'SUCCEEDED'}},
    }
    monkeypatch.setattr(wave_ext, '_pipelines', pipelines)
    monkeypatch.setattr(wave_ext, '_hydrate_data_os_scope', lambda scope: None)
    monkeypatch.setattr(wave_ext, '_latest_authoritative_pipeline_runs', lambda scope: {})
    assert wave_ext.list_builds(principal)['items'] == []
    monkeypatch.setattr(wave_ext, '_latest_authoritative_pipeline_runs', lambda scope: {
        'seed': {'id': 'persisted-run', 'status': 'FAILED', 'rowsWritten': 0}})
    items = wave_ext.list_builds(principal)['items']
    assert len(items) == 1
    assert items[0]['id'] == 'persisted-run'
    assert items[0]['status'] == 'FAILED'
