"""Schedule HTTP owner persistence order; no real main database writes."""
from copy import deepcopy
import pytest
from aos_api.auth import Principal
from aos_api.errors import ApiError
from aos_api.routers import wave_ext as routes
from aos_api import data_os_store

HYDRATE = routes._hydrate_data_os_scope


@pytest.fixture
def owner(monkeypatch):
    principal = Principal('tester', 'org-org', 'dev-project', roles=['data-owner'])
    monkeypatch.setattr(routes, '_schedules', {})
    monkeypatch.setattr(routes, '_data_os_loaded_scopes', {('org-org', 'dev-project')})
    monkeypatch.setattr(routes, '_hydrate_data_os_scope', lambda scope: None)
    return principal


def item():
    return dict(id='s', orgId='org-org', projectId='dev-project', enabled=False,
                cron='0 * * * *', pipelineId='P01-shop-qyh', name='original')


@pytest.mark.parametrize('existing', [False, True])
def test_create_failure_preserves_previous_cache_and_invalidates_load(owner, monkeypatch, existing):
    if existing:
        routes._schedules['s'] = item()
    before = deepcopy(routes._schedules)
    def fail(*args):
        raise RuntimeError('private database detail')
    monkeypatch.setattr(data_os_store, 'persist_schedule', fail)
    with pytest.raises(ApiError) as exc:
        routes.create_schedule(dict(id='s', enabled=False), owner)
    assert exc.value.status_code == 503
    assert exc.value.code == 'SCHEDULE_PERSISTENCE_UNCONFIRMED'
    assert 'private' not in exc.value.message
    assert routes._schedules == before
    assert ('org-org', 'dev-project') not in routes._data_os_loaded_scopes


def test_edit_failure_does_not_mutate_original_object(owner, monkeypatch):
    previous = item(); routes._schedules['s'] = previous
    def fail(*args): raise RuntimeError('unconfirmed')
    monkeypatch.setattr(data_os_store, 'persist_schedule', fail)
    with pytest.raises(ApiError):
        routes.patch_schedule('s', dict(enabled=True, name='changed'), owner)
    assert previous == item() and routes._schedules['s'] == item()
    assert ('org-org', 'dev-project') not in routes._data_os_loaded_scopes


@pytest.mark.parametrize('edit', [False, True])
def test_success_persists_before_publishing_cache(owner, monkeypatch, edit):
    if edit: routes._schedules['s'] = item()
    before = deepcopy(routes._schedules); calls = []
    def save(scope, value):
        assert scope.key == ('org-org', 'dev-project')
        assert routes._schedules == before
        calls.append(deepcopy(value))
    monkeypatch.setattr(data_os_store, 'persist_schedule', save)
    result = (routes.patch_schedule('s', dict(name='changed'), owner) if edit else
              routes.create_schedule(dict(id='s', enabled=False), owner))
    assert calls == [result] and routes._schedules['s'] == result


def test_original_api_error_and_scope_guard_preserved(owner, monkeypatch):
    error = ApiError(code='TENANT_SCOPE_MISMATCH', message='denied', status_code=403)
    def fail(*args): raise error
    monkeypatch.setattr(data_os_store, 'persist_schedule', fail)
    with pytest.raises(ApiError) as exc:
        routes.create_schedule(dict(id='s', enabled=False), owner)
    assert exc.value is error
    routes._schedules['s'] = {**item(), 'orgId': 'dev-org'}
    monkeypatch.setattr(data_os_store, 'persist_schedule', lambda *args: pytest.fail('cross tenant write'))
    with pytest.raises(ApiError):
        routes.create_schedule(dict(id='s', enabled=False), owner)


def test_actual_app_first_schedule_post_route_is_persistent_owner():
    from aos_api.main import app
    def effective(items):
        for route in items:
            children = getattr(route, 'effective_candidates', None)
            if callable(children):
                yield from effective(children())
            else:
                yield route
    matches = [r for r in effective(app.routes) if getattr(r, 'path', None) == '/v1/schedules'
               and 'POST' in getattr(r, 'methods', ())]
    assert matches and matches[0].endpoint is routes.create_schedule


def test_unknown_ack_then_get_reads_original_persistent_result(owner, monkeypatch):
    persisted = {}
    def lost_ack(scope, value):
        persisted[value['id']] = deepcopy(value)
        raise RuntimeError('ack lost after commit')
    monkeypatch.setattr(data_os_store, 'persist_schedule', lost_ack)
    with pytest.raises(ApiError):
        routes.create_schedule(dict(id='s', enabled=False), owner)
    assert routes._schedules == {}
    for name in ('_connectors', '_pipelines', '_syncs', '_datasets', '_dataset_history'):
        monkeypatch.setattr(routes, name, {})
    reads = []
    def load(scope):
        reads.append(scope.key)
        return dict(connectors={}, pipelines={}, syncs={}, datasets={}, dataset_history={}, schedules=persisted)
    monkeypatch.setattr(data_os_store, 'load_all', load)
    monkeypatch.setattr(routes, '_hydrate_data_os_scope', HYDRATE)
    assert routes.get_schedule('s', owner) == persisted['s']
    assert reads == [('org-org', 'dev-project')]
