"""A saved graph remains discoverable after process-local state is lost."""
from aos_api.phase5_pipeline_engine import get_engine
from aos_api.routers import wave_ext
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope('dev-org', 'dev-project')


def test_cold_saved_graph_is_listed_and_detail_recovers_disabled(client, auth_headers):
    pipeline_id = 'discovery-recovery-graph'
    saved = client.put(f'/v1/pipelines/{pipeline_id}/graph', headers=auth_headers, json={
        'name': 'Saved business graph', 'pipeline_type': 'Batch',
        'nodes': [{'id': 'discovery-source', 'name': 'Registered source', 'node_type': 'source',
                   'config': {'source_id': 'configured-only', 'private_note': 'not-for-directory'}}],
        'edges': [],
    })
    assert saved.status_code == 200
    revision = saved.json()['revision']
    get_engine().reset(scope=SCOPE, purge_persisted=False)
    response = client.get('/v1/pipelines', headers=auth_headers)
    assert response.status_code == 200
    matching = [p for p in response.json()['items'] if p['id'] == pipeline_id]
    assert len(matching) == 1
    assert matching[0]['name'] == 'Saved business graph'
    assert matching[0]['execution_mode'] == 'disabled'
    assert matching[0].get('sourceId') is None
    assert 'private_note' not in response.text
    detail = client.get(f'/v1/pipelines/{pipeline_id}', headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()['execution_mode'] == 'disabled'
    assert detail.json()['executor_id'] == ''
    graph = client.get(f'/v1/pipelines/{pipeline_id}/graph', headers=auth_headers)
    assert graph.json()['revision'] == revision
    assert graph.json()['nodes'][0]['config']['source_id'] == 'configured-only'
    warm = client.get('/v1/pipelines', headers=auth_headers).json()['items']
    assert next(p for p in warm if p['id'] == pipeline_id)['sourceId'] == 'configured-only'
    other = {**auth_headers, 'X-Project-Id': 'discovery-other-workspace'}
    other_list = client.get('/v1/pipelines', headers=other)
    assert other_list.status_code == 403
    assert pipeline_id not in other_list.text
    assert client.get(f'/v1/pipelines/{pipeline_id}', headers=other).status_code == 403
    from aos_api.data_os_store import load_phase5_pipeline_graph_catalog
    assert load_phase5_pipeline_graph_catalog(TenantScope(SCOPE.org_id, 'discovery-other-workspace')) == []


def test_saved_graph_does_not_resurrect_retired_catalog_entry(client, auth_headers, monkeypatch):
    pipeline_id = 'discovery-retired-graph'
    saved = client.put(f'/v1/pipelines/{pipeline_id}/graph', headers=auth_headers, json={
        'name': 'Retired graph', 'nodes': [], 'edges': []})
    assert saved.status_code == 200
    assert client.get('/v1/pipelines', headers=auth_headers).status_code == 200
    monkeypatch.setitem(wave_ext._pipelines, pipeline_id, {
        'id': pipeline_id, 'orgId': SCOPE.org_id, 'projectId': SCOPE.project_id,
        'status': 'decommissioned'})
    assert pipeline_id not in client.get('/v1/pipelines', headers=auth_headers).text
    get_engine().reset(scope=SCOPE, purge_persisted=False)
    assert pipeline_id not in client.get('/v1/pipelines', headers=auth_headers).text
