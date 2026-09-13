from types import SimpleNamespace
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from test_configuration_store_pg import configuration_case,database,pytestmark
from test_runtime_installations_api import _app,_view,_control_plane,INSTALLATION_ID
from aos_api.extension_runtime.configuration_store import append_configuration
from aos_api.extension_runtime.configuration_catalog import read_catalog,ConfigurationCatalog
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict


def snapshot(args,ref=None):
    return SimpleNamespace(installationId=str(args['installation_id']),installationRevision=1,installationEtag=1,
        binding=SimpleNamespace(generation=args['generation'],revision=1,configRef=ref.model_dump(mode='json') if ref else None))


def test_real_registered_choice_has_only_ref_not_policy_body(configuration_case):
    conn,args=configuration_case
    with conn.transaction():ref=append_configuration(conn,**args)
    result=read_catalog(conn,org_id=args['org_id'],project_id=args['project_id'],view=snapshot(args,ref))
    assert len(result.items)==1 and result.items[0].isCurrent and result.items[0].ref==ref
    assert result.hasMore is False
    raw=result.model_dump_json()
    assert 'test.configuration' not in raw and 'roleRefs' not in raw and 'test-actor' not in raw


@pytest.mark.parametrize('drift',['tenant','project','generation','revision','etag','installation'])
def test_configuration_catalog_rejects_target_drift(configuration_case,drift):
    conn,args=configuration_case;view=snapshot(args)
    if drift=='generation':view.binding.generation=str(uuid4())
    if drift=='revision':view.binding.revision=2
    if drift=='etag':view.installationEtag=2
    if drift=='installation':view.installationId=str(uuid4())
    with pytest.raises(RuntimeConflict):read_catalog(conn,org_id='canary' if drift=='tenant' else args['org_id'],
        project_id='other' if drift=='project' else args['project_id'],view=view)


def test_real_catalog_reports_truncation(configuration_case):
    conn,args=configuration_case
    for index in range(51):
        with conn.transaction():append_configuration(conn,**{**args,'idempotency_key':f'choice-{index}'})
    result=read_catalog(conn,org_id=args['org_id'],project_id=args['project_id'],view=snapshot(args))
    assert len(result.items)==50 and result.hasMore is True
    assert [x.ref.configurationId for x in result.items]==sorted(x.ref.configurationId for x in result.items)


def test_catalog_hash_mismatch_is_not_returned(configuration_case):
    conn,args=configuration_case
    with conn.transaction():append_configuration(conn,**args)
    class CorruptRead:
        def execute(self,query,params):
            result=conn.execute(query,params)
            if 'FROM extension_runtime_configuration' in query:
                rows=result.fetchall();first=list(rows[0]);first[3]='sha256:'+'f'*64
                return SimpleNamespace(fetchall=lambda:[tuple(first)])
            return result
    with pytest.raises(RuntimeConflict,match='hash'):read_catalog(CorruptRead(),org_id=args['org_id'],project_id=args['project_id'],view=snapshot(args))


@pytest.mark.parametrize('error,status',[(None,200),(PermissionError('private'),403),(RuntimeConflict('private'),409),(RuntimeError('private'),503)])
def test_http_catalog_uses_principal_and_no_store(error,status):
    plane=_control_plane();calls=[]
    def list_configurations(**kwargs):
        calls.append(kwargs)
        if error:raise error
        return ConfigurationCatalog(installationId=INSTALLATION_ID,installationRevision=1,installationEtag=1,generation=None,bindingRevision=None,items=(),hasMore=False)
    plane.view_reader.list_configurations=list_configurations
    response=TestClient(_app(plane)).get(f'/v1/bundle-runtime-installations/{INSTALLATION_ID}/configurations')
    assert response.status_code==status and response.headers['cache-control']=='no-store'
    assert 'private' not in response.text
    assert calls==[dict(installation_id=INSTALLATION_ID,org_id='org-org',project_id='dev-project',roles=['admin'],markings=['public'])]


def test_catalog_requires_maintenance_role_before_reading_any_installation():
    from aos_api.extension_runtime.runtime_view import RuntimeViewReader
    from aos_api.asset_registry.errors import AssetRegistryError
    reader=RuntimeViewReader(installation_reader=SimpleNamespace(get=lambda **kw:pytest.fail('unauthorized installation read')),
        connect_factory=lambda:pytest.fail('unauthorized database connection'))
    with pytest.raises(AssetRegistryError):reader.list_configurations(installation_id=INSTALLATION_ID,
        org_id='org-org',project_id='dev-project',roles=['viewer'],markings=[])
