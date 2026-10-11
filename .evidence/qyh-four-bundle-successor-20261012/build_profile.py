"""Original full builder profile for the exact unsigned Qiyuehui successor set."""
import importlib.util
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
D=Path(__file__).resolve().parent
OUTPUT=ROOT.parent/'aos-recovery/qyh-four-bundle-build-20261012-r1'
CASES=(('domain.ecommerce.core/1.4.4','domain.ecommerce.core','1.4.4','ecommerce_core'),('platform.ecommerce.niushop/1.23.3','platform.ecommerce.niushop','1.23.3','ecommerce_niushop'),('solution.ecommerce.growth/1.13.1','solution.ecommerce.growth','1.13.1','ecommerce_growth'),('solution.ecommerce.operations-base/1.2.2','solution.ecommerce.operations-base','1.2.2',None))
def load_builder():
    s=importlib.util.spec_from_file_location('qyh_successor_builder',ROOT/'scripts/build_ecommerce_runtime_candidates.py');b=importlib.util.module_from_spec(s);s.loader.exec_module(b)
    b.CANDIDATE_ROOT=D/'source';b.ALL_CASES=CASES;b.RUNTIME_CASES=CASES[:3];b.EXPECTED_RUNTIME_OPERATION_COUNT=15
    frozen=json.loads((D/'source-hashes.json').read_text())
    original=b.preflight
    def preflight():
        assert all(b._tree_hash(D/'source'/k)==v for k,v in frozen.items()), 'frozen source drift'
        return original()
    b.preflight=preflight
    augment=b._augment_sbom
    def augment_sbom(bundle,*,sdk_hash,base_config_digest):
        assert bundle.resolve().is_relative_to(OUTPUT.resolve()), 'only registered new output'
        assert not (bundle/'evidence/sbom.json').exists() and not (bundle/'evidence/bundle-evals.json').exists()
        record=next(i for i in preflight()['bundles'] if i['id']==bundle.parent.name)
        (bundle/'evidence/bundle-evals.json').write_text(json.dumps({'status':'passed','failed':0,'scope':'source-preflight-only','runtimeReadiness':'blocked','sourceTreeHash':record['sourceTreeHash'],'runtimeOperations':record['runtimeOperations'],'schemaCompatibilityHash':record['schemaCompatibilityHash']},sort_keys=True)+'\n')
        (bundle/'evidence/sbom.json').write_text('{"bomFormat":"CycloneDX","specVersion":"1.5","version":1,"components":[]}\n')
        augment(bundle,sdk_hash=sdk_hash,base_config_digest=base_config_digest)
    b._augment_sbom=augment_sbom
    return b
if __name__=='__main__':
    assert not (D/'build-result.json').exists() and not OUTPUT.exists(), 'reconcile unknown build instead of replay'
    b=load_builder();pre=b.preflight();(D/'preflight.json').write_text(json.dumps(pre,indent=2)+'\n')
    result=b.build(context='colima-aos-extension',port=18438,output=OUTPUT,retain_artifacts=True)
    (D/'build-result.json').write_text(json.dumps(result,indent=2)+'\n')
    print('full original builder returned',result['outcome'],'4 bundles,3 runtime images,8 modules; no formal publish/install')
