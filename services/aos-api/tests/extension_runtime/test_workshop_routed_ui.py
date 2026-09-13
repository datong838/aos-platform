import json
from contextlib import nullcontext
from types import SimpleNamespace
import pytest
from test_ui_resources import _Connection, _Result, _Policy, _installation, HASH_A, HASH_B, HASH_C, HASH_D, INSTALLATION_ID
from aos_api.extension_runtime import ui_resources


@pytest.mark.parametrize('case', ['growth', 'operations', 'no-route', 'missing', 'foreign-claim', 'wildcard', 'duplicate-owner', 'duplicate-without-frontend', 'unsafe', 'resource-drift'])
def test_routed_session_preserves_signed_bundle_route_ownership(monkeypatch, case):
    routes = {'growth':['/workshop/analyst','/workshop/content-campaign'], 'operations':['/workshop/operations']}
    if case in {'duplicate-owner','duplicate-without-frontend'}: routes['operations'].append('/workshop/analyst')
    records, selected, manifests = {}, [], {}
    for name, own_routes in routes.items():
        frontend = SimpleNamespace(manifest='frontend/manifest.json', artifact_hash=HASH_A)
        if name == 'operations' and case == 'duplicate-without-frontend': frontend=None
        manifest = SimpleNamespace(spec=SimpleNamespace(runtime=SimpleNamespace(frontend=frontend),
            contributions=[SimpleNamespace(kind='navigation',route=route) for route in own_routes]))
        records[name] = SimpleNamespace(content_hash=HASH_C,manifest=manifest,
            evidence=[SimpleNamespace(type=SimpleNamespace(value='content_hash'),artifact_ref=f'bundle://catalog/{name}/bundle.yaml')])
        selected.append(SimpleNamespace(publisher='aos',id=name,version='1.0.0',content_hash=HASH_C,
            signature_fingerprint=HASH_D,release_evidence_revision=HASH_A))
        claims = list(own_routes)
        if name == 'growth' and case == 'foreign-claim': claims.append('/workshop/operations')
        if name == 'growth' and case == 'wildcard': claims.append('/workshop/*')
        manifests[name] = dict(schemaVersion='aos.dev/frontend-runtime/v1alpha1',title=name,
            entrypoint='frontend/index.html',initialRoute=own_routes[0],routeClaims=claims,
            readOperationClaims=[],commandOperationClaims=[])
    class Connection(_Connection):
        def execute(self, statement, *args):
            if 'FROM asset_bundle_version' in statement:
                return _Result(many=[dict(publisher='aos',bundle_id=name,version='1.0.0') for name in routes])
            return super().execute(statement,*args)
    class Loader:
        def __init__(self): self.reads=[]
        def load(self, source):
            name = source.rsplit('/',1)[-1]
            return SimpleNamespace(content_hash=HASH_D if case=='resource-drift' else HASH_C,
                manifest=records[name].manifest,artifacts=[
                    SimpleNamespace(relative_path='frontend/manifest.json',digest=HASH_A),
                    SimpleNamespace(relative_path='frontend/index.html',digest=HASH_B)])
        def read_verified_artifact(self, source, path, **kwargs):
            self.reads.append(source)
            return json.dumps(manifests[source.rsplit('/',1)[-1]]).encode()
    loader=Loader()
    monkeypatch.setattr(ui_resources,'load_stored_lock',lambda *a,**kw:(None,SimpleNamespace(payload=SimpleNamespace(resolved=selected))))
    monkeypatch.setattr(ui_resources,'_record_from_row',lambda row:records[row['bundle_id']])
    resolver=ui_resources.ProductionUiSessionResolver(connect_factory=lambda:nullcontext(Connection()),
        release_policy=_Policy(),loader=loader,resource_origin='http://127.0.0.1:18182/extensions')
    requested = '/workshop/operations' if case=='operations' else '/workshop/analyst'
    if case=='missing': requested='/workshop/missing'
    if case=='unsafe': requested='/workshop/%2e%2e/admin'
    if case=='no-route': requested=None
    result=resolver(installation=_installation(),org_id='org-org',project_id='dev-project',
        installation_id=INSTALLATION_ID,installation_revision=5,generation='generation',execution_epoch=3,
        roles=['admin'],markings=['public'],requested_route=requested)
    if case in {'growth','operations'}:
        assert result is not None and result.initialRoute==requested
        assert f'/aos/{case}/1.0.0/' in result.signedResourceUrl
        assert set(result.routeClaims)==set(routes[case])
        assert loader.reads==[f'bundle://catalog/{case}']
    else:
        assert result is None
