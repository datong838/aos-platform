"""Original limited-login read-only verification; no Registry transition."""
from contextlib import contextmanager
from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'services/aos-api')]
import psycopg
from psycopg.rows import dict_row
import a0v_qyh_restored_http as gate
from aos_api.asset_registry.registry_store import PostgresRegistryStore
from aos_api.asset_registry.registry_service import RegistryService
from aos_api.asset_registry.manifest_loader import ManifestLoader
from aos_api.asset_registry.signature import FileTrustRootProvider
from aos_api.asset_registry.errors import AssetRegistryError
from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope


def main():
    output=Path(__file__).parent/'live-readback.json';assert not output.exists(),'Existing result: reconcile only'
    root=ROOT/'.evidence/qyh-full-system-restoration-20261011';identity=root/'private/restored-identity.json';gate.preflight(identity);parameters=gate._identity_parameters(identity)
    @contextmanager
    def factory():
        with psycopg.connect(host=parameters['host'],port=parameters['port'],dbname=parameters['dbname'],user=parameters['user'],passfile=parameters['pgpassFile'],row_factory=dict_row) as conn:
            conn.read_only=True;conn.execute('SET LOCAL ROLE aos_runtime')
            apply_asset_transaction_scope(conn,org_id='org-org',project_id='dev-project')
            yield conn
    trust=FileTrustRootProvider((root/'restoration-public-trust-roots.json').resolve()).snapshot()
    loader=ManifestLoader({'qyh-current':(root/'selected-public-bundles').resolve()},trust_roots=trust)
    service=RegistryService(store=PostgresRegistryStore(factory),loader=loader,trust_roots=trust)
    rows=[]
    for bundle,version in [('platform.ecommerce.niushop','1.23.2'),('solution.ecommerce.operations-base','1.2.2'),('domain.ecommerce.core','1.4.3'),('solution.ecommerce.growth','1.13.0')]:
        try:
            material=service.get_published_reference_material(bundle_id=bundle,version=version,publisher='aos')
            assert material['publicationSequence']==2 and material['tenantInstallationVerified'] is False
            rows.append({'bundleId':bundle,'version':version,'status':'VERIFIED_PUBLISHED_MATERIAL','material':material})
        except AssetRegistryError as error:
            assert bundle in ('domain.ecommerce.core','solution.ecommerce.growth')
            rows.append({'bundleId':bundle,'version':version,'status':'REFUSED_NOT_PUBLISHED','errorType':type(error).__name__})
    assert sum(x['status']=='VERIFIED_PUBLISHED_MATERIAL' for x in rows)==2
    with output.open('x') as stream:json.dump({'rows':rows,'limitedLoginReadOnly':True,'databaseWrites':0,'registryTransitions':0,'newRefGenerated':False,'wholeMediaSourceAccepted':False},stream,indent=2)
    print(json.dumps({'publishedMaterialPositive':2,'nonPublishedRejected':2,'writes':0}))

if __name__=='__main__':main()
