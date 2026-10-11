"""Read actual signed current packages and Registry, without any publication."""
import hashlib
import json
import sys
from pathlib import Path
from contextlib import contextmanager
from datetime import UTC, datetime
import yaml
from pydantic import ValidationError
import real_contract as C
sys.path.insert(0,str(C.ROOT / '.evidence/qyh-full-system-restoration-20261011'))
import release_transition as T
from prepare_public_bundle_root import OUTPUT, fingerprints
from aos_api.aip_production_contracts import RegisterMediaGateProfileRequest

out = C.R / 'signed-media-source-result.json'
assert not out.exists(), 'Existing result: reconcile only'
before = fingerprints(OUTPUT)
trust = T.FileTrustRootProvider(T.TRUST).snapshot()
loader = T.ManifestLoader({'qyh-selected':OUTPUT}, trust_roots=trust)
opened = []
@contextmanager
def readonly():
    with T.factory() as conn:
        conn.read_only = True
        row = conn.execute('SELECT current_user AS role,current_database() AS db,current_setting(\'transaction_read_only\') AS readonly').fetchone()
        assert row['role']=='aos_runtime' and row['db']=='aos_meta_head' and row['readonly']=='on'
        opened.append(row)
        yield conn
registry = T.PostgresRegistryStore(connect_factory=readonly)
versions, documents = [], []
for _, bid, version, _ in T.CASES:
    bundle = loader.load(f'bundle://qyh-selected/{bid}/{version}')
    assert bundle.signature is not None
    stored = registry.get_version(bid,version,publisher='aos')
    assert stored['contentHash']==bundle.content_hash
    assert stored['signature']==bundle.signature.model_dump(mode='json',by_alias=True)
    versions.append({'id':bid,'version':version,'contentHash':bundle.content_hash,
        'registryStatus':stored['status'],'signatureVerifiedByOriginalLoader':True,
        'registrySignatureExact':True,'modules':len(bundle.workshop_modules),
        'artifactCount':len(bundle.artifacts)})
    for artifact in bundle.artifacts:
        p=OUTPUT/bid/version/artifact.relative_path
        if p.suffix.lower() not in {'.json','.yaml','.yml'}:
            continue
        raw=p.read_bytes()
        body=json.loads(raw) if p.suffix.lower()=='.json' else yaml.safe_load(raw)
        if not isinstance(body,dict):
            continue
        accepted=False
        try:
            RegisterMediaGateProfileRequest.model_validate(body)
            accepted=True
        except ValidationError:
            pass
        documents.append({'bundleId':bid,'version':version,'path':artifact.relative_path,
            'sha256':hashlib.sha256(raw).hexdigest(),
            'declaredSchema':body.get('schema',body.get('schemaVersion')),
            'hasGateField':'gates' in body,
            'hasSourceSignaturePolicyTriple':all(k in body for k in ('sourceBundleRef','signatureRef','policyRef')),
            'completeMediaGateRequestDocument':accepted})
assert fingerprints(OUTPUT)==before
growth=[x for x in documents if x['bundleId']=='solution.ecommerce.growth']
templates=[x for x in growth if x['path'].startswith('content/media-production-templates/')]
assert len(templates)==6
assert sum(x['modules'] for x in versions)==8
result={'head':__import__('subprocess').check_output(['git','rev-parse','HEAD'],cwd=C.ROOT,text=True).strip(),
    'authority':'AOS-001895','task':'qyh-source-boundary-rehearsal-20261011',
    'observedAt':datetime.now(UTC).isoformat(),'versions':versions,
    'signedDocuments':documents,'completeMediaGateRequestDocuments':sum(x['completeMediaGateRequestDocument'] for x in documents),
    'sixSignedMediaProductionTemplatesRetained':True,'eightSignedModuleDefinitionsRetained':True,
    'fourSelectedPackagesFilesUnchanged':True,'filesCount':len(before),
    'filesHash':hashlib.sha256(json.dumps(before,sort_keys=True).encode()).hexdigest(),
    'databaseConnections':opened,'databaseWrites':0,'objectWrites':0,'signatureOrPublisherCreated':False,
    'localSignatureCheckDoesNotProveCurrentPublishedAdmission':True,
    'remoteOrAllMachineProducerAbsenceNotProven':True,'formalLoginConnected':False,
    'formalPublisherConnected':False,'fullRestorationAccepted':False,
    'scriptHash':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
with out.open('x') as stream:
    stream.write(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'signedModules':8,'retainedMediaTemplates':6,
    'completeMediaGateRequestDocuments':result['completeMediaGateRequestDocuments'],
    'registryStatuses':{x['id']:x['registryStatus'] for x in versions},'databaseWrites':0}))
