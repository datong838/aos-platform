#!/usr/bin/env python3
"""Freeze a minimal 1.8 frontend/read successor without changing 1.7."""
from __future__ import annotations

import ast
import hashlib
import json
import shutil
from pathlib import Path

from prepare_ecommerce_growth_1_5_candidate import tree_hash

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'bundles/candidates/ecommerce/solution.ecommerce.growth/1.7.0'
AUTHOR = ROOT / 'bundles/solutions/ecommerce-growth'
TARGET = BASE.parent / '1.8.0'
BASE_HASH = '2ba9ed424307ca1d4bf379656714705429a3efa93b9657d0a3976bd5fbd3a1b1'
SOURCES = {
    'backend/ecommerce_growth/__init__.py': '7e3439197836e0275d343c5a70e25adc7318307ad1d184d2644bf453444423b3',
    'backend/ecommerce_growth/analyst_workspace_view.py': '2103a547d5a20f234980ae63be00ea599beadc978e86ed201df137218ea3c38a',
    'frontend/index.html': '43c779eff6ec959f51b06452a146d96754ef65907c3e2681a656707832b78d77',
}


def prepare(target: Path = TARGET):
    if not isinstance(target, Path) or target.exists() or target.is_symlink():
        raise ValueError('new candidate target must not exist')
    if tree_hash(BASE) != BASE_HASH:
        raise ValueError('immutable 1.7 baseline drifted')
    contents = {path: (AUTHOR / path).read_bytes() for path in SOURCES}
    if any(hashlib.sha256(raw).hexdigest() != SOURCES[path] for path, raw in contents.items()):
        raise ValueError('reviewed author source drifted')
    parsed = ast.parse((BASE / 'backend/ecommerce_growth/__init__.py').read_text())
    declarations = [ast.literal_eval(node.value) for node in parsed.body if isinstance(node, ast.Assign)
                    and any(isinstance(name, ast.Name) and name.id == '_STATIC_CONTRIBUTIONS' for name in node.targets)]
    if len(declarations) != 1 or len(declarations[0]) != 14:
        raise ValueError('baseline registration differs')
    shutil.copytree(BASE, target, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    try:
        for relative, raw in contents.items():
            path = target / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        entry = target / 'backend/ecommerce_growth/__init__.py'
        code = entry.read_text()
        marker = '"contributions": ['
        if code.count(marker) != 1:
            raise ValueError('author registration differs')
        entry.write_text(code.replace(marker, marker[:-1] + '[dict(item) for item in _STATIC_CONTRIBUTIONS] + [', 1)
                         + '\n\n_STATIC_CONTRIBUTIONS = ' + repr(declarations[0]) + '\n')
        ui = dict(schemaVersion='aos.dev/frontend-runtime/v1alpha1', title='经营参谋',
                  entrypoint='frontend/index.html', initialRoute='/workshop/analyst',
                  routeClaims=['/workshop/analyst'], readOperationClaims=['analyst_workspace_view_v1'],
                  commandOperationClaims=[])
        ui_bytes = (json.dumps(ui, ensure_ascii=False, indent=2) + '\n').encode()
        (target / 'frontend/manifest.json').write_bytes(ui_bytes)
        manifest = target / 'bundle.yaml'
        body = manifest.read_text()
        substitutions = {
            '  version: 1.7.0\n': '  version: 1.8.0\n',
            '  dependencies:\n': '    frontend:\n      manifest: frontend/manifest.json\n      artifactHash: sha256:'
                                + hashlib.sha256(ui_bytes).hexdigest() + '\n  dependencies:\n',
            '    dataScopes: []\n': '    dataScopes: [ecommerce.workshop.read]\n',
        }
        for old, new in substitutions.items():
            if body.count(old) != 1:
                raise ValueError('baseline manifest marker differs')
            body = body.replace(old, new, 1)
        body += ('    - kind: api\n      operationId: analyst_workspace_view_v1\n      method: POST\n'
                 '      path: /ecommerce/growth/workspace/view\n      mode: exclusive\n')
        manifest.write_text(body)
        changed_refs = []
        for path in sorted((target / 'content/workshops').glob('*.json')):
            raw = path.read_bytes()
            old = b'bundle://aos/solution.ecommerce.growth@1.7.0'
            if old in raw:
                if raw.count(old) != 1:
                    raise ValueError('ambiguous self reference')
                path.write_bytes(raw.replace(old, b'bundle://aos/solution.ecommerce.growth@1.8.0'))
                changed_refs.append(str(path.relative_to(target)))
        if len(changed_refs) != 8 or tree_hash(BASE) != BASE_HASH:
            raise ValueError('baseline or self references drifted')
        return dict(coordinate='aos/solution.ecommerce.growth@1.8.0', treeHash='sha256:' + tree_hash(target),
                    updatedSelfReferences=changed_refs, sourceHashes=SOURCES)
    except BaseException:
        shutil.rmtree(target)
        raise


if __name__ == '__main__':
    print(json.dumps(prepare(), ensure_ascii=False, indent=2))
