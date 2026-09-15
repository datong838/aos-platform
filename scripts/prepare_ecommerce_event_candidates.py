"""Freeze complete event runtime dependencies without changing signed history."""
import hashlib
import json
import shutil
from pathlib import Path
from prepare_ecommerce_growth_1_5_candidate import tree_hash
ROOT=Path(__file__).resolve().parents[1]
CANDIDATES=ROOT/'bundles/candidates/ecommerce'
AUTHOR=ROOT/'bundles/domains/ecommerce-core'
BASE_HASHES={'domain.ecommerce.core/1.3.0': '3ea7e6a6d5707644b8e51b668c849efb7569562760cf31805c07383e790c3db6', 'solution.ecommerce.growth/1.9.0': '6c27c24ae96bc2cb013526e2f431d3ee2d2fdb6925e0b3729f6a6e12c3c4472f'}
SOURCES={'backend/ecommerce_core/__init__.py': 'f888f9972388ac7c3e14fb40a1dfea6f7a6cd1dfbd9d31dc63bf9d90d29fb83a', 'backend/ecommerce_core/product_source_event.py': 'd61d673f42084354f9b7b740b114d6ead585cbd1fdd0360049846e9ab3d4537e', 'backend/ecommerce_core/product_source_event_window.py': '7368a10ed3f7b10aa418c0dc754eff336d3e463bb0cc1ec00e11ea5092b9f4e3', 'backend/ecommerce_core/product_source_event_window_operation.py': '25a2e42526476daa9dafd38268bb333ef43d1af10fd49114e526caba72c7e39a'}


def replace_once(text,old,new):
    if text.count(old)!=1:raise ValueError('exact candidate marker required')
    return text.replace(old,new,1)


def prepare(destination=CANDIDATES):
    targets=[destination/'domain.ecommerce.core/1.4.0',destination/'solution.ecommerce.growth/1.10.0']
    if any(p.exists() or p.is_symlink() for p in targets):raise ValueError('immutable candidate target exists')
    if any(tree_hash(CANDIDATES/k)!=v for k,v in BASE_HASHES.items()):raise ValueError('candidate baseline drifted')
    sources={k:(AUTHOR/k).read_bytes() for k in SOURCES}
    if any(hashlib.sha256(v).hexdigest()!=SOURCES[k] for k,v in sources.items()):raise ValueError('reviewed source drifted')
    for original,target in zip(BASE_HASHES,targets):
        shutil.copytree(CANDIDATES/original,target,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    core,growth=targets
    for name,value in sources.items():(core/name).write_bytes(value)
    path=core/'bundle.yaml';text=replace_once(path.read_text(),'  version: 1.3.0\n','  version: 1.4.0\n')
    text=replace_once(text,'  contributions:\n','  contributions:\n    - kind: api\n      operationId: ecommerce_core_product_event_windows\n      method: POST\n      path: /ecommerce/core/events/windows\n      mode: exclusive\n')
    path.write_text(text)
    path=growth/'bundle.yaml';text=replace_once(path.read_text(),'  version: 1.9.0\n','  version: 1.10.0\n')
    text=replace_once(text,'      version: ">=1.2.0 <2.0.0"','      version: ">=1.4.0 <2.0.0"');path.write_text(text)
    changed=[]
    for path in sorted((growth/'content/workshops').glob('*.json')):
        text=path.read_text();old='bundle://aos/solution.ecommerce.growth@1.9.0'
        if old in text:
            path.write_text(replace_once(text,old,'bundle://aos/solution.ecommerce.growth@1.10.0'));changed.append(str(path.relative_to(growth)))
    if len(changed)!=8 or any(tree_hash(CANDIDATES/k)!=v for k,v in BASE_HASHES.items()):raise ValueError('history or self references differ')
    return dict(candidates={str(p.relative_to(destination)):tree_hash(p) for p in targets},sourceHashes=SOURCES,updatedSelfReferences=changed)


if __name__=='__main__':print(json.dumps(prepare(),indent=2))
