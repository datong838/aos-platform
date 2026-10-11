"""Actual original builder paths; scoped image probes, no runtime authority."""
import importlib.util
import json
from hashlib import sha256
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
D=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('actual_builder',ROOT/'scripts/build_ecommerce_runtime_candidates.py')
b=importlib.util.module_from_spec(s);s.loader.exec_module(b)
assert not (D/'actual-images.json').exists(), 'reconcile existing outcomes first'
engine=b._require_isolated_engine('colima-aos-extension')
work=D/'actual-build';work.mkdir()
cases=[('ecommerce_growth',ROOT/'.evidence/qyh-growth-source-candidate-20261012/candidate/solution.ecommerce.growth/1.13.1'),('ecommerce_niushop',ROOT/'bundles/candidates/ecommerce/platform.ecommerce.niushop/1.23.0')]
results=[]
for package,source in cases:
    before=b._tree_hash(source)
    image,archive=b._build_image(context='colima-aos-extension',bundle=source,package=package,work=work)
    probe=json.loads((work/f'{package}-import-probe.json').read_text());assert probe['passed'] and probe['exitCode']==0
    assert b._tree_hash(source)==before
    results.append({'package':package,'sourceHash':before,'imageId':image,'archiveHash':sha256(archive.read_bytes()).hexdigest(),'dependencyLockHash':b._sha256(b._dependency_lock(source)),'probe':probe})
    (D/'actual-images-progress.json').write_text(json.dumps(results,indent=2)+'\n')
retained=json.loads((ROOT/'.evidence/qyh-analyst-eval-policy-contract-20261012/retained-package-hashes.json').read_text())
assert all(sha256((ROOT/name).read_bytes()).hexdigest()==digest for name,digest in retained.items())
(D/'actual-images.json').write_text(json.dumps({'engine':engine,'images':results,'retainedFilesUnchanged':len(retained),'formalRuntimeReady':False},indent=2)+'\n')
print('actual original builder Growth and Niushop offline images, immutable zero-network import probes PASS; retained1695 exact')
