"""Prepare an immutable unsigned successor set, retaining all original sources."""
import importlib.util
import json
import shutil
import sys
from pathlib import Path
from datetime import UTC,datetime
ROOT=Path(__file__).resolve().parents[2]
D=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'services/aos-api')]
from build_ecommerce_runtime_candidates import _tree_hash,_release_record
from aos_api.asset_registry.manifest_loader import ManifestLoader
from aos_api.asset_registry.signature import FileTrustRootProvider
from aos_api.asset_registry.release_policy import ReleasePolicy
PUBLIC=ROOT/'.evidence/qyh-full-system-restoration-20261011/selected-public-bundles'
TRUST=ROOT/'.evidence/qyh-full-system-restoration-20261011/restoration-public-trust-roots.json'
CASES=[('domain.ecommerce.core','1.4.3','1.4.4'),('platform.ecommerce.niushop','1.23.2','1.23.3'),('solution.ecommerce.growth','1.13.0','1.13.1'),('solution.ecommerce.operations-base','1.2.2','1.2.2')]
if __name__=='__main__':
    assert not (D/'source').exists() and not (D/'inputs.json').exists(), 'reconcile existing preparation first'
    trust=FileTrustRootProvider(TRUST).snapshot();loader=ManifestLoader({'current':PUBLIC},trust_roots=trust);policy=ReleasePolicy(trust_roots=trust)
    terminal=json.loads((PUBLIC.parent/'selected-public-root-terminal.json').read_text());old={i['id']:i for i in terminal['versions']}
    inputs=[]
    for bid,version,new in CASES:
        loaded=loader.load(f'bundle://current/{bid}/{version}')
        assert loaded.content_hash==old[bid]['contentHash']
        policy.evaluate(_release_record(loaded),checked_at=datetime.now(UTC))
        path=PUBLIC/bid/version;inputs.append({'id':bid,'baseVersion':version,'version':new,'baseHash':_tree_hash(path)})
    growth=ROOT/'.evidence/qyh-growth-source-candidate-20261012/candidate/solution.ecommerce.growth/1.13.1'
    expected='sha256:'+json.loads((growth.parents[2]/'preparation.json').read_text())['treeHash'];assert _tree_hash(growth)==expected
    (D/'inputs.json').write_text(json.dumps({'bases':inputs,'growthSourceHash':expected,'head':'5d57578fa090a917a923fe22e0cbacc0253afcb2'},indent=2)+'\n')
    for item in inputs:
        bid=item['id'];target=D/'source'/bid/item['version'];source=growth if bid=='solution.ecommerce.growth' else PUBLIC/bid/item['baseVersion']
        shutil.copytree(source,target,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        if item['baseVersion']!=item['version'] and bid!='solution.ecommerce.growth':
            p=target/'bundle.yaml';s=p.read_text();oldmarker=f"  version: {item['baseVersion']}\n";assert s.count(oldmarker)==1;p.write_text(s.replace(oldmarker,f"  version: {item['version']}\n",1))
        if bid!='solution.ecommerce.operations-base':
            for rel in ('bundle.signature.json','evidence/bundle-evals.json','evidence/sbom.json','artifacts/runtime-image-index.json','artifacts/python-dependencies.lock'):
                (target/rel).unlink(missing_ok=True)
            (target/'evidence').mkdir(exist_ok=True)
            (target/'evidence/content-source-provenance.json').write_text(json.dumps({'status':'UNBUILT_UNSIGNED','baseVersion':item['baseVersion'],'baseTreeHash':item['baseHash'],'sourcePurpose':'电商域/栖月汇/八工作台','runtimeReadiness':'blocked','formalPublishingAuthority':False},ensure_ascii=False,sort_keys=True)+'\n')
    assert all(_tree_hash(PUBLIC/i['id']/i['baseVersion'])==i['baseHash'] for i in inputs)
    assert _tree_hash(growth)==expected
    print('original4 signatures/current byte identities verified; independent successors prepared; no publishing')
