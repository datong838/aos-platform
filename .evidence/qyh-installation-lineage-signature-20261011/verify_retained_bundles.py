import hashlib,json
from pathlib import Path
from aos_api.asset_registry.manifest_loader import ManifestLoader
from aos_api.asset_registry.signature import FileTrustRootProvider
R=Path(__file__).resolve().parent
BASE=Path('/Users/ddt/work/projects/ai_agent/.aos-recovery-20260920/state/q-advisor-baseline')
root=BASE/'bn-canonical-alias-registry/signed-bundles'
trust=BASE/'bm-trust-root-rotation/signing/trust-roots.json'
loader=ManifestLoader({'a0v-canonical':root},trust_roots=FileTrustRootProvider(trust))
result=[]
for entry in json.loads((R/'candidate-artifacts.json').read_text()):
 source=entry['sources'][0];version=entry['version'];bundle=entry['bundle']
 record={'source':source,'root':str(root),'directoryPresent':(root/bundle/version).is_dir()}
 try:
  loaded=loader.load(source)
  expected=[{'relativePath':a['relative_path'],'artifactRef':a['artifact_ref'],'digest':a['digest'],'size':a['size']} for a in entry['artifacts']]
  actual=[{'relativePath':a.relative_path,'artifactRef':a.artifact_ref,'digest':a.digest,'size':a.size} for a in loaded.artifacts]
  signatures=[e.model_dump(mode='json',by_alias=True) for e in loaded.evidence if str(e.type)=='signature_verification']
  record.update({'loaded':True,'artifactIndexExact':actual==expected,'contentHash':loaded.content_hash,'signatureEvidence':signatures,'moduleIds':[m.module_id for m in loaded.workshop_modules]})
 except Exception as e:
  record.update({'loaded':False,'errorType':type(e).__name__,'error':str(e)})
 result.append(record)
(R/'retained-bundle-readback.json').write_text(json.dumps({'trustRootSha256':hashlib.sha256(trust.read_bytes()).hexdigest(),'items':result},ensure_ascii=False,indent=2))
print(json.dumps(result,ensure_ascii=False))
