import importlib.util,json,sys,hashlib,subprocess
from pathlib import Path
from datetime import datetime,timezone
from aos_api.asset_registry.manifest_loader import ManifestLoader
from aos_api.asset_registry.signature import FileTrustRootProvider
from aos_api.asset_registry.release_policy import ReleasePolicy
R=Path(__file__).resolve().parent;REPO=R.parents[1];BASE=REPO.parent/'aos-recovery'
s=importlib.util.spec_from_file_location('signer',REPO/'scripts/sign_ecommerce_growth_1_13_candidates.py');signer=importlib.util.module_from_spec(s);s.loader.exec_module(signer)
signer.validate_qualification(build=BASE/'.aos-growth-113-build-20261002-r2',build_receipt=BASE/'.aos-growth-113-build-receipt-20261002-r2.json',qualification_receipt=BASE/'.aos-growth-113-qualification-receipt-20261002-r2.json')
receipt=BASE/'.aos-growth-113-signing-receipt-20261002-r1.json';data=json.loads(receipt.read_text());root=Path(data['signedTree']);trust=root.parent/'trust-roots.json'
assert data['outcome']=='SIGNED_TREE_GREEN'
base_signer=signer.load_signer();builder=base_signer._builder()
assert builder._tree_hash(root)==data['signedTreeHash']
assert builder._tree_hash(BASE/'.aos-growth-113-build-20261002-r2')==data['buildTreeHash']
provider=FileTrustRootProvider(trust).snapshot();loader=ManifestLoader({'a0v-current':root},trust_roots=provider);policy=ReleasePolicy(trust_roots=provider)
items=[]
for bundle,version in signer.VERSIONS.items():
 loaded=loader.load('bundle://a0v-current/'+bundle+'/'+version)
 assert loaded.content_hash==data['contentHashes'][bundle]
 policy.evaluate(builder._release_record(loaded),checked_at=datetime.now(timezone.utc))
 sig=[e for e in loaded.evidence if str(e.type)=='signature_verification'];assert len(sig)==1 and str(sig[0].status)=='valid'
 entry={'bundle':bundle,'version':version,'contentHash':loaded.content_hash,'signatureValid':True,'releasePolicyPassed':True,'moduleIds':[m.module_id for m in loaded.workshop_modules]}
 for relative in ['artifacts/schema-requirements.json','artifacts/schema-compatibility.json','artifacts/runtime-image-index.json']:
  p=root/bundle/version/relative
  if p.is_file():
   raw=p.read_bytes();a=[a for a in loaded.artifacts if a.relative_path==relative];assert len(a)==1 and a[0].digest=='sha256:'+hashlib.sha256(raw).hexdigest() and a[0].size==len(raw)
   entry[relative]=json.loads(raw)
 items.append(entry)
(R/'signed-readback.json').write_text(json.dumps({'observedAt':datetime.now(timezone.utc).isoformat(),'qualificationInputsPassed':True,'signingReceiptSha256':hashlib.sha256(receipt.read_bytes()).hexdigest(),'trustRootsSha256':hashlib.sha256(trust.read_bytes()).hexdigest(),'items':items,'runtimeStart':False},ensure_ascii=False,indent=2))
print(json.dumps({'bundlesVerified':len(items),'moduleCount':sum(len(x['moduleIds']) for x in items),'effects':0}))
