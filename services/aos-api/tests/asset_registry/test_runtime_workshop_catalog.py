from types import SimpleNamespace
import pytest
from .test_ecommerce_workshop_catalog import (
    _loaded_growth, _persisted, _active, _active_row, _ReadOnlyConnection, _QueryResult,
    REPOSITORY_ROOT, INSTALLATION_ID,
)
from aos_api.asset_registry.workshop_catalog_source import PostgresWorkshopCatalogSource


@pytest.mark.parametrize('legacy_flag', [False,True,None])
def test_runtime_candidates_do_not_reopen_legacy_catalog(monkeypatch, legacy_flag):
    persisted = _persisted(_loaded_growth())
    active = _active(persisted)
    row = _active_row(active.lock, installation_id=INSTALLATION_ID, overlay_revision=active.overlay_revision)
    row['legacy_eligible'] = legacy_flag
    class Connection(_ReadOnlyConnection):
        def execute(self, statement, params=None):
            if 'FROM bundle_installation i' in statement:
                return _QueryResult(many=[row])
            return super().execute(statement,params)
    monkeypatch.setattr('aos_api.asset_registry.workshop_catalog_source._load_registry_version', lambda *a,**kw:persisted)
    source = PostgresWorkshopCatalogSource(connect_factory=Connection)
    arguments = dict(org_id='org-org',project_id='dev-project',markings=['public'])
    legacy = source.read_active_bundles(**arguments)
    runtime = source.read_runtime_candidate_bundles(**arguments)
    assert len(legacy) == (1 if legacy_flag is True else 0)
    assert len(runtime) == (1 if legacy_flag is False else 0)


@pytest.mark.parametrize('state', ['ready','no-ui','disabled','old-revision','wrong-route','fenced','binding-disabled','no-role','no-marking'])
def test_runtime_catalog_requires_current_ready_signed_route(state):
    from aos_api.ecommerce_runtime_workshop_catalog import RuntimeWorkshopCatalog
    from aos_api.extension_runtime.runtime_view import RuntimeUiSessionView
    persisted = _persisted(_loaded_growth())
    from aos_api.asset_registry.manifest_loader import ManifestLoader
    source = SimpleNamespace(read_runtime_candidate_bundles=lambda **kw:(_active(persisted),))
    calls=[]
    class Reader:
        def get_installation(self, **kwargs):
            calls.append(kwargs)
            route=kwargs['requested_route']
            ui=RuntimeUiSessionView(title='fixture',signedResourceUrl='https://ui.example.test/frontend/index.html',
                resourceHash='sha256:'+'a'*64, initialRoute=route,routeClaims=('/other',) if state=='wrong-route' else (route,),
                readOperationClaims=(),commandOperationClaims=())
            return SimpleNamespace(installationId=INSTALLATION_ID,installationRevision=4 if state=='old-revision' else 5,
                effectiveState='disabled' if state=='disabled' else 'ready',
                binding=SimpleNamespace(generation='33333333-3333-4333-8333-333333333333',executionEpoch=3,revision=4,
                    enabled=state!='binding-disabled',operationFence=state=='fenced',installationRevision=5),
                ui=None if state=='no-ui' else ui)
    result=RuntimeWorkshopCatalog(source=source,loader=ManifestLoader({'catalog':REPOSITORY_ROOT/'bundles'}),view_reader=Reader()).list_modules(
        org_id='org-org',project_id='dev-project',roles=[] if state=='no-role' else ['operator'],markings=[] if state=='no-marking' else ['public'])
    expected = 7 if state == 'ready' else 0
    if state in {'no-role', 'no-marking'}:
        expected = sum(not (m.permissions.roles if state == 'no-role' else m.permissions.markings)
                       for m in _loaded_growth().workshop_modules)
    assert result.count == expected
    if state == 'no-role':
        assert all(not item.module.permissions.roles for item in result.items)
    if state == 'no-marking':
        assert all(not item.module.permissions.markings for item in result.items)
    assert all(call['org_id']=='org-org' and call['installation_id']==INSTALLATION_ID for call in calls)
