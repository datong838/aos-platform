from dataclasses import replace
from types import SimpleNamespace

import pytest

from test_production_runtime import _connector,_dependencies,_patch_identities
from aos_api.asset_registry.workshop_catalog_source import PostgresWorkshopCatalogSource
from aos_api.ecommerce_runtime_workshop_catalog import RuntimeWorkshopCatalog
from aos_api.extension_runtime.production_runtime import select_production_runtime_host
from aos_api.extension_runtime.ui_read_consumer import RuntimeUiReadConsumer


def catalog(dependencies):
    return RuntimeWorkshopCatalog(source=PostgresWorkshopCatalogSource(),loader=dependencies.preparation.loader,
                                   view_reader=SimpleNamespace(get_installation=lambda **_:None))


@pytest.mark.parametrize('ready',[True,False])
def test_explicit_ui_selection_preflights_and_shares_original_dependencies(monkeypatch,ready):
    _patch_identities(monkeypatch)
    calls=[];runtime=_connector('runtime',calls);base=_dependencies(runtime)
    dependencies=replace(base,ui_read_catalog=catalog(base),ui_read_markings=('public',))
    seen=[]
    def preflight(conn):seen.append(conn.name);return ready
    monkeypatch.setattr('aos_api.extension_runtime.production_runtime.runtime_ui_read_ready',preflight)
    rows=({'org_id':'org-org','project_id':'dev-project','assignment_revision':1},)
    selected=select_production_runtime_host(enabled=True,directory_connect=_connector('directory',calls,rows),
        runtime_connect=runtime,web_connect=_connector('web',calls),dependencies=dependencies)
    assert seen==['runtime']
    if not ready:
        assert selected.status=='INACTIVE' and selected.error_code=='UI_READ_PREFLIGHT_FAILED'
        assert 'web' not in calls
    else:
        assignment=selected.host._current_assignments()[0]
        reader=assignment.consumers[-1]
        assert type(reader) is RuntimeUiReadConsumer and reader.scope==assignment.scope
        assert reader.store is dependencies.installation_store
        assert reader.directory is dependencies.preparation.live_directory
        assert reader.connect is runtime and reader.markings==('public',)


def test_read_dependency_loader_and_markings_cannot_drift():
    base=_dependencies(_connector('runtime',[]))
    other=_dependencies(_connector('other',[]))
    with pytest.raises(TypeError,match='loader'):replace(base,ui_read_catalog=catalog(other))
    with pytest.raises(ValueError,match='markings'):replace(base,ui_read_catalog=catalog(base),ui_read_markings=('public','public'))
    with pytest.raises(ValueError,match='markings'):replace(base,ui_read_markings=('public',))


@pytest.mark.parametrize('mode',['enabled','disabled','bad-json','bad-shape','missing-view'])
def test_environment_wiring_is_explicit_and_closed_on_invalid_configuration(monkeypatch,mode):
    from aos_api.asset_registry.control_wiring import RuntimeControlPlane,build_production_runtime_host_selection
    from aos_api.extension_runtime.production_runtime import RuntimeHostSelection
    monkeypatch.setenv('AOS_EXTENSION_RUNTIME_HOST_ENABLED','1')
    monkeypatch.setenv('AOS_EXTENSION_RUNTIME_DATABASE_URL','fixture-runtime')
    monkeypatch.setenv('AOS_EXTENSION_DIRECTORY_DATABASE_URL','fixture-directory')
    monkeypatch.delenv('AOS_EXTENSION_RUNTIME_CREDENTIAL_FILE',raising=False)
    monkeypatch.setenv('AOS_EXTENSION_OCI_CONTEXT','colima-aos-extension')
    monkeypatch.setenv('AOS_EXTENSION_RUNTIME_PLATFORM','linux/arm64')
    monkeypatch.setenv('AOS_EXTENSION_RUNTIME_UI_READ_ENABLED','0' if mode=='disabled' else '1')
    monkeypatch.setenv('AOS_EXTENSION_UI_READ_MARKINGS_JSON','invalid' if mode=='bad-json' else ('{}' if mode=='bad-shape' else '["public"]'))
    base=_dependencies(_connector('unused',[]));captured={}
    def select(**kwargs):
        captured.update(kwargs);return RuntimeHostSelection(None,'INACTIVE','TEST_CAPTURE')
    monkeypatch.setattr('aos_api.extension_runtime.production_runtime.select_production_runtime_host',select)
    plane=RuntimeControlPlane(base.installation_store,None,None,None,None,base.configuration_authorize,
        view_reader=None if mode=='missing-view' else SimpleNamespace(get_installation=lambda **_:None),
        disable_dependent=base.disable_dependent,live_job_directory=base.preparation.live_directory)
    build_production_runtime_host_selection(control_plane=plane)
    dependencies=captured['dependencies']
    if mode in {'bad-json','bad-shape','missing-view'}:assert dependencies is None
    elif mode=='disabled':assert dependencies.ui_read_catalog is None and dependencies.ui_read_markings==()
    else:
        assert dependencies.ui_read_catalog._loader is dependencies.preparation.loader
        assert dependencies.ui_read_markings==('public',)
        assert dependencies.preparation.live_directory is plane.live_job_directory
